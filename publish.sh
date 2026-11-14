#!/usr/bin/env bash
# medium-import-mirror — one command: blog URL in, Medium import link out.
#
# Usage:
#   ./publish.sh "https://example.com/blog/my-original-post" "My Original Post Title" "2026-11-14"
#
# What it does:
#   1. Builds a clean static mirror with mirror.py into mirrors/<slug>.html
#   2. Commits + pushes it to GitHub (main branch)
#   3. Prints the GitHub Pages URL — paste that into https://medium.com/p/import
#
# One-time setup (do once, never again):
#   - pip install -r requirements.txt
#   - GitHub repo Settings -> Pages -> Source: Deploy from a branch, Branch: main, Folder: / (root)
#   - Wait ~1 minute after the first push for Pages to go live.
set -euo pipefail

URL="${1:?Usage: ./publish.sh \"<blog-url>\" \"<title>\" \"<published YYYY-MM-DD>\"}"
TITLE="${2:?Usage: ./publish.sh \"<blog-url>\" \"<title>\" \"<published YYYY-MM-DD>\"}"
PUBLISHED="${3:?Usage: ./publish.sh \"<blog-url>\" \"<title>\" \"<published YYYY-MM-DD>\"}"

# Slug = last part of the blog URL, e.g. my-original-post
SLUG="$(echo "$URL" | sed -e 's:/*$::' -e 's:.*/::')"
OUT="mirrors/${SLUG}.html"

python3 mirror.py --url "$URL" --title "$TITLE" --published "$PUBLISHED" --out "$OUT"

git add "$OUT"
git commit -m "Add mirror for $SLUG" || echo "(nothing new to commit)"
git push origin main

echo ""
echo "Done. Paste this URL into https://medium.com/p/import :"
echo "https://$(git remote get-url origin | sed -E 's#.*github\.com[:/]([^/]+)/.*#\1#').github.io/medium-import-mirror/mirrors/${SLUG}.html"
echo ""
echo "In Medium, before publishing, check: More settings -> Advanced Settings ->"
echo "Canonical link must be your blog URL, not the github.io URL."
