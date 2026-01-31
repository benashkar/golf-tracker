"""
API Routes
===========

This module defines JSON API endpoints for the Golf Tracker application.

These endpoints can be used by:
- Frontend JavaScript for dynamic updates
- Third-party applications
- Mobile apps
- Other integrations

For Junior Developers:
---------------------
REST APIs return data in JSON format instead of HTML.
This is useful for:
1. AJAX requests from the frontend
2. Mobile applications
3. Integration with other systems

The pattern is:
- GET /api/players - List players (JSON)
- GET /api/players/<id> - Get single player (JSON)
- etc.
"""

from flask import Blueprint, jsonify, request, abort
from datetime import datetime
from loguru import logger

from services.player_service import PlayerService
from services.tournament_service import TournamentService
from services.news_generator import NewsGenerator

# Create the blueprint
api_bp = Blueprint('api', __name__)

# Initialize services
player_service = PlayerService()
tournament_service = TournamentService()
news_generator = NewsGenerator()


# ==============================================================================
# Player API Endpoints
# ==============================================================================

@api_bp.route('/players')
def api_players():
    """
    Get a list of players.

    Query Parameters:
        page: Page number (default 1)
        per_page: Items per page (default 50)
        league: Filter by league code
        q: Search query

    Returns:
        JSON with players list and pagination info
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    league = request.args.get('league', None)
    search_query = request.args.get('q', None)

    try:
        result = player_service.get_players(
            page=page,
            per_page=per_page,
            league_code=league,
            search_query=search_query
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"API error - players list: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/players/<int:player_id>')
def api_player_detail(player_id: int):
    """
    Get a single player's details.

    Returns:
        JSON with player data
    """
    try:
        player = player_service.get_player(player_id, include_leagues=True)

        if not player:
            return jsonify({'error': 'Player not found'}), 404

        return jsonify(player)

    except Exception as e:
        logger.error(f"API error - player detail: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/players/<int:player_id>/history')
def api_player_history(player_id: int):
    """
    Get a player's tournament history.

    Query Parameters:
        year: Filter by year
        league: Filter by league code

    Returns:
        JSON with tournament results
    """
    year = request.args.get('year', None, type=int)
    league = request.args.get('league', None)

    try:
        history = player_service.get_player_tournament_history(
            player_id=player_id,
            year=year,
            league_code=league
        )

        return jsonify({
            'player_id': player_id,
            'year': year,
            'results': history
        })

    except Exception as e:
        logger.error(f"API error - player history: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/players/search')
def api_player_search():
    """
    Search players by various criteria.

    Query Parameters:
        high_school: High school name
        hs_state: High school state
        college: College name
        hometown_state: Hometown state

    Returns:
        JSON with matching players
    """
    hs_name = request.args.get('high_school', None)
    hs_state = request.args.get('hs_state', None)
    college = request.args.get('college', None)
    hometown_state = request.args.get('hometown_state', None)

    try:
        if college:
            players = player_service.search_by_college(college_name=college)
        elif hometown_state:
            players = player_service.search_by_hometown(state=hometown_state)
        else:
            players = player_service.search_by_high_school(
                school_name=hs_name,
                state=hs_state
            )

        return jsonify({
            'count': len(players),
            'players': players
        })

    except Exception as e:
        logger.error(f"API error - player search: {e}")
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# Tournament API Endpoints
# ==============================================================================

@api_bp.route('/tournaments')
def api_tournaments():
    """
    Get a list of tournaments.

    Query Parameters:
        page: Page number
        per_page: Items per page
        year: Filter by year
        league: Filter by league code
        status: Filter by status

    Returns:
        JSON with tournaments list and pagination info
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    year = request.args.get('year', None, type=int)
    league = request.args.get('league', None)
    status = request.args.get('status', None)

    try:
        result = tournament_service.get_tournaments(
            year=year,
            league_code=league,
            status=status,
            page=page,
            per_page=per_page
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"API error - tournaments list: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tournaments/<int:tournament_id>')
def api_tournament_detail(tournament_id: int):
    """
    Get a tournament's details and results.

    Returns:
        JSON with tournament data and leaderboard
    """
    try:
        tournament = tournament_service.get_tournament_results(
            tournament_id=tournament_id,
            include_player_bio=True
        )

        if not tournament:
            return jsonify({'error': 'Tournament not found'}), 404

        return jsonify(tournament)

    except Exception as e:
        logger.error(f"API error - tournament detail: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tournaments/upcoming')
def api_upcoming_tournaments():
    """
    Get upcoming tournaments.

    Query Parameters:
        days: Days to look ahead (default 30)
        league: Filter by league code

    Returns:
        JSON with upcoming tournaments
    """
    days = request.args.get('days', 30, type=int)
    league = request.args.get('league', None)

    try:
        tournaments = tournament_service.get_upcoming_tournaments(
            days=days,
            league_code=league
        )

        return jsonify({
            'days': days,
            'count': len(tournaments),
            'tournaments': tournaments
        })

    except Exception as e:
        logger.error(f"API error - upcoming tournaments: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tournaments/recent')
def api_recent_results():
    """
    Get recent tournament results.

    Query Parameters:
        days: Days to look back (default 14)
        league: Filter by league code

    Returns:
        JSON with recent results
    """
    days = request.args.get('days', 14, type=int)
    league = request.args.get('league', None)

    try:
        results = tournament_service.get_recent_results(
            days=days,
            league_code=league
        )

        return jsonify({
            'days': days,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logger.error(f"API error - recent results: {e}")
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# News Generation API Endpoints
# ==============================================================================

@api_bp.route('/news/player-intro/<int:player_id>')
def api_player_intro(player_id: int):
    """
    Generate a news-ready player introduction.

    Returns:
        JSON with the formatted introduction text
    """
    try:
        intro = news_generator.generate_player_intro(player_id)

        if not intro:
            return jsonify({'error': 'Player not found'}), 404

        return jsonify({
            'player_id': player_id,
            'intro': intro
        })

    except Exception as e:
        logger.error(f"API error - player intro: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/news/result-snippet/<int:player_id>/<int:tournament_id>')
def api_result_snippet(player_id: int, tournament_id: int):
    """
    Generate a news snippet for a player's tournament result.

    Returns:
        JSON with the formatted news snippet
    """
    try:
        snippet = news_generator.generate_result_snippet(
            player_id=player_id,
            tournament_id=tournament_id,
            include_bio=True,
            include_scores=True
        )

        if not snippet:
            return jsonify({'error': 'Result not found'}), 404

        return jsonify({
            'player_id': player_id,
            'tournament_id': tournament_id,
            'snippet': snippet
        })

    except Exception as e:
        logger.error(f"API error - result snippet: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/news/local-package/<int:tournament_id>')
def api_local_news_package(tournament_id: int):
    """
    Generate a local news package for a tournament.

    Query Parameters:
        state: High school state filter
        city: Hometown city filter

    Returns:
        JSON with news snippets for local players
    """
    state = request.args.get('state', None)
    city = request.args.get('city', None)

    try:
        package = news_generator.generate_local_news_package(
            tournament_id=tournament_id,
            state=state,
            city=city
        )

        return jsonify({
            'tournament_id': tournament_id,
            'state_filter': state,
            'city_filter': city,
            'count': len(package),
            'players': package
        })

    except Exception as e:
        logger.error(f"API error - local news package: {e}")
        return jsonify({'error': str(e)}), 500


# ==============================================================================
# Health Check
# ==============================================================================

@api_bp.route('/health')
def api_health():
    """
    Health check endpoint.

    Returns:
        JSON with status and timestamp
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'golf-tracker'
    })
