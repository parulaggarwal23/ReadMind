"""Sourcegraph integration: semantic code search + code navigation for the repositories ReadMind indexes.

ReadMind explains WHY code looks the way it does (history RAG). Sourcegraph answers WHERE/WHAT:
cross-repo code search, symbol search, structural search and precise go-to-definition / find-references
(from the SCIP indexes uploaded by .github/workflows/sourcegraph-scip.yml).

Endpoints (mounted in api/main.py):
    GET  /api/sourcegraph/status                    is the Sourcegraph instance reachable?
    POST /api/sourcegraph/search                    {query, repo?, mode} -> file / line / symbol matches
    GET  /api/sourcegraph/links?repo=..&id=..       deep links (blob, history, references) for an evidence id

Settings (.env): SOURCEGRAPH_URL (default http://localhost:7080), SOURCEGRAPH_TOKEN (access token).
Run Sourcegraph locally with:  docker compose -f sourcegraph/docker-compose.sourcegraph.yml up -d
"""
from __future__ import annotations

import re
from typing import Literal, Optional
from urllib.parse import quote

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import SOURCEGRAPH_TOKEN, SOURCEGRAPH_URL

router = APIRouter(prefix="/api/sourcegraph", tags=["sourcegraph"])

Mode = Literal["keyword", "symbol", "structural", "regexp", "commit", "diff"]

SEARCH_GQL = """
query ReadMindSearch($query: String!) {
  search(query: $query, version: V3) {
    results {
      matchCount
      limitHit
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path url }
          lineMatches { preview lineNumber }
          symbols { name kind url }
        }
        ... on CommitSearchResult {
          url
          commit { oid subject author { person { name } date } }
        }
      }
    }
  }
}
"""

VERSION_GQL = "query { site { productVersion } }"


# --------------------------------------------------------------------------- helpers
def sg_repo_name(slug: str) -> str:
    """ReadMind slug 'owner__name' -> Sourcegraph repo name 'github.com/owner/name'."""
    return "github.com/" + slug.replace("__", "/", 1)


def build_query(query: str, slug: Optional[str] = None, mode: Mode = "keyword", count: int = 30) -> str:
    """Turn a ReadMind search request into Sourcegraph query syntax."""
    parts = []
    if slug:
        parts.append(f"repo:^{re.escape(sg_repo_name(slug))}$")
    if mode == "symbol":
        parts.append("type:symbol")
    elif mode == "structural":
        parts.append("patternType:structural")
    elif mode == "regexp":
        parts.append("patternType:regexp")
    elif mode == "commit":
        parts.append("type:commit")
    elif mode == "diff":
        parts.append("type:diff")
    else:
        parts.append("patternType:standard")
    parts.append(f"count:{count}")
    parts.append(query.strip())
    return " ".join(parts)


def _graphql(gql: str, variables: dict | None = None, timeout: int = 20) -> dict:
    headers = {"Content-Type": "application/json"}
    if SOURCEGRAPH_TOKEN:
        headers["Authorization"] = f"token {SOURCEGRAPH_TOKEN}"
    r = requests.post(f"{SOURCEGRAPH_URL.rstrip('/')}/.api/graphql", json={"query": gql, "variables": variables or {}},
                      headers=headers, timeout=timeout)
    if r.status_code in (401, 403):
        raise HTTPException(502, "Sourcegraph rejected the request: set SOURCEGRAPH_TOKEN in .env")
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise HTTPException(502, "Sourcegraph error: " + "; ".join(e.get("message", "") for e in body["errors"]))
    return body["data"]


def _abs(url: str) -> str:
    return url if url.startswith("http") else f"{SOURCEGRAPH_URL.rstrip('/')}{url}"


def normalize_results(data: dict) -> dict:
    res = (data.get("search") or {}).get("results") or {}
    items = []
    for m in res.get("results", []):
        kind = m.get("__typename")
        if kind == "FileMatch":
            items.append({
                "kind": "file",
                "repo": m["repository"]["name"],
                "path": m["file"]["path"],
                "url": _abs(m["file"]["url"]),
                "lines": [{"line": lm["lineNumber"] + 1, "preview": lm["preview"]}
                          for lm in (m.get("lineMatches") or [])][:5],
                "symbols": [{"name": s["name"], "kind": s["kind"], "url": _abs(s["url"])}
                            for s in (m.get("symbols") or [])][:10],
            })
        elif kind == "CommitSearchResult":
            c = m["commit"]
            items.append({
                "kind": "commit",
                "url": _abs(m["url"]),
                "sha": c["oid"],
                "subject": c["subject"],
                "author": ((c.get("author") or {}).get("person") or {}).get("name", ""),
                "date": (c.get("author") or {}).get("date", ""),
            })
    return {"match_count": res.get("matchCount", 0), "limit_hit": res.get("limitHit", False), "results": items}


def evidence_links(slug: str, doc: dict) -> dict:
    """Deep links into Sourcegraph for one ReadMind evidence document."""
    base = f"{SOURCEGRAPH_URL.rstrip('/')}/{sg_repo_name(slug)}"
    t, links = doc.get("type"), {}
    if t == "code":
        path, start, end = doc.get("path", ""), doc.get("start", 1), doc.get("end", 1)
        links["blob"] = f"{base}/-/blob/{quote(path)}?L{start}-{end}"
        links["references"] = f"{base}/-/blob/{quote(path)}?L{start}#tab=references"
        links["history"] = f"{base}/-/commits/{quote(path)}"
        symbol = (doc.get("symbol") or "").split()[-1] if doc.get("symbol") else ""
        if symbol and symbol != "<module>":
            q = build_query(symbol, slug, "symbol")
            links["symbol_search"] = f"{SOURCEGRAPH_URL.rstrip('/')}/search?q={quote(q)}"
    elif t == "doc":
        links["blob"] = f"{base}/-/blob/{quote(doc.get('path', ''))}"
    elif t == "commit":
        m = re.search(r"/commit/([0-9a-f]{7,40})", doc.get("url", ""))
        sha = m.group(1) if m else doc["id"].split(":", 1)[1]
        links["commit"] = f"{base}/-/commit/{sha}"
    elif t in {"pr", "issue", "review"}:
        files = doc.get("files") or []
        if files:
            links["history"] = f"{base}/-/commits/{quote(files[0])}"
    return links


# --------------------------------------------------------------------------- routes
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    repo: Optional[str] = None  # ReadMind slug, e.g. infiniflow__ragflow; omit to search every repo
    mode: Mode = "keyword"
    count: int = Field(30, ge=1, le=200)


@router.get("/status")
def status():
    try:
        data = _graphql(VERSION_GQL, timeout=5)
        return {"configured": True, "reachable": True, "url": SOURCEGRAPH_URL,
                "version": data["site"]["productVersion"], "token": bool(SOURCEGRAPH_TOKEN)}
    except HTTPException as e:
        return {"configured": True, "reachable": False, "url": SOURCEGRAPH_URL, "error": e.detail,
                "token": bool(SOURCEGRAPH_TOKEN)}
    except Exception as e:  # connection refused, timeout, ...
        return {"configured": bool(SOURCEGRAPH_URL), "reachable": False, "url": SOURCEGRAPH_URL,
                "error": f"{type(e).__name__}: {e}", "token": bool(SOURCEGRAPH_TOKEN)}


@router.post("/search")
def search(req: SearchRequest):
    q = build_query(req.query, req.repo, req.mode, req.count)
    try:
        data = _graphql(SEARCH_GQL, {"query": q})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Sourcegraph is not reachable at {SOURCEGRAPH_URL}: {type(e).__name__}")
    out = normalize_results(data)
    out["query"] = q
    out["web_url"] = f"{SOURCEGRAPH_URL.rstrip('/')}/search?q={quote(q)}"
    return out


@router.get("/links")
def links(repo: str, id: str = Query(..., min_length=3)):
    from rag.retriever import get_index
    try:
        idx = get_index(repo)
    except FileNotFoundError:
        raise HTTPException(404, f"Repository '{repo}' is not indexed")
    doc_id = idx.resolve_id(id)
    if not doc_id:
        raise HTTPException(404, f"Evidence '{id}' not found")
    return {"id": doc_id, "links": evidence_links(repo, idx.docs[doc_id])}
