"""Manifest V2 增量一致性集成测试：临时知识库 + 本地 Qdrant。"""

import copy
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
from qdrant_client.http import models as qdrant_models

from rag_app.core.exceptions import RebuildRequiredError
from rag_app.langchain_components.vector_store import get_client
from tests.fixtures.fake_embeddings import FakeEmbeddings
from tests.integration.test_incremental import FAKE_DIM, _make_md_file, _setup_config


@pytest.fixture
def rag_env():
    kb_dir = tempfile.mkdtemp(prefix="manifest_v2_kb_")
    data_dir = tempfile.mkdtemp(prefix="manifest_v2_data_")
    _setup_config(kb_dir, data_dir)
    embeddings = FakeEmbeddings(dimension=FAKE_DIM)

    with (
        patch("rag_app.langchain_components.embeddings.create_embeddings", return_value=embeddings),
        patch("rag_app.services.ingestion_service.create_embeddings", return_value=embeddings),
    ):
        from rag_app.services.ingestion_service import IngestionService

        def make_service():
            service = IngestionService()
            service._embeddings = embeddings
            return service

        yield kb_dir, data_dir, make_service

    try:
        import rag_app.langchain_components.vector_store as vector_store

        if vector_store._client is not None:
            vector_store._client.close()
            vector_store._client = None
    finally:
        shutil.rmtree(kb_dir, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)


def _document_points(collection: str, document_id: str):
    points, _ = get_client().scroll(
        collection_name=collection,
        scroll_filter=qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.document_id",
                    match=qdrant_models.MatchValue(value=document_id),
                )
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return points


def _point_chunk_ids(points) -> set[str]:
    return {
        point.payload.get("metadata", {}).get("chunk_id", "")
        for point in points
    }


class TestIncrementalVectorConsistency:
    def test_content_change_removes_old_point_and_preserves_other_scope(self, rag_env):
        kb_dir, _, make_service = rag_env
        path = "01-test/doc.md"
        _make_md_file(kb_dir, path, "doc-content", "Content", "Original AAA.", privacy="internal")

        service = make_service()
        service.ingest_full("all")
        before = copy.deepcopy(service.manifest.load())
        old_internal_chunks = set(
            before["documents"][path]["scopes"]["kb_internal"]["chunk_ids"]
        )
        private_before = copy.deepcopy(
            before["documents"][path]["scopes"]["kb_private"]
        )

        _make_md_file(kb_dir, path, "doc-content", "Content", "Changed ZZZ.", privacy="internal")
        updated = make_service()
        result = updated.ingest_incremental("internal")
        after = updated.manifest.load()
        new_internal_chunks = set(
            after["documents"][path]["scopes"]["kb_internal"]["chunk_ids"]
        )
        points = _document_points("kb_internal", "doc-content")

        assert result["updated_files"] == 1
        assert old_internal_chunks.isdisjoint(new_internal_chunks)
        assert len(points) == len(new_internal_chunks)
        assert _point_chunk_ids(points) == new_internal_chunks
        assert after["documents"][path]["scopes"]["kb_private"] == private_before

    def test_metadata_change_replaces_payload_without_duplicate(self, rag_env):
        kb_dir, _, make_service = rag_env
        path = "01-test/meta.md"
        _make_md_file(
            kb_dir, path, "doc-meta", "Metadata", "Same body.",
            privacy="internal", verification="pending",
        )
        make_service().ingest_full("internal")

        _make_md_file(
            kb_dir, path, "doc-meta", "Metadata", "Same body.",
            privacy="internal", verification="verified",
        )
        updated = make_service()
        result = updated.ingest_incremental("internal")
        points = _document_points("kb_internal", "doc-meta")
        manifest = updated.manifest.load()
        manifest_chunks = manifest["documents"][path]["scopes"]["kb_internal"]["chunk_ids"]

        assert result["metadata_changed_files"] == 1
        assert len(points) == len(manifest_chunks)
        assert all(
            point.payload.get("metadata", {}).get("verification_status") == "verified"
            for point in points
        )

    def test_delete_failure_stops_before_manifest_update(self, rag_env):
        kb_dir, data_dir, make_service = rag_env
        path = "01-test/failure.md"
        _make_md_file(kb_dir, path, "doc-failure", "Failure", "Original.", privacy="internal")
        make_service().ingest_full("internal")
        manifest_path = os.path.join(data_dir, "manifest.json")
        with open(manifest_path, "rb") as manifest_file:
            manifest_before = manifest_file.read()

        _make_md_file(kb_dir, path, "doc-failure", "Failure", "Changed.", privacy="internal")
        with patch(
            "rag_app.services.ingestion_service.delete_by_document_id",
            side_effect=RuntimeError("simulated delete failure"),
        ):
            with pytest.raises(RuntimeError, match="delete failure"):
                make_service().ingest_incremental("internal")

        with open(manifest_path, "rb") as manifest_file:
            assert manifest_file.read() == manifest_before
        assert len(_document_points("kb_internal", "doc-failure")) == 1


class TestUniqueFileCounts:
    def test_scope_all_counts_unique_documents(self, rag_env):
        kb_dir, _, make_service = rag_env
        first_path = "01-test/first.md"
        second_path = "01-test/second.md"
        _make_md_file(kb_dir, first_path, "doc-first", "First", "First body.", privacy="internal")
        make_service().ingest_full("all")

        _make_md_file(kb_dir, second_path, "doc-second", "Second", "Second body.", privacy="internal")
        added = make_service().ingest_incremental("all")
        assert added["added_files"] == 1
        assert added["written_chunks"] == 2

        _make_md_file(kb_dir, first_path, "doc-first", "First", "Changed body.", privacy="internal")
        updated = make_service().ingest_incremental("all")
        assert updated["updated_files"] == 1
        assert updated["written_chunks"] == 2

        os.remove(os.path.join(kb_dir, second_path))
        deleted = make_service().ingest_incremental("all")
        assert deleted["deleted_files"] == 1
        assert deleted["deleted_chunks"] == 2


class TestPrivacyMigrationConsistency:
    def test_internal_to_private_removes_internal_points(self, rag_env):
        kb_dir, _, make_service = rag_env
        path = "01-test/privacy.md"
        _make_md_file(kb_dir, path, "doc-privacy", "Privacy", "Body.", privacy="internal")
        make_service().ingest_full("all")

        _make_md_file(kb_dir, path, "doc-privacy", "Privacy", "Body.", privacy="private")
        updated = make_service()
        updated.ingest_incremental("all")
        manifest = updated.manifest.load()

        assert set(manifest["documents"][path]["scopes"]) == {"kb_private"}
        assert len(_document_points("kb_private", "doc-privacy")) == 1
        assert len(_document_points("kb_internal", "doc-privacy")) == 0

    def test_public_downgrade_removes_public_points(self, rag_env):
        kb_dir, _, make_service = rag_env
        path = "01-test/public.md"
        _make_md_file(
            kb_dir, path, "doc-public", "Public", "Body.", privacy="public",
            verification="verified", publish="published", review="approved",
        )
        make_service().ingest_full("all")
        assert len(_document_points("kb_public", "doc-public")) == 1

        _make_md_file(
            kb_dir, path, "doc-public", "Public", "Body.", privacy="public",
            verification="verified", publish="published", review="pending",
        )
        updated = make_service()
        updated.ingest_incremental("public")
        manifest = updated.manifest.load()

        assert len(_document_points("kb_public", "doc-public")) == 0
        assert "kb_public" not in manifest["documents"][path]["scopes"]


class TestMigrationStateMachine:
    def test_v1_requires_full_all_before_incremental(self, rag_env):
        kb_dir, data_dir, make_service = rag_env
        path = "01-test/migration.md"
        _make_md_file(kb_dir, path, "doc-migration", "Migration", "Body.", privacy="internal")
        v1 = {
            path: {
                "document_id": "doc-migration",
                "content_hash": "old",
                "metadata_hash": "old-meta",
                "chunk_ids": ["old-chunk"],
                "indexed_scopes": ["kb_private"],
                "indexed_at": "2025-01-01T00:00:00Z",
            }
        }
        with open(os.path.join(data_dir, "manifest.json"), "w", encoding="utf-8") as manifest_file:
            json.dump(v1, manifest_file)

        service = make_service()
        assert service.manifest.load()["rebuild_required"] is True
        with pytest.raises(RebuildRequiredError):
            service.ingest_incremental("internal")

        make_service().ingest_full("internal")
        assert make_service().manifest.load()["rebuild_required"] is True

        make_service().ingest_full("all")
        assert make_service().manifest.load()["rebuild_required"] is False
