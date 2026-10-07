"""Project status checker: shows which phases are complete on THIS machine.

    cd backend
    python status.py
"""
import json
from collections import Counter

from config import EVAL_DIR, INDEX_DIR, RAW_DIR, load_repos


def _count(path):
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _lines(path):
    try:
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def main():
    ok_all = True
    print("== Steps 1-2: ingestion + index (per repo) ==")
    print(f"{'repo':38}{'commits':>8}{'issues':>8}{'PRs':>6}{'index':>7}  chunks")
    for r in load_repos():
        raw, idx = RAW_DIR / r["slug"], INDEX_DIR / r["slug"]
        c, i, p = (_count(raw / f) for f in ("commits.json", "issues.json", "prs.json"))
        stats = {}
        if (idx / "stats.json").exists():
            stats = json.loads((idx / "stats.json").read_text(encoding="utf-8"))
        built = bool(stats)
        counts = stats.get("counts", {})
        flag = "" if (built and c and i and p) else "   <-- incomplete (issues/PRs missing?)"
        ok_all &= not flag
        print(f"{r['slug']:38}{str(c):>8}{str(i):>8}{str(p):>6}{'yes' if built else 'NO':>7}  {counts}{flag}")

    print("\n== Step 3: benchmark ==")
    bench = _lines(EVAL_DIR / "benchmark.jsonl")
    ver = [b for b in bench if b.get("verified")]
    per = Counter(b.get("repo") for b in ver)
    print(f"questions: {len(bench)} | verified: {len(ver)} (target >= 150) | by repo: {dict(per)}")
    ok_all &= len(ver) >= 150

    print("\n== Step 4: experiment ==")
    res = _lines(EVAL_DIR / "results.jsonl")
    conds = Counter(x.get("condition") for x in res)
    print(f"result rows: {len(res)} | per condition: {dict(conds)}")
    print("summary.json:", "found" if (EVAL_DIR / "summary.json").exists() else "MISSING (run evaluation.run_eval + evaluation.stats)")
    ok_all &= (EVAL_DIR / "summary.json").exists()

    print("\n== Step 5: human evaluation ==")
    hum = sorted(p.name for p in EVAL_DIR.glob("*human*"))
    print("human-eval files:", hum or "none (see README, human_eval export/score)")

    print("\nOVERALL:", "steps 1-4 look complete" if ok_all else "not complete yet - see flags above")


if __name__ == "__main__":
    main()
