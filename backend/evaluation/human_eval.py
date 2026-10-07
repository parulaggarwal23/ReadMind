"""Blind human evaluation.

1) Export a blinded sheet (condition names hidden, order shuffled):
       python -m evaluation.human_eval export --n 40
   -> data/eval/human_sheet.csv  (give a copy to each rater)
   -> data/eval/human_key.json   (keep secret until scoring)

2) Each rater fills `accuracy` and `usefulness` (1-5) and saves e.g. rater1.csv, rater2.csv.

3) Score:
       python -m evaluation.human_eval score data/eval/rater1.csv data/eval/rater2.csv
   -> data/eval/human_summary.json (mean ratings per condition + Cohen's weighted kappa)"""
import argparse
import json
import random

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from config import EVAL_DIR


def export(n, seed):
    df = pd.read_json(EVAL_DIR / "results.jsonl", lines=True)
    qids = sorted(df["qid"].unique())
    rng = random.Random(seed)
    sample = rng.sample(qids, min(n, len(qids)))
    rows, key = [], {}
    for qid in sample:
        sub = df[df["qid"] == qid].sample(frac=1, random_state=rng.randint(0, 10_000))
        for _, r in sub.iterrows():
            item_id = f"H{len(rows) + 1:04d}"
            key[item_id] = {"qid": qid, "condition": r["condition"]}
            rows.append({"item_id": item_id, "question": r["question"], "answer": r["answer"],
                         "accuracy": "", "usefulness": "", "notes": ""})
    pd.DataFrame(rows).to_csv(EVAL_DIR / "human_sheet.csv", index=False)
    (EVAL_DIR / "human_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"exported {len(rows)} answers for {len(sample)} questions")


def score(files):
    key = json.loads((EVAL_DIR / "human_key.json").read_text(encoding="utf-8"))
    raters = [pd.read_csv(f).dropna(subset=["accuracy"]) for f in files]
    long = []
    for i, df in enumerate(raters):
        for _, r in df.iterrows():
            long.append({"rater": i, "item_id": r["item_id"], "condition": key[r["item_id"]]["condition"],
                         "accuracy": float(r["accuracy"]), "usefulness": float(r.get("usefulness") or 0)})
    long = pd.DataFrame(long)
    out = {"n_raters": len(raters), "conditions": {}}
    for cond, g in long.groupby("condition"):
        out["conditions"][cond] = {"accuracy": round(g["accuracy"].mean(), 3),
                                   "usefulness": round(g["usefulness"].mean(), 3), "n": len(g)}
    if len(raters) >= 2:
        merged = raters[0].merge(raters[1], on="item_id", suffixes=("_1", "_2"))
        out["kappa_accuracy"] = round(cohen_kappa_score(merged["accuracy_1"].astype(int),
                                                        merged["accuracy_2"].astype(int), weights="quadratic"), 3)
    (EVAL_DIR / "human_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--n", type=int, default=40)
    e.add_argument("--seed", type=int, default=7)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    args = ap.parse_args()
    export(args.n, args.seed) if args.cmd == "export" else score(args.files)


if __name__ == "__main__":
    main()
