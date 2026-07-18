"""评测执行器 V2 — 检索评测用 /search，拒答评测用 /ask。"""

import os, sys, json, tempfile, shutil
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.fixtures.fake_embeddings import FakeEmbeddings
from tests.fixtures.fake_chat_model import FakeChatModel
from tests.evaluation.eval_questions import EVALUATION_QUESTIONS

FAKE_DIM = 128
KB_ROOT = _PROJECT_ROOT / "ai-job-knowledge-base"


def _fake_emb():
    return FakeEmbeddings(dimension=FAKE_DIM)

def _fake_chat():
    return FakeChatModel()


def run_evaluation():
    data_dir = tempfile.mkdtemp(prefix="eval_rag_")
    results_path = _PROJECT_ROOT / "logs" / "evaluation-results.json"

    try:
        import rag_app.core.config as cfg
        orig = {k: getattr(cfg.settings, k) for k in [
            "kb_root", "rag_data_dir", "qdrant_path", "embedding_dimension", "relevance_threshold"
        ]}
        cfg.settings.kb_root = str(KB_ROOT)
        cfg.settings.rag_data_dir = data_dir
        cfg.settings.qdrant_path = os.path.join(data_dir, "qdrant")
        cfg.settings.embedding_dimension = FAKE_DIM
        cfg.settings.relevance_threshold = 0.0

        from rag_app.main import app
        with (
            patch("rag_app.langchain_components.embeddings.create_embeddings", _fake_emb),
            patch("rag_app.services.ingestion_service.create_embeddings", _fake_emb),
            patch("rag_app.services.search_service.create_embeddings", _fake_emb),
            patch("rag_app.langchain_components.chat_model.create_chat_model", _fake_chat),
            patch("rag_app.services.answer_service.create_chat_model", _fake_chat),
            TestClient(app) as client,
        ):
            # Build
            r = client.post("/ingest", json={"mode": "full", "scope": "all"})
            print(f"Build: {r.json()['total_chunks']} chunks\n")

            results = []
            for q in EVALUATION_QUESTIONS:
                # Phase 1: 检索评测 — 用 /search 测试 Recall
                r_search = client.post("/search", json={
                    "query": q["question"], "index_scope": q["scope"], "top_k": 5
                })
                search_data = r_search.json()
                hits = search_data.get("hits", [])
                retrieved_docs = [h["metadata"].get("document_id", "") for h in hits]

                # Phase 2: 问答评测 — 用 /ask 测试状态
                r_ask = client.post("/ask", json={
                    "question": q["question"], "index_scope": q["scope"], "top_k": 5
                })
                ask_data = r_ask.json()
                citations = ask_data.get("citations", [])

                # Recall@5
                expected = q.get("expected_document_ids", [])
                recall_ok = bool(expected) and any(ed in retrieved_docs for ed in expected)

                # Citation validity
                citations_valid = _validate_citations(citations, KB_ROOT)

                # Forbidden hits
                forbidden_hit = any(fd in retrieved_docs for fd in q.get("forbidden_document_ids", []))

                results.append({
                    "id": q["id"], "question": q["question"],
                    "expected_status": q["expected_status"],
                    "actual_status": ask_data["status"],
                    "retrieved_docs": retrieved_docs,
                    "expected_docs": expected,
                    "recall_ok": recall_ok,
                    "must_refuse": q.get("must_refuse", False),
                    "requires_pending": q.get("requires_pending_notice", False),
                    "has_disclaimer": bool(ask_data.get("disclaimer")),
                    "citations_count": len(citations),
                    "citations_valid": citations_valid,
                    "forbidden_hit": forbidden_hit,
                })

            # Compute metrics
            has_answer_qs = [r for r in results if r["expected_docs"]]
            must_refuse_qs = [r for r in results if r["must_refuse"]]

            recall_hits = sum(1 for r in has_answer_qs if r["recall_ok"])
            recall_at_5 = recall_hits / len(has_answer_qs) * 100 if has_answer_qs else 100

            all_citations = [v for r in results for v in r["citations_valid"]]
            citation_correct = sum(1 for v in all_citations if v) if all_citations else 0
            citation_rate = citation_correct / len(all_citations) * 100 if all_citations else 100

            refused_correct = sum(1 for r in must_refuse_qs if r["actual_status"] == "insufficient_context")
            refusal_rate = refused_correct / len(must_refuse_qs) * 100 if must_refuse_qs else 100

            pending_qs = [r for r in results if r["requires_pending"]]
            pending_ok = sum(1 for r in pending_qs if r["has_disclaimer"])
            pending_rate = pending_ok / len(pending_qs) * 100 if pending_qs else 100

            forbidden_hits = sum(1 for r in results if r["forbidden_hit"])
            status_match = sum(1 for r in results if r["actual_status"] == r["expected_status"])

            # Print
            print(f"{'='*60}")
            print(f"Evaluation Results V2 ({len(results)} questions)")
            print(f"{'='*60}")
            print(f"Status match: {status_match}/{len(results)} ({status_match/len(results)*100:.0f}%)")
            print(f"Recall@5: {recall_at_5:.1f}%  (检索召回：{recall_hits}/{len(has_answer_qs)})")
            print(f"Citation accuracy: {citation_rate:.1f}%")
            print(f"Refusal rate: {refusal_rate:.1f}%  ({refused_correct}/{len(must_refuse_qs)})")
            print(f"Pending notice rate: {pending_rate:.1f}%")
            print(f"Privacy violations: {forbidden_hits}")
            print()

            for r in results:
                m = "PASS" if r["actual_status"] == r["expected_status"] else "FAIL"
                rec = "R" if r["recall_ok"] else ("-" if not r["expected_docs"] else "X")
                print(f"[{m} {rec}] {r['id']}: exp={r['expected_status']} act={r['actual_status']} cites={r['citations_count']} docs={r['retrieved_docs'][:3]}")

            # Save JSON
            results_path.parent.mkdir(parents=True, exist_ok=True)
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump({
                    "recall_at_5": round(recall_at_5, 1),
                    "citation_accuracy": round(citation_rate, 1),
                    "refusal_rate": round(refusal_rate, 1),
                    "pending_rate": round(pending_rate, 1),
                    "privacy_violations": forbidden_hits,
                    "status_match": f"{status_match}/{len(results)}",
                    "results": results,
                }, f, ensure_ascii=False, indent=2)
            print(f"\nResults: {results_path}")
            print("Note: 离线确定性评测（Fake Embedding + Fake ChatModel）")

        for k, v in orig.items():
            if v is not None:
                setattr(cfg.settings, k, v)

        # Reset Qdrant client
        import rag_app.langchain_components.vector_store as vs
        if vs._client is not None:
            try: vs._client.close()
            except: pass
            vs._client = None

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


def _validate_citations(citations: list, kb_root: Path) -> list[bool]:
    results = []
    for c in citations:
        src = c.get("source_file", "")
        if not src:
            results.append(False); continue
        fp = kb_root / src
        if not fp.exists():
            results.append(False); continue
        try:
            content = fp.read_text(encoding="utf-8")
            snippet = c.get("snippet", "")[:50].strip()
            results.append(bool(snippet and snippet[:20] in content))
        except Exception:
            results.append(False)
    return results


if __name__ == "__main__":
    run_evaluation()
