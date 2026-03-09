"""
Database connection management for Toolkit LLM Gateway
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from toolkit_extensions.database.models import Base


class DatabaseConfig:
    """Database configuration"""

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        echo: bool = False,
    ):
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./gateway.db")
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.echo = echo

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite"""
        return self.database_url.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL"""
        return self.database_url.startswith("postgresql")


class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def engine(self) -> Engine:
        """Get or create database engine"""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create session factory"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    def _create_engine(self) -> Engine:
        """Create database engine with appropriate configuration"""
        engine_kwargs = {
            "echo": self.config.echo,
        }

        # Configure connection pooling
        if self.config.is_sqlite:
            # SQLite: Use NullPool for simplicity
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # PostgreSQL: Use connection pooling
            engine_kwargs["poolclass"] = QueuePool
            engine_kwargs["pool_size"] = self.config.pool_size
            engine_kwargs["max_overflow"] = self.config.max_overflow
            engine_kwargs["pool_timeout"] = self.config.pool_timeout
            engine_kwargs["pool_pre_ping"] = True  # Test connections before use

        engine = create_engine(self.config.database_url, **engine_kwargs)

        # Enable foreign keys for SQLite
        if self.config.is_sqlite:

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        return engine

    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.

        Usage:
            with db_manager.session() as session:
                user = session.query(User).first()
                # ... do work ...
                session.commit()
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """
        Get a new session (caller responsible for closing).

        Usage:
            session = db_manager.get_session()
            try:
                # ... do work ...
                session.commit()
            finally:
                session.close()
        """
        return self.session_factory()

    def close(self):
        """Close all connections"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_database(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """Initialize database with custom configuration"""
    global _db_manager
    _db_manager = DatabaseManager(config)
    _db_manager.create_tables()
    return _db_manager


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Convenience function to get a database session.

    Usage:
        from toolkit_extensions.database.connection import get_session

        with get_session() as session:
            user = session.query(User).filter_by(email="alice@example.com").first()
    """
    db_manager = get_db_manager()
    with db_manager.session() as session:
        yield session
