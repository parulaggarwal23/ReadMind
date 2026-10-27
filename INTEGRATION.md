# Integration guide — ReadMind AI DevOps files

Every file in this zip sits at its exact path in the ReadMind repo. Copy the folders over the repo root
(NEW files are added, MODIFIED files replace the current version), or apply everything at once from the repo root:

```bash
git apply --check readmind-devops.patch && git apply readmind-devops.patch
```

Made against commit 0fddfc7 (main). What each concept adds and how to demo it: DEVOPS_AI.md.

## Files

| Status | Path | Concept |
|---|---|---|
| MODIFIED | `.env.example` | 4 Sourcegraph |
| MODIFIED | `.github/workflows/ci.yml` | 3 AI test generation (Qodo Cover) |
| MODIFIED | `.gitignore` | docs / tooling |
| MODIFIED | `Makefile` | docs / tooling |
| MODIFIED | `README.md` | docs / tooling |
| MODIFIED | `backend/api/main.py` | 1 + 4 (engine switch, Sourcegraph routes/tab) |
| MODIFIED | `backend/config.py` | 4 Sourcegraph |
| MODIFIED | `backend/evaluation/run_eval.py` | 1 LangChain / LlamaIndex |
| MODIFIED | `backend/rag/pipeline.py` | 1 LangChain / LlamaIndex |
| MODIFIED | `backend/requirements-ci.txt` | 1 + 3 (langchain-core, llama-index-core, pytest-cov, fastapi in CI) |
| MODIFIED | `backend/requirements.txt` | 1 + 3 (langchain-core, llama-index-core, pytest-cov, fastapi in CI) |
| MODIFIED | `frontend/src/App.jsx` | 1 + 4 (engine switch, Sourcegraph routes/tab) |
| MODIFIED | `frontend/src/api.js` | 1 + 4 (engine switch, Sourcegraph routes/tab) |
| MODIFIED | `frontend/src/components/AnswerCard.jsx` | 1 LangChain / LlamaIndex |
| MODIFIED | `frontend/src/components/AskPanel.jsx` | 1 LangChain / LlamaIndex |
| MODIFIED | `frontend/src/components/EvidenceDrawer.jsx` | 4 Sourcegraph |
| MODIFIED | `frontend/src/styles.css` | 1 + 4 (engine switch, Sourcegraph routes/tab) |
| NEW | `.github/ISSUE_TEMPLATE/sweep-task.yml` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `.github/workflows/ai-pr-review.yml` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `.github/workflows/ai-test-generation.yml` | 3 AI test generation (Qodo Cover) |
| NEW | `.github/workflows/sourcegraph-scip.yml` | 4 Sourcegraph |
| NEW | `.github/workflows/sweep-ci-autofix.yml` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `DEVOPS_AI.md` | docs / tooling |
| NEW | `backend/api/sourcegraph_client.py` | 4 Sourcegraph |
| NEW | `backend/devops/__init__.py` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `backend/devops/ai_pr_review.py` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `backend/rag/frameworks/__init__.py` | 1 LangChain / LlamaIndex |
| NEW | `backend/rag/frameworks/common.py` | 1 LangChain / LlamaIndex |
| NEW | `backend/rag/frameworks/langchain_rag.py` | 1 LangChain / LlamaIndex |
| NEW | `backend/rag/frameworks/llamaindex_rag.py` | 1 LangChain / LlamaIndex |
| NEW | `backend/scripts/ai_test_targets.txt` | 3 AI test generation (Qodo Cover) |
| NEW | `backend/scripts/generate_tests.sh` | 3 AI test generation (Qodo Cover) |
| NEW | `backend/tests/test_ai_pr_review.py` | 2 Sweep.dev + AI GitHub Actions |
| NEW | `backend/tests/test_frameworks.py` | 1 LangChain / LlamaIndex |
| NEW | `backend/tests/test_guardrails.py` | 3 AI test generation (Qodo Cover) |
| NEW | `backend/tests/test_sourcegraph_client.py` | 4 Sourcegraph |
| NEW | `docker-compose.sourcegraph.yml` | 4 Sourcegraph |
| NEW | `frontend/scip/tsconfig.json` | 4 Sourcegraph |
| NEW | `frontend/src/components/SourcegraphView.jsx` | 4 Sourcegraph |
| NEW | `sourcegraph/README.md` | 4 Sourcegraph |
| NEW | `sourcegraph/code-host-github.json` | 4 Sourcegraph |
| NEW | `sourcegraph/sync_code_host.py` | 4 Sourcegraph |
| NEW | `sourcegraph/upload-scip.sh` | 4 Sourcegraph |
| NEW | `sweep.yaml` | 2 Sweep.dev + AI GitHub Actions |
