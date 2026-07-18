"""扫描器自身测试 — 正例和反例（对应方案 V2 阶段 F 10.5）。

测试覆盖：
  - 正例：真实密钥/敏感文件名/拒绝目录应被检出
  - 反例：授权联系信息在批准路径/占位符/哈希内嵌数字不应被检出
"""
import importlib.util
import sys
from pathlib import Path

import pytest

# 加载 tools/scan-secrets.py（非标准包，按文件路径加载）
_SCANNER_PATH = Path(__file__).resolve().parent.parent.parent / "tools" / "scan-secrets.py"
_spec = importlib.util.spec_from_file_location("scan_secrets", _SCANNER_PATH)
scan_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_secrets)


# ============================================================
# Layer 1: 敏感文件名
# ============================================================

class TestLayer1SensitiveFilename:
    def test_real_env_file_detected(self):
        """正例：真实 .env 文件应被检出。"""
        findings = scan_secrets.scan_layer1_filename(".env")
        assert any(f["rule"] == "ENV" for f in findings)

    def test_env_production_detected(self):
        """正例：.env.production 应被检出。"""
        findings = scan_secrets.scan_layer1_filename(".env.production")
        assert any(f["rule"] == "ENV" for f in findings)

    def test_pem_key_detected(self):
        """正例：*.pem 文件应被检出。"""
        findings = scan_secrets.scan_layer1_filename("secret.pem")
        assert any(f["rule"] == "PEM" for f in findings)

    def test_id_rsa_detected(self):
        """正例：id_rsa 应被检出。"""
        findings = scan_secrets.scan_layer1_filename("id_rsa")
        assert any(f["rule"] == "SSH" for f in findings)

    def test_sqlite_detected(self):
        """正例：*.sqlite 应被检出。"""
        findings = scan_secrets.scan_layer1_filename("data.sqlite")
        assert any(f["rule"] == "DB" for f in findings)

    def test_env_example_not_detected(self):
        """反例：.env.example 模板不应被检出。"""
        findings = scan_secrets.scan_layer1_filename(".env.example")
        assert not any(f["rule"] == "ENV" for f in findings)

    def test_env_demo_example_not_detected(self):
        """反例：.env.demo.example 模板不应被检出。"""
        findings = scan_secrets.scan_layer1_filename(".env.demo.example")
        assert not any(f["rule"] == "ENV" for f in findings)

    def test_production_env_example_not_detected(self):
        """反例：production.env.example 模板不应被检出。"""
        findings = scan_secrets.scan_layer1_filename("production.env.example")
        assert not any(f["rule"] == "ENV" for f in findings)

    def test_normal_source_not_detected(self):
        """反例：普通源码文件名不应被检出。"""
        findings = scan_secrets.scan_layer1_filename("main.py")
        assert len(findings) == 0


# ============================================================
# Layer 2: 密钥形态
# ============================================================

class TestLayer2SecretPatterns:
    def test_openai_key_detected(self):
        """正例：OpenAI API Key 应被检出。"""
        content = 'LLM_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234'
        findings = scan_secrets.scan_layer2_secrets("config.yaml", content)
        assert any(f["rule"] == "SEC-OPENAI" for f in findings)

    def test_github_pat_detected(self):
        """正例：GitHub PAT 应被检出。"""
        content = 'GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789'
        findings = scan_secrets.scan_layer2_secrets("config.yml", content)
        assert any(f["rule"] == "SEC-GITHUB" for f in findings)

    def test_aws_key_detected(self):
        """正例：AWS Access Key 应被检出。"""
        content = 'AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE'
        findings = scan_secrets.scan_layer2_secrets("deploy.sh", content)
        assert any(f["rule"] == "SEC-AWS-AK" for f in findings)

    def test_pem_private_key_detected(self):
        """正例：PEM 私钥头应被检出。"""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        findings = scan_secrets.scan_layer2_secrets("key.pem", content)
        assert any(f["rule"] == "SEC-PEM" for f in findings)

    def test_jwt_detected(self):
        """正例：JWT 应被检出。"""
        content = 'token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        findings = scan_secrets.scan_layer2_secrets("auth.json", content)
        assert any(f["rule"] == "SEC-JWT" for f in findings)

    def test_basic_auth_detected(self):
        """正例：Basic Auth URL 应被检出。"""
        content = 'DB_URL=https://user:secretpass@example.com/db'
        findings = scan_secrets.scan_layer2_secrets("config.conf", content)
        assert any(f["rule"] == "SEC-BASICAUTH" for f in findings)

    def test_short_placeholder_not_detected(self):
        """反例：sk-your-key 短占位符（<20位）不应被检出。"""
        content = 'LLM_API_KEY=sk-your-key'
        findings = scan_secrets.scan_layer2_secrets("config.yaml", content)
        assert not any(f["rule"] == "SEC-OPENAI" for f in findings)

    def test_replace_placeholder_not_detected(self):
        """反例：replace-with-secret-at-deploy-time 不应被检出。"""
        content = 'LLM_API_KEY=replace-with-secret-at-deploy-time'
        findings = scan_secrets.scan_layer2_secrets("production.env.example", content)
        assert len(findings) == 0


# ============================================================
# Layer 3: 个人敏感信息
# ============================================================

class TestLayer3PII:
    def test_id_card_detected(self):
        """正例：身份证号应被检出。"""
        content = "身份证：350203199001011234"
        findings = scan_secrets.scan_layer3_pii("doc.md", content)
        assert any(f["rule"] == "PII-IDCARD" for f in findings)

    def test_unauthorized_phone_detected(self):
        """正例：未授权手机号应被检出。"""
        content = "联系电话：13800138000"
        findings = scan_secrets.scan_layer3_pii("doc.md", content)
        assert any(f["rule"] == "PII-PHONE" for f in findings)

    def test_authorized_phone_in_approved_path(self):
        """反例：授权手机号在批准路径不应被检出。"""
        content = "手机号：15059779318"
        findings = scan_secrets.scan_layer3_pii(
            "public-content/个人介绍/联系方式.md", content
        )
        assert not any(f["rule"] == "PII-PHONE" for f in findings)

    def test_authorized_phone_in_docs(self):
        """反例：授权手机号在 docs/ 不应被检出（文档记载 allowlist）。"""
        content = "手机号：15059779318"
        findings = scan_secrets.scan_layer3_pii(
            "docs/some-report.md", content
        )
        assert not any(f["rule"] == "PII-PHONE" for f in findings)

    def test_authorized_phone_misplaced_detected(self):
        """正例：授权手机号出现在未批准路径应被检出。"""
        content = "联系方式：15059779318"
        findings = scan_secrets.scan_layer3_pii(
            "wordpress/themes/zwd-portfolio/footer.php", content
        )
        assert any(f["rule"] == "PII-PHONE-AUTH-MISPLACED" for f in findings)

    def test_phone_in_hash_not_detected(self):
        """反例：SHA-256 哈希中的数字子串不应被当作手机号。"""
        # 这是一个真实的 SHA-256 哈希样例
        content = '"sha256": "e8af9aa996a534235d9ec5fce830cff9e345ed22b8113e4fac1cfc0ba6cc6b20"'
        findings = scan_secrets.scan_layer3_pii("manifests/test.json", content)
        assert not any(f["rule"] == "PII-PHONE" for f in findings)

    def test_bank_card_detected(self):
        """正例：银行卡号应被检出。"""
        content = "卡号：6222021234567890123"
        findings = scan_secrets.scan_layer3_pii("doc.md", content)
        assert any(f["rule"] == "PII-BANKCARD" for f in findings)


# ============================================================
# Layer 4: 拒绝目录
# ============================================================

class TestLayer4DenyPaths:
    def test_private_dir_detected(self):
        """正例：private/ 目录应被检出。"""
        findings = scan_secrets.scan_layer4_deny("private/secret.md")
        assert any(f["rule"] == "DENY-DIR" for f in findings)

    def test_internal_dir_detected(self):
        """正例：internal/ 目录应被检出。"""
        findings = scan_secrets.scan_layer4_deny("internal/notes.md")
        assert any(f["rule"] == "DENY-DIR" for f in findings)

    def test_ai_job_kb_detected(self):
        """正例：ai-job-knowledge-base/ 应被检出。"""
        findings = scan_secrets.scan_layer4_deny("ai-job-knowledge-base/01-个人基础档案/info.md")
        assert any(f["rule"] == "DENY-DIR" for f in findings)

    def test_data_rag_detected(self):
        """正例：data/rag/ 应被检出。"""
        findings = scan_secrets.scan_layer4_deny("data/rag/qdrant.cfg")
        assert any(f["rule"] == "DENY-DIR" for f in findings)

    def test_pycache_segment_detected(self):
        """正例：__pycache__ 路径段应被检出。"""
        findings = scan_secrets.scan_layer4_deny("rag-api/rag_app/__pycache__/module.cpython-312.pyc")
        assert any(f["rule"] == "DENY-SEG" for f in findings)

    def test_normal_path_not_detected(self):
        """反例：正常路径不应被检出。"""
        findings = scan_secrets.scan_layer4_deny("rag-api/rag_app/main.py")
        assert len(findings) == 0

    def test_theme_data_subdir_not_detected(self):
        """反例：主题 assets/src/data/ 不应被当作拒绝目录。"""
        findings = scan_secrets.scan_layer4_deny(
            "wordpress/themes/zwd-portfolio/assets/src/data/navigation-items.js"
        )
        assert len(findings) == 0

    def test_public_content_not_detected(self):
        """反例：public-content/ 不应被检出。"""
        findings = scan_secrets.scan_layer4_deny("public-content/个人介绍/联系方式.md")
        assert len(findings) == 0
