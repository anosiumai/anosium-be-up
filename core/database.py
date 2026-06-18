"""
Database connection and session management
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from typing import Generator
from fastapi import APIRouter, HTTPException, status
import logging
from core.config import settings

read_engine = create_engine(
    settings.DATABASE_READ_URL or settings.DATABASE_URL,
    pool_pre_ping=True,
    **({
        "poolclass": QueuePool,
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
    } if settings.ENVIRONMENT == "production" else {"poolclass": NullPool})
)

ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)

def get_read_db() -> Generator[Session, None, None]:
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()

# Create SQLAlchemy engine
engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if settings.ENVIRONMENT == "production":
    engine_kwargs.update(
        {
            "poolclass": QueuePool,
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
        }
    )
else:
    engine_kwargs.update(
        {
            "poolclass": NullPool,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Create SessionLocal class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create Base class for models
Base = declarative_base()


# Database session dependency
def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI
    
    Yields:
        Database session
        
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Event listeners for connection management
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Set SQLite pragmas on connect (if using SQLite)
    """
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """
    Log database connection checkout
    """
    if settings.DEBUG:
        logger.debug("Connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """
    Log database connection checkin
    """
    if settings.DEBUG:
        logger.debug("Connection returned to pool")


# Database initialization
def init_db():
    """
    Initialize database tables
    
    Creates all tables defined in models.
    Should only be called once during application setup.
    """
    try:
        # Import all models here to ensure they're registered with Base
        from models import (
            tenant, user, patient, doctor, department,
            appointment, visit, service, billing,
            ai_lead, notification, audit, analytics  # ✅ Only existing models
        )
       
        # Remove these - they don't exist:
        # security, compliance, backup, integration
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


def drop_db():
    """
    Drop all database tables
    
    WARNING: This will delete all data!
    Should only be used in development/testing.
    """
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("Cannot drop database in production environment")
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Error dropping database: {str(e)}")
        raise


def check_db_connection() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


def get_db_info() -> dict:
    """
    Get database connection information
    
    Returns:
        Dictionary with database info
    """
    return {
        "url": settings.DATABASE_URL.split("@")[-1],  # Hide credentials
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
        "environment": settings.ENVIRONMENT,
    }


# Context manager for database sessions
class DatabaseSession:
    """
    Context manager for database sessions
    
    Usage:
        with DatabaseSession() as db:
            # Use db session
            user = db.query(User).first()
    """
    
    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
        self.db.close()


# Transaction context manager
class Transaction:
    """
    Context manager for database transactions
    
    Usage:
        with Transaction() as db:
            # All operations in this block will be in a transaction
            user = User(...)
            db.add(user)
            # Transaction will be committed automatically
            # or rolled back if an exception occurs
    """
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.should_close = db is None
    
    def __enter__(self) -> Session:
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.db.rollback()
            else:
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
                    raise
        finally:
            if self.should_close:
                self.db.close()

@router.get("/ping", summary="Basic API Health Check")
def ping():
    """
    Check if the API container is running.
    Does NOT check dependencies (use /health for readiness probes).
    """
    return {"status": "ok"}

@router.get("/health", summary="Deep Health Check (Readiness Probe)")
def health_check():
    """
    Check if the application and its dependencies (Database) are healthy.
    Load balancers should point here.
    """
    is_db_healthy = check_db_connection()
    
    if not is_db_healthy:
        # Return 503 Service Unavailable so orchestrators know to route traffic away
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )
        
    return {
        "status": "healthy",
        "database": "connected"
    }