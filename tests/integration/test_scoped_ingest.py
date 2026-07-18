"""集成测试 — scope 隔离：验证 scope=internal 时只操作 kb_internal，不删除/改写 kb_private/kb_public。"""

import os
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from tests.fixtures.fake_embeddings import FakeEmbeddings

FAKE_DIM = 128


def _fake_emb():
    return FakeEmbeddings(dimension=FAKE_DIM)


def _make_md_file(dir_path, rel_path, doc_id, title, body,
                  privacy="internal", verification="pending",
                  publish="draft", review="pending"):
    full_path = os.path.join(dir_path, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    content = f"""---
doc_id: {doc_id}
title: {title}
privacy_level: {privacy}
verification_status: {verification}
publish_status: {publish}
review_status: {review}
category: test
tags: []
ai_generated: false
updated: "2025-01-01"
---

# {title}

{body}
"""
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return full_path


def _setup_config(kb_dir, data_dir):
    import rag_app.core.config as config_mod
    config_mod.settings.kb_root = kb_dir
    config_mod.settings.rag_data_dir = data_dir
    config_mod.settings.qdrant_path = os.path.join(data_dir, "qdrant")
    config_mod.settings.embedding_dimension = FAKE_DIM
    # Allow all dirs (temp KB doesn't match production include_dirs)
    config_mod.settings.yaml_config.setdefault("knowledge_base", {})["include_dirs"] = []


class TestScopedFullInternal:
    """scope=internal 时只操作 kb_internal。"""

    def test_internal_does_not_delete_other_collections(self):
        """full(internal) 后 kb_private 数据应保持不变。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_int_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_int_")
        try:
            _make_md_file(kb_dir, "01-test/private_doc.md", "kb-priv", "Private Doc",
                          "private content here.", privacy="private")
            _make_md_file(kb_dir, "01-test/internal_doc.md", "kb-int", "Internal Doc",
                          "internal content here.", privacy="internal")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService

                svc = IngestionService()
                svc._embeddings = emb
                svc.ingest_full("all")

                info_all = {k: v.get("points_count", 0) for k, v in svc.get_stats().items()}
                assert info_all.get("kb_private", 0) > 0, "kb_private should have data"
                assert info_all.get("kb_internal", 0) > 0, "kb_internal should have data"

                svc2 = IngestionService()
                svc2._embeddings = emb
                result = svc2.ingest_full("internal")

                assert "kb_internal" in str(result["chunks_by_collection"])

                info2 = {k: v.get("points_count", 0) for k, v in svc2.get_stats().items()}
                assert info2.get("kb_private", 0) > 0, \
                    f"scope=internal must not delete kb_private: {info2}"
                assert info2.get("kb_internal", 0) > 0, "kb_internal should have data"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_internal_preserves_private_point_count(self):
        """scope=internal 重建后 kb_private point 数不变。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_int2_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_int2_")
        try:
            _make_md_file(kb_dir, "01-test/private_doc.md", "kb-priv2", "Private Doc 2",
                          "private 2.", privacy="private")
            _make_md_file(kb_dir, "01-test/internal_doc.md", "kb-int2", "Internal Doc 2",
                          "internal 2.", privacy="internal")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService

                svc = IngestionService()
                svc._embeddings = emb
                svc.ingest_full("all")
                stats_before = svc.get_stats()
                private_before = stats_before["kb_private"]["points_count"]

                svc2 = IngestionService()
                svc2._embeddings = emb
                svc2.ingest_full("internal")
                stats_after = svc2.get_stats()
                private_after = stats_after["kb_private"]["points_count"]

                assert private_after == private_before, \
                    f"kb_private must not change: before={private_before}, after={private_after}"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestScopedFullPrivate:
    """scope=private 时只操作 kb_private。"""

    def test_private_does_not_delete_internal(self):
        """full(private) 后 kb_internal 数据应保持不变。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_priv_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_priv_")
        try:
            _make_md_file(kb_dir, "01-test/private_doc.md", "kb-priv3", "P Doc",
                          "private.", privacy="private")
            _make_md_file(kb_dir, "01-test/internal_doc.md", "kb-int3", "I Doc",
                          "internal.", privacy="internal")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService

                svc = IngestionService()
                svc._embeddings = emb
                svc.ingest_full("all")
                stats_before = svc.get_stats()

                svc2 = IngestionService()
                svc2._embeddings = emb
                svc2.ingest_full("private")
                stats_after = svc2.get_stats()

                internal_before = stats_before["kb_internal"]["points_count"]
                internal_after = stats_after["kb_internal"]["points_count"]
                assert internal_after == internal_before, \
                    f"kb_internal must not change: before={internal_before}, after={internal_after}"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestScopedFullPublic:
    """scope=public 时只操作 kb_public。"""

    def test_public_collection_exists(self):
        """scope=public 时三 collection 均存在。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_pub_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_pub_")
        try:
            _make_md_file(kb_dir, "01-test/internal_doc.md", "kb-int4", "I Doc",
                          "internal.", privacy="internal")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService

                svc = IngestionService()
                svc._embeddings = emb
                svc.ingest_full("all")

                svc2 = IngestionService()
                svc2._embeddings = emb
                svc2.ingest_full("public")
                stats = svc2.get_stats()

                assert "kb_public" in stats, "kb_public should be in stats"
                assert "kb_private" in stats, "kb_private should be in stats"
                assert "kb_internal" in stats, "kb_internal should be in stats"
                assert stats["kb_public"]["points_count"] >= 0
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestUnknownScopeRejected:
    """未知 scope 应报错。"""

    def test_unknown_scope_raises(self):
        """scope=unknown 应抛出 IngestionError。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_unk_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_unk_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A", "body.")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService
                from rag_app.core.exceptions import IngestionError

                svc = IngestionService()
                svc._embeddings = emb

                with pytest.raises(IngestionError, match="Unknown scope"):
                    svc.ingest_full("unknown")
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestManifestMergeOnScoped:
    """局部 scope 构建时 manifest 正确合并。"""

    def test_manifest_preserves_other_scope_entries(self):
        """scope=internal 不应丢失 private 文件的 manifest 条目。"""
        kb_dir = tempfile.mkdtemp(prefix="rag_scope_mani_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_mani_")
        try:
            _make_md_file(kb_dir, "01-test/private_doc.md", "kb-priv5", "P Doc",
                          "private.", privacy="private")
            _make_md_file(kb_dir, "01-test/internal_doc.md", "kb-int5", "I Doc",
                          "internal.", privacy="internal")

            _setup_config(kb_dir, data_dir)

            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService
                from rag_app.knowledge.manifest import Manifest

                svc = IngestionService()
                svc._embeddings = emb
                svc.ingest_full("all")

                m1 = Manifest()
                m1._path = svc.manifest._path
                before = m1.load()
                before_count = len(before.get("documents", {}))

                svc2 = IngestionService()
                svc2._embeddings = emb
                svc2.ingest_full("internal")

                m2 = Manifest()
                m2._path = svc2.manifest._path
                after = m2.load()
                after_docs = after.get("documents", {})
                assert len(after_docs) == before_count, \
                    f"manifest entry count must not change: before={before_count}, after={len(after_docs)}"
                assert "01-test/private_doc.md" in after_docs or "01-test\\private_doc.md" in after_docs, "private file entry must not be lost"
                assert "01-test/internal_doc.md" in after_docs or "01-test\\internal_doc.md" in after_docs, "internal file entry must not be lost"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)
