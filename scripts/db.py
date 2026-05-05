"""SQLite layer for the SEO empire. Multi-site, anti-duplicate, fast."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seo-empire.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  domain TEXT NOT NULL,
  niche TEXT NOT NULL,
  repo_path TEXT,
  vercel_hook TEXT,
  posts_per_day INTEGER DEFAULT 3,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS keywords (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER NOT NULL REFERENCES sites(id),
  keyword TEXT NOT NULL,
  score INTEGER DEFAULT 5,
  type TEXT,
  category TEXT,
  source TEXT,
  status TEXT DEFAULT 'new',
  viral_potential TEXT DEFAULT 'unknown',
  discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(site_id, keyword)
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER NOT NULL REFERENCES sites(id),
  slug TEXT NOT NULL,
  keyword TEXT,
  title TEXT NOT NULL,
  excerpt TEXT,
  category TEXT,
  tags TEXT,
  type TEXT,
  published_at TEXT,
  url TEXT,
  content_hash TEXT,
  shingle_json TEXT,
  image_path TEXT,
  image_hash TEXT,
  status TEXT DEFAULT 'published',
  canonical_of TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(site_id, slug)
);

CREATE TABLE IF NOT EXISTS images (
  hash TEXT PRIMARY KEY,
  site_id INTEGER REFERENCES sites(id),
  path TEXT NOT NULL,
  source TEXT,
  source_url TEXT,
  pexels_id INTEGER,
  used_in_post_id INTEGER REFERENCES posts(id),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_keywords_status ON keywords(site_id, status);
CREATE INDEX IF NOT EXISTS idx_keywords_score ON keywords(site_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_posts_site ON posts(site_id);
CREATE INDEX IF NOT EXISTS idx_posts_hash ON posts(content_hash);
"""

DEFAULT_SITES = [
    ("sleepupgradehub", "sleepupgradehub.com", "sleep",
     "C:/Users/06123/GitHub/astrowind"),
    ("tradinghub",      "tradinghub.com",      "trading",   None),
    ("aitoolsedge",     "aitoolsedge.com",     "ai-tools",  None),
    ("codestackhub",    "codestackhub.com",    "dev-tools", None),
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    for slug, domain, niche, path in DEFAULT_SITES:
        conn.execute(
            "INSERT OR IGNORE INTO sites (slug, domain, niche, repo_path) "
            "VALUES (?, ?, ?, ?)",
            (slug, domain, niche, path),
        )
    conn.commit()
    conn.close()
    print(f"[db] initialized at {DB_PATH}")


def site_id(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT id FROM sites WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise ValueError(f"unknown site: {slug}")
    return row["id"]


def normalize_text(text: str) -> str:
    body = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    body = re.sub(r"!?\[[^\]]*\]\([^)]*\)", "", body)
    body = re.sub(r"[^a-z0-9\s]", " ", body.lower())
    return " ".join(body.split())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def shingles(text: str, k: int = 5) -> set[str]:
    words = normalize_text(text).split()
    if len(words) < k:
        return set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_similar(conn: sqlite3.Connection, site_id_: int, new_text: str,
                 threshold: float = 0.20) -> list[tuple[float, str, str]]:
    """Return [(jaccard, slug, title)] for posts above threshold."""
    new_sh = shingles(new_text)
    if not new_sh:
        return []
    rows = conn.execute(
        "SELECT slug, title, shingle_json FROM posts "
        "WHERE site_id = ? AND shingle_json IS NOT NULL",
        (site_id_,),
    ).fetchall()
    out: list[tuple[float, str, str]] = []
    for r in rows:
        try:
            existing = set(json.loads(r["shingle_json"]))
        except Exception:
            continue
        j = jaccard(new_sh, existing)
        if j >= threshold:
            out.append((j, r["slug"], r["title"]))
    return sorted(out, reverse=True)


if __name__ == "__main__":
    init()
