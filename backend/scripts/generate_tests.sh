#!/usr/bin/env bash
# AI-assisted test generation for ReadMind with Qodo Cover (CodiumAI's open-source cover-agent).
#
# For each target in scripts/ai_test_targets.txt, cover-agent asks an LLM for new tests, runs them,
# keeps only the ones that PASS and RAISE coverage, and appends them to the existing test file.
#
#   cd backend
#   export GEMINI_API_KEY=...                       # or OPENAI_API_KEY + COVER_MODEL=gpt-4o-mini
#   bash scripts/generate_tests.sh                  # all targets
#   bash scripts/generate_tests.sh rag/guardrails.py   # one target
#
# Report: data/ai-tests/report.md (coverage before/after per file).
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${COVER_MODEL:-gemini/gemini-2.5-flash}"   # any LiteLLM model id
ITERATIONS="${COVER_MAX_ITERATIONS:-3}"
ONLY="${1:-}"
OUT_DIR="data/ai-tests"
mkdir -p "$OUT_DIR"
export LLM_PROVIDER=mock EMBED_MODEL=hash          # ReadMind's own tests never call a real LLM
INSTRUCTIONS="This is ReadMind's FastAPI backend. Write plain pytest functions (no classes). Tests run from backend/ with \
LLM_PROVIDER=mock and EMBED_MODEL=hash and must not need network, API keys, chromadb, sentence_transformers or torch; \
use small in-memory fixtures or stub objects. Import modules as e.g. 'from rag.guardrails import ...'. \
Assert on concrete values, not just that no exception is raised."

if ! command -v cover-agent >/dev/null; then
  echo "Installing Qodo Cover (cover-agent)…"
  pip install --quiet "git+https://github.com/qodo-ai/qodo-cover.git@0.3.9"   # needs Python 3.10-3.12
fi

coverage_of() {  # line coverage % of one source file from coverage.xml
  python - "$1" <<'PY'
import sys, xml.etree.ElementTree as ET
target = sys.argv[1]
try:
    root = ET.parse("coverage.xml").getroot()
except Exception:
    print("n/a"); sys.exit()
for c in root.iter("class"):
    if c.get("filename", "").replace("\\", "/").endswith(target):
        print(f"{float(c.get('line-rate', 0)) * 100:.0f}"); sys.exit()
print("0")
PY
}

run_cov() { python -m pytest -q --cov=. --cov-report=xml:coverage.xml "$@" >/dev/null 2>&1 || true; }

REPORT="$OUT_DIR/report.md"
{
  echo "# AI test generation report ($(date -u +%Y-%m-%dT%H:%MZ))"
  echo
  echo "Tool: Qodo Cover (cover-agent) · model \`$MODEL\` · max iterations $ITERATIONS"
  echo
  echo "| Source file | Test file | Coverage before | Coverage after | Target |"
  echo "|---|---|---|---|---|"
} > "$REPORT"

grep -vE '^\s*(#|$)' scripts/ai_test_targets.txt | while read -r SRC TEST TARGET; do
  [ -n "$ONLY" ] && [ "$SRC" != "$ONLY" ] && continue
  echo "▶ $SRC → $TEST (target ${TARGET}%)"
  [ -f "$TEST" ] || printf '"""Tests for %s (seeded for AI test generation)."""\n' "$SRC" > "$TEST"

  run_cov "$TEST"
  BEFORE=$(coverage_of "$SRC")

  cover-agent \
    --source-file-path "$SRC" \
    --test-file-path "$TEST" \
    --project-root . \
    --code-coverage-report-path coverage.xml \
    --test-command "python -m pytest -q --cov=. --cov-report=xml:coverage.xml $TEST" \
    --test-command-dir . \
    --coverage-type cobertura \
    --desired-coverage "$TARGET" \
    --max-iterations "$ITERATIONS" \
    --model "$MODEL" \
    --additional-instructions "$INSTRUCTIONS" \
    --report-filepath "$OUT_DIR/$(basename "$SRC" .py)_report.html" \
    --log-db-path "$OUT_DIR/cover_agent.db" \
    || echo "  cover-agent stopped early for $SRC (kept whatever passing tests it added)"

  run_cov "$TEST"
  AFTER=$(coverage_of "$SRC")
  echo "| \`$SRC\` | \`$TEST\` | ${BEFORE}% | ${AFTER}% | ${TARGET}% |" >> "$REPORT"
done

echo
echo "▶ full suite with generated tests"
python -m pytest -q
cat "$REPORT"
