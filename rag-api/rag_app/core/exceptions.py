"""异常定义。"""


class RagAppError(Exception):
    """基础异常。"""


class ConfigurationError(RagAppError):
    """配置错误。"""


class InvalidScopeError(RagAppError):
    """非法的 index_scope。"""


class PrivacyViolationError(RagAppError):
    """隐私违规 — 私密内容进入了不应出现的索引。"""


class IngestionError(RagAppError):
    """索引构建失败。"""


class SearchError(RagAppError):
    """检索失败。"""


class AnswerError(RagAppError):
    """问答生成失败。"""


class MetadataValidationError(RagAppError):
    """元数据不合法。"""


class FileNotIncludedError(RagAppError):
    """文件被排除规则拒绝。"""


class ManifestMigrationError(RagAppError):
    """Manifest 迁移失败。"""


class RebuildRequiredError(RagAppError):
    """Manifest 需要 full(all) 重建后才能执行增量操作。"""
