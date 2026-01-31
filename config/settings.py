"""
Configuration Settings Module
==============================

This module manages all configuration settings for the Golf Tracker application.
It loads settings from environment variables and provides sensible defaults.

For Junior Developers:
---------------------
Configuration management is crucial for production applications because:
1. Different environments (dev, test, prod) need different settings
2. Sensitive data (passwords, API keys) should never be in code
3. Settings should be easy to change without modifying code

We use environment variables loaded from a .env file for local development.
In production (Render, Heroku, etc.), these are set in the hosting dashboard.

Usage:
    from config.settings import Config

    # Access settings
    database_url = Config.DATABASE_URL
    debug_mode = Config.DEBUG

Environment Variables:
    See .env.example for all available settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==============================================================================
# Load Environment Variables
# ==============================================================================
# Find the project root directory (where .env file should be)
# Path(__file__) gives us the path to this file (settings.py)
# .parent.parent goes up two directories to the project root
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env file if it exists
# This only affects local development - production uses real env vars
env_path = PROJECT_ROOT / '.env'
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """
    Base configuration class with all settings.

    This class reads from environment variables and provides defaults.
    All settings are class attributes, so you access them like:
        Config.DATABASE_URL

    For Junior Developers:
    ---------------------
    os.getenv('NAME', 'default') reads the environment variable 'NAME'.
    If it doesn't exist, it returns 'default' instead.

    We use class attributes (not instance attributes) so you don't need
    to create an instance of Config - just import and use directly.
    """

    # ==========================================================================
    # Project Paths
    # ==========================================================================
    # These help us reference files relative to the project root
    PROJECT_ROOT = PROJECT_ROOT
    LOGS_DIR = PROJECT_ROOT / 'logs'

    # ==========================================================================
    # Database Configuration
    # ==========================================================================
    # DATABASE_URL is the full connection string used by SQLAlchemy
    # Format: mysql+pymysql://user:password@host:port/database
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'mysql+pymysql://golf_tracker:password@localhost:3306/golf_tracker'
    )

    # Individual database components (for when you need them separately)
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
    MYSQL_USER = os.getenv('MYSQL_USER', 'golf_tracker')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'password')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'golf_tracker')

    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable event system (uses less memory)
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'

    # Connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,           # Number of connections to keep open
        'pool_recycle': 3600,     # Recycle connections after 1 hour
        'pool_pre_ping': True,    # Test connections before using them
    }

    # ==========================================================================
    # Flask Configuration
    # ==========================================================================
    # Secret key for session encryption - CHANGE THIS IN PRODUCTION!
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Flask environment and debug mode
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'

    # ==========================================================================
    # Scraping Configuration
    # ==========================================================================
    # Delay between HTTP requests (in seconds)
    # This is important to be respectful to the websites we're scraping
    SCRAPE_DELAY_SECONDS = float(os.getenv('SCRAPE_DELAY_SECONDS', '2'))

    # User agent string sent with HTTP requests
    # This identifies our scraper to websites
    USER_AGENT = os.getenv(
        'USER_AGENT',
        'GolfTracker/1.0 (Local News Research; github.com/golf-tracker)'
    )

    # Request timeout in seconds
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # Maximum retries for failed requests
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

    # ==========================================================================
    # Notification Configuration
    # ==========================================================================
    # Slack webhook for sending notifications
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')

    # Email for notifications
    NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL', '')

    # ==========================================================================
    # Logging Configuration
    # ==========================================================================
    # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Log file path
    LOG_FILE = os.getenv('LOG_FILE', 'logs/golf_tracker.log')

    # ==========================================================================
    # League-Specific URLs
    # ==========================================================================
    # Base URLs for each golf tour's website
    PGA_TOUR_BASE_URL = 'https://www.pgatour.com'
    DP_WORLD_TOUR_BASE_URL = 'https://www.europeantour.com'
    KORN_FERRY_BASE_URL = 'https://www.pgatour.com/korn-ferry-tour'
    LPGA_BASE_URL = 'https://www.lpga.com'
    LIV_GOLF_BASE_URL = 'https://www.livgolf.com'
    CHAMPIONS_TOUR_BASE_URL = 'https://www.pgatour.com/champions'

    @classmethod
    def get_database_url(cls) -> str:
        """
        Get the database URL, building it from components if needed.

        Returns:
            str: The database connection URL

        For Junior Developers:
        ---------------------
        This method first checks if DATABASE_URL is set directly.
        If not, it builds the URL from the individual components
        (host, port, user, password, database name).

        The @classmethod decorator means this method can be called
        on the class itself: Config.get_database_url()
        """
        if cls.DATABASE_URL and cls.DATABASE_URL != 'mysql+pymysql://golf_tracker:password@localhost:3306/golf_tracker':
            return cls.DATABASE_URL

        # Build URL from components
        return (
            f"mysql+pymysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}"
            f"@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}"
        )


class DevelopmentConfig(Config):
    """
    Development configuration - used for local development.

    Inherits all settings from Config and overrides specific ones
    for the development environment.
    """
    DEBUG = True
    FLASK_ENV = 'development'
    SQLALCHEMY_ECHO = True  # Log all SQL queries (helpful for debugging)


class ProductionConfig(Config):
    """
    Production configuration - used for the live application.

    This configuration is more strict and secure.
    """
    DEBUG = False
    FLASK_ENV = 'production'
    SQLALCHEMY_ECHO = False  # Don't log SQL queries in production

    # In production, we require the secret key to be set
    @classmethod
    def validate(cls):
        """Validate that required production settings are set."""
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production! "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


class TestingConfig(Config):
    """
    Testing configuration - used when running pytest.

    Uses an in-memory SQLite database for fast tests.
    """
    TESTING = True
    DEBUG = True

    # Use SQLite in-memory database for tests (fast!)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    DATABASE_URL = 'sqlite:///:memory:'

    # Disable CSRF protection in tests
    WTF_CSRF_ENABLED = False


# ==============================================================================
# Configuration Factory
# ==============================================================================
# This dictionary maps environment names to configuration classes
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """
    Get the appropriate configuration based on FLASK_ENV.

    Returns:
        The configuration class for the current environment.

    Example:
        config = get_config()
        print(config.DEBUG)  # True if in development
    """
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
