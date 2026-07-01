"""Lightweight schema migrations for SQLite / PostgreSQL dev databases."""

import logging
from sqlalchemy import inspect, text

from backend.database import Base, engine

logger = logging.getLogger("backend_logger")


def _column_names(inspector, table: str) -> set[str]:
    if not inspector.has_table(table):
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def run_migrations() -> None:
    """Create missing tables and patch legacy SQLite schemas in-place."""
    # Import models so metadata is populated before create_all
    from backend.models import ChatSession, Message, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    if inspector.has_table("chat_sessions"):
        session_cols = _column_names(inspector, "chat_sessions")
        if "user_id" not in session_cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE chat_sessions ADD COLUMN user_id VARCHAR(36)")
                )
            logger.info("Migration: added chat_sessions.user_id column")

    logger.info("Database migrations complete")
