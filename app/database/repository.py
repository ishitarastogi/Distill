"""
Every database read and write lives here — no other file constructs
a query. This is what makes a schema change a one-file diff.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from .models import Article
from .connection import get_session


class Repository:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    # ---------- Save ----------

    def save_article(
        self,
        id: str,
        source_type: str,
        source_name: str,
        title: str,
        url: str,
        published_at: datetime,
        description: str = "",
        content: Optional[str] = None,
        is_relevant: Optional[bool] = None,
        relevance_reason: Optional[str] = None,
    ) -> Optional[Article]:
        """
        Individual-fields version. Skips silently if the article already
        exists — the id (source's natural ID) is the primary key, so
        re-running a scraper never creates duplicates.
        """
        existing = self.session.query(Article).filter_by(id=id).first()
        if existing:
            return None

        article = Article(
            id=id,
            source_type=source_type,
            source_name=source_name,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            content=content,
            is_relevant=is_relevant,
            relevance_reason=relevance_reason,
        )
        self.session.add(article)
        self.session.commit()
        return article

    def save_article_object(self, article: Article) -> bool:
        """
        Object version — saves a pre-built Article directly. Returns True
        if it was actually new and saved, False if it already existed
        (skipped). Used by runner.py, which constructs full Article
        objects itself via build_blog_article() / build_youtube_article()
        rather than passing individual fields.
        """
        existing = self.session.query(Article).filter_by(id=article.id).first()
        if existing:
            return False

        self.session.add(article)
        self.session.commit()
        return True

    def bulk_save_articles(self, articles: List[dict]) -> int:
        """Returns how many were actually new (skips existing ones)."""
        saved_count = 0
        for a in articles:
            result = self.save_article(**a)
            if result is not None:
                saved_count += 1
        return saved_count

    # ---------- Query ----------

    def get_articles_needing_content(self, source_type: Optional[str] = None) -> List[Article]:
        """Articles that passed relevance but have no full content yet —
        the enrichment stage's queue."""
        query = self.session.query(Article).filter(
            Article.is_relevant == True,
            Article.content.is_(None),
        )
        if source_type:
            query = query.filter_by(source_type=source_type)
        return query.all()

    def get_articles_needing_summary(self) -> List[Article]:
        """Articles with content but no digest summary yet."""
        return self.session.query(Article).filter(
            Article.content.isnot(None),
            Article.summary.is_(None),
        ).all()

    def get_recent_relevant_articles(self, hours: int = 24 * 7) -> List[Article]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.session.query(Article).filter(
            Article.is_relevant == True,
            Article.published_at >= cutoff,
        ).all()

    def update_content(self, article_id: str, content: str) -> None:
        article = self.session.query(Article).filter_by(id=article_id).first()
        if article:
            article.content = content
            self.session.commit()

    def update_summary(self, article_id: str, title: str, summary: str) -> None:
        article = self.session.query(Article).filter_by(id=article_id).first()
        if article:
            article.digest_title = title
            article.summary = summary
            self.session.commit()

    def get_recent_digests(self, hours: int = 24 * 7):
        """Articles that have a digest summary, within the time window —
        this is the email step's input: everything ready to be ranked
        and sent."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.session.query(Article).filter(
            Article.summary.isnot(None),
            Article.published_at >= cutoff,
        ).all()
