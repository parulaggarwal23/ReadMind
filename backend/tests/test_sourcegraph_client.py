"""Tests for api/sourcegraph_client.py (pure helpers only — no Sourcegraph instance needed).

Seed tests (hand-written); Qodo Cover appends AI-generated tests (scripts/generate_tests.sh)."""
from api.sourcegraph_client import build_query, evidence_links, normalize_results, sg_repo_name


def test_repo_name_from_slug():
    assert sg_repo_name("infiniflow__ragflow") == "github.com/infiniflow/ragflow"


def test_build_query_scopes_repo_and_mode():
    q = build_query("RepoIndex", "parulaggarwal23__ReadMind", "symbol", count=10)
    assert q.startswith(r"repo:^github\.com/parulaggarwal23/ReadMind$")
    assert "type:symbol" in q and "count:10" in q and q.endswith("RepoIndex")


def test_code_evidence_links():
    doc = {"id": "code:rag/retriever.py:20-80", "type": "code", "path": "rag/retriever.py",
           "start": 20, "end": 80, "symbol": "class RepoIndex"}
    links = evidence_links("me__app", doc)
    assert links["blob"].endswith("/github.com/me/app/-/blob/rag/retriever.py?L20-80")
    assert "#tab=references" in links["references"]
    assert "RepoIndex" in links["symbol_search"]


def test_commit_evidence_links_use_full_sha():
    doc = {"id": "commit:abcdef1234", "type": "commit", "url": "https://github.com/me/app/commit/" + "a" * 40}
    assert evidence_links("me__app", doc)["commit"].endswith("/-/commit/" + "a" * 40)


def test_normalize_file_match():
    data = {"search": {"results": {"matchCount": 1, "limitHit": False, "results": [{
        "__typename": "FileMatch", "repository": {"name": "github.com/me/app"},
        "file": {"path": "a.py", "url": "/github.com/me/app/-/blob/a.py"},
        "lineMatches": [{"preview": "def f():", "lineNumber": 0}], "symbols": []}]}}}
    out = normalize_results(data)
    assert out["match_count"] == 1
    assert out["results"][0]["lines"][0]["line"] == 1          # Sourcegraph lines are 0-based
    assert out["results"][0]["url"].startswith("http")
