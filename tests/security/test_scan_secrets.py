"""扫描器自身测试 — 正例和反例（对应方案 V2 阶段 F 10.5）。

测试覆盖：
  - 正例：真实密钥/敏感文件名/拒绝目录应被检出
  - 反例：授权联系信息在批准路径/占位符/哈希内嵌数字不应被检出

注意：本测试使用虚假 allowlist（FAKE_ALLOWLIST）和虚假联系信息，
不包含任何真实联系方式。通过 allowlist 参数注入实现隔离。
"""
import importlib.util
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# 加载 tools/scan-secrets.py（非标准包，按文件路径加载）
_SCANNER_PATH = Path(__file__).resolve().parent.parent.parent / "tools" / "scan-secrets.py"
_spec = importlib.util.spec_from_file_location("scan_secrets", _SCANNER_PATH)
scan_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_secrets)

# ============================================================
# 虚假 allowlist — 用于测试，不含任何真实联系方式
# ============================================================
FAKE_ALLOWLIST = {
    "values": [
        "FAKEWX001",            # 虚假微信号
        "13900000000",          # 虚假手机号
        "fake@example.test",    # 虚假邮箱
    ],
    "allowed_paths": [
        "public-content/fake-contact.md",
        "fake-plugin/render.php",
    ],
    "allowed_path_prefixes": [],
    "purpose": "测试用虚假 allowlist",
}


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
        content = "LLM_API_KEY=" + "sk-" + "t3stK3yAbCdEf1234567890XYZ"
        findings = scan_secrets.scan_layer2_secrets("config.yaml", content)
        assert any(f["rule"] == "SEC-OPENAI" and f["severity"] == "fail" for f in findings)

    def test_github_pat_detected(self):
        """正例：GitHub PAT 应被检出。"""
        content = "GITHUB_TOKEN=" + "ghp_" + "t3stT0k3nAbCdEfGhIjKlMnOpQrStUv0123456"
        findings = scan_secrets.scan_layer2_secrets("config.yml", content)
        assert any(f["rule"] == "SEC-GITHUB" and f["severity"] == "fail" for f in findings)

    def test_aws_key_detected(self):
        """正例：AWS Access Key 应被检出。"""
        content = "AWS_ACCESS_KEY_ID=" + "AKIA" + "TESTKEY1234567890"
        findings = scan_secrets.scan_layer2_secrets("deploy.sh", content)
        assert any(f["rule"] == "SEC-AWS-AK" and f["severity"] == "fail" for f in findings)

    def test_pem_private_key_detected(self):
        """正例：PEM 私钥头应被检出。"""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        findings = scan_secrets.scan_layer2_secrets("key.pem", content)
        assert any(f["rule"] == "SEC-PEM" and f["severity"] == "fail" for f in findings)

    def test_jwt_detected(self):
        """正例：JWT 应被检出。"""
        content = "token=" + "eyJ" + "t3stHeader.eyJt3stPayload.t3stSignature123abc"
        findings = scan_secrets.scan_layer2_secrets("auth.json", content)
        assert any(f["rule"] == "SEC-JWT" and f["severity"] == "fail" for f in findings)

    def test_basic_auth_detected(self):
        """正例：Basic Auth URL 应被检出。"""
        content = "DB_URL=https://" + "user:secretpass@" + "example.com/db"
        findings = scan_secrets.scan_layer2_secrets("config.conf", content)
        assert any(f["rule"] == "SEC-BASICAUTH" and f["severity"] == "fail" for f in findings)

    def test_known_example_classified_as_info(self):
        """反例：已知示例值应分类为 info（非阻塞）。"""
        content = "KEY=" + "sk-" + "abcdefghijklmnopqrstuvwxyz1234"
        findings = scan_secrets.scan_layer2_secrets("config.yaml", content)
        sec_findings = [f for f in findings if f["rule"] == "SEC-OPENAI"]
        assert len(sec_findings) == 1
        assert sec_findings[0]["severity"] == "info"

    def test_replace_placeholder_not_detected(self):
        """反例：replace-with-secret-at-deploy-time 不应被检出。"""
        content = 'LLM_API_KEY=replace-with-secret-at-deploy-time'
        findings = scan_secrets.scan_layer2_secrets("production.env.example", content)
        assert len(findings) == 0


# ============================================================
# Layer 3: 个人敏感信息（使用虚假 allowlist）
# ============================================================

class TestLayer3PII:
    def test_id_card_detected(self):
        """正例：身份证号应被检出。"""
        content = "身份证：350203199001011234"
        findings = scan_secrets.scan_layer3_pii("doc.md", content, FAKE_ALLOWLIST)
        assert any(f["rule"] == "PII-IDCARD" for f in findings)

    def test_unauthorized_phone_detected(self):
        """正例：未授权手机号应被检出。"""
        content = "联系电话：13800138000"
        findings = scan_secrets.scan_layer3_pii("doc.md", content, FAKE_ALLOWLIST)
        assert any(f["rule"] == "PII-PHONE" for f in findings)

    def test_authorized_phone_in_approved_path(self):
        """反例：授权手机号在批准路径不应被检出。"""
        content = "手机号：13900000000"
        findings = scan_secrets.scan_layer3_pii(
            "public-content/fake-contact.md", content, FAKE_ALLOWLIST
        )
        assert not any(f["rule"] == "PII-PHONE" for f in findings)

    def test_authorized_phone_in_unapproved_detected(self):
        """正例：授权手机号出现在未批准路径应被检出。"""
        content = "联系方式：13900000000"
        findings = scan_secrets.scan_layer3_pii(
            "wordpress/themes/zwd-portfolio/footer.php", content, FAKE_ALLOWLIST
        )
        assert any(f["rule"] == "PII-CONTACT-AUTH-MISPLACED" for f in findings)

    def test_authorized_wechat_in_approved_path(self):
        """反例：授权微信号在批准路径不应被检出。"""
        content = "微信号：FAKEWX001"
        findings = scan_secrets.scan_layer3_pii(
            "public-content/fake-contact.md", content, FAKE_ALLOWLIST
        )
        assert not any(f["rule"] == "PII-CONTACT-AUTH-MISPLACED" for f in findings)

    def test_authorized_wechat_in_unapproved_detected(self):
        """正例：授权微信号出现在未批准路径应被检出。"""
        content = "微信号：FAKEWX001"
        findings = scan_secrets.scan_layer3_pii(
            "wordpress/themes/zwd-portfolio/footer.php", content, FAKE_ALLOWLIST
        )
        assert any(f["rule"] == "PII-CONTACT-AUTH-MISPLACED" for f in findings)

    def test_authorized_email_in_approved_path(self):
        """反例：授权邮箱在批准路径不应被检出。"""
        content = "邮箱：fake@example.test"
        findings = scan_secrets.scan_layer3_pii(
            "public-content/fake-contact.md", content, FAKE_ALLOWLIST
        )
        assert not any(f["rule"] == "PII-CONTACT-AUTH-MISPLACED" for f in findings)

    def test_authorized_email_in_unapproved_detected(self):
        """正例：授权邮箱出现在未批准路径应被检出。"""
        content = "邮箱：fake@example.test"
        findings = scan_secrets.scan_layer3_pii(
            "wordpress/themes/zwd-portfolio/footer.php", content, FAKE_ALLOWLIST
        )
        assert any(f["rule"] == "PII-CONTACT-AUTH-MISPLACED" for f in findings)

    def test_phone_in_hash_not_detected(self):
        """反例：SHA-256 哈希中的数字子串不应被当作手机号。"""
        content = '"sha256": "e8af9aa996a534235d9ec5fce830cff9e345ed22b8113e4fac1cfc0ba6cc6b20"'
        findings = scan_secrets.scan_layer3_pii("manifests/test.json", content, FAKE_ALLOWLIST)
        assert not any(f["rule"] == "PII-PHONE" for f in findings)

    def test_bank_card_detected(self):
        """正例：银行卡号应被检出。"""
        content = "卡号：6222021234567890123"
        findings = scan_secrets.scan_layer3_pii("doc.md", content, FAKE_ALLOWLIST)
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


# ============================================================
# 白名单同步真实执行测试
# ============================================================

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SYNC_SCRIPT = _PROJECT_ROOT / "tools" / "sync-public-source.ps1"


def _powershell_executable() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if not executable:
        pytest.skip("PowerShell is unavailable")
    return executable


def _write_public_markdown(path: Path, *, valid: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = """
privacy_level: public
publish_status: published
review_status: approved
verification_status: verified
""".strip()
    if not valid:
        fields = """
privacy_level: public
publish_status: draft
review_status: approved
""".strip()
    path.write_text(f"---\n{fields}\n---\n\n# 测试公开内容\n", encoding="utf-8")


def _prepare_sync_source(root: Path) -> None:
    files = {
        "src/wordpress/themes/zwd-portfolio/style.css": "/* test theme */\n",
        "src/wordpress/plugins/zwd-portfolio-core/zwd-portfolio-core.php": "<?php\n",
        "src/rag_app/public_main.py": '"""test public app"""\n',
        "requirements.txt": "fastapi==0.1.0\n",
        "tests/test_public.py": "def test_public(): assert True\n",
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _write_public_markdown(
        root / "ai-job-knowledge-base/12-网站公开候选/个人介绍/公开资料.md"
    )


def _run_sync(source: Path, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-File",
            str(_SYNC_SCRIPT),
            "-SourceRoot",
            str(source),
            "-TargetRoot",
            str(target),
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


class TestSyncPolicy:
    def test_sync_is_idempotent_and_preserves_owned_files(self, tmp_path: Path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        _prepare_sync_source(source)

        owned_file = target / "deploy/owned.conf"
        owned_file.parent.mkdir(parents=True, exist_ok=True)
        owned_file.write_text("production-owned\n", encoding="utf-8")

        first = _run_sync(source, target)
        assert first.returncode == 0, first.stdout + first.stderr
        first_hashes = _tree_hashes(target)

        second = _run_sync(source, target)
        assert second.returncode == 0, second.stdout + second.stderr
        assert _tree_hashes(target) == first_hashes
        assert owned_file.read_text(encoding="utf-8") == "production-owned\n"

    def test_source_withdrawal_removes_only_synced_file(self, tmp_path: Path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        _prepare_sync_source(source)

        owned_file = target / "deploy/owned.conf"
        owned_file.parent.mkdir(parents=True, exist_ok=True)
        owned_file.write_text("keep\n", encoding="utf-8")

        first = _run_sync(source, target)
        assert first.returncode == 0, first.stdout + first.stderr

        source_file = source / "src/rag_app/public_main.py"
        target_file = target / "rag-api/rag_app/public_main.py"
        assert target_file.exists()
        source_file.unlink()

        second = _run_sync(source, target)
        assert second.returncode == 0, second.stdout + second.stderr
        assert not target_file.exists()
        assert owned_file.exists()

    def test_invalid_public_metadata_blocks_sync(self, tmp_path: Path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        _prepare_sync_source(source)
        _write_public_markdown(
            source / "ai-job-knowledge-base/12-网站公开候选/个人介绍/未审核资料.md",
            valid=False,
        )

        result = _run_sync(source, target)
        assert result.returncode != 0
