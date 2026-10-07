"""Run the benchmark under every condition, score it, and write the summary.

    python -m evaluation.run_eval                          # all conditions, verified questions
    python -m evaluation.run_eval --conditions full_history code_only --limit 20
    python -m evaluation.run_eval --no-judge               # retrieval + latency only (no judge cost)

Results are appended to data/eval/results.jsonl and the run resumes where it stopped."""
import argparse
import json

from tqdm import tqdm

from config import EVAL_DIR
from evaluation.metrics import judge_answer, retrieval_metrics
from evaluation.stats import summarize
from rag.pipeline import ALL_CONDITIONS, CONDITIONS, answer_question
from rag.retriever import get_index


def load_benchmark(path, include_unverified=False):
    items = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    return [i for i in items if include_unverified or i.get("verified")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default=str(EVAL_DIR / "benchmark.jsonl"))
    ap.add_argument("--out", default=str(EVAL_DIR / "results.jsonl"))
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(ALL_CONDITIONS))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--include-unverified", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()

    items = load_benchmark(args.benchmark, args.include_unverified)
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit("No (verified) questions found. See evaluation/benchmark.example.jsonl.")

    done = set()
    try:
        for line in open(args.out, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["qid"], r["condition"]))
    except FileNotFoundError:
        pass

    with open(args.out, "a", encoding="utf-8") as out:
        for item in tqdm(items, desc="questions"):
            index = get_index(item["repo"])
            gold = item.get("gold_evidence", [])
            gold_texts = [index.docs[g]["text"] for g in (index.resolve_id(x) for x in gold) if g]
            for cond in args.conditions:
                if (item["id"], cond) in done:
                    continue
                try:
                    res = answer_question(item["repo"], item["question"], cond, args.k)
                except Exception as e:
                    print(f"\n{item['id']} [{cond}] failed: {e}")
                    continue
                retrieved = [e["id"] for e in res["evidence"]]
                v = res["verification"]
                row = {
                    "qid": item["id"], "repo": item["repo"], "category": item.get("category"),
                    "condition": cond, "question": item["question"], "answer": res["answer"],
                    "retrieved": retrieved, "gold_evidence": gold,
                    "latency_total_ms": res["latency_ms"]["total"],
                    "latency_retrieval_ms": res["latency_ms"]["retrieval"],
                    "latency_generation_ms": res["latency_ms"]["generation"],
                    "citation_precision": v["citation_precision"], "grounded_ratio": v["grounded_ratio"],
                    "invalid_citations": len(v["invalid"]),
                }
                if res["evidence"]:
                    row.update(retrieval_metrics(retrieved, gold, args.k))
                if not args.no_judge:
                    try:
                        row.update(judge_answer(item, res["answer"], gold_texts))
                    except Exception as e:
                        print(f"\njudge failed for {item['id']} [{cond}]: {e}")
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()

    summary = summarize(args.out)
    print(json.dumps({c: {k: v for k, v in m.items() if k in ("accuracy", "completeness", "hallucination_rate",
                                                                "recall_at_k", "latency_p50_ms")}
                      for c, m in summary["conditions"].items()}, indent=2))


if __name__ == "__main__":
    main()
