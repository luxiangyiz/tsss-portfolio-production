"""安全模块 — 密钥脱敏、隐私校验。"""

import re
from functools import lru_cache

# 敏感字段黑名单（匹配 key 名）
_SENSITIVE_KEY_PATTERNS = [
    re.compile(r".*api[_-]?key$", re.IGNORECASE),
    re.compile(r".*token$", re.IGNORECASE),
    re.compile(r".*password$", re.IGNORECASE),
    re.compile(r".*secret$", re.IGNORECASE),
]


@lru_cache(maxsize=1)
def _sensitive_patterns():
    return _SENSITIVE_KEY_PATTERNS


def is_sensitive_key(key: str) -> bool:
    for pat in _sensitive_patterns():
        if pat.match(key):
            return True
    return False


def sanitize_dict(data: dict) -> dict:
    """递归脱敏：将敏感字段值替换为 [REDACTED]。"""
    result = {}
    for k, v in data.items():
        if is_sensitive_key(k):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = sanitize_dict(v)
        else:
            result[k] = v
    return result


def check_no_secrets_in_text(text: str) -> bool:
    """检查文本中是否包含常见密钥格式。返回 True 表示安全。"""
    if not text:
        return True
    # OpenAI key pattern
    if re.search(r"sk-[A-Za-z0-9]{20,}", text):
        return False
    # Generic API key pattern
    if re.search(r"[A-Za-z0-9]{32,}", text):
        return False
    return True
