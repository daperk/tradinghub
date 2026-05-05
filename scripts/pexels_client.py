"""Pexels image picker. Free real photos, anti-duplicate via Pexels ID + content hash."""
from __future__ import annotations

import hashlib
import os
import random
import time
from pathlib import Path

import requests

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
PEXELS_URL = "https://api.pexels.com/v1/search"


class PexelsError(RuntimeError):
    pass


def _used_pexels_ids(conn, site_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT pexels_id FROM images WHERE site_id = ? AND pexels_id IS NOT NULL",
        (site_id,),
    ).fetchall()
    return {r["pexels_id"] for r in rows if r["pexels_id"]}


def search_pexels(query: str, per_page: int = 30, page: int = 1) -> list[dict]:
    if not PEXELS_KEY:
        raise PexelsError("PEXELS_API_KEY not set in environment")
    r = requests.get(
        PEXELS_URL,
        params={"query": query, "per_page": per_page, "page": page,
                "orientation": "landscape"},
        headers={"Authorization": PEXELS_KEY},
        timeout=15,
    )
    if r.status_code == 429:
        raise PexelsError("rate-limited (50 req/h on free tier)")
    r.raise_for_status()
    return r.json().get("photos", [])


def pick_image(conn, site_id: int, query: str,
               fallback_queries: list[str] | None = None) -> dict | None:
    """Return {pexels_id, src_url, photographer} or None."""
    used = _used_pexels_ids(conn, site_id)
    queries = [query] + (fallback_queries or [])
    for q in queries:
        for page in (1, 2, 3):
            try:
                photos = search_pexels(q, per_page=30, page=page)
            except PexelsError as e:
                print(f"  pexels: {e}")
                return None
            for p in photos:
                if p["id"] not in used:
                    return {
                        "pexels_id": p["id"],
                        "src_url": p["src"]["large2x"],
                        "photographer": p.get("photographer", ""),
                        "alt": p.get("alt", ""),
                    }
            time.sleep(0.3)
    return None


def download_to(url: str, dest: Path) -> str:
    """Download URL to dest path, return SHA256 hex of bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=30, stream=True)
    r.raise_for_status()
    h = hashlib.sha256()
    with dest.open("wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            h.update(chunk)
    return h.hexdigest()


def acquire_image(conn, site_id: int, slug: str, query: str,
                  blog_dir: Path,
                  fallback_queries: list[str] | None = None) -> dict | None:
    """Pick + download + register in DB. Returns {path, hash, pexels_id}."""
    pick = pick_image(conn, site_id, query, fallback_queries)
    if not pick:
        return None
    dest = blog_dir / f"{slug}.jpg"
    file_hash = download_to(pick["src_url"], dest)

    if conn.execute("SELECT 1 FROM images WHERE hash = ?", (file_hash,)).fetchone():
        dest.unlink(missing_ok=True)
        print(f"  image hash collision, retrying...")
        return None

    conn.execute(
        "INSERT INTO images (hash, site_id, path, source, source_url, pexels_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (file_hash, site_id, str(dest), "pexels", pick["src_url"], pick["pexels_id"]),
    )
    conn.commit()
    return {
        "path": str(dest),
        "hash": file_hash,
        "pexels_id": pick["pexels_id"],
        "photographer": pick["photographer"],
    }
