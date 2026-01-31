"""
WSGI Entry Point for Production Deployment
==========================================

This module creates the Flask application for WSGI servers like gunicorn.
It avoids shell parsing issues with the application factory pattern.

Usage:
    gunicorn --bind 0.0.0.0:$PORT wsgi:app
"""

from web.app import create_app

# Create the application instance
app = create_app()

if __name__ == "__main__":
    app.run()
