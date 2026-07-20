#!/usr/bin/env python3
"""敏感信息扫描器 — 4 层扫描覆盖工作区所有 Git 跟踪文本文件。

对应方案 V2 阶段 F。退出码：
  0 = 全部通过
  1 = 发现有效密钥或敏感信息
  2 = 扫描环境错误

四层扫描：
  Layer 1: 敏感文件名（.env / *.pem / *.key / *.pfx / id_rsa / credentials* 等）
  Layer 2: 常见密钥形态（OpenAI/GitHub/AWS/Google/Slack/JWT/PEM/Aliyun/Basic Auth/DB 连接串）
  Layer 3: 个人敏感信息（身份证号 / 银行卡 / 未授权手机号 / 精确住址）
  Layer 4: 拒绝目录和路径（private/ internal/ data/rag/ logs/ backups/ 等）

输出规则（方案 10.4）：不打印完整密钥值，只输出 规则编号/文件路径/行号/风险类型。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ============================================================
# 已授权公开联系信息 allowlist（方案 10.2 layer 3）
# 每项包含：精确值、允许出现的文件路径、用途
# ============================================================
CONTACT_ALLOWLIST = {
    "values": [
        "Tsss9318",                # 微信号
        "15059779318",             # 手机号
        "15059779318@163.com",     # 邮箱
    ],
    # 精确文件列表 — 不使用目录前缀放行（避免新文件自动获得授权）
    "allowed_paths": [
        # 公开联系页（用户确认公开的真实用途）
        "public-content/个人介绍/联系方式.md",
        "wordpress/plugins/zwd-portfolio-core/zwd-portfolio-core.php",
        # 扫描器/配置自身必须包含授权值以实现 allowlist 功能
        "tools/scan-secrets.py",
        ".gitleaks.toml",
        # 文档记载 allowlist（精确到每个文件）
        "docs/GitHub仓库脱敏整改执行方案-V2.md",
        "docs/执行报告-阶段0-4-6.md",
        "docs/仓库脱敏整改执行报告-A-I.md",
        "docs/阶段J-K-GitHub移交说明.md",
    ],
    "allowed_path_prefixes": [],  # 空：不使用前缀放行
    "purpose": "个人网站公开联系方式，已用户确认公开",
}

# 扫描器自测文件 — 含测试用假密钥/假 PII（非真实凭证），跳过 Layer 2/3 内容扫描
SCANNER_TEST_FILES = {
    "tests/security/test_scan_secrets.py",
}

# 已知文档/测试示例值 — 形似密钥但非真实凭证，分类为 info 不阻塞
# 这些值在公开文档中广泛用作示例，不构成泄露
KNOWN_EXAMPLE_VALUES = {
    "sk-" + "abcdefghijklmnopqrstuvwxyz1234",       # 文档负向示例
    "AKIA" + "IOSFODNN7EXAMPLE",                   # AWS 官方文档示例
    "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789", # 测试 fixture
}


def is_path_allowed(rel_path: str, allowlist: dict = None) -> bool:
    """判断该路径是否在联系信息 allowlist 范围内。支持注入用于测试。"""
    if allowlist is None:
        allowlist = CONTACT_ALLOWLIST
    if rel_path in allowlist["allowed_paths"]:
        return True
    for prefix in allowlist.get("allowed_path_prefixes", []):
        if rel_path.startswith(prefix):
            return True
    return False


# ============================================================
# Layer 1: 敏感文件名
# ============================================================
SENSITIVE_FILE_PATTERNS = [
    (re.compile(r"^\.env$", re.I), "ENV", "真实环境变量文件"),
    (re.compile(r"^\.env\.production$", re.I), "ENV", "生产环境变量文件"),
    (re.compile(r"^\.env\.local$", re.I), "ENV", "本地环境变量文件"),
    (re.compile(r".*\.pem$", re.I), "PEM", "PEM 证书/私钥"),
    (re.compile(r".*\.key$", re.I), "KEY", "私钥文件"),
    (re.compile(r".*\.pfx$", re.I), "PFX", "PFX 证书"),
    (re.compile(r"^id_rsa$", re.I), "SSH", "SSH 私钥"),
    (re.compile(r"^id_ed25519$", re.I), "SSH", "SSH 私钥"),
    (re.compile(r"^credentials", re.I), "CRED", "凭证文件"),
    (re.compile(r"^secret", re.I), "SECRET", "密钥文件"),
    (re.compile(r".*\.sqlite$", re.I), "DB", "SQLite 数据库"),
    (re.compile(r".*\.db$", re.I), "DB", "数据库文件"),
    (re.compile(r".*\.dump$", re.I), "DUMP", "数据库导出"),
    (re.compile(r".*\.bak$", re.I), "BAK", "备份文件"),
]

# .env.example / .env.demo.example / production.env.example 是允许的模板
ALLOWED_ENV_TEMPLATES = {
    ".env.example", ".env.demo.example", "production.env.example",
}

# ============================================================
# Layer 2: 密钥形态
# ============================================================
SECRET_PATTERNS = [
    ("SEC-OPENAI",     re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("SEC-AWS-AK",     re.compile(r"AKIA[0-9A-Z]{16}")),
    ("SEC-GITHUB",     re.compile(r"gh[pousr]_[a-zA-Z0-9]{36}")),
    ("SEC-SLACK",      re.compile(r"xox[baprs]-[a-zA-Z0-9-]{10,}")),
    ("SEC-GOOGLE",     re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("SEC-JWT",        re.compile(r"eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}")),
    ("SEC-ALIYUN",     re.compile(r"LTAI[0-9A-Za-z]{12,18}")),
    ("SEC-PEM",        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("SEC-BASICAUTH",  re.compile(r"https?://[^\s/]+:[^\s/]+@[^\s/]+")),
    ("SEC-DBCONN",     re.compile(r"(?:mysql|postgres|mongodb|redis)://[^\s/]+:[^\s/]+@")),
]

# ============================================================
# Layer 3: 个人敏感信息
# 边界规则：使用负向断言确保匹配是独立值，而非 SHA-256 哈希等十六进制串的子串
# ============================================================
PII_PATTERNS = [
    ("PII-IDCARD", re.compile(r"(?<![0-9a-fA-F])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9a-fA-F])")),
    ("PII-BANKCARD", re.compile(r"(?<![0-9a-fA-F])6\d{15,18}(?![0-9a-fA-F])")),
]

# 手机号：1[3-9] 开头 11 位。允许列表中的 15059779318 已排除
# 负向断言避免在 SHA-256 哈希中误匹配
PHONE_PATTERN = re.compile(r"(?<![0-9a-fA-F])1[3-9]\d{9}(?![0-9a-fA-F])")

# ============================================================
# Layer 4: 拒绝目录（根级）
# ============================================================
DENY_ROOT_DIRS = [
    "private", "internal", "ai-job-knowledge-base",
    "data/rag", "logs", "backups",
    ".wp-env-runtime", "node_modules", "__pycache__",
]

DENY_PATH_SEGMENTS = [
    "private", "internal", "__pycache__",
    ".pytest_cache", "node_modules", ".venv", "venv",
    ".wp-env-runtime",
]


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[ERROR] git ls-files 失败: {result.stderr}", file=sys.stderr)
        sys.exit(2)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_text_file(path: Path) -> bool:
    """简单判断是否为文本文件（按扩展名）。"""
    text_exts = {
        ".py", ".php", ".js", ".css", ".json", ".yaml", ".yml", ".md",
        ".txt", ".html", ".conf", ".sh", ".ps1", ".toml", ".env",
        ".example", ".sql", ".env.example", ".env.demo.example",
        ".htaccess", ".ini", ".xml", ".csv",
    }
    # 无扩展名但常见文本文件
    if path.name in {".env", ".gitignore", ".dockerignore", ".gitattributes", ".editorconfig"}:
        return True
    ext = path.suffix.lower()
    if ext in text_exts:
        return True
    # .env.example 等复合扩展名
    if path.name.endswith(".env.example") or path.name.endswith(".env.demo.example"):
        return True
    if path.name == "production.env.example":
        return True
    return False


def scan_layer1_filename(rel_path: str) -> list[dict]:
    """Layer 1: 敏感文件名检查。"""
    findings = []
    name = Path(rel_path).name
    for pattern, rule_id, desc in SENSITIVE_FILE_PATTERNS:
        if pattern.match(name):
            # 允许 env 模板
            if name in ALLOWED_ENV_TEMPLATES:
                continue
            findings.append({
                "rule": rule_id,
                "file": rel_path,
                "line": 0,
                "type": f"敏感文件名: {desc}",
            })
    return findings


def scan_layer2_secrets(rel_path: str, content: str) -> list[dict]:
    """Layer 2: 密钥形态扫描。已知示例值分类为 info（不阻塞）。"""
    findings = []
    for rule_id, pattern in SECRET_PATTERNS:
        for m in pattern.finditer(content):
            line_no = content[:m.start()].count("\n") + 1
            matched_value = m.group()
            severity = "info" if matched_value in KNOWN_EXAMPLE_VALUES else "fail"
            findings.append({
                "rule": rule_id,
                "file": rel_path,
                "line": line_no,
                "type": "密钥形态" if severity == "fail" else "已知示例值（非真实密钥）",
                "severity": severity,
            })
    return findings


def scan_layer3_pii(rel_path: str, content: str, allowlist: dict = None) -> list[dict]:
    """Layer 3: 个人敏感信息扫描（带 allowlist）。支持注入用于测试。"""
    if allowlist is None:
        allowlist = CONTACT_ALLOWLIST
    findings = []
    path_allowed = is_path_allowed(rel_path, allowlist)

    for rule_id, pattern in PII_PATTERNS:
        for m in pattern.finditer(content):
            line_no = content[:m.start()].count("\n") + 1
            findings.append({
                "rule": rule_id,
                "file": rel_path,
                "line": line_no,
                "type": "个人敏感信息",
                "severity": "fail",
            })

    # 已授权联系方式仍必须位于精确批准路径。
    # 这里逐值检查，覆盖手机号、微信号和邮箱；不依赖值本身的格式。
    for value in allowlist["values"]:
        for m in re.finditer(re.escape(value), content):
            if not path_allowed:
                findings.append({
                    "rule": "PII-CONTACT-AUTH-MISPLACED",
                    "file": rel_path,
                    "line": content[:m.start()].count("\n") + 1,
                    "type": "授权联系方式出现在未批准文件",
                    "severity": "fail",
                })

    # 手机号：继续检查所有未授权号码。
    for m in PHONE_PATTERN.finditer(content):
        phone = m.group()
        if phone in allowlist["values"]:
            # 授权值的路径限制已由上面的统一联系方式检查处理。
            continue
        # 未授权手机号
        findings.append({
            "rule": "PII-PHONE",
            "file": rel_path,
            "line": content[:m.start()].count("\n") + 1,
            "type": "未授权手机号",
            "severity": "fail",
        })

    return findings


def scan_layer4_deny(rel_path: str) -> list[dict]:
    """Layer 4: 拒绝目录和路径检查。"""
    findings = []
    normalized = rel_path.replace("\\", "/").lstrip("/")
    segments = normalized.split("/")

    # 根级拒绝目录
    for deny_dir in DENY_ROOT_DIRS:
        if normalized == deny_dir or normalized.startswith(deny_dir + "/"):
            findings.append({
                "rule": "DENY-DIR",
                "file": rel_path,
                "line": 0,
                "type": f"拒绝目录: {deny_dir}",
            })

    # 路径段拒绝（递归检查）
    for seg in segments:
        if seg in DENY_PATH_SEGMENTS:
            findings.append({
                "rule": "DENY-SEG",
                "file": rel_path,
                "line": 0,
                "type": f"拒绝路径段: {seg}",
            })

    return findings


def scan_workspace(scan_root: Path = None) -> list[dict]:
    """扫描工作区所有 Git 跟踪文件。"""
    if scan_root is None:
        scan_root = ROOT

    tracked = git_ls_files()
    all_findings = []

    for rel in tracked:
        fp = scan_root / rel
        if not fp.exists():
            all_findings.append({
                "rule": "MISSING",
                "file": rel,
                "line": 0,
                "type": "Git 跟踪但磁盘不存在",
            })
            continue

        # Layer 1 + Layer 4: 基于文件名/路径
        all_findings.extend(scan_layer1_filename(rel))
        all_findings.extend(scan_layer4_deny(rel))

        # Layer 2 + Layer 3: 基于内容（仅文本文件，且非扫描器自测文件）
        if is_text_file(fp) and rel not in SCANNER_TEST_FILES:
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            all_findings.extend(scan_layer2_secrets(rel, content))
            all_findings.extend(scan_layer3_pii(rel, content))

    return all_findings


def scan_git_history() -> list[dict]:
    """扫描 Git 全历史：文件名 + blob 内容（逐 Commit Blob 扫描）。

    对应方案 V2 阶段 G：真正的完整 Git 历史内容扫描。
    遍历所有提交的所有 blob，对内容执行 Layer 2/3 扫描。
    """
    findings = []

    # --- 第一部分：历史文件名和路径检查 ---
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "log", "--all", "--name-only", "--pretty=format:"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[WARN] git log 历史文件名扫描失败: {result.stderr}", file=sys.stderr)
    else:
        historical_files = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                historical_files.add(line)

        deny_historical = [".env", "id_rsa", "id_ed25519", "credentials.json"]
        for hf in historical_files:
            name = Path(hf).name
            if name in deny_historical:
                findings.append({
                    "rule": "HIST-DENY-FILE",
                    "file": hf,
                    "line": 0,
                    "type": f"历史中存在拒绝文件: {name}",
                })
            normalized = hf.replace("\\", "/").lstrip("/")
            for deny_dir in DENY_ROOT_DIRS:
                if normalized.startswith(deny_dir + "/") or normalized == deny_dir:
                    findings.append({
                        "rule": "HIST-DENY-DIR",
                        "file": hf,
                        "line": 0,
                        "type": f"历史中存在拒绝目录: {deny_dir}",
                    })

    # --- 第二部分：历史 blob 内容扫描（密钥/PII） ---
    # 收集所有提交的所有 blob（去重）
    commits_result = subprocess.run(
        ["git", "rev-list", "--all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if commits_result.returncode != 0:
        print(f"[WARN] git rev-list 失败: {commits_result.stderr}", file=sys.stderr)
        return findings

    commits = [c.strip() for c in commits_result.stdout.splitlines() if c.strip()]
    seen_blobs = {}  # blob_sha -> path（首次出现的路径）

    for commit in commits:
        tree_result = subprocess.run(
            ["git", "ls-tree", "-r", commit],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if tree_result.returncode != 0:
            continue
        for line in tree_result.stdout.splitlines():
            # 格式: <mode> <type> <sha>\t<path>
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            meta, path = parts
            meta_parts = meta.split()
            if len(meta_parts) >= 3 and meta_parts[1] == "blob":
                sha = meta_parts[2]
                if sha not in seen_blobs:
                    seen_blobs[sha] = path

    print(f"  历史唯一 blob 数: {len(seen_blobs)}")

    # 扫描每个唯一 blob 的内容（跳过测试 fixture 文件）
    for sha, path in seen_blobs.items():
        if path in SCANNER_TEST_FILES:
            continue

        blob_result = subprocess.run(
            ["git", "cat-file", "blob", sha],
            cwd=ROOT,
            capture_output=True,
        )
        if blob_result.returncode != 0:
            continue
        try:
            content = blob_result.stdout.decode("utf-8", errors="ignore")
        except Exception:
            continue

        # Layer 2: 密钥形态
        for finding in scan_layer2_secrets(path, content):
            finding["type"] = f"历史 blob: {finding['type']}"
            findings.append(finding)

        # Layer 3: PII（授权值在历史中不报 misplaced）
        for finding in scan_layer3_pii(path, content):
            if finding["rule"] == "PII-CONTACT-AUTH-MISPLACED":
                continue
            finding["type"] = f"历史 blob: {finding['type']}"
            findings.append(finding)

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="敏感信息扫描器")
    parser.add_argument("--history", action="store_true", help="同时扫描 Git 全历史")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--output", type=str, help="JSON 报告输出路径")
    args = parser.parse_args()

    print("=" * 60)
    print("敏感信息扫描 — 4 层覆盖")
    print("=" * 60)

    findings = scan_workspace()

    if args.history:
        print()
        print("--- Git 历史扫描 ---")
        hist_findings = scan_git_history()
        findings.extend(hist_findings)

    # 输出
    if args.json or args.output:
        # info 级别不阻塞，但仍记录在报告中
        blocking = [f for f in findings if f.get("severity", "fail") == "fail"]
        report = {
            "total_findings": len(findings),
            "blocking_findings": len(blocking),
            "findings": findings,
        }
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(report_json, encoding="utf-8")
            print(f"报告已写入: {args.output}")
        if args.json:
            print(report_json)
    else:
        # 控制台输出（不打印密钥原文）
        if findings:
            print()
            for f in findings:
                sev = f.get("severity", "fail")
                icon = "[FAIL]" if sev == "fail" else "[INFO]"
                print(f"  {icon} {f['rule']} | {f['file']}:{f['line']} | {f['type']}")
        print()
        blocking = [f for f in findings if f.get("severity", "fail") == "fail"]
        print(f"发现 {len(findings)} 项（阻塞 {len(blocking)}，已知示例 {len(findings) - len(blocking)}）")

    print()
    blocking = [f for f in findings if f.get("severity", "fail") == "fail"]
    if blocking:
        print("扫描结果: 失败")
        return 1
    else:
        print("扫描结果: 通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
