"""Aggregate results.jsonl into summary.json / summary.csv with paired significance tests.

    python -m evaluation.stats"""
import itertools
import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import wilcoxon

from config import EVAL_DIR

METRICS = ["accuracy", "relevance", "completeness", "hallucination_rate", "precision_at_k", "recall_at_k",
           "mrr", "citation_precision", "grounded_ratio"]
TESTED = ["accuracy", "completeness", "hallucination_rate", "relevance"]
ORDER = ["llm_only", "code_only", "full_history", "full_no_graph"]


def _clean(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), 4)


def summarize(results_path=EVAL_DIR / "results.jsonl", out_dir=EVAL_DIR) -> dict:
    df = pd.read_json(results_path, lines=True)
    conds = [c for c in ORDER if c in set(df["condition"])]
    summary = {"n_questions": int(df["qid"].nunique()), "n_rows": len(df), "conditions": {}, "tests": [],
               "per_category": {}, "per_repo": {}}

    for cond in conds:
        g = df[df["condition"] == cond]
        m = {metric: _clean(g[metric].mean()) if metric in g and g[metric].notna().any() else None
             for metric in METRICS}
        lat = g["latency_total_ms"]
        m.update({"n": len(g), "latency_mean_ms": _clean(lat.mean()), "latency_p50_ms": _clean(lat.quantile(0.5)),
                  "latency_p95_ms": _clean(lat.quantile(0.95))})
        summary["conditions"][cond] = m

    for metric in TESTED:
        if metric not in df:
            continue
        pivot = df.pivot_table(index="qid", columns="condition", values=metric)
        for a, b in itertools.combinations(reversed(conds), 2):  # full_history vs others first
            if a not in pivot or b not in pivot:
                continue
            pair = pivot[[a, b]].dropna()
            entry = {"metric": metric, "a": a, "b": b, "n": len(pair),
                     "mean_a": _clean(pair[a].mean()), "mean_b": _clean(pair[b].mean()),
                     "statistic": None, "p_value": None}
            if len(pair) >= 5 and (pair[a] - pair[b]).abs().sum() > 0:
                try:
                    stat, p = wilcoxon(pair[a], pair[b])
                    entry.update(statistic=_clean(stat), p_value=_clean(p))
                except ValueError:
                    pass
            summary["tests"].append(entry)

    for key, col in (("per_category", "category"), ("per_repo", "repo")):
        if col in df and "accuracy" in df:
            grouped = df.groupby([col, "condition"])["accuracy"].mean()
            for (grp, cond), val in grouped.items():
                summary[key].setdefault(str(grp), {})[cond] = _clean(val)

    human = Path(out_dir) / "human_summary.json"
    if human.exists():
        summary["human"] = json.loads(human.read_text(encoding="utf-8"))

    Path(out_dir, "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(summary["conditions"]).T.to_csv(Path(out_dir, "summary.csv"))
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
