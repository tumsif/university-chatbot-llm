"""Lightweight schema migrations for SQLite / PostgreSQL dev databases."""

import fcntl
import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from backend.database import Base, engine

logger = logging.getLogger("backend_logger")

MIGRATION_LOCK = Path("/tmp/unisupport_migrate.lock")


def _column_names(inspector, table: str) -> set[str]:
    if not inspector.has_table(table):
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _create_missing_tables() -> None:
    """Create tables one-by-one so partial runs are safe."""
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if inspector.has_table(table.name):
            continue
        try:
            table.create(bind=engine, checkfirst=True)
            logger.info("Migration: created table %s", table.name)
        except OperationalError as exc:
            if "already exists" in str(exc).lower():
                logger.info("Migration: table %s already exists (race)", table.name)
            else:
                raise


def run_migrations() -> None:
    """Create missing tables and patch legacy SQLite schemas in-place."""
    # Import models so metadata is populated before create_all
    from backend.models import ChatSession, Message, User, UserDocument  # noqa: F401

    MIGRATION_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(MIGRATION_LOCK, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            _create_missing_tables()
            inspector = inspect(engine)

            if inspector.has_table("chat_sessions"):
                session_cols = _column_names(inspector, "chat_sessions")
                if "user_id" not in session_cols:
                    with engine.begin() as conn:
                        conn.execute(
                            text("ALTER TABLE chat_sessions ADD COLUMN user_id VARCHAR(36)")
                        )
                    logger.info("Migration: added chat_sessions.user_id column")
                if "document_id" not in session_cols:
                    with engine.begin() as conn:
                        conn.execute(
                            text("ALTER TABLE chat_sessions ADD COLUMN document_id VARCHAR(36)")
                        )
                    logger.info("Migration: added chat_sessions.document_id column")
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    logger.info("Database migrations complete")
