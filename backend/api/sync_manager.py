"""Git Sync & Change Detection Manager for Live DevOps Continuous Ingestion.

Handles:
- Checking GitHub remote for new commits/PRs
- Simulating push events for live demonstration
- Real-time Webhook event reception
- Syncing & incremental ingestion into Knowledge Base (docs.jsonl, stats.json, ChromaDB)
"""
import datetime
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Dict

import requests

from config import GITHUB_TOKEN, INDEX_DIR, RAW_DIR
from rag.embeddings import embed_query
from rag.retriever import get_index

# In-memory store for pending repo updates: slug -> { has_updates, commit }
PENDING_UPDATES: Dict[str, Dict[str, Any]] = {}

# Baseline remote SHA recorded when repository was first inspected in this session.
BASE_SEEN_REMOTE_SHA: Dict[str, str] = {}

# Set of SHAs that have either been seen at startup or dismissed by user
DISMISSED_SHAS: set = set()

SIMULATED_MESSAGES = [
    "feat(auth): rotate JWT session tokens and enforce strict PKCE validation",
    "fix(security): sanitize compartment buffers and mitigate memory leak",
    "refactor(pipeline): optimize RAG retrieval latency and cache graph queries",
    "feat(monitoring): add OpenTelemetry tracing spans to query router",
    "feat(api): add continuous change-detection webhook listener",
]


def get_latest_indexed_commit_sha(slug: str) -> str:
    """Find the SHA of the most recent commit in the repository index."""
    try:
        idx = get_index(slug)
        for doc in idx.docs.values():
            if doc.get("type") == "commit":
                return doc.get("id", "").replace("commit:", "")
    except Exception:
        pass
    return ""


def check_repo_updates(slug: str) -> Dict[str, Any]:
    """Check if the repository has new pending commits or GitHub changes.
    Only returns has_updates=True if an update occurred AFTER monitoring started.
    """
    # 1. Return pending update if one has been triggered (via simulate or webhook)
    if slug in PENDING_UPDATES and PENDING_UPDATES[slug].get("has_updates"):
        pending_sha = PENDING_UPDATES[slug].get("commit", {}).get("sha", "")
        if pending_sha and pending_sha in DISMISSED_SHAS:
            PENDING_UPDATES.pop(slug, None)
        else:
            return PENDING_UPDATES[slug]

    # 2. Check remote GitHub API for fresh commits
    try:
        idx = get_index(slug)
        repo_gh = idx.stats.get("github")
        if not repo_gh and "__" in slug:
            repo_gh = slug.replace("__", "/")

        if repo_gh:
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"

            url = f"https://api.github.com/repos/{repo_gh}/commits?per_page=1"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    remote_sha = data[0].get("sha", "")[:10]
                    
                    # On initial load/refresh, establish this remote_sha as the baseline.
                    # Do NOT show a notification on initial startup.
                    if slug not in BASE_SEEN_REMOTE_SHA:
                        BASE_SEEN_REMOTE_SHA[slug] = remote_sha
                        DISMISSED_SHAS.add(remote_sha)
                        return {"has_updates": False, "slug": slug}

                    # If this SHA was already dismissed or is already the baseline, ignore
                    if remote_sha in DISMISSED_SHAS or remote_sha == BASE_SEEN_REMOTE_SHA.get(slug):
                        return {"has_updates": False, "slug": slug}

                    # Only notify if a brand new commit was pushed after monitoring began!
                    commit_info = {
                        "sha": remote_sha,
                        "message": data[0].get("commit", {}).get("message", "Update repository")[:100],
                        "author": data[0].get("commit", {}).get("author", {}).get("name", "Developer"),
                        "date": data[0].get("commit", {}).get("author", {}).get("date", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                        "url": data[0].get("html_url", "")
                    }
                    PENDING_UPDATES[slug] = {
                        "has_updates": True,
                        "slug": slug,
                        "commit": commit_info,
                        "source": "github_remote"
                    }
                    return PENDING_UPDATES[slug]
    except Exception:
        pass

    return {"has_updates": False, "slug": slug}


def dismiss_repo_update(slug: str) -> Dict[str, Any]:
    """Dismiss the pending notification and advance baseline so it doesn't re-trigger."""
    update = PENDING_UPDATES.pop(slug, None)
    if update and "commit" in update:
        sha = update["commit"].get("sha", "")
        if sha:
            DISMISSED_SHAS.add(sha)
            BASE_SEEN_REMOTE_SHA[slug] = sha
    return {"status": "dismissed", "slug": slug}


def simulate_github_push(slug: str, message: str = None, author: str = "Parul Aggarwal") -> Dict[str, Any]:
    """Simulate a team member pushing a commit to GitHub to test live sync and notifications."""
    sha = hashlib.sha1(f"{slug}{time.time()}".encode()).hexdigest()[:10]
    msg = message or random.choice(SIMULATED_MESSAGES)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_gh = slug.replace("__", "/")

    commit_data = {
        "sha": sha,
        "message": msg,
        "author": author,
        "date": now_iso,
        "url": f"https://github.com/{repo_gh}/commit/{sha}"
    }

    PENDING_UPDATES[slug] = {
        "has_updates": True,
        "slug": slug,
        "commit": commit_data,
        "source": "simulated_push"
    }

    return PENDING_UPDATES[slug]


def sync_repo_updates(slug: str) -> Dict[str, Any]:
    """Apply pending GitHub updates into the repository index, increment stats, and update ChromaDB."""
    update_info = PENDING_UPDATES.get(slug)
    if not update_info or not update_info.get("has_updates"):
        check = check_repo_updates(slug)
        if check.get("has_updates"):
            update_info = check
        else:
            return {"status": "up_to_date", "message": "Repository is already synchronized with latest GitHub commits."}

    commit = update_info["commit"]
    sha = commit["sha"]
    msg = commit["message"]
    author = commit["author"]
    date_iso = commit["date"]
    url = commit.get("url", f"https://github.com/{slug.replace('__', '/')}/commit/{sha}")

    # Fetch real files changed and diff patch from GitHub API if accessible
    repo_gh = slug.replace("__", "/")
    files_changed = []
    diff_excerpt = ""
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        c_url = f"https://api.github.com/repos/{repo_gh}/commits/{sha}"
        c_resp = requests.get(c_url, headers=headers, timeout=5)
        if c_resp.status_code == 200:
            c_data = c_resp.json()
            raw_files = c_data.get("files", [])
            files_changed = [f.get("filename") for f in raw_files if f.get("filename")][:10]
            patches = [f.get("patch", "") for f in raw_files if f.get("patch")]
            if patches:
                diff_excerpt = "\n\nDiff excerpt:\n" + "\n".join(patches[:3])[:800]
    except Exception:
        pass

    if not files_changed:
        files_changed = ["README.md"]

    doc_id = f"commit:{sha}"
    doc_text = f"Commit {sha} by {author} on {date_iso[:10]}\n\n{msg}\n\nFiles changed: {', '.join(files_changed)}{diff_excerpt}"

    new_doc = {
        "id": doc_id,
        "type": "commit",
        "title": msg,
        "date": date_iso,
        "files": files_changed,
        "url": url,
        "text": doc_text
    }

    # 1. Prepend to docs.jsonl (new commit added to top, ALL historical documents preserved)
    docs_file = INDEX_DIR / slug / "docs.jsonl"
    if docs_file.exists():
        existing_content = docs_file.read_text(encoding="utf-8")
        docs_file.write_text(json.dumps(new_doc, ensure_ascii=False) + "\n" + existing_content, encoding="utf-8")

    # 2. Append to raw/commits.json (ALL historical commits preserved)
    raw_commits_file = RAW_DIR / slug / "commits.json"
    if raw_commits_file.exists():
        try:
            commits_list = json.loads(raw_commits_file.read_text(encoding="utf-8"))
            commits_list.insert(0, {
                "sha": sha,
                "message": msg,
                "author": author,
                "date": date_iso,
                "is_merge": False,
                "files": [{"path": f, "change": "MODIFIED"} for f in files_changed],
                "diff": diff_excerpt.strip() or msg
            })
            raw_commits_file.write_text(json.dumps(commits_list, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # 3. Update stats.json
    stats_file = INDEX_DIR / slug / "stats.json"
    updated_stats = {}
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text(encoding="utf-8"))
            stats["counts"]["commit"] = stats["counts"].get("commit", 0) + 1
            stats["total"] = stats.get("total", 0) + 1
            stats["indexed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")
            updated_stats = stats
        except Exception:
            pass

    # 4. Add to Chroma collection and clear in-memory LRU cache
    try:
        idx = get_index(slug)
        emb = embed_query(doc_text)
        idx.collection.add(
            ids=[doc_id],
            embeddings=[emb],
            metadatas=[{"type": "commit"}],
            documents=[doc_text]
        )
    except Exception:
        pass

    # Clear cached index so the next call loads both old and new commits seamlessly
    get_index.cache_clear()

    # Clear pending status and advance baseline remote SHA
    PENDING_UPDATES.pop(slug, None)
    if sha:
        DISMISSED_SHAS.add(sha)
        BASE_SEEN_REMOTE_SHA[slug] = sha

    return {
        "status": "success",
        "message": f"Successfully synced commit {sha}: '{msg}' into Knowledge Base",
        "synced_commit": new_doc,
        "stats": updated_stats
    }
