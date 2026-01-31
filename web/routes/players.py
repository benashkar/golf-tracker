"""
Player Routes
==============

This module defines all routes related to players.

Routes:
- /players - List all players
- /players/<id> - Player detail page
- /players/search - Search page with filters
- /players/by-school/<school_name> - Players from a specific school

For Junior Developers:
---------------------
These routes handle the player-related pages of the application.
The player detail page is especially important because it shows:
- Player biographical info (high school, college, hometown)
- Tournament history
- The pre-formatted news snippet
"""

from flask import Blueprint, render_template, request, abort
from loguru import logger

from services.player_service import PlayerService
from services.news_generator import NewsGenerator

# Create the blueprint
players_bp = Blueprint('players', __name__)

# Initialize services
player_service = PlayerService()
news_generator = NewsGenerator()


@players_bp.route('/')
def player_list():
    """
    List all players with pagination and filtering.

    Query Parameters:
        page: Page number (default 1)
        per_page: Items per page (default 50)
        league: Filter by league code
        q: Search query
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    league = request.args.get('league', None)
    search_query = request.args.get('q', None)

    logger.debug(f"Player list: page={page}, league={league}, q={search_query}")

    try:
        result = player_service.get_players(
            page=page,
            per_page=per_page,
            league_code=league,
            search_query=search_query
        )

        return render_template(
            'players/list.html',
            players=result['players'],
            page=result['page'],
            per_page=result['per_page'],
            total=result['total'],
            total_pages=result['total_pages'],
            league=league,
            search_query=search_query,
        )

    except Exception as e:
        logger.error(f"Error loading player list: {e}")
        return render_template(
            'players/list.html',
            players=[],
            error="Could not load players."
        )


@players_bp.route('/<int:player_id>')
def player_detail(player_id: int):
    """
    Player detail page.

    Shows:
    - Player photo and basic info
    - High school, graduation year, city/state (prominently displayed)
    - Hometown and college info
    - Tournament history for selected year
    - Pre-formatted news snippet

    This is THE KEY PAGE for local news research.
    """
    year = request.args.get('year', None, type=int)

    logger.debug(f"Player detail: id={player_id}, year={year}")

    try:
        player = player_service.get_player(player_id, include_leagues=True)

        if not player:
            abort(404)

        # Get tournament history
        history = player_service.get_player_tournament_history(
            player_id=player_id,
            year=year
        )

        # Get player stats
        stats = player_service.get_player_stats(player_id, year=year)

        # Generate news intro
        news_intro = news_generator.generate_player_intro(player_id)

        return render_template(
            'players/detail.html',
            player=player,
            tournament_history=history,
            stats=stats,
            news_intro=news_intro,
            selected_year=year,
        )

    except Exception as e:
        logger.error(f"Error loading player {player_id}: {e}")
        abort(500)


@players_bp.route('/search')
def player_search():
    """
    Player search page with filters.

    Allows searching by:
    - High school name
    - High school city
    - High school state
    - Graduation year
    - College
    - Hometown
    """
    # Get filter parameters
    hs_name = request.args.get('high_school', None)
    hs_city = request.args.get('hs_city', None)
    hs_state = request.args.get('hs_state', None)
    grad_year = request.args.get('grad_year', None, type=int)
    college = request.args.get('college', None)
    hometown_city = request.args.get('hometown_city', None)
    hometown_state = request.args.get('hometown_state', None)

    players = []
    searched = False

    # Only search if at least one filter is provided
    if any([hs_name, hs_city, hs_state, grad_year, college, hometown_city, hometown_state]):
        searched = True

        if college:
            players = player_service.search_by_college(college_name=college)
        elif hometown_city or hometown_state:
            players = player_service.search_by_hometown(
                city=hometown_city,
                state=hometown_state
            )
        else:
            players = player_service.search_by_high_school(
                school_name=hs_name,
                city=hs_city,
                state=hs_state,
                graduation_year=grad_year
            )

    return render_template(
        'players/search.html',
        players=players,
        searched=searched,
        filters={
            'high_school': hs_name,
            'hs_city': hs_city,
            'hs_state': hs_state,
            'grad_year': grad_year,
            'college': college,
            'hometown_city': hometown_city,
            'hometown_state': hometown_state,
        }
    )


@players_bp.route('/by-school/<path:school_name>')
def players_by_school(school_name: str):
    """
    Get all players from a specific high school.

    URL Example:
        /players/by-school/Highland Park High School
    """
    logger.debug(f"Players by school: {school_name}")

    try:
        players = player_service.search_by_high_school(school_name=school_name)

        return render_template(
            'players/by_school.html',
            school_name=school_name,
            players=players,
        )

    except Exception as e:
        logger.error(f"Error searching by school: {e}")
        return render_template(
            'players/by_school.html',
            school_name=school_name,
            players=[],
            error="Could not search players."
        )


@players_bp.route('/by-state/<state>')
def players_by_state(state: str):
    """
    Get all players from high schools in a specific state.

    URL Example:
        /players/by-state/Texas
    """
    logger.debug(f"Players by state: {state}")

    try:
        players = player_service.search_by_high_school(state=state)

        return render_template(
            'players/by_state.html',
            state=state,
            players=players,
        )

    except Exception as e:
        logger.error(f"Error searching by state: {e}")
        return render_template(
            'players/by_state.html',
            state=state,
            players=[],
            error="Could not search players."
        )


@players_bp.route('/by-college/<path:college_name>')
def players_by_college(college_name: str):
    """
    Get all players from a specific college.

    URL Example:
        /players/by-college/University of Texas
    """
    logger.debug(f"Players by college: {college_name}")

    try:
        players = player_service.search_by_college(college_name=college_name)

        return render_template(
            'players/by_college.html',
            college_name=college_name,
            players=players,
        )

    except Exception as e:
        logger.error(f"Error searching by college: {e}")
        return render_template(
            'players/by_college.html',
            college_name=college_name,
            players=[],
            error="Could not search players."
        )
