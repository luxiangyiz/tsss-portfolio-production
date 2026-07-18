"""索引构建服务 — 全量/增量构建三类 privacy collection (Manifest V2 per-scope)。"""

import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

from rag_app.core.config import settings
from rag_app.core.exceptions import IngestionError, PrivacyViolationError, RebuildRequiredError
from rag_app.knowledge.chunk_id import make_chunk_id
from rag_app.knowledge.inclusion_policy import InclusionPolicy
from rag_app.knowledge.manifest import Manifest, normalize_relative_path
from rag_app.knowledge.markdown_parser import MarkdownParser
from rag_app.knowledge.metadata_validator import MetadataValidator
from rag_app.knowledge.privacy_router import PrivacyRouter
from rag_app.knowledge.scanner import Scanner
from rag_app.langchain_components.document_factory import kb_file_to_langchain_document
from rag_app.langchain_components.embeddings import create_embeddings
from rag_app.langchain_components.splitter import split_document_with_headings
from rag_app.langchain_components.vector_store import (
    add_documents,
    delete_by_document_id,
    delete_collection,
    get_client,
    get_collection_info,
    ensure_collection,
)
from rag_app.models.documents import KBFile


class IngestionService:
    """知识库索引构建服务 (Manifest V2 per-scope)。"""

    def __init__(self):
        self.scanner = Scanner()
        self.parser = MarkdownParser()
        self.validator = MetadataValidator()
        self.policy = InclusionPolicy()
        self.router = PrivacyRouter()
        self.manifest = Manifest()
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = create_embeddings()
        return self._embeddings

    # ================================================================
    # Public API
    # ================================================================

    def preview(self) -> dict:
        """扫描但不写入，返回预览结果。"""
        entries = self.scanner.scan()
        kb_files = self._parse_and_validate(entries)

        included = []
        excluded = []
        rejected = []
        errors = []

        for kf in kb_files:
            include, reason = self.policy.should_include(kf)
            if include:
                kf.inclusion_status = "included"
                included.append(kf)
            else:
                kf.inclusion_status = "excluded"
                kf.exclusion_reason = reason
                if any(reason.startswith(p) for p in ("invalid", "disputed", "missing", "parse error")):
                    rejected.append(kf)
                else:
                    excluded.append(kf)
            if kf.parse_errors:
                errors.extend(kf.parse_errors)

        stats = {"private": 0, "internal": 0, "public": 0}
        for kf in included:
            stats[kf.frontmatter.privacy_level] = stats.get(kf.frontmatter.privacy_level, 0) + 1

        return {
            "mode": "preview",
            "scope": "all",
            "scanned_files": len(entries),
            "included_files": len(included),
            "excluded_files": len(excluded),
            "rejected_files": len(rejected),
            "included": [
                {
                    "path": f.relative_path,
                    "status": f.inclusion_status,
                    "reason": f.exclusion_reason,
                    "privacy_level": f.frontmatter.privacy_level,
                }
                for f in kb_files
            ],
            "errors": errors,
            "stats_by_privacy": stats,
        }

    def ingest(self, mode: str, scope: str) -> dict:
        """统一的索引入口，分发到 full 或 incremental。"""
        if mode == "full":
            return self.ingest_full(scope)
        elif mode == "incremental":
            return self.ingest_incremental(scope)
        else:
            raise IngestionError(f"Unknown ingest mode: {mode}")

    def ingest_full(self, scope: str = "all") -> dict:
        """全量重建索引 (Manifest V2 per-scope)。

        - scope=all: 删除并重建全部三个 collection，生成完整 V2 manifest
        - scope=private/internal/public: 只删除并重建目标 collection，
          保留其他 scope 的 manifest 记录不变
        """
        start = time.time()
        valid_scopes = {"all", "private", "internal", "public"}
        if scope not in valid_scopes:
            raise IngestionError(f"Unknown scope: {scope}. Must be one of {valid_scopes}")

        entries = self.scanner.scan()
        kb_files = self._parse_and_validate(entries)
        included = [f for f in kb_files if self.policy.should_include(f)[0]]
        rejected = [f for f in kb_files if not self.policy.should_include(f)[0]]

        target_cols = self.router.get_target_collections(scope)

        # 加载现有 manifest
        old_data = self.manifest.load()

        if scope == "all":
            # 全量：清空所有三个 collection
            for col in self.router.get_target_collections("all"):
                delete_collection(col)
                ensure_collection(col)
            # 全量重建 manifest
            chunks_by_col, new_manifest_data = self._index_files_by_scope(
                included, self.router.get_target_collections("all")
            )
            # 直接用全新的 manifest（清除 rebuild_required）
            new_manifest_data["rebuild_required"] = False
            new_manifest_data.pop("migration", None)
            manifest_to_save = new_manifest_data
        else:
            # 局部 scope：只清空目标 collection
            for col in target_cols:
                delete_collection(col)
                ensure_collection(col)

            # 在旧 manifest 中清除目标 scope 的所有记录
            self._clear_scope_from_manifest(old_data, scope)

            # 重建目标 scope
            chunks_by_col, scope_manifest = self._index_files_by_scope(included, target_cols)

            # 将 per-scope 结果合并到旧 manifest（只覆盖目标 scope）
            self._merge_scope_manifest(old_data, scope_manifest, target_cols)
            manifest_to_save = old_data

        self.manifest.save_atomic(manifest_to_save)

        duration = time.time() - start
        total_chunks = sum(chunks_by_col.values())

        errors = []
        for f in kb_files:
            if not f.frontmatter.doc_id:
                errors.append(f"Missing id: {f.relative_path}")
            if f.frontmatter.privacy_level not in ("private", "internal", "public"):
                errors.append(f"Invalid privacy_level: {f.relative_path}")

        return {
            "mode": "full",
            "scope": scope,
            "scanned_files": len(entries),
            "included_files": len(included),
            "excluded_files": len(kb_files) - len(included),
            "rejected_files": len(rejected),
            "total_chunks": total_chunks,
            "chunks_by_collection": chunks_by_col,
            "errors": errors,
            "duration_seconds": round(duration, 2),
            "added_files": len(included),
            "updated_files": 0,
            "metadata_changed_files": 0,
            "deleted_files": 0,
            "skipped_files": 0,
            "written_chunks": total_chunks,
            "deleted_chunks": 0,
        }

    def ingest_incremental(self, scope: str = "all") -> dict:
        """增量更新索引 (Manifest V2 per-scope)。

        对每个目标 Collection 独立判断：added / content_changed / metadata_changed / removed。
        只修改目标 scope 的 manifest 记录。
        """
        start = time.time()
        valid_scopes = {"all", "private", "internal", "public"}
        if scope not in valid_scopes:
            raise IngestionError(f"Unknown scope: {scope}. Must be one of {valid_scopes}")

        entries = self.scanner.scan()
        kb_files = self._parse_and_validate(entries)
        included = [f for f in kb_files if self.policy.should_include(f)[0]]

        target_cols = self.router.get_target_collections(scope)
        old_data = self.manifest.load()

        # 检查 rebuild_required 状态
        if old_data.get("rebuild_required"):
            raise RebuildRequiredError(
                "Manifest 处于未校准状态（V1 迁移后未执行 full(all)）。"
                " 请先执行 full(all) 重建所有 Collection。"
            )

        # 计算哈希
        new_hashes: dict[str, str] = {}
        new_metadata: dict[str, str] = {}
        file_tuples: list[tuple] = []
        for f in included:
            try:
                h = hashlib.sha256(f.body_text.encode("utf-8")).hexdigest()[:16]
            except Exception:
                h = ""
            mh = self.manifest.compute_metadata_hash({
                "privacy_level": f.frontmatter.privacy_level,
                "verification_status": f.frontmatter.verification_status,
                "publish_status": f.frontmatter.publish_status,
                "review_status": f.frontmatter.review_status,
            })
            new_hashes[f.relative_path] = h
            new_metadata[f.relative_path] = mh
            file_tuples.append((f.absolute_path, f.relative_path))

        # 构建 lookup
        included_by_rel: dict[str, KBFile] = {}
        for f in included:
            rp = normalize_relative_path(f.relative_path)
            included_by_rel[rp] = f

        added_rels: set[str] = set()
        updated_rels: set[str] = set()
        metadata_changed_rels: set[str] = set()
        deleted_rels: set[str] = set()
        total_written = 0
        total_deleted_chunks = 0
        chunks_by_col: dict[str, int] = {}
        processed_rels: set[str] = set()  # 实际被处理过的文件路径

        for col in target_cols:
            added, content_changed, meta_changed, removed = self.manifest.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, col
            )

            # 检测隐私迁移导致的"资格变化"移除
            privacy_removed = self._find_privacy_removals(included_by_rel, old_data, col)
            # 合并 removed
            all_removed = set(removed) | set(privacy_removed)

            now = datetime.now(timezone.utc).isoformat()

            # --- 处理 removed ---
            for rel_path in all_removed:
                doc = old_data.get("documents", {}).get(rel_path, {})
                old_doc_id = doc.get("document_id", "")
                old_entry = self.manifest.get_scope_entry(old_data, rel_path, col)
                if old_doc_id:
                    delete_by_document_id(col, old_doc_id)
                    total_deleted_chunks += len(old_entry.get("chunk_ids", [])) if old_entry else 0
                self.manifest.remove_scope_entry(old_data, rel_path, col)
                normalized_rel = normalize_relative_path(rel_path)
                processed_rels.add(normalized_rel)
                deleted_rels.add(normalized_rel)

            # --- 处理 content_changed + metadata_changed ---
            changed = set(content_changed) | set(meta_changed)
            for abs_path in changed:
                rel_path = self._rel_path_of(abs_path, file_tuples)
                kf = included_by_rel.get(normalize_relative_path(rel_path))
                if not kf:
                    continue

                # 检查路由资格
                routed_cols = self.router.route(kf)
                if col not in routed_cols:
                    # 不再有资格 → 移除
                    old_doc_id, old_entry = self._get_document_state(old_data, rel_path, col)
                    if old_entry:
                        if old_doc_id:
                            delete_by_document_id(col, old_doc_id)
                            total_deleted_chunks += len(old_entry.get("chunk_ids", []))
                        self.manifest.remove_scope_entry(old_data, rel_path, col)
                    continue

                # 删除旧向量
                old_doc_id, old_entry = self._get_document_state(old_data, rel_path, col)
                if old_doc_id:
                    delete_by_document_id(col, old_doc_id)
                    total_deleted_chunks += len(old_entry.get("chunk_ids", [])) if old_entry else 0

                # 重新索引
                self.router.check_no_private_in_public(col, kf)
                chunk_results = self._index_single_file(kf, [col])
                if col in chunk_results:
                    scope_entry = chunk_results[col]
                    self.manifest.set_scope_entry(old_data, rel_path, col, {
                        "document_id": kf.frontmatter.doc_id,
                        **scope_entry,
                    })
                    chunks_by_col[col] = chunks_by_col.get(col, 0) + len(scope_entry.get("chunk_ids", []))
                    total_written += len(scope_entry.get("chunk_ids", []))
                    processed_rels.add(normalize_relative_path(rel_path))

                # 统计
                normalized_rel = normalize_relative_path(rel_path)
                if abs_path in content_changed:
                    updated_rels.add(normalized_rel)
                else:
                    metadata_changed_rels.add(normalized_rel)

            # --- 处理 added ---
            for abs_path in added:
                rel_path = self._rel_path_of(abs_path, file_tuples)
                kf = included_by_rel.get(normalize_relative_path(rel_path))
                if not kf:
                    continue

                routed_cols = self.router.route(kf)
                if col not in routed_cols:
                    continue

                self.router.check_no_private_in_public(col, kf)
                chunk_results = self._index_single_file(kf, [col])
                if col in chunk_results:
                    scope_entry = chunk_results[col]
                    self.manifest.set_scope_entry(old_data, rel_path, col, {
                        "document_id": kf.frontmatter.doc_id,
                        **scope_entry,
                    })
                    chunks_by_col[col] = chunks_by_col.get(col, 0) + len(scope_entry.get("chunk_ids", []))
                    total_written += len(scope_entry.get("chunk_ids", []))
                    normalized_rel = normalize_relative_path(rel_path)
                    processed_rels.add(normalized_rel)
                    added_rels.add(normalized_rel)

        # --- 计算 skipped ---
        all_included_rels = {normalize_relative_path(f.relative_path) for f in included}
        total_skipped = len(all_included_rels - processed_rels)

        self.manifest.save_atomic(old_data)

        duration = time.time() - start
        total_chunks = sum(chunks_by_col.values())

        return {
            "mode": "incremental",
            "scope": scope,
            "scanned_files": len(entries),
            "included_files": len(included),
            "excluded_files": len(kb_files) - len(included),
            "rejected_files": sum(1 for f in kb_files if not self.policy.should_include(f)[0]),
            "total_chunks": total_chunks,
            "chunks_by_collection": chunks_by_col,
            "errors": [],
            "duration_seconds": round(duration, 2),
            "added_files": len(added_rels),
            "updated_files": len(updated_rels),
            "metadata_changed_files": len(metadata_changed_rels),
            "deleted_files": len(deleted_rels),
            "skipped_files": total_skipped,
            "written_chunks": total_written,
            "deleted_chunks": total_deleted_chunks,
        }

    @staticmethod
    def _rel_path_of(abs_path: str, file_tuples: list[tuple]) -> str:
        for ap, rp in file_tuples:
            if ap == abs_path:
                return rp
        return ""

    def get_stats(self) -> dict:
        """获取索引统计。"""
        cols = self.router.get_target_collections("all")
        result = {}
        for col in cols:
            result[col] = get_collection_info(col)
        return result

    # ================================================================
    # Internal helpers
    # ================================================================

    @staticmethod
    def _get_document_state(manifest_data: dict, relative_path: str, collection: str) -> tuple:
        """返回 (document_id, scope_entry)，统一读取文档层和 scope 层。"""
        from rag_app.knowledge.manifest import normalize_relative_path
        rp = normalize_relative_path(relative_path)
        doc = manifest_data.get("documents", {}).get(rp, {})
        doc_id = doc.get("document_id", "")
        scope_entry = doc.get("scopes", {}).get(collection)
        return doc_id, scope_entry

    # ================================================================
    # Internal
    # ================================================================

    def _parse_and_validate(self, entries) -> list[KBFile]:
        result: list[KBFile] = []
        for entry in entries:
            kf = self.parser.parse(entry)
            errs = self.validator.validate(kf)
            if errs:
                kf.parse_errors.extend(errs)
            result.append(kf)
        return result

    def _build_metadata_dict(self, kf: KBFile) -> dict:
        """构建用于元数据哈希的 dict。"""
        return {
            "privacy_level": kf.frontmatter.privacy_level,
            "verification_status": kf.frontmatter.verification_status,
            "publish_status": kf.frontmatter.publish_status,
            "review_status": kf.frontmatter.review_status,
        }

    def _index_files_by_scope(
        self, kb_files: list[KBFile], target_cols: list[str]
    ) -> tuple[dict, dict]:
        """将文件切分并按 scope 写入对应 collection。

        返回:
        - chunks_by_col: {collection_name: chunk_count}
        - manifest_data: 完整 V2 manifest dict (含 schema_version/documents)
        """
        chunks_by_col: dict[str, int] = {}
        manifest_data = self.manifest.empty_v2()

        for kf in kb_files:
            routed_cols = self.router.route(kf)
            if not routed_cols:
                continue

            # 过滤只写目标 collection
            write_cols = [c for c in routed_cols if c in target_cols]
            if not write_cols:
                continue

            chunk_results = self._index_single_file(kf, write_cols)

            rp = normalize_relative_path(kf.relative_path)

            # 构建 manifest 条目
            if rp not in manifest_data["documents"]:
                manifest_data["documents"][rp] = {
                    "document_id": kf.frontmatter.doc_id,
                    "scopes": {},
                }

            for col, entry in chunk_results.items():
                manifest_data["documents"][rp]["scopes"][col] = {
                    "content_hash": entry["content_hash"],
                    "metadata_hash": entry["metadata_hash"],
                    "chunk_ids": entry["chunk_ids"],
                    "indexed_at": entry["indexed_at"],
                }
                chunks_by_col[col] = chunks_by_col.get(col, 0) + len(entry["chunk_ids"])

        return chunks_by_col, manifest_data

    def _index_single_file(
        self, kf: KBFile, write_cols: list[str]
    ) -> dict[str, dict]:
        """索引单个文件到指定 collections，返回 {col: {content_hash, metadata_hash, chunk_ids, indexed_at}}。"""
        result: dict[str, dict] = {}
        now = datetime.now(timezone.utc).isoformat()

        try:
            content_hash = hashlib.sha256(kf.body_text.encode("utf-8")).hexdigest()[:16]
        except Exception:
            content_hash = ""

        metadata_hash = self.manifest.compute_metadata_hash(self._build_metadata_dict(kf))

        # 转为 LangChain Document
        lc_doc = kb_file_to_langchain_document(kf)

        # 按标题切分
        chunks = split_document_with_headings(lc_doc)

        # 为每个 chunk 补充 metadata
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = total

        for col in write_cols:
            self.router.check_no_private_in_public(col, kf)
            chunk_ids = add_documents(col, chunks, self.embeddings)
            result[col] = {
                "content_hash": content_hash,
                "metadata_hash": metadata_hash,
                "chunk_ids": chunk_ids,
                "indexed_at": now,
            }

        return result

    def _clear_scope_from_manifest(self, data: dict, scope: str) -> None:
        """从 manifest 中清除指定 scope 的所有记录。"""
        col = self._scope_to_collection(scope)
        for rp in list(data.get("documents", {}).keys()):
            self.manifest.remove_scope_entry(data, rp, col)

    def _merge_scope_manifest(
        self, base_data: dict, scope_data: dict, target_cols: list[str]
    ) -> None:
        """将 scope_data 中的 per-scope 记录合并到 base_data（只覆盖 target_cols 的 scope）。"""
        for rp, doc in scope_data.get("documents", {}).items():
            for col in target_cols:
                scope_entry = doc.get("scopes", {}).get(col)
                if scope_entry:
                    self.manifest.set_scope_entry(base_data, rp, col, {
                        "document_id": doc.get("document_id", ""),
                        **scope_entry,
                    })

    def _find_privacy_removals(
        self,
        included_by_rel: dict[str, KBFile],
        old_data: dict,
        col: str,
    ) -> list[str]:
        """检测因隐私/发布状态变化，应从 col 移除但文件仍存在的路径。"""
        removals: list[str] = []
        for rp, doc in old_data.get("documents", {}).items():
            scope_entry = doc.get("scopes", {}).get(col)
            if not scope_entry:
                continue

            kf = included_by_rel.get(rp)
            if kf is None:
                continue  # 文件已物理删除，由常规 removed 处理

            # 检查当前路由资格
            routed = self.router.route(kf)
            if col not in routed:
                removals.append(rp)

        return removals

    def _scope_to_collection(self, scope: str) -> str:
        """将 short scope 名映射到 collection 名。"""
        mapping = {
            "private": "kb_private",
            "internal": "kb_internal",
            "public": "kb_public",
            "all": "all",
        }
        return mapping.get(scope, scope)
