"""快速验证脚本 — 测试扫描、解析、隐私路由。"""

import sys
sys.path.insert(0, "src")

from rag_app.core.config import settings
from rag_app.knowledge.scanner import Scanner
from rag_app.knowledge.markdown_parser import MarkdownParser
from rag_app.knowledge.metadata_validator import MetadataValidator
from rag_app.knowledge.inclusion_policy import InclusionPolicy
from rag_app.knowledge.privacy_router import PrivacyRouter

print("=" * 60)
print("RAG 系统验证")
print("=" * 60)

# 1. 配置
print(f"\nKB_ROOT: {settings.kb_root}")
print(f"Chunk Size: {settings.rag_chunk_size}, Top-K: {settings.rag_top_k}")

# 2. 扫描
scanner = Scanner()
files = scanner.scan()
print(f"\n扫描到 {len(files)} 个 Markdown 文件")

# 3. 解析
parser = MarkdownParser()
validator = MetadataValidator()
policy = InclusionPolicy()
router = PrivacyRouter()

stats = {"private": 0, "internal": 0, "public": 0, "excluded": 0, "errors": 0}
collections = {"kb_private": 0, "kb_internal": 0, "kb_public": 0}

for fe in files[:10]:  # 只检查前10个
    kb = parser.parse(fe)
    errs = kb.parse_errors + validator.validate(kb)
    if errs:
        stats["errors"] += 1
        print(f"  ⚠️ {kb.file_name}: {errs[0]}")
        continue

    included, reason = policy.should_include(kb)
    if not included:
        stats["excluded"] += 1
        continue

    fm = kb.frontmatter
    stats[fm.privacy_level] = stats.get(fm.privacy_level, 0) + 1
    cols = router.route(kb)
    for c in cols:
        collections[c] = collections.get(c, 0) + 1

print(f"\n隐私分布: private={stats.get('private',0)}, internal={stats.get('internal',0)}, public={stats.get('public',0)}")
print(f"排除: {stats['excluded']}, 错误: {stats['errors']}")
print(f"Collection 分布: {collections}")
print("\n✅ 所有模块导入和基础流程正常")
