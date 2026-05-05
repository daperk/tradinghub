"""Import the 89 existing posts into the SQLite DB with content hashes + shingles."""
from __future__ import annotations

import json
import re
from pathlib import Path

from db import content_hash, get_conn, init, shingles, site_id

REPO = Path("C:/Users/06123/GitHub/astrowind")
SITE_SLUG = "sleepupgradehub"


def parse_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm: dict[str, str] = {}
    current_key = None
    list_collect: list[str] = []
    for line in m.group(1).splitlines():
        if line.startswith("  - "):
            list_collect.append(line.strip()[2:].strip().strip('"').strip("'"))
            continue
        if current_key and list_collect:
            fm[current_key] = json.dumps(list_collect)
            list_collect = []
            current_key = None
        if ":" in line:
            k, _, v = line.partition(":")
            v = v.strip().strip('"').strip("'")
            if v == "":
                current_key = k.strip()
                continue
            fm[k.strip()] = v
    if current_key and list_collect:
        fm[current_key] = json.dumps(list_collect)
    return fm


def main() -> None:
    init()
    conn = get_conn()
    sid = site_id(conn, SITE_SLUG)

    posts = sorted((REPO / "src" / "data" / "post").glob("*.md"))
    n_imported = 0
    errors: list[str] = []

    for p in posts:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{p.name}: read failed → {e}")
            continue

        fm = parse_frontmatter(text)
        slug = p.stem
        ch = content_hash(text)
        sh = shingles(text)
        url = f"https://sleepupgradehub.com/{slug}"

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO posts
                  (site_id, slug, title, excerpt, category, tags,
                   published_at, url, content_hash, shingle_json,
                   image_path, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    slug,
                    fm.get("title", slug),
                    fm.get("excerpt", ""),
                    fm.get("category", ""),
                    fm.get("tags", "[]"),
                    fm.get("publishDate", ""),
                    url,
                    ch,
                    json.dumps(list(sh)),
                    fm.get("image", ""),
                    "published",
                ),
            )
            n_imported += 1
        except Exception as e:
            errors.append(f"{p.name}: insert failed → {e}")

    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE site_id = ?", (sid,)
    ).fetchone()["n"]
    dup_hashes = conn.execute(
        "SELECT content_hash, COUNT(*) AS n FROM posts "
        "WHERE site_id = ? GROUP BY content_hash HAVING n > 1",
        (sid,),
    ).fetchall()

    print(f"[import] {n_imported} posts imported / {len(posts)} files")
    print(f"[import] DB total for {SITE_SLUG}: {total}")
    if dup_hashes:
        print(f"[import] WARNING duplicate content_hash groups: {len(dup_hashes)}")
    if errors:
        print(f"[import] {len(errors)} errors:")
        for e in errors[:10]:
            print("  -", e)
    conn.close()


if __name__ == "__main__":
    main()
