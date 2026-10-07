from rag.citations import extract_citations, split_claims, verify_citations


def test_extract_multiple_ids_in_one_bracket():
    text = "It was changed after a bug [issue:12, commit:abcdef1234]. See also [pr:7]."
    assert extract_citations(text) == ["issue:12", "commit:abcdef1234", "pr:7"]


def test_ignores_non_id_brackets():
    assert extract_citations("Use list[int] and [optional] args.") == []


def test_short_commit_hash_is_valid():
    v = verify_citations("The retry loop was added to fix timeouts in production [commit:abcdef1].",
                         ["commit:abcdef1234", "issue:3"])
    assert v["valid"] == ["commit:abcdef1"] and v["invalid"] == []


def test_fabricated_citation_detected():
    v = verify_citations("This was introduced to fix a security problem reported by users [issue:999].",
                         ["issue:3"])
    assert v["invalid"] == ["issue:999"]
    assert v["citation_precision"] == 0.0


def test_uncited_claims_counted():
    answer = ("The authentication code uses signed cookies for sessions [pr:4]. "
              "It also stores refresh tokens in the database for thirty days.")
    v = verify_citations(answer, ["pr:4"])
    assert v["total_claims"] == 2 and v["uncited_claims"] == 1 and v["grounded_ratio"] == 0.5


def test_citation_after_full_stop_is_attached_to_previous_sentence():
    claims = split_claims("The cache was removed because it leaked memory. [issue:5] Next sentence here.")
    assert claims[0].endswith("[issue:5]")
