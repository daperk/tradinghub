"""For each topic cluster, designate the longest post as 'pillar' and add
metadata.canonical to the others, pointing back to the pillar.

This protects against Google Helpful Content Update keyword cannibalization
without deleting any posts. Idempotent — safe to re-run.

Usage:
  python scripts/apply_canonicals.py --site sleepupgradehub --dry-run
  python scripts/apply_canonicals.py --site sleepupgradehub --apply
"""
from __future__ import annotations

import _env  # noqa: F401

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from db import get_conn, site_id
from niches import NICHES

CLUSTER_RULES: dict[str, callable] = {
    "sleep-masks": lambda t: "sleep mask" in t,
    "adult-pillows": lambda t: "pillow" in t and "adult" in t,
    "magnesium": lambda t: "magnesium" in t,
    "cooling-mattress": lambda t: "cooling" in t and "mattress" in t,
    "deep-sleep-techniques": lambda t: "deep sleep" in t and "best" not in t and "apple" not in t,
    "cooling-other": lambda t: ("cooling" in t and "mattress" not in t),
    "sleep-trackers-regional": lambda t: "sleep tracker" in t and ("india" in t or "android" in t or "2024" in t),
    "oura-vs-apple": lambda t: "oura" in t and "apple watch" in t,
}


def find_clusters(conn, sid: int) -> dict[str, list[dict]]:
    rows = conn.execute(
        "SELECT slug, title, url FROM posts WHERE site_id = ?", (sid,),
    ).fetchall()
    clusters: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        title = (r["title"] or "").lower()
        for cluster_name, predicate in CLUSTER_RULES.items():
            if predicate(title):
                clusters[cluster_name].append(dict(r))
                break
    return {k: v for k, v in clusters.items() if len(v) >= 2}


def pick_pillar(cluster: list[dict], post_dir: Path,
                official_pillars: set[str]) -> dict:
    """Prefer official pillar posts; otherwise pick longest body."""
    for p in cluster:
        if p["slug"] in official_pillars:
            return p
    best = None
    best_len = -1
    for p in cluster:
        path = post_dir / f"{p['slug']}.md"
        if not path.exists():
            continue
        n = len(path.read_text(encoding="utf-8"))
        if n > best_len:
            best_len = n
            best = p
    return best or cluster[0]


def has_canonical(text: str) -> bool:
    return bool(re.search(r"^\s*canonical:\s*", text, re.M))


def add_canonical(text: str, canonical_url: str) -> str:
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not fm_match:
        return text
    fm_body = fm_match.group(1)

    if "metadata:" in fm_body:
        new_fm = re.sub(
            r"(metadata:\s*\n)",
            f"\\1  canonical: {canonical_url}\n",
            fm_body,
            count=1,
        )
    else:
        new_fm = fm_body + f"\nmetadata:\n  canonical: {canonical_url}"

    return f"---\n{new_fm}\n---\n" + text[fm_match.end():]


def apply(site_slug: str, dry_run: bool = True) -> int:
    conn = get_conn()
    sid = site_id(conn, site_slug)
    repo_row = conn.execute(
        "SELECT repo_path FROM sites WHERE id = ?", (sid,),
    ).fetchone()
    if not repo_row or not repo_row["repo_path"]:
        print(f"[canonicals] no repo path for site {site_slug}")
        return 1
    post_dir = Path(repo_row["repo_path"]) / "src" / "data" / "post"

    niche_cfg = next(
        (c for c in NICHES.values() if c["site_slug"] == site_slug), None
    )
    official_pillars: set[str] = set()
    if niche_cfg:
        for url, _ in niche_cfg.get("pillar_posts", []):
            official_pillars.add(url.lstrip("/"))

    clusters = find_clusters(conn, sid)
    if not clusters:
        print("[canonicals] no clusters found")
        return 0

    print(f"[canonicals] {len(clusters)} clusters identified:")
    changes_planned = 0
    changes_applied = 0

    for name, posts in clusters.items():
        pillar = pick_pillar(posts, post_dir, official_pillars)
        canonical_url = pillar["url"]
        non_pillars = [p for p in posts if p["slug"] != pillar["slug"]]

        print(f"\n  {name} ({len(posts)} posts)")
        print(f"    pillar: {pillar['slug']}")

        for p in non_pillars:
            path = post_dir / f"{p['slug']}.md"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if has_canonical(text):
                print(f"    skip   (already has canonical): {p['slug']}")
                continue
            changes_planned += 1
            print(f"    {'WOULD ADD' if dry_run else 'add'} canonical: {p['slug']}")
            if not dry_run:
                new_text = add_canonical(text, canonical_url)
                path.write_text(new_text, encoding="utf-8")
                conn.execute(
                    "UPDATE posts SET canonical_of = ? "
                    "WHERE site_id = ? AND slug = ?",
                    (pillar["slug"], sid, p["slug"]),
                )
                changes_applied += 1

    conn.commit()
    print(f"\n[canonicals] {'planned' if dry_run else 'applied'}: "
          f"{changes_planned if dry_run else changes_applied} changes "
          f"across {len(clusters)} clusters")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.exit(apply(args.site, dry_run=not args.apply))


if __name__ == "__main__":
    main()
