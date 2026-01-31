"""
Tournament Routes
==================

This module defines all routes related to tournaments.

Routes:
- /tournaments - List tournaments
- /tournaments/<id> - Tournament detail with full results
- /tournaments/calendar - Calendar view
- /tournaments/recent - Recent results

For Junior Developers:
---------------------
These routes handle tournament-related pages. The tournament detail
page is crucial for the local news use case because it shows:
- Full leaderboard with positions and scores
- Player information including high school data
- The ability to filter players by local connections
"""

from flask import Blueprint, render_template, request, abort
from datetime import datetime
from loguru import logger

from services.tournament_service import TournamentService
from services.news_generator import NewsGenerator

# Create the blueprint
tournaments_bp = Blueprint('tournaments', __name__)

# Initialize services
tournament_service = TournamentService()
news_generator = NewsGenerator()


@tournaments_bp.route('/')
def tournament_list():
    """
    List all tournaments with pagination and filtering.

    Query Parameters:
        page: Page number (default 1)
        per_page: Items per page (default 50)
        year: Filter by year
        league: Filter by league code
        status: Filter by status (scheduled, in_progress, completed)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    league = request.args.get('league', None)
    status = request.args.get('status', None)

    logger.debug(f"Tournament list: year={year}, league={league}, status={status}")

    try:
        result = tournament_service.get_tournaments(
            year=year,
            league_code=league,
            status=status,
            page=page,
            per_page=per_page
        )

        return render_template(
            'tournaments/list.html',
            tournaments=result['tournaments'],
            page=result['page'],
            per_page=result['per_page'],
            total=result['total'],
            total_pages=result['total_pages'],
            selected_year=year,
            selected_league=league,
            selected_status=status,
        )

    except Exception as e:
        logger.error(f"Error loading tournament list: {e}")
        return render_template(
            'tournaments/list.html',
            tournaments=[],
            error="Could not load tournaments."
        )


@tournaments_bp.route('/<int:tournament_id>')
def tournament_detail(tournament_id: int):
    """
    Tournament detail page with full leaderboard.

    Shows:
    - Tournament name, dates, location
    - Course information
    - Full leaderboard with:
      - Position
      - Player name (linked to player detail)
      - Player's high school (for local news angle)
      - Round scores
      - Total score and to-par
      - Earnings

    Query Parameters:
        state: Filter leaderboard by player's high school state
    """
    state_filter = request.args.get('state', None)

    logger.debug(f"Tournament detail: id={tournament_id}, state={state_filter}")

    try:
        tournament = tournament_service.get_tournament_results(
            tournament_id=tournament_id,
            include_player_bio=True
        )

        if not tournament:
            abort(404)

        # Apply state filter to leaderboard if specified
        leaderboard = tournament.get('leaderboard', [])
        if state_filter:
            leaderboard = [
                entry for entry in leaderboard
                if entry.get('player_bio', {}).get('high_school_state', '').lower() == state_filter.lower()
            ]

        # Get unique states for filter dropdown
        all_states = set()
        for entry in tournament.get('leaderboard', []):
            state = entry.get('player_bio', {}).get('high_school_state')
            if state:
                all_states.add(state)

        return render_template(
            'tournaments/detail.html',
            tournament=tournament,
            leaderboard=leaderboard,
            available_states=sorted(all_states),
            state_filter=state_filter,
        )

    except Exception as e:
        logger.error(f"Error loading tournament {tournament_id}: {e}")
        abort(500)


@tournaments_bp.route('/calendar')
def tournament_calendar():
    """
    Calendar view of tournaments for a year.

    Query Parameters:
        year: Year to display (default current year)
        league: Filter by league code
    """
    year = request.args.get('year', datetime.now().year, type=int)
    league = request.args.get('league', None)

    logger.debug(f"Tournament calendar: year={year}, league={league}")

    try:
        calendar = tournament_service.get_tournament_calendar(
            year=year,
            league_code=league
        )

        return render_template(
            'tournaments/calendar.html',
            calendar=calendar,
            selected_year=year,
            selected_league=league,
        )

    except Exception as e:
        logger.error(f"Error loading calendar: {e}")
        return render_template(
            'tournaments/calendar.html',
            calendar={},
            error="Could not load calendar."
        )


@tournaments_bp.route('/recent')
def recent_results():
    """
    Recent tournament results.

    Query Parameters:
        days: Number of days to look back (default 14)
        league: Filter by league code
    """
    days = request.args.get('days', 14, type=int)
    league = request.args.get('league', None)

    logger.debug(f"Recent results: days={days}, league={league}")

    try:
        results = tournament_service.get_recent_results(
            days=days,
            league_code=league
        )

        return render_template(
            'tournaments/recent.html',
            results=results,
            days=days,
            selected_league=league,
        )

    except Exception as e:
        logger.error(f"Error loading recent results: {e}")
        return render_template(
            'tournaments/recent.html',
            results=[],
            error="Could not load results."
        )


@tournaments_bp.route('/upcoming')
def upcoming_tournaments():
    """
    Upcoming tournaments.

    Query Parameters:
        days: Number of days to look ahead (default 30)
        league: Filter by league code
    """
    days = request.args.get('days', 30, type=int)
    league = request.args.get('league', None)

    logger.debug(f"Upcoming tournaments: days={days}, league={league}")

    try:
        tournaments = tournament_service.get_upcoming_tournaments(
            days=days,
            league_code=league
        )

        return render_template(
            'tournaments/upcoming.html',
            tournaments=tournaments,
            days=days,
            selected_league=league,
        )

    except Exception as e:
        logger.error(f"Error loading upcoming tournaments: {e}")
        return render_template(
            'tournaments/upcoming.html',
            tournaments=[],
            error="Could not load tournaments."
        )


@tournaments_bp.route('/<int:tournament_id>/local-news')
def tournament_local_news(tournament_id: int):
    """
    Generate local news package for a tournament.

    This page shows all players with local connections and
    pre-formatted news snippets for each.

    Query Parameters:
        state: High school state to filter by
        city: Hometown city to filter by
    """
    state = request.args.get('state', None)
    city = request.args.get('city', None)

    logger.debug(f"Local news package: tournament={tournament_id}, state={state}, city={city}")

    try:
        tournament = tournament_service.get_tournament(tournament_id)

        if not tournament:
            abort(404)

        package = news_generator.generate_local_news_package(
            tournament_id=tournament_id,
            state=state,
            city=city
        )

        return render_template(
            'tournaments/local_news.html',
            tournament=tournament,
            package=package,
            state_filter=state,
            city_filter=city,
        )

    except Exception as e:
        logger.error(f"Error generating local news: {e}")
        abort(500)
