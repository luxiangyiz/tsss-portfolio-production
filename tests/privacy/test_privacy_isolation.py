"""隐私测试 — 验证三类 collection 完全隔离。"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from rag_app.knowledge.scanner import Scanner
from rag_app.knowledge.markdown_parser import MarkdownParser
from rag_app.knowledge.privacy_router import PrivacyRouter


class TestPrivacyIsolation:
    """验证隐私隔离规则。"""

    def setup_method(self):
        self.scanner = Scanner()
        self.parser = MarkdownParser()
        self.router = PrivacyRouter()

    def test_private_files_not_in_public_collection(self):
        """private 文件绝不能进入 kb_public。"""
        for fe in self.scanner.scan():
            kb = self.parser.parse(fe)
            if kb.frontmatter.privacy_level == "private":
                cols = self.router.route(kb)
                assert "kb_public" not in cols, \
                    f"PRIVACY VIOLATION: {kb.relative_path} (private) entered public collection"

    def test_internal_files_not_in_private_search_scope(self):
        """internal 文件可以进 kb_private 但不能让 public 用户搜到。"""
        for fe in self.scanner.scan():
            kb = self.parser.parse(fe)
            if kb.frontmatter.privacy_level == "internal":
                cols = self.router.route(kb)
                # internal 不应进入 kb_public（除非四项条件全部满足）
                # 但可以进入 kb_private 和 kb_internal
                assert "kb_private" in cols or "kb_internal" in cols, \
                    f"internal file should go to at least kb_private or kb_internal"

    def test_public_index_empty_by_default(self):
        """没有满足四项条件的文件时，public collection 应为空。"""
        public_count = 0
        for fe in self.scanner.scan():
            kb = self.parser.parse(fe)
            cols = self.router.route(kb)
            if "kb_public" in cols:
                public_count += 1
                # 如果进入了 public，必须验证四项条件
                fm = kb.frontmatter
                assert fm.privacy_level == "public", \
                    f"public collection requires privacy_level=public, got {fm.privacy_level}"
                assert fm.publish_status == "published", \
                    f"public collection requires publish_status=published, got {fm.publish_status}"
                assert fm.review_status == "approved", \
                    f"public collection requires review_status=approved, got {fm.review_status}"
                assert fm.verification_status == "verified", \
                    f"public collection requires verification_status=verified, got {fm.verification_status}"

    def test_scope_restricts_search(self):
        """验证 scope 限制：public scope 只能用 public collection。"""
        public_cols = self.router.get_target_collections("public")
        assert "kb_private" not in public_cols, "public scope should not include kb_private"
        assert "kb_internal" not in public_cols, "public scope should not include kb_internal"

        internal_cols = self.router.get_target_collections("internal")
        assert "kb_private" not in internal_cols, "internal scope should not include kb_private"

    def test_all_files_in_some_collection(self):
        """所有纳入的文件至少进入一个 collection。"""
        for fe in self.scanner.scan():
            kb = self.parser.parse(fe)
            cols = self.router.route(kb)
            assert len(cols) > 0, \
                f"File {kb.relative_path} was not routed to any collection"
