"""Judge-free answer metrics: how much of the verified reference answer does each answer contain?

    python evaluation/lexical_metrics.py --results data/eval/results.jsonl --benchmark data/eval/benchmark.jsonl

Needs only numpy and scipy, and no LLM, so the numbers are exactly reproducible. For every answer:
  token_f1      F1 between the answer's content words and the reference answer's content words
  ref_recall    share of the reference's content words that appear in the answer
  key_points    share of the question's key points whose content words are at least 60% present

These are overlap measures, not correctness judgements: an answer can share words with the reference
and still be wrong, or be right in different words. Use them next to an LLM judge and human ratings,
and as a check on whether the judge can be trusted."""
import argparse
import collections
import json
import re

import numpy as np
from scipy.stats import spearmanr, wilcoxon

STOP = set("the a an and or of to in is it for on this that with as be was were are by at from why what how did "
           "does do which when who has have had not but if so its their they them then than there also can could "
           "would will now no into only both each such these those being been because where while after before "
           "about over under more most other some any all very".split())
# Small models often copy this sentence from the prompt before answering; it says nothing about content.
BOILERPLATE = re.compile(r"the available evidence does not explain this\.?", re.I)
CITATION = re.compile(r"\[(?:commit|issue|pr|review|code|doc):")
ORDER = ["llm_only", "code_only", "full_history", "full_no_graph"]


def tokens(text):
    out = []
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", (text or "").lower()):
        for part in word.split("_"):
            if len(part) > 2 and part not in STOP:
                out.append(re.sub(r"(ing|ed|es|s)$", "", part) if len(part) > 5 else part)
    return out


def overlap(answer, reference):
    a, r = collections.Counter(tokens(answer)), collections.Counter(tokens(reference))
    common = sum((a & r).values())
    if not common:
        return 0.0, 0.0
    precision, recall = common / sum(a.values()), common / sum(r.values())
    return 2 * precision * recall / (precision + recall), recall


def key_point_coverage(answer, key_points, threshold=0.6):
    have = set(tokens(answer))
    hits = sum(1 for k in key_points if set(tokens(k)) and len(set(tokens(k)) & have) / len(set(tokens(k))) >= threshold)
    return hits / len(key_points) if key_points else None


def ci(values, rng):
    v = np.asarray(values, float)
    means = v[rng.integers(0, len(v), (2000, len(v)))].mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--out", default="lexical_summary.json")
    args = ap.parse_args()
    rng = np.random.default_rng(13)
    bench = {b["id"]: b for b in map(json.loads, open(args.benchmark, encoding="utf-8"))}
    recs = []
    for line in open(args.results, encoding="utf-8"):
        r = json.loads(line)
        b = bench[r["qid"]]
        answer = BOILERPLATE.sub("", r["answer"])
        f1, recall = overlap(answer, b["reference_answer"])
        recs.append({"qid": r["qid"], "condition": r["condition"], "model": r.get("model", "default"),
                     "repo": r["repo"], "category": r.get("category"), "token_f1": f1, "ref_recall": recall,
                     "key_points": key_point_coverage(answer, b.get("key_points", [])),
                     "starts_with_boilerplate": bool(BOILERPLATE.search(r["answer"])),
                     "has_citation": bool(CITATION.search(r["answer"])), "judge_accuracy": r.get("accuracy")})

    out = {"n_rows": len(recs), "models": {}}
    for model in sorted({x["model"] for x in recs}):
        mine = [x for x in recs if x["model"] == model]
        conds = [c for c in ORDER if any(x["condition"] == c for x in mine)]
        summary = {}
        for c in conds:
            g = [x for x in mine if x["condition"] == c]
            summary[c] = {"n": len(g)}
            for m in ("token_f1", "ref_recall", "key_points"):
                vals = [x[m] for x in g if x[m] is not None]
                summary[c][m] = round(float(np.mean(vals)), 4)
                summary[c][m + "_ci"] = ci(vals, rng)
            summary[c]["starts_with_boilerplate"] = round(float(np.mean([x["starts_with_boilerplate"] for x in g])), 4)
            summary[c]["has_citation"] = round(float(np.mean([x["has_citation"] for x in g])), 4)

        by_q = collections.defaultdict(dict)
        for x in mine:
            by_q[x["qid"]][x["condition"]] = x
        tests = []
        for m in ("token_f1", "key_points"):
            for i, b_ in enumerate(conds):
                for a_ in conds[i + 1:]:
                    pairs = [(q[a_][m], q[b_][m]) for q in by_q.values() if a_ in q and b_ in q]
                    if len(pairs) < 6:
                        continue
                    A, B = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
                    diff = A - B
                    p = float(wilcoxon(A, B).pvalue) if np.abs(diff).sum() > 0 else None
                    tests.append({"metric": m, "a": a_, "b": b_, "n": len(pairs), "mean_diff": round(float(diff.mean()), 4),
                                  "diff_ci": ci(diff, rng), "wins": int((diff > 0).sum()), "ties": int((diff == 0).sum()),
                                  "losses": int((diff < 0).sum()), "p_value": p})
        ranked = sorted((t for t in tests if t["p_value"] is not None), key=lambda t: t["p_value"])
        running = 0.0
        for i, t in enumerate(ranked):   # Holm correction
            running = max(running, min(1.0, (len(ranked) - i) * t["p_value"]))
            t["p_holm"] = running

        judge = [(x["judge_accuracy"], x["token_f1"]) for x in mine if x["judge_accuracy"] is not None]
        agreement = None
        if len(judge) >= 10 and len({j[0] for j in judge}) > 1:
            agreement = round(float(spearmanr([j[0] for j in judge], [j[1] for j in judge]).statistic), 3)
        out["models"][model] = {"conditions": summary, "tests": tests, "judge_vs_token_f1_spearman": agreement}

        print(f"\n{model}")
        print(f"{'':<22}" + "".join(f"{c:>30}" for c in conds))
        for m, label in (("token_f1", "token F1"), ("ref_recall", "reference recall"), ("key_points", "key points covered")):
            print(f"{label:<22}" + "".join(f"{summary[c][m]:>10.3f} {str(summary[c][m + '_ci']):>19}" for c in conds))
        for t in tests:
            p = "n/a" if t["p_value"] is None else f"{t['p_holm']:.1e}"
            print(f"  {t['metric']:<10} {t['a']} vs {t['b']}: {t['mean_diff']:+.3f} {t['diff_ci']}  "
                  f"W/T/L {t['wins']}/{t['ties']}/{t['losses']}  p(Holm)={p}")
        print("  judge accuracy vs token F1 (Spearman):", agreement)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print("\nwrote", args.out)


if __name__ == "__main__":
    main()
