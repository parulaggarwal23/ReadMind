# RepoHistory RAG

**Research question:** Does incorporating repository history (commits, issues, pull requests, code reviews) into an LLM-RAG pipeline improve the accuracy and usefulness of software-development answers?

The system answers developer questions like *"Why did the previous developers implement authentication this way?"* with explanations **grounded in, and cited to, real repository evidence**, and it includes the full evaluation harness that compares:

| Condition | Context given to the LLM |
|---|---|
| `llm_only` | Question only |
| `code_only` | RAG over current code + docs |
| `full_history` | RAG over code + docs + commits + issues + PRs + reviews, with history-graph expansion |
| `full_no_graph` *(ablation)* | Same as `full_history` but without graph expansion |

---

## Architecture

```
OFFLINE  repos.yaml ─► clone + PyDriller commits ─► GitHub API issues / PRs / reviews
                    ─► code chunks (function/class) + doc sections
                    ─► history graph  (code ─file─ commit ─ PR ─ issue ─ review)
                    ─► embeddings → Chroma   (+ BM25 rebuilt from docs.jsonl)

ONLINE   question ─► BM25 + vector search ─► RRF fusion ─► graph expansion
                  ─► cross-encoder rerank ─► history quota ─► LLM with [id] citations
                  ─► citation verifier ─► answer + evidence + latency   (FastAPI → React)

EVAL     benchmark.jsonl ─► every condition ─► retrieval metrics + LLM judge
                         ─► summary.json (+ Wilcoxon tests) ─► dashboard; human-eval export/score
```

## Project structure

```
repo-history-rag/
├── .env.example                  # copy to .env
├── docker-compose.yml
├── Makefile
├── .github/workflows/ci.yml      # tests + frontend build + docker build
├── backend/
│   ├── config.py                 # all settings (env vars)
│   ├── repos.yaml                # ← your 5 repositories
│   ├── requirements.txt / requirements-ci.txt / Dockerfile
│   ├── ingestion/
│   │   ├── extract_git.py        # clone + commits (PyDriller)
│   │   ├── extract_github.py     # issues, PRs, review comments, discussions
│   │   ├── extract_code.py       # function/class chunks + doc sections
│   │   ├── link_graph.py         # history graph + reference parsing
│   │   ├── build_index.py        # documents → Chroma + graph + stats
│   │   └── run_ingestion.py      # CLI
│   ├── rag/
│   │   ├── text_utils.py         # identifier-aware tokenizer
│   │   ├── embeddings.py         # sentence-transformers (or offline "hash")
│   │   ├── retriever.py          # hybrid retrieval, RRF, graph expansion, rerank
│   │   ├── llm.py                # gemini | openai | ollama | mock
│   │   ├── citations.py          # citation extraction + verification
│   │   └── pipeline.py           # the experimental conditions
│   ├── api/main.py               # FastAPI
│   ├── evaluation/
│   │   ├── generate_questions.py # draft benchmark questions from history
│   │   ├── metrics.py            # precision/recall/MRR + LLM judge
│   │   ├── run_eval.py           # run benchmark × conditions (resumable)
│   │   ├── stats.py              # summary.json + Wilcoxon tests
│   │   ├── human_eval.py         # blinded sheets + Cohen's kappa
│   │   └── benchmark.example.jsonl
│   └── tests/
└── frontend/                     # Vite + React
    ├── Dockerfile / nginx.conf / vite.config.js / package.json / index.html
    └── src/
        ├── api.js, App.jsx, main.jsx, styles.css
        └── components/  AskPanel, AnswerCard, AnswerText, EvidenceList,
                         EvidenceDrawer, CompareView, EvalDashboard, RepoSelector
```

---

## Setup

**Requirements:** Python 3.11+, Node 20+, git. Docker is optional.

```bash
cp .env.example .env            # add GITHUB_TOKEN and GEMINI_API_KEY (or OpenAI / Ollama)
# backend/repos.yaml is configured with: seL4/seL4, actualbudget/actual, KDE/kio, CHERIoT-Platform/cheriot-rtos, infiniflow/ragflow

cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd ../frontend && npm install
```

### 1. Ingest the repositories

```bash
cd backend
python -m ingestion.run_ingestion --repo all
```

The first run downloads the embedding model (~130 MB) and fetches the GitHub data. PRs cost 5 API calls each, so 400 PRs is about 2,000 calls; with a token that fits well within the hourly limit, and the script waits automatically if it hits the limit. Raw data is cached in `data/raw/`, so re-runs are fast. Use `--refresh` to fetch new history.

Check the printed counts. If `issue`/`pr` counts are 0, the token is missing or the repo has issues disabled.

### 2. Run the app

```bash
# terminal 1
cd backend && uvicorn api.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev          # http://localhost:5173
```

Or run everything in Docker: `docker compose up --build`, then open http://localhost:3000.

**UI:** *Ask* (one condition, clickable citations, evidence drawer with linked history and GitHub links), *Compare conditions* (same question, three answers side by side), *Evaluation* (charts, metrics table, significance tests, per-category and human-eval tables).

### 3. Build the benchmark

```bash
python -m evaluation.generate_questions --repo owner__name --n 50
```

This drafts questions from real issue → PR → commit chains into `data/eval/candidates_<slug>.jsonl`. **Every question must be checked by a person.** Open the gold evidence (the UI evidence drawer or GitHub), fix the question and reference answer, remove bad ones, set `"verified": true`, and append to `data/eval/benchmark.jsonl`. See `evaluation/benchmark.example.jsonl` for the format. Target: ~30–40 verified questions per repo (150–200 total), spread over the five categories: `rationale`, `provenance`, `bug_history`, `rejected_alternative`, `change_impact`.

### 4. Run the experiment

```bash
python -m evaluation.run_eval                                   # 3 main conditions
python -m evaluation.run_eval --conditions full_no_graph        # ablation
python -m evaluation.stats                                      # recompute summary
```

Results go to `data/eval/results.jsonl` (resumable) and `summary.json` / `summary.csv`, which the dashboard reads.

### 5. Human evaluation

```bash
python -m evaluation.human_eval export --n 40      # blinded human_sheet.csv
# each rater fills accuracy + usefulness (1–5) → rater1.csv, rater2.csv, rater3.csv
python -m evaluation.human_eval score data/eval/rater1.csv data/eval/rater2.csv data/eval/rater3.csv
python -m evaluation.stats                          # merges human results into summary
```

---

## Metrics

| Metric | How |
|---|---|
| Answer accuracy (1–5) | LLM judge vs verified reference answer + gold evidence |
| Relevance (1–5) | LLM judge |
| Completeness | Share of the question's key points covered (judge) |
| Hallucination rate | Unsupported or contradicted claims ÷ total claims (judge) |
| Evidence precision@k / recall@k / MRR | Retrieved ids vs `gold_evidence` |
| Valid citations | Cited ids that were actually retrieved (automatic, no judge) |
| Latency | Retrieval, generation and total per question; p50 / p95 |
| Human rating | Blinded 1–5 accuracy + usefulness, weighted Cohen's κ |
| Significance | Paired Wilcoxon signed-rank test per metric and condition pair |

## Notes for a sound study

- **Memorisation:** famous repos can be answered from the LLM's training data, which inflates `llm_only`. Report results per repo, and include at least one less-popular repo or questions about history newer than the model's training cutoff.
- **Judge bias:** use a different or stronger model as `JUDGE_MODEL` than the answering model, and validate the judge against human ratings on a sample.
- **Fairness:** all conditions use the same LLM, temperature 0 and the same `k`.
- **Known limitation:** code chunks are linked to history at file level. Line-level linking via `git blame` is a good extension.

## Tests

```bash
cd backend && LLM_PROVIDER=mock EMBED_MODEL=hash pytest -q
```

`LLM_PROVIDER=mock` and `EMBED_MODEL=hash` run the whole pipeline without API keys or model downloads, which is useful for demos without internet and for CI.
