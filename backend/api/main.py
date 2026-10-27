import json
import shutil
import subprocess
import sys
from typing import Literal
from pathlib import Path

import requests
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import (
    BASE_DIR,
    CORS_ORIGINS,
    EVAL_DIR,
    GITHUB_TOKEN,
    INDEX_DIR,
    LLM_MODEL,
    LLM_PROVIDER,
    RAW_DIR,
    REPOS_FILE,
)
from rag.pipeline import CONDITIONS, ENGINES, answer_question
from rag.retriever import get_index, list_indexed
from api.sync_manager import check_repo_updates, dismiss_repo_update, simulate_github_push, sync_repo_updates
from api.k8s_manager import get_cluster_status, simulate_traffic_spike, reset_traffic, get_k8s_manifests
from api.sourcegraph_client import router as sourcegraph_router

app = FastAPI(title="ReadMind", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(sourcegraph_router)

Condition = Literal["llm_only", "code_only", "full_history"]
Engine = Literal["native", "langchain", "llamaindex"]


class AskRequest(BaseModel):
    repo: str
    question: str = Field(min_length=3, max_length=2000)
    condition: Condition = "full_history"
    top_k: int = Field(8, ge=1, le=20)
    engine: Engine = "native"  # native | langchain | llamaindex (same retrieval, prompts and LLM)


class CompareRequest(BaseModel):
    repo: str
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(8, ge=1, le=20)
    engine: Engine = "native"


def _index(slug):
    try:
        return get_index(slug)
    except FileNotFoundError:
        raise HTTPException(404, f"Repository '{slug}' is not indexed. Run ingestion first.")


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": LLM_PROVIDER, "model": LLM_MODEL}


@app.get("/api/repos")
def repos():
    return list_indexed()


@app.get("/api/conditions")
def conditions():
    return [{"id": k, "label": v["label"]} for k, v in CONDITIONS.items()]


@app.get("/api/engines")
def engines():
    """RAG engines: ReadMind's native pipeline, or the same retrieval run through LangChain / LlamaIndex."""
    out = []
    for k, label in ENGINES.items():
        available = True
        if k == "langchain":
            available = _importable("langchain_core")
        elif k == "llamaindex":
            available = _importable("llama_index.core")
        out.append({"id": k, "label": label, "available": available})
    return out


def _importable(module):
    import importlib.util
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


@app.post("/api/ask")
def ask(req: AskRequest):
    _index(req.repo)
    try:
        return answer_question(req.repo, req.question, req.condition, req.top_k, engine=req.engine)
    except Exception as e:  # surface LLM/provider errors to the UI
        raise HTTPException(502, f"{type(e).__name__}: {e}")

@app.get("/api/repos/verify-github")
def verify_github_repo(repo: str = Query(...)):
    """Check if GitHub repository exists and is accessible using backend GITHUB_TOKEN."""
    owner_name = repo.strip().strip("/")
    if "github.com/" in owner_name:
        owner_name = owner_name.split("github.com/")[-1].strip("/")
    if owner_name.endswith(".git"):
        owner_name = owner_name[:-4]
    
    parts = [p for p in owner_name.split("/") if p]
    if len(parts) < 2:
        return {"valid": False, "error": "Invalid format. Expected owner/repo (e.g. facebook/react)"}
    
    target = f"{parts[0]}/{parts[1]}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        
    try:
        r = requests.get(f"https://api.github.com/repos/{target}", headers=headers, timeout=10)
        if r.status_code == 404:
            return {"valid": False, "error": f"Repository '{target}' was not found on GitHub."}
        if r.status_code == 200:
            data = r.json()
            return {
                "valid": True,
                "repo": target,
                "slug": target.replace("/", "__"),
                "description": data.get("description", ""),
                "stars": data.get("stargazers_count", 0),
                "is_private": data.get("private", False)
            }
        return {"valid": True, "repo": target, "slug": target.replace("/", "__")}
    except Exception as e:
        # Fallback: git ls-remote
        try:
            res = subprocess.run(["git", "ls-remote", f"https://github.com/{target}.git"], capture_output=True, timeout=8)
            if res.returncode == 0:
                return {"valid": True, "repo": target, "slug": target.replace("/", "__")}
        except Exception:
            pass
        return {"valid": False, "error": str(e)}


@app.post("/api/ingest")
def run_ingest(req: dict):
    repo = req.get("repo")
    if not repo:
        raise HTTPException(400, "repo is required")
        
    slug = repo.replace("/", "__")
    
    # 1. Update repos.yaml cleanly
    if REPOS_FILE.exists():
        cfg = yaml.safe_load(REPOS_FILE.read_text(encoding="utf-8")) or {}
        repo_entries = cfg.get("repos", [])
        if not any(r.get("github") == repo for r in repo_entries if isinstance(r, dict)):
            repo_entries.append({"github": repo})
            cfg["repos"] = repo_entries
            REPOS_FILE.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
            
    # 2. Run ingestion synchronously with sys.executable and BASE_DIR cwd
    try:
        subprocess.run(
            [sys.executable, "-m", "ingestion.run_ingestion", "--repo", slug],
            cwd=str(BASE_DIR),
            check=True
        )
        get_index.cache_clear()
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Ingestion failed: {e}")
        
    return {"status": "success", "slug": slug}


@app.delete("/api/repos/{slug}")
def delete_repo(slug: str):
    repo = slug.replace("__", "/")
    
    # 1. Remove from repos.yaml
    if REPOS_FILE.exists():
        cfg = yaml.safe_load(REPOS_FILE.read_text(encoding="utf-8")) or {}
        repo_entries = cfg.get("repos", [])
        cfg["repos"] = [r for r in repo_entries if (r.get("github") if isinstance(r, dict) else r) != repo]
        REPOS_FILE.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
        
    # 2. Delete index and raw data folders
    shutil.rmtree(INDEX_DIR / slug, ignore_errors=True)
    shutil.rmtree(RAW_DIR / slug, ignore_errors=True)
    get_index.cache_clear()
    
    return {"status": "deleted"}


@app.get("/api/repos/{slug}/check-updates")
def check_updates(slug: str):
    """Poll or check if repository has new commits / PRs on GitHub."""
    return check_repo_updates(slug)


@app.post("/api/repos/{slug}/dismiss-update")
def dismiss_update(slug: str):
    """Dismiss pending update notification for this repository."""
    return dismiss_repo_update(slug)


@app.post("/api/repos/{slug}/simulate-push")
def simulate_push(slug: str, req: dict = None):
    """Simulate a team member pushing new code to GitHub for live notification demonstration."""
    message = req.get("message") if req else None
    author = req.get("author", "Parul Aggarwal") if req else "Parul Aggarwal"
    return simulate_github_push(slug, message=message, author=author)


@app.post("/api/repos/{slug}/sync")
def sync_repo(slug: str):
    """Synchronize latest changes into the Knowledge Base, update stats, and re-index."""
    return sync_repo_updates(slug)


@app.post("/api/webhook/github")
def github_webhook(payload: dict):
    """GitHub Push / PR Webhook receiver for real-time continuous ingestion."""
    repo_info = payload.get("repository", {})
    repo_full = repo_info.get("full_name", "")
    if repo_full:
        slug = repo_full.replace("/", "__")
        head_commit = payload.get("head_commit", {})
        simulate_github_push(
            slug=slug,
            message=head_commit.get("message", "GitHub Push Event"),
            author=head_commit.get("author", {}).get("name", "GitHub Webhook")
        )
    return {"status": "received"}


@app.get("/api/k8s/status")
def k8s_status():
    """Return live Kubernetes cluster topology, microservices, and HPA auto-scaler state."""
    return get_cluster_status()


@app.post("/api/k8s/simulate-load")
def k8s_simulate_load():
    """Simulate high query traffic spike that triggers HPA auto-scaling."""
    return simulate_traffic_spike()


@app.post("/api/k8s/reset-load")
def k8s_reset_load():
    """Reset cluster traffic back to baseline."""
    return reset_traffic()


@app.get("/api/k8s/manifests")
def k8s_manifests():
    """Return raw Kubernetes declarative YAML manifests."""
    return get_k8s_manifests()


@app.get("/api/repos/{slug}/sample-chunks")
def sample_chunks(slug: str, skip: int = 0, limit: int = 10, type: str = None):
    idx = _index(slug)
    matching_ids = idx.get_typed_ids(type)
    total_matching = len(matching_ids)
    items = [idx.docs[i] for i in matching_ids[skip : skip + limit]]
    return {
        "items": items,
        "total": total_matching,
        "skip": skip,
        "limit": limit
    }


@app.get("/api/repos/{slug}/sample-embeddings")
def sample_embeddings(slug: str, skip: int = 0, limit: int = 10):
    idx = _index(slug)
    total_count = idx.collection.count()
    res = idx.collection.get(limit=limit, offset=skip, include=["embeddings", "metadatas"])
    samples = []
    if res and res.get("embeddings") is not None:
        for i in range(len(res["ids"])):
            emb = res["embeddings"][i]
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            truncated_emb = emb[:10] + [f"... ({len(emb) - 10} more dimensions omitted)"]
            samples.append({
                "id": res["ids"][i],
                "type": res["metadatas"][i]["type"] if res.get("metadatas") else "unknown",
                "embedding": truncated_emb
            })
    return {
        "items": samples,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }

@app.post("/api/compare")
def compare(req: CompareRequest):
    _index(req.repo)
    results = []
    for cond in CONDITIONS:  # sequential so latency numbers aren't distorted
        try:
            results.append(answer_question(req.repo, req.question, cond, req.top_k, engine=req.engine))
        except Exception as e:
            results.append({"condition": cond, "condition_label": CONDITIONS[cond]["label"],
                            "error": f"{type(e).__name__}: {e}"})
    return results


@app.get("/api/evidence")
def evidence(repo: str, id: str = Query(..., min_length=3)):
    idx = _index(repo)
    doc_id = idx.resolve_id(id)
    if not doc_id:
        raise HTTPException(404, f"Evidence '{id}' not found")
    d = idx.docs[doc_id]
    linked = [{"id": n, "type": idx.docs[n]["type"], "title": idx.docs[n].get("title", ""),
               "date": idx.docs[n].get("date", "")} for n in idx.neighbours(doc_id)]
    return {"doc": d, "linked": linked}


def _read_json(name):
    p = EVAL_DIR / name
    if not p.exists():
        raise HTTPException(404, f"{name} not found. Run the evaluation first (see README).")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/eval/summary")
def eval_summary():
    summary = _read_json("summary.json")
    
    # Map friend's custom keys to standard UI keys if needed
    if "n_questions" not in summary:
        summary["n_questions"] = max([c.get("n", 0) for c in summary.get("conditions", {}).values()] + [0])
        
    for c_id, c_data in summary.get("conditions", {}).items():
        if "mean" in c_data and "accuracy" not in c_data:
            c_data["accuracy"] = c_data["mean"]
    
    # Merge lexical_summary.json if it exists
    lex_path = EVAL_DIR / "lexical_summary.json"
    if lex_path.exists():
        lex = json.loads(lex_path.read_text(encoding="utf-8"))
        if "models" in lex and lex["models"]:
            model_key = list(lex["models"].keys())[0]
            lex_conds = lex["models"][model_key].get("conditions", {})
            for c_id, c_data in lex_conds.items():
                if c_id in summary.get("conditions", {}):
                    summary["conditions"][c_id]["token_f1"] = c_data.get("token_f1")
                    summary["conditions"][c_id]["ref_recall"] = c_data.get("ref_recall")
                    summary["conditions"][c_id]["key_points"] = c_data.get("key_points")
                    
    return summary


@app.get("/api/eval/results")
def eval_results(limit: int = 500):
    p = EVAL_DIR / "results.jsonl"
    if not p.exists():
        raise HTTPException(404, "results.jsonl not found. Run the evaluation first.")
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit]
