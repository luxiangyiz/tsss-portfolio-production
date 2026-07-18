#!/usr/bin/env python3
"""公开内容四字段验证器 — 校验 public-content/**/*.md 的 Front Matter。

对应方案 V2 阶段 H 检查 8 和阶段 I public-content-gate。
退出码：0=通过，1=存在失败项，2=环境错误

四字段强制门槛（方案 8.5）：
  privacy_level:       public
  publish_status:      published
  review_status:       approved
  verification_status: verified

以下情况均失败：字段缺失、值为空、值错误、Front Matter 无法解析。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_CONTENT = ROOT / "public-content"

REQUIRED_FIELDS = {
    "privacy_level": "public",
    "publish_status": "published",
    "review_status": "approved",
    "verification_status": "verified",
}

FRONT_MATTER_RE = re.compile(r"(?s)^---\s*\r?\n(.*?)\r?\n---\s*(\r?\n|$)")


def parse_front_matter(content: str) -> dict | None:
    """解析 YAML Front Matter，返回字段字典。无法解析返回 None。"""
    m = FRONT_MATTER_RE.match(content)
    if not m:
        return None
    fm = m.group(1)
    result = {}
    for line in fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            result[key.strip()] = val
    return result


def validate_file(path: Path) -> list[str]:
    """校验单个 md 文件，返回失败原因列表（空列表=通过）。"""
    failures = []
    rel = path.relative_to(ROOT).as_posix()

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{rel}: 无法读取 — {e}"]

    if not content.strip():
        return [f"{rel}: 文件为空"]

    fm = parse_front_matter(content)
    if fm is None:
        return [f"{rel}: 缺少 YAML Front Matter（--- ... ---）"]

    for field, expected in REQUIRED_FIELDS.items():
        if field not in fm:
            failures.append(f"{rel}: 缺少字段 {field}（应为 {expected}）")
        elif fm[field] == "":
            failures.append(f"{rel}: {field} 值为空（应为 {expected}）")
        elif fm[field] != expected:
            failures.append(f"{rel}: {field} 值为 '{fm[field]}'（应为 {expected}）")

    return failures


def main() -> int:
    if not PUBLIC_CONTENT.exists():
        print(f"[ERROR] public-content 目录不存在: {PUBLIC_CONTENT}", file=sys.stderr)
        return 2

    md_files = sorted(PUBLIC_CONTENT.rglob("*.md"))
    if not md_files:
        print("[FAIL] public-content 中无 Markdown 文件")
        return 1

    all_failures = []
    pass_count = 0
    for md in md_files:
        failures = validate_file(md)
        if failures:
            all_failures.extend(failures)
            print(f"  [FAIL] {md.name}")
            for f in failures:
                print(f"         {f}")
        else:
            pass_count += 1
            print(f"  [PASS] {md.name}")

    print()
    print(f"公开内容校验: {pass_count}/{len(md_files)} 通过")

    if all_failures:
        print(f"结果: 失败（{len(all_failures)} 项问题）")
        return 1
    else:
        print("结果: 通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
