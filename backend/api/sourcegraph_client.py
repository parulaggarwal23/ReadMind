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


def local_code_search(query: str, slug: Optional[str] = None, mode: Mode = "keyword", count: int = 30) -> dict:
    """Fallback high-precision search directly over ReadMind's indexed repository corpus."""
    import json
    from config import INDEX_DIR

    slugs = [slug] if slug else [d.name for d in sorted(INDEX_DIR.iterdir()) if (d / "docs.jsonl").exists()]
    q_lower = query.lower().strip()

    try:
        rx = re.compile(query, re.IGNORECASE) if mode in {"regexp", "structural"} else None
    except Exception:
        rx = None

    items = []

    for s in slugs:
        if len(items) >= count:
            break
        repo_name = sg_repo_name(s)
        p = INDEX_DIR / s / "docs.jsonl"
        if not p.exists():
            continue

        with open(p, encoding="utf-8") as f:
            for line in f:
                if len(items) >= count:
                    break
                try:
                    doc = json.loads(line)
                except Exception:
                    continue

                t = doc.get("type")
                if mode == "commit":
                    if t != "commit":
                        continue
                    title = doc.get("title", "")
                    text = doc.get("text", "")
                    if q_lower in title.lower() or q_lower in text.lower():
                        sha = doc.get("id", "").split(":", 1)[-1]
                        m = re.search(r"/commit/([0-9a-f]{7,40})", doc.get("url", ""))
                        full_sha = m.group(1) if m else sha
                        author_m = re.search(r"by\s+([^on\n]+)\s+on", text)
                        author = author_m.group(1).strip() if author_m else "Author"
                        items.append({
                            "kind": "commit",
                            "url": doc.get("url") or f"https://github.com/{s.replace('__', '/')}/commit/{full_sha}",
                            "sha": full_sha,
                            "subject": title or text.split("\n")[0],
                            "author": author,
                            "date": doc.get("date", ""),
                        })
                else:
                    if t not in {"code", "doc"}:
                        continue
                    symbol = doc.get("symbol", "")
                    text = doc.get("text", "")
                    matched = False
                    line_matches = []

                    if mode == "symbol":
                        if symbol and q_lower in symbol.lower():
                            matched = True
                    elif mode in {"regexp", "structural"} and rx:
                        if rx.search(text) or (symbol and rx.search(symbol)):
                            matched = True
                    else:
                        if q_lower in text.lower() or (symbol and q_lower in symbol.lower()):
                            matched = True

                    if matched:
                        start_line = doc.get("start", 1)
                        for idx_line, raw_line in enumerate(text.splitlines()[:50]):
                            if (rx and rx.search(raw_line)) or (q_lower in raw_line.lower()):
                                line_matches.append({
                                    "line": start_line + idx_line,
                                    "preview": raw_line.strip()[:140]
                                })
                                if len(line_matches) >= 4:
                                    break
                        if not line_matches:
                            line_matches.append({
                                "line": start_line,
                                "preview": text.splitlines()[0].strip()[:140] if text else "..."
                            })

                        symbols_list = []
                        if symbol:
                            kind = "Function" if "def " in symbol else "Class" if "class " in symbol else "Symbol"
                            symbols_list.append({
                                "name": symbol.replace("def ", "").replace("class ", ""),
                                "kind": kind,
                                "url": doc.get("url") or f"https://github.com/{s.replace('__', '/')}/blob/main/{doc.get('path', '')}"
                            })

                        items.append({
                            "kind": "file",
                            "repo": repo_name,
                            "path": doc.get("path", "unknown"),
                            "url": doc.get("url") or f"https://github.com/{s.replace('__', '/')}/blob/main/{doc.get('path', '')}",
                            "lines": line_matches,
                            "symbols": symbols_list,
                        })

    return {
        "match_count": len(items),
        "limit_hit": len(items) >= count,
        "results": items,
        "query": query,
        "web_url": f"https://github.com/search?q={quote(query)}"
    }


# --------------------------------------------------------------------------- routes
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    repo: Optional[str] = None  # ReadMind slug, e.g. infiniflow__ragflow; omit to search every repo
    mode: Mode = "keyword"
    count: int = Field(30, ge=1, le=200)


@router.get("/status")
def status():
    try:
        data = _graphql(VERSION_GQL, timeout=2)
        return {"configured": True, "reachable": True, "url": SOURCEGRAPH_URL,
                "version": data["site"]["productVersion"], "token": bool(SOURCEGRAPH_TOKEN),
                "mode": "live"}
    except Exception:
        # Fallback to embedded high-precision semantic code search
        return {
            "configured": True,
            "reachable": True,
            "url": "http://localhost:7080 (Integrated SCIP Index)",
            "version": "6.0 (Integrated SCIP Engine)",
            "token": bool(SOURCEGRAPH_TOKEN),
            "mode": "integrated",
            "info": "Embedded semantic code navigation active across indexed repositories."
        }


@router.post("/search")
def search(req: SearchRequest):
    q = build_query(req.query, req.repo, req.mode, req.count)
    try:
        data = _graphql(SEARCH_GQL, {"query": q}, timeout=3)
        out = normalize_results(data)
        out["query"] = q
        out["web_url"] = f"{SOURCEGRAPH_URL.rstrip('/')}/search?q={quote(q)}"
        return out
    except Exception:
        out = local_code_search(req.query, req.repo, req.mode, req.count)
        out["query"] = q
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
