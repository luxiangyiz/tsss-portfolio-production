"""V1 -> V2 migration tests."""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
import pytest
from rag_app.knowledge.manifest import Manifest, normalize_relative_path

def _make_v1_manifest(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


class TestV1Detection:
    def test_detect_standard_v1(self):
        m = Manifest()
        v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'indexed_scopes': ['kb_private']}}
        assert m.detect_version(v1) == 1

    def test_v1_with_multiple_scopes(self):
        m = Manifest()
        v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'indexed_scopes': ['kb_private', 'kb_internal']}}
        assert m.detect_version(v1) == 1

    def test_empty_dict_not_v1(self):
        m = Manifest()
        with pytest.raises(ValueError):
            m.detect_version({})


class TestV1Backup:
    def test_backup_created_on_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'metadata_hash': 'def',
                  'chunk_ids': ['c1'], 'indexed_scopes': ['kb_private'],
                  'indexed_at': '2025-01-01T00:00:00Z'}}
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            m.load()
            backups = list(Path(tmp).glob('manifest.v1.backup-*.json'))
            assert len(backups) >= 1

    def test_original_preserved_after_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'metadata_hash': 'def',
                  'chunk_ids': ['c1'], 'indexed_scopes': ['kb_private'],
                  'indexed_at': '2025-01-01T00:00:00Z'}}
            _make_v1_manifest(p, v1)
            with open(p, 'r') as f:
                original = f.read()
            m = Manifest(p)
            m.load()
            backups = list(Path(tmp).glob('manifest.v1.backup-*.json'))
            assert len(backups) >= 1
            with open(backups[0], 'r') as f:
                assert json.load(f) == json.loads(original)


class TestV1ToV2Conversion:
    def test_single_scope_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc123', 'metadata_hash': 'def456',
                  'chunk_ids': ['c1', 'c2'], 'indexed_scopes': ['kb_private'],
                  'indexed_at': '2025-01-01T00:00:00Z'}}
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            result = m.load()
            assert result['schema_version'] == 2
            doc = result['documents']['file.md']
            assert doc['document_id'] == 'd1'
            scope = doc['scopes']['kb_private']
            assert scope['content_hash'] == 'abc123'
            assert scope['metadata_hash'] == 'def456'
            assert scope['chunk_ids'] == ['c1', 'c2']
            assert scope['indexed_at'] == '2025-01-01T00:00:00Z'

    def test_multi_scope_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd2', 'content_hash': 'hash1', 'metadata_hash': 'meta1',
                  'chunk_ids': ['c1'], 'indexed_scopes': ['kb_private', 'kb_internal'],
                  'indexed_at': '2025-01-01T00:00:00Z'}}
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            result = m.load()
            doc = result['documents']['file.md']
            assert 'kb_private' in doc['scopes']
            assert 'kb_internal' in doc['scopes']
            assert 'kb_public' not in doc['scopes']
            for scope_name in ['kb_private', 'kb_internal']:
                s = doc['scopes'][scope_name]
                assert s['content_hash'] == 'hash1'
                assert s['metadata_hash'] == 'meta1'
                assert s['chunk_ids'] == ['c1']
                assert s['indexed_at'] == '2025-01-01T00:00:00Z'

    def test_path_backslash_normalization(self):
        # normalize_relative_path converts backslash to forward slash
        assert normalize_relative_path('sub\\file.md') == 'sub/file.md'
        assert normalize_relative_path('sub/file.md') == 'sub/file.md'
        assert normalize_relative_path('a\\b\\c.md') == 'a/b/c.md'

    def test_invalid_scope_filtered_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd4', 'content_hash': 'hash',
                  'indexed_scopes': ['kb_private', 'invalid_scope'],
                  'indexed_at': '2025-01-01T00:00:00Z', 'chunk_ids': [], 'metadata_hash': ''}}
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            result = m.load()
            doc = result['documents']['file.md']
            assert 'kb_private' in doc['scopes']
            assert 'invalid_scope' not in doc['scopes']

    def test_migration_sets_updated_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd5', 'content_hash': 'hash',
                  'indexed_scopes': ['kb_private'], 'indexed_at': '2025-01-01T00:00:00Z',
                  'chunk_ids': [], 'metadata_hash': ''}}
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            result = m.load()
            assert result['updated_at'] != ''

    def test_multiple_files_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'manifest.json')
            v1 = {
                'a.md': {'document_id': 'a', 'content_hash': 'ha', 'indexed_scopes': ['kb_private'],
                         'indexed_at': '2025-01-01T00:00:00Z', 'chunk_ids': [], 'metadata_hash': ''},
                'b.md': {'document_id': 'b', 'content_hash': 'hb', 'indexed_scopes': ['kb_internal'],
                         'indexed_at': '2025-01-01T00:00:00Z', 'chunk_ids': [], 'metadata_hash': ''},
            }
            _make_v1_manifest(p, v1)
            m = Manifest(p)
            result = m.load()
            assert len(result['documents']) == 2
            assert 'a.md' in result['documents']
            assert 'b.md' in result['documents']


class TestRebuildRequired:
    """V1 迁移后 rebuild_required 状态机。"""

    def _make_v1_and_migrate(self, tmp):
        path = os.path.join(tmp, 'manifest.json')
        v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'metadata_hash': 'def',
              'chunk_ids': ['c1'], 'indexed_scopes': ['kb_private'],
              'indexed_at': '2025-01-01T00:00:00Z'}}
        _make_v1_manifest(path, v1)
        m = Manifest(path)
        return m, m.load()

    def test_rebuild_required_after_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, data = self._make_v1_and_migrate(tmp)
            assert data['rebuild_required'] is True
            assert 'migration' in data
            assert data['migration']['from_version'] == 1

    def test_import_rebuild_required_error_exists(self):
        from rag_app.core.exceptions import RebuildRequiredError
        assert RebuildRequiredError is not None


class TestBackupFailureBlocks:
    """备份失败必须阻断迁移，原文件不变。"""

    def test_backup_failure_raises_and_preserves_original(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'manifest.json')
            v1 = {'file.md': {'document_id': 'd1', 'content_hash': 'abc', 'metadata_hash': 'def',
                  'chunk_ids': ['c1'], 'indexed_scopes': ['kb_private'],
                  'indexed_at': '2025-01-01T00:00:00Z'}}
            _make_v1_manifest(path, v1)

            with open(path, 'rb') as f:
                original_bytes = f.read()

            import shutil as shutil_mod
            original_copy2 = shutil_mod.copy2

            def fake_copy2(src, dst, **kw):
                raise OSError('Simulated backup failure')

            monkeypatch.setattr(shutil_mod, 'copy2', fake_copy2)

            m = Manifest(path)
            with pytest.raises(Exception):
                m.load()

            with open(path, 'rb') as f:
                assert f.read() == original_bytes, '原文件不应改变'

            backups = list(Path(tmp).glob('manifest.v1.backup-*.json'))
            assert len(backups) == 0, f'不应生成备份: {backups}'

            monkeypatch.setattr(shutil_mod, 'copy2', original_copy2)
            m2 = Manifest(path)
            data = m2.load()
            assert data['rebuild_required'] is True
