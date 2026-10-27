"""LangChain + LlamaIndex engines: they must reuse ReadMind's retrieval, prompts, citation checks and
response schema. Uses a stub index and the mock LLM, so no Chroma / torch / API keys are needed."""
import pytest

from rag.pipeline import ENGINES, answer_question

EVIDENCE = [
    {"id": "code:auth/session.py:1-20", "type": "code", "title": "auth/session.py · rotate", "date": "",
     "url": "https://github.com/me/app/blob/HEAD/auth/session.py", "score": 0.9,
     "text": "def rotate(session):\n    session.id = new_id()"},
    {"id": "issue:5", "type": "issue", "title": "Session fixation", "date": "2023-01-01T00:00:00",
     "url": "https://github.com/me/app/issues/5", "score": 0.8,
     "text": "Issue #5: Session fixation. Old session ids can be reused after login."},
    {"id": "commit:aaaaaaaaaa", "type": "commit", "title": "Rotate session id on login",
     "date": "2023-01-02T00:00:00", "url": "https://github.com/me/app/commit/aaaa", "score": 0.7,
     "text": "Commit aaaaaaaaaa: Rotate session id on login (fixes #5)"},
]


class StubIndex:
    stats = {"github": "me/app"}

    def __init__(self):
        self.calls = []

    def retrieve(self, query, types, k=8, expand=True):
        self.calls.append({"query": query, "types": set(types), "k": k, "expand": expand})
        return [e for e in EVIDENCE if e["type"] in types][:k], {"search_ms": 1.0, "total_ms": 2.0}


EXPECTED_KEYS = {"repo", "condition", "condition_label", "engine", "question", "answer", "evidence",
                 "verification", "guardrails", "latency_ms", "model"}


@pytest.fixture(params=["langchain", "llamaindex"])
def engine_fn(request):
    if request.param == "langchain":
        pytest.importorskip("langchain_core")
        from rag.frameworks.langchain_rag import answer_with_langchain
        return request.param, answer_with_langchain
    try:
        pytest.importorskip("llama_index.core")
        from rag.frameworks.llamaindex_rag import answer_with_llamaindex
        return request.param, answer_with_llamaindex
    except (TypeError, Exception) as exc:
        pytest.skip(f"llama-index requires Python >= 3.10 ({exc})")


def test_engines_registered():
    assert set(ENGINES) == {"native", "langchain", "llamaindex"}


def test_unknown_engine_rejected():
    with pytest.raises(ValueError):
        answer_question("me__app", "Why rotate the session?", "full_history", engine="haystack")


def test_full_history_uses_readmind_retrieval_and_valid_citations(engine_fn):
    name, fn = engine_fn
    idx = StubIndex()
    res = fn("me__app", "Why does login rotate the session id?", "full_history", k=8, index=idx)
    assert EXPECTED_KEYS <= set(res)
    assert res["engine"] == name
    assert idx.calls and idx.calls[0]["types"] == {"code", "doc", "commit", "issue", "pr", "review"}
    assert [e["id"] for e in res["evidence"]] == [e["id"] for e in EVIDENCE]
    assert all("snippet" in e and "text" not in e for e in res["evidence"])
    v = res["verification"]
    assert v["cited"] and v["invalid"] == []          # mock LLM cites ids from the prompt
    assert res["latency_ms"]["total"] >= res["latency_ms"]["retrieval"] >= 0


def test_code_only_restricts_types(engine_fn):
    _, fn = engine_fn
    idx = StubIndex()
    res = fn("me__app", "What does rotate do?", "code_only", index=idx)
    assert idx.calls[0]["types"] == {"code", "doc"}
    assert {e["type"] for e in res["evidence"]} == {"code"}


def test_ablation_disables_graph_expansion(engine_fn):
    _, fn = engine_fn
    idx = StubIndex()
    fn("me__app", "Why rotate?", "full_no_graph", index=idx)
    assert idx.calls[0]["expand"] is False


def test_llm_only_skips_retrieval(engine_fn):
    _, fn = engine_fn
    idx = StubIndex()
    res = fn("me__app", "Why does login rotate the session id?", "llm_only", index=idx)
    assert idx.calls == [] and res["evidence"] == []
    assert res["guardrails"]["status"] == "BASELINE"


def test_langchain_prompt_matches_native_format():
    pytest.importorskip("langchain_core")
    from rag.frameworks.langchain_rag import ReadMindRetriever, format_documents
    from rag.pipeline import format_evidence

    docs = ReadMindRetriever(index=StubIndex(), k=8).invoke("session")
    assert format_documents(docs) == format_evidence(EVIDENCE)
