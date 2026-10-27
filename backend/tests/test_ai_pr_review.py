"""Tests for devops/ai_pr_review.py using a throwaway git repository.

Seed tests (hand-written); Qodo Cover appends AI-generated tests (scripts/generate_tests.sh)."""
import subprocess

import pytest

from devops.ai_pr_review import build_evidence, changed_files, format_prompt, offline_review, render_comment


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    (tmp_path / "auth.py").write_text("def login():\n    pass\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "Add login (fixes #5)")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "auth.py").write_text("def login():\n    rotate_session()\n")
    (tmp_path / "new.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "Rotate session on login")
    return str(tmp_path)


def test_changed_files_and_history(repo):
    files = changed_files("main", "feature", repo)
    assert files == ["auth.py", "new.py"]
    ev = build_evidence(files, "main", repo)
    assert len(ev) == 1 and ev[0]["paths"] == ["auth.py"]
    assert ev[0]["id"].startswith("commit:") and len(ev[0]["id"]) == len("commit:") + 10


def test_offline_review_cites_real_history(repo):
    files = changed_files("main", "feature", repo)
    ev = build_evidence(files, "main", repo)
    text = offline_review(files, ev)
    assert f"[{ev[0]['id']}]" in text and "new.py" in text


def test_prompt_contains_history_and_diff(repo):
    ev = build_evidence(["auth.py"], "main", repo)
    prompt = format_prompt("+ rotate_session()", ev, "Rotate")
    assert ev[0]["id"] in prompt and "rotate_session" in prompt


def test_render_comment_reports_citation_check():
    result = {"text": "ok [commit:abc1234567]", "files": ["a.py"], "evidence": [], "model": "mock:x",
              "verification": {"cited": ["commit:abc1234567"], "valid": [], "invalid": ["commit:abc1234567"]}}
    body = render_comment(result)
    assert body.startswith("<!-- readmind-ai-review -->")
    assert "unverified" in body and "mock" in body
