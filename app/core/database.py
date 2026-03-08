"""
Database Connection and Session Management

This module provides database engine configuration and session factory
for the FlowCare application.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool if settings.DEBUG else None,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Session:
    """
    Get database session for dependency injection.
    
    Yields a database session and ensures it's closed after use.
    This is used as a FastAPI dependency.
    
    Yields:
        Session: Database session
    
    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    
    Returns:
        Session: Database session for the request
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.
    
    Creates all tables based on SQLAlchemy models.
    Typically called during application startup.
    
    Returns:
        None
    """
    from app.models.models import Base
    Base.metadata.create_all(bind=engine)

