#!/usr/bin/env bash
# Build ReadMind's SCIP indexes locally and upload them to your Sourcegraph (default http://localhost:7080).
#
#   export SRC_ACCESS_TOKEN=<token from Sourcegraph → Settings → Access tokens>
#   bash sourcegraph/upload-scip.sh
#
# Needs: Node 20+, Python venv with backend requirements active, git checkout of ReadMind.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SRC_ENDPOINT="${SRC_ENDPOINT:-http://localhost:7080}"
: "${SRC_ACCESS_TOKEN:?Set SRC_ACCESS_TOKEN first}"
REPO="${READMIND_SG_REPO:-github.com/parulaggarwal23/ReadMind}"
COMMIT="$(git -C "$ROOT" rev-parse HEAD)"

command -v scip-python >/dev/null || npm install -g @sourcegraph/scip-python
command -v scip-typescript >/dev/null || npm install -g @sourcegraph/scip-typescript
command -v src >/dev/null || npm install -g @sourcegraph/src

echo "▶ indexing backend"
(cd "$ROOT/backend" && scip-python index . --project-name=readmind-backend --output=index.scip)
echo "▶ indexing frontend"
(cd "$ROOT/frontend" && [ -d node_modules ] || npm install --no-audit --no-fund)
(cd "$ROOT/frontend" && scip-typescript index scip --output index.scip)

# Sourcegraph matches uploads to the commit it has cloned, so HEAD must be pushed to GitHub.
echo "▶ uploading to $SRC_ENDPOINT ($REPO @ ${COMMIT:0:10})"
(cd "$ROOT" && src code-intel upload -file=backend/index.scip  -root=backend  -repo="$REPO" -commit="$COMMIT" -no-progress)
(cd "$ROOT" && src code-intel upload -file=frontend/index.scip -root=frontend -repo="$REPO" -commit="$COMMIT" -no-progress)
echo "✔ done — open $SRC_ENDPOINT/$REPO and hover any symbol: 'Go to definition' / 'Find references' are now precise"
