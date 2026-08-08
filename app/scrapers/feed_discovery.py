"""
Source discovery for blog/newsletter sources.

Checks each URL in order, cheapest and most reliable first:
1. RSS/Atom feed — via the page's own <link rel="alternate"> tag,
   falling back to guessing common paths.
2. robots.txt — many sites list their real sitemap path here directly.
   IMPORTANT: robots.txt is trusted for the URL, but the content it
   points to is always validated — some sites have a stale or broken
   sitemap.xml route (e.g. returns "{}" instead of real XML) even
   though robots.txt claims it exists.
3. sitemap.xml — checked at the domain root by guessing common paths,
   if robots.txt didn't reveal a valid one.
4. Sitemap index handling — if what's found is a <sitemapindex> rather
   than a real <urlset>, it doesn't list pages directly, it points to
   child sitemaps. This script follows ONE level into the first child
   sitemap to get a real page count, rather than reporting the index
   itself as "the sitemap."
5. Neither found — tier 3, needs a hand-built scraper.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DistillBot/1.0)"}

FEED_SUFFIXES = [
    "/feed", "/rss", "/feed.xml", "/rss.xml",
    "/atom.xml", "/index.xml", "/feed/",
]

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap-0.xml",
    "/wp-sitemap.xml",
]


def get_domain_root(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


# ---------- Tier 1: RSS/Atom feed ----------

def discover_via_link_tag(url: str) -> str | None:
    body = fetch(url)
    if not body:
        return None
    soup = BeautifulSoup(body, "html.parser")
    link = soup.find(
        "link",
        rel="alternate",
        type=lambda t: t and ("rss" in t or "atom" in t),
    )
    if link and link.get("href"):
        href = link["href"]
        if href.startswith("/"):
            href = urljoin(url, href)
        return href
    return None


def discover_via_common_paths(base_url: str) -> str | None:
    base = base_url.rstrip("/")
    for suffix in FEED_SUFFIXES:
        body = fetch(base + suffix)
        if body and ("<rss" in body[:1000] or "<feed" in body[:1000]):
            return base + suffix
    return None


def check_feed(url: str) -> dict:
    feed_url = discover_via_link_tag(url)
    method = "link_tag" if feed_url else None

    if not feed_url:
        feed_url = discover_via_common_paths(url)
        method = "common_path" if feed_url else None

    return {"source": url, "has_feed": feed_url is not None, "feed_url": feed_url, "method": method}


# ---------- Sitemap: validated content check ----------

def is_valid_sitemap_content(body: str) -> str | None:
    """
    Returns 'urlset' if this is a real sitemap listing pages directly,
    'sitemapindex' if it's an index pointing to child sitemaps,
    None if the content isn't a real sitemap at all (e.g. Midas's "{}").
    """
    head = body[:2000]
    if "<sitemapindex" in head:
        return "sitemapindex"
    if "<urlset" in head:
        return "urlset"
    return None


def get_first_child_sitemap(index_body: str) -> str | None:
    match = re.search(r"<loc>(.*?)</loc>", index_body)
    return match.group(1).strip() if match else None


def discover_sitemap_via_robots(domain_root: str) -> str | None:
    body = fetch(f"{domain_root}/robots.txt")
    if not body:
        return None
    for line in body.splitlines():
        if line.lower().strip().startswith("sitemap:"):
            return line.split(":", 1)[1].strip()
    return None


def discover_sitemap_via_common_paths(domain_root: str) -> str | None:
    for path in SITEMAP_PATHS:
        candidate = domain_root + path
        body = fetch(candidate)
        if body and is_valid_sitemap_content(body):
            return candidate
    return None


def check_sitemap(source_url: str) -> dict:
    root = get_domain_root(source_url)
    empty_result = {"source": source_url, "has_sitemap": False,
                    "sitemap_url": None, "url_count": 0, "method": None}

    candidate_url = discover_sitemap_via_robots(root)
    method = "robots_txt"

    if not candidate_url:
        candidate_url = discover_sitemap_via_common_paths(root)
        method = "common_path"

    if not candidate_url:
        return empty_result

    body = fetch(candidate_url)
    if not body:
        return empty_result

    kind = is_valid_sitemap_content(body)
    if kind is None:
        # robots.txt (or a guessed path) pointed somewhere, but the
        # content there isn't actually a sitemap — don't trust it.
        return empty_result

    if kind == "urlset":
        return {
            "source": source_url,
            "has_sitemap": True,
            "sitemap_url": candidate_url,
            "url_count": body.count("<loc>"),
            "method": method,
        }

    # kind == "sitemapindex" — follow one level into the first child
    child_url = get_first_child_sitemap(body)
    if not child_url:
        return empty_result

    child_body = fetch(child_url)
    if not child_body or is_valid_sitemap_content(child_body) != "urlset":
        return empty_result

    return {
        "source": source_url,
        "has_sitemap": True,
        "sitemap_url": child_url,
        "url_count": child_body.count("<loc>"),
        "method": f"{method} -> sitemap_index -> child",
    }


# ---------- Combined check ----------

def classify_source(url: str) -> dict:
    feed_result = check_feed(url)
    if feed_result["has_feed"]:
        return {"source": url, "tier": 1, "detail": feed_result["feed_url"], "method": feed_result["method"]}

    sitemap_result = check_sitemap(url)
    if sitemap_result["has_sitemap"]:
        return {
            "source": url,
            "tier": 2,
            "detail": sitemap_result["sitemap_url"],
            "url_count": sitemap_result["url_count"],
            "method": sitemap_result["method"],
        }

    return {"source": url, "tier": 3, "detail": None}


if __name__ == "__main__":
    SOURCES = [
        "https://midas.app/blog",
        "https://www.3jane.xyz/reports",
        "https://www.tradable.xyz/blog",
        "https://strata.markets/blog",
        "https://www.figure.com/blog/",
        "https://maple.finance/insights",
        "https://centrifuge.io/blog",
        "https://www.cap.app/blog",
        "https://clearpool.medium.com/",
        "https://www.pharos.xyz/resources",
        "https://app.rwa.xyz/blog",
        "https://newsletter.tokenizedpod.com/",
        "https://securitize.io/insights/articles",
        "https://www.hamiltonlane.com/en-us/insight",
        "https://kitchen.steakhouse.financial/",
    ]

    tier1, tier2, tier3 = [], [], []

    for url in SOURCES:
        result = classify_source(url)
        if result["tier"] == 1:
            tier1.append(result)
            print(f"✓ tier 1 (RSS, via {result['method']}): {url}")
            print(f"    {result['detail']}")
        elif result["tier"] == 2:
            tier2.append(result)
            print(
                f"~ tier 2 (sitemap via {result['method']}, ~{result['url_count']} URLs): {url}")
            print(f"    {result['detail']}")
        else:
            tier3.append(result)
            print(f"✗ tier 3 (needs manual scrape): {url}")

    print(f"\nTier 1 (RSS):      {len(tier1)}")
    print(f"Tier 2 (sitemap):  {len(tier2)}")
    print(f"Tier 3 (scrape):   {len(tier3)}")
    print(f"Total:             {len(SOURCES)}")
