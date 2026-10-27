# AI DevOps integrations in ReadMind

Four handout requirements, each built on ReadMind's own code rather than bolted on beside it.

| # | Requirement (rubric) | What was added | Where |
|---|---|---|---|
| 1 | RAG Q&A bot with **LangChain or LlamaIndex** (A2, 10%) | ReadMind's history-aware retriever exposed as a LangChain `BaseRetriever` + LCEL chain **and** a LlamaIndex `BaseRetriever` + `RetrieverQueryEngine`; selectable per question in the UI, the API and the benchmark | `backend/rag/frameworks/` |
| 2 | **GitHub Actions CI/CD with Sweep.dev** (A2, 10%) | `sweep.yaml` with project context and rules, a Sweep issue template, CI-failure → Sweep issue loop, and a history-aware AI PR review that runs ReadMind's own citation verifier | `sweep.yaml`, `.github/` |
| 3 | **Test generation with CodiumAI / Codeium** (A2, 5%) | Qodo Cover (CodiumAI's cover-agent) pipeline: target list, local script, scheduled workflow that opens a PR with only tests that pass and raise coverage; coverage tracked in CI | `backend/scripts/`, `.github/workflows/ai-test-generation.yml` |
| 4 | **Sourcegraph setup + semantic code navigation** (A1, 10%) | Sourcegraph in docker compose, code host generated from `repos.yaml`, SCIP indexing in CI, a Code Navigation tab and Sourcegraph links in the evidence drawer | `docker-compose.sourcegraph.yml`, `sourcegraph/`, `backend/api/sourcegraph_client.py` |

---

## 1. LangChain + LlamaIndex RAG

**Design decision (say this in the viva):** the research contribution is the retrieval — BM25 + vectors,
RRF fusion, history-graph expansion, cross-encoder rerank, history quota. Replacing it with a stock
LangChain vector store would remove exactly what the experiment measures. So the frameworks *wrap* it:

```
LangChain   question ─► ReadMindRetriever(BaseRetriever) ─► format evidence ─► ChatPromptTemplate
                        (RepoIndex.retrieve)                                 ─► ReadMindChatModel(BaseChatModel)
                                                                             ─► StrOutputParser      (LCEL)
LlamaIndex  question ─► ReadMindLlamaRetriever(BaseRetriever) ─► RetrieverQueryEngine(compact)
                                                              ─► ReadMindLlamaLLM(CustomLLM)
both        ─► rag.citations.verify_citations ─► rag.guardrails ─► same JSON as the native pipeline
```

Same prompts (`SYSTEM_RAG`, `SYSTEM_NO_CONTEXT`), same provider via `rag.llm.generate`
(gemini / openai / ollama / mock), same `k`, temperature 0 — so the three engines are comparable and the
LangChain run can be reported as a reproducibility check.

**Use it**
- UI: *Ask* tab → **RAG engine** dropdown (ReadMind / LangChain / LlamaIndex). Answers show a 🦜 / 🦙 badge.
- API: `POST /api/ask {"repo": "...", "question": "...", "engine": "langchain"}`; `GET /api/engines`.
- Benchmark: `python -m evaluation.run_eval --engine langchain` → `data/eval/results_langchain.jsonl`.
- Tests: `tests/test_frameworks.py` — every condition through both frameworks, checks retrieval types,
  ablation (`expand=False`), citations and response schema, with a stub index and the mock LLM.

Verified here: on a real Chroma index all three engines return identical evidence ids and identical
citation verification for `full_history`, `code_only` and `llm_only`.

## 2. Sweep.dev + AI-powered GitHub Actions

| File | Role |
|---|---|
| `sweep.yaml` | Branch, `gha_enabled`, blocked dirs (`backend/data/`, `k8s/`, workflows) and ReadMind-specific description + rules (mock-LLM tests, citations, lazy heavy imports, no secrets) |
| `.github/ISSUE_TEMPLATE/sweep-task.yml` | "Sweep: …" issues with the `sweep` label |
| `.github/workflows/sweep-ci-autofix.yml` | When **CI** fails on `main`, opens/updates a `Sweep: Fix failing CI on main` issue with failing jobs + log tail → Sweep opens the fix PR |
| `.github/workflows/ai-pr-review.yml` + `backend/devops/ai_pr_review.py` | On every PR: diff + **recent history of each changed file** → Gemini → cited review → every `[commit:…]` checked with `rag/citations.py` → one sticky PR comment |

The AI review is ReadMind's research idea applied to its own CI (history-aware answers with verified
citations). Without a `GEMINI_API_KEY` secret (e.g. PRs from forks) it posts an offline history report
instead of failing.

**Setup:** install the Sweep GitHub App on the repo (github.com/apps/sweep-ai), add the `GEMINI_API_KEY`
secret, and allow Actions to create PRs (Settings → Actions → General → Workflow permissions).
**Demo:** open a *Sweep task* issue, e.g. "add tests for `backend/rag/guardrails.py` edge cases"; show the
Sweep PR, the CI run and the ReadMind AI review comment on it.

## 3. AI-assisted test generation (Qodo Cover / CodiumAI)

CodiumAI is now **Qodo**; *Qodo Gen* is the IDE plugin and *Qodo Cover* (`cover-agent`) is its open-source
CLI. The pipeline uses Qodo Cover because it runs in CI and only keeps tests that **pass and increase
coverage**:

```bash
cd backend
export GEMINI_API_KEY=...
bash scripts/generate_tests.sh                    # all targets in scripts/ai_test_targets.txt
bash scripts/generate_tests.sh rag/guardrails.py  # one file
# → data/ai-tests/report.md: coverage before / after per file
```

Targets are modules that are testable without Chroma / torch / keys: guardrails, citations, text utils,
link graph, the Sourcegraph client and the AI PR reviewer. The script passes ReadMind-specific
instructions to the agent (mock LLM, no network, plain pytest functions).
`ai-test-generation.yml` runs it weekly or on demand and opens a PR `ai/qodo-generated-tests`, so each
generated test is reviewed by a person, CI and the AI review. CI now reports line coverage, which is the
baseline the generated tests are measured against.

`tests/test_guardrails.py`, `tests/test_sourcegraph_client.py` and `tests/test_ai_pr_review.py` are small
**hand-written seed files** (cover-agent needs an existing test file to extend). The AI-generated tests are
what the workflow appends to them — present only those as AI-generated. You can also use the Qodo Gen IDE
extension (`/test` on a function) for the same files and commit those tests with a `test(qodo-gen):` prefix.

Notes: cover-agent needs Python 3.10–3.12 (CI uses 3.11); the qodo-cover repo is marked no longer
maintained, so it is pinned to tag `0.3.9`.

## 4. Sourcegraph — setup and semantic code navigation

See **`sourcegraph/README.md`** for the full walkthrough. Short version:

```bash
make sourcegraph-up                         # Sourcegraph 6.x on http://localhost:7080
python sourcegraph/sync_code_host.py        # code host JSON for ReadMind + every repo in repos.yaml
# add it in Site admin → Code host connections, create an access token → .env SOURCEGRAPH_TOKEN
SRC_ACCESS_TOKEN=... make scip              # precise go-to-definition / find-references for ReadMind
```

In the app: **🔎 Code Navigation** tab (code / symbol / structural / regex / commit search, scoped to the
selected repo or all, with *Ask why →* into the history RAG) and Sourcegraph links in the evidence drawer.
API: `GET /api/sourcegraph/status`, `POST /api/sourcegraph/search`, `GET /api/sourcegraph/links`.

---

## New secrets / settings

| Name | Where | Used by |
|---|---|---|
| `GEMINI_API_KEY` | repo secret | AI PR review, AI test generation |
| `SRC_ENDPOINT`, `SRC_ACCESS_TOKEN` | repo secrets (optional) | SCIP upload from CI |
| `LLM_MODEL` | repo variable (optional) | AI PR review model (default `gemini-2.5-flash`) |
| `SOURCEGRAPH_URL`, `SOURCEGRAPH_TOKEN` | `.env` | backend Sourcegraph client |

## Check everything

```bash
cd backend && pip install -r requirements.txt
LLM_PROVIDER=mock EMBED_MODEL=hash pytest -q --cov=.    # 34 tests incl. frameworks, Sourcegraph, AI review
cd ../frontend && npm run build
```
