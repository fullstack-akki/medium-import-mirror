#!/usr/bin/env python3
"""
medium-import-mirror: Generate a static, script-free HTML mirror of a blog
post with a canonical link back to the original URL so Medium's importer
(medium.com/p/import) can parse it reliably.

Usage:
    python mirror.py --url "https://example.com/blog/my-original-post" \
        --title "My Original Post Title" \
        --published "2026-11-14" \
        --out "mirrors/my-original-post.html"

    # Pure client-side SPA: pass a locally saved rendered HTML file:
    python mirror.py --url "https://example.com/blog/my-original-post" \
        --title "My Original Post Title" \
        --published "2026-11-14" \
        --input-html rendered.html \
        --out "mirrors/my-original-post.html"

Notes:
- The script does NOT run JavaScript. It only parses the HTML it is given.
- If --url returns an empty SPA shell, use --input-html.
- No tracking, no <script>, no external CSS/JS in the output.
"""

import argparse
import datetime
import html
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "blockquote", "pre", "code",
    "ul", "ol", "li", "strong", "b", "em", "i", "u", "s",
    "a", "img", "figure", "figcaption", "hr", "br",
}

STRIP_CONTAINERS = {
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "nav", "header", "footer", "aside", "form",
    "button", "input", "select", "textarea",
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "gclid", "fbclid", "mc_cid", "mc_eid",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a static, script-free HTML mirror of a blog post "
            "for Medium's importer."
        )
    )
    parser.add_argument("--url", required=True, help="Original blog post URL.")
    parser.add_argument("--title", required=True, help="Medium story title.")
    parser.add_argument(
        "--published",
        required=True,
        help="Original publish date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--out", required=True, help="Output HTML path, e.g. mirrors/post.html."
    )
    parser.add_argument(
        "--input-html",
        default=None,
        help=(
            "Optional local HTML file with the rendered article. "
            "Use this for pure client-side SPAs where requests.get() "
            "only returns an empty <div id=\"root\"></div> shell."
        ),
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Optional og:description / meta description override.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for --url (default: 30).",
    )
    return parser.parse_args()


def is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_inputs(args: argparse.Namespace) -> datetime.date:
    if not is_valid_http_url(args.url):
        raise ValueError(f"--url must be a valid http(s) URL, got: {args.url}")
    try:
        published = datetime.date.fromisoformat(args.published)
    except ValueError as exc:
        raise ValueError(
            f"--published must be YYYY-MM-DD, got: {args.published}"
        ) from exc
    if args.input_html and not Path(args.input_html).is_file():
        raise ValueError(f"--input-html file not found: {args.input_html}")
    return published


def fetch_html(url: str, timeout: int) -> str:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    return response.text


def clean_url(url: str, base_url: str) -> str:
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    if not parsed.netloc:
        return ""
    query = "&".join(
        part
        for part in parsed.query.split("&")
        if part and part.split("=", 1)[0] not in TRACKING_PARAMS
    )
    cleaned = parsed._replace(query=query, fragment="").geturl()
    return cleaned


def is_data_or_svg_image(src: str) -> bool:
    lowered = src.strip().lower()
    return lowered.startswith("data:") or lowered.endswith(".svg")


def convert_tables_to_lists(soup: BeautifulSoup) -> None:
    for table in soup.find_all("table"):
        items = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all(["th", "td"])
                if cell.get_text(" ", strip=True)
            ]
            if cells:
                items.append(" — ".join(cells))
        replacement = soup.new_tag("ul")
        if not items:
            table.decompose()
            continue
        for item in items:
            list_item = soup.new_tag("li")
            list_item.string = item
            replacement.append(list_item)
        table.replace_with(replacement)


def locate_article_container(soup: BeautifulSoup) -> Tag:
    selectors = [
        "article",
        "main article",
        "[role='main']",
        "main",
        ".post-content",
        ".article-body",
        ".entry-content",
        ".content",
        ".post-body",
        "#content",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element is not None:
            return element
    if soup.body is not None:
        return soup.body
    raise ValueError("No <article>, <main>, or <body> element found in the HTML.")


def extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    first_paragraph = soup.find("p")
    if first_paragraph:
        return first_paragraph.get_text(" ", strip=True)[:200]
    return ""


def clean_and_normalize_tree(root: Tag, base_url: str) -> None:
    for tag in root.find_all(list(STRIP_CONTAINERS)):
        tag.decompose()
    for tag in root.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        if tag.name == "a":
            href = tag.get("href")
            if not href:
                tag.unwrap()
                continue
            cleaned = clean_url(href, base_url)
            if not cleaned:
                tag.unwrap()
                continue
            tag.attrs = {"href": cleaned}
        if tag.name == "img":
            src_value = (
                tag.get("src")
                or tag.get("data-src")
                or tag.get("data-lazy-src")
                or ""
            )
            if not src_value or is_data_or_svg_image(src_value):
                tag.decompose()
                continue
            cleaned_src = clean_url(src_value, base_url)
            if not cleaned_src:
                tag.decompose()
                continue
            new_attrs = {"src": cleaned_src}
            alt_text = tag.get("alt")
            if alt_text:
                new_attrs["alt"] = alt_text
            tag.attrs = new_attrs
        else:
            for attr in list(tag.attrs):
                if attr not in {"href", "src", "alt"}:
                    tag.attrs.pop(attr, None)


def build_static_document(
    *,
    title: str,
    description: str,
    article_inner_html: str,
    canonical_url: str,
    published_date: datetime.date,
) -> str:
    esc_title = html.escape(title)
    esc_description = html.escape(description) if description else esc_title
    esc_canonical = html.escape(canonical_url, quote=True)
    esc_date = html.escape(published_date.isoformat())
    esc_iso = html.escape(published_date.isoformat() + "T00:00:00Z", quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc_title}</title>
<link rel="canonical" href="{esc_canonical}">
<meta name="description" content="{esc_description}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc_title}">
<meta property="og:description" content="{esc_description}">
<meta property="og:url" content="{esc_canonical}">
<meta property="article:published_time" content="{esc_iso}">
</head>
<body>
<header>
<h1>{esc_title}</h1>
<p><time class="dt-published" datetime="{esc_iso}">{esc_date}</time></p>
</header>
<article>
{article_inner_html}
</article>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    try:
        published = validate_inputs(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        if args.input_html:
            source_html = Path(args.input_html).read_text(encoding="utf-8")
        else:
            source_html = fetch_html(args.url, args.timeout)
    except requests.RequestException as exc:
        print(f"error: failed to fetch {args.url}: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"error: cannot read --input-html: {exc}", file=sys.stderr)
        sys.exit(1)
    soup = BeautifulSoup(source_html, "html.parser")
    container = locate_article_container(soup)
    convert_tables_to_lists(container)
    clean_and_normalize_tree(container, args.url)
    inner_html_lines = []
    for child in list(container.children):
        if isinstance(child, NavigableString):
            text = child.strip()
            if text:
                inner_html_lines.append(f"<p>{html.escape(text)}</p>")
            continue
        if isinstance(child, Tag) and child.name in ALLOWED_TAGS:
            inner_html_lines.append(str(child))
    article_inner_html = "\n".join(inner_html_lines)
    soup_text_check = BeautifulSoup(article_inner_html, "html.parser")
    meaningful = [
        element.get_text(" ", strip=True)
        for element in soup_text_check.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
        if element.get_text(" ", strip=True)
    ]
    if not meaningful:
        print(
            "error: no paragraph or heading text was found in the fetched HTML. "
            "This usually means the original page is a pure client-side SPA "
            "that returns an empty <div id=\"root\"></div> shell. "
            "Save the rendered page in your browser (Save Page As -> "
            "Web Page, Complete/HTML Only), then re-run with --input-html "
            "pointing at that saved file.",
            file=sys.stderr,
        )
        sys.exit(1)
    description = args.description or extract_meta_description(soup)
    if not description:
        description = title = args.title
    document = build_static_document(
        title=args.title,
        description=description,
        article_inner_html=article_inner_html,
        canonical_url=args.url,
        published_date=published,
    )
    if "<script" in document.lower():
        raise RuntimeError("Internal error: generated document contains <script>.")
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    print(f"Wrote {output_path} ({len(document)} bytes)")


if __name__ == "__main__":
    main()
