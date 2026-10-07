"""Draft benchmark questions from real history (issue ↔ PR ↔ commit chains).

    python -m evaluation.generate_questions --repo owner__name --n 40

Writes data/eval/candidates_<slug>.jsonl. EVERY candidate must be checked by a person:
fix the question/answer, set "verified": true, then append it to data/eval/benchmark.jsonl."""
import argparse
import json
import random

from config import EVAL_DIR
from rag.llm import generate, parse_json
from rag.retriever import get_index

CATEGORIES = ["rationale", "provenance", "bug_history", "rejected_alternative", "change_impact"]

SYSTEM = """You create evaluation questions for a study on answering developer questions from repository history.
You get a linked chain of repository evidence (issue, pull request, commits, review comments).
Write ONE question a developer might ask while looking at the CURRENT code, whose correct answer is only knowable
from this history. Refer to code (function, file, behaviour), NOT to issue/PR numbers, in the question.
Return JSON: {"question": str, "category": one of %s, "reference_answer": str (2-4 sentences, factual, from the evidence),
"key_points": [2-4 short facts a complete answer must contain]}""" % CATEGORIES


def chains(index, min_body=150):
    """Yield (anchor_id, [evidence ids]) for PRs/commits that link to an issue or have a rich PR description."""
    G, docs = index.graph, index.docs
    for node in index.ids:
        t = docs[node]["type"]
        if t not in ("pr", "commit"):
            continue
        nbrs = [n for n in set(G.successors(node)) | set(G.predecessors(node)) if n in docs]
        issues = [n for n in nbrs if docs[n]["type"] == "issue"]
        if t == "pr":
            if not issues and len(docs[node]["text"]) < min_body * 3:
                continue
            commits = [n for n in nbrs if docs[n]["type"] == "commit"][:2]
            reviews = [n for n in nbrs if docs[n]["type"] == "review"][:2]
            yield node, [node] + issues[:1] + commits + reviews
        elif issues and len(docs[issues[0]]["text"]) > min_body:
            yield node, [node] + issues[:1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    index = get_index(args.repo)
    pool = list(chains(index))
    random.Random(args.seed).shuffle(pool)
    out_path = EVAL_DIR / f"candidates_{args.repo}.jsonl"
    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for anchor, ids in pool:
            if written >= args.n:
                break
            context = "\n\n---\n\n".join(f"[{i}]\n{index.docs[i]['text'][:2500]}" for i in ids)
            try:
                q = parse_json(generate(SYSTEM, context, json_mode=True, temperature=0.3))
            except Exception as e:
                print("skip", anchor, e)
                continue
            if not q.get("question"):
                continue
            item = {"id": f"{args.repo}-{written + 1:03d}", "repo": args.repo, "question": q["question"],
                    "category": q.get("category", "rationale"), "reference_answer": q.get("reference_answer", ""),
                    "key_points": q.get("key_points", []), "gold_evidence": ids, "verified": False}
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            written += 1
    print(f"wrote {written} candidates to {out_path} — verify them manually before use")


if __name__ == "__main__":
    main()
