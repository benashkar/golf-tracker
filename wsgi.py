"""
WSGI Entry Point for Production Deployment
==========================================

This module creates the Flask application for WSGI servers like gunicorn.
It avoids shell parsing issues with the application factory pattern.

Usage:
    gunicorn --bind 0.0.0.0:$PORT wsgi:app
"""

from web.app import create_app, db
from loguru import logger

# Create the application instance
app = create_app()

# Initialize database tables on startup
with app.app_context():
    try:
        # Import models to ensure they're registered
        from database.models import Base, League

        # Get the engine from Flask-SQLAlchemy
        engine = db.engine

        # Create all tables using the models' Base metadata
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")

        # Seed leagues if not already present
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            count = session.query(League).count()
            if count == 0:
                leagues_data = [
                    ('PGA', 'PGA Tour', 'https://www.pgatour.com'),
                    ('LPGA', 'LPGA Tour', 'https://www.lpga.com'),
                    ('DP', 'DP World Tour', 'https://www.europeantour.com'),
                    ('KF', 'Korn Ferry Tour', 'https://www.pgatour.com/korn-ferry-tour'),
                    ('LIV', 'LIV Golf', 'https://www.livgolf.com'),
                    ('CHAMP', 'PGA Tour Champions', 'https://www.pgatour.com/champions'),
                ]
                for code, name, url in leagues_data:
                    league = League(league_code=code, league_name=name, website_url=url)
                    session.add(league)
                session.commit()
                logger.info("Leagues seeded successfully")
            else:
                logger.info(f"Leagues already exist ({count} found)")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    app.run()
