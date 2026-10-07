# RepoHistory RAG - final run guide

Repos (backend/repos.yaml): seL4/seL4, actualbudget/actual, KDE/kio, CHERIoT-Platform/cheriot-rtos, infiniflow/ragflow.
KDE/kio caveat: it is a read-only GitHub mirror, so GitHub has little/no issue/PR/review history for it.
Report this as a limitation, or swap it for e.g. encode/httpx.

## Setup (once)
    copy .env.example .env        (Linux/Mac: cp)    -> fill GITHUB_TOKEN and your LLM key
    cd backend
    python -m venv .venv
    .venv\Scripts\activate        (Linux/Mac: source .venv/bin/activate)
    pip install -r requirements.txt
    cd ..\frontend && npm install

## Steps
1. Ingest + index   : cd backend && python -m ingestion.run_ingestion --repo all
2. Run the app      : backend: uvicorn api.main:app --port 8000   |   frontend: npm run dev  (http://localhost:5173)
                      or: docker compose up --build  (http://localhost:3000)
3. Benchmark        : python -m evaluation.generate_questions --repo <slug> --n 40   (then hand-verify, set "verified": true,
                      append to data/eval/benchmark.jsonl; target >= 150 verified)
4. Experiment       : python -m evaluation.run_eval ; python -m evaluation.stats
5. Human evaluation : see README (python -m evaluation.human_eval ...)

## Check your progress at any time
    cd backend
    python status.py

## Do not share/upload
backend/.venv, backend/data/repos (git clones), node_modules - they are huge and machine-specific (all git-ignored).
