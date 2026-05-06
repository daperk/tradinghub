#!/usr/bin/env bash
# Init git + commit + push for each scaffolded niche repo.
# Assumes empty GitHub repos exist at github.com/daperk/<slug>.
# Run from anywhere; uses absolute paths.
set -euo pipefail

OWNER="daperk"
NICHES=("tradinghub" "aitoolsedge" "codestackhub")
BASE="C:/Users/06123/GitHub"

for slug in "${NICHES[@]}"; do
  dir="$BASE/$slug"
  if [ ! -d "$dir" ]; then
    echo "[skip] $dir does not exist (run scaffold_site.py --all first)"
    continue
  fi

  echo ""
  echo "=== $slug ==="
  cd "$dir"

  if [ ! -d ".git" ]; then
    git init -b main
    git add .
    git commit -m "Initial scaffold from astrowind template" \
      --author="Daniel Pena <noreply@anthropic.com>"
  else
    echo "[info] $slug already initialized"
  fi

  remote_url="https://github.com/$OWNER/$slug.git"
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$remote_url"
  else
    git remote set-url origin "$remote_url"
  fi

  echo "[push] -> $remote_url"
  git push -u origin main 2>&1 | tail -3
done

echo ""
echo "=== done ==="
echo "Next: import each on https://vercel.com/new (auto-detects Astro)."
echo "After Vercel imports, copy each Deploy Hook URL into astrowind/.env:"
echo "  VERCEL_HOOK_TRADINGHUB=..."
echo "  VERCEL_HOOK_AITOOLSEDGE=..."
echo "  VERCEL_HOOK_CODESTACKHUB=..."
echo "Then update sites table:"
echo "  python -c \"import sys; sys.path.insert(0,'scripts'); from db import get_conn"
echo "  conn=get_conn()"
echo "  for slug in ('tradinghub','aitoolsedge','codestackhub'):"
echo "    conn.execute('UPDATE sites SET repo_path=? WHERE slug=?', (f'C:/Users/06123/GitHub/{slug}', slug))"
echo "  conn.commit()\""
