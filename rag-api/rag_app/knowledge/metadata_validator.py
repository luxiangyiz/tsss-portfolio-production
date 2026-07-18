"""元数据验证器 — 校验 frontmatter 字段的合法性。"""

from rag_app.core.config import settings
from rag_app.models.documents import KBFile


class MetadataValidator:
    """校验 frontmatter 字段值是否在合法范围内。"""

    def __init__(self):
        yaml = settings.yaml_config
        self._valid_verification = set(yaml.get("metadata", {}).get("verification_status", []))
        self._valid_privacy = set(yaml.get("metadata", {}).get("privacy_level", []))
        self._valid_publish = set(yaml.get("metadata", {}).get("publish_status", []))
        self._valid_review = set(yaml.get("metadata", {}).get("review_status", []))

    def validate(self, kb_file: KBFile) -> list[str]:
        """返回校验错误列表。无错误返回空列表。"""
        errors: list[str] = []
        fm = kb_file.frontmatter

        if fm.verification_status and fm.verification_status not in self._valid_verification:
            errors.append(
                f"Invalid verification_status '{fm.verification_status}' "
                f"in {kb_file.relative_path}"
            )

        if fm.privacy_level and fm.privacy_level not in self._valid_privacy:
            errors.append(
                f"Invalid privacy_level '{fm.privacy_level}' "
                f"in {kb_file.relative_path}"
            )

        if fm.publish_status and fm.publish_status not in self._valid_publish:
            errors.append(
                f"Invalid publish_status '{fm.publish_status}' "
                f"in {kb_file.relative_path}"
            )

        if fm.review_status and fm.review_status not in self._valid_review:
            errors.append(
                f"Invalid review_status '{fm.review_status}' "
                f"in {kb_file.relative_path}"
            )

        return errors
