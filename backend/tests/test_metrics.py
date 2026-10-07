from evaluation.metrics import retrieval_metrics
from rag.text_utils import tokenize


def test_tokenize_splits_identifiers():
    toks = tokenize("refreshToken get_user_by_id")
    assert {"refresh", "token", "refreshtoken", "user", "id"} <= set(toks)


def test_retrieval_metrics():
    m = retrieval_metrics(["code:a", "issue:5", "commit:abcdef1234"], ["issue:5", "commit:abcdef1"], k=3)
    assert m["recall_at_k"] == 1.0
    assert abs(m["precision_at_k"] - 2 / 3) < 1e-9
    assert m["mrr"] == 0.5
