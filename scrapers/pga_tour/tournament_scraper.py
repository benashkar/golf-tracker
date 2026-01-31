"""
PGA Tour Tournament Scraper
============================

This module scrapes PGA Tour tournament schedules and results from pgatour.com.
It extracts tournament information, dates, locations, and player results.

For Junior Developers:
---------------------
This is a more complex scraper because it needs to:
1. Get the tournament schedule (list of all tournaments)
2. Get results for each completed tournament
3. Match players with their results
4. Handle different tournament statuses (upcoming, in-progress, completed)

The PGA Tour season typically runs from January to August (with wrap-around
events in the fall being part of the next season).

Usage:
    from scrapers.pga_tour.tournament_scraper import PGATourTournamentScraper

    scraper = PGATourTournamentScraper()

    # Scrape the 2025 season
    result = scraper.run(year=2025)

    # Or scrape a specific tournament's results
    result = scraper.scrape_tournament_results(tournament_id='R2025xxx')
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
import re

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League
from config.leagues import get_league_config


class PGATourTournamentScraper(BaseScraper):
    """
    Scrapes PGA Tour tournament schedule and results.

    This scraper handles:
    1. Tournament schedule for a season
    2. Individual tournament results (leaderboards)
    3. Player score data (round-by-round)

    For Junior Developers:
    ---------------------
    Golf tournaments typically have:
    - 4 rounds (Thursday through Sunday)
    - A "cut" after round 2 (only top ~65 players continue)
    - Various statuses (WD=withdrew, DQ=disqualified, CUT=missed cut)

    Attributes:
        scrape_type: Type of scrape for logging
        current_year: The year being scraped
    """

    scrape_type = 'tournament_list'

    def __init__(self):
        """Initialize the PGA Tour tournament scraper."""
        config = get_league_config('PGA')
        super().__init__('PGA', config['base_url'])

        self.source_url = config['urls']['schedule']
        self.current_year = datetime.now().year

        # API endpoints
        self.schedule_api = 'https://statdata.pgatour.com/r/current/schedule-v2.json'
        self.leaderboard_api = 'https://statdata.pgatour.com/r/{tournament_id}/leaderboard-v2.json'

        self.logger = logger.bind(
            scraper='PGATourTournamentScraper',
            league='PGA'
        )

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape PGA Tour tournaments for a given year.

        Args:
            year: The season year to scrape (defaults to current year)

        Returns:
            Dictionary with scrape results

        For Junior Developers:
        ---------------------
        This method coordinates the entire scraping process:
        1. Fetch the tournament schedule
        2. For each tournament, save basic info
        3. For completed tournaments, fetch and save results
        """
        year = year or self.current_year
        self.logger.info(f"Starting PGA Tour tournament scrape for {year}")

        # Fetch the schedule
        tournaments = self._fetch_schedule(year)

        if not tournaments:
            self.logger.error("Failed to fetch tournament schedule")
            return {
                'status': 'failed',
                'error': 'Could not fetch tournament schedule',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        # Process each tournament
        for tournament_data in tournaments:
            try:
                tournament = self._process_tournament(tournament_data, year)
                self._stats['records_processed'] += 1

                # If tournament is completed, fetch results
                if tournament and tournament_data.get('status') == 'completed':
                    self._fetch_and_save_results(tournament, tournament_data)

            except Exception as e:
                self.logger.error(f"Error processing tournament: {e}")
                self._stats['errors'].append(str(e))

        # Determine final status
        if self._stats['errors']:
            status = 'partial' if self._stats['records_processed'] > 0 else 'failed'
        else:
            status = 'success'

        return {
            'status': status,
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _fetch_schedule(self, year: int) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the tournament schedule for a season.

        Args:
            year: The season year

        Returns:
            List of tournament dictionaries, or None if failed
        """
        self.logger.info(f"Fetching {year} tournament schedule")

        # Try the API first
        data = self.get_json(self.schedule_api)

        if data and 'years' in data:
            # Find the requested year
            for year_data in data['years']:
                if year_data.get('year') == str(year):
                    return self._parse_schedule_data(year_data)

        # Fallback to HTML
        return self._fetch_schedule_html(year)

    def _parse_schedule_data(
        self,
        year_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse tournament schedule from API data.

        Args:
            year_data: Year section from the schedule API

        Returns:
            List of normalized tournament dictionaries
        """
        tournaments = []

        for tour_data in year_data.get('tours', []):
            for tournament in tour_data.get('trns', []):
                # Parse dates
                start_date = self._parse_date(tournament.get('date', {}).get('start'))
                end_date = self._parse_date(tournament.get('date', {}).get('end'))

                # Determine status
                status = self._determine_status(tournament, start_date, end_date)

                tournaments.append({
                    'tournament_id': tournament.get('permNum', ''),
                    'name': tournament.get('trnName', {}).get('long', ''),
                    'short_name': tournament.get('trnName', {}).get('short', ''),
                    'start_date': start_date,
                    'end_date': end_date,
                    'course': tournament.get('courses', [{}])[0].get('courseName', '') if tournament.get('courses') else '',
                    'city': tournament.get('city', ''),
                    'state': tournament.get('state', ''),
                    'country': tournament.get('country', ''),
                    'purse': self._parse_purse(tournament.get('Purse', '')),
                    'status': status,
                    'pga_tournament_id': tournament.get('permNum', ''),
                })

        return tournaments

    def _fetch_schedule_html(self, year: int) -> Optional[List[Dict[str, Any]]]:
        """
        Fallback: Fetch schedule from HTML page.

        Args:
            year: The season year

        Returns:
            List of tournament dictionaries, or None if failed
        """
        self.logger.info(f"Fetching schedule from HTML for {year}")

        soup = self.get_page(f"{self.source_url}/{year}")
        if not soup:
            return None

        tournaments = []

        # Look for tournament entries
        # Note: Structure may change, this is a basic implementation
        tournament_sections = soup.find_all('div', class_=re.compile(r'tournament|event'))

        for section in tournament_sections:
            try:
                name_elem = section.find(['h3', 'h4', 'a'], class_=re.compile(r'name|title'))
                if name_elem:
                    name = name_elem.get_text(strip=True)

                    tournaments.append({
                        'name': name,
                        'tournament_id': '',
                        'status': 'scheduled',
                    })
            except Exception as e:
                self.logger.debug(f"Error parsing tournament section: {e}")

        return tournaments if tournaments else None

    def _process_tournament(
        self,
        tournament_data: Dict[str, Any],
        year: int
    ) -> Optional[Tournament]:
        """
        Process and save a tournament to the database.

        Args:
            tournament_data: Dictionary with tournament information
            year: The season year

        Returns:
            The Tournament object, or None if failed
        """
        name = tournament_data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            # Get league
            league = session.query(League).filter_by(
                league_code='PGA'
            ).first()

            if not league:
                self.logger.error("PGA Tour league not found")
                return None

            # Check if tournament exists
            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            if tournament:
                # Update existing
                self._update_tournament(tournament, tournament_data)
                self._stats['records_updated'] += 1
                self.logger.debug(f"Updated tournament: {name}")
            else:
                # Create new
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=tournament_data.get('start_date'),
                    end_date=tournament_data.get('end_date'),
                    course_name=tournament_data.get('course', ''),
                    city=tournament_data.get('city', ''),
                    state=tournament_data.get('state', ''),
                    country=tournament_data.get('country', 'USA'),
                    purse_amount=tournament_data.get('purse'),
                    status=tournament_data.get('status', 'scheduled'),
                    pga_tour_tournament_id=tournament_data.get('pga_tournament_id', ''),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f"Created tournament: {name}")

            return tournament

    def _update_tournament(
        self,
        tournament: Tournament,
        tournament_data: Dict[str, Any]
    ):
        """Update an existing tournament with new data."""
        if tournament_data.get('start_date'):
            tournament.start_date = tournament_data['start_date']
        if tournament_data.get('end_date'):
            tournament.end_date = tournament_data['end_date']
        if tournament_data.get('course'):
            tournament.course_name = tournament_data['course']
        if tournament_data.get('city'):
            tournament.city = tournament_data['city']
        if tournament_data.get('state'):
            tournament.state = tournament_data['state']
        if tournament_data.get('purse'):
            tournament.purse_amount = tournament_data['purse']
        if tournament_data.get('status'):
            tournament.status = tournament_data['status']

        tournament.updated_at = datetime.utcnow()

    def _fetch_and_save_results(
        self,
        tournament: Tournament,
        tournament_data: Dict[str, Any]
    ):
        """
        Fetch and save results for a completed tournament.

        Args:
            tournament: Tournament object
            tournament_data: Dictionary with tournament info (contains tournament ID)
        """
        tournament_id = tournament_data.get('pga_tournament_id', '')
        if not tournament_id:
            return

        self.logger.info(f"Fetching results for {tournament.tournament_name}")

        # Fetch leaderboard
        url = self.leaderboard_api.format(tournament_id=tournament_id)
        data = self.get_json(url)

        if not data or 'leaderboard' not in data:
            self.logger.warning(f"No leaderboard data for {tournament.tournament_name}")
            return

        leaderboard = data.get('leaderboard', {})
        players = leaderboard.get('players', [])

        with self.db.get_session() as session:
            # Re-fetch tournament in this session
            tournament = session.query(Tournament).get(tournament.tournament_id)

            for player_result in players:
                try:
                    self._save_player_result(session, tournament, player_result)
                except Exception as e:
                    self.logger.error(f"Error saving result: {e}")

    def _save_player_result(
        self,
        session,
        tournament: Tournament,
        player_result: Dict[str, Any]
    ):
        """
        Save a single player's tournament result.

        Args:
            session: Database session
            tournament: Tournament object
            player_result: Dictionary with player result data
        """
        # Get or create player
        pga_id = player_result.get('pid', '')
        first_name = player_result.get('playerNames', {}).get('firstName', '')
        last_name = player_result.get('playerNames', {}).get('lastName', '')

        if not first_name or not last_name:
            return

        # Find player
        player = session.query(Player).filter_by(
            pga_tour_id=pga_id
        ).first()

        if not player:
            player = session.query(Player).filter_by(
                first_name=first_name,
                last_name=last_name
            ).first()

        if not player:
            # Create minimal player record
            player = Player(
                first_name=first_name,
                last_name=last_name,
                pga_tour_id=pga_id
            )
            session.add(player)
            session.flush()

        # Check for existing result
        result = session.query(TournamentResult).filter_by(
            tournament_id=tournament.tournament_id,
            player_id=player.player_id
        ).first()

        # Parse scores
        rounds = player_result.get('rounds', [])
        round_scores = {}
        round_to_par = {}

        for i, round_data in enumerate(rounds[:4], 1):
            score = round_data.get('strokes')
            if score:
                round_scores[f'R{i}'] = score

            to_par = round_data.get('toPar')
            if to_par is not None:
                round_to_par[f'R{i}'] = to_par

        # Parse position
        position = player_result.get('position', {})
        position_value = position.get('value', None)
        position_display = position.get('displayValue', '')

        # Determine if made cut
        status_str = player_result.get('status', 'active')
        made_cut = status_str not in ['cut', 'CUT']

        if result:
            # Update existing result
            result.final_position = position_value
            result.final_position_display = position_display
            result.total_score = player_result.get('totalStrokes')
            result.total_to_par = player_result.get('total')
            result.round_scores = round_scores
            result.round_to_par = round_to_par
            result.round_1_score = rounds[0].get('strokes') if len(rounds) > 0 else None
            result.round_2_score = rounds[1].get('strokes') if len(rounds) > 1 else None
            result.round_3_score = rounds[2].get('strokes') if len(rounds) > 2 else None
            result.round_4_score = rounds[3].get('strokes') if len(rounds) > 3 else None
            result.made_cut = made_cut
            result.status = 'cut' if not made_cut else 'active'
            result.earnings = self._parse_earnings(player_result.get('money', ''))
        else:
            # Create new result
            result = TournamentResult(
                tournament_id=tournament.tournament_id,
                player_id=player.player_id,
                final_position=position_value,
                final_position_display=position_display,
                total_score=player_result.get('totalStrokes'),
                total_to_par=player_result.get('total'),
                round_scores=round_scores,
                round_to_par=round_to_par,
                round_1_score=rounds[0].get('strokes') if len(rounds) > 0 else None,
                round_2_score=rounds[1].get('strokes') if len(rounds) > 1 else None,
                round_3_score=rounds[2].get('strokes') if len(rounds) > 2 else None,
                round_4_score=rounds[3].get('strokes') if len(rounds) > 3 else None,
                made_cut=made_cut,
                status='cut' if not made_cut else 'active',
                earnings=self._parse_earnings(player_result.get('money', '')),
            )
            session.add(result)

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(date_str, '%m/%d/%Y').date()
            except ValueError:
                return None

    def _parse_purse(self, purse_str: str) -> Optional[Decimal]:
        """Parse purse amount string to Decimal."""
        if not purse_str:
            return None

        try:
            # Remove $ and commas
            clean = purse_str.replace('$', '').replace(',', '').strip()
            return Decimal(clean)
        except:
            return None

    def _parse_earnings(self, earnings_str: str) -> Optional[Decimal]:
        """Parse earnings string to Decimal."""
        return self._parse_purse(earnings_str)

    def _determine_status(
        self,
        tournament_data: Dict,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> str:
        """Determine tournament status based on dates and data."""
        today = date.today()

        if not start_date:
            return 'scheduled'

        if end_date and today > end_date:
            return 'completed'
        elif start_date <= today <= (end_date or start_date):
            return 'in_progress'
        else:
            return 'scheduled'


def scrape_pga_tournaments(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function to scrape PGA Tour tournaments.

    Args:
        year: Season year (defaults to current year)

    Returns:
        Dictionary with scrape results
    """
    scraper = PGATourTournamentScraper()
    return scraper.run(year=year)


if __name__ == '__main__':
    result = scrape_pga_tournaments()
    print(f"Scrape complete: {result}")
