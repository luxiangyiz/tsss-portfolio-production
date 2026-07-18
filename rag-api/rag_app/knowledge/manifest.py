"""索引清单 — 记录已索引文件的哈希，支持增量更新。

存放于 data/rag/manifest.json

V2 schema:
{
  "schema_version": 2,
  "updated_at": "2026-07-16T08:00:00+00:00",
  "documents": {
    "relative/path.md": {
      "document_id": "...",
      "scopes": {
        "kb_private": {
          "content_hash": "...",
          "metadata_hash": "...",
          "chunk_ids": [...],
          "indexed_at": "..."
        },
        "kb_internal": { ... },
        "kb_public": { ... }
      }
    }
  }
}
"""

import hashlib
import json
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rag_app.core.config import settings
from rag_app.core.exceptions import ManifestMigrationError


# ---- 常量 ----

VALID_SCOPES = {"kb_private", "kb_internal", "kb_public"}

# 用于原子写入的进程内锁
_write_lock = threading.Lock()


# ---- 工具函数 ----

def normalize_relative_path(path: str) -> str:
    """统一使用 /，避免 Windows \\ 导致重复条目。"""
    return path.replace("\\", "/")


# ---- Manifest V2 操作 ----

class Manifest:
    """管理已索引文件的哈希清单 (V2 per-scope schema)。"""

    def __init__(self, path: Optional[Path] = None):
        if path is not None:
            self._path = Path(path)
        else:
            self._path = Path(settings.rag_data_dir) / "manifest.json"

    # ================================================================
    # 基础 I/O
    # ================================================================

    @staticmethod
    def empty_v2() -> dict:
        """返回标准空 V2 结构。"""
        return {
            "schema_version": 2,
            "updated_at": "",
            "rebuild_required": False,
            "documents": {},
        }

    def load(self) -> dict:
        """加载 manifest。

        - 文件不存在 → 返回空 V2
        - V1 格式 → 自动迁移并返回 V2（同时创建备份）
        - V2 格式 → 验证后返回
        - JSON 损坏 / 未知结构 → 抛出 ValueError
        """
        if not self._path.exists():
            return self.empty_v2()

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Manifest 文件损坏，无法解析: {self._path} — {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Manifest 结构非法: 顶层不是对象 — {self._path}")

        version = self.detect_version(data)

        if version == 1:
            return self.migrate_v1_to_v2(data)

        if version == 2:
            self._validate_v2(data)
            return data

        raise ValueError(f"Manifest 未知版本: {version} — {self._path}")

    def save_atomic(self, data: dict) -> None:
        """原子保存：临时文件 → flush → 原子替换。

        写入前验证 V2 结构，更新 updated_at。
        """
        self._validate_v2(data)

        now = datetime.now(timezone.utc).isoformat()
        data["updated_at"] = now
        data["schema_version"] = 2

        json_text = json.dumps(data, ensure_ascii=False, indent=2)

        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)

        with _write_lock:
            # 写入同名目录下的临时文件
            fd, tmp_path = tempfile.mkstemp(
                dir=str(parent),
                prefix=".manifest-",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json_text)
                    f.flush()
                    os.fsync(f.fileno())
                # 原子替换（os.replace 是原子操作，跨平台）
                os.replace(tmp_path, str(self._path))
            except Exception:
                # 清理临时文件
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise

    # ================================================================
    # 版本检测
    # ================================================================

    @staticmethod
    def detect_version(data: dict) -> int:
        """检测 manifest 版本。

        - V2: 含有 "schema_version" 键，值为 2
        - V1: 不含 schema_version，且顶层键为文件路径（条目含 indexed_scopes）
        - 无法识别则抛出 ValueError
        """
        if "schema_version" in data:
            v = data["schema_version"]
            if v == 2:
                return 2
            raise ValueError(f"不支持的 manifest schema_version: {v}")

        # 检测 V1：顶层有文件路径条目，且条目中含 indexed_scopes
        if data and isinstance(data, dict):
            sample_key = next(iter(data))
            sample_val = data.get(sample_key)
            if isinstance(sample_val, dict) and "indexed_scopes" in sample_val:
                return 1

        raise ValueError("无法识别 manifest 版本：缺少 schema_version 且不匹配 V1 特征")

    # ================================================================
    # V2 验证
    # ================================================================

    def _validate_v2(self, data: dict) -> None:
        """验证 V2 结构完整性（顶层、文档层、scope 层）。"""
        if not isinstance(data, dict):
            raise ValueError("Manifest V2 顶层必须是 dict")
        if data.get("schema_version") != 2:
            raise ValueError(f"Manifest schema_version 必须为 2，实际: {data.get('schema_version')}")
        if "documents" not in data or not isinstance(data["documents"], dict):
            raise ValueError("Manifest V2 缺少 documents 字段或格式错误")
        if "rebuild_required" in data and not isinstance(data["rebuild_required"], bool):
            raise ValueError("Manifest rebuild_required 必须是 bool")

        docs = data["documents"]
        for path, doc in docs.items():
            # 文档路径校验
            if not isinstance(path, str) or not path:
                raise ValueError(f"Manifest 文档路径不能为空: {path!r}")
            if "\\" in path:
                raise ValueError(f"Manifest 文档路径不得含反斜杠: {path!r}")
            if not isinstance(doc, dict):
                raise ValueError(f"Manifest 文档条目必须是 dict: {path}")
            if not isinstance(doc.get("document_id"), str) or not doc["document_id"]:
                raise ValueError(f"Manifest 文档 document_id 不能为空: {path}")
            scopes = doc.get("scopes")
            if not isinstance(scopes, dict):
                raise ValueError(f"Manifest 文档 scopes 必须是 dict: {path}")

            for scope_name, scope_entry in scopes.items():
                if scope_name not in VALID_SCOPES:
                    raise ValueError(f"Manifest 非法 scope: {scope_name} in {path}")
                if not isinstance(scope_entry, dict):
                    raise ValueError(f"Manifest scope entry 必须是 dict: {path}/{scope_name}")

                # content_hash 非空
                if not isinstance(scope_entry.get("content_hash"), str) or not scope_entry["content_hash"]:
                    raise ValueError(f"Manifest content_hash 不能为空: {path}/{scope_name}")
                # metadata_hash 非空
                if not isinstance(scope_entry.get("metadata_hash"), str) or not scope_entry["metadata_hash"]:
                    raise ValueError(f"Manifest metadata_hash 不能为空: {path}/{scope_name}")
                # chunk_ids 必须是 list[str]，不含空字符串和重复项
                chunk_ids = scope_entry.get("chunk_ids")
                if not isinstance(chunk_ids, list):
                    raise ValueError(f"Manifest chunk_ids 必须是 list: {path}/{scope_name}")
                if any(not isinstance(c, str) or not c for c in chunk_ids):
                    raise ValueError(f"Manifest chunk_ids 不得含空字符串: {path}/{scope_name}")
                if len(chunk_ids) != len(set(chunk_ids)):
                    raise ValueError(f"Manifest chunk_ids 不得含重复项: {path}/{scope_name}")
                # indexed_at 非空
                indexed_at = scope_entry.get("indexed_at")
                if not isinstance(indexed_at, str) or not indexed_at:
                    raise ValueError(f"Manifest indexed_at 不能为空: {path}/{scope_name}")
                try:
                    datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(
                        f"Manifest indexed_at 必须是合法 ISO 8601: {path}/{scope_name}"
                    ) from exc

    # ================================================================
    # Per-scope 存取
    # ================================================================

    @staticmethod
    def get_scope_entry(data: dict, relative_path: str, collection: str) -> Optional[dict]:
        """获取某文档在某 Collection 的 scope 记录，不存在返回 None。"""
        rp = normalize_relative_path(relative_path)
        doc = data.get("documents", {}).get(rp)
        if not doc:
            return None
        return doc.get("scopes", {}).get(collection)

    @staticmethod
    def set_scope_entry(data: dict, relative_path: str, collection: str, entry: dict) -> None:
        """设置某文档在某 Collection 的 scope 记录。

        同时确保 documents 和文档级别的 document_id 存在。
        """
        rp = normalize_relative_path(relative_path)
        if "documents" not in data:
            data["documents"] = {}

        if rp not in data["documents"]:
            data["documents"][rp] = {
                "document_id": entry.get("document_id", ""),
                "scopes": {},
            }

        doc = data["documents"][rp]
        # 保持 document_id 一致
        if entry.get("document_id") and not doc.get("document_id"):
            doc["document_id"] = entry["document_id"]

        if "scopes" not in doc:
            doc["scopes"] = {}

        doc["scopes"][collection] = {
            "content_hash": entry.get("content_hash", ""),
            "metadata_hash": entry.get("metadata_hash", ""),
            "chunk_ids": entry.get("chunk_ids", []),
            "indexed_at": entry.get("indexed_at", ""),
        }

    @staticmethod
    def remove_scope_entry(data: dict, relative_path: str, collection: str) -> None:
        """移除某文档在某 Collection 的 scope 记录。

        如果该文档已无任何 scope 记录，从 documents 中移除。
        """
        rp = normalize_relative_path(relative_path)
        doc = data.get("documents", {}).get(rp)
        if not doc:
            return
        doc.get("scopes", {}).pop(collection, None)
        if not doc.get("scopes"):
            data["documents"].pop(rp, None)

    # ================================================================
    # V1 → V2 迁移
    # ================================================================

    def migrate_v1_to_v2(self, v1_data: dict) -> dict:
        """将 V1 manifest 迁移到 V2 结构。

        迁移规则：
        1. 在同目录创建备份 (manifest.v1.backup-{timestamp}.json)
        2. 将 V1 的 indexed_scopes 逐个转为 scopes.<collection>
        3. 设置 rebuild_required=true，强制 full(all) 校准
        4. 迁移后只能执行 full(all)，所有 incremental 被拒绝

        返回 V2 结构 dict。
        """
        # 创建备份（失败应抛出异常阻断）
        self._backup_v1()

        v2 = self.empty_v2()
        now = datetime.now(timezone.utc).isoformat()

        # 标记为需要重建
        v2["rebuild_required"] = True
        v2["migration"] = {
            "from_version": 1,
            "migrated_at": now,
            "reason": "v1_scope_state_untrusted",
        }

        for rel_path, entry in v1_data.items():
            rp = normalize_relative_path(rel_path)
            doc_id = entry.get("document_id", "")
            content_hash = entry.get("content_hash", "") or "unknown"
            metadata_hash = entry.get("metadata_hash", "") or "unknown"
            chunk_ids = entry.get("chunk_ids", [])
            indexed_scopes = entry.get("indexed_scopes", [])
            indexed_at = entry.get("indexed_at", "") or now

            scopes: dict = {}
            for scope_name in indexed_scopes:
                if scope_name in VALID_SCOPES:
                    scopes[scope_name] = {
                        "content_hash": content_hash,
                        "metadata_hash": metadata_hash,
                        "chunk_ids": list(chunk_ids) if chunk_ids else [],
                        "indexed_at": indexed_at,
                    }

            if scopes:
                v2["documents"][rp] = {
                    "document_id": doc_id,
                    "scopes": scopes,
                }

        # 原子保存迁移结果
        self.save_atomic(v2)
        return v2

    def _backup_v1(self) -> Optional[str]:
        """创建 V1 manifest 备份。

        备份失败时抛出 ManifestMigrationError，阻断迁移。
        """
        if not self._path.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"manifest.v1.backup-{timestamp}.json"
        backup_path = self._path.parent / backup_name

        # 如果这个时间戳的备份已存在，不覆盖
        if backup_path.exists():
            return str(backup_path)

        try:
            shutil.copy2(str(self._path), str(backup_path))
            return str(backup_path)
        except OSError as e:
            # 清理可能的不完整备份
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ManifestMigrationError(
                f"V1 备份失败: {self._path} -> {backup_path}: {e}"
            ) from e

    # ================================================================
    # 哈希计算
    # ================================================================

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """计算文件内容的 SHA256（完整 64 字符 hex）。"""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except IOError:
            return ""

    @staticmethod
    def compute_metadata_hash(metadata: dict) -> str:
        """计算 metadata 的 SHA256 前 16 字符（用于检测元数据变化）。"""
        raw = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # ================================================================
    # Per-scope 变更检测
    # ================================================================

    def find_changed_for_scope(
        self,
        file_tuples: list[tuple],
        new_hashes: dict[str, str],
        new_metadata: dict[str, str],
        scope: str,
    ) -> tuple[list, list, list, list]:
        """对比指定 scope 的清单，返回 (added, content_changed, metadata_changed, removed)。

        对每个目标 Collection 独立比较：
        - added: 当前应进入该 scope，但没有 scope 记录
        - content_changed: 正文哈希不同
        - metadata_changed: 元数据哈希不同
        - removed: 文件删除，或当前已不再有资格进入该 scope（由调用方处理）

        返回的都是 absolute_path 列表（removed 是 relative_path 列表）。
        """
        data = self.load()
        added: list[str] = []
        content_changed: list[str] = []
        metadata_changed: list[str] = []

        new_rel_paths: set[str] = set()

        for abs_path, rel_path in file_tuples:
            rp = normalize_relative_path(rel_path)
            new_rel_paths.add(rp)

            h = new_hashes.get(rel_path, "")
            mh = new_metadata.get(rel_path, "")

            scope_entry = self.get_scope_entry(data, rp, scope)

            if scope_entry is None:
                # 没有该 scope 的 historical 记录 → added
                added.append(abs_path)
            elif scope_entry.get("content_hash") != h:
                content_changed.append(abs_path)
            elif scope_entry.get("metadata_hash") != mh:
                metadata_changed.append(abs_path)

        # removed: 旧 manifest 中有 scope 记录，但文件系统中已不存在
        removed: list[str] = []
        for rp, doc in data.get("documents", {}).items():
            if rp not in new_rel_paths:
                if scope in doc.get("scopes", {}):
                    removed.append(rp)

        return added, content_changed, metadata_changed, removed


# 保留旧版别名以兼容历史调用（逐步弃用）
ManifestEntry = None  # type: ignore
