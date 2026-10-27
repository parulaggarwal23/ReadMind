"""History-aware AI pull-request review — ReadMind's own research idea applied to ReadMind's CI.

For every changed file the reviewer pulls that file's recent commit history (the same kind of evidence
ReadMind indexes), gives the LLM the diff + history with [commit:<sha10>] ids, asks for a cited review,
and then checks every citation with ReadMind's own verifier (rag.citations.verify_citations).

    python -m devops.ai_pr_review --base origin/main --head HEAD            # print review
    python -m devops.ai_pr_review --base $BASE --head $HEAD --post          # comment on the PR (CI)

Env: LLM_PROVIDER / LLM_MODEL / GEMINI_API_KEY (same as the app). Without a key it falls back to the
offline mock provider so the workflow never fails on forks. For --post: GITHUB_TOKEN, GITHUB_REPOSITORY,
PR_NUMBER.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import requests

MARKER = "<!-- readmind-ai-review -->"
MAX_DIFF_CHARS = 24000
MAX_FILES = 25
HISTORY_PER_FILE = 4

SYSTEM_REVIEW = """You are a senior engineer reviewing a pull request to ReadMind, a FastAPI + React system that
answers developer questions with RAG over repository history (commits, issues, PRs, reviews).
You get the DIFF and, for each changed file, its RECENT HISTORY as evidence with ids like [commit:1a2b3c4d5e].
Write a short Markdown review with these sections:
### Summary            (2-3 sentences: what the PR does)
### Risks              (bullets; tie each risk to earlier history when relevant and cite it, e.g. [commit:1a2b3c4d5e])
### Tests to add       (bullets naming concrete test cases; tests run with LLM_PROVIDER=mock EMBED_MODEL=hash)
### Verdict            (one of: LGTM / Needs changes / Needs discussion, plus one sentence)
Rules: cite ONLY ids that appear in the evidence; never invent commit hashes. Be specific and concise."""


def git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def changed_files(base: str, head: str, cwd: str | None = None) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}", cwd=cwd)
    return [f for f in out.splitlines() if f.strip()][:MAX_FILES]


def file_history(path: str, base: str, cwd: str | None = None, n: int = HISTORY_PER_FILE) -> list[dict]:
    """Recent commits touching `path` on the base branch — the 'repository history' evidence."""
    fmt = "%H%x1f%an%x1f%ad%x1f%s%x1f%b%x1e"
    try:
        out = git("log", f"-n{n}", "--date=short", f"--format={fmt}", base, "--", path, cwd=cwd)
    except subprocess.CalledProcessError:
        return []
    commits = []
    for rec in out.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) < 4 or not parts[0]:
            continue
        sha, author, date, subject = parts[:4]
        body = parts[4].strip() if len(parts) > 4 else ""
        commits.append({"id": f"commit:{sha[:10]}", "sha": sha, "author": author, "date": date,
                        "subject": subject, "body": body[:400], "path": path})
    return commits


def build_evidence(files: list[str], base: str, cwd: str | None = None) -> list[dict]:
    """One evidence item per commit; `paths` lists every changed file that commit touched."""
    by_id: dict[str, dict] = {}
    for f in files:
        for c in file_history(f, base, cwd):
            if c["id"] in by_id:
                by_id[c["id"]]["paths"].append(f)
            else:
                by_id[c["id"]] = {**c, "paths": [f]}
    return list(by_id.values())


def format_prompt(diff: str, evidence: list[dict], title: str = "") -> str:
    hist = "\n\n".join(
        f"[{e['id']}] ({e['date']}, {e['author']}) touched {', '.join(e['paths'])}: {e['subject']}"
        + (f"\n{e['body']}" if e["body"] else "")
        for e in evidence) or "(no earlier history for these files)"
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + f"\n\n… diff truncated ({len(diff)} chars total)"
    return f"PR title: {title}\n\nRECENT HISTORY OF CHANGED FILES:\n\n{hist}\n\nDIFF:\n```diff\n{diff}\n```"


def review(base: str, head: str, title: str = "", cwd: str | None = None) -> dict:
    # Fall back to the offline mock provider when no key is available (e.g. PRs from forks).
    if os.getenv("LLM_PROVIDER", "gemini") == "gemini" and not os.getenv("GEMINI_API_KEY"):
        os.environ["LLM_PROVIDER"] = "mock"
    from config import LLM_MODEL, LLM_PROVIDER
    from rag.citations import verify_citations
    from rag.llm import generate

    files = changed_files(base, head, cwd)
    diff = git("diff", f"{base}...{head}", "--", *files, cwd=cwd) if files else ""
    evidence = build_evidence(files, base, cwd)
    if not files:
        text = "No reviewable file changes."
    elif LLM_PROVIDER == "mock":
        text = offline_review(files, evidence)
    else:
        text = generate(SYSTEM_REVIEW, format_prompt(diff, evidence, title))
    verification = verify_citations(text, [e["id"] for e in evidence])
    return {"text": text, "files": files, "evidence": evidence, "verification": verification,
            "model": f"{LLM_PROVIDER}:{LLM_MODEL}"}


def offline_review(files: list[str], evidence: list[dict]) -> str:
    """Deterministic review used when no LLM key is available: still history-aware and cited."""
    by_file: dict[str, list[dict]] = {}
    for e in evidence:
        for p in e["paths"]:
            by_file.setdefault(p, []).append(e)
    lines = ["### Summary", f"This PR changes {len(files)} file(s). No LLM key was available, so this is the "
             "offline history report instead of a model review.", "", "### Risks"]
    for f in files:
        hist = sorted(by_file.get(f, []), key=lambda e: e["date"], reverse=True)
        if hist:
            last = hist[0]
            lines.append(f"- `{f}` was last changed in \"{last['subject']}\" ({last['date']}) [{last['id']}]; "
                         f"{len(hist)} recent commit(s) touch it.")
        else:
            lines.append(f"- `{f}` is new or has no earlier history on the base branch.")
    lines += ["", "### Tests to add",
              "- Cover the changed functions in `backend/tests/` (run with `LLM_PROVIDER=mock EMBED_MODEL=hash pytest -q`).",
              "", "### Verdict", "Needs discussion — add a `GEMINI_API_KEY` secret for a full AI review."]
    return "\n".join(lines)


def render_comment(result: dict, repo: str = "") -> str:
    v = result["verification"]
    if v["cited"]:
        cite_line = (f"{len(v['valid'])}/{len(v['cited'])} citations verified against git history"
                     + (f" — ⚠ unverified: {', '.join(v['invalid'])}" if v["invalid"] else " ✅"))
    else:
        cite_line = "no history citations"
    links = ""
    if repo and result["evidence"]:
        links = "\n".join(f"- [`{e['id']}`](https://github.com/{repo}/commit/{e['sha']}) {e['subject']}"
                          for e in result["evidence"][:12])
        links = f"\n\n<details><summary>History evidence given to the reviewer ({len(result['evidence'])} commits)</summary>\n\n{links}\n</details>"
    mock_note = ("\n\n> ℹ️ Ran with the offline **mock** model (no `GEMINI_API_KEY` secret available)."
                 if result["model"].startswith("mock") else "")
    return (f"{MARKER}\n## 🤖 ReadMind AI review (history-aware)\n\n{result['text']}\n\n---\n"
            f"<sub>Model `{result['model']}` · {len(result['files'])} files · {cite_line} · "
            f"citations checked with `rag.citations.verify_citations`</sub>{mock_note}{links}")


def post_comment(body: str) -> None:
    """Create or update a single sticky comment on the PR."""
    token, repo, pr = os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"], os.environ["PR_NUMBER"]
    api = f"https://api.github.com/repos/{repo}/issues/{pr}/comments"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    existing = requests.get(api, headers=h, params={"per_page": 100}, timeout=20).json()
    mine = next((c for c in existing if isinstance(c, dict) and MARKER in (c.get("body") or "")), None)
    if mine:
        r = requests.patch(mine["url"], headers=h, json={"body": body}, timeout=20)
    else:
        r = requests.post(api, headers=h, json={"body": body}, timeout=20)
    r.raise_for_status()
    print(f"Posted review comment: {r.json().get('html_url')}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--title", default=os.getenv("PR_TITLE", ""))
    ap.add_argument("--repo-dir", default=None, help="git checkout to review (default: current directory)")
    ap.add_argument("--post", action="store_true", help="post/update the PR comment")
    ap.add_argument("--summary-file", default=os.getenv("GITHUB_STEP_SUMMARY"))
    args = ap.parse_args(argv)

    result = review(args.base, args.head, args.title, args.repo_dir)
    body = render_comment(result, os.getenv("GITHUB_REPOSITORY", ""))
    print(body)
    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as f:
            f.write(body.replace(MARKER, "") + "\n")
    if args.post:
        post_comment(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
