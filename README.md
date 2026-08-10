# Distil
"Distill watches 9 YouTube channels and 15 blog and newsletter sources for content about real-world assets, and turns whatever's actually relevant into a weekly email. Most of what a source publishes isn't relevant, though — so an AI classifier checks each YouTube video before anything expensive happens, reading the title and description and deciding yes or no, with a reason. Blog sources skip that check, since I hand-picked those and trust everything they publish. What passes gets the real content pulled, summarized, ranked, and sent out."
Distil is a daily AI news aggregator for RWA, private credit, and related crypto / finance infrastructure. It pulls from YouTube RSS feeds, blog RSS feeds, newsletters, and configured web URLs; stores articles in PostgreSQL; enriches articles with full content; extracts tracked protocol mentions; summarizes and ranks the best items against a user profile; and emails a short daily digest.

1. Fetch. Get videos from the 9 channels, get post links from the 15 blog sources.

2. Classify. Every YouTube video gets its title and description checked by AI — relevant or not, with a reason. Blogs skip this, they're already trusted.

3. Save. Everything goes into one Postgres table, whether it's a video or a blog post.

4. Get real content. For videos that passed, pull the actual transcript. For blog posts, fetch the real webpage and clean it up.

5. Summarize. AI writes a short title and 2-3 sentence summary for everything that now has real content.

6. Rank and send. AI ranks everything by relevance, picks the top items, formats them into an email, sends it.
## Folder Structure

```text
distil/
├── app/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py              # shared RSS parsing, time filter, dedup
│   │   ├── rss.py               # generic feed scraper, configured by URL
│   │   └── youtube.py           # channel feeds, keyword search, transcripts
│   ├── services/
│   │   ├── __init__.py
│   │   ├── enrich.py            # fetch full content for rows missing it
│   │   ├── process_digest.py    # run digest agent
│   │   ├── process_mentions.py  # run mention extraction agent
│   │   ├── process_curator.py   # rank against profile
│   │   ├── process_email.py     # build and send digest
│   │   └── email.py             # SMTP helper
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── digest_agent.py
│   │   ├── mention_agent.py     # extracts tracked protocols
│   │   ├── curator_agent.py
│   │   └── email_agent.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py            # articles, protocols, mentions, digests
│   │   ├── repository.py        # all reads and writes
│   │   ├── connection.py        # engine, session, local vs prod
│   │   ├── create_tables.py
│   │   └── seed_protocols.py    # load protocols.yaml into the DB
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py            # reads the YAML files
│   │   ├── sources.yaml         # sources + YouTube keywords
│   │   └── protocols.yaml       # protocols with aliases
│   ├── profiles/
│   │   ├── __init__.py
│   │   └── user_profile.py      # RWA / private credit interests
│   ├── __init__.py
│   ├── runner.py                # stage 1: scrape all sources
│   └── daily_runner.py          # orchestrates all stages
├── docker/
│   └── docker-compose.yml
├── main.py
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## Database Plan

Core tables:

- `articles`: normalized article/video records from all sources.
- `sources`: configured RSS feeds, YouTube feeds, and web URLs.
- `protocols`: tracked protocols/projects with aliases.
- `mentions`: extracted protocol mentions per article.
- `digests`: generated daily digest runs.
- `digest_items`: ranked article snippets included in each digest.

Recommended fields:

- `sources`: `id`, `name`, `source_type`, `url`, `keywords`, `is_active`, `last_fetched_at`, `last_error`, timestamps.
- `articles`: `id`, `source_id`, `external_id`, `title`, `url`, `canonical_url`, `author`, `published_at`, `fetched_at`, `raw_summary`, `content_text`, `content_hash`, `status`, timestamps.
- `protocols`: `id`, `name`, `aliases`, `category`, `is_active`, timestamps.
- `mentions`: `id`, `article_id`, `protocol_id`, `matched_text`, `confidence`, `context`, timestamps.
- `digests`: `id`, `window_start`, `window_end`, `subject`, `body_text`, `body_html`, `sent_at`, `status`, `error`, timestamps.
- `digest_items`: `id`, `digest_id`, `article_id`, `rank`, `summary`, `relevance_score`, `relevance_reason`, timestamps.

Useful indexes:

- Unique `articles.canonical_url`.
- Optional unique `(articles.source_id, articles.external_id)`.
- Index `articles.published_at`.
- Index `(articles.status, articles.published_at)`.
- Unique `protocols.name`.
- Index `mentions.article_id`.
- Index `mentions.protocol_id`.
- Unique `(digest_items.digest_id, digest_items.article_id)`.

## Build Order

1. Project foundation: settings, environment variables, Docker Postgres, SQLAlchemy connection.
2. Database models: create `sources`, `articles`, `protocols`, `mentions`, `digests`, and `digest_items`.
3. Config loading: read `sources.yaml` and `protocols.yaml`.
4. Repository layer: centralize all database reads and writes.
5. RSS ingestion: implement generic RSS and YouTube RSS scrapers.
6. Deduplication: normalize URLs, compare external IDs, and hash content.
7. Enrichment: fetch full article text for rows that only have feed metadata.
8. Mention extraction: identify tracked protocols and aliases in article content.
9. Digest summarization: summarize each candidate article.
10. Curation: rank summaries against the RWA / private credit user profile.
11. Email delivery: render and send the digest.
12. Daily runner: orchestrate the whole pipeline as one idempotent scheduled job.
13. Render deployment: run `python -m app.daily_runner` every 24 hours with Render Cron / scheduled jobs.

## Dependencies

Suggested runtime dependencies:

- `sqlalchemy`
- `psycopg[binary]`
- `pydantic-settings`
- `python-dotenv`
- `pyyaml`
- `feedparser`
- `httpx`
- `beautifulsoup4`
- `readability-lxml`
- `lxml`
- `python-dateutil`
- `openai`
- `youtube-transcript-api`
- `typer`
- `rich`

Suggested development dependencies:

- `pytest`
- `ruff`

Optional later:

- `alembic` for migrations once the schema stabilizes.
- `pgvector` for embedding-based ranking.
- A hosted email SDK such as `resend` or `sendgrid` if SMTP feels too manual.

## Daily Pipeline

1. Scrape all active configured sources.
2. Store new articles after deduplication.
3. Enrich articles missing full text.
4. Extract protocol mentions.
5. Select articles from the last 24 hours.
6. Summarize candidate articles.
7. Rank them against the user profile.
8. Build a short digest.
9. Email the digest.
10. Store digest status and failures.
