#!/usr/bin/env python3
"""Manifest 验证器 — 只读校验 source-sync-manifest 和 repository-manifest。

对应方案 V2 阶段 E（10 项检查）。退出码：
  0 = 全部通过
  1 = 存在校验失败项
  2 = 验证环境错误（文件缺失/无法解析）

检查项：
  1. JSON 可以解析
  2. 必需字段存在
  3. total_files 与数组数量一致
  4. 每个目标文件真实存在
  5. 每个 SHA-256 与文件内容一致
  6. 不存在重复目标路径
  7. 不存在绝对源路径
  8. source-sync-manifest 中的目标文件全部被 Git 跟踪
  9. repository-manifest 与 git ls-files 一致
 10. Manifest 没有包含自身
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = ROOT / "manifests" / "source-sync-manifest.json"
REPO_MANIFEST = ROOT / "manifests" / "repository-manifest.json"

SOURCE_SELF = "manifests/source-sync-manifest.json"
REPO_SELF = "manifests/repository-manifest.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_ls_files() -> set[str]:
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
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def load_json(path: Path, label: str) -> dict | None:
    if not path.exists():
        print(f"[FAIL] {label}: 文件不存在 ({path.relative_to(ROOT)})")
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[FAIL] {label}: JSON 解析失败 — {e}")
        return None


def verify_source_manifest(tracked: set[str]) -> int:
    """校验 source-sync-manifest.json（检查 1-8, 10）。"""
    print("=" * 60)
    print("校验 source-sync-manifest.json")
    print("=" * 60)
    failures = 0

    m = load_json(SOURCE_MANIFEST, "source-sync-manifest")
    if m is None:
        return 1  # 检查 1 失败

    # 检查 2: 必需字段
    required = ["version", "source_project", "target_project", "total_files", "files"]
    for field in required:
        if field not in m:
            print(f"[FAIL] 检查2: 缺少必需字段 '{field}'")
            failures += 1
    if failures:
        return failures

    # 检查 3: total_files 与数组数量一致
    if m["total_files"] != len(m["files"]):
        print(f"[FAIL] 检查3: total_files={m['total_files']} 与实际数组长度 {len(m['files'])} 不一致")
        failures += 1
    else:
        print(f"[PASS] 检查3: total_files={m['total_files']} 一致")

    files = m["files"]
    seen_paths = set()
    dup_paths = []

    for entry in files:
        target = entry.get("target_path", "")
        source = entry.get("source_path", "")
        sha = entry.get("sha256", "")

        # 检查 6: 重复路径
        if target in seen_paths:
            dup_paths.append(target)
        seen_paths.add(target)

        # 检查 7: 绝对源路径（含盘符或以 / 开头）
        if ":" in source or source.startswith("/"):
            print(f"[FAIL] 检查7: 绝对源路径 '{source}' (target={target})")
            failures += 1

        # 检查 10: Manifest 不包含自身
        if target == SOURCE_SELF:
            print(f"[FAIL] 检查10: source-sync-manifest 包含自身条目")
            failures += 1

        # 检查 4: 目标文件存在
        fp = ROOT / target
        if not fp.exists():
            print(f"[FAIL] 检查4: 目标文件不存在 '{target}'")
            failures += 1
            continue

        # 检查 5: SHA-256 一致
        actual = sha256_of(fp)
        if actual != sha:
            print(f"[FAIL] 检查5: 哈希不一致 '{target}'")
            print(f"       manifest: {sha}")
            print(f"       actual:   {actual}")
            failures += 1

    # 检查 6 汇总
    if dup_paths:
        print(f"[FAIL] 检查6: 存在 {len(dup_paths)} 个重复目标路径: {dup_paths[:5]}")
        failures += 1
    else:
        print(f"[PASS] 检查6: 无重复目标路径")

    # 检查 7 汇总
    print(f"[PASS] 检查7: 无绝对源路径" if not any(":" in e.get("source_path", "") or e.get("source_path", "").startswith("/") for e in files) else "")

    # 检查 8: source-sync 目标全部被 Git 跟踪
    untracked = seen_paths - tracked
    if untracked:
        print(f"[FAIL] 检查8: {len(untracked)} 个同步目标未被 Git 跟踪: {sorted(untracked)[:5]}")
        failures += 1
    else:
        print(f"[PASS] 检查8: 全部 {len(seen_paths)} 个同步目标被 Git 跟踪")

    # 检查 10 汇总
    print(f"[PASS] 检查10: Manifest 未包含自身" if not any(e.get("target_path") == SOURCE_SELF for e in files) else "")

    return failures


def verify_repo_manifest(tracked: set[str]) -> int:
    """校验 repository-manifest.json（检查 1-5, 9, 10）。"""
    print()
    print("=" * 60)
    print("校验 repository-manifest.json")
    print("=" * 60)
    failures = 0

    m = load_json(REPO_MANIFEST, "repository-manifest")
    if m is None:
        return 1

    # 检查 2: 必需字段
    required = ["version", "project", "total_files", "files"]
    for field in required:
        if field not in m:
            print(f"[FAIL] 检查2: 缺少必需字段 '{field}'")
            failures += 1
    if failures:
        return failures

    # 检查 3: total_files 一致
    if m["total_files"] != len(m["files"]):
        print(f"[FAIL] 检查3: total_files={m['total_files']} 与数组长度 {len(m['files'])} 不一致")
        failures += 1
    else:
        print(f"[PASS] 检查3: total_files={m['total_files']} 一致")

    files = m["files"]
    manifest_paths = set()
    for entry in files:
        path = entry.get("path", "")
        sha = entry.get("sha256", "")
        manifest_paths.add(path)

        # 检查 10: 不包含自身
        if path == REPO_SELF:
            print(f"[FAIL] 检查10: repository-manifest 包含自身条目")
            failures += 1

        # 检查 4: 文件存在
        fp = ROOT / path
        if not fp.exists():
            print(f"[FAIL] 检查4: 文件不存在 '{path}'")
            failures += 1
            continue

        # 检查 5: SHA-256 一致
        actual = sha256_of(fp)
        if actual != sha:
            print(f"[FAIL] 检查5: 哈希不一致 '{path}'")
            failures += 1

    # 检查 9: repository-manifest 与 git ls-files 一致
    # git ls-files 包含 repository-manifest.json 自身，但 manifest 排除了自身
    expected_tracked = tracked - {REPO_SELF}
    in_git_not_manifest = expected_tracked - manifest_paths
    in_manifest_not_git = manifest_paths - expected_tracked

    if in_git_not_manifest:
        print(f"[FAIL] 检查9: {len(in_git_not_manifest)} 个 Git 跟踪文件未在 Manifest 中: {sorted(in_git_not_manifest)[:5]}")
        failures += 1
    if in_manifest_not_git:
        print(f"[FAIL] 检查9: {len(in_manifest_not_git)} 个 Manifest 文件未被 Git 跟踪: {sorted(in_manifest_not_git)[:5]}")
        failures += 1
    if not in_git_not_manifest and not in_manifest_not_git:
        print(f"[PASS] 检查9: Manifest 与 git ls-files 完全一致 ({len(manifest_paths)} 文件)")

    return failures


def main() -> int:
    if not ROOT.exists():
        print("[ERROR] 项目根目录不存在", file=sys.stderr)
        return 2

    tracked = git_ls_files()

    f1 = verify_source_manifest(tracked)
    f2 = verify_repo_manifest(tracked)

    total = f1 + f2
    print()
    print("=" * 60)
    if total == 0:
        print("Manifest 验证: 全部通过")
    else:
        print(f"Manifest 验证: {total} 项失败")
    print("=" * 60)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
