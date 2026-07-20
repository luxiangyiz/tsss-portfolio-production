#!/usr/bin/env python3
"""Generate repository-manifest.json — 完整 Git 跟踪文件清单及 SHA-256。

对应方案 V2 阶段 E。该清单用于发布前完整性校验，记录当前 Git 跟踪的所有文件。
- 通过 git ls-files 获取跟踪文件
- 排除 repository-manifest.json 自身（避免自引用哈希）
- 按 path 排序，输出无 BOM 的 UTF-8 JSON
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "manifests" / "repository-manifest.json"
SELF_REL = "manifests/repository-manifest.json"


def git_ls_files() -> list[str]:
    """Return list of git-tracked files (repo-relative, forward slashes)."""
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[ERROR] git ls-files failed: {result.stderr}", file=sys.stderr)
        sys.exit(2)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def canonical_content(path: Path) -> bytes:
    """Return cross-platform bytes for hashing.

    Git normalizes repository text to LF, while Windows worktrees can still
    contain CRLF. UTF-8 text is therefore hashed after CRLF normalization;
    binary files retain their exact bytes.
    """
    data = path.read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return data.replace(b"\r\n", b"\n")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(canonical_content(path)).hexdigest()


def main() -> int:
    tracked = git_ls_files()

    files = []
    for rel in tracked:
        # 排除自身，避免自引用哈希（方案 9.2）
        if rel == SELF_REL:
            continue
        fp = ROOT / rel
        if not fp.exists():
            # git 跟踪但磁盘不存在（异常状态）
            print(f"[WARN] git 跟踪但磁盘不存在: {rel}", file=sys.stderr)
            continue
        files.append({
            "path": rel,
            "sha256": sha256_of(fp),
        })

    # 按 path 排序（Unicode 码点序，跨平台一致）
    files.sort(key=lambda x: x["path"])

    manifest = {
        "version": "2.0",
        "project": "project-016-zwd-portfolio-production",
        "total_files": len(files),
        "files": files,
    }

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 无 BOM UTF-8
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"repository-manifest.json 已生成: {len(files)} 个文件")
    print(f"位置: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
