"""End-to-end pipeline: keyword -> Claude post -> Pexels image -> file -> git -> deploy.

Usage:
  python scripts/pipeline.py --site sleepupgradehub --keyword "best sleep gummies 2025"
  python scripts/pipeline.py --site sleepupgradehub --keyword "..." --dry-run
  python scripts/pipeline.py --site sleepupgradehub --keyword "..." --no-image
  python scripts/pipeline.py --site sleepupgradehub --keyword "..." --no-deploy
"""
from __future__ import annotations

import _env  # noqa: F401

import argparse
import os
import sys
from pathlib import Path

from db import get_conn, site_id
from generate_post import generate
from niches import NICHES
from pexels_client import acquire_image, PexelsError
from publish import (git_commit_push, ping_indexnow, register_in_db,
                     trigger_vercel, write_post_file)


def _niche_for_site(site_slug: str) -> tuple[str, dict]:
    for key, cfg in NICHES.items():
        if cfg["site_slug"] == site_slug:
            return key, cfg
    raise ValueError(f"no niche config for site {site_slug}")


def _category_for_keyword(keyword: str, niche_cfg: dict) -> str:
    kw = keyword.lower()
    cats = niche_cfg["categories"]
    if any(t in kw for t in ("tracker", "oura", "whoop", "garmin", "fitbit", "apple watch")):
        return next((c for c in cats if "Tracker" in c), cats[0])
    if any(t in kw for t in (
            "supplement", "magnesium", "melatonin", "gumm", "vitamin",
            "valerian", "ashwagandha", "theanine", "glycine", "tea")):
        return next((c for c in cats if c == "Supplements"), cats[0])
    if any(t in kw for t in ("mask", "pillow", "blanket", "earbud", "earplug")):
        return next((c for c in cats if "Tools" in c), cats[0])
    if any(t in kw for t in ("noise", "sound machine", "hatch", "white noise")):
        return next((c for c in cats if "Noise" in c), None) or \
               next((c for c in cats if "Tools" in c), cats[0])
    if any(t in kw for t in ("mattress", "bedroom", "temperature", "cooling", "eight sleep")):
        return next((c for c in cats if "Environment" in c), None) or \
               next((c for c in cats if "Tools" in c), cats[0])
    if any(t in kw for t in ("how to", "habit", "routine", "schedule", "rem ", "deep sleep", "circadian")):
        return next((c for c in cats if c == "Habits"), cats[0])
    return next((c for c in cats if c == "Habits"), cats[0])


def run(site_slug: str, keyword: str, *,
        dry_run: bool = False, no_image: bool = False,
        no_deploy: bool = False) -> int:
    niche_key, niche_cfg = _niche_for_site(site_slug)
    category = _category_for_keyword(keyword, niche_cfg)

    conn = get_conn()
    sid = site_id(conn, site_slug)
    repo_row = conn.execute(
        "SELECT repo_path FROM sites WHERE id = ?", (sid,)
    ).fetchone()
    repo = Path(repo_row["repo_path"]) if repo_row["repo_path"] else None
    if not repo:
        print(f"[pipeline] site {site_slug} has no repo_path set")
        return 2

    print(f"[pipeline] site={site_slug} niche={niche_key} keyword='{keyword}' category={category}")

    if dry_run:
        generate(conn, sid, niche_key, keyword, category,
                 type_="informational", dry_run=True)
        print("[pipeline] dry-run complete (no API calls, no writes)")
        return 0

    print("[pipeline] generating post...")
    post = generate(conn, sid, niche_key, keyword, category,
                    type_="informational", dry_run=False)
    if not post:
        print("[pipeline] generation blocked or failed")
        return 1
    post["keyword"] = keyword
    print(f"[pipeline] generated: {post['title']}")
    print(f"[pipeline] body length: {len(post['body'])} chars")

    image_rel: str | None = None
    image_path: str | None = None
    image_hash: str | None = None

    if not no_image and os.environ.get("PEXELS_API_KEY"):
        blog_dir = repo / "src" / "assets" / "images" / "blog"
        try:
            img_query = niche_cfg["image_query_template"].format(keyword=keyword)
            img = acquire_image(conn, sid, post["slug"], img_query,
                                blog_dir, niche_cfg["image_fallback_queries"])
            if img:
                image_rel = f"~/assets/images/blog/{post['slug']}.jpg"
                image_path = img["path"]
                image_hash = img["hash"]
                print(f"[pipeline] image: pexels#{img['pexels_id']} -> {image_rel}")
        except PexelsError as e:
            print(f"[pipeline] pexels failed: {e}")
    elif not no_image:
        print("[pipeline] PEXELS_API_KEY not set — post will have no image")

    dest = write_post_file(repo, post, image_rel)
    print(f"[pipeline] wrote {dest.relative_to(repo)}")

    register_in_db(conn, site_slug, post, image_path, image_hash)
    print(f"[pipeline] registered in DB")

    if no_deploy:
        print("[pipeline] --no-deploy set; skipping git push + Vercel hook")
        return 0

    pushed = git_commit_push(repo, f"Add post: {post['title']}")
    if pushed:
        site_row = conn.execute(
            "SELECT domain FROM sites WHERE id = ?", (sid,)
        ).fetchone()
        url = f"https://{site_row['domain']}/{post['slug']}"
        env_var = f"VERCEL_HOOK_{site_slug.upper()}"
        trigger_vercel(env_var)
        ping_indexnow(url)

    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True,
                    help="site slug (sleepupgradehub|tradinghub|aitoolsedge|codestackhub)")
    ap.add_argument("--keyword", required=True, help="target keyword")
    ap.add_argument("--dry-run", action="store_true",
                    help="print prompt only, no API calls")
    ap.add_argument("--no-image", action="store_true",
                    help="skip Pexels image fetch")
    ap.add_argument("--no-deploy", action="store_true",
                    help="skip git push + Vercel deploy hook")
    args = ap.parse_args()
    sys.exit(run(args.site, args.keyword,
                 dry_run=args.dry_run, no_image=args.no_image,
                 no_deploy=args.no_deploy))


if __name__ == "__main__":
    main()
