"""
USGA Amateur Tournament Scraper
================================

Scrapes USGA amateur championship schedules and results.
Since USGA doesn't have a public API, this scraper uses:
1. Known championship schedule for 2026
2. AmateurGolf.com for results when available
3. USGA website for leaderboard data

USGA Championships Format:
- Stroke play qualifying rounds (2 rounds)
- Match play brackets (64 players)
- 18-hole matches through semifinals
- 36-hole championship match

Data Sources:
- https://championships.usga.org for schedule
- https://www.amateurgolf.com for results
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
import re

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League


class USGATournamentScraper(BaseScraper):
    """Scrapes USGA amateur championship schedules and results."""

    league_code = 'USGA'
    scrape_type = 'tournaments'

    def __init__(self):
        super().__init__('USGA', 'https://championships.usga.org')
        self.logger = logger.bind(scraper='USGATournamentScraper')

        # Known 2026 USGA Championship Schedule
        # Format: stroke play qualifying, then match play
        self.schedule_2026 = [
            {
                'name': 'U.S. Amateur Four-Ball',
                'start_date': date(2026, 5, 23),
                'end_date': date(2026, 5, 27),
                'course': 'Bandon Dunes Golf Resort',
                'city': 'Bandon',
                'state': 'Oregon',
                'country': 'USA',
                'format': 'four_ball',
                'total_rounds': 4,  # 2 stroke play + knockout
            },
            {
                'name': 'U.S. Women\'s Amateur Four-Ball',
                'start_date': date(2026, 5, 2),
                'end_date': date(2026, 5, 6),
                'course': 'The Resort at Pelican Hill',
                'city': 'Newport Coast',
                'state': 'California',
                'country': 'USA',
                'format': 'four_ball',
                'total_rounds': 4,
            },
            {
                'name': 'U.S. Junior Amateur',
                'start_date': date(2026, 7, 20),
                'end_date': date(2026, 7, 25),
                'course': 'The Country Club of Birmingham',
                'city': 'Birmingham',
                'state': 'Alabama',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,  # Stroke play rounds
            },
            {
                'name': 'U.S. Girls\' Junior',
                'start_date': date(2026, 7, 13),
                'end_date': date(2026, 7, 18),
                'course': 'The Tuxedo Club',
                'city': 'Tuxedo Park',
                'state': 'New York',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Amateur',
                'start_date': date(2026, 8, 10),
                'end_date': date(2026, 8, 16),
                'course': 'Merion Golf Club',
                'city': 'Ardmore',
                'state': 'Pennsylvania',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Women\'s Amateur',
                'start_date': date(2026, 8, 3),
                'end_date': date(2026, 8, 9),
                'course': 'Southern Hills Country Club',
                'city': 'Tulsa',
                'state': 'Oklahoma',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Senior Amateur',
                'start_date': date(2026, 8, 29),
                'end_date': date(2026, 9, 3),
                'course': 'Medinah Country Club',
                'city': 'Medinah',
                'state': 'Illinois',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Senior Women\'s Amateur',
                'start_date': date(2026, 9, 12),
                'end_date': date(2026, 9, 17),
                'course': 'Country Club of Charleston',
                'city': 'Charleston',
                'state': 'South Carolina',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Mid-Amateur',
                'start_date': date(2026, 9, 26),
                'end_date': date(2026, 10, 1),
                'course': 'Sand Valley Resort',
                'city': 'Nekoosa',
                'state': 'Wisconsin',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
            {
                'name': 'U.S. Women\'s Mid-Amateur',
                'start_date': date(2026, 10, 10),
                'end_date': date(2026, 10, 15),
                'course': 'TBD',
                'city': 'TBD',
                'state': 'TBD',
                'country': 'USA',
                'format': 'stroke_match',
                'total_rounds': 2,
            },
        ]

        # Known 2025 results for reference
        self.results_2025 = {
            'U.S. Amateur': {
                'champion': {'first_name': 'Mason', 'last_name': 'Howell'},
                'runner_up': {'first_name': 'Jackson', 'last_name': 'Herrington'},
                'medalist': {'first_name': 'Preston', 'last_name': 'Stout'},
                'medalist_score': 132,  # 2-round qualifying score
                'venue': 'The Olympic Club',
                'city': 'San Francisco',
                'state': 'California',
                'final_score': '7 & 6',
            },
        }

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape USGA amateur championships for a given year.

        Args:
            year: The year to scrape (defaults to current year)

        Returns:
            Dictionary with scrape results
        """
        year = year or datetime.now().year
        self.logger.info(f'Starting USGA amateur tournament scrape for {year}')

        tournaments = self._get_schedule(year)

        if not tournaments:
            return {
                'status': 'failed',
                'error': 'No USGA schedule available for this year',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        today = date.today()

        for t in tournaments:
            try:
                # Determine tournament status
                if t['end_date'] < today:
                    t['status'] = 'completed'
                elif t['start_date'] <= today <= t['end_date']:
                    t['status'] = 'in_progress'
                else:
                    t['status'] = 'scheduled'

                tournament_id = self._process_tournament(t, year)
                self._stats['records_processed'] += 1

                # Try to fetch results for completed tournaments
                if tournament_id and t['status'] == 'completed':
                    self._fetch_and_save_results(tournament_id, t, year)

            except Exception as e:
                self.logger.error(f"Error processing tournament {t['name']}: {e}")
                self._stats['errors'].append(str(e))

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _get_schedule(self, year: int) -> List[Dict]:
        """Get USGA championship schedule for a given year."""
        if year == 2026:
            return self.schedule_2026

        # For other years, try to scrape from USGA website
        # or return empty if not available
        self.logger.warning(f"No hardcoded schedule for {year}, attempting web scrape")
        return self._scrape_schedule(year)

    def _scrape_schedule(self, year: int) -> List[Dict]:
        """
        Scrape USGA championship schedule from website.

        This is a fallback for years not in our hardcoded data.
        """
        schedule = []

        # Try to get schedule from USGA
        url = f'https://www.usga.org/championships.html'
        soup = self.get_page(url)

        if not soup:
            return schedule

        # USGA website structure varies
        # Look for championship cards/links
        for link in soup.find_all('a', href=re.compile(r'championship')):
            text = link.get_text(strip=True)
            if 'Amateur' in text or 'Junior' in text or 'Mid-Amateur' in text:
                # Found a championship link
                self.logger.debug(f"Found championship: {text}")

        return schedule

    def _process_tournament(self, data: Dict, year: int) -> Optional[int]:
        """Process and save a tournament to the database."""
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='USGA').first()
            if not league:
                self.logger.warning("USGA league not found in database")
                return None

            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            if tournament:
                tournament.status = data.get('status', tournament.status)
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    course_name=data.get('course', ''),
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    country=data.get('country', 'USA'),
                    total_rounds=data.get('total_rounds', 2),
                    status=data.get('status', 'scheduled'),
                    usga_tournament_id=data.get('tournament_id', ''),
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f"Created tournament: {name} {year}")

            return tournament.tournament_id

    def _fetch_and_save_results(self, tournament_id: int, data: Dict, year: int):
        """
        Fetch and save results for a completed USGA championship.

        USGA championships use a unique format:
        - 2 rounds of stroke play qualifying
        - Top 64 advance to match play
        - Single elimination bracket to final
        """
        name = data.get('name', 'Unknown')
        self.logger.info(f"Fetching results for {name} {year}")

        # Check if we have known results
        if year == 2025 and name in self.results_2025:
            results = self.results_2025[name]
            self._save_known_results(tournament_id, results)
            return

        # Try to scrape results from AmateurGolf.com
        self._scrape_amateurgolf_results(tournament_id, name, year)

    def _save_known_results(self, tournament_id: int, results: Dict):
        """Save known championship results."""
        with self.db.get_session() as session:
            tournament = session.query(Tournament).filter_by(
                tournament_id=tournament_id
            ).first()
            if not tournament:
                return

            # Save champion
            if 'champion' in results:
                champ = results['champion']
                self._save_player_result(
                    session, tournament,
                    champ['first_name'], champ['last_name'],
                    position=1, position_display='1', result='Champion'
                )

            # Save runner-up
            if 'runner_up' in results:
                ru = results['runner_up']
                self._save_player_result(
                    session, tournament,
                    ru['first_name'], ru['last_name'],
                    position=2, position_display='2', result='Runner-up'
                )

            # Save medalist (stroke play qualifying leader)
            if 'medalist' in results:
                med = results['medalist']
                self._save_player_result(
                    session, tournament,
                    med['first_name'], med['last_name'],
                    position=None, position_display='Medalist',
                    total_score=results.get('medalist_score')
                )

    def _save_player_result(self, session, tournament, first_name: str, last_name: str,
                           position: Optional[int] = None, position_display: str = '',
                           result: str = '', total_score: Optional[int] = None):
        """Save a single player's result."""
        # Find or create player
        player = session.query(Player).filter_by(
            first_name=first_name,
            last_name=last_name
        ).first()

        if not player:
            player = Player(first_name=first_name, last_name=last_name)
            session.add(player)
            session.flush()

        # Check for existing result
        existing = session.query(TournamentResult).filter_by(
            tournament_id=tournament.tournament_id,
            player_id=player.player_id
        ).first()

        if existing:
            existing.final_position = position
            existing.final_position_display = position_display
            existing.total_score = total_score
        else:
            session.add(TournamentResult(
                tournament_id=tournament.tournament_id,
                player_id=player.player_id,
                final_position=position,
                final_position_display=position_display,
                total_score=total_score,
                made_cut=True,  # Champions made it through
                status='active',
            ))

    def _scrape_amateurgolf_results(self, tournament_id: int, name: str, year: int):
        """
        Scrape results from AmateurGolf.com.

        AmateurGolf.com has comprehensive USGA championship coverage
        with stroke play qualifying scores and match play results.
        """
        # Build AmateurGolf URL
        champ_slug = name.lower().replace(' ', '-').replace("'", '')
        url = f'https://www.amateurgolf.com/usga-championships/{champ_slug}/{year}'

        self.logger.debug(f"Attempting to scrape results from: {url}")

        soup = self.get_page(url)
        if not soup:
            return

        # Parse results table
        # AmateurGolf.com typically has:
        # - Stroke play results table
        # - Match play bracket

        with self.db.get_session() as session:
            tournament = session.query(Tournament).filter_by(
                tournament_id=tournament_id
            ).first()
            if not tournament:
                return

            # Find results tables
            tables = soup.find_all('table', class_=re.compile(r'result|leaderboard|score', re.I))

            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        # Try to extract: Position, Name, Score
                        try:
                            pos = cells[0].get_text(strip=True)
                            name_text = cells[1].get_text(strip=True)
                            score_text = cells[2].get_text(strip=True)

                            # Parse name (typically "First Last" or "Last, First")
                            if ',' in name_text:
                                parts = name_text.split(',')
                                last_name = parts[0].strip()
                                first_name = parts[1].strip() if len(parts) > 1 else ''
                            else:
                                parts = name_text.split()
                                first_name = parts[0] if parts else ''
                                last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

                            if first_name and last_name:
                                # Parse position
                                pos_val = None
                                if pos.isdigit():
                                    pos_val = int(pos)
                                elif pos.startswith('T'):
                                    pos_val = int(pos[1:])

                                # Parse score
                                total = None
                                if score_text.isdigit():
                                    total = int(score_text)
                                elif score_text.startswith('+') or score_text.startswith('-'):
                                    # Score relative to par
                                    pass

                                self._save_player_result(
                                    session, tournament,
                                    first_name, last_name,
                                    position=pos_val,
                                    position_display=pos,
                                    total_score=total
                                )

                        except Exception as e:
                            self.logger.debug(f"Could not parse result row: {e}")


def scrape_usga_tournaments(year: Optional[int] = None) -> Dict[str, Any]:
    """Convenience function to scrape USGA amateur tournaments."""
    scraper = USGATournamentScraper()
    return scraper.run(year=year)


if __name__ == '__main__':
    result = scrape_usga_tournaments(year=2026)
    print(f"Scrape complete: {result}")
