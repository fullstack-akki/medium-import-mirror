# medium-import-mirror

Generate clean, static, script-free HTML mirrors of blog posts so Medium's importer (medium.com/p/import) can parse them — even when the original blog is a JavaScript-rendered SPA that Medium's parser cannot read.

## Quick start — 3 steps, that's it

```bash
git clone https://github.com/YOUR_USERNAME/medium-import-mirror.git
cd medium-import-mirror
pip install -r requirements.txt
./publish.sh "https://example.com/blog/my-original-post" "My Original Post Title" "2026-11-14"
```

That one command builds the mirror, pushes it to GitHub, and prints the link.
Then:

1. Paste the printed link into https://medium.com/p/import
2. In Medium, check More settings → Advanced Settings → Canonical link is your **blog URL** (not the github.io URL)
3. Add tags, publish. Done.

One-time setup (once, never again): GitHub repo → Settings → Pages → Source: **Deploy from a branch**, Branch: **main**, Folder: **/ (root)**. Wait ~1 minute after the first push for Pages to go live.

After a story is published, the mirror file is only a bridge — you can replace it with a tiny redirect to your blog, or delete it. Medium keeps its own copy of the story, so deleting the mirror never breaks the published story. (Do it **after** the import, never before — if Medium's importer follows a redirect to your JS blog it will fail.)

## What problem does this solve?

Medium's import tool (medium.com/p/import) uses a third-party parser that does not execute JavaScript. If your blog is a React / Vite single-page app (SPA), the initial HTML response contains only an empty `<div id="root"></div>` shell, so the importer fails with "server stopped responding" or "could not be imported", even though the page loads fine in a browser.

Medium has closed new Integration Token generation since 1 January 2025, so new accounts cannot use the official REST API. If you already have a legacy token, that route still exists, but this project does not use it.

The workaround is simple: generate a clean, static, plain HTML mirror of the article (no JavaScript at all), host it at a public URL, import *that* URL in Medium, and let Medium pick up the canonical link back to the original post.

## What this tool does

- Fetches an original blog post URL with `requests`.
- Extracts headings, paragraphs, lists, blockquotes, code blocks, and images (with absolute URLs).
- Outputs ONE clean static HTML file with:
  - `<title>`
  - `<link rel="canonical" href="ORIGINAL_URL">`
  - `<meta property="article:published_time" content="YYYY-MM-DDT00:00:00Z">`
  - `og:title` and `og:description`
  - The full article inside `<article>`
  - Zero `<script>` tags, zero external CSS/JS, zero tracking
- Converts HTML `<table>` elements into plain bulleted lines (Medium's importer drops tables).
- Keeps all text — it does not summarise or shorten.
- Optionally accepts `--input-html` for pure client-side SPAs where `requests.get()` only returns an empty shell (see Usage, Case 2).

## Repository layout

```
medium-import-mirror/
├── .github/workflows/pages.yml
├── mirrors/
│   └── example-structure.html
├── .gitignore
├── LICENSE
├── README.md
├── mirror.py
└── requirements.txt
```

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/medium-import-mirror.git
cd medium-import-mirror
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify the script:

```bash
python mirror.py --help
```

## Usage

### Case 1: Your blog returns article HTML in the initial HTTP response

If your site includes the article text in the HTML response (or pre-renders it), run:

```bash
python mirror.py \
  --url "https://example.com/blog/my-original-post" \
  --title "My Original Post Title" \
  --published "2026-11-14" \
  --out "mirrors/my-original-post.html"
```

### Case 2: Your blog is a pure client-side SPA (React / Vite)

Because `mirror.py` uses Python `requests` (not a headless browser), calling `requests.get()` on a pure client-side React/Vite site will only receive `<div id="root"></div>`.

To mirror a pure client-side SPA:

1. Open your live blog post in Chrome/Firefox.
2. Right-click the page -> Inspect, right-click the `<article>` (or `<body>`) element in DevTools -> Copy -> Copy outerHTML, and save it as `rendered.html` (or press `Ctrl+S` / `Cmd+S` -> Webpage, HTML Only).
3. Run `mirror.py` with `--input-html`:

```bash
python mirror.py \
  --url "https://example.com/blog/my-original-post" \
  --title "My Original Post Title" \
  --published "2026-11-14" \
  --input-html rendered.html \
  --out "mirrors/my-original-post.html"
```

The script resolves all relative image and anchor URLs against `--url`, converts HTML `<table>` elements into bulleted lists (`<ul><li>...</li></ul>`), strips all `<script>`, `<style>`, `<svg>`, and tracking tags, and outputs a single static HTML file in `mirrors/`.

## Enabling GitHub Pages (Manual Steps Required — once only)

1. Push this repository to a public GitHub repository on the `main` branch.
2. On GitHub, open your repository and click Settings in the top navigation bar.
3. In the left sidebar under "Code and automation", click Pages.
4. Under Build and deployment -> Source, choose `Deploy from a branch`, Branch `main`, Folder `/ (root)`, then Save.
5. Commit and push your generated file inside `mirrors/` (or just run `./publish.sh`, which does this for you):

```bash
git add mirrors/my-original-post.html
git commit -m "Add mirror for my-original-post"
git push origin main
```

6. Wait ~1 minute for Pages to build.

Your static mirror is now live at:

```
https://YOUR_GITHUB_USERNAME.github.io/medium-import-mirror/mirrors/my-original-post.html
```

## Importing Into Medium

1. Open https://medium.com/p/import in your browser.
2. Paste your GitHub Pages mirror URL (not your SPA URL):

```
https://YOUR_GITHUB_USERNAME.github.io/medium-import-mirror/mirrors/my-original-post.html
```

3. Click Import.
4. Wait for Medium to generate the draft, then click See your story.
5. Review formatting, add tags, and publish (or stay in draft).

## How to Verify the Canonical URL Points to Your Original Site

Before and after publishing on Medium, verify that Medium picked up your original blog URL (`--url`) and not the GitHub Pages mirror URL:

**Inside the Medium Editor (Before Publishing):**

1. Click the three-dot menu (...) in the top right of the Medium editor -> More settings.
2. Scroll down and expand Advanced Settings.
3. Check that "This story was originally published elsewhere" is ticked and the URL field contains your original URL (`https://example.com/blog/my-original-post`).

**In the Live Medium Post Source (After Publishing):**

1. Open your published Medium post in a browser.
2. Right-click -> View Page Source (or press `Ctrl+U` / `Cmd+Option+U`).
3. Search (`Ctrl+F` / `Cmd+F`) for `rel="canonical"`.
4. Confirm the tag reads:

```html
<link data-rh="true" rel="canonical" href="https://example.com/blog/my-original-post"/>
```

## Known Limitations

- **Medium API Closed to New Users (1 Jan 2025):** There is no official API way to automate draft creation for new accounts. You must import manually via medium.com/p/import.
- **Pure Client-Side SPAs Need `--input-html`:** `requests` does not run JavaScript. If your server returns an empty HTML shell without SSR/pre-rendering, you must save the rendered page in your browser and pass it via `--input-html`.
- **HTML Tables:** Medium's importer drops native `<table>` elements completely. `mirror.py` converts table rows into `<ul><li>Header: Value — Header: Value</li></ul>` bullet lists so no text is lost.
- **SVG and Base64 Images:** Medium's importer ignores inline `<svg>` and `data:image/...` URIs. `mirror.py` strips `.svg` and `data:` images and keeps standard raster images (`.jpg`, `.png`, `.webp`, `.gif`) with absolute `https://` URLs.
- **Medium Importer Caching & Rate Limits:** If you re-import the exact same mirror URL multiple times while testing, Medium may serve a cached copy. Append a query string like `?v=2` to the GitHub Pages mirror URL when pasting into medium.com/p/import to force a fresh fetch, while keeping the `<link rel="canonical">` inside the file clean.
