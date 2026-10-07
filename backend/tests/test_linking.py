from ingestion.link_graph import build_graph, linked, parse_refs


def test_parse_refs_keywords_and_other_repos():
    refs = dict(parse_refs("Fixes #12, see #13 and other/lib#99 and https://github.com/me/app/issues/20", "me", "app"))
    assert refs == {12: "fixes", 13: "mentions", 20: "mentions"}


def test_graph_links_code_to_issue_through_commit():
    commits = [{"sha": "a" * 40, "message": "Rotate session id on login (fixes #5)", "date": "2023-01-02T00:00:00",
                "files": [{"path": "auth/session.py"}]}]
    issues = [{"number": 5, "created_at": "2023-01-01T00:00:00", "body": "Session fixation", "comments": []}]
    prs = [{"number": 6, "created_at": "2023-01-02", "merged_at": "2023-01-03", "title": "Rotate ids", "body": "Closes #5",
            "commits": ["a" * 40], "merge_commit_sha": None, "files": ["auth/session.py"], "discussion": [],
            "review_comments": [{"id": 77, "date": "2023-01-02", "path": "auth/session.py"}], "reviews": []}]
    code = [{"id": "code:auth/session.py:1-20", "path": "auth/session.py"}]
    G = build_graph(commits, issues, prs, code, "me", "app")
    assert G.edges["commit:aaaaaaaaaa", "issue:5"]["rel"] == "fixes"
    assert G.edges["pr:6", "issue:5"]["rel"] == "fixes"
    found = set(linked(G, "code:auth/session.py:1-20", {"commit", "issue", "pr", "review"}))
    assert {"commit:aaaaaaaaaa", "issue:5", "pr:6", "review:77"} <= found
