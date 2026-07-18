from rag_app.api.public import _clean_public_answer


def test_clean_public_answer_removes_inline_source_markers():
    answer = "我是钟伟达。[来源: 个人网站常见问答, 你是谁？]"
    assert _clean_public_answer(answer) == "我是钟伟达。"


def test_clean_public_answer_preserves_normal_content():
    answer = "我目前关注 AI 应用交付与 RAG。"
    assert _clean_public_answer(answer) == answer
