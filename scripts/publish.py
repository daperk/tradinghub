"""Write generated post to disk, register in DB, optionally git commit + deploy."""
from __future__ import annotations

import _env  # noqa: F401

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from db import get_conn, site_id


def _build_md(post: dict, image_rel: str | None, author: str = "Sleep Team") -> str:
    pub = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tags_yaml = "\n".join(f"  - \"{t}\"" for t in post["tags"])
    title_safe = post["title"].replace('"', '\\"')
    excerpt_safe = post["excerpt"].replace('"', '\\"')
    cat_safe = post["category"].replace('"', '\\"')
    image_line = f"image: {image_rel}\n" if image_rel else ""

    return (
        "---\n"
        f"publishDate: {pub}\n"
        f"author: \"{author}\"\n"
        f"title: \"{title_safe}\"\n"
        f"excerpt: \"{excerpt_safe}\"\n"
        f"{image_line}"
        f"category: \"{cat_safe}\"\n"
        "tags:\n"
        f"{tags_yaml}\n"
        "---\n\n"
        f"{post['body']}\n"
    )


def write_post_file(repo: Path, post: dict, image_rel: str | None,
                    author: str = "Sleep Team") -> Path:
    md = _build_md(post, image_rel, author)
    dest = repo / "src" / "data" / "post" / f"{post['slug']}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md, encoding="utf-8")
    return dest


def register_in_db(conn, site_slug: str, post: dict, image_path: str | None,
                   image_hash: str | None) -> None:
    sid = site_id(conn, site_slug)
    site = conn.execute("SELECT domain FROM sites WHERE id = ?", (sid,)).fetchone()
    url = f"https://{site['domain']}/{post['slug']}"

    conn.execute(
        """
        INSERT OR REPLACE INTO posts
          (site_id, slug, keyword, title, excerpt, category, tags, type,
           published_at, url, content_hash, shingle_json,
           image_path, image_hash, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            sid, post["slug"], post.get("keyword", ""),
            post["title"], post["excerpt"], post["category"],
            json.dumps(post["tags"]), post.get("type", "informational"),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            url, post["content_hash"],
            json.dumps(post["shingles"]),
            image_path, image_hash, "published",
        ),
    )

    conn.execute(
        "UPDATE keywords SET status = 'written' WHERE site_id = ? AND keyword = ?",
        (sid, post.get("keyword", "")),
    )
    conn.commit()


def git_commit_push(repo: Path, message: str, remote: str = "origin",
                    branch: str = "main") -> bool:
    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            args, cwd=repo, capture_output=True, text=True, timeout=120
        )

    status = run("git", "status", "--porcelain").stdout.strip()
    if not status:
        print("[git] no changes to commit")
        return False

    run("git", "add", "src/data/post", "src/assets/images/blog")
    res = run("git", "commit", "-m", message)
    if res.returncode != 0:
        print(f"[git] commit failed: {res.stderr}")
        return False
    push = run("git", "push", remote, branch)
    if push.returncode != 0:
        print(f"[git] push failed: {push.stderr}")
        return False
    print(f"[git] pushed: {message}")
    return True


def trigger_vercel(env_var: str = "VERCEL_HOOK_SLEEPUPGRADEHUB") -> bool:
    hook = os.environ.get(env_var, "")
    if not hook:
        print(f"[vercel] {env_var} not set, skipping deploy hook")
        return False
    r = requests.post(hook, timeout=15)
    if r.ok:
        print(f"[vercel] deploy triggered ({r.status_code})")
        return True
    print(f"[vercel] hook failed: {r.status_code} {r.text[:200]}")
    return False


def ping_indexnow(url: str) -> bool:
    key = os.environ.get("INDEXNOW_KEY", "")
    if not key:
        return False
    payload = {
        "host": url.split("://", 1)[1].split("/", 1)[0],
        "key": key,
        "urlList": [url],
    }
    try:
        r = requests.post("https://api.indexnow.org/indexnow",
                          json=payload, timeout=15)
        if r.ok:
            print(f"[indexnow] pinged {url}")
            return True
        print(f"[indexnow] {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[indexnow] error: {e}")
    return False
