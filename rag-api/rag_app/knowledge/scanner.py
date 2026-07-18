"""知识库扫描器 — 递归扫描 KB_ROOT，收集所有 Markdown 文件。"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rag_app.core.config import settings
from rag_app.core.exceptions import ConfigurationError


class FileEntry:
    """扫描到的文件条目。"""
    def __init__(self, root: Path, file_path: Path):
        self.root = root
        self.relative_path = str(file_path.relative_to(root))
        self.absolute_path = str(file_path)
        self.file_name = file_path.name
        self.size_bytes = file_path.stat().st_size if file_path.exists() else 0
        self.modified = file_path.stat().st_mtime if file_path.exists() else 0
        self.modified_at = datetime.fromtimestamp(self.modified).isoformat() if self.modified else ""


class Scanner:
    """知识库文件扫描器。"""

    def __init__(self, kb_root: Optional[str] = None):
        self._root = Path(kb_root or settings.kb_root).resolve()
        if not self._root.exists():
            raise ConfigurationError(f"KB_ROOT does not exist: {self._root}")
        if not self._root.is_dir():
            raise ConfigurationError(f"KB_ROOT is not a directory: {self._root}")

        self._yaml = settings.yaml_config
        self._include_dirs: list[str] = self._yaml.get("knowledge_base", {}).get("include_dirs", [])
        self._exclude_dirs: list[str] = self._yaml.get("knowledge_base", {}).get("exclude_dirs", [])
        self._include_ext: list[str] = self._yaml.get("knowledge_base", {}).get("include_extensions", [".md"])
        self._exclude_patterns: list[str] = self._yaml.get("knowledge_base", {}).get("exclude_patterns", [])

    @property
    def root(self) -> Path:
        return self._root

    def scan(self) -> list[FileEntry]:
        """扫描所有候选文件。"""
        entries: list[FileEntry] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            # 过滤排除目录
            rel_dir = str(Path(dirpath).relative_to(self._root))
            if self._is_excluded_dir(rel_dir):
                dirnames.clear()
                continue

            for fname in filenames:
                file_path = Path(dirpath) / fname
                rel_path = str(file_path.relative_to(self._root))

                # 检查扩展名
                if not any(fname.endswith(ext) for ext in self._include_ext):
                    continue

                # 检查排除 pattern
                if any(fname == p or fname.endswith(p.lstrip("*")) for p in self._exclude_patterns):
                    continue

                # 检查是否在纳入目录中
                if not self._is_included_dir(rel_path):
                    continue

                entries.append(FileEntry(self._root, file_path))

        return entries

    def _is_excluded_dir(self, rel_path: str) -> bool:
        for ex in self._exclude_dirs:
            if rel_path == ex or rel_path.startswith(ex + os.sep):
                return True
        return False

    def _is_included_dir(self, rel_path: str) -> bool:
        if not self._include_dirs:
            return True
        for inc in self._include_dirs:
            norm_inc = inc.replace("\\", "/")
            norm_rel = rel_path.replace("\\", "/")
            if norm_rel.startswith(norm_inc + "/") or norm_rel == norm_inc:
                return True
        return False
