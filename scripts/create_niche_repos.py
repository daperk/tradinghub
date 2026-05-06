"""Create 3 empty GitHub repos via REST API, then init + push each scaffold.

Requires GITHUB_TOKEN in .env with `repo` scope.
Idempotent: skips repo creation if already exists, skips push if up-to-date.

Usage:
  python scripts/create_niche_repos.py
  python scripts/create_niche_repos.py --private
"""
from __future__ import annotations

import _env  # noqa: F401

import argparse
import os
import subprocess
import sys
from pathlib import Path

import requests

OWNER = os.environ.get("GITHUB_OWNER", "daperk")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
NICHES = ["tradinghub", "aitoolsedge", "codestackhub"]
BASE = Path("C:/Users/06123/GitHub")


def repo_exists(slug: str) -> bool:
    r = requests.get(
        f"https://api.github.com/repos/{OWNER}/{slug}",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    return r.status_code == 200


def create_repo(slug: str, private: bool) -> bool:
    payload = {
        "name": slug,
        "private": private,
        "description": f"Niche affiliate site — {slug}",
        "auto_init": False,
    }
    r = requests.post(
        "https://api.github.com/user/repos",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json"},
        json=payload,
        timeout=15,
    )
    if r.status_code == 201:
        print(f"  created github.com/{OWNER}/{slug}")
        return True
    print(f"  create failed ({r.status_code}): {r.text[:200]}")
    return False


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr).strip()


def init_and_push(slug: str) -> bool:
    dir_ = BASE / slug
    if not dir_.exists():
        print(f"  skip: {dir_} does not exist")
        return False

    if not (dir_ / ".git").exists():
        run(["git", "init", "-b", "main"], dir_)
        run(["git", "add", "."], dir_)
        run(["git", "commit", "-m", "Initial scaffold from astrowind template"], dir_)

    remote = f"https://github.com/{OWNER}/{slug}.git"
    rc, _ = run(["git", "remote", "get-url", "origin"], dir_)
    if rc != 0:
        run(["git", "remote", "add", "origin", remote], dir_)
    else:
        run(["git", "remote", "set-url", "origin", remote], dir_)

    rc, out = run(["git", "push", "-u", "origin", "main"], dir_)
    if rc != 0:
        print(f"  push failed:\n{out}")
        return False
    print(f"  pushed -> {remote}")
    return True


def update_sites_table() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from db import get_conn
    conn = get_conn()
    for slug in NICHES:
        conn.execute(
            "UPDATE sites SET repo_path = ? WHERE slug = ?",
            (str(BASE / slug).replace("\\", "/"), slug),
        )
    conn.commit()
    print("[db] sites.repo_path updated for all 3 niches")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", action="store_true",
                    help="create as private (default: public)")
    args = ap.parse_args()

    if not TOKEN:
        print("ERROR: GITHUB_TOKEN missing from .env")
        print("Create one at https://github.com/settings/tokens (classic, scope: repo)")
        return 1

    for slug in NICHES:
        print(f"\n=== {slug} ===")
        if repo_exists(slug):
            print(f"  github.com/{OWNER}/{slug} already exists, skipping create")
        else:
            if not create_repo(slug, args.private):
                continue
        init_and_push(slug)

    update_sites_table()
    print("\n=== done ===")
    print("Next: vercel.com/new -> import each repo (auto-detects Astro).")
    print("Add each Deploy Hook URL to astrowind/.env as VERCEL_HOOK_<SLUG>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
