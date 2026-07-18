"""Generate public-source-manifest.json with SHA-256 hashes for all synced files."""
import json
import os
import hashlib
from datetime import datetime, timezone, timedelta

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tz = timezone(timedelta(hours=8))
now = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")

files = []
for dirpath, dirnames, filenames in os.walk(root):
    if ".git" in dirpath:
        continue
    for fn in filenames:
        fp = os.path.join(dirpath, fn)
        rel = os.path.relpath(fp, root).replace("\\", "/")
        try:
            with open(fp, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            h = "error"
        files.append({"path": rel, "sha256": h, "synced_at": now})

# Sort by path for consistency
files.sort(key=lambda x: x["path"])

manifest = {
    "version": "1.0",
    "generated_at": now,
    "source_project": "project-015-personal-knowledge-assistant",
    "target_project": "project-016-zwd-portfolio-production",
    "total_files": len(files),
    "files": files,
}

manifest_path = os.path.join(root, "manifests", "public-source-manifest.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f"Manifest generated: {len(files)} files at {manifest_path}")
