"""
AJGA (American Junior Golf Association) Tournament Scraper
===========================================================

Scrapes AJGA tournament schedules and results from ajga.org.

AJGA is the premier junior golf tour in the US, featuring players ages 12-19.
These players are excellent for local news stories since:
- They're typically still in high school or recently graduated
- Most are from the USA with strong local connections
- High school name, graduation year, and hometown are often available

Data sources:
- AJGA Schedule: https://www.ajga.org/schedule
- BlueGolf Platform: https://ajga.bluegolf.com
- Legacy Results: https://legacy.ajga.org

For Junior Developers:
---------------------
AJGA players are junior golfers (under 19). The data model is similar
to professional tours, but with additional fields like:
- High school information (very relevant for our use case!)
- Class year (freshman, sophomore, etc.)
- Age category
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
import re
from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League


class AJGATournamentScraper(BaseScraper):
    """
    Scrapes AJGA tournament data.

    The AJGA provides:
    - Tournament schedules and results
    - Player profiles with high school and hometown
    - Live scoring during events

    This is valuable for local news because junior golfers
    have strong local connections (high school, hometown).
    """

    league_code = 'AJGA'
    scrape_type = 'tournaments'

    def __init__(self):
        """Initialize the AJGA scraper."""
        super().__init__('AJGA', 'https://www.ajga.org')
        self.logger = logger.bind(scraper='AJGATournamentScraper')

        # AJGA URLs
        self.base_url = 'https://www.ajga.org'
        self.schedule_url = f'{self.base_url}/schedule'
        self.results_url = f'{self.base_url}/tournaments/archived-results'
        self.bluegolf_url = 'https://ajga.bluegolf.com/bluegolf/ajga/schedule'

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape AJGA tournaments for a given year.

        Args:
            year: The year to scrape (defaults to current year)

        Returns:
            Dictionary with scrape results
        """
        year = year or datetime.now().year
        self.logger.info(f'Starting AJGA tournament scrape for {year}')

        # Fetch tournaments from schedule page
        tournaments = self._fetch_schedule(year)

        if not tournaments:
            self.logger.warning('No AJGA tournaments found')
            return {
                'status': 'partial',
                'message': 'Could not fetch AJGA tournaments',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for t in tournaments:
            try:
                tournament_id = self._process_tournament(t, year)
                self._stats['records_processed'] += 1

                # Fetch results if available
                if tournament_id and t.get('results_url'):
                    self._fetch_and_save_results(tournament_id, t)

            except Exception as e:
                self.logger.error(f"Error processing tournament {t.get('name', 'unknown')}: {e}")
                self._stats['errors'].append(str(e))

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _fetch_schedule(self, year: int) -> List[Dict]:
        """
        Fetch AJGA tournament schedule.

        Returns:
            List of tournament dictionaries
        """
        self.logger.info(f'Fetching AJGA schedule for {year}')
        tournaments = []

        # Try the main schedule page
        schedule_url = f'{self.schedule_url}/{year}' if year != datetime.now().year else self.schedule_url
        soup = self.get_page(schedule_url)

        if soup:
            tournaments.extend(self._parse_schedule_page(soup, year))

        # Also try BlueGolf for additional events
        bluegolf_soup = self.get_page(f'{self.bluegolf_url}/index.htm')
        if bluegolf_soup:
            tournaments.extend(self._parse_bluegolf_schedule(bluegolf_soup, year))

        # Deduplicate by name
        seen = set()
        unique_tournaments = []
        for t in tournaments:
            name = t.get('name', '')
            if name and name not in seen:
                seen.add(name)
                unique_tournaments.append(t)

        self.logger.info(f'Found {len(unique_tournaments)} AJGA tournaments')
        return unique_tournaments

    def _parse_schedule_page(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse the AJGA schedule page."""
        tournaments = []

        # Look for tournament entries
        # AJGA typically lists tournaments in cards or list items
        event_elements = soup.find_all(['div', 'article', 'li'],
            class_=re.compile(r'event|tournament|schedule', re.I))

        for elem in event_elements:
            try:
                tournament = self._parse_tournament_element(elem)
                if tournament:
                    tournaments.append(tournament)
            except Exception as e:
                self.logger.debug(f"Error parsing tournament element: {e}")

        # Also look for links to tournament pages
        links = soup.find_all('a', href=re.compile(r'/tournaments?/|leaderboard|results'))
        for link in links:
            href = link.get('href', '')
            name = link.get_text(strip=True)

            # Filter out navigation links
            if name and len(name) > 5 and not any(nav in name.lower() for nav in ['schedule', 'home', 'about', 'register']):
                tournament = {
                    'name': name,
                    'results_url': self._normalize_url(href),
                    'status': 'scheduled',
                }
                tournaments.append(tournament)

        return tournaments

    def _parse_bluegolf_schedule(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse BlueGolf schedule page for AJGA events."""
        tournaments = []

        # BlueGolf uses tables for tournament listings
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell often has tournament name/link
                    link = cells[0].find('a')
                    if link:
                        name = link.get_text(strip=True)
                        href = link.get('href', '')

                        if name and len(name) > 3:
                            # Try to find date in other cells
                            start_date = None
                            for cell in cells[1:]:
                                text = cell.get_text(strip=True)
                                start_date = self._parse_date_text(text)
                                if start_date:
                                    break

                            tournaments.append({
                                'name': name,
                                'results_url': self._normalize_url(href),
                                'start_date': start_date,
                                'status': 'scheduled',
                            })

        return tournaments

    def _parse_tournament_element(self, elem) -> Optional[Dict]:
        """Parse a single tournament element from HTML."""
        # Try to find name
        name_elem = elem.find(['h3', 'h4', 'h5', 'a', 'span'],
            class_=re.compile(r'title|name', re.I))
        if not name_elem:
            name_elem = elem.find('a')

        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 4:
            return None

        # Try to find date
        date_elem = elem.find(['span', 'div', 'time'],
            class_=re.compile(r'date', re.I))
        start_date = None
        if date_elem:
            start_date = self._parse_date_text(date_elem.get_text(strip=True))

        # Try to find location
        location_elem = elem.find(['span', 'div'],
            class_=re.compile(r'location|venue|course', re.I))
        location = location_elem.get_text(strip=True) if location_elem else None

        # Try to find results URL
        results_url = None
        link = elem.find('a', href=True)
        if link:
            results_url = self._normalize_url(link.get('href', ''))

        return {
            'name': name,
            'start_date': start_date,
            'location': location,
            'results_url': results_url,
            'status': 'scheduled',
        }

    def _normalize_url(self, url: str) -> str:
        """Convert relative URLs to absolute."""
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return f'https:{url}'
        if url.startswith('/'):
            return f'{self.base_url}{url}'
        return f'{self.base_url}/{url}'

    def _parse_date_text(self, text: str) -> Optional[date]:
        """Parse various date formats from text."""
        if not text:
            return None

        # Common formats
        formats = [
            '%B %d, %Y',      # January 15, 2026
            '%b %d, %Y',      # Jan 15, 2026
            '%m/%d/%Y',       # 01/15/2026
            '%Y-%m-%d',       # 2026-01-15
            '%B %d-%d, %Y',   # January 15-17, 2026 (take first date)
        ]

        # Clean the text - extract first date if range
        clean_text = re.sub(r'-\d+', '', text).strip()

        for fmt in formats:
            try:
                return datetime.strptime(clean_text, fmt).date()
            except ValueError:
                continue

        return None

    def _process_tournament(self, data: Dict, year: int) -> Optional[int]:
        """
        Process and save a tournament to the database.

        Returns tournament_id to avoid session detachment.
        """
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            # Get or create AJGA league
            league = session.query(League).filter_by(league_code='AJGA').first()
            if not league:
                league = League(
                    league_code='AJGA',
                    league_name='American Junior Golf Association',
                    website_url='https://www.ajga.org',
                    is_active=True
                )
                session.add(league)
                session.flush()
                self.logger.info('Created AJGA league')

            # Check if tournament exists
            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            if tournament:
                # Update existing
                if data.get('start_date'):
                    tournament.start_date = data['start_date']
                if data.get('location'):
                    tournament.course_name = data['location']
                if data.get('status'):
                    tournament.status = data['status']
                self._stats['records_updated'] += 1
            else:
                # Create new
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    course_name=data.get('location', ''),
                    status=data.get('status', 'scheduled'),
                    total_rounds=3,  # AJGA typically 54 holes
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')

            return tournament.tournament_id

    def _fetch_and_save_results(self, tournament_id: int, data: Dict):
        """
        Fetch and save results for a tournament.

        AJGA results include:
        - Player name
        - High school / hometown (very important for our use case!)
        - Round-by-round scores
        - Final position
        """
        results_url = data.get('results_url', '')
        if not results_url:
            return

        tournament_name = data.get('name', 'Unknown')
        self.logger.info(f'Fetching results for {tournament_name}')

        soup = self.get_page(results_url)
        if not soup:
            self.logger.warning(f'Could not fetch results for {tournament_name}')
            return

        results = self._parse_results_page(soup)
        if not results:
            self.logger.debug(f'No results found for {tournament_name}')
            return

        self.logger.info(f'Found {len(results)} player results for {tournament_name}')

        with self.db.get_session() as session:
            tournament = session.query(Tournament).get(tournament_id)
            if not tournament:
                return

            for result in results:
                try:
                    self._save_player_result(session, tournament, result)
                except Exception as e:
                    self.logger.error(f"Error saving result: {e}")

    def _parse_results_page(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse player results from an AJGA results page.

        AJGA results often include hometown/high school which is
        exactly what we need for local news stories!
        """
        results = []

        # Look for leaderboard tables
        tables = soup.find_all('table', class_=re.compile(r'leaderboard|results|scores', re.I))
        if not tables:
            tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue

                try:
                    result = self._parse_result_row(cells)
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.debug(f"Error parsing result row: {e}")

        return results

    def _parse_result_row(self, cells) -> Optional[Dict]:
        """Parse a single result row from a table."""
        if len(cells) < 3:
            return None

        text_values = [c.get_text(strip=True) for c in cells]

        # Skip header rows
        if any(h in text_values[0].lower() for h in ['pos', 'position', 'place', '#', 'rank']):
            return None

        result = {}

        # Position is usually first column
        pos_text = text_values[0]
        result['position'] = self._parse_position(pos_text)
        result['position_display'] = pos_text

        # Name is usually second column
        result['player_name'] = text_values[1] if len(text_values) > 1 else ''

        # Look for hometown/state (often in format "City, ST" or just state abbreviation)
        for i, val in enumerate(text_values[2:], start=2):
            # Check for state abbreviation pattern
            if re.match(r'^[A-Z]{2}$', val):
                result['state'] = val
            # Check for city, state pattern
            elif ',' in val and len(val) < 50:
                parts = val.split(',')
                if len(parts) == 2:
                    result['hometown_city'] = parts[0].strip()
                    result['hometown_state'] = parts[1].strip()
            # Check for high school pattern
            elif 'high school' in val.lower() or 'hs' in val.lower():
                result['high_school'] = val

        # Look for round scores (numeric values 55-95)
        scores = []
        for val in text_values[2:]:
            try:
                score = int(val)
                if 55 <= score <= 95:
                    scores.append(score)
            except ValueError:
                pass

        # Assign round scores
        result['round_1'] = scores[0] if len(scores) > 0 else None
        result['round_2'] = scores[1] if len(scores) > 1 else None
        result['round_3'] = scores[2] if len(scores) > 2 else None

        # Calculate total
        if scores:
            result['total'] = sum(scores)

        # Try to find to-par value
        for val in text_values:
            if val.startswith('+') or val.startswith('-') or val == 'E':
                result['to_par'] = self._parse_to_par(val)
                break

        # Validate
        if not result.get('player_name') or len(result['player_name']) < 2:
            return None

        return result

    def _parse_position(self, pos_text: str) -> Optional[int]:
        """Parse position string to integer."""
        if not pos_text:
            return None
        clean = pos_text.replace('T', '').strip()
        try:
            return int(clean)
        except ValueError:
            return None

    def _parse_to_par(self, par_text: str) -> Optional[int]:
        """Parse to-par string to integer."""
        if not par_text:
            return None
        if par_text == 'E':
            return 0
        try:
            return int(par_text)
        except ValueError:
            return None

    def _save_player_result(self, session, tournament: Tournament, result: Dict):
        """
        Save a single player's result.

        For junior golfers, we're especially interested in capturing:
        - High school name
        - Hometown (city, state)
        - Class year / graduation year
        """
        player_name = result.get('player_name', '').strip()
        if not player_name:
            return

        # Parse name
        name_parts = player_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Find or create player
        player = session.query(Player).filter_by(
            first_name=first_name,
            last_name=last_name
        ).first()

        if not player:
            if not first_name or not last_name:
                return
            player = Player(
                first_name=first_name,
                last_name=last_name,
            )
            session.add(player)
            session.flush()

        # Update player with hometown/high school info if we found it
        if result.get('hometown_city') and not player.hometown_city:
            player.hometown_city = result['hometown_city']
        if result.get('hometown_state') and not player.hometown_state:
            player.hometown_state = result['hometown_state']
        if result.get('state') and not player.hometown_state:
            player.hometown_state = result['state']
        if result.get('high_school') and not player.high_school_name:
            player.high_school_name = result['high_school']

        # Check for existing result
        existing = session.query(TournamentResult).filter_by(
            tournament_id=tournament.tournament_id,
            player_id=player.player_id
        ).first()

        pos = result.get('position')
        pos_display = result.get('position_display', str(pos) if pos else '')

        if existing:
            # Update
            existing.final_position = pos
            existing.final_position_display = pos_display
            existing.total_to_par = result.get('to_par')
            existing.total_score = result.get('total')
            existing.round_1_score = result.get('round_1')
            existing.round_2_score = result.get('round_2')
            existing.round_3_score = result.get('round_3')
        else:
            # Create
            session.add(TournamentResult(
                tournament_id=tournament.tournament_id,
                player_id=player.player_id,
                final_position=pos,
                final_position_display=pos_display,
                total_to_par=result.get('to_par'),
                total_score=result.get('total'),
                round_1_score=result.get('round_1'),
                round_2_score=result.get('round_2'),
                round_3_score=result.get('round_3'),
                made_cut=True,
                status='active',
            ))


def scrape_ajga_tournaments(year=None):
    """
    Convenience function to scrape AJGA tournaments.

    Args:
        year: Season year (defaults to current year)

    Returns:
        Dictionary with scrape results
    """
    scraper = AJGATournamentScraper()
    return scraper.run(year=year)
