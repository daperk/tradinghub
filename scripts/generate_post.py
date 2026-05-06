"""Claude-powered blog post generator with anti-duplicate gating."""
from __future__ import annotations

import _env  # noqa: F401  loads .env

import json
import os
import re
from datetime import datetime, timezone

from anthropic import Anthropic

from db import find_similar, shingles, content_hash
from niches import NICHES

CLAUDE_MODEL = "claude-sonnet-4-6"
SIMILARITY_THRESHOLD = 0.20


BODY_DELIMITER = "===BODY==="


def _build_prompt(keyword: str, category: str, niche_cfg: dict,
                  pillar_posts: list[tuple[str, str]]) -> str:
    pillars_block = "\n".join(f"- {url} ({title})" for url, title in pillar_posts) \
        or "(no pillar posts yet — use plain anchor text without href)"

    current_year = datetime.now().year
    return f"""Write a unique blog post for {niche_cfg["domain"]}.

CURRENT YEAR: {current_year} — use {current_year} for all date references,
prices, "best of" framing, and recency claims. Never write 2025 or earlier
unless explicitly comparing historical data.

KEYWORD: {keyword}
CATEGORY: {category}
NICHE: {niche_cfg["site_slug"]}

STRUCTURE (1800-2200 words):
1. Opening hook with keyword (100 words)
2. Quick verdict / TL;DR (100 words)
3. 4-6 H2 sections (300-400 words each, distinct angles)
4. Comparison table if products
5. FAQ block (3-5 questions)
6. Final recommendation (100 words)

REQUIREMENTS:
- Short paragraphs (2-3 sentences max)
- **Bold** product names
- Real current-year prices when relevant
- Bullet lists for features
- 2-3 internal links from this list (markdown format):
{pillars_block}
- Voice: {niche_cfg["voice"]}

ANTI-DUPLICATE: This post MUST take a unique angle vs other posts on the same site.
If the keyword is similar to existing topics, focus on the differentiator
(audience: men/women/side-sleepers/beginners, region, year, format).

OUTPUT FORMAT — TWO PARTS, NO CODE FENCES, NO EXTRA PROSE:

PART 1: A single-line minified JSON with metadata only (no body):
{{"title":"SEO title 50-65 chars","excerpt":"Meta description 140-155 chars","tags":["tag1","tag2","tag3"],"h1_angle":"1-line description of the unique angle"}}

PART 2: After exactly the line `{BODY_DELIMITER}`, output the full markdown body.
Use real quotes, asterisks, lists, tables — do NOT escape anything. The body
runs until end of message.

Example shape:
{{"title":"...","excerpt":"...","tags":["a","b"],"h1_angle":"..."}}
{BODY_DELIMITER}
# Heading

Paragraph one.
"""


def _parse_two_part(text: str) -> dict:
    if BODY_DELIMITER not in text:
        raise ValueError(f"missing body delimiter `{BODY_DELIMITER}` in model output")
    head, body = text.split(BODY_DELIMITER, 1)
    head = head.strip()
    body = body.lstrip("\n").rstrip()

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", head, re.S)
    if fence:
        head = fence.group(1)
    start, end = head.find("{"), head.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in metadata part")
    meta = json.loads(head[start:end + 1])
    if not body:
        raise ValueError("empty body after delimiter")
    meta["body"] = body
    return meta


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-")


def generate(conn, site_id: int, niche_key: str, keyword: str,
             category: str, type_: str = "informational",
             dry_run: bool = False) -> dict | None:
    """Generate a post. Returns dict ready for publish, or None if blocked."""
    niche_cfg = NICHES[niche_key]
    pillars = niche_cfg["pillar_posts"]

    prompt = _build_prompt(keyword, category, niche_cfg, pillars)

    if dry_run:
        print("[generate] DRY RUN — would call Claude with prompt:")
        print(prompt[:600] + "...\n")
        return None

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[generate] ANTHROPIC_API_KEY missing")
        return None

    client = Anthropic()
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text
    out = _parse_two_part(raw)

    body = out["body"]
    similar = find_similar(conn, site_id, body, threshold=SIMILARITY_THRESHOLD)
    if similar:
        print(f"[generate] BLOCKED — too similar to existing posts:")
        for j, slug, title in similar[:5]:
            print(f"  {j:.2f}  {slug}  ({title})")
        return None

    timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
    slug = f"{_slugify(out['title'])}-{timestamp[-4:]}"

    return {
        "slug": slug,
        "title": out["title"],
        "excerpt": out["excerpt"],
        "tags": out["tags"],
        "h1_angle": out.get("h1_angle", ""),
        "body": body,
        "category": category,
        "type": type_,
        "keyword": keyword,
        "content_hash": content_hash(body),
        "shingles": list(shingles(body)),
    }


def to_frontmatter_md(post: dict, image_rel_path: str) -> str:
    pub = datetime.now(timezone.utc).isoformat()
    tags_yaml = "\n".join(f"  - \"{t}\"" for t in post["tags"])
    title_safe = post["title"].replace('"', '\\"')
    excerpt_safe = post["excerpt"].replace('"', '\\"')
    return f"""---
publishDate: {pub}
author: "Sleep Team"
title: "{title_safe}"
excerpt: "{excerpt_safe}"
image: {image_rel_path}
category: "{post["category"]}"
tags:
{tags_yaml}
---

{post["body"]}
"""
