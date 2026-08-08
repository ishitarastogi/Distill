"""
Tier-1 blog scraper: sources that have a real RSS/Atom feed.

Same shape as the YouTube scraper — one scraper class, feed in,
filtered Pydantic models out. Config-driven: add a new source by
editing app/config/sources.yaml, not this file.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import html
import re
import feedparser
import yaml
from pydantic import BaseModel

CONFIG_PATH = "app/config/sources.yaml"


class BlogPost(BaseModel):
    title: str
    url: str
    guid: str
    source_name: str
    published_at: datetime
    description: str


def load_rss_sources() -> List[dict]:
    """Reads the tier_1_rss list from sources.yaml."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return config.get("tier_1_rss", [])


def clean_html(raw: str) -> str:
    """Strip HTML tags and unescape entities — descriptions often
    arrive as raw HTML from the feed."""
    text = html.unescape(raw or "")
    return re.sub(r"<[^>]+>", " ", text).strip()


class BlogRSSScraper:
    def get_posts(self, source_name: str, feed_url: str, hours: int = 24 * 7) -> List[BlogPost]:
        """
        Fetches one feed, returns posts published within the time window.
        No content fetching here — this is metadata only, matching the
        same two-stage pattern as the YouTube scraper.
        """
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        posts = []

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                continue

            published_time = datetime(
                *published_parsed[:6], tzinfo=timezone.utc)
            if published_time < cutoff_time:
                continue

            guid = entry.get("id", entry.get("link", ""))
            description = clean_html(entry.get("summary", ""))

            posts.append(BlogPost(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                guid=guid,
                source_name=source_name,
                published_at=published_time,
                description=description,
            ))

        return posts

    def get_all_posts(self, hours: int = 24 * 7) -> List[BlogPost]:
        """Runs get_posts() across every tier-1 source in the config."""
        sources = load_rss_sources()
        all_posts = []

        for source in sources:
            posts = self.get_posts(
                source["name"], source["feed_url"], hours=hours)
            all_posts.extend(posts)

        return all_posts


if __name__ == "__main__":
    scraper = BlogRSSScraper()
    posts = scraper.get_all_posts(hours=24 * 7)

    by_source: dict[str, list] = {}
    for post in posts:
        by_source.setdefault(post.source_name, []).append(post)

    for source_name, source_posts in by_source.items():
        print(f"{source_name}: {len(source_posts)} posts")
        for p in source_posts:
            print(f"  - {p.title}")
            print(f"    {p.url}")

    print(f"\nTotal posts across all tier-1 sources: {len(posts)}")
