import sys
sys.path.insert(0, "src")

from rag_app.services.ingestion_service import IngestionService

svc = IngestionService()
assert svc._embeddings is None, "Preview should not create embeddings"
preview = svc.preview()
print(f"Preview OK: scanned={preview['scanned_files']}, included={preview['included_files']}, rejected={preview['rejected_files']}")
assert isinstance(preview, dict), "Preview must return dict"
print("TypeOK: returns dict")

# 验证 InclusionPolicy 拒绝缺少 id 的文件
from rag_app.models.documents import KBFile
from rag_app.knowledge.inclusion_policy import InclusionPolicy
policy = InclusionPolicy()
kf_no_id = KBFile(relative_path="test/missing_id.md", absolute_path="/fake/test.md", file_name="test.md")
kf_no_id.frontmatter.doc_id = ""
kf_no_id.frontmatter.privacy_level = "internal"
inc, reason = policy.should_include(kf_no_id)
assert not inc, f"Should reject missing id, got reason={reason}"
print(f"InclusionPolicy OK: missing id rejected ({reason})")

kf_no_privacy = KBFile(relative_path="test/no_privacy.md", absolute_path="/fake/test.md", file_name="test.md")
kf_no_privacy.frontmatter.doc_id = "kb-test"
kf_no_privacy.frontmatter.privacy_level = ""
inc, reason = policy.should_include(kf_no_privacy)
assert not inc, f"Should reject missing privacy_level, got reason={reason}"
print(f"InclusionPolicy OK: missing privacy_level rejected ({reason})")

print("\nAll checks passed")
