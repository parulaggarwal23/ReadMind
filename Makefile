.PHONY: install ingest api web test eval stats up

install:            ## install backend + frontend dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

ingest:             ## extract + index every repo in backend/repos.yaml
	cd backend && python -m ingestion.run_ingestion --repo all

api:                ## run the FastAPI backend on :8000
	cd backend && uvicorn api.main:app --reload --port 8000

web:                ## run the React dev server on :5173
	cd frontend && npm run dev

test:               ## unit tests
	cd backend && LLM_PROVIDER=mock EMBED_MODEL=hash pytest -q

eval:               ## run the benchmark under all 3 conditions
	cd backend && python -m evaluation.run_eval

stats:              ## recompute summary.json from results.jsonl
	cd backend && python -m evaluation.stats

up:                 ## everything in Docker (frontend on :3000)
	docker compose up --build
