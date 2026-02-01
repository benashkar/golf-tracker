from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from loguru import logger
from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League
from config.leagues import get_league_config


class LPGATournamentScraper(BaseScraper):
    """Scrapes LPGA Tour tournaments using ESPN API."""

    league_code = 'LPGA'
    scrape_type = 'tournaments'

    def __init__(self):
        config = get_league_config('LPGA')
        base_url = config['base_url'] if config else 'https://www.lpga.com'
        super().__init__('LPGA', base_url)
        self.espn_scoreboard = 'https://site.web.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard'
        self.logger = logger.bind(scraper='LPGATournamentScraper', league='LPGA')

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        year = year or datetime.now().year
        self.logger.info(f'Starting LPGA Tour tournament scrape for {year}')
        tournaments = self._fetch_schedule(year)
        if not tournaments:
            return {'status': 'failed', 'records_processed': 0, 'records_created': 0, 'records_updated': 0, 'errors': self._stats['errors']}
        for t in tournaments:
            try:
                self._process_tournament(t, year)
                self._stats['records_processed'] += 1
            except Exception as e:
                self._stats['errors'].append(str(e))
        return {'status': 'success' if not self._stats['errors'] else 'partial', 'records_processed': self._stats['records_processed'], 'records_created': self._stats['records_created'], 'records_updated': self._stats['records_updated'], 'errors': self._stats['errors']}

    def _fetch_schedule(self, year: int) -> Optional[List[Dict]]:
        data = self.get_json(self.espn_scoreboard)
        if not data:
            return None
        tournaments = []
        for league in data.get('leagues', []):
            if league.get('abbreviation') == 'LPGA':
                for event in league.get('calendar', []):
                    start_str = event.get('startDate', '')
                    end_str = event.get('endDate', '')
                    start_date = self._parse_date(start_str)
                    end_date = self._parse_date(end_str)
                    # Filter by year
                    if start_date and start_date.year == year:
                        status = 'completed' if end_date and datetime.now().date() > end_date else 'scheduled'
                        tournaments.append({
                            'espn_id': event.get('id', ''),
                            'name': event.get('label', ''),
                            'start_date': start_date,
                            'end_date': end_date,
                            'status': status,
                        })
        self.logger.info(f'Found {len(tournaments)} LPGA tournaments for {year}')
        return tournaments

    def _parse_date(self, date_str: str):
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except:
            return None

    def _process_tournament(self, data: Dict, year: int):
        name = data.get('name', '').strip()
        if not name:
            return
        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='LPGA').first()
            if not league:
                return
            tournament = session.query(Tournament).filter_by(league_id=league.league_id, tournament_name=name, tournament_year=year).first()
            if tournament:
                tournament.start_date = data.get('start_date')
                tournament.end_date = data.get('end_date')
                tournament.status = data.get('status', 'scheduled')
                tournament.lpga_tournament_id = data.get('espn_id', '')
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    status=data.get('status', 'scheduled'),
                    lpga_tournament_id=data.get('espn_id', ''),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')


def scrape_lpga_tournaments(year=None):
    return LPGATournamentScraper().run(year=year)
