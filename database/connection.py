"""
Database Connection Manager
============================

This module manages database connections for the Golf Tracker application.
It provides a centralized way to connect to MySQL, execute queries, and
manage database sessions with proper error handling.

For Junior Developers:
---------------------
Database connections are like phone calls - you need to:
1. Establish the connection (dial)
2. Do your work (talk)
3. Close the connection (hang up)

If you don't properly close connections, you'll run out of available
connections (like running out of phone lines). This module handles
all of that automatically using "context managers" (the `with` statement).

Usage:
    from database.connection import DatabaseManager

    db = DatabaseManager()

    # Using context manager (recommended)
    with db.get_session() as session:
        players = session.query(Player).all()
        # Session is automatically closed when we exit the `with` block

    # Or for raw SQL
    results = db.execute_query("SELECT * FROM players WHERE last_name = %s", ("Scheffler",))
"""

from contextlib import contextmanager
from typing import Optional, Any, List, Dict, Generator
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import QueuePool
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import Config


class DatabaseManager:
    """
    Manages database connections and sessions.

    This class provides:
    1. Connection pooling (reusing connections for efficiency)
    2. Automatic retries on connection failures
    3. Session management with proper cleanup
    4. Logging of database operations

    For Junior Developers:
    ---------------------
    Think of this class as a "librarian" for database connections.
    Instead of everyone grabbing connections randomly, the librarian
    keeps track of who has what and makes sure everything is returned.

    Attributes:
        engine: SQLAlchemy engine (the connection pool)
        session_factory: Creates new sessions
        Session: Thread-safe session factory

    Example:
        db = DatabaseManager()

        # Get a session to work with
        with db.get_session() as session:
            player = session.query(Player).filter_by(id=1).first()
            player.age = 30
            session.commit()
        # Session is automatically closed here
    """

    _instance: Optional['DatabaseManager'] = None

    def __new__(cls):
        """
        Singleton pattern - only create one instance.

        This ensures we have a single connection pool shared across
        the entire application, rather than creating new pools everywhere.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the database manager.

        Creates the SQLAlchemy engine with connection pooling and
        sets up the session factory.
        """
        # Only initialize once (singleton pattern)
        if self._initialized:
            return

        self.logger = logger.bind(component='DatabaseManager')
        self._engine = None
        self._session_factory = None
        self._Session = None

        # Initialize the connection
        self._initialize_engine()
        self._initialized = True

    def _initialize_engine(self):
        """
        Create the SQLAlchemy engine with connection pooling.

        For Junior Developers:
        ---------------------
        An "engine" in SQLAlchemy is like a factory that creates
        database connections. We configure it with:
        - pool_size: How many connections to keep ready
        - max_overflow: Extra connections if we need more
        - pool_recycle: How often to refresh connections
        """
        database_url = Config.get_database_url()

        self.logger.info(f"Initializing database connection...")
        self.logger.debug(f"Database URL: {database_url.split('@')[0]}@***")  # Hide password

        try:
            # Create the engine with connection pooling
            self._engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=5,           # Keep 5 connections ready
                max_overflow=10,       # Allow up to 10 more if needed
                pool_recycle=3600,     # Recycle connections every hour
                pool_pre_ping=True,    # Test connections before using
                echo=Config.SQLALCHEMY_ECHO,  # Log SQL if in debug mode
            )

            # Create session factory
            self._session_factory = sessionmaker(bind=self._engine)

            # Create thread-safe session
            self._Session = scoped_session(self._session_factory)

            self.logger.info("Database engine initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize database engine: {e}")
            raise

    @property
    def engine(self):
        """Get the SQLAlchemy engine."""
        return self._engine

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(OperationalError),
        before_sleep=lambda retry_state: logger.warning(
            f"Database connection failed, retrying in {retry_state.next_action.sleep} seconds..."
        )
    )
    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            True if connection is successful

        Raises:
            OperationalError: If connection fails after retries

        For Junior Developers:
        ---------------------
        The @retry decorator automatically retries this method if it fails.
        - stop_after_attempt(3): Try up to 3 times
        - wait_exponential: Wait 1s, then 2s, then 4s between retries
        """
        self.logger.info("Testing database connection...")

        with self._engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()

        self.logger.info("Database connection test successful!")
        return True

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session as a context manager.

        This is the recommended way to work with the database.
        The session is automatically closed when you exit the `with` block.

        Yields:
            SQLAlchemy Session object

        Example:
            with db.get_session() as session:
                players = session.query(Player).all()
                for player in players:
                    print(player.full_name)
            # Session is closed here, even if an error occurred

        For Junior Developers:
        ---------------------
        A "context manager" is Python's way of ensuring cleanup happens.
        The `with` statement guarantees that even if an error occurs,
        the session will be properly closed (like a try/finally block).
        """
        session = self._Session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Database error, rolling back: {e}")
            raise
        except Exception as e:
            session.rollback()
            self.logger.error(f"Unexpected error, rolling back: {e}")
            raise
        finally:
            session.close()

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query and return results.

        Args:
            query: SQL query string (use %s for parameters)
            params: Tuple of parameters to safely insert

        Returns:
            List of dictionaries, one per row

        Example:
            results = db.execute_query(
                "SELECT * FROM players WHERE last_name = :name",
                {"name": "Scheffler"}
            )
            for row in results:
                print(row['full_name'])

        For Junior Developers:
        ---------------------
        NEVER put user input directly into SQL strings! Always use parameters.
        Bad:  f"SELECT * FROM players WHERE name = '{user_input}'"  # SQL injection!
        Good: "SELECT * FROM players WHERE name = :name", {"name": user_input}
        """
        self.logger.debug(f"Executing query: {query[:100]}...")

        with self._engine.connect() as connection:
            if params:
                result = connection.execute(text(query), params)
            else:
                result = connection.execute(text(query))

            # Convert rows to dictionaries
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        self.logger.debug(f"Query returned {len(rows)} rows")
        return rows

    def create_all_tables(self):
        """
        Create all database tables defined in models.

        This is used during initial setup or testing.
        In production, use proper migrations instead.
        """
        from database.models import Base

        self.logger.info("Creating all database tables...")

        try:
            Base.metadata.create_all(self._engine)
            self.logger.info("All tables created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            raise

    def drop_all_tables(self):
        """
        Drop all database tables.

        WARNING: This deletes all data! Only use in development/testing.
        """
        from database.models import Base

        self.logger.warning("Dropping all database tables...")

        try:
            Base.metadata.drop_all(self._engine)
            self.logger.info("All tables dropped")
        except Exception as e:
            self.logger.error(f"Failed to drop tables: {e}")
            raise

    def seed_leagues(self):
        """
        Insert initial league data into the database.

        This populates the leagues table with the tours we're tracking.
        """
        from database.models import League
        from config.leagues import LEAGUES

        self.logger.info("Seeding leagues table...")

        with self.get_session() as session:
            for code, config in LEAGUES.items():
                # Check if league already exists
                existing = session.query(League).filter_by(league_code=code).first()

                if existing:
                    self.logger.debug(f"League {code} already exists, skipping")
                    continue

                # Create new league
                league = League(
                    league_code=code,
                    league_name=config['league_name'],
                    website_url=config['base_url'],
                    is_active=config.get('is_active', True)
                )
                session.add(league)
                self.logger.info(f"Added league: {config['league_name']}")

        self.logger.info("League seeding complete")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database connection pool statistics.

        Returns:
            Dictionary with pool size, checked out connections, etc.

        Useful for monitoring and debugging connection issues.
        """
        pool = self._engine.pool
        return {
            'pool_size': pool.size(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'checked_in': pool.checkedin(),
        }


# ==============================================================================
# Convenience function for quick access
# ==============================================================================
def get_db() -> DatabaseManager:
    """
    Get the database manager instance.

    This is a convenience function that returns the singleton instance.

    Returns:
        DatabaseManager instance

    Example:
        from database.connection import get_db

        db = get_db()
        with db.get_session() as session:
            # Do database work
            pass
    """
    return DatabaseManager()
