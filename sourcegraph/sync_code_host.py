"""Keep Sourcegraph's GitHub code host in sync with ReadMind's backend/repos.yaml.

    python sourcegraph/sync_code_host.py            # print the code-host JSON (paste into Sourcegraph)
    python sourcegraph/sync_code_host.py --apply    # create it through the Sourcegraph GraphQL API

Reads GITHUB_TOKEN, SOURCEGRAPH_URL and SOURCEGRAPH_TOKEN from .env (same file the backend uses).
ReadMind itself is always included so its own code is searchable and SCIP uploads have a target repo.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SELF_REPO = os.getenv("READMIND_GITHUB_REPO", "parulaggarwal23/ReadMind")


def repos_from_yaml(path: Path) -> list[str]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = [SELF_REPO]
    for entry in cfg.get("repos", []):
        gh = (entry.get("github") if isinstance(entry, dict) else str(entry)).strip()
        if "/" in gh and "OWNER" not in gh and gh not in out:
            out.append(gh)
    return out


def code_host_config(repos: list[str], token: str) -> dict:
    return {"url": "https://github.com", "token": token or "<YOUR_GITHUB_TOKEN>", "repos": repos}


ADD_GQL = """
mutation AddGitHub($input: AddExternalServiceInput!) {
  addExternalService(input: $input) { id displayName }
}
"""


def apply(config: dict) -> None:
    url = os.getenv("SOURCEGRAPH_URL", "http://localhost:7080").rstrip("/")
    token = os.getenv("SOURCEGRAPH_TOKEN", "")
    if not token:
        sys.exit("SOURCEGRAPH_TOKEN is not set in .env (Sourcegraph → Settings → Access tokens)")
    if config["token"].startswith("<"):
        sys.exit("GITHUB_TOKEN is not set in .env")
    body = {"query": ADD_GQL, "variables": {"input": {
        "kind": "GITHUB", "displayName": "GitHub (ReadMind repos)", "config": json.dumps(config)}}}
    r = requests.post(f"{url}/.api/graphql", json=body, headers={"Authorization": f"token {token}"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        sys.exit("Sourcegraph: " + "; ".join(e["message"] for e in data["errors"]))
    print("Created code host:", data["data"]["addExternalService"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-file", default=str(ROOT / "backend" / "repos.yaml"))
    ap.add_argument("--apply", action="store_true", help="create the code host via the GraphQL API")
    args = ap.parse_args()
    config = code_host_config(repos_from_yaml(Path(args.repos_file)), os.getenv("GITHUB_TOKEN", ""))
    if args.apply:
        apply(config)
    else:
        shown = {**config, "token": "<YOUR_GITHUB_TOKEN>"}  # never print the real token
        print(json.dumps(shown, indent=2))


if __name__ == "__main__":
    main()
