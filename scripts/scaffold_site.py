"""Scaffold a new niche site from astrowind. Single-shot, idempotent.

Creates a sibling directory next to this repo, copies the relevant files,
strips sleep-specific content, and writes a niche-customized config.

Usage:
  python scripts/scaffold_site.py --niche trading
  python scripts/scaffold_site.py --niche ai-tools --target C:/Users/06123/GitHub/aitoolsedge
  python scripts/scaffold_site.py --all           # scaffold all 3 unbuilt niches
"""
from __future__ import annotations

import _env  # noqa: F401

import argparse
import shutil
import sys
from pathlib import Path

from niches import NICHES

SRC = Path("C:/Users/06123/GitHub/astrowind")

EXCLUDE_DIRS = {".git", "node_modules", "dist", ".astro", ".vercel",
                ".claude", "data", "venv", ".venv"}

EXCLUDE_FILES = {".env", ".env.production", ".env.local",
                 "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}

EXCLUDE_GLOB_PATTERNS = [
    "src/data/post/",
    "src/assets/images/blog/",
]


def _should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    if path.name in EXCLUDE_FILES:
        return True
    for d in EXCLUDE_DIRS:
        if rel == d or rel.startswith(f"{d}/"):
            return True
    for pat in EXCLUDE_GLOB_PATTERNS:
        if rel.startswith(pat):
            return True
    return False


def copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if _should_skip(p, src):
            continue
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    return n


def write_config_yaml(target: Path, niche_cfg: dict, site_name_pretty: str) -> None:
    domain = niche_cfg["domain"]
    yaml = f"""site:
  name: {site_name_pretty}
  site: 'https://{domain}'
  base: '/'
  trailingSlash: false

  googleSiteVerificationId: null

metadata:
  title:
    default: {site_name_pretty}
    template: '%s — {site_name_pretty}'
  description: '{niche_cfg["voice"]}'
  robots:
    index: true
    follow: true
  openGraph:
    site_name: {site_name_pretty}
    images:
      - url: '~/assets/images/default.png'
        width: 1200
        height: 628
    type: website
  twitter:
    handle: '@{niche_cfg["site_slug"]}'
    site: '@{niche_cfg["site_slug"]}'
    cardType: summary_large_image

i18n:
  language: en
  textDirection: ltr

apps:
  blog:
    isEnabled: true
    postsPerPage: 6
    post:
      isEnabled: true
      permalink: '/%slug%'
      robots:
        index: true
    list:
      isEnabled: true
      pathname: 'blog'
      robots:
        index: true
    category:
      isEnabled: true
      pathname: 'category'
      robots:
        index: true
    tag:
      isEnabled: true
      pathname: 'tag'
      robots:
        index: true
    isRelatedPostsEnabled: true
    relatedPostsCount: 4

analytics:
  vendors:
    googleAnalytics:
      id: null

ui:
  theme: 'system'
"""
    (target / "src" / "config.yaml").write_text(yaml, encoding="utf-8")


def write_navigation_ts(target: Path, niche_cfg: dict, site_name_pretty: str) -> None:
    cats = niche_cfg["categories"]
    cat_links = "\n        ".join(
        f"{{ text: '{c}', href: getPermalink('{slugify(c)}', 'category') }},"
        for c in cats
    )
    footer_cats = "\n        ".join(
        f"{{ text: '{c}', href: getPermalink('{slugify(c)}', 'category') }},"
        for c in cats[:6]
    )
    content = f"""import {{ getPermalink, getBlogPermalink }} from './utils/permalinks';

export const headerData = {{
  links: [
    {{
      text: 'Guides',
      links: [
        {{ text: 'All Guides', href: getBlogPermalink() }},
        {cat_links}
      ],
    }},
    {{ text: 'About', href: getPermalink('/about') }},
    {{ text: 'Contact', href: getPermalink('/contact') }},
  ],
  actions: [],
}};

export const footerData = {{
  links: [
    {{
      title: 'Categories',
      links: [
        {footer_cats}
      ],
    }},
    {{
      title: 'Resources',
      links: [
        {{ text: 'All Guides', href: getBlogPermalink() }},
      ],
    }},
    {{
      title: 'Company',
      links: [
        {{ text: 'About', href: getPermalink('/about') }},
        {{ text: 'Contact', href: getPermalink('/contact') }},
        {{ text: 'Blog', href: getBlogPermalink() }},
      ],
    }},
    {{
      title: 'Legal',
      links: [
        {{ text: 'Privacy Policy', href: getPermalink('/privacy') }},
        {{ text: 'Terms & Conditions', href: getPermalink('/terms') }},
        {{ text: 'Affiliate Disclosure', href: getPermalink('/disclosure') }},
      ],
    }},
  ],
  secondaryLinks: [
    {{ text: 'Privacy Policy', href: getPermalink('/privacy') }},
    {{ text: 'Terms', href: getPermalink('/terms') }},
    {{ text: 'Disclosure', href: getPermalink('/disclosure') }},
  ],
  socialLinks: [],
  footNote: `
    © ${{new Date().getFullYear()}} {site_name_pretty}. All rights reserved.
  `,
}};
"""
    (target / "src" / "navigation.ts").write_text(content, encoding="utf-8")


def slugify(s: str) -> str:
    return s.lower().replace(" ", "-").replace("&", "and")


def write_homepage(target: Path, niche_cfg: dict, site_name_pretty: str) -> None:
    tagline = {
        "trading":   "Practical, risk-aware reviews of prop firms, brokers, and trading systems.",
        "ai-tools":  "Hands-on AI tool reviews. Real use cases, real costs, no hype.",
        "dev-tools": "Production-grade tradeoffs across IDEs, frameworks, and infrastructure.",
        "sleep":     "Science-backed sleep optimization guides.",
    }.get(niche_cfg.get("niche") or "", "")
    if not tagline:
        for slug, cfg in NICHES.items():
            if cfg["site_slug"] == niche_cfg["site_slug"]:
                tagline = {
                    "trading":   "Practical, risk-aware reviews of prop firms, brokers, and trading systems.",
                    "ai-tools":  "Hands-on AI tool reviews. Real use cases, real costs, no hype.",
                    "dev-tools": "Production-grade tradeoffs across IDEs, frameworks, and infrastructure.",
                }.get(slug, "")
                break

    content = f"""---
import Layout from '~/layouts/PageLayout.astro';
import Hero from '~/components/widgets/Hero.astro';
import BlogLatestPosts from '~/components/widgets/BlogLatestPosts.astro';

const metadata = {{
  title: '{site_name_pretty} — Honest reviews, real tradeoffs',
}};
---

<Layout metadata={{metadata}}>
  <Hero
    tagline="Welcome to {site_name_pretty}"
  >
    <Fragment slot="title">
      {site_name_pretty}
    </Fragment>
    <Fragment slot="subtitle">
      {tagline}
    </Fragment>
  </Hero>

  <BlogLatestPosts
    title="Latest Guides"
    information={{`Hands-on, no-fluff reviews and how-to guides.`}}
  />
</Layout>
"""
    (target / "src" / "pages" / "index.astro").write_text(content, encoding="utf-8")


def write_about(target: Path, site_name_pretty: str, niche_cfg: dict) -> None:
    content = f"""---
import Layout from '~/layouts/PageLayout.astro';
import Hero from '~/components/widgets/Hero.astro';
import Features2 from '~/components/widgets/Features2.astro';

const metadata = {{
  title: 'About {site_name_pretty}',
}};
---

<Layout metadata={{metadata}}>
  <Hero tagline="About">
    <Fragment slot="title">{site_name_pretty}</Fragment>
    <Fragment slot="subtitle">{niche_cfg["voice"]}</Fragment>
  </Hero>

  <Features2
    title="What we do differently"
    columns={{3}}
    items={{[
      {{ title: 'No paid placements', description: 'Recommendations are independent. Affiliate links never alter rankings.', icon: 'tabler:shield-check' }},
      {{ title: 'Honest tradeoffs', description: 'Every guide names what we'd skip and why.', icon: 'tabler:scale' }},
      {{ title: 'Updated frequently', description: 'We revisit content as products and pricing change.', icon: 'tabler:refresh' }},
    ]}}
  />
</Layout>
"""
    (target / "src" / "pages" / "about.astro").write_text(content, encoding="utf-8")


def replace_in_file(path: Path, replacements: list[tuple[str, str]]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def site_name_for(niche_cfg: dict) -> str:
    pretty_map = {
        "tradinghub":   "TradingHub",
        "aitoolsedge":  "AIToolsEdge",
        "codestackhub": "CodeStackHub",
    }
    return pretty_map.get(niche_cfg["site_slug"], niche_cfg["site_slug"])


def write_next_steps(target: Path, niche_cfg: dict, site_name_pretty: str) -> None:
    content = f"""# {site_name_pretty} — next steps

Generated by `scaffold_site.py`. Local repo only — not connected to GitHub or Vercel yet.

## 1. GitHub
```bash
cd {target}
git init
git add .
git commit -m "Initial scaffold from astrowind"
gh repo create {niche_cfg["site_slug"]} --private --source=. --push
```

## 2. Vercel
- Dashboard → New Project → Import the GitHub repo
- Framework: Astro (auto-detected)
- Root: `./`
- Add domain: `{niche_cfg["domain"]}`
- Settings → Git → Deploy Hooks → create one named `cli`
- Paste the hook URL into `astrowind/.env` as `VERCEL_HOOK_{niche_cfg["site_slug"].upper()}`

## 3. Update site DB
```bash
sqlite3 ../astrowind/data/seo-empire.db "UPDATE sites SET repo_path='{target.as_posix()}', vercel_hook='<URL>' WHERE slug='{niche_cfg["site_slug"]}'"
```

## 4. First post
```bash
cd ../astrowind
python scripts/keyword_discovery.py --site {niche_cfg["site_slug"]}
python scripts/batch.py --site {niche_cfg["site_slug"]} --count 1 --no-deploy
```
Review the post, then drop `--no-deploy` to let it commit + push + trigger Vercel.

## 5. AdSense (later, after ~30 quality posts)
- Apply at https://adsense.google.com
- After approval, add to Vercel project env vars:
  - `PUBLIC_ADSENSE_ENABLED=true`
  - `PUBLIC_ADSENSE_CLIENT=ca-pub-XXXXXXXXXXXXXXXX`
- Redeploy. Ad slots and cookie consent will activate automatically.
"""
    (target / "NEXT_STEPS.md").write_text(content, encoding="utf-8")


def scaffold(niche_key: str, target: Path, force: bool = False) -> int:
    cfg = NICHES.get(niche_key)
    if not cfg:
        print(f"unknown niche: {niche_key}")
        return 1

    if target.exists() and any(target.iterdir()):
        if not force:
            print(f"[scaffold] target exists and is not empty: {target}")
            print("  pass --force to overwrite")
            return 1
        shutil.rmtree(target)

    site_name_pretty = site_name_for(cfg)
    domain = cfg["domain"]

    print(f"[scaffold] {niche_key} -> {target}")
    target.mkdir(parents=True, exist_ok=True)

    n = copy_tree(SRC, target)
    print(f"[scaffold] copied {n} files")

    write_config_yaml(target, cfg, site_name_pretty)
    write_navigation_ts(target, cfg, site_name_pretty)
    write_homepage(target, cfg, site_name_pretty)
    write_about(target, site_name_pretty, cfg)

    legal_replacements = [
        ("SleepUpgradeHub", site_name_pretty),
        ("sleepupgradehub.com", domain),
        ("sleepupgradehub", cfg["site_slug"]),
    ]
    for fname in ("privacy.astro", "terms.astro", "disclosure.astro", "contact.astro", "404.astro"):
        replace_in_file(target / "src" / "pages" / fname, legal_replacements)
    replace_in_file(target / "public" / "robots.txt", legal_replacements)

    pkg = target / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8")
        text = text.replace('"@onwidget/astrowind"', f'"@daperk/{cfg["site_slug"]}"')
        pkg.write_text(text, encoding="utf-8")

    for sub in ("habits.astro", "tools.astro"):
        p = target / "src" / "pages" / sub
        if p.exists():
            p.unlink()

    write_next_steps(target, cfg, site_name_pretty)
    print(f"[scaffold] done. See {target / 'NEXT_STEPS.md'}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", choices=list(NICHES.keys()))
    ap.add_argument("--all", action="store_true",
                    help="scaffold all niches except 'sleep'")
    ap.add_argument("--target", help="override target directory")
    ap.add_argument("--force", action="store_true",
                    help="overwrite if target exists")
    args = ap.parse_args()

    if args.all:
        rc = 0
        for niche_key, cfg in NICHES.items():
            if niche_key == "sleep":
                continue
            target = Path(f"C:/Users/06123/GitHub/{cfg['site_slug']}")
            rc |= scaffold(niche_key, target, force=args.force)
        sys.exit(rc)

    if not args.niche:
        ap.error("--niche or --all required")

    cfg = NICHES[args.niche]
    target = Path(args.target) if args.target else \
        Path(f"C:/Users/06123/GitHub/{cfg['site_slug']}")
    sys.exit(scaffold(args.niche, target, force=args.force))


if __name__ == "__main__":
    main()
