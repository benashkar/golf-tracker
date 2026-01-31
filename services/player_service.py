"""
Player Service Module
======================

This module provides business logic for player-related operations.
It acts as a layer between the database and the web routes.

For Junior Developers:
---------------------
The "service layer" is a common pattern in software architecture.
It separates business logic from both the database (models) and
the web interface (routes). This makes code:
1. Easier to test (you can test services without web requests)
2. Reusable (multiple routes can use the same service)
3. Maintainable (business logic is in one place)

Usage:
    from services.player_service import PlayerService

    service = PlayerService()

    # Get a player by ID
    player = service.get_player(player_id=123)

    # Search players by high school
    players = service.search_by_high_school(state="Texas")

    # Get player's tournament history
    history = service.get_player_tournament_history(player_id=123, year=2025)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from loguru import logger

from database.connection import DatabaseManager
from database.models import Player, PlayerLeague, League, TournamentResult, Tournament


class PlayerService:
    """
    Service class for player-related operations.

    This class provides methods for:
    - Retrieving player information
    - Searching players by various criteria
    - Getting player tournament history
    - Generating player statistics

    For Junior Developers:
    ---------------------
    Notice that this class uses dependency injection - we pass in
    the database manager rather than creating it inside. This makes
    testing easier (we can pass a mock database in tests).

    Attributes:
        db: DatabaseManager instance for database access
        logger: Logger for this service
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initialize the player service.

        Args:
            db: Optional database manager (creates one if not provided)
        """
        self.db = db or DatabaseManager()
        self.logger = logger.bind(service='PlayerService')

    def get_player(
        self,
        player_id: int,
        include_leagues: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get a player by their ID.

        Args:
            player_id: The player's database ID
            include_leagues: Whether to include league information

        Returns:
            Dictionary with player data, or None if not found

        Example:
            player = service.get_player(123)
            if player:
                print(player['full_name'])
                print(player['news_blurb'])
        """
        self.logger.debug(f"Getting player {player_id}")

        with self.db.get_session() as session:
            query = session.query(Player)

            if include_leagues:
                query = query.options(
                    joinedload(Player.player_leagues).joinedload(PlayerLeague.league)
                )

            player = query.filter(Player.player_id == player_id).first()

            if not player:
                return None

            return self._player_to_dict(player, include_leagues)

    def get_players(
        self,
        page: int = 1,
        per_page: int = 50,
        league_code: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a paginated list of players.

        Args:
            page: Page number (1-based)
            per_page: Number of players per page
            league_code: Optional filter by league
            search_query: Optional search by name

        Returns:
            Dictionary with:
            - players: List of player dictionaries
            - total: Total number of matching players
            - page: Current page
            - per_page: Items per page
            - total_pages: Total number of pages
        """
        self.logger.debug(f"Getting players page {page}")

        with self.db.get_session() as session:
            query = session.query(Player)

            # Apply filters
            if league_code:
                query = query.join(Player.player_leagues).join(PlayerLeague.league).filter(
                    League.league_code == league_code.upper()
                )

            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Player.first_name.ilike(search_term),
                        Player.last_name.ilike(search_term),
                    )
                )

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (page - 1) * per_page
            players = query.order_by(Player.last_name).offset(offset).limit(per_page).all()

            return {
                'players': [self._player_to_dict(p, include_leagues=False) for p in players],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }

    def search_by_high_school(
        self,
        school_name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        graduation_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search players by high school information.

        Args:
            school_name: High school name (partial match)
            city: High school city
            state: High school state
            graduation_year: Graduation year

        Returns:
            List of matching player dictionaries

        Example:
            # Find all players from Texas high schools
            players = service.search_by_high_school(state="Texas")

            # Find players from a specific school
            players = service.search_by_high_school(
                school_name="Highland Park",
                state="Texas"
            )
        """
        self.logger.debug(f"Searching by high school: {school_name}, {city}, {state}")

        with self.db.get_session() as session:
            query = session.query(Player)

            filters = []

            if school_name:
                filters.append(Player.high_school_name.ilike(f"%{school_name}%"))

            if city:
                filters.append(Player.high_school_city.ilike(f"%{city}%"))

            if state:
                filters.append(Player.high_school_state.ilike(f"%{state}%"))

            if graduation_year:
                filters.append(Player.high_school_graduation_year == graduation_year)

            if filters:
                query = query.filter(and_(*filters))

            # Only return players with high school info
            query = query.filter(Player.high_school_name.isnot(None))

            players = query.order_by(
                Player.high_school_state,
                Player.high_school_name,
                Player.last_name
            ).all()

            return [self._player_to_dict(p) for p in players]

    def search_by_college(
        self,
        college_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search players by college.

        Args:
            college_name: College name (partial match)

        Returns:
            List of matching player dictionaries
        """
        self.logger.debug(f"Searching by college: {college_name}")

        with self.db.get_session() as session:
            query = session.query(Player).filter(
                Player.college_name.isnot(None)
            )

            if college_name:
                query = query.filter(
                    Player.college_name.ilike(f"%{college_name}%")
                )

            players = query.order_by(Player.college_name, Player.last_name).all()

            return [self._player_to_dict(p) for p in players]

    def search_by_hometown(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search players by hometown.

        Args:
            city: Hometown city
            state: Hometown state
            country: Hometown country

        Returns:
            List of matching player dictionaries
        """
        self.logger.debug(f"Searching by hometown: {city}, {state}, {country}")

        with self.db.get_session() as session:
            query = session.query(Player)

            filters = []

            if city:
                filters.append(Player.hometown_city.ilike(f"%{city}%"))

            if state:
                filters.append(Player.hometown_state.ilike(f"%{state}%"))

            if country:
                filters.append(Player.hometown_country.ilike(f"%{country}%"))

            if filters:
                query = query.filter(and_(*filters))

            players = query.order_by(
                Player.hometown_state,
                Player.hometown_city,
                Player.last_name
            ).all()

            return [self._player_to_dict(p) for p in players]

    def get_player_tournament_history(
        self,
        player_id: int,
        year: Optional[int] = None,
        league_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a player's tournament history.

        Args:
            player_id: The player's database ID
            year: Optional filter by year
            league_code: Optional filter by league

        Returns:
            List of tournament result dictionaries

        Example:
            # Get all 2025 results for a player
            history = service.get_player_tournament_history(
                player_id=123,
                year=2025
            )
            for result in history:
                print(f"{result['tournament_name']}: {result['final_position_display']}")
        """
        self.logger.debug(f"Getting tournament history for player {player_id}")

        with self.db.get_session() as session:
            query = session.query(TournamentResult).join(
                Tournament
            ).filter(
                TournamentResult.player_id == player_id
            )

            if year:
                query = query.filter(Tournament.tournament_year == year)

            if league_code:
                query = query.join(League).filter(
                    League.league_code == league_code.upper()
                )

            results = query.options(
                joinedload(TournamentResult.tournament).joinedload(Tournament.league)
            ).order_by(
                Tournament.start_date.desc()
            ).all()

            return [self._result_to_dict(r) for r in results]

    def get_player_stats(self, player_id: int, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get aggregate statistics for a player.

        Args:
            player_id: The player's database ID
            year: Optional year filter

        Returns:
            Dictionary with player statistics
        """
        with self.db.get_session() as session:
            query = session.query(TournamentResult).join(
                Tournament
            ).filter(
                TournamentResult.player_id == player_id
            )

            if year:
                query = query.filter(Tournament.tournament_year == year)

            results = query.all()

            if not results:
                return {
                    'tournaments_played': 0,
                    'wins': 0,
                    'top_10': 0,
                    'cuts_made': 0,
                    'total_earnings': 0,
                }

            wins = sum(1 for r in results if r.final_position == 1)
            top_10 = sum(1 for r in results if r.final_position and r.final_position <= 10)
            cuts_made = sum(1 for r in results if r.made_cut)
            total_earnings = sum(float(r.earnings or 0) for r in results)

            return {
                'tournaments_played': len(results),
                'wins': wins,
                'top_10': top_10,
                'cuts_made': cuts_made,
                'total_earnings': total_earnings,
            }

    def _player_to_dict(
        self,
        player: Player,
        include_leagues: bool = True
    ) -> Dict[str, Any]:
        """
        Convert a Player model to a dictionary.

        Args:
            player: Player model instance
            include_leagues: Whether to include league information

        Returns:
            Dictionary with player data
        """
        data = {
            'player_id': player.player_id,
            'first_name': player.first_name,
            'last_name': player.last_name,
            'full_name': player.full_name,
            'birth_date': player.birth_date.isoformat() if player.birth_date else None,
            'age': player.age,

            # High school info (critical for local news)
            'high_school_name': player.high_school_name,
            'high_school_city': player.high_school_city,
            'high_school_state': player.high_school_state,
            'high_school_graduation_year': player.high_school_graduation_year,
            'high_school_full': player.high_school_full,

            # Hometown
            'hometown_city': player.hometown_city,
            'hometown_state': player.hometown_state,
            'hometown_country': player.hometown_country,

            # College
            'college_name': player.college_name,
            'college_graduation_year': player.college_graduation_year,

            # News blurb
            'news_blurb': player.news_blurb,

            # Profile
            'profile_image_url': player.profile_image_url,
            'wikipedia_url': player.wikipedia_url,

            # External IDs
            'pga_tour_id': player.pga_tour_id,
        }

        if include_leagues and player.player_leagues:
            data['leagues'] = [
                {
                    'league_code': pl.league.league_code,
                    'league_name': pl.league.league_name,
                    'is_current': pl.is_current_member,
                }
                for pl in player.player_leagues
            ]

        return data

    def _result_to_dict(self, result: TournamentResult) -> Dict[str, Any]:
        """
        Convert a TournamentResult model to a dictionary.

        Args:
            result: TournamentResult model instance

        Returns:
            Dictionary with result data
        """
        tournament = result.tournament

        return {
            'result_id': result.result_id,
            'tournament_id': tournament.tournament_id,
            'tournament_name': tournament.tournament_name,
            'tournament_year': tournament.tournament_year,
            'league_name': tournament.league.league_name if tournament.league else None,
            'start_date': tournament.start_date.isoformat() if tournament.start_date else None,
            'course_name': tournament.course_name,
            'city': tournament.city,
            'state': tournament.state,

            'final_position': result.final_position,
            'final_position_display': result.final_position_display,
            'total_score': result.total_score,
            'total_to_par': result.total_to_par,
            'to_par_display': result.to_par_display,

            'round_1_score': result.round_1_score,
            'round_2_score': result.round_2_score,
            'round_3_score': result.round_3_score,
            'round_4_score': result.round_4_score,

            'made_cut': result.made_cut,
            'status': result.status,
            'earnings': float(result.earnings) if result.earnings else None,
            'points_earned': float(result.points_earned) if result.points_earned else None,
        }
