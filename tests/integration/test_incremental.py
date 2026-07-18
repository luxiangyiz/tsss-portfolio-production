"""集成测试 — 增量更新端到端，使用临时目录 + FakeEmbeddings。

覆盖：全量构建 / 无变化增量 / 新增文件 / 修改正文 / 删除文件
"""

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
    """Setup settings for temp KB dir; must be called before importing services."""
    import rag_app.core.config as config_mod
    config_mod.settings.kb_root = kb_dir
    config_mod.settings.rag_data_dir = data_dir
    config_mod.settings.qdrant_path = os.path.join(data_dir, "qdrant")
    config_mod.settings.embedding_dimension = FAKE_DIM
    # Allow all dirs (temp KB doesn't match production include_dirs)
    config_mod.settings.yaml_config.setdefault("knowledge_base", {})["include_dirs"] = []


class TestIncrementalFullBuild:
    """Full build and no-change incremental."""

    def test_full_build_and_stats(self):
        kb_dir = tempfile.mkdtemp(prefix="rag_incr_full_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_full_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A",
                          "text AAA for full build test.")
            _make_md_file(kb_dir, "01-test/doc_b.md", "kb-b", "Doc B",
                          "text BBB, second test file.")

            _setup_config(kb_dir, data_dir)
            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService
                svc = IngestionService()
                svc._embeddings = emb
                result = svc.ingest_full("all")

            assert result["mode"] == "full"
            assert result["scanned_files"] == 2
            assert result["included_files"] == 2
            assert result["added_files"] == 2
            assert result["updated_files"] == 0
            assert result["metadata_changed_files"] == 0
            assert result["deleted_files"] == 0
            assert result["skipped_files"] == 0
            assert result["written_chunks"] > 0
            assert result["deleted_chunks"] == 0
            assert result["total_chunks"] > 0
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_no_change_incremental_writes_zero(self):
        kb_dir = tempfile.mkdtemp(prefix="rag_incr_nochg_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_nochg_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A",
                          "text AAA for no-change test.")
            _make_md_file(kb_dir, "01-test/doc_b.md", "kb-b", "Doc B",
                          "text BBB, second file.")

            _setup_config(kb_dir, data_dir)
            emb = _fake_emb()
            with (
                patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=emb),
                patch("rag_app.services.ingestion_service.create_embeddings", return_value=emb),
            ):
                from rag_app.services.ingestion_service import IngestionService

                svc1 = IngestionService()
                svc1._embeddings = emb
                r1 = svc1.ingest_full("all")
                assert r1["written_chunks"] > 0

                svc2 = IngestionService()
                svc2._embeddings = emb
                r2 = svc2.ingest_incremental("all")

            assert r2["mode"] == "incremental"
            assert r2["written_chunks"] == 0, f"no-change should write 0, got {r2['written_chunks']}"
            assert r2["skipped_files"] == r2["included_files"],                 f"should skip all: skipped={r2['skipped_files']}, included={r2['included_files']}"
            assert r2["added_files"] == 0
            assert r2["updated_files"] == 0
            assert r2["deleted_files"] == 0
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestIncrementalAddFile:
    def test_add_file_detected(self):
        kb_dir = tempfile.mkdtemp(prefix="rag_incr_add_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_add_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A", "text AAA.")

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

                _make_md_file(kb_dir, "01-test/doc_c.md", "kb-c", "Doc C",
                              "new file text CCC.")

                svc2 = IngestionService()
                svc2._embeddings = emb
                r = svc2.ingest_incremental("all")

            assert r["added_files"] >= 1, f"should detect new file, got added={r['added_files']}"
            assert r["written_chunks"] > 0
            assert r["skipped_files"] >= 1, "old file should be skipped"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestIncrementalModifyContent:
    def test_modify_body_detected(self):
        kb_dir = tempfile.mkdtemp(prefix="rag_incr_mod_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_mod_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A",
                          "original text AAA.")

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

                _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A",
                              "modified text ZZZ. completely different.")

                svc2 = IngestionService()
                svc2._embeddings = emb
                r = svc2.ingest_incremental("all")

            assert r["updated_files"] >= 1, f"should detect body change, got updated={r['updated_files']}"
            assert r["written_chunks"] > 0
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)


class TestIncrementalDeleteFile:
    def test_delete_file_detected(self):
        kb_dir = tempfile.mkdtemp(prefix="rag_incr_del_")
        data_dir = tempfile.mkdtemp(prefix="rag_data_del_")
        try:
            _make_md_file(kb_dir, "01-test/doc_a.md", "kb-a", "Doc A", "text AAA.")
            _make_md_file(kb_dir, "01-test/doc_b.md", "kb-b", "Doc B", "text BBB.")

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

                os.remove(os.path.join(kb_dir, "01-test", "doc_b.md"))

                svc2 = IngestionService()
                svc2._embeddings = emb
                r = svc2.ingest_incremental("all")

            assert r["deleted_files"] >= 1, f"should detect deletion, got deleted={r['deleted_files']}"
            assert r["deleted_chunks"] > 0
            assert r["included_files"] == 1, f"should have 1 file left, got {r['included_files']}"
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
            shutil.rmtree(data_dir, ignore_errors=True)
