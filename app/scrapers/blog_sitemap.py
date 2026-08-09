"""
Tier-2 blog scraper: sources with a sitemap but no RSS feed.

A sitemap lists every URL on a site, but usually without dates — so
"what's new since last run" can't be read from the sitemap itself.
Instead every article URL is returned, and the database's primary key
check (save_article_object) skips anything already stored. First run
pulls the site's archive; every run after only adds genuinely new posts.

url_pattern filters the sitemap down to actual articles, since sitemaps
also list /about, /contact, /terms and similar pages.
"""

from datetime import datetime, timezone
from typing import List
import re
import requests
import yaml
from pydantic import BaseModel

CONFIG_PATH = "app/config/sources.yaml"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DistillBot/1.0)"}


class SitemapPost(BaseModel):
    title: str
    url: str
    guid: str
    source_name: str
    published_at: datetime
    description: str


def load_sitemap_sources() -> List[dict]:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return config.get("tier_2_sitemap", [])


def title_from_url(url: str) -> str:
    """
    Sitemaps give a URL and nothing else — no title. The slug is the only
    hint available at this stage, so it's converted into a readable
    placeholder. The digest agent later generates a real title from the
    article's actual content, so this only needs to be good enough to
    identify the row.
    """
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\.(html|php)$", "", slug)
    return slug.title() if slug else url


class BlogSitemapScraper:
    def get_posts(self, source_name: str, sitemap_url: str, url_pattern: str) -> List[SitemapPost]:
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"  {source_name}: sitemap returned {resp.status_code}")
                return []
        except Exception as e:
            print(f"  {source_name}: sitemap fetch failed — {e}")
            return []

        # re.DOTALL is required: some sitemaps put the URL on its own line
        # inside the <loc> tag, so the tag spans multiple lines. Without
        # DOTALL, "." won't match the newline and the URL is never captured.
        # Stripping happens before the pattern match, since those same
        # sitemaps pad the URL with surrounding whitespace.
        all_urls = [u.strip() for u in re.findall(
            r"<loc>(.*?)</loc>", resp.text, re.DOTALL)]
        article_urls = [u for u in all_urls if url_pattern in u]

        posts = []
        for url in article_urls:
            posts.append(SitemapPost(
                title=title_from_url(url),
                url=url,
                guid=url,
                source_name=source_name,
                # Sitemaps rarely carry reliable dates. Using "now" means
                # these enter the pipeline as current — acceptable because
                # the primary key check prevents re-adding them on later runs.
                published_at=datetime.now(timezone.utc),
                description="",
            ))
        return posts

    def get_all_posts(self) -> List[SitemapPost]:
        sources = load_sitemap_sources()
        all_posts = []
        for source in sources:
            posts = self.get_posts(
                source["name"],
                source["sitemap_url"],
                source["url_pattern"],
            )
            print(f"  {source['name']}: {len(posts)} article URLs found")
            all_posts.extend(posts)
        return all_posts


if __name__ == "__main__":
    scraper = BlogSitemapScraper()
    posts = scraper.get_all_posts()
    print(f"\nTotal article URLs across all sitemap sources: {len(posts)}")
    for p in posts[:5]:
        print(f"  [{p.source_name}] {p.title}")
        print(f"    {p.url}")
