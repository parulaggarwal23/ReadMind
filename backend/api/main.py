"""FastAPI backend.   Run from backend/:   uvicorn api.main:app --reload --port 8000"""
import json
from typing import Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import CORS_ORIGINS, EVAL_DIR, LLM_MODEL, LLM_PROVIDER
from rag.pipeline import CONDITIONS, answer_question
from rag.retriever import get_index, list_indexed

app = FastAPI(title="ReadMind", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

Condition = Literal["llm_only", "code_only", "full_history"]


class AskRequest(BaseModel):
    repo: str
    question: str = Field(min_length=3, max_length=2000)
    condition: Condition = "full_history"
    top_k: int = Field(8, ge=1, le=20)


class CompareRequest(BaseModel):
    repo: str
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(8, ge=1, le=20)


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


@app.post("/api/ask")
def ask(req: AskRequest):
    _index(req.repo)
    try:
        return answer_question(req.repo, req.question, req.condition, req.top_k)
    except Exception as e:  # surface LLM/provider errors to the UI
        raise HTTPException(502, f"{type(e).__name__}: {e}")

import subprocess

@app.post("/api/ingest")
def run_ingest(req: dict):
    repo = req.get("repo")
    if not repo:
        raise HTTPException(400, "repo is required")
        
    slug = repo.replace("/", "__")
    
    # 1. Append to repos.yaml if not already there
    repos_file = Path("repos.yaml")
    content = repos_file.read_text()
    if repo not in content:
        with open("repos.yaml", "a") as f:
            f.write(f"\n  - github: {repo}\n")
            
    # 2. Run ingestion synchronously so the frontend can wait for it
    try:
        subprocess.run(["python", "-m", "ingestion.run_ingestion", "--repo", slug], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Ingestion failed: {e}")
        
    return {"status": "success", "slug": slug}

import shutil
from config import INDEX_DIR, RAW_DIR

@app.delete("/api/repos/{slug}")
def delete_repo(slug: str):
    repo = slug.replace("__", "/")
    
    # 1. Remove from repos.yaml
    repos_file = Path("repos.yaml")
    if repos_file.exists():
        content = repos_file.read_text().splitlines()
        new_content = [line for line in content if repo not in line]
        repos_file.write_text("\n".join(new_content) + "\n")
        
    # 2. Delete index and raw data folders
    shutil.rmtree(INDEX_DIR / slug, ignore_errors=True)
    shutil.rmtree(RAW_DIR / slug, ignore_errors=True)
    
    return {"status": "deleted"}


@app.get("/api/repos/{slug}/sample-chunks")
def sample_chunks(slug: str, skip: int = 0, limit: int = 10):
    idx = _index(slug)
    return [idx.docs[i] for i in idx.ids[skip : skip + limit]]


@app.get("/api/repos/{slug}/sample-embeddings")
def sample_embeddings(slug: str, skip: int = 0, limit: int = 10):
    idx = _index(slug)
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
    return samples

@app.post("/api/compare")
def compare(req: CompareRequest):
    _index(req.repo)
    results = []
    for cond in CONDITIONS:  # sequential so latency numbers aren't distorted
        try:
            results.append(answer_question(req.repo, req.question, cond, req.top_k))
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
