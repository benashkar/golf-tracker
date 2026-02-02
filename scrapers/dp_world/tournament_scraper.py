"""
DP World Tour Tournament Scraper
=================================

Scrapes DP World Tour (European Tour) tournament schedules and results using ESPN API.
Supports both completed tournaments and live/in-progress tournaments with round-by-round scores.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
from loguru import logger
from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League


class DPWorldTournamentScraper(BaseScraper):
    """Scrapes DP World Tour tournaments using ESPN API."""

    league_code = 'DPWORLD'
    scrape_type = 'tournaments'

    def __init__(self):
        super().__init__('DPWORLD', 'https://www.europeantour.com')
        self.espn_scoreboard = 'https://site.web.api.espn.com/apis/site/v2/sports/golf/eur/scoreboard'
        self.logger = logger.bind(scraper='DPWorldTournamentScraper', league='DPWORLD')

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Scrape DP World Tour tournaments for a given year."""
        year = year or datetime.now().year
        self.logger.info(f'Starting DP World Tour tournament scrape for {year}')

        # Ensure league exists
        self._ensure_league()

        # First fetch schedule
        tournaments = self._fetch_schedule(year)
        if not tournaments:
            return {
                'status': 'failed',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for t in tournaments:
            try:
                tournament = self._process_tournament(t, year)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing tournament: {e}")
                self._stats['errors'].append(str(e))

        # Fetch current/live event results
        self._fetch_current_results()

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _ensure_league(self):
        """Ensure DPWORLD league exists in database."""
        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='DPWORLD').first()
            if not league:
                league = League(
                    league_code='DPWORLD',
                    league_name='DP World Tour',
                    website_url='https://www.europeantour.com',
                    is_active=True
                )
                session.add(league)

    def _fetch_schedule(self, year: int) -> Optional[List[Dict]]:
        """Fetch DP World tournament schedule from ESPN."""
        data = self.get_json(self.espn_scoreboard)
        if not data:
            return None

        tournaments = []
        for league in data.get('leagues', []):
            # ESPN uses 'eur' for European/DP World Tour
            if league.get('abbreviation') in ['EUR', 'EURO']:
                for event in league.get('calendar', []):
                    start_str = event.get('startDate', '')
                    end_str = event.get('endDate', '')
                    start_date = self._parse_date(start_str)
                    end_date = self._parse_date(end_str)

                    # Filter by year
                    if start_date and start_date.year == year:
                        today = date.today()
                        if end_date and today > end_date:
                            status = 'completed'
                        elif start_date and start_date <= today <= (end_date or start_date):
                            status = 'in_progress'
                        else:
                            status = 'scheduled'

                        tournaments.append({
                            'espn_id': event.get('id', ''),
                            'name': event.get('label', ''),
                            'start_date': start_date,
                            'end_date': end_date,
                            'status': status,
                        })

        self.logger.info(f'Found {len(tournaments)} DP World tournaments for {year}')
        return tournaments

    def _fetch_current_results(self):
        """Fetch results for current/in-progress DP World events."""
        data = self.get_json(self.espn_scoreboard)
        if not data:
            return

        events = data.get('events', [])
        for event in events:
            event_status = event.get('status', {}).get('type', {}).get('name', '')
            event_name = event.get('name', '')

            # Process in-progress or completed events
            if event_status in ['STATUS_IN_PROGRESS', 'STATUS_FINAL', 'STATUS_SCHEDULED']:
                self.logger.info(f"Processing DP World event: {event_name} (status: {event_status})")
                self._process_event_results(event)

    def _process_event_results(self, event: Dict):
        """Process results for an ESPN DP World event."""
        event_name = event.get('name', '').strip()
        if not event_name:
            return

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='DPWORLD').first()
            if not league:
                return

            # Find tournament by name
            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=event_name
            ).first()

            if not tournament:
                short_name = event.get('shortName', '')
                if short_name:
                    tournament = session.query(Tournament).filter_by(
                        league_id=league.league_id,
                        tournament_name=short_name
                    ).first()

            if not tournament:
                # Create tournament if doesn't exist
                start_str = event.get('date', '')
                end_str = event.get('endDate', '')
                start_date = self._parse_date(start_str)
                end_date = self._parse_date(end_str)
                year = start_date.year if start_date else datetime.now().year

                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=event_name,
                    tournament_year=year,
                    start_date=start_date,
                    end_date=end_date,
                    status='in_progress',
                    dpworld_tournament_id=event.get('id', ''),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1

            # Update tournament status
            event_status = event.get('status', {}).get('type', {}).get('name', '')
            if event_status == 'STATUS_IN_PROGRESS':
                tournament.status = 'in_progress'
            elif event_status == 'STATUS_FINAL':
                tournament.status = 'completed'

            # Process competitors
            competitions = event.get('competitions', [])
            for comp in competitions:
                competitors = comp.get('competitors', [])
                self.logger.info(f"Processing {len(competitors)} competitors for {event_name}")

                for competitor in competitors:
                    try:
                        self._save_competitor_result(session, tournament, competitor, event_status)
                    except Exception as e:
                        self.logger.error(f"Error saving competitor result: {e}")

    def _save_competitor_result(self, session, tournament: Tournament, competitor: Dict, event_status: str):
        """Save a competitor's result with round-by-round scores."""
        athlete = competitor.get('athlete', {})
        if not athlete:
            return

        espn_id = athlete.get('id', '')
        display_name = athlete.get('displayName', '')

        if not display_name:
            return

        # Parse name
        name_parts = display_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Find player by DP World ID
        player = session.query(Player).filter_by(dpworld_id=espn_id).first()
        if not player:
            player = session.query(Player).filter_by(
                first_name=first_name,
                last_name=last_name
            ).first()
        if not player:
            if not first_name or not last_name:
                return
            player = Player(first_name=first_name, last_name=last_name, dpworld_id=espn_id)
            session.add(player)
            session.flush()

        # Check for existing result
        existing = session.query(TournamentResult).filter_by(
            tournament_id=tournament.tournament_id,
            player_id=player.player_id
        ).first()

        # Parse position
        position = competitor.get('order')
        position_display = str(position) if position else '-'

        # Parse score (to-par)
        score_str = competitor.get('score', '')
        total_to_par = self._parse_score(score_str)

        # Parse round-by-round scores
        linescores = competitor.get('linescores', [])
        r1, r2, r3, r4 = None, None, None, None

        for ls in linescores:
            period = ls.get('period')
            value = ls.get('value')
            if value is not None:
                score = int(value) if isinstance(value, (int, float)) else None
                if period == 1:
                    r1 = score
                elif period == 2:
                    r2 = score
                elif period == 3:
                    r3 = score
                elif period == 4:
                    r4 = score

        # Calculate total strokes
        total_strokes = None
        round_scores = [r for r in [r1, r2, r3, r4] if r is not None]
        if round_scores:
            total_strokes = sum(round_scores)

        # Build round_scores dict
        round_scores_dict = {}
        if r1 is not None:
            round_scores_dict['R1'] = r1
        if r2 is not None:
            round_scores_dict['R2'] = r2
        if r3 is not None:
            round_scores_dict['R3'] = r3
        if r4 is not None:
            round_scores_dict['R4'] = r4

        # Determine status
        player_status = 'active'

        if existing:
            existing.final_position = position
            existing.final_position_display = position_display
            existing.total_to_par = total_to_par
            existing.total_score = total_strokes
            existing.status = player_status
            existing.round_1_score = r1
            existing.round_2_score = r2
            existing.round_3_score = r3
            existing.round_4_score = r4
            existing.round_scores = round_scores_dict if round_scores_dict else None
        else:
            session.add(TournamentResult(
                tournament_id=tournament.tournament_id,
                player_id=player.player_id,
                final_position=position,
                final_position_display=position_display,
                total_to_par=total_to_par,
                total_score=total_strokes,
                status=player_status,
                round_1_score=r1,
                round_2_score=r2,
                round_3_score=r3,
                round_4_score=r4,
                round_scores=round_scores_dict if round_scores_dict else None
            ))

    def _parse_date(self, date_str: str):
        """Parse ISO date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except:
            return None

    def _parse_score(self, score_str: str) -> Optional[int]:
        """Parse score string to integer."""
        if not score_str:
            return None
        if score_str == 'E':
            return 0
        try:
            return int(score_str)
        except (ValueError, TypeError):
            return None

    def _process_tournament(self, data: Dict, year: int) -> Optional[Tournament]:
        """Process and save a tournament to the database."""
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='DPWORLD').first()
            if not league:
                return None

            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            if tournament:
                tournament.start_date = data.get('start_date')
                tournament.end_date = data.get('end_date')
                tournament.status = data.get('status', 'scheduled')
                tournament.dpworld_tournament_id = data.get('espn_id', '')
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    status=data.get('status', 'scheduled'),
                    dpworld_tournament_id=data.get('espn_id', ''),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')

            return tournament


def scrape_dpworld_tournaments(year=None):
    """Convenience function to scrape DP World tournaments."""
    return DPWorldTournamentScraper().run(year=year)
