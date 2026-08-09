"""Run the digest agent over candidate articles."""
"""
Run the digest agent over candidate articles.

Finds articles that have content (a transcript or blog body) but no
digest summary yet, runs DigestAgent on each, and saves the result
back. This is a standalone stage — same pattern as everything else in
the pipeline: ask the repository what needs doing, do it, save it.
"""

from app.agent.digest_agent import DigestAgent
from app.database.connection import get_session
from app.database.repository import Repository


def run_digest_stage() -> int:
    session = get_session()
    repo = Repository(session)
    agent = DigestAgent()

    articles = repo.get_articles_needing_summary()
    print(f"Found {len(articles)} articles needing a digest summary")

    summarized = 0
    for article in articles:
        try:
            digest = agent.summarize(article.title, article.content)
            repo.update_summary(str(article.id), digest.title, digest.summary)
            summarized += 1
            print(f"  ✓ {digest.title}")
        except Exception as e:
            print(f"  ✗ Failed to summarize {article.title!r}: {e}")

    print(f"Digest stage complete: {summarized} of {len(articles)} summarized")
    return summarized


if __name__ == "__main__":
    run_digest_stage()
