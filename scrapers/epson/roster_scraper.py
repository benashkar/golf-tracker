"""
Epson Tour Roster Scraper
=========================

Scrapes the Epson Tour player roster from epsontour.com.
Uses Selenium for JavaScript rendering since the site is React-based.

This is a HIGH-VALUE data source for American high school connections because:
- Most Epson Tour players are Americans who played NCAA golf
- They typically have strong hometown/high school connections
- Perfect for local news research
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import time
import re

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player, PlayerLeague, League
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


class EpsonRosterScraper(BaseScraper):
    """
    Scrapes Epson Tour player roster using Selenium for JS rendering.

    The Epson Tour website uses React/JavaScript for rendering content,
    so we need Selenium to properly load and parse the athlete directory.
    """

    league_code = 'EPSON'
    scrape_type = 'roster'

    def __init__(self):
        config = get_league_config('EPSON')
        base_url = config['base_url'] if config else 'https://www.epsontour.com'
        super().__init__('EPSON', base_url)
        self.athletes_url = 'https://www.epsontour.com/athletes/directory'
        self.logger = logger.bind(scraper='EpsonRosterScraper', league='EPSON')

    def _get_selenium_driver(self):
        """Create a headless Chrome driver for JavaScript rendering."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required for Epson Tour scraping. Install with: pip install selenium webdriver-manager")

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

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """Scrape the Epson Tour roster with full biographical data."""
        self.logger.info('Starting Epson Tour roster scrape')

        # Try Selenium-based scraping first
        if SELENIUM_AVAILABLE:
            players_data = self._fetch_players_selenium()
        else:
            # Fallback to basic HTTP (may not work for JS-heavy sites)
            self.logger.warning("Selenium not available, trying basic HTTP scrape")
            players_data = self._fetch_players_basic()

        if not players_data:
            return {
                'status': 'failed',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for p in players_data:
            try:
                self._process_player(p)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing player: {e}")
                self._stats['errors'].append(str(e))

        return {
            'status': 'success' if not self._stats['errors'] else 'partial',
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _fetch_players_selenium(self) -> Optional[List[Dict]]:
        """Fetch players using Selenium for JavaScript rendering."""
        driver = None
        players = []

        try:
            driver = self._get_selenium_driver()
            driver.get(self.athletes_url)

            # Wait for content to load
            self.logger.info("Waiting for athlete directory to load...")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Give extra time for React to render
            time.sleep(3)

            # Scroll to load more players (many sites use infinite scroll)
            self._scroll_to_load_all(driver)

            # Get the rendered HTML
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')

            # Parse player cards - try multiple selectors
            players = self._parse_athlete_cards(soup)

            if not players:
                # Try alternative parsing strategies
                players = self._parse_athlete_links(soup)

            self.logger.info(f'Found {len(players)} Epson Tour players')

        except Exception as e:
            self.logger.error(f"Selenium scraping failed: {e}")
            self._stats['errors'].append(f"Selenium error: {str(e)}")

        finally:
            if driver:
                driver.quit()

        return players if players else None

    def _scroll_to_load_all(self, driver, max_scrolls: int = 10):
        """Scroll down to load all players (for infinite scroll sites)."""
        last_height = driver.execute_script("return document.body.scrollHeight")

        for i in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for content to load

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _parse_athlete_cards(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse athlete data from card-style layouts."""
        players = []

        # Common CSS patterns for athlete cards
        card_selectors = [
            'div[class*="athlete"]',
            'div[class*="player"]',
            'a[href*="/athletes/"]',
            'div[class*="card"]',
            'article[class*="athlete"]',
        ]

        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                self.logger.debug(f"Found {len(cards)} elements with selector: {selector}")

                for card in cards:
                    player_data = self._extract_player_from_card(card)
                    if player_data and player_data.get('first_name'):
                        players.append(player_data)

                if players:
                    break

        return players

    def _parse_athlete_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse players from athlete profile links."""
        players = []

        # Find all links to athlete profiles
        links = soup.find_all('a', href=re.compile(r'/athletes/[^/]+/?$'))

        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            if text and '/athletes/' in href:
                # Extract name from link text
                names = text.split()
                if len(names) >= 2:
                    player_data = {
                        'first_name': names[0],
                        'last_name': ' '.join(names[1:]),
                        'profile_url': f"https://www.epsontour.com{href}" if href.startswith('/') else href,
                    }
                    players.append(player_data)

        return players

    def _extract_player_from_card(self, card) -> Optional[Dict]:
        """Extract player information from an athlete card element."""
        player_data = {
            'first_name': None,
            'last_name': None,
            'hometown_city': None,
            'hometown_state': None,
            'hometown_country': None,
            'college_name': None,
            'profile_url': None,
        }

        # Try to find player name
        name_selectors = [
            'h2', 'h3', 'h4',
            '[class*="name"]',
            '[class*="title"]',
            'a[href*="/athletes/"]',
        ]

        for selector in name_selectors:
            name_elem = card.select_one(selector)
            if name_elem:
                name_text = name_elem.get_text(strip=True)
                if name_text and ' ' in name_text:
                    parts = name_text.split(None, 1)
                    player_data['first_name'] = parts[0]
                    player_data['last_name'] = parts[1] if len(parts) > 1 else ''
                    break

        # Try to find location/hometown
        location_selectors = [
            '[class*="location"]',
            '[class*="hometown"]',
            '[class*="country"]',
            'span[class*="meta"]',
        ]

        for selector in location_selectors:
            loc_elem = card.select_one(selector)
            if loc_elem:
                loc_text = loc_elem.get_text(strip=True)
                if loc_text:
                    self._parse_location(player_data, loc_text)
                    break

        # Try to find profile link
        link = card.find('a', href=re.compile(r'/athletes/'))
        if link:
            href = link.get('href', '')
            player_data['profile_url'] = f"https://www.epsontour.com{href}" if href.startswith('/') else href

        return player_data if player_data['first_name'] else None

    def _parse_location(self, player_data: Dict, location_text: str):
        """Parse location text into city, state, country."""
        # Common formats: "City, State", "City, State, Country", "Country"
        parts = [p.strip() for p in location_text.split(',')]

        if len(parts) >= 3:
            player_data['hometown_city'] = parts[0]
            player_data['hometown_state'] = parts[1]
            player_data['hometown_country'] = parts[2]
        elif len(parts) == 2:
            player_data['hometown_city'] = parts[0]
            # Check if second part is a US state abbreviation
            if len(parts[1]) == 2 and parts[1].isupper():
                player_data['hometown_state'] = parts[1]
                player_data['hometown_country'] = 'USA'
            else:
                player_data['hometown_state'] = parts[1]
        elif len(parts) == 1:
            player_data['hometown_country'] = parts[0]

    def _fetch_players_basic(self) -> Optional[List[Dict]]:
        """Fallback: Try basic HTTP scrape (unlikely to work for JS sites)."""
        soup = self.get_page(self.athletes_url)
        if not soup:
            return None

        players = self._parse_athlete_cards(soup)
        if not players:
            players = self._parse_athlete_links(soup)

        return players if players else None

    def _process_player(self, player_data: Dict):
        """Process and save a player to the database."""
        first_name = player_data.get('first_name', '').strip()
        last_name = player_data.get('last_name', '').strip()

        if not first_name or not last_name:
            return

        with self.db.get_session() as session:
            # Try to find existing player by name
            player = session.query(Player).filter_by(
                first_name=first_name,
                last_name=last_name
            ).first()

            if player:
                self._update_player(player, player_data)
                self._stats['records_updated'] += 1
            else:
                player = self._create_player(session, player_data)
                self._stats['records_created'] += 1
                self.logger.info(f'Created player: {first_name} {last_name}')

            self._ensure_league(session, player)

    def _create_player(self, session, player_data: Dict) -> Player:
        """Create a new player."""
        player = Player(
            first_name=player_data.get('first_name', '').strip(),
            last_name=player_data.get('last_name', '').strip(),
            hometown_city=player_data.get('hometown_city'),
            hometown_state=player_data.get('hometown_state'),
            hometown_country=player_data.get('hometown_country'),
            college_name=player_data.get('college_name'),
        )
        session.add(player)
        session.flush()
        return player

    def _update_player(self, player: Player, player_data: Dict):
        """Update existing player with new data (only fill in missing fields)."""
        if player_data.get('hometown_city') and not player.hometown_city:
            player.hometown_city = player_data['hometown_city']
        if player_data.get('hometown_state') and not player.hometown_state:
            player.hometown_state = player_data['hometown_state']
        if player_data.get('hometown_country') and not player.hometown_country:
            player.hometown_country = player_data['hometown_country']
        if player_data.get('college_name') and not player.college_name:
            player.college_name = player_data['college_name']

        player.updated_at = datetime.utcnow()

    def _ensure_league(self, session, player: Player):
        """Ensure player is associated with Epson Tour league."""
        league = session.query(League).filter_by(league_code='EPSON').first()
        if not league:
            return

        existing = session.query(PlayerLeague).filter_by(
            player_id=player.player_id,
            league_id=league.league_id
        ).first()

        if not existing:
            session.add(PlayerLeague(
                player_id=player.player_id,
                league_id=league.league_id,
                is_current_member=True
            ))


def scrape_epson_roster():
    """Convenience function to scrape Epson Tour roster."""
    return EpsonRosterScraper().run()
