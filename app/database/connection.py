"""Database engine and session setup for local and production environments."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Falls back to the local Docker Postgres — matches the credentials
    # in docker/docker-compose.yml (container: distil-postgres).
    return "postgresql://distil:distil@localhost:5432/distil"


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


def get_session():
    return SessionLocal()
