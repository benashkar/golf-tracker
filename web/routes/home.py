"""
Home Routes
============

This module defines the routes for the home page and dashboard.

For Junior Developers:
---------------------
Flask "routes" are URL patterns that your application responds to.
When someone visits "/", Flask runs the function decorated with
@home_bp.route('/').

Blueprints group related routes together. The home blueprint
contains the main dashboard and landing page routes.
"""

from flask import Blueprint, render_template
from loguru import logger

from services.player_service import PlayerService
from services.tournament_service import TournamentService

# Create the blueprint
home_bp = Blueprint('home', __name__)

# Initialize services
player_service = PlayerService()
tournament_service = TournamentService()


@home_bp.route('/')
def index():
    """
    Home page / Dashboard.

    Shows:
    - Recent tournament results
    - Upcoming tournaments
    - Quick stats
    """
    logger.debug("Rendering home page")

    try:
        # Get recent results
        recent_results = tournament_service.get_recent_results(days=14)

        # Get upcoming tournaments
        upcoming = tournament_service.get_upcoming_tournaments(days=30)

        return render_template(
            'home.html',
            recent_results=recent_results[:5],  # Top 5
            upcoming_tournaments=upcoming[:5],  # Next 5
        )

    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return render_template(
            'home.html',
            recent_results=[],
            upcoming_tournaments=[],
            error="Could not load data. Please try again later."
        )


@home_bp.route('/about')
def about():
    """About page explaining the project."""
    return render_template('about.html')


@home_bp.route('/search')
def search():
    """
    Global search page.

    Allows searching across players and tournaments.
    """
    from flask import request

    query = request.args.get('q', '')

    if not query:
        return render_template('search.html', query='', results=None)

    # Search players
    player_results = player_service.get_players(
        search_query=query,
        page=1,
        per_page=20
    )

    return render_template(
        'search.html',
        query=query,
        players=player_results['players'],
    )
