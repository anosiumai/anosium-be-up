"""
Database Configuration with Connection Pooling
Optimized for high performance and concurrency
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
import os

# Load .env file BEFORE reading any env vars
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/clinic_saas"
)

# Build connect_args conditionally based on driver
_connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    _connect_args = {"connect_timeout": 10}
elif DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

# Create engine with optimized connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    connect_args=_connect_args,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    Automatically handles session lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions.
    Use in non-FastAPI contexts (e.g. scripts, background tasks).
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Performance tuning hooks — fire once per raw DBAPI connection
# ---------------------------------------------------------------------------

@event.listens_for(engine, "connect")
def _tune_sqlite(dbapi_conn, connection_record):
    """WAL mode + memory temp store for SQLite."""
    if "sqlite" not in DATABASE_URL:
        return
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA cache_size=10000")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.close()


@event.listens_for(engine, "connect")
def _tune_postgres(dbapi_conn, connection_record):
    """Safe statement & lock timeouts for PostgreSQL."""
    if "postgresql" not in DATABASE_URL:
        return
    cur = dbapi_conn.cursor()
    cur.execute("SET statement_timeout = '30s'")
    cur.execute("SET lock_timeout = '10s'")
    cur.close()


# ---------------------------------------------------------------------------
# Init / drop helpers
# ---------------------------------------------------------------------------

def init_db():
    """
    Create all tables declared in the models.
    Called once at application startup via the lifespan hook.
    """
    from models.base import Base  # adjust import if your Base lives elsewhere
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop every table.  Development / migration-reset only.
    """
    from models.base import Base
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_db_health() -> bool:
    """
    Ping the database.  Returns True when the connection is usable.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False