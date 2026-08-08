"""SQLAlchemy models for articles, protocols, mentions, and digests."""
"""
One unified Article table for every source — blogs, YouTube channels,
YouTube search results — instead of a separate table per source type.

This is deliberate: with 25+ sources planned, a table-per-source design
means a table-per-source repository too. One table with a source_type
column scales to any number of sources without new tables or new
repository methods.
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Text, Boolean
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"

    # The natural ID from the source: a blog post GUID, or a YouTube
    # video ID. Using this as the primary key is what makes saving
    # idempotent — re-running the scraper never creates duplicates.
    id = Column(String, primary_key=True)

    # "blog" | "youtube_channel" | "youtube_search"
    source_type = Column(String, nullable=False)
    # "Centrifuge", "The Rollup", etc.
    source_name = Column(String, nullable=False)

    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    description = Column(Text)

    # Full text — blog body markdown, or video transcript. Filled in
    # by the enrichment stage, empty at ingest time.
    content = Column(Text, nullable=True)

    # Set by the relevance classifier. Null means "not checked yet".
    is_relevant = Column(Boolean, nullable=True)
    relevance_reason = Column(Text, nullable=True)

    # Set once the digest agent has summarized this article.
    summary = Column(Text, nullable=True)
    digest_title = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
