"""Manifest V2 单元测试 — 覆盖 V2 结构、per-scope 存取、原子写入、变更检测。"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from rag_app.knowledge.manifest import Manifest, normalize_relative_path


class TestManifestV2Basics:
    """V2 基本操作。"""

    def test_empty_v2_structure(self):
        m = Manifest()
        data = m.empty_v2()
        assert data["schema_version"] == 2
        assert "updated_at" in data
        assert "documents" in data
        assert data["documents"] == {}

    def test_load_returns_v2_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nonexistent.json")
            m = Manifest(path=path)
            data = m.load()
            assert data["schema_version"] == 2
            assert "documents" in data

    def test_save_atomic_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            data["documents"]["test/file.md"] = {
                "document_id": "doc-1",
                "scopes": {
                    "kb_private": {
                        "content_hash": "abc123",
                        "metadata_hash": "def456",
                        "chunk_ids": ["chunk-1", "chunk-2"],
                        "indexed_at": "2026-07-16T00:00:00Z",
                    }
                },
            }
            m.save_atomic(data)

            # 验证文件存在
            assert os.path.exists(path)

            # 加载验证
            loaded = m.load()
            assert loaded["schema_version"] == 2
            assert "updated_at" in loaded
            assert loaded["updated_at"] != ""
            assert "test/file.md" in loaded["documents"]
            doc = loaded["documents"]["test/file.md"]
            assert doc["document_id"] == "doc-1"
            assert "kb_private" in doc["scopes"]

    def test_updated_at_is_set_on_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            m.save_atomic(data)

            loaded = m.load()
            assert loaded["updated_at"] != ""
            # 确认是 ISO 时间格式
            assert "T" in loaded["updated_at"]


class TestManifestScopeAccess:
    """Per-scope 存取测试。"""

    def test_get_set_scope_entry(self):
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "path/to/file.md", "kb_private", {
            "document_id": "doc-1",
            "content_hash": "hash1",
            "metadata_hash": "mh1",
            "chunk_ids": ["c1", "c2"],
            "indexed_at": "2026-01-01T00:00:00Z",
        })

        entry = m.get_scope_entry(data, "path/to/file.md", "kb_private")
        assert entry is not None
        assert entry["content_hash"] == "hash1"
        assert entry["metadata_hash"] == "mh1"
        assert entry["chunk_ids"] == ["c1", "c2"]

        # 其他 scope 不存在
        assert m.get_scope_entry(data, "path/to/file.md", "kb_internal") is None

    def test_set_multiple_scopes(self):
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "file.md", "kb_private", {
            "document_id": "doc-1",
            "content_hash": "h1",
            "metadata_hash": "m1",
            "chunk_ids": ["c1"],
            "indexed_at": "2026-01-01T00:00:00+00:00",
        })
        m.set_scope_entry(data, "file.md", "kb_internal", {
            "document_id": "doc-1",
            "content_hash": "h2",
            "metadata_hash": "m2",
            "chunk_ids": ["c2"],
            "indexed_at": "2026-01-01T00:00:01+00:00",
        })

        doc = data["documents"]["file.md"]
        assert len(doc["scopes"]) == 2
        assert doc["scopes"]["kb_private"]["content_hash"] == "h1"
        assert doc["scopes"]["kb_internal"]["content_hash"] == "h2"

    def test_remove_scope_entry(self):
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "file.md", "kb_private", {
            "document_id": "doc-1",
            "content_hash": "h1",
            "metadata_hash": "m1",
            "chunk_ids": ["c1"],
            "indexed_at": "2026-01-01T00:00:00+00:00",
        })
        m.set_scope_entry(data, "file.md", "kb_internal", {
            "document_id": "doc-1",
            "content_hash": "h2",
            "metadata_hash": "m2",
            "chunk_ids": ["c2"],
            "indexed_at": "2026-01-01T00:00:01+00:00",
        })

        # 移除一个 scope
        m.remove_scope_entry(data, "file.md", "kb_private")
        assert m.get_scope_entry(data, "file.md", "kb_private") is None
        assert m.get_scope_entry(data, "file.md", "kb_internal") is not None

    def test_remove_last_scope_removes_document(self):
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "file.md", "kb_private", {
            "document_id": "doc-1",
            "content_hash": "h1",
            "metadata_hash": "m1",
            "chunk_ids": ["c1"],
            "indexed_at": "2026-01-01T00:00:00+00:00",
        })

        m.remove_scope_entry(data, "file.md", "kb_private")
        assert "file.md" not in data["documents"]

    def test_document_id_preserved(self):
        """验证 document_id 在文档级别保存。"""
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "file.md", "kb_private", {
            "document_id": "my-doc-id",
            "content_hash": "h1",
            "metadata_hash": "m1",
            "chunk_ids": [],
            "indexed_at": "2026-01-01T00:00:00+00:00",
        })

        m.set_scope_entry(data, "file.md", "kb_internal", {
            "document_id": "",  # 第二个 scope 不设置 document_id
            "content_hash": "h2",
            "metadata_hash": "m2",
            "chunk_ids": [],
            "indexed_at": "2026-01-01T00:00:01+00:00",
        })

        assert data["documents"]["file.md"]["document_id"] == "my-doc-id"


class TestManifestPathNormalization:
    """路径归一化。"""

    def test_normalize_backslash(self):
        assert normalize_relative_path("01-test\\doc.md") == "01-test/doc.md"

    def test_normalize_forward_slash(self):
        assert normalize_relative_path("01-test/doc.md") == "01-test/doc.md"

    def test_path_in_scope_access(self):
        """Windows 路径在 scope 存取时自动归一化。"""
        m = Manifest()
        data = m.empty_v2()

        m.set_scope_entry(data, "01-test\\private.md", "kb_private", {
            "document_id": "doc-1",
            "content_hash": "h",
            "metadata_hash": "m",
            "chunk_ids": [],
            "indexed_at": "t",
        })

        # 用 / 查询
        entry = m.get_scope_entry(data, "01-test/private.md", "kb_private")
        assert entry is not None
        assert entry["content_hash"] == "h"


class TestManifestVersionDetection:
    """版本检测。"""

    def test_detect_v2(self):
        m = Manifest()
        assert m.detect_version({"schema_version": 2, "documents": {}}) == 2

    def test_detect_v1(self):
        m = Manifest()
        v1 = {
            "path/to/file.md": {
                "document_id": "doc-1",
                "content_hash": "abc",
                "metadata_hash": "def",
                "chunk_ids": [],
                "indexed_scopes": ["kb_private"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            }
        }
        assert m.detect_version(v1) == 1

    def test_detect_unknown_raises(self):
        m = Manifest()
        with pytest.raises(ValueError, match="不支持的"):
            m.detect_version({"schema_version": 99})

    def test_detect_empty_dict_is_v1_like_but_raises(self):
        m = Manifest()
        # 空 dict 不匹配 V1 特征（无 indexed_scopes）
        with pytest.raises(ValueError, match="无法识别"):
            m.detect_version({})

    def test_validate_v2_rejects_v1(self):
        m = Manifest()
        with pytest.raises(ValueError):
            m._validate_v2({"schema_version": 1, "documents": {}})

    def test_validate_v2_requires_documents(self):
        m = Manifest()
        with pytest.raises(ValueError, match="缺少 documents"):
            m._validate_v2({"schema_version": 2})

    def test_corrupt_json_raises_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "corrupt.json")
            with open(path, "w") as f:
                f.write("not valid json{{{")

            m = Manifest(path=path)
            with pytest.raises(ValueError, match="损坏"):
                m.load()


class TestManifestAtomicWrite:
    """原子写入测试。"""

    def test_atomic_write_does_not_corrupt_existing(self):
        """写入失败时不应损坏旧文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            # 先写入有效数据
            data = m.empty_v2()
            data["documents"]["old_file.md"] = {
                "document_id": "old",
                "scopes": {},
            }
            m.save_atomic(data)

            # 验证旧数据存在
            loaded = m.load()
            assert "old_file.md" in loaded["documents"]

            # 现在写入新数据（不应该损坏）
            data2 = m.empty_v2()
            data2["documents"]["new_file.md"] = {
                "document_id": "new",
                "scopes": {},
            }
            m.save_atomic(data2)

            # 验证新数据
            loaded2 = m.load()
            assert "new_file.md" in loaded2["documents"]

    def test_two_consecutive_writes(self):
        """连续两次写入应都能正确加载。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            data["documents"]["a.md"] = {"document_id": "a", "scopes": {}}
            m.save_atomic(data)

            loaded1 = m.load()
            assert "a.md" in loaded1["documents"]

            data["documents"]["b.md"] = {"document_id": "b", "scopes": {}}
            m.save_atomic(data)

            loaded2 = m.load()
            assert "a.md" in loaded2["documents"]
            assert "b.md" in loaded2["documents"]


class TestManifestFindChangedForScope:
    """Per-scope 变更检测。"""

    def test_new_file_detected_as_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            # 写入空 V2 manifest
            m.save_atomic(m.empty_v2())

            # 创建临时文件
            file_path = os.path.join(tmp, "test.md")
            with open(file_path, "w") as f:
                f.write("hello world")

            new_hashes = {"test.md": "abc123"}
            new_metadata = {"test.md": "def456"}
            file_tuples = [(file_path, "test.md")]

            added, changed, meta, removed = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )

            assert len(added) == 1  # 新文件→added
            assert len(changed) == 0
            assert len(meta) == 0
            assert len(removed) == 0

    def test_unchanged_file_not_in_any_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            m.set_scope_entry(data, "test.md", "kb_private", {
                "document_id": "doc-1",
                "content_hash": "same_hash",
                "metadata_hash": "same_meta",
                "chunk_ids": ["c1"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            })
            m.save_atomic(data)

            file_path = os.path.join(tmp, "test.md")
            with open(file_path, "w") as f:
                f.write("hello world")

            new_hashes = {"test.md": "same_hash"}
            new_metadata = {"test.md": "same_meta"}
            file_tuples = [(file_path, "test.md")]

            added, changed, meta, removed = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )

            assert len(added) == 0
            assert len(changed) == 0
            assert len(meta) == 0
            assert len(removed) == 0

    def test_content_changed_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            m.set_scope_entry(data, "test.md", "kb_private", {
                "document_id": "doc-1",
                "content_hash": "old_hash",
                "metadata_hash": "old_meta",
                "chunk_ids": ["c1"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            })
            m.save_atomic(data)

            file_path = os.path.join(tmp, "test.md")
            with open(file_path, "w") as f:
                f.write("modified content")

            new_hashes = {"test.md": "new_hash"}
            new_metadata = {"test.md": "old_meta"}
            file_tuples = [(file_path, "test.md")]

            added, changed, meta, removed = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )

            assert len(changed) == 1  # content changed
            assert len(added) == 0
            assert len(meta) == 0

    def test_metadata_changed_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            m.set_scope_entry(data, "test.md", "kb_private", {
                "document_id": "doc-1",
                "content_hash": "same_hash",
                "metadata_hash": "old_meta",
                "chunk_ids": ["c1"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            })
            m.save_atomic(data)

            file_path = os.path.join(tmp, "test.md")
            with open(file_path, "w") as f:
                f.write("hello world")

            new_hashes = {"test.md": "same_hash"}
            new_metadata = {"test.md": "new_meta"}
            file_tuples = [(file_path, "test.md")]

            added, changed, meta, removed = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )

            assert len(meta) == 1  # metadata changed
            assert len(added) == 0
            assert len(changed) == 0

    def test_deleted_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            m.set_scope_entry(data, "deleted.md", "kb_private", {
                "document_id": "doc-1",
                "content_hash": "h",
                "metadata_hash": "m",
                "chunk_ids": ["c1"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            })
            m.save_atomic(data)

            # 空文件列表 → deleted.md 应该出现在 removed 中
            file_tuples = []
            new_hashes = {}
            new_metadata = {}

            added, changed, meta, removed = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )

            assert len(removed) == 1
            assert "deleted.md" in removed

    def test_scope_isolation_in_detection(self):
        """scope=kb_private 的变化不影响 kb_internal 检测。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            data = m.empty_v2()
            # 文件在 kb_private 中有记录，但在 kb_internal 中没有
            m.set_scope_entry(data, "test.md", "kb_private", {
                "document_id": "doc-1",
                "content_hash": "h",
                "metadata_hash": "m",
                "chunk_ids": ["c1"],
                "indexed_at": "2026-01-01T00:00:00+00:00",
            })
            m.save_atomic(data)

            file_path = os.path.join(tmp, "test.md")
            with open(file_path, "w") as f:
                f.write("hello world")

            new_hashes = {"test.md": "h"}
            new_metadata = {"test.md": "m"}
            file_tuples = [(file_path, "test.md")]

            # 检查 kb_private → unchanged
            a1, c1, m1, r1 = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_private"
            )
            assert len(a1) == 0 and len(c1) == 0  # 无变化

            # 检查 kb_internal → added（因为该文件没有 kb_internal scope）
            a2, c2, m2, r2 = m.find_changed_for_scope(
                file_tuples, new_hashes, new_metadata, "kb_internal"
            )
            assert len(a2) == 1  # 对 kb_internal 是新增


class TestManifestHashComputation:
    """哈希计算。"""

    def test_compute_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            with open(path, "w") as f:
                f.write("test content")
            h = Manifest.compute_file_hash(path)
            assert len(h) == 64  # SHA256 完整 hex
            assert h == Manifest.compute_file_hash(path)  # 确定性

    def test_compute_metadata_hash(self):
        h1 = Manifest.compute_metadata_hash({"a": 1, "b": 2})
        h2 = Manifest.compute_metadata_hash({"b": 2, "a": 1})  # 顺序不同
        assert h1 == h2  # sort_keys 保证确定性
        assert len(h1) == 16  # 前16字符

    def test_compute_file_hash_nonexistent(self):
        h = Manifest.compute_file_hash("/nonexistent/file.txt")
        assert h == ""


class TestDeepValidationNegative:
    """深层校验反向测试 — 所有非法输入必须报错。"""

    def _make_v2(self, **overrides):
        data = Manifest.empty_v2()
        data.update(overrides)
        return data

    def test_empty_document_id_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {"document_id": "", "scopes": {}}
        with pytest.raises(ValueError, match="document_id"):
            m._validate_v2(data)

    def test_missing_scopes_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {"document_id": "d1"}
        with pytest.raises(ValueError, match="scopes"):
            m._validate_v2(data)

    def test_invalid_scope_name_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "d1",
            "scopes": {"invalid_scope": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": ["c1"], "indexed_at": "2025-01-01T00:00:00Z"}}
        }
        with pytest.raises(ValueError, match="非法 scope"):
            m._validate_v2(data)

    def test_scope_entry_missing_field(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "d1",
            "scopes": {"kb_private": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": ["c1"]}}
        }
        with pytest.raises(ValueError, match="indexed_at"):
            m._validate_v2(data)

    def test_chunk_ids_not_list_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "d1",
            "scopes": {"kb_private": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": "not-a-list", "indexed_at": "2025-01-01T00:00:00Z"}}
        }
        with pytest.raises(ValueError, match="chunk_ids 必须是 list"):
            m._validate_v2(data)

    def test_chunk_ids_with_empty_string_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "d1",
            "scopes": {"kb_private": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": ["c1", ""], "indexed_at": "2025-01-01T00:00:00Z"}}
        }
        with pytest.raises(ValueError, match="空字符串"):
            m._validate_v2(data)

    def test_chunk_ids_with_duplicates_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "d1",
            "scopes": {"kb_private": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": ["c1", "c1"], "indexed_at": "2025-01-01T00:00:00Z"}}
        }
        with pytest.raises(ValueError, match="重复"):
            m._validate_v2(data)

    def test_path_with_backslash_rejected(self):
        m = Manifest()
        data = self._make_v2()
        path = "sub\\file.md"
        data["documents"][path] = {
            "document_id": "d1",
            "scopes": {"kb_private": {"content_hash": "h", "metadata_hash": "m", "chunk_ids": ["c1"], "indexed_at": "2025-01-01T00:00:00Z"}}
        }
        with pytest.raises(ValueError, match="反斜杠"):
            m._validate_v2(data)

    def test_rebuild_required_not_bool_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["rebuild_required"] = "not-a-bool"
        with pytest.raises(ValueError, match="bool"):
            m._validate_v2(data)

    def test_invalid_indexed_at_rejected(self):
        m = Manifest()
        data = self._make_v2()
        data["documents"]["file.md"] = {
            "document_id": "doc-1",
            "scopes": {
                "kb_private": {
                    "content_hash": "hash",
                    "metadata_hash": "meta",
                    "chunk_ids": ["chunk-1"],
                    "indexed_at": "not-a-date",
                }
            },
        }
        with pytest.raises(ValueError, match="ISO 8601"):
            m._validate_v2(data)


class TestAtomicReplaceFailure:
    """os.replace 失败测试。"""

    def test_failed_replace_preserves_original(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            m = Manifest(path=path)

            # 写入旧 manifest
            old_data = m.empty_v2()
            old_data["documents"]["old.md"] = {
                "document_id": "old",
                "scopes": {"kb_private": {"content_hash": "oldhash", "metadata_hash": "oldmeta", "chunk_ids": ["oc1"], "indexed_at": "2025-01-01T00:00:00Z"}}
            }
            m.save_atomic(old_data)

            # 记录旧内容
            with open(path, "rb") as f:
                original_bytes = f.read()

            # 创建新数据
            new_data = m.empty_v2()
            new_data["documents"]["new.md"] = {
                "document_id": "new",
                "scopes": {"kb_private": {"content_hash": "newhash", "metadata_hash": "newmeta", "chunk_ids": ["nc1"], "indexed_at": "2025-01-01T00:00:00Z"}}
            }

            # monkeypatch os.replace 抛出 OSError
            original_replace = os.replace

            def fake_replace(src, dst, **kwargs):
                raise OSError("Simulated atomic replace failure")

            monkeypatch.setattr(os, "replace", fake_replace)

            # 保存应该失败
            with pytest.raises(OSError):
                m.save_atomic(new_data)

            # 恢复后文件内容应与旧内容一致
            with open(path, "rb") as f:
                current_bytes = f.read()
            assert current_bytes == original_bytes, "os.replace 失败后原文件不应改变"

            # 验证没有遗留的临时文件
            tmps = list(Path(tmp).glob(".manifest-*.tmp"))
            assert len(tmps) == 0, f"遗留临时文件: {tmps}"

            # 恢复 os.replace 后正常保存
            monkeypatch.setattr(os, "replace", original_replace)
            m.save_atomic(new_data)
            loaded = m.load()
            assert "new.md" in loaded["documents"]
