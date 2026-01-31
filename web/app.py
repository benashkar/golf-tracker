"""
Flask Application Factory
==========================

This module creates and configures the Flask web application.

For Junior Developers:
---------------------
The "application factory" pattern means we have a function that creates
the Flask app, rather than creating it at module level. This makes testing
easier and allows us to create multiple instances with different configs.

Benefits:
1. Easier testing (create app with test config)
2. Multiple instances possible
3. Delayed configuration (load config at runtime)

Usage:
    from web.app import create_app

    app = create_app()
    app.run()

    # Or with specific config
    app = create_app(config_class=TestingConfig)
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from loguru import logger
import sys

from config.settings import Config, get_config

# ==============================================================================
# SQLAlchemy Extension
# ==============================================================================
# Create SQLAlchemy instance (but don't initialize yet)
# This allows the extension to be used across the application
db = SQLAlchemy()


def create_app(config_class=None):
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class to use (defaults to auto-detect)

    Returns:
        Configured Flask application

    Example:
        # Production
        app = create_app()

        # Testing
        from config.settings import TestingConfig
        app = create_app(TestingConfig)
    """
    # Create Flask app
    app = Flask(__name__)

    # ===========================================================================
    # Configuration
    # ===========================================================================
    # Load configuration
    if config_class is None:
        config_class = get_config()

    app.config.from_object(config_class)

    # ===========================================================================
    # Logging Setup
    # ===========================================================================
    # Configure loguru to work with Flask
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=Config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # Add file logging
    try:
        logger.add(
            Config.LOG_FILE,
            rotation="10 MB",
            retention="7 days",
            level=Config.LOG_LEVEL,
        )
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}")

    logger.info("Creating Flask application...")

    # ===========================================================================
    # Initialize Extensions
    # ===========================================================================
    db.init_app(app)

    # ===========================================================================
    # Register Blueprints
    # ===========================================================================
    # Blueprints are like mini-applications that group related routes
    from web.routes.home import home_bp
    from web.routes.players import players_bp
    from web.routes.tournaments import tournaments_bp
    from web.routes.api import api_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(players_bp, url_prefix='/players')
    app.register_blueprint(tournaments_bp, url_prefix='/tournaments')
    app.register_blueprint(api_bp, url_prefix='/api')

    # ===========================================================================
    # Context Processors
    # ===========================================================================
    @app.context_processor
    def inject_globals():
        """
        Inject global variables into all templates.

        This makes certain variables available in every template without
        having to pass them explicitly.
        """
        from datetime import datetime
        return {
            'current_year': datetime.now().year,
            'app_name': 'Golf Tracker',
        }

    # ===========================================================================
    # Error Handlers
    # ===========================================================================
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        from flask import render_template
        db.session.rollback()  # Rollback any failed transactions
        return render_template('errors/500.html'), 500

    logger.info("Flask application created successfully")

    return app


# ==============================================================================
# CLI Commands
# ==============================================================================
def register_cli_commands(app):
    """
    Register CLI commands with the Flask app.

    This allows running commands like:
        flask init-db
        flask scrape --league PGA
    """
    @app.cli.command()
    def init_db():
        """Initialize the database."""
        from database.connection import DatabaseManager

        click.echo("Initializing database...")
        db_manager = DatabaseManager()
        db_manager.create_all_tables()
        db_manager.seed_leagues()
        click.echo("Database initialized!")


# ==============================================================================
# Application Entry Point
# ==============================================================================
if __name__ == '__main__':
    # This runs when you execute: python -m web.app
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
