.PHONY: install ingest api web test eval stats up eval-langchain eval-llamaindex ai-tests ai-review sourcegraph-up sourcegraph-code-host scip

install:            ## install backend + frontend dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

ingest:             ## extract + index every repo in backend/repos.yaml
	cd backend && python -m ingestion.run_ingestion --repo all

api:                ## run the FastAPI backend on :8000
	cd backend && uvicorn api.main:app --reload --port 8000

web:                ## run the React dev server on :5173
	cd frontend && npm run dev

test:               ## unit tests (+ coverage)
	cd backend && LLM_PROVIDER=mock EMBED_MODEL=hash pytest -q --cov=. --cov-report=term

eval:               ## run the benchmark under all 3 conditions
	cd backend && python -m evaluation.run_eval

stats:              ## recompute summary.json from results.jsonl
	cd backend && python -m evaluation.stats

up:                 ## everything in Docker (frontend on :3000)
	docker compose up --build

# ---------- AI DevOps integrations (see DEVOPS_AI.md) ----------
eval-langchain:     ## run the benchmark through the LangChain engine
	cd backend && python -m evaluation.run_eval --engine langchain

eval-llamaindex:    ## run the benchmark through the LlamaIndex engine
	cd backend && python -m evaluation.run_eval --engine llamaindex

ai-tests:           ## AI test generation with Qodo Cover (needs GEMINI_API_KEY, Python 3.10-3.12)
	cd backend && bash scripts/generate_tests.sh

ai-review:          ## history-aware AI review of your branch vs main
	cd backend && python -m devops.ai_pr_review --base origin/main --head HEAD --repo-dir ..

sourcegraph-up:     ## start Sourcegraph on http://localhost:7080
	docker compose -f docker-compose.yml -f docker-compose.sourcegraph.yml up -d sourcegraph

sourcegraph-code-host: ## print the Sourcegraph GitHub code-host config from repos.yaml
	python sourcegraph/sync_code_host.py

scip:               ## build + upload SCIP indexes to local Sourcegraph (needs SRC_ACCESS_TOKEN)
	bash sourcegraph/upload-scip.sh
