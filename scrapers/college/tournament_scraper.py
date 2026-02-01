"""
College Golf Tournament Scraper
================================

Scrapes college golf tournament schedules and results from Golfstat (golfstat.com).
Golfstat is the official source for NCAA college golf statistics.

Data sources:
- Golfstat live scoring: https://www.golfstat.com
- Tournament results with round-by-round scores
- Player/team standings

For Junior Developers:
---------------------
College golf differs from pro golf in several ways:
- Tournaments are team-based (schools compete)
- Typically 3 rounds (54 holes) instead of 4
- Both individual and team scores matter
- Different divisions: D1, D2, D3, NAIA, NJCAA
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
import re
from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League


class CollegeGolfTournamentScraper(BaseScraper):
    """
    Scrapes college golf tournaments from Golfstat.

    Golfstat provides live scoring and historical results for:
    - NCAA Division I, II, III Men's and Women's Golf
    - NAIA Golf
    - NJCAA Golf

    The scraper extracts:
    - Tournament schedules
    - Team standings
    - Individual player results with round-by-round scores
    - Player biographical info (school, class year)
    """

    league_code = 'NCAA_D1_MENS'  # Default to D1 Men's
    scrape_type = 'tournaments'

    # Division codes for Golfstat
    DIVISIONS = {
        'NCAA_D1_MENS': {'code': 'ncaa_d1', 'gender': 'men'},
        'NCAA_D1_WOMENS': {'code': 'ncaa_d1', 'gender': 'women'},
        'NCAA_D2_MENS': {'code': 'ncaa_d2', 'gender': 'men'},
        'NCAA_D2_WOMENS': {'code': 'ncaa_d2', 'gender': 'women'},
        'NCAA_D3_MENS': {'code': 'ncaa_d3', 'gender': 'men'},
        'NCAA_D3_WOMENS': {'code': 'ncaa_d3', 'gender': 'women'},
    }

    def __init__(self, division: str = 'NCAA_D1_MENS'):
        """
        Initialize the college golf scraper.

        Args:
            division: Which NCAA division to scrape (default: NCAA_D1_MENS)
        """
        super().__init__('NCAA', 'https://www.golfstat.com')
        self.division = division
        self.league_code = division
        self.logger = logger.bind(
            scraper='CollegeGolfTournamentScraper',
            division=division
        )

        # Golfstat URLs
        self.base_url = 'https://www.golfstat.com'
        self.schedule_url = f'{self.base_url}/public/scoreboard'

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape college golf tournaments for a given season.

        Args:
            year: The academic year (e.g., 2026 for 2025-26 season)
            division: Override the default division

        Returns:
            Dictionary with scrape results
        """
        year = year or datetime.now().year
        division = kwargs.get('division', self.division)

        self.logger.info(f'Starting college golf tournament scrape for {division} - {year}')

        # Fetch current/live tournaments from scoreboard
        tournaments = self._fetch_scoreboard()

        if not tournaments:
            self.logger.warning('No tournaments found on Golfstat scoreboard')
            return {
                'status': 'partial',
                'message': 'Could not fetch tournaments from Golfstat - site may require authentication',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for t in tournaments:
            try:
                tournament = self._process_tournament(t, year)
                self._stats['records_processed'] += 1

                # Fetch results if tournament has a results URL
                if tournament and t.get('results_url'):
                    self._fetch_and_save_results(tournament, t)

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

    def _fetch_scoreboard(self) -> Optional[List[Dict]]:
        """
        Fetch current tournaments from Golfstat scoreboard.

        Returns:
            List of tournament dictionaries, or empty list if failed
        """
        self.logger.info('Fetching Golfstat scoreboard')

        soup = self.get_page(self.schedule_url)
        if not soup:
            self.logger.warning('Could not fetch Golfstat scoreboard page')
            return []

        tournaments = []

        # Look for tournament entries on the scoreboard
        # Golfstat typically shows live/recent tournaments in sections
        tournament_sections = soup.find_all(['div', 'tr', 'a'],
            class_=re.compile(r'tournament|event|score', re.I))

        for section in tournament_sections:
            try:
                tournament = self._parse_tournament_section(section)
                if tournament:
                    tournaments.append(tournament)
            except Exception as e:
                self.logger.debug(f"Error parsing tournament section: {e}")

        # Also check for links to tournament pages
        links = soup.find_all('a', href=re.compile(r'tournament|leaderboard|results'))
        for link in links:
            try:
                href = link.get('href', '')
                name = link.get_text(strip=True)
                if name and len(name) > 3:  # Filter out short text
                    tournament = {
                        'name': name,
                        'results_url': self._normalize_url(href),
                        'status': 'in_progress' if 'live' in href.lower() else 'completed',
                    }
                    # Avoid duplicates
                    if not any(t.get('name') == name for t in tournaments):
                        tournaments.append(tournament)
            except Exception as e:
                self.logger.debug(f"Error parsing tournament link: {e}")

        self.logger.info(f'Found {len(tournaments)} tournaments on Golfstat')
        return tournaments

    def _parse_tournament_section(self, section) -> Optional[Dict]:
        """Parse a tournament from an HTML section."""
        # Try to find tournament name
        name_elem = section.find(['h3', 'h4', 'a', 'span'],
            class_=re.compile(r'name|title', re.I))
        if not name_elem:
            name_elem = section.find('a')

        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 4:
            return None

        # Try to find dates
        date_elem = section.find(['span', 'div'], class_=re.compile(r'date', re.I))
        start_date = None
        if date_elem:
            start_date = self._parse_date_text(date_elem.get_text(strip=True))

        # Try to find results URL
        results_url = None
        link = section.find('a', href=True)
        if link:
            results_url = self._normalize_url(link.get('href', ''))

        # Try to find course/location
        location_elem = section.find(['span', 'div'], class_=re.compile(r'course|location', re.I))
        course = location_elem.get_text(strip=True) if location_elem else None

        return {
            'name': name,
            'start_date': start_date,
            'course': course,
            'results_url': results_url,
            'status': 'scheduled',
        }

    def _normalize_url(self, url: str) -> str:
        """Convert relative URLs to absolute."""
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('/'):
            return f'{self.base_url}{url}'
        return f'{self.base_url}/{url}'

    def _parse_date_text(self, text: str) -> Optional[date]:
        """Parse various date formats from text."""
        if not text:
            return None

        # Try common formats
        formats = [
            '%B %d, %Y',  # January 15, 2026
            '%b %d, %Y',  # Jan 15, 2026
            '%m/%d/%Y',   # 01/15/2026
            '%Y-%m-%d',   # 2026-01-15
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text.strip(), fmt).date()
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
            # Get or create NCAA league
            league = session.query(League).filter_by(league_code=self.league_code).first()
            if not league:
                # Create NCAA league if it doesn't exist
                league = League(
                    league_code=self.league_code,
                    league_name=f'NCAA {self.division.replace("_", " ").title()}',
                    website_url='https://www.golfstat.com',
                    is_active=True
                )
                session.add(league)
                session.flush()
                self.logger.info(f'Created league: {league.league_name}')

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
                if data.get('course'):
                    tournament.course_name = data['course']
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
                    course_name=data.get('course', ''),
                    status=data.get('status', 'scheduled'),
                    total_rounds=3,  # College golf typically 54 holes
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')

            return tournament.tournament_id

    def _fetch_and_save_results(self, tournament_id: int, data: Dict):
        """
        Fetch and save results for a tournament.

        College golf results include:
        - Team standings
        - Individual player results with round scores
        """
        results_url = data.get('results_url', '')
        if not results_url:
            return

        tournament_name = data.get('name', 'Unknown')
        self.logger.info(f'Fetching results for {tournament_name} from {results_url}')

        soup = self.get_page(results_url)
        if not soup:
            self.logger.warning(f'Could not fetch results page for {tournament_name}')
            return

        # Parse individual results
        results = self._parse_results_page(soup)
        if not results:
            self.logger.warning(f'No results found for {tournament_name}')
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
        Parse player results from a Golfstat results page.

        Returns list of result dictionaries with:
        - player_name
        - school
        - position
        - scores (round 1, 2, 3)
        - total
        - to_par
        """
        results = []

        # Look for leaderboard/results table
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

        # Try to identify columns
        # Common layouts: Pos | Name | School | R1 | R2 | R3 | Total | To Par
        text_values = [c.get_text(strip=True) for c in cells]

        # Skip header rows
        if any(h in text_values[0].lower() for h in ['pos', 'position', 'place', '#']):
            return None

        result = {}

        # Position is usually first column
        pos_text = text_values[0]
        result['position'] = self._parse_position(pos_text)
        result['position_display'] = pos_text

        # Name is usually second column
        result['player_name'] = text_values[1] if len(text_values) > 1 else ''

        # School is usually third column
        result['school'] = text_values[2] if len(text_values) > 2 else ''

        # Look for round scores (usually numeric values 60-90)
        scores = []
        for val in text_values[3:]:
            try:
                score = int(val)
                if 55 <= score <= 95:  # Reasonable golf scores
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

        # Validate - need at least a name
        if not result.get('player_name') or len(result['player_name']) < 2:
            return None

        return result

    def _parse_position(self, pos_text: str) -> Optional[int]:
        """Parse position string to integer."""
        if not pos_text:
            return None
        # Remove 'T' prefix for ties
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
        """Save a single player's result."""
        player_name = result.get('player_name', '').strip()
        if not player_name:
            return

        # Parse name
        name_parts = player_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Get school
        school = result.get('school', '')

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
                college_name=school if school else None,
            )
            session.add(player)
            session.flush()
        elif school and not player.college_name:
            # Update college if we have it
            player.college_name = school

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
            # Create new
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
                made_cut=True,  # College golf typically doesn't have cuts
                status='active',
            ))


def scrape_college_tournaments(year=None, division='NCAA_D1_MENS'):
    """
    Convenience function to scrape college golf tournaments.

    Args:
        year: Season year (defaults to current year)
        division: NCAA division to scrape

    Returns:
        Dictionary with scrape results
    """
    scraper = CollegeGolfTournamentScraper(division=division)
    return scraper.run(year=year)
