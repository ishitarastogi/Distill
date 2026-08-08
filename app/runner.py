"""Pipeline runner for scraping and storing Distil article candidates.

This file intentionally stays thin: scrapers fetch source data, agents make
LLM decisions, and the repository owns database writes. Keeping orchestration
here makes each daily stage easy to run locally and later from Render.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from app.agent.relevance_agent import RelevanceAgent, RelevanceCheck
from app.database.connection import get_session
from app.database.models import Article
from app.database.repository import Repository
from app.scrapers.blog_rss import BlogPost, BlogRSSScraper
from app.scrapers.youtube import CHANNELS, Video, YouTubeScraper


LOOKBACK_HOURS = 24 * 7
SEARCH_DAYS = 7
SEARCH_MAX_RESULTS = 15
YOUTUBE_SEARCH_QUERIES = [
    "tokenized private credit",
    "onchain private credit",
    "RWA tokenization",
    "tokenized treasuries",
    "asset tokenization blockchain",
]


@dataclass
class PipelineStats:
    """Counters for the final run summary."""

    blog_posts_saved: int = 0
    youtube_candidates_checked: int = 0
    youtube_relevant: int = 0
    transcripts_fetched: int = 0


@contextmanager
def managed_session() -> Iterator[Any]:
    """Support the common SQLAlchemy session shapes used in small apps."""

    session_source = get_session()

    if hasattr(session_source, "__enter__"):
        with session_source as session:
            yield session
        return

    if inspect.isgenerator(session_source):
        session = next(session_source)
        try:
            yield session
        finally:
            try:
                next(session_source)
            except StopIteration:
                pass
        return

    try:
        yield session_source
    finally:
        close = getattr(session_source, "close", None)
        if callable(close):
            close()


def build_blog_article(post: BlogPost) -> Article:
    """Map curated RSS posts into the unified Article table."""

    return Article(
        id=post.guid,
        source_type="blog",
        source_name=post.source_name,
        title=post.title,
        url=post.url,
        published_at=post.published_at,
        description=post.description,
        content=None,
        is_relevant=True,
        relevance_reason="Curated blog source",
    )


def build_youtube_article(
    video: Video,
    source_type: str,
    relevance: RelevanceCheck,
) -> Article:
    """Map YouTube metadata and relevance output into the unified schema."""

    return Article(
        id=video.video_id,
        source_type=source_type,
        source_name=video.channel_title,
        title=video.title,
        url=video.url,
        published_at=video.published_at,
        description=video.description,
        content=video.transcript,
        is_relevant=relevance.is_relevant,
        relevance_reason=relevance.reason,
    )


def save_article(repo: Repository, article: Article) -> bool:
    """Save one article via the repository's object-based save method."""

    return repo.save_article_object(article)


def run_blog_scrape(repo: Repository) -> int:
    """Fetch curated RSS posts and save them as relevant by default."""

    try:
        posts = BlogRSSScraper().get_all_posts(hours=LOOKBACK_HOURS)
    except Exception as exc:
        print(f"Blog scraping failed: {exc}")
        return 0

    saved = 0
    for post in posts:
        try:
            if save_article(repo, build_blog_article(post)):
                saved += 1
        except Exception as exc:
            print(f"Failed to save blog post {post.title!r}: {exc}")

    print(f"Blog RSS: saved {saved} of {len(posts)} posts")
    return saved


def classify_and_save_videos(
    repo: Repository,
    classifier: RelevanceAgent,
    videos: list[Video],
    source_type: str,
) -> tuple[int, int]:
    """Classify YouTube candidates, then save every result for auditability."""

    checked = 0
    relevant = 0

    for video in videos:
        checked += 1
        try:
            relevance = classifier.classify(video.title, video.description)
        except Exception as exc:
            print(f"Failed relevance check for {video.title!r}: {exc}")
            continue

        if relevance.is_relevant:
            relevant += 1

        try:
            save_article(repo, build_youtube_article(
                video, source_type, relevance))
        except Exception as exc:
            print(f"Failed to save YouTube video {video.video_id}: {exc}")

    return checked, relevant


def run_youtube_channels(
    repo: Repository,
    scraper: YouTubeScraper,
    classifier: RelevanceAgent,
) -> tuple[int, int]:
    """Scrape the configured channels, isolating failures per channel."""

    total_checked = 0
    total_relevant = 0

    for channel_title, channel_id in CHANNELS.items():
        try:
            videos = scraper.get_channel_videos(
                channel_id=channel_id,
                channel_title=channel_title,
                hours=LOOKBACK_HOURS,
            )
            checked, relevant = classify_and_save_videos(
                repo=repo,
                classifier=classifier,
                videos=videos,
                source_type="youtube_channel",
            )
            total_checked += checked
            total_relevant += relevant
            print(f"{channel_title}: checked {checked}, relevant {relevant}")
        except Exception as exc:
            print(f"YouTube channel failed for {channel_title}: {exc}")

    return total_checked, total_relevant


def run_youtube_search(
    repo: Repository,
    scraper: YouTubeScraper,
    classifier: RelevanceAgent,
) -> tuple[int, int]:
    """Run broad keyword searches, isolating failures per query."""

    total_checked = 0
    total_relevant = 0

    for query in YOUTUBE_SEARCH_QUERIES:
        try:
            videos = scraper.search_videos(
                query=query,
                days=SEARCH_DAYS,
                max_results=SEARCH_MAX_RESULTS,
            )
            checked, relevant = classify_and_save_videos(
                repo=repo,
                classifier=classifier,
                videos=videos,
                source_type="youtube_search",
            )
            total_checked += checked
            total_relevant += relevant
            print(f"Search {query!r}: checked {checked}, relevant {relevant}")
        except Exception as exc:
            print(f"YouTube search failed for {query!r}: {exc}")

    return total_checked, total_relevant


def article_needs_youtube_transcript(article: Article) -> bool:
    """Limit transcript work to relevant YouTube rows missing content."""

    source_type = getattr(article, "source_type", "") or ""
    content = getattr(article, "content", None)
    return (
        bool(getattr(article, "is_relevant", False))
        and source_type.startswith("youtube")
        and not content
    )


def video_from_article(article: Article) -> Video:
    """Rebuild the minimal Video object needed by add_transcripts().

    The Article schema stores the video ID as the natural primary key. It does
    not need channel_id for transcript fetching, so an empty string is enough.
    """

    return Video(
        title=article.title,
        url=article.url,
        video_id=str(article.id),
        channel_id="",
        channel_title=article.source_name or "",
        published_at=article.published_at or datetime.now(timezone.utc),
        description=article.description or "",
        transcript=article.content,
    )


def fetch_relevant_youtube_transcripts(
    repo: Repository,
    scraper: YouTubeScraper,
) -> int:
    """Fetch transcripts for relevant YouTube articles and store as content."""

    try:
        articles = [
            article
            for article in repo.get_articles_needing_content()
            if article_needs_youtube_transcript(article)
        ]
    except Exception as exc:
        print(f"Could not load YouTube articles needing transcripts: {exc}")
        return 0

    if not articles:
        print("YouTube transcripts: no relevant articles need content")
        return 0

    try:
        videos = scraper.add_transcripts(
            [video_from_article(article) for article in articles]
        )
    except Exception as exc:
        print(f"YouTube transcript batch failed: {exc}")
        return 0

    fetched = 0
    for article, video in zip(articles, videos):
        if not video.transcript:
            continue

        try:
            repo.update_content(str(article.id), video.transcript)
            fetched += 1
        except Exception as exc:
            print(f"Failed to update transcript for {article.id}: {exc}")

    print(f"YouTube transcripts: fetched {fetched} of {len(articles)}")
    return fetched


def print_summary(stats: PipelineStats) -> None:
    """Print the final operator-friendly run summary."""

    print("\nDistil pipeline complete")
    print(f"Blog posts saved: {stats.blog_posts_saved}")
    print(f"YouTube candidates checked: {stats.youtube_candidates_checked}")
    print(f"YouTube candidates relevant: {stats.youtube_relevant}")
    print(f"Transcripts fetched: {stats.transcripts_fetched}")


def run_pipeline() -> PipelineStats:
    """Run the full scrape, relevance, save, and transcript pipeline."""

    stats = PipelineStats()

    with managed_session() as session:
        repo = Repository(session)
        youtube_scraper = YouTubeScraper()
        classifier = RelevanceAgent()

        stats.blog_posts_saved = run_blog_scrape(repo)

        checked, relevant = run_youtube_channels(
            repo, youtube_scraper, classifier)
        stats.youtube_candidates_checked += checked
        stats.youtube_relevant += relevant

        checked, relevant = run_youtube_search(
            repo, youtube_scraper, classifier)
        stats.youtube_candidates_checked += checked
        stats.youtube_relevant += relevant

        stats.transcripts_fetched = fetch_relevant_youtube_transcripts(
            repo,
            youtube_scraper,
        )

    print_summary(stats)
    return stats


if __name__ == "__main__":
    run_pipeline()
