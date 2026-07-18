"""单元测试 — 扫描器、解析器、元数据验证器、纳入策略、隐私路由。"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from rag_app.knowledge.scanner import Scanner
from rag_app.knowledge.markdown_parser import MarkdownParser
from rag_app.knowledge.metadata_validator import MetadataValidator
from rag_app.knowledge.inclusion_policy import InclusionPolicy
from rag_app.knowledge.privacy_router import PrivacyRouter
from rag_app.knowledge.chunk_id import make_chunk_id
from rag_app.core.config import settings


class TestScanner:
    def test_scanner_finds_files(self):
        scanner = Scanner()
        files = scanner.scan()
        assert len(files) > 0, "Should find at least 1 Markdown file"

    def test_scanner_excludes_templates(self):
        scanner = Scanner()
        files = scanner.scan()
        paths = [f.relative_path for f in files]
        for p in paths:
            assert "90-模板" not in p, "Template directory should be excluded"
            assert "00-待整理收件箱" not in p, "Inbox should be excluded"

    def test_scanner_only_md(self):
        scanner = Scanner()
        files = scanner.scan()
        for f in files:
            assert f.file_name.endswith(".md"), "Only .md files should be included"


class TestMarkdownParser:
    def test_parse_with_frontmatter(self):
        parser = MarkdownParser()
        scanner = Scanner()
        files = scanner.scan()
        assert len(files) > 0
        kb = parser.parse(files[0])
        assert kb.file_name.endswith(".md")
        assert kb.frontmatter is not None

    def test_parse_extracts_privacy(self):
        parser = MarkdownParser()
        scanner = Scanner()
        files = scanner.scan()
        kb = parser.parse(files[0])
        assert kb.frontmatter.privacy_level in ("private", "internal", "public")


class TestMetadataValidator:
    def test_valid_privacy_levels(self):
        validator = MetadataValidator()
        scanner = Scanner()
        parser = MarkdownParser()
        for fe in scanner.scan()[:5]:
            kb = parser.parse(fe)
            errs = validator.validate(kb)
            for e in errs:
                assert "Invalid" not in e or "privacy_level" not in e, \
                    f"Should not have invalid privacy_level: {e}"


class TestInclusionPolicy:
    def test_includes_valid_files(self):
        policy = InclusionPolicy()
        scanner = Scanner()
        parser = MarkdownParser()
        for fe in scanner.scan()[:5]:
            kb = parser.parse(fe)
            included, reason = policy.should_include(kb)
            assert included, f"Should include {kb.file_name}: {reason}"


class TestPrivacyRouter:
    def test_route_returns_collections(self):
        router = PrivacyRouter()
        scanner = Scanner()
        parser = MarkdownParser()
        for fe in scanner.scan()[:5]:
            kb = parser.parse(fe)
            cols = router.route(kb)
            assert len(cols) > 0, f"Should route to at least 1 collection: {kb.file_name}"
            for c in cols:
                assert c.startswith("kb_"), f"Collection name should start with kb_: {c}"

    def test_no_private_in_public(self):
        router = PrivacyRouter()
        scanner = Scanner()
        parser = MarkdownParser()
        for fe in scanner.scan():
            kb = parser.parse(fe)
            cols = router.route(kb)
            if kb.frontmatter.privacy_level == "private":
                assert "kb_public" not in cols, \
                    f"Private file {kb.file_name} must not enter kb_public"


class TestChunkId:
    def test_stable_id(self):
        id1 = make_chunk_id("test/file.md", 0, "hello world")
        id2 = make_chunk_id("test/file.md", 0, "hello world")
        assert id1 == id2, "Same inputs should produce same ID"

    def test_different_content_different_id(self):
        id1 = make_chunk_id("test/file.md", 0, "hello")
        id2 = make_chunk_id("test/file.md", 0, "world")
        assert id1 != id2, "Different content should produce different ID"


class TestConfig:
    def test_kb_root_exists(self):
        assert os.path.isdir(settings.kb_root), f"KB_ROOT should exist: {settings.kb_root}"

    def test_collections_defined(self):
        yaml = settings.yaml_config
        cols = yaml.get("collections", {})
        assert "private" in cols
        assert "internal" in cols
        assert "public" in cols
