"""
Epson Tour Tournament Scraper
==============================

Scrapes Epson Tour tournament schedules and results.
Uses Selenium for JavaScript rendering since the site is React-based.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import time
import re

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League
from config.leagues import get_league_config

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class EpsonTournamentScraper(BaseScraper):
    """
    Scrapes Epson Tour tournaments using Selenium for JS rendering.
    """

    league_code = 'EPSON'
    scrape_type = 'tournament_list'

    def __init__(self):
        config = get_league_config('EPSON')
        base_url = config['base_url'] if config else 'https://www.epsontour.com'
        super().__init__('EPSON', base_url)
        self.tournaments_url = 'https://www.epsontour.com/tournaments'
        self.logger = logger.bind(scraper='EpsonTournamentScraper', league='EPSON')

    def _get_selenium_driver(self):
        """Create a headless Chrome driver for JavaScript rendering."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required for Epson Tour scraping")

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'user-agent={self.user_agent}')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception as e:
            self.logger.error(f"Failed to create Chrome driver: {e}")
            raise

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape Epson Tour tournaments for a given year.

        Args:
            year: The season year to scrape (defaults to current year)
        """
        year = year or datetime.now().year
        self.logger.info(f'Starting Epson Tour tournament scrape for {year}')

        if SELENIUM_AVAILABLE:
            tournaments_data = self._fetch_tournaments_selenium(year)
        else:
            self.logger.warning("Selenium not available, using known schedule")
            tournaments_data = self._get_known_schedule(year)

        if not tournaments_data:
            return {
                'status': 'failed',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for t in tournaments_data:
            try:
                self._process_tournament(t, year)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing tournament: {e}")
                self._stats['errors'].append(str(e))

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _fetch_tournaments_selenium(self, year: int) -> Optional[List[Dict]]:
        """Fetch tournaments using Selenium."""
        driver = None
        tournaments = []

        try:
            driver = self._get_selenium_driver()
            driver.get(self.tournaments_url)

            # Wait for content to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')

            tournaments = self._parse_tournament_cards(soup, year)

            self.logger.info(f'Found {len(tournaments)} Epson Tour tournaments for {year}')

        except Exception as e:
            self.logger.error(f"Selenium tournament scraping failed: {e}")
            self._stats['errors'].append(f"Selenium error: {str(e)}")
            # Fall back to known schedule
            tournaments = self._get_known_schedule(year)

        finally:
            if driver:
                driver.quit()

        return tournaments if tournaments else None

    def _parse_tournament_cards(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse tournament data from the schedule page."""
        tournaments = []

        # Common selectors for tournament cards
        card_selectors = [
            'div[class*="tournament"]',
            'div[class*="event"]',
            'article[class*="tournament"]',
            'a[href*="/tournaments/"]',
        ]

        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                self.logger.debug(f"Found {len(cards)} elements with selector: {selector}")

                for card in cards:
                    tournament_data = self._extract_tournament_from_card(card)
                    if tournament_data and tournament_data.get('name'):
                        # Filter by year if we have a date
                        start_date = tournament_data.get('start_date')
                        if start_date is None or start_date.year == year:
                            tournaments.append(tournament_data)

                if tournaments:
                    break

        return tournaments

    def _extract_tournament_from_card(self, card) -> Optional[Dict]:
        """Extract tournament information from a card element."""
        tournament_data = {
            'name': None,
            'start_date': None,
            'end_date': None,
            'city': None,
            'state': None,
            'country': 'USA',
            'course_name': None,
            'purse': None,
            'status': 'scheduled',
        }

        # Find tournament name
        name_selectors = ['h2', 'h3', 'h4', '[class*="name"]', '[class*="title"]']
        for selector in name_selectors:
            name_elem = card.select_one(selector)
            if name_elem:
                name_text = name_elem.get_text(strip=True)
                if name_text and len(name_text) > 3:
                    tournament_data['name'] = name_text
                    break

        # Find dates
        date_selectors = ['[class*="date"]', 'time', '[class*="when"]']
        for selector in date_selectors:
            date_elem = card.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                dates = self._parse_date_range(date_text)
                if dates:
                    tournament_data['start_date'] = dates[0]
                    tournament_data['end_date'] = dates[1] if len(dates) > 1 else dates[0] + timedelta(days=2)
                    break

        # Find location
        loc_selectors = ['[class*="location"]', '[class*="venue"]', '[class*="course"]']
        for selector in loc_selectors:
            loc_elem = card.select_one(selector)
            if loc_elem:
                loc_text = loc_elem.get_text(strip=True)
                self._parse_tournament_location(tournament_data, loc_text)
                break

        # Find purse
        purse_selectors = ['[class*="purse"]', '[class*="prize"]']
        for selector in purse_selectors:
            purse_elem = card.select_one(selector)
            if purse_elem:
                purse_text = purse_elem.get_text(strip=True)
                purse = self._parse_purse(purse_text)
                if purse:
                    tournament_data['purse'] = purse
                    break

        return tournament_data if tournament_data['name'] else None

    def _parse_date_range(self, date_text: str) -> Optional[List[date]]:
        """Parse date range text into date objects."""
        if not date_text:
            return None

        # Common patterns: "March 5-7, 2026", "Mar 5 - Mar 7", "03/05/2026 - 03/07/2026"
        months = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }

        try:
            # Try "Month Day-Day, Year" pattern
            match = re.search(r'(\w+)\s+(\d+)\s*[-–]\s*(\d+),?\s*(\d{4})', date_text, re.I)
            if match:
                month_str, start_day, end_day, year = match.groups()
                month = months.get(month_str.lower()[:3])
                if month:
                    start = date(int(year), month, int(start_day))
                    end = date(int(year), month, int(end_day))
                    return [start, end]

            # Try "Month Day, Year" for single date
            match = re.search(r'(\w+)\s+(\d+),?\s*(\d{4})', date_text, re.I)
            if match:
                month_str, day, year = match.groups()
                month = months.get(month_str.lower()[:3])
                if month:
                    start = date(int(year), month, int(day))
                    return [start, start + timedelta(days=2)]

        except (ValueError, TypeError):
            pass

        return None

    def _parse_tournament_location(self, tournament_data: Dict, location_text: str):
        """Parse location text for tournament."""
        # Patterns: "City, State" or "Course Name\nCity, State"
        lines = location_text.split('\n')

        for line in lines:
            line = line.strip()
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    # Check if it looks like City, State
                    if len(parts[1]) == 2 or parts[1].lower() in ['florida', 'california', 'texas', 'arizona', 'georgia']:
                        tournament_data['city'] = parts[0]
                        tournament_data['state'] = parts[1]
                    else:
                        tournament_data['course_name'] = parts[0]
                        tournament_data['city'] = parts[1] if len(parts) > 1 else None
            elif line and not tournament_data['course_name']:
                tournament_data['course_name'] = line

    def _parse_purse(self, purse_text: str) -> Optional[int]:
        """Parse purse text to integer (e.g., '$250,000' -> 250000)."""
        if not purse_text:
            return None

        # Remove currency symbols and commas
        cleaned = re.sub(r'[^\d]', '', purse_text)
        if cleaned:
            return int(cleaned)
        return None

    def _get_known_schedule(self, year: int) -> List[Dict]:
        """Return known Epson Tour schedule for given year."""
        # 2026 Epson Tour schedule (based on web search results)
        if year == 2026:
            return [
                {'name': 'Atlantic Beach Classic', 'start_date': date(2026, 3, 5), 'end_date': date(2026, 3, 7),
                 'city': 'Atlantic Beach', 'state': 'FL', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Garden State Championship', 'start_date': date(2026, 3, 19), 'end_date': date(2026, 3, 21),
                 'city': 'Atlantic City', 'state': 'NJ', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'IOA Championship', 'start_date': date(2026, 4, 2), 'end_date': date(2026, 4, 4),
                 'city': 'Beaumont', 'state': 'CA', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Casino Del Sol Golf Classic', 'start_date': date(2026, 4, 16), 'end_date': date(2026, 4, 18),
                 'city': 'Tucson', 'state': 'AZ', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Murphy USA El Dorado Shootout', 'start_date': date(2026, 4, 30), 'end_date': date(2026, 5, 2),
                 'city': 'El Dorado', 'state': 'AR', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Copper Rock Championship', 'start_date': date(2026, 5, 14), 'end_date': date(2026, 5, 16),
                 'city': 'Hurricane', 'state': 'UT', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Mission Inn Resort & Club Championship', 'start_date': date(2026, 5, 28), 'end_date': date(2026, 5, 30),
                 'city': 'Howey-in-the-Hills', 'state': 'FL', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Circling Raven Championship', 'start_date': date(2026, 6, 18), 'end_date': date(2026, 6, 20),
                 'city': 'Worley', 'state': 'ID', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Donald Ross Classic', 'start_date': date(2026, 6, 25), 'end_date': date(2026, 6, 27),
                 'city': 'French Lick', 'state': 'IN', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'FireKeepers Casino Hotel Championship', 'start_date': date(2026, 7, 9), 'end_date': date(2026, 7, 11),
                 'city': 'Battle Creek', 'state': 'MI', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Island Resort Championship', 'start_date': date(2026, 7, 16), 'end_date': date(2026, 7, 18),
                 'city': 'Harris', 'state': 'MI', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Smoky Mountain Championship', 'start_date': date(2026, 7, 30), 'end_date': date(2026, 8, 1),
                 'city': 'Sevierville', 'state': 'TN', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Four Winds Invitational', 'start_date': date(2026, 8, 6), 'end_date': date(2026, 8, 8),
                 'city': 'South Bend', 'state': 'IN', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Wildhorse Ladies Championship', 'start_date': date(2026, 8, 20), 'end_date': date(2026, 8, 22),
                 'city': 'Pendleton', 'state': 'OR', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Link at Union Vale Championship', 'start_date': date(2026, 9, 3), 'end_date': date(2026, 9, 5),
                 'city': 'Lagrangeville', 'state': 'NY', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Valley Forge Invitational', 'start_date': date(2026, 9, 10), 'end_date': date(2026, 9, 12),
                 'city': 'King of Prussia', 'state': 'PA', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Carolina Golf Classic', 'start_date': date(2026, 9, 24), 'end_date': date(2026, 9, 26),
                 'city': 'Myrtle Beach', 'state': 'SC', 'purse': 250000, 'status': 'scheduled'},
                {'name': 'Epson Tour Championship', 'start_date': date(2026, 10, 1), 'end_date': date(2026, 10, 3),
                 'city': 'Indian Wells', 'state': 'CA', 'purse': 300000, 'status': 'scheduled'},
            ]
        else:
            self.logger.warning(f"No known schedule for Epson Tour {year}")
            return []

    def _process_tournament(self, data: Dict, year: int) -> Optional[Tournament]:
        """Process and save a tournament to the database."""
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='EPSON').first()
            if not league:
                return None

            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            # Determine status based on dates
            today = date.today()
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            if end_date and today > end_date:
                status = 'completed'
            elif start_date and end_date and start_date <= today <= end_date:
                status = 'in_progress'
            else:
                status = 'scheduled'

            if tournament:
                tournament.start_date = start_date
                tournament.end_date = end_date
                tournament.city = data.get('city')
                tournament.state = data.get('state')
                tournament.country = data.get('country', 'USA')
                tournament.course_name = data.get('course_name')
                tournament.status = status
                if data.get('purse'):
                    tournament.purse_amount = data['purse']
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=start_date,
                    end_date=end_date,
                    city=data.get('city'),
                    state=data.get('state'),
                    country=data.get('country', 'USA'),
                    course_name=data.get('course_name'),
                    purse_amount=data.get('purse'),
                    status=status,
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created tournament: {name}')

            return tournament


def scrape_epson_tournaments(year=None):
    """Convenience function to scrape Epson Tour tournaments."""
    return EpsonTournamentScraper().run(year=year)
