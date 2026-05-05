"""Sanity check: confirm dedup logic catches near-duplicates."""
from __future__ import annotations

from pathlib import Path

from db import find_similar, get_conn, normalize_text, shingles, site_id

REPO = Path("C:/Users/06123/GitHub/astrowind")


def main() -> None:
    conn = get_conn()
    sid = site_id(conn, "sleepupgradehub")

    sample = (REPO / "src" / "data" / "post" /
              "10-best-sleep-masks-of-2025-find-your-perfect-blac-728154.md").read_text(encoding="utf-8")

    print("=== Test 1: identical post should match itself with Jaccard 1.0 ===")
    matches = find_similar(conn, sid, sample, threshold=0.05)
    for j, slug, title in matches[:5]:
        print(f"  {j:.2f}  {slug}")

    fake_dup = sample + "\n\nExtra paragraph here. " * 50
    print("\n=== Test 2: 'fake_dup' (sample + 50 sentences) should still match the original ===")
    matches = find_similar(conn, sid, fake_dup, threshold=0.10)
    for j, slug, title in matches[:5]:
        print(f"  {j:.2f}  {slug}")

    print("\n=== Test 3: totally unrelated text should match nothing above 0.10 ===")
    novel = "The sea otter is a marine mammal native to the coasts of the Pacific Ocean. " * 100
    matches = find_similar(conn, sid, novel, threshold=0.10)
    print(f"  matches: {len(matches)} (expected 0)")

    print("\n=== DB stats ===")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE site_id = ?", (sid,)
    ).fetchone()["n"]
    print(f"  posts: {n}")
    sites = conn.execute("SELECT slug, niche, repo_path FROM sites").fetchall()
    for s in sites:
        print(f"  site: {s['slug']:20s} niche={s['niche']:10s} repo={s['repo_path']}")
    conn.close()


if __name__ == "__main__":
    main()
