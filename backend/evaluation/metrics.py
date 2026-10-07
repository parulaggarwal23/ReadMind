"""Retrieval metrics and LLM-as-judge answer metrics."""
from config import JUDGE_MODEL, JUDGE_PROVIDER
from rag.llm import generate, parse_json


def id_match(pred: str, gold: str) -> bool:
    if pred == gold:
        return True
    if pred.startswith("commit:") and gold.startswith("commit:"):
        return pred.startswith(gold) or gold.startswith(pred)
    return False


def retrieval_metrics(retrieved: list[str], gold: list[str], k: int) -> dict:
    if not gold:
        return {}
    top = retrieved[:k]
    hits = [r for r in top if any(id_match(r, g) for g in gold)]
    found = sum(1 for g in gold if any(id_match(r, g) for r in top))
    mrr = 0.0
    for rank, r in enumerate(retrieved, 1):
        if any(id_match(r, g) for g in gold):
            mrr = 1.0 / rank
            break
    return {"precision_at_k": len(hits) / len(top) if top else 0.0,
            "recall_at_k": found / len(gold), "mrr": mrr}


JUDGE_SYSTEM = """You are a strict grader in a study on software-engineering question answering.
Compare a CANDIDATE answer with the REFERENCE answer and the GOLD evidence from the repository.
Return ONLY JSON with these keys:
- "accuracy": 1-5 (5 = fully correct explanation matching the reference; 3 = partly correct; 1 = wrong or no answer)
- "relevance": 1-5 (does it address the question that was asked?)
- "key_points_covered": list of true/false, one per key point, in order
- "claims_total": number of distinct factual claims the candidate makes about this repository or its history
- "claims_unsupported": how many of those claims are contradicted by, or not supported by, the reference or gold evidence
- "rationale": one sentence
Statements of uncertainty ("I am not sure", "the evidence does not explain this") are NOT claims.
Citation markers like [commit:abc] are not claims by themselves."""


def judge_answer(item: dict, answer: str, gold_texts: list[str]) -> dict:
    kp = item.get("key_points", [])
    prompt = (f"QUESTION:\n{item['question']}\n\nREFERENCE ANSWER:\n{item['reference_answer']}\n\n"
              f"KEY POINTS:\n" + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(kp)) +
              "\n\nGOLD EVIDENCE:\n" + "\n---\n".join(t[:1200] for t in gold_texts) +
              f"\n\nCANDIDATE ANSWER:\n{answer}")
    data = parse_json(generate(JUDGE_SYSTEM, prompt, provider=JUDGE_PROVIDER, model=JUDGE_MODEL, json_mode=True))
    covered = [bool(x) for x in data.get("key_points_covered", [])][: len(kp)]
    total = int(data.get("claims_total", 0) or 0)
    unsupported = min(int(data.get("claims_unsupported", 0) or 0), total)
    return {
        "accuracy": float(data.get("accuracy", 1)),
        "relevance": float(data.get("relevance", 1)),
        "completeness": (sum(covered) / len(kp)) if kp else None,
        "claims_total": total,
        "claims_unsupported": unsupported,
        "hallucination_rate": (unsupported / total) if total else 0.0,
        "judge_rationale": data.get("rationale", ""),
    }
