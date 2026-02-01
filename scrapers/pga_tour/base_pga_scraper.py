"""
PGA Tour Ecosystem Base Scraper
================================

Base class for all PGA Tour ecosystem scrapers (PGA Tour, Korn Ferry, Champions, etc.)
These tours share the same GraphQL API with different tour codes.

Tour Codes:
    R = PGA Tour
    H = Korn Ferry Tour
    S = PGA Tour Champions
    Y = PGA Tour Americas
    C = PGA Tour Canada
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
from abc import abstractmethod

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player, Tournament, TournamentResult, League, PlayerLeague
from config.leagues import get_league_config


class BasePGAEcosystemScraper(BaseScraper):
    """
    Base scraper for PGA Tour ecosystem tours.

    Subclasses must define:
        - league_code: The code used in our database (e.g., 'PGA', 'KORNFERRY')
        - tour_code: The PGA API tour code (e.g., 'R', 'H', 'S')
        - scrape_type: Type of scrape for logging
    """

    # Subclasses must override these
    league_code: str = None
    tour_code: str = None
    scrape_type: str = 'roster'

    def __init__(self):
        """Initialize the scraper."""
        config = get_league_config(self.league_code)
        base_url = config['base_url'] if config else 'https://www.pgatour.com'
        super().__init__(self.league_code, base_url)

        # GraphQL API endpoints (shared across all PGA ecosystem tours)
        self.api_base = 'https://orchestrator.pgatour.com/graphql'
        self.api_key = 'da2-gsrx5bibzbb4njvhl7t37wqyl4'

        self.logger = logger.bind(
            scraper=self.__class__.__name__,
            league=self.league_code,
            tour_code=self.tour_code
        )

    def _get_graphql_headers(self) -> Dict[str, str]:
        """Get headers for GraphQL requests."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-api-key': self.api_key,
            'Origin': 'https://www.pgatour.com',
            'Referer': 'https://www.pgatour.com/',
        }

    def _graphql_request(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """
        Make a GraphQL request to the PGA Tour API.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Response data dict or None if failed
        """
        try:
            payload = {'query': query}
            if variables:
                payload['variables'] = variables

            response = self.session.post(
                self.api_base,
                json=payload,
                headers=self._get_graphql_headers(),
                timeout=self.timeout
            )

            if not response.text:
                self.logger.error("Empty response from GraphQL API")
                return None

            response.raise_for_status()
            data = response.json()

            if 'errors' in data:
                self.logger.error(f"GraphQL errors: {data['errors']}")
                return None

            return data.get('data')

        except Exception as e:
            self.logger.error(f"GraphQL request failed: {e}")
            return None

    def fetch_players(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch player directory for this tour.

        Returns:
            List of player dictionaries or None if failed
        """
        query = """
        query PlayerDirectory($tourCode: TourCode!) {
            playerDirectory(tourCode: $tourCode) {
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

        # Tour code is an enum, not a string
        query_no_var = f"""
        query {{
            playerDirectory(tourCode: {self.tour_code}) {{
                players {{
                    id
                    firstName
                    lastName
                    country
                    isActive
                }}
            }}
        }}
        """

        data = self._graphql_request(query_no_var)
        if not data or 'playerDirectory' not in data:
            return None

        players_raw = data['playerDirectory'].get('players', [])
        players = []

        for p in players_raw:
            if p.get('isActive', False):
                players.append({
                    'tour_player_id': p.get('id', ''),
                    'first_name': p.get('firstName', ''),
                    'last_name': p.get('lastName', ''),
                    'country': p.get('country', ''),
                })

        self.logger.info(f"Found {len(players)} active players")
        return players

    def fetch_schedule(self, year: int) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch tournament schedule for this tour.

        Args:
            year: Season year

        Returns:
            List of tournament dictionaries or None if failed
        """
        query = f"""
        query {{
            schedule(tourCode: "{self.tour_code}", year: "{year}") {{
                completed {{
                    month
                    tournaments {{
                        id
                        tournamentName
                        startDate
                        city
                        state
                        country
                        purse
                    }}
                }}
                upcoming {{
                    month
                    tournaments {{
                        id
                        tournamentName
                        startDate
                        city
                        state
                        country
                        purse
                    }}
                }}
            }}
        }}
        """

        data = self._graphql_request(query)
        if not data or 'schedule' not in data:
            return None

        schedule = data['schedule']
        tournaments = []

        # Process completed tournaments
        for month_data in schedule.get('completed', []):
            for t in month_data.get('tournaments', []):
                tournaments.append(self._parse_tournament(t, 'completed'))

        # Process upcoming tournaments
        for month_data in schedule.get('upcoming', []):
            for t in month_data.get('tournaments', []):
                tournaments.append(self._parse_tournament(t, 'scheduled'))

        self.logger.info(f"Found {len(tournaments)} tournaments for {year}")
        return tournaments

    def _parse_tournament(self, t: Dict, status: str) -> Dict[str, Any]:
        """Parse tournament data from GraphQL response."""
        start_date = None
        if t.get('startDate'):
            try:
                start_date = datetime.fromtimestamp(t['startDate'] / 1000).date()
            except:
                pass

        purse = None
        if t.get('purse'):
            try:
                purse = Decimal(str(t['purse']).replace('$', '').replace(',', ''))
            except:
                pass

        return {
            'tournament_id': t.get('id', ''),
            'name': t.get('tournamentName', ''),
            'start_date': start_date,
            'city': t.get('city', ''),
            'state': t.get('state', ''),
            'country': t.get('country', 'USA'),
            'purse': purse,
            'status': status,
        }

    def fetch_leaderboard(self, tournament_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch leaderboard/results for a tournament.

        Args:
            tournament_id: The tournament ID (e.g., 'R2026006')

        Returns:
            List of player result dictionaries or None if failed
        """
        query = """
        query Leaderboard($id: ID!) {
            leaderboardV2(id: $id) {
                id
                players {
                    ... on PlayerRowV2 {
                        id
                        position
                        total
                        score
                        player {
                            id
                            firstName
                            lastName
                            country
                        }
                    }
                }
            }
        }
        """

        data = self._graphql_request(query, {'id': tournament_id})
        if not data or 'leaderboardV2' not in data:
            return None

        players = data['leaderboardV2'].get('players', [])
        # Filter out empty entries
        return [p for p in players if p and p.get('player')]

    def _parse_position(self, position_str: str) -> Optional[int]:
        """Parse position string to integer (e.g., 'T4' -> 4)."""
        if not position_str:
            return None
        clean = position_str.replace('T', '').strip()
        try:
            return int(clean)
        except (ValueError, TypeError):
            return None

    def _parse_to_par(self, par_str: str) -> Optional[int]:
        """Parse to-par string (e.g., '-16' -> -16, 'E' -> 0)."""
        if not par_str:
            return None
        if par_str == 'E':
            return 0
        try:
            return int(par_str)
        except (ValueError, TypeError):
            return None
