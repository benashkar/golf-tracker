"""
Tournament Service Module
==========================

This module provides business logic for tournament-related operations.
It handles tournament listings, results, and leaderboard data.

For Junior Developers:
---------------------
This service provides methods for:
1. Getting tournament schedules
2. Retrieving tournament results (leaderboards)
3. Filtering tournaments by league, year, status
4. Getting upcoming and recent tournaments

Usage:
    from services.tournament_service import TournamentService

    service = TournamentService()

    # Get all 2025 PGA Tour tournaments
    tournaments = service.get_tournaments(year=2025, league_code='PGA')

    # Get full results for a tournament
    results = service.get_tournament_results(tournament_id=123)

    # Get upcoming tournaments
    upcoming = service.get_upcoming_tournaments(days=14)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import joinedload
from loguru import logger

from database.connection import DatabaseManager
from database.models import Tournament, TournamentResult, Player, League


class TournamentService:
    """
    Service class for tournament-related operations.

    This class provides methods for:
    - Listing tournaments with filters
    - Getting tournament details and results
    - Finding upcoming and recent tournaments
    - Generating tournament statistics

    Attributes:
        db: DatabaseManager instance for database access
        logger: Logger for this service
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initialize the tournament service.

        Args:
            db: Optional database manager (creates one if not provided)
        """
        self.db = db or DatabaseManager()
        self.logger = logger.bind(service='TournamentService')

    def get_tournament(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a tournament by its ID.

        Args:
            tournament_id: The tournament's database ID

        Returns:
            Dictionary with tournament data, or None if not found
        """
        self.logger.debug(f"Getting tournament {tournament_id}")

        with self.db.get_session() as session:
            tournament = session.query(Tournament).options(
                joinedload(Tournament.league)
            ).filter(
                Tournament.tournament_id == tournament_id
            ).first()

            if not tournament:
                return None

            return self._tournament_to_dict(tournament)

    def get_tournaments(
        self,
        year: Optional[int] = None,
        league_code: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Get a paginated list of tournaments.

        Args:
            year: Filter by year
            league_code: Filter by league (e.g., 'PGA', 'LPGA')
            status: Filter by status ('scheduled', 'in_progress', 'completed')
            page: Page number (1-based)
            per_page: Items per page

        Returns:
            Dictionary with:
            - tournaments: List of tournament dictionaries
            - total: Total matching tournaments
            - page: Current page
            - per_page: Items per page
            - total_pages: Total pages
        """
        self.logger.debug(f"Getting tournaments: year={year}, league={league_code}")

        with self.db.get_session() as session:
            query = session.query(Tournament).options(
                joinedload(Tournament.league)
            )

            # Apply filters
            if year:
                query = query.filter(Tournament.tournament_year == year)

            if league_code:
                query = query.join(League).filter(
                    League.league_code == league_code.upper()
                )

            if status:
                query = query.filter(Tournament.status == status)

            # Get total count
            total = query.count()

            # Apply pagination and ordering
            offset = (page - 1) * per_page
            tournaments = query.order_by(
                Tournament.start_date.desc()
            ).offset(offset).limit(per_page).all()

            return {
                'tournaments': [self._tournament_to_dict(t) for t in tournaments],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }

    def get_tournament_results(
        self,
        tournament_id: int,
        include_player_bio: bool = True
    ) -> Dict[str, Any]:
        """
        Get full results (leaderboard) for a tournament.

        Args:
            tournament_id: The tournament's database ID
            include_player_bio: Whether to include player biographical info

        Returns:
            Dictionary with tournament info and complete leaderboard

        Example:
            results = service.get_tournament_results(123)
            print(f"Winner: {results['leaderboard'][0]['player_name']}")

        For Junior Developers:
        ---------------------
        This is a key method for the local news use case. It returns
        the full leaderboard with player information, so we can see:
        - Who finished where
        - What high school each player attended
        - Their scores for each round
        """
        self.logger.debug(f"Getting results for tournament {tournament_id}")

        with self.db.get_session() as session:
            tournament = session.query(Tournament).options(
                joinedload(Tournament.league)
            ).filter(
                Tournament.tournament_id == tournament_id
            ).first()

            if not tournament:
                return None

            # Get all results for this tournament
            results = session.query(TournamentResult).options(
                joinedload(TournamentResult.player)
            ).filter(
                TournamentResult.tournament_id == tournament_id
            ).order_by(
                TournamentResult.final_position.nullslast(),
                TournamentResult.total_to_par
            ).all()

            leaderboard = []
            for result in results:
                entry = self._result_to_dict(result)

                if include_player_bio:
                    player = result.player
                    entry['player_bio'] = {
                        'high_school_name': player.high_school_name,
                        'high_school_city': player.high_school_city,
                        'high_school_state': player.high_school_state,
                        'high_school_graduation_year': player.high_school_graduation_year,
                        'college_name': player.college_name,
                        'hometown_city': player.hometown_city,
                        'hometown_state': player.hometown_state,
                        'news_blurb': player.news_blurb,
                    }

                leaderboard.append(entry)

            tournament_data = self._tournament_to_dict(tournament)
            tournament_data['leaderboard'] = leaderboard
            tournament_data['total_players'] = len(leaderboard)

            return tournament_data

    def get_upcoming_tournaments(
        self,
        days: int = 30,
        league_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming tournaments within a date range.

        Args:
            days: Number of days to look ahead
            league_code: Optional league filter

        Returns:
            List of upcoming tournament dictionaries
        """
        self.logger.debug(f"Getting upcoming tournaments (next {days} days)")

        today = date.today()
        end_date = today + timedelta(days=days)

        with self.db.get_session() as session:
            query = session.query(Tournament).options(
                joinedload(Tournament.league)
            ).filter(
                Tournament.start_date >= today,
                Tournament.start_date <= end_date,
                Tournament.status.in_(['scheduled', 'in_progress'])
            )

            if league_code:
                query = query.join(League).filter(
                    League.league_code == league_code.upper()
                )

            tournaments = query.order_by(Tournament.start_date).all()

            return [self._tournament_to_dict(t) for t in tournaments]

    def get_recent_results(
        self,
        days: int = 14,
        league_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recently completed tournaments.

        Args:
            days: Number of days to look back
            league_code: Optional league filter

        Returns:
            List of completed tournament dictionaries with winner info
        """
        self.logger.debug(f"Getting recent results (last {days} days)")

        today = date.today()
        start_date = today - timedelta(days=days)

        with self.db.get_session() as session:
            query = session.query(Tournament).options(
                joinedload(Tournament.league)
            ).filter(
                Tournament.end_date >= start_date,
                Tournament.end_date <= today,
                Tournament.status == 'completed'
            )

            if league_code:
                query = query.join(League).filter(
                    League.league_code == league_code.upper()
                )

            tournaments = query.order_by(desc(Tournament.end_date)).all()

            results = []
            for tournament in tournaments:
                t_dict = self._tournament_to_dict(tournament)

                # Get winner info
                winner = session.query(TournamentResult).options(
                    joinedload(TournamentResult.player)
                ).filter(
                    TournamentResult.tournament_id == tournament.tournament_id,
                    TournamentResult.final_position == 1
                ).first()

                if winner:
                    player = winner.player
                    t_dict['winner'] = {
                        'player_id': player.player_id,
                        'player_name': player.full_name,
                        'total_to_par': winner.total_to_par,
                        'to_par_display': winner.to_par_display,
                        'earnings': float(winner.earnings) if winner.earnings else None,
                        'high_school_name': player.high_school_name,
                        'high_school_state': player.high_school_state,
                        'news_blurb': player.news_blurb,
                    }

                results.append(t_dict)

            return results

    def get_tournaments_by_location(
        self,
        state: Optional[str] = None,
        city: Optional[str] = None,
        year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find tournaments by location.

        Args:
            state: State to filter by
            city: City to filter by
            year: Year to filter by

        Returns:
            List of matching tournament dictionaries
        """
        with self.db.get_session() as session:
            query = session.query(Tournament).options(
                joinedload(Tournament.league)
            )

            if state:
                query = query.filter(Tournament.state.ilike(f"%{state}%"))

            if city:
                query = query.filter(Tournament.city.ilike(f"%{city}%"))

            if year:
                query = query.filter(Tournament.tournament_year == year)

            tournaments = query.order_by(Tournament.start_date).all()

            return [self._tournament_to_dict(t) for t in tournaments]

    def get_tournament_calendar(
        self,
        year: int,
        league_code: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a calendar view of tournaments for a year.

        Args:
            year: The year to get the calendar for
            league_code: Optional league filter

        Returns:
            Dictionary with months as keys and lists of tournaments as values

        Example:
            calendar = service.get_tournament_calendar(2025, 'PGA')
            for month, tournaments in calendar.items():
                print(f"\n{month}:")
                for t in tournaments:
                    print(f"  - {t['tournament_name']}")
        """
        self.logger.debug(f"Getting tournament calendar for {year}")

        with self.db.get_session() as session:
            query = session.query(Tournament).options(
                joinedload(Tournament.league)
            ).filter(
                Tournament.tournament_year == year
            )

            if league_code:
                query = query.join(League).filter(
                    League.league_code == league_code.upper()
                )

            tournaments = query.order_by(Tournament.start_date).all()

            # Group by month
            calendar = {}
            month_names = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]

            for tournament in tournaments:
                if tournament.start_date:
                    month = month_names[tournament.start_date.month - 1]
                    if month not in calendar:
                        calendar[month] = []
                    calendar[month].append(self._tournament_to_dict(tournament))

            return calendar

    def _tournament_to_dict(self, tournament: Tournament) -> Dict[str, Any]:
        """
        Convert a Tournament model to a dictionary.

        Args:
            tournament: Tournament model instance

        Returns:
            Dictionary with tournament data
        """
        return {
            'tournament_id': tournament.tournament_id,
            'tournament_name': tournament.tournament_name,
            'tournament_year': tournament.tournament_year,
            'league_code': tournament.league.league_code if tournament.league else None,
            'league_name': tournament.league.league_name if tournament.league else None,

            'start_date': tournament.start_date.isoformat() if tournament.start_date else None,
            'end_date': tournament.end_date.isoformat() if tournament.end_date else None,
            'date_range_display': tournament.date_range_display,

            'course_name': tournament.course_name,
            'city': tournament.city,
            'state': tournament.state,
            'country': tournament.country,

            'purse_amount': float(tournament.purse_amount) if tournament.purse_amount else None,
            'purse_currency': tournament.purse_currency,
            'par': tournament.par,
            'total_rounds': tournament.total_rounds,

            'status': tournament.status,
        }

    def _result_to_dict(self, result: TournamentResult) -> Dict[str, Any]:
        """
        Convert a TournamentResult to a dictionary.

        Args:
            result: TournamentResult model instance

        Returns:
            Dictionary with result data
        """
        player = result.player

        return {
            'result_id': result.result_id,
            'player_id': player.player_id,
            'player_name': player.full_name,

            'final_position': result.final_position,
            'final_position_display': result.final_position_display,
            'total_score': result.total_score,
            'total_to_par': result.total_to_par,
            'to_par_display': result.to_par_display,

            'round_1_score': result.round_1_score,
            'round_2_score': result.round_2_score,
            'round_3_score': result.round_3_score,
            'round_4_score': result.round_4_score,
            'round_scores_display': result.round_scores_display,

            'made_cut': result.made_cut,
            'status': result.status,
            'earnings': float(result.earnings) if result.earnings else None,
            'points_earned': float(result.points_earned) if result.points_earned else None,
        }
