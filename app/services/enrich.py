"""Fetch full content for articles missing extracted body text."""
"""
Fetch full content for articles missing extracted body text.

Blog posts arrive from blog_rss.py with metadata only — title, URL,
description — no full article body. This stage fetches each page and
converts it to clean markdown, so the digest agent has real content
to summarize instead of just a short RSS description.

Deliberately NOT using Docling here — it loads OCR models at import
time and caused an out-of-memory failure on deployment in the
reference project this was built from. markdownify + BeautifulSoup is
lighter weight and sufficient for blog post bodies.
"""

from bs4 import BeautifulSoup
import requests
from markdownify import markdownify as html_to_md
from app.database.repository import Repository
from app.database.connection import get_session


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DistillBot/1.0)"}

# Tags that are almost never part of the actual article body — stripped
# before conversion so the digest agent isn't summarizing nav menus and
# cookie banners.
NOISE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "form"]

# Common containers that hold the real article body, checked in order.
# Falls back to the whole page if none match.
CONTENT_SELECTORS = ["article", "main", "[role=main]",
                     ".post-content", ".article-content"]


def fetch_and_clean(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
    except Exception as e:
        print(f"    fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag_name in NOISE_TAGS:
        for tag in soup.select(tag_name):
            tag.decompose()

    content_node = None
    for selector in CONTENT_SELECTORS:
        content_node = soup.select_one(selector)
        if content_node:
            break

    target = content_node if content_node else soup.body
    if not target:
        return None

    markdown = html_to_md(str(target), heading_style="ATX")
    # Collapse excessive blank lines left over from stripped elements
    lines = [line for line in markdown.splitlines() if line.strip()]
    cleaned = "\n\n".join(lines)

    # too short = probably not real content
    return cleaned if len(cleaned) > 100 else None


def run_enrich_stage(source_type: str = "blog") -> int:
    session = get_session()
    repo = Repository(session)

    articles = repo.get_articles_needing_content(source_type=source_type)
    print(f"Found {len(articles)} {source_type} articles needing content")

    enriched = 0
    for article in articles:
        print(f"  Fetching: {article.title[:60]}")
        content = fetch_and_clean(article.url)

        if content:
            repo.update_content(str(article.id), content)
            enriched += 1
            print(f"    ✓ {len(content)} chars")
        else:
            print(f"    ✗ could not extract content")

    print(f"Enrich stage complete: {enriched} of {len(articles)} enriched")
    return enriched


if __name__ == "__main__":
    run_enrich_stage(source_type="blog")
