# Sourcegraph for ReadMind — setup and semantic code navigation

ReadMind answers **why** code looks the way it does (RAG over commits, issues, PRs, reviews).
Sourcegraph answers **where / what**: cross-repo code search, symbol search, structural search and
precise *go to definition / find references*. ReadMind uses it in three places:

| Where | What it does |
|---|---|
| **🔎 Code Navigation** tab | Search the study repos (or one repo) by code, symbol, structural pattern, regex or commit; each file result has **Ask why →**, which sends it to ReadMind's history RAG |
| Evidence drawer | Code evidence gets *view in Sourcegraph*, *find references*, *symbol search* and *file history* links; commit evidence gets a Sourcegraph commit link |
| CI (`sourcegraph-scip.yml`) | Builds SCIP indexes for the Python backend (`scip-python`) and React frontend (`scip-typescript`) and uploads them, so navigation in ReadMind's own code is precise, not text-based |

## 1. Start Sourcegraph

```bash
docker compose -f docker-compose.yml -f docker-compose.sourcegraph.yml up -d sourcegraph
# or: make sourcegraph-up
```

Open http://localhost:7080 (first start takes 1–2 minutes) and create the admin account.
The image is pinned to the last 6.x single-container release; set `SOURCEGRAPH_VERSION` to change it.

## 2. Add the repositories

Site admin → **Code host connections** → **Add** → **GitHub**, then paste `sourcegraph/code-host-github.json`
with your `GITHUB_TOKEN`. The list is ReadMind itself plus every repo in `backend/repos.yaml`.
To regenerate it after editing `repos.yaml` (or create it through the API):

```bash
python sourcegraph/sync_code_host.py            # prints the JSON
python sourcegraph/sync_code_host.py --apply    # creates the code host (needs SOURCEGRAPH_TOKEN)
```

Wait until the repos show as cloned (Site admin → Repositories).

## 3. Connect ReadMind

Sourcegraph → your avatar → **Settings → Access tokens** → generate one, then in `.env`:

```
SOURCEGRAPH_URL=http://localhost:7080      # backend run with uvicorn
SOURCEGRAPH_TOKEN=sgp_...
```

(With the full docker-compose stack the overlay already sets `SOURCEGRAPH_URL=http://sourcegraph:7080`.)
Restart the backend; the **🔎 Code Navigation** tab shows a green *Sourcegraph 6.x* badge.

## 4. Precise code navigation (SCIP)

```bash
export SRC_ACCESS_TOKEN=sgp_...
bash sourcegraph/upload-scip.sh        # or: make scip
```

This indexes `backend/` with scip-python and `frontend/` with scip-typescript and uploads both for the
current commit (push it to GitHub first, Sourcegraph matches uploads to commits it has cloned).
In CI, `.github/workflows/sourcegraph-scip.yml` does the same on every push to `main`; it uploads when
the `SRC_ENDPOINT` and `SRC_ACCESS_TOKEN` secrets point at a Sourcegraph that GitHub can reach, and
always keeps the indexes as a workflow artifact.

Check it worked: open `github.com/parulaggarwal23/ReadMind` in Sourcegraph → `backend/rag/retriever.py`
→ hover `RepoIndex` → the popover says **Precise** and *Find references* lists `pipeline.py`, `api/main.py`,
`run_eval.py` and the LangChain / LlamaIndex engines.

## Queries worth showing in the demo

| Goal | Query |
|---|---|
| Where is ReadMind's retrieval defined and used? | `repo:ReadMind$ type:symbol retrieve` |
| Every LLM provider branch | `repo:ReadMind$ lang:python provider ==` |
| All FastAPI routes | `repo:ReadMind$ patternType:regexp @app\.(get\|post\|delete)\(` |
| Structural: functions that swallow exceptions | `repo:ReadMind$ lang:python patternType:structural except Exception: pass` |
| Session handling across all study repos | `session rotate count:50` |
| Commits about flaky tests in ragflow | `repo:infiniflow/ragflow$ type:commit flaky` |
| Code changed by a specific commit's area | `repo:actualbudget/actual$ type:diff budget` |

## Troubleshooting

- **"Sourcegraph offline" in the tab** — check `SOURCEGRAPH_URL` from the backend's point of view
  (`localhost` for uvicorn, `sourcegraph` inside docker compose).
- **401/403** — `SOURCEGRAPH_TOKEN` missing or expired.
- **No precise navigation** — the SCIP upload is for a commit Sourcegraph has not cloned yet; push, wait for
  the repo to update, re-run `upload-scip.sh`.
