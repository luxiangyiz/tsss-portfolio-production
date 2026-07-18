"""隐私路由器 — 决定文件进入哪些 collection。"""

from rag_app.core.config import settings
from rag_app.core.exceptions import PrivacyViolationError
from rag_app.knowledge.metadata_validator import MetadataValidator
from rag_app.models.documents import KBFile


class PrivacyRouter:
    """根据 privacy_level + public 四项条件决定 collection 归属。"""

    def __init__(self):
        yaml = settings.yaml_config
        self._collections = yaml.get("collections", {})
        self._public_req = yaml.get("privacy", {}).get("public_index_requirements", {})

    def route(self, kb_file: KBFile) -> list[str]:
        """返回文件应进入的 collection 列表。"""
        fm = kb_file.frontmatter
        collections: list[str] = []

        # private-index: 接受 private / internal / public
        if fm.privacy_level in ("private", "internal", "public"):
            collections.append(self._collections.get("private", "kb_private"))

        # internal-index: 接受 internal / public
        if fm.privacy_level in ("internal", "public"):
            collections.append(self._collections.get("internal", "kb_internal"))

        # public-index: 仅当四项条件全部满足
        if self._qualifies_for_public(fm):
            collections.append(self._collections.get("public", "kb_public"))

        return collections

    def _qualifies_for_public(self, fm) -> bool:
        return (
            fm.privacy_level == self._public_req.get("privacy_level", "public")
            and fm.publish_status == self._public_req.get("publish_status", "published")
            and fm.review_status == self._public_req.get("review_status", "approved")
            and fm.verification_status == self._public_req.get("verification_status", "verified")
        )

    def get_target_collections(self, scope: str) -> list[str]:
        """根据 scope 返回对应的 collection 名列表。"""
        mapping = {
            "private": [self._collections.get("private", "kb_private")],
            "internal": [self._collections.get("internal", "kb_internal")],
            "public": [self._collections.get("public", "kb_public")],
            "all": [
                self._collections.get("private", "kb_private"),
                self._collections.get("internal", "kb_internal"),
                self._collections.get("public", "kb_public"),
            ],
        }
        return mapping.get(scope, [self._collections.get("internal", "kb_internal")])

    def check_no_private_in_public(self, collection_name: str, kb_file: KBFile):
        """安全检查：确保 private 内容不会进入 public collection。"""
        public_col = self._collections.get("public", "kb_public")
        if collection_name == public_col and kb_file.frontmatter.privacy_level != "public":
            raise PrivacyViolationError(
                f"Cannot insert {kb_file.frontmatter.privacy_level} content "
                f"({kb_file.relative_path}) into {public_col}"
            )
