"""Batch: pull top N keywords from DB queue, generate + publish posts.

Usage:
  python scripts/batch.py --site sleepupgradehub --count 5
  python scripts/batch.py --site sleepupgradehub --count 5 --no-deploy
"""
from __future__ import annotations

import _env  # noqa: F401

import argparse
import sys
import time

from db import get_conn, site_id
from pipeline import run as run_pipeline


def pop_top_keyword(conn, sid: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, keyword, type, category
        FROM keywords
        WHERE site_id = ? AND status = 'new'
        ORDER BY score DESC, RANDOM()
        LIMIT 1
        """,
        (sid,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def mark_status(conn, kw_id: int, status: str) -> None:
    conn.execute(
        "UPDATE keywords SET status = ? WHERE id = ?", (status, kw_id),
    )
    conn.commit()


def run_batch(site_slug: str, count: int, *,
              no_image: bool = False, no_deploy: bool = False,
              delay_seconds: float = 5.0) -> int:
    conn = get_conn()
    sid = site_id(conn, site_slug)

    written = 0
    blocked = 0
    failed = 0

    for i in range(count):
        kw = pop_top_keyword(conn, sid)
        if not kw:
            print(f"[batch] queue empty after {i} posts")
            break
        print(f"\n[batch] {i+1}/{count} → {kw['keyword']!r}")
        try:
            rc = run_pipeline(
                site_slug, kw["keyword"],
                dry_run=False, no_image=no_image, no_deploy=no_deploy,
            )
            if rc == 0:
                written += 1
            else:
                mark_status(conn, kw["id"], "rejected")
                blocked += 1
        except Exception as e:
            print(f"[batch] error: {e}")
            mark_status(conn, kw["id"], "failed")
            failed += 1

        if i < count - 1:
            time.sleep(delay_seconds)

    print(f"\n[batch] done — written={written} blocked/duplicate={blocked} failed={failed}")
    return 0 if written > 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--no-image", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--delay", type=float, default=5.0,
                    help="seconds between posts (Pexels 200/h, Anthropic limits)")
    args = ap.parse_args()
    sys.exit(run_batch(
        args.site, args.count,
        no_image=args.no_image, no_deploy=args.no_deploy,
        delay_seconds=args.delay,
    ))


if __name__ == "__main__":
    main()
