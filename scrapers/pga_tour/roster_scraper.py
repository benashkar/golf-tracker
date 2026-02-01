"""
PGA Tour Roster Scraper
========================

This module scrapes the PGA Tour player roster from pgatour.com.
It extracts player names, IDs, and basic information.

For Junior Developers:
---------------------
This scraper fetches the list of all PGA Tour players. The PGA Tour website
uses JavaScript to load player data, so we use their API endpoint directly
instead of parsing HTML.

The data flow is:
1. Fetch player list from PGA Tour API
2. Parse player information (name, ID, country)
3. Save to the database
4. Return a summary of what was done

Data Source:
    The PGA Tour uses GraphQL for their API. We make requests to their
    orchestrator endpoint to get player data.

Usage:
    from scrapers.pga_tour.roster_scraper import PGATourRosterScraper

    scraper = PGATourRosterScraper()
    result = scraper.run()
    print(f"Found {result['records_created']} new players")
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player, PlayerLeague, League
from config.leagues import get_league_config


class PGATourRosterScraper(BaseScraper):
    """
    Scrapes the PGA Tour player roster.

    This scraper connects to the PGA Tour website and extracts
    all current players, saving them to our database.

    For Junior Developers:
    ---------------------
    Web scraping is like being a detective - you need to:
    1. Understand how the website works (inspect the network requests)
    2. Find the data you need (usually in JSON responses)
    3. Parse it correctly
    4. Handle errors gracefully

    The PGA Tour website is JavaScript-heavy, which means the HTML
    you see in "View Source" isn't the same as what's on the page.
    Modern websites load data dynamically via APIs.

    Attributes:
        scrape_type: The type of scrape for logging ('roster')
        source_url: The URL being scraped
    """

    # Class-level attributes for logging
    scrape_type = 'roster'

    def __init__(self):
        """Initialize the PGA Tour roster scraper."""
        config = get_league_config('PGA')
        super().__init__('PGA', config['base_url'])

        self.source_url = config['urls']['players']

        # PGA Tour API endpoints
        # These were discovered by inspecting network requests on pgatour.com
        self.api_base = 'https://orchestrator.pgatour.com/graphql'
        self.api_key = 'da2-gsrx5bibzbb4njvhl7t37wqyl4'

        self.logger = logger.bind(
            scraper='PGATourRosterScraper',
            league='PGA'
        )

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """
        Scrape the PGA Tour player roster.

        This method:
        1. Fetches the player list from the PGA Tour API
        2. Parses each player's information
        3. Creates or updates players in the database
        4. Associates players with the PGA Tour league

        Returns:
            Dictionary with:
            - status: 'success' or 'failed'
            - records_processed: Total players found
            - records_created: New players added
            - records_updated: Existing players updated
            - errors: List of any errors encountered

        For Junior Developers:
        ---------------------
        This is the main method that does all the work. It follows
        a common pattern for scraping:
        1. Fetch data
        2. Parse data
        3. Save data
        4. Report results
        """
        self.logger.info("Starting PGA Tour roster scrape")

        # Try to fetch from the API first
        players_data = self._fetch_players_api()

        if not players_data:
            # Fallback to HTML scraping if API fails
            self.logger.warning("API fetch failed, trying HTML scrape")
            players_data = self._fetch_players_html()

        if not players_data:
            self.logger.error("Failed to fetch player data")
            return {
                'status': 'failed',
                'error': 'Could not fetch player data from any source',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        # Process each player
        for player_data in players_data:
            try:
                self._process_player(player_data)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing player: {e}")
                self._stats['errors'].append(f"Player error: {str(e)}")

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

    def _fetch_players_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch player data from the PGA Tour GraphQL API.

        Returns:
            List of player dictionaries, or None if failed

        For Junior Developers:
        ---------------------
        Modern websites often have APIs that power their pages.
        These APIs are often easier to scrape than HTML because:
        1. The data is already structured (JSON)
        2. No HTML parsing needed
        3. Usually more reliable

        To find these APIs, open your browser's Developer Tools,
        go to the Network tab, and reload the page. Look for
        XHR/Fetch requests that return JSON.
        """
        self.logger.info("Fetching players from PGA Tour GraphQL API")

        # Use the working GraphQL playerDirectory query
        return self._fetch_players_graphql()

    def _fetch_players_graphql(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch player data using the PGA Tour GraphQL API.

        Returns:
            List of player dictionaries, or None if failed
        """
        # GraphQL query for player directory - uses enum TourCode (R = PGA Tour)
        query = """
        query {
            playerDirectory(tourCode: R) {
                players {
                    id
                    firstName
                    lastName
                    country
                    isActive
                }
            }
        }
        """

        try:
            response = self.session.post(
                self.api_base,
                json={'query': query},
                headers={
                    **self.get_headers(),
                    'Content-Type': 'application/json',
                    'x-api-key': self.api_key,
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if 'errors' in data:
                self.logger.error(f"GraphQL errors: {data['errors']}")
                return None

            if 'data' in data and 'playerDirectory' in data['data']:
                players_raw = data['data']['playerDirectory']['players']
                players = []
                for p in players_raw:
                    if p.get('isActive', False):
                        players.append({
                            'pga_tour_id': p.get('id', ''),
                            'first_name': p.get('firstName', ''),
                            'last_name': p.get('lastName', ''),
                            'country': p.get('country', ''),
                        })
                self.logger.info(f"Found {len(players)} active players from GraphQL API")
                return players

        except Exception as e:
            self.logger.error(f"GraphQL request failed: {e}")

        return None

    def _fetch_players_html(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fallback method: Scrape player data from HTML.

        This is used if the API endpoints fail. It scrapes the
        player list page directly.

        Returns:
            List of player dictionaries, or None if failed

        For Junior Developers:
        ---------------------
        HTML scraping is more fragile than API scraping because:
        1. HTML structure can change at any time
        2. You need to parse nested elements
        3. The data might be in JavaScript variables

        Always try to find an API first!
        """
        self.logger.info("Fetching players from HTML page")

        soup = self.get_page(self.source_url)
        if not soup:
            return None

        players = []

        # Look for player cards/links
        # Note: This is fragile and may need updating if the site changes
        player_links = soup.find_all('a', href=re.compile(r'/players/player\.\d+\.'))

        for link in player_links:
            try:
                # Extract player ID from URL
                href = link.get('href', '')
                id_match = re.search(r'player\.(\d+)\.', href)
                pga_id = id_match.group(1) if id_match else ''

                # Try to get the player name
                name = link.get_text(strip=True)
                if name and ' ' in name:
                    parts = name.split(' ', 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ''

                    players.append({
                        'pga_tour_id': pga_id,
                        'first_name': first_name,
                        'last_name': last_name,
                    })

            except Exception as e:
                self.logger.debug(f"Error parsing player link: {e}")

        self.logger.info(f"Found {len(players)} players from HTML")
        return players if players else None

    def _process_player(self, player_data: Dict[str, Any]):
        """
        Process and save a single player to the database.

        Args:
            player_data: Dictionary with player information

        For Junior Developers:
        ---------------------
        This method implements an "upsert" pattern:
        - If the player exists, update their information
        - If the player doesn't exist, create them

        We identify players by their pga_tour_id because:
        1. It's unique per player
        2. It doesn't change (unlike names which can have typos)
        """
        pga_tour_id = player_data.get('pga_tour_id', '')
        first_name = player_data.get('first_name', '').strip()
        last_name = player_data.get('last_name', '').strip()

        # Skip if we don't have essential data
        if not first_name or not last_name:
            self.logger.debug(f"Skipping player with missing name: {player_data}")
            return

        with self.db.get_session() as session:
            # Try to find existing player
            player = None

            if pga_tour_id:
                player = session.query(Player).filter_by(
                    pga_tour_id=pga_tour_id
                ).first()

            # If not found by ID, try by name (less reliable but catches some)
            if not player:
                player = session.query(Player).filter_by(
                    first_name=first_name,
                    last_name=last_name
                ).first()

            if player:
                # Update existing player
                self._update_player(player, player_data)
                self._stats['records_updated'] += 1
                self.logger.debug(f"Updated player: {first_name} {last_name}")
            else:
                # Create new player
                player = self._create_player(session, player_data)
                self._stats['records_created'] += 1
                self.logger.info(f"Created new player: {first_name} {last_name}")

            # Ensure player is linked to PGA Tour
            self._ensure_league_association(session, player)

    def _create_player(
        self,
        session,
        player_data: Dict[str, Any]
    ) -> Player:
        """
        Create a new player in the database.

        Args:
            session: Database session
            player_data: Dictionary with player information

        Returns:
            The newly created Player object
        """
        player = Player(
            first_name=player_data.get('first_name', '').strip(),
            last_name=player_data.get('last_name', '').strip(),
            pga_tour_id=player_data.get('pga_tour_id', ''),
            hometown_country=player_data.get('country', ''),
        )
        session.add(player)
        session.flush()  # Get the ID

        return player

    def _update_player(self, player: Player, player_data: Dict[str, Any]):
        """
        Update an existing player with new data.

        Args:
            player: Existing Player object
            player_data: Dictionary with new information

        For Junior Developers:
        ---------------------
        When updating, we only update fields that:
        1. Have new data (not empty)
        2. Were previously empty OR the new data is more complete

        This prevents accidentally overwriting good data with empty values.
        """
        # Update PGA Tour ID if we have one and they don't
        if player_data.get('pga_tour_id') and not player.pga_tour_id:
            player.pga_tour_id = player_data['pga_tour_id']

        # Update country if we have one and they don't
        if player_data.get('country') and not player.hometown_country:
            player.hometown_country = player_data['country']

        player.updated_at = datetime.utcnow()

    def _ensure_league_association(self, session, player: Player):
        """
        Ensure the player is associated with the PGA Tour league.

        Args:
            session: Database session
            player: Player object to associate
        """
        # Get PGA Tour league
        league = session.query(League).filter_by(
            league_code='PGA'
        ).first()

        if not league:
            self.logger.warning("PGA Tour league not found in database")
            return

        # Check if association exists
        existing = session.query(PlayerLeague).filter_by(
            player_id=player.player_id,
            league_id=league.league_id
        ).first()

        if not existing:
            player_league = PlayerLeague(
                player_id=player.player_id,
                league_id=league.league_id,
                league_player_id=player.pga_tour_id,
                is_current_member=True
            )
            session.add(player_league)
            self.logger.debug(
                f"Associated {player.first_name} {player.last_name} with PGA Tour"
            )


# ==============================================================================
# Convenience function for running the scraper
# ==============================================================================
def scrape_pga_roster() -> Dict[str, Any]:
    """
    Convenience function to scrape the PGA Tour roster.

    Returns:
        Dictionary with scrape results

    Example:
        from scrapers.pga_tour.roster_scraper import scrape_pga_roster

        result = scrape_pga_roster()
        print(f"Found {result['records_created']} new players")
    """
    scraper = PGATourRosterScraper()
    return scraper.run()


if __name__ == '__main__':
    # Allow running directly for testing
    # python -m scrapers.pga_tour.roster_scraper
    result = scrape_pga_roster()
    print(f"Scrape complete: {result}")
