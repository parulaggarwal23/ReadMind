"""Re-grade saved answers with a stronger judge, without re-running the models.

    set GEMINI_API_KEY=...            (Linux / Mac / Kaggle: export GEMINI_API_KEY=...)
    python evaluation/rejudge.py --results data/eval/results.jsonl --benchmark data/eval/benchmark.jsonl

Writes <results>_rejudged.jsonl with the same columns, where accuracy, relevance, completeness and
hallucination_rate come from the new judge. The old judge's accuracy is kept as accuracy_old_judge.
Then run the project's statistics on the new file.

Needs only `pip install google-genai`. No GPU, no index: the judge sees the question, the verified
reference answer, the key points and the answer. It is not told which condition or model produced
the answer. The run is resumable: start it again after a rate-limit stop and it continues."""
import argparse
import json
import os
import re
import time

SYSTEM = """You are a strict grader in a study on software-engineering question answering.
Compare a CANDIDATE answer with the REFERENCE answer, which was verified against the repository history.
Return ONLY JSON with these keys:
- "accuracy": 1-5 (5 = states the same specific reason as the reference; 3 = partly right or right but vague;
  1 = wrong, generic, or no answer). A fluent but generic answer that contains none of the reference's
  specific facts is 1 or 2, never higher.
- "relevance": 1-5 (does it address the question that was asked?)
- "key_points_covered": list of true/false, one per key point, in order
- "claims_total": number of distinct factual claims the candidate makes about this repository or its history
- "claims_unsupported": how many of those claims are contradicted by, or absent from, the reference and key points
- "rationale": one sentence
Statements of uncertainty are not claims. Ignore a leading sentence such as "The available evidence does not
explain this." if the candidate then goes on to answer; grade what follows. Citation markers like [commit:abc]
are not claims."""


def call_gemini(model, prompt):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.0,
                                           response_mime_type="application/json"))
    return resp.text or ""


def parse(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}


def grade(item, answer, call):
    kp = item.get("key_points", [])
    prompt = (f"QUESTION:\n{item['question']}\n\nREFERENCE ANSWER:\n{item['reference_answer']}\n\nKEY POINTS:\n"
              + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(kp)) + f"\n\nCANDIDATE ANSWER:\n{answer}")
    data = parse(call(prompt))
    if "accuracy" not in data:
        raise ValueError("judge returned no usable JSON")
    covered = [bool(x) for x in data.get("key_points_covered", [])][: len(kp)]
    total = int(data.get("claims_total", 0) or 0)
    unsupported = min(int(data.get("claims_unsupported", 0) or 0), total)
    return {"accuracy": min(5.0, max(1.0, float(data["accuracy"]))),
            "relevance": min(5.0, max(1.0, float(data.get("relevance", 1)))),
            "completeness": (sum(covered) / len(kp)) if kp else None,
            "claims_total": total, "claims_unsupported": unsupported,
            "hallucination_rate": (unsupported / total) if total else 0.0,
            "judge_rationale": data.get("rationale", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--out")
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--rpm", type=float, default=8, help="requests per minute (free tiers are rate-limited)")
    args = ap.parse_args()
    out_path = args.out or re.sub(r"\.jsonl$", "", args.results) + "_rejudged.jsonl"
    call = (lambda p: call_gemini(args.model, p))
    if os.environ.get("REJUDGE_FAKE"):   # offline self-test of the file handling only
        call = lambda p: json.dumps({"accuracy": 4, "relevance": 5, "key_points_covered": [True, False, True, True],
                                     "claims_total": 3, "claims_unsupported": 1, "rationale": "fake"})
    elif not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY first.")

    bench = {b["id"]: b for b in map(json.loads, open(args.benchmark, encoding="utf-8"))}
    rows = [json.loads(line) for line in open(args.results, encoding="utf-8") if line.strip()]
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["qid"], r.get("model"), r["condition"]))
    print(f"{len(rows)} answers, {len(done)} already graded, judge = {args.model}")

    failures = 0
    with open(out_path, "a", encoding="utf-8") as out:
        for i, r in enumerate(rows, 1):
            key = (r["qid"], r.get("model"), r["condition"])
            if key in done:
                continue
            new = None
            for attempt in range(4):
                try:
                    new = grade(bench[r["qid"]], r["answer"], call)
                    break
                except Exception as e:   # rate limit or malformed reply: wait and retry
                    wait = 20 * (attempt + 1)
                    print(f"  {r['qid']} [{r['condition']}] attempt {attempt + 1} failed: {str(e)[:100]} (waiting {wait}s)")
                    time.sleep(0 if os.environ.get("REJUDGE_FAKE") else wait)
            if new is None:
                failures += 1
                if failures >= 5:
                    raise SystemExit("Stopping after repeated failures (daily quota?). Run again later to resume.")
                continue
            row = {**r, "accuracy_old_judge": r.get("accuracy"), **new, "judge_model": args.model}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(rows)}")
            if not os.environ.get("REJUDGE_FAKE"):
                time.sleep(60.0 / args.rpm)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
