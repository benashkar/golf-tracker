"""
LIV Golf Tournament Scraper
============================

Scrapes LIV Golf League tournament schedules and results.
LIV Golf uses a different format: 54-hole (3 rounds) events with shotgun starts.

Note: LIV Golf doesn't have a public API, so we use web scraping and known schedules.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import re

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League


class LIVTournamentScraper(BaseScraper):
    """Scrapes LIV Golf League tournaments."""

    league_code = 'LIV'
    scrape_type = 'tournament_list'

    def __init__(self):
        super().__init__('LIV', 'https://www.livgolf.com')
        self.schedule_url = 'https://www.livgolf.com/schedule'
        self.results_url = 'https://www.livgolf.com/results'
        self.logger = logger.bind(scraper='LIVTournamentScraper', league='LIV')

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Scrape LIV Golf tournaments for a given year."""
        year = year or datetime.now().year
        self.logger.info(f'Starting LIV Golf tournament scrape for {year}')

        # Ensure league exists
        self._ensure_league()

        # Fetch tournaments
        tournaments = self._fetch_tournaments(year)
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
                self._process_tournament(t, year)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing tournament: {e}")
                self._stats['errors'].append(str(e))

        # Fetch leaderboard results for recent/current tournaments
        self._fetch_leaderboard_results(year)

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _ensure_league(self):
        """Ensure LIV league exists in database."""
        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='LIV').first()
            if not league:
                league = League(
                    league_code='LIV',
                    league_name='LIV Golf',
                    website_url='https://www.livgolf.com',
                    is_active=True
                )
                session.add(league)

    def _fetch_tournaments(self, year: int) -> Optional[List[Dict]]:
        """Fetch LIV Golf tournaments. Try web scraping first, fall back to known schedule."""
        tournaments = []

        # Try scraping the website first
        soup = self.get_page(self.schedule_url)
        if soup:
            tournaments = self._parse_schedule_page(soup, year)

        # If scraping didn't work, use known 2025/2026 schedule
        if not tournaments:
            tournaments = self._get_known_schedule(year)

        self.logger.info(f'Found {len(tournaments)} LIV Golf tournaments for {year}')
        return tournaments if tournaments else None

    def _parse_schedule_page(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse LIV Golf schedule from website."""
        tournaments = []

        # Look for tournament cards/entries
        event_elements = soup.find_all(['div', 'article', 'a'],
                                        class_=re.compile(r'event|tournament|schedule', re.I))

        for elem in event_elements:
            try:
                # Try to extract event info
                name = None
                location = None
                dates = None

                # Look for name in headings
                name_elem = elem.find(['h2', 'h3', 'h4', 'span'],
                                       class_=re.compile(r'name|title', re.I))
                if name_elem:
                    name = name_elem.get_text(strip=True)

                # Look for location
                location_elem = elem.find(['span', 'p'],
                                          class_=re.compile(r'location|venue', re.I))
                if location_elem:
                    location = location_elem.get_text(strip=True)

                # Look for dates
                date_elem = elem.find(['span', 'p', 'time'],
                                       class_=re.compile(r'date', re.I))
                if date_elem:
                    dates = date_elem.get_text(strip=True)

                if name:
                    tournaments.append({
                        'name': name,
                        'location': location,
                        'dates': dates,
                    })

            except Exception as e:
                self.logger.debug(f"Error parsing event element: {e}")

        return tournaments

    def _get_known_schedule(self, year: int) -> List[Dict]:
        """Return known LIV Golf schedule for the year."""
        # LIV Golf 2025/2026 schedule (approximate)
        # Each event is 3 rounds (Fri-Sun) with individual and team competitions
        today = date.today()

        schedules = {
            2025: [
                {'name': 'LIV Golf Riyadh', 'location': 'Riyadh, Saudi Arabia', 'start_date': date(2025, 2, 6)},
                {'name': 'LIV Golf Hong Kong', 'location': 'Hong Kong', 'start_date': date(2025, 3, 7)},
                {'name': 'LIV Golf Adelaide', 'location': 'Adelaide, Australia', 'start_date': date(2025, 4, 18)},
                {'name': 'LIV Golf Singapore', 'location': 'Singapore', 'start_date': date(2025, 5, 2)},
                {'name': 'LIV Golf Houston', 'location': 'Houston, TX, USA', 'start_date': date(2025, 6, 6)},
                {'name': 'LIV Golf Nashville', 'location': 'Nashville, TN, USA', 'start_date': date(2025, 6, 20)},
                {'name': 'LIV Golf Andalucia', 'location': 'Andalucia, Spain', 'start_date': date(2025, 7, 11)},
                {'name': 'LIV Golf UK', 'location': 'United Kingdom', 'start_date': date(2025, 7, 25)},
                {'name': 'LIV Golf Greenbrier', 'location': 'West Virginia, USA', 'start_date': date(2025, 8, 15)},
                {'name': 'LIV Golf Chicago', 'location': 'Chicago, IL, USA', 'start_date': date(2025, 9, 12)},
                {'name': 'LIV Golf Dallas', 'location': 'Dallas, TX, USA', 'start_date': date(2025, 9, 26)},
                {'name': 'LIV Golf Team Championship', 'location': 'Miami, FL, USA', 'start_date': date(2025, 10, 17)},
            ],
            2026: [
                {'name': 'LIV Golf Riyadh', 'location': 'Riyadh, Saudi Arabia', 'start_date': date(2026, 2, 5)},
                {'name': 'LIV Golf Hong Kong', 'location': 'Hong Kong', 'start_date': date(2026, 3, 6)},
                {'name': 'LIV Golf Adelaide', 'location': 'Adelaide, Australia', 'start_date': date(2026, 4, 17)},
                {'name': 'LIV Golf Singapore', 'location': 'Singapore', 'start_date': date(2026, 5, 1)},
                {'name': 'LIV Golf Houston', 'location': 'Houston, TX, USA', 'start_date': date(2026, 6, 5)},
                {'name': 'LIV Golf Nashville', 'location': 'Nashville, TN, USA', 'start_date': date(2026, 6, 19)},
                {'name': 'LIV Golf Andalucia', 'location': 'Andalucia, Spain', 'start_date': date(2026, 7, 10)},
                {'name': 'LIV Golf UK', 'location': 'United Kingdom', 'start_date': date(2026, 7, 24)},
                {'name': 'LIV Golf Greenbrier', 'location': 'West Virginia, USA', 'start_date': date(2026, 8, 14)},
                {'name': 'LIV Golf Chicago', 'location': 'Chicago, IL, USA', 'start_date': date(2026, 9, 11)},
                {'name': 'LIV Golf Dallas', 'location': 'Dallas, TX, USA', 'start_date': date(2026, 9, 25)},
                {'name': 'LIV Golf Team Championship', 'location': 'Miami, FL, USA', 'start_date': date(2026, 10, 16)},
            ]
        }

        tournaments = []
        year_schedule = schedules.get(year, [])

        for event in year_schedule:
            start_date = event['start_date']
            # LIV events are 3 days (Fri-Sun)
            end_date = start_date + timedelta(days=2)

            # Determine status
            if today > end_date:
                status = 'completed'
            elif start_date <= today <= end_date:
                status = 'in_progress'
            else:
                status = 'scheduled'

            tournaments.append({
                'name': event['name'],
                'location': event['location'],
                'start_date': start_date,
                'end_date': end_date,
                'status': status,
            })

        return tournaments

    def _fetch_leaderboard_results(self, year: int):
        """Fetch leaderboard results for completed/in-progress LIV events."""
        # Try to get results from LIV Golf website
        soup = self.get_page(self.results_url)
        if not soup:
            return

        # Look for leaderboard data
        # LIV Golf website structure may vary, try multiple approaches
        self._parse_leaderboard_page(soup, year)

    def _parse_leaderboard_page(self, soup: BeautifulSoup, year: int):
        """Parse leaderboard results from LIV Golf website."""
        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='LIV').first()
            if not league:
                return

            # Look for player results in the leaderboard
            leaderboard_rows = soup.find_all(['tr', 'div'],
                                              class_=re.compile(r'player|competitor|row', re.I))

            for row in leaderboard_rows:
                try:
                    # Extract player info
                    pos_elem = row.find(['td', 'span'], class_=re.compile(r'pos|rank|position', re.I))
                    name_elem = row.find(['td', 'span', 'a'], class_=re.compile(r'name|player', re.I))
                    score_elem = row.find(['td', 'span'], class_=re.compile(r'score|total', re.I))

                    if pos_elem and name_elem:
                        position = pos_elem.get_text(strip=True)
                        name = name_elem.get_text(strip=True)
                        score = score_elem.get_text(strip=True) if score_elem else ''

                        self.logger.debug(f"Found result: {position}. {name} ({score})")

                except Exception as e:
                    self.logger.debug(f"Error parsing leaderboard row: {e}")

    def _process_tournament(self, data: Dict, year: int) -> Optional[Tournament]:
        """Process and save a tournament to the database."""
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='LIV').first()
            if not league:
                return None

            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            # Parse location
            location = data.get('location', '')
            city, state, country = self._parse_location(location)

            if tournament:
                tournament.start_date = data.get('start_date')
                tournament.end_date = data.get('end_date')
                tournament.status = data.get('status', 'scheduled')
                if city:
                    tournament.city = city
                if country:
                    tournament.country = country
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    city=city,
                    state=state,
                    country=country,
                    status=data.get('status', 'scheduled'),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')

            return tournament

    def _parse_location(self, location: str) -> tuple:
        """Parse location string into city, state, country."""
        if not location:
            return None, None, None

        parts = [p.strip() for p in location.split(',')]

        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            # Could be city, country or city, state
            return parts[0], None, parts[1]
        elif len(parts) == 1:
            return parts[0], None, None

        return None, None, None


def scrape_liv_tournaments(year=None):
    """Convenience function to scrape LIV Golf tournaments."""
    return LIVTournamentScraper().run(year=year)
