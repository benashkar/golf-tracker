"""
DP World Tour Roster Scraper
=============================

Scrapes the DP World Tour (formerly European Tour) player roster.
Uses the European Tour API and ESPN for biographical data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player, PlayerLeague, League


class DPWorldRosterScraper(BaseScraper):
    """
    Scrapes the DP World Tour player roster.

    Uses multiple sources:
    1. DP World Tour official API
    2. ESPN Golf API for biographical data
    """

    league_code = 'DPWORLD'
    scrape_type = 'roster'

    def __init__(self):
        super().__init__('DPWORLD', 'https://www.europeantour.com')

        # API endpoints
        self.dpworld_api = 'https://www.europeantour.com/api/players'
        self.espn_api = 'https://sports.core.api.espn.com/v2/sports/golf/leagues/eur'

        self.logger = logger.bind(scraper='DPWorldRosterScraper', league='DPWORLD')

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """Scrape the DP World Tour roster."""
        self.logger.info("Starting DP World Tour roster scrape")

        # Try ESPN API first (more reliable for player data)
        players_data = self._fetch_players_espn()

        if not players_data:
            self.logger.warning("ESPN fetch failed, trying DP World API")
            players_data = self._fetch_players_dpworld()

        if not players_data:
            return {
                'status': 'failed',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': ['Could not fetch player data']
            }

        for player_data in players_data:
            try:
                self._process_player(player_data)
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

    def _fetch_players_espn(self) -> Optional[List[Dict]]:
        """Fetch players from ESPN's European Tour API."""
        players = []
        page = 1

        while True:
            url = f'{self.espn_api}/athletes?limit=100&page={page}'
            self.logger.debug(f"Fetching ESPN page {page}: {url}")

            data = self.get_json(url)
            if not data or 'items' not in data:
                break

            for item in data['items']:
                ref = item.get('$ref', '')
                if ref:
                    player_data = self.get_json(ref)
                    if player_data:
                        # Get detailed bio data
                        bio_data = self._extract_espn_bio(player_data)
                        if bio_data:
                            players.append(bio_data)

            if page >= data.get('pageCount', 1):
                break
            page += 1
            if page > 15:  # Safety limit
                break

        self.logger.info(f"Found {len(players)} DP World Tour players from ESPN")
        return players if players else None

    def _extract_espn_bio(self, data: Dict) -> Optional[Dict]:
        """Extract biographical data from ESPN player response."""
        if not data.get('firstName') or not data.get('lastName'):
            return None

        player_info = {
            'espn_id': str(data.get('id', '')),
            'first_name': data.get('firstName', '').strip(),
            'last_name': data.get('lastName', '').strip(),
            'birth_date': None,
            'birthplace_city': None,
            'birthplace_state': None,
            'birthplace_country': None,
            'hometown_city': None,
            'hometown_state': None,
            'hometown_country': None,
            'college_name': None,
        }

        # Parse birthplace
        birthplace = data.get('birthPlace', {})
        if birthplace:
            player_info['birthplace_city'] = birthplace.get('city')
            player_info['birthplace_state'] = birthplace.get('state')
            player_info['birthplace_country'] = birthplace.get('country')
            # Use birthplace as hometown if not specified
            if not player_info['hometown_city']:
                player_info['hometown_city'] = birthplace.get('city')
                player_info['hometown_state'] = birthplace.get('state')
                player_info['hometown_country'] = birthplace.get('country')

        # Parse birth date
        if data.get('dateOfBirth'):
            try:
                player_info['birth_date'] = datetime.strptime(
                    data['dateOfBirth'][:10], '%Y-%m-%d'
                ).date()
            except:
                pass

        # Parse college from experience or other fields
        experience = data.get('experience', {})
        if isinstance(experience, dict):
            college = experience.get('college')
            if college:
                player_info['college_name'] = college

        # Check for college in statistics or other nested data
        if not player_info['college_name']:
            for stat in data.get('statistics', []):
                if 'college' in str(stat).lower():
                    # Try to extract college name
                    pass

        return player_info

    def _fetch_players_dpworld(self) -> Optional[List[Dict]]:
        """Fetch players from DP World Tour API."""
        try:
            # Try the rankings/players endpoint
            url = 'https://www.europeantour.com/api/players/search?limit=500'
            data = self.get_json(url)

            if data and isinstance(data, list):
                players = []
                for p in data:
                    players.append({
                        'dpworld_id': str(p.get('playerId', '')),
                        'first_name': p.get('firstName', '').strip(),
                        'last_name': p.get('lastName', '').strip(),
                        'hometown_country': p.get('country', ''),
                    })
                return players
        except Exception as e:
            self.logger.error(f"DP World API error: {e}")

        return None

    def _process_player(self, player_data: Dict):
        """Process and save a player to the database."""
        first_name = player_data.get('first_name', '').strip()
        last_name = player_data.get('last_name', '').strip()
        espn_id = player_data.get('espn_id', '')
        dpworld_id = player_data.get('dpworld_id', '')

        if not first_name or not last_name:
            return

        with self.db.get_session() as session:
            # Try to find existing player
            player = None

            if espn_id:
                player = session.query(Player).filter_by(espn_id=espn_id).first()

            if not player and dpworld_id:
                player = session.query(Player).filter_by(dpworld_id=dpworld_id).first()

            if not player:
                player = session.query(Player).filter_by(
                    first_name=first_name, last_name=last_name
                ).first()

            if player:
                self._update_player(player, player_data)
                self._stats['records_updated'] += 1
            else:
                player = self._create_player(session, player_data)
                self._stats['records_created'] += 1
                self.logger.info(f"Created player: {first_name} {last_name}")

            self._ensure_league_association(session, player)

    def _create_player(self, session, player_data: Dict) -> Player:
        """Create a new player."""
        player = Player(
            first_name=player_data.get('first_name', '').strip(),
            last_name=player_data.get('last_name', '').strip(),
            espn_id=player_data.get('espn_id'),
            dpworld_id=player_data.get('dpworld_id'),
            birth_date=player_data.get('birth_date'),
            birthplace_city=player_data.get('birthplace_city'),
            birthplace_state=player_data.get('birthplace_state'),
            birthplace_country=player_data.get('birthplace_country'),
            hometown_city=player_data.get('hometown_city'),
            hometown_state=player_data.get('hometown_state'),
            hometown_country=player_data.get('hometown_country'),
            college_name=player_data.get('college_name'),
        )
        session.add(player)
        session.flush()
        return player

    def _update_player(self, player: Player, player_data: Dict):
        """Update existing player with new data."""
        if player_data.get('espn_id') and not player.espn_id:
            player.espn_id = player_data['espn_id']
        if player_data.get('dpworld_id') and not player.dpworld_id:
            player.dpworld_id = player_data['dpworld_id']
        if player_data.get('birth_date') and not player.birth_date:
            player.birth_date = player_data['birth_date']
        if player_data.get('birthplace_city') and not player.birthplace_city:
            player.birthplace_city = player_data['birthplace_city']
        if player_data.get('birthplace_country') and not player.birthplace_country:
            player.birthplace_country = player_data['birthplace_country']
        if player_data.get('hometown_city') and not player.hometown_city:
            player.hometown_city = player_data['hometown_city']
        if player_data.get('hometown_state') and not player.hometown_state:
            player.hometown_state = player_data['hometown_state']
        if player_data.get('hometown_country') and not player.hometown_country:
            player.hometown_country = player_data['hometown_country']
        if player_data.get('college_name') and not player.college_name:
            player.college_name = player_data['college_name']

        player.updated_at = datetime.utcnow()

    def _ensure_league_association(self, session, player: Player):
        """Ensure player is associated with DP World Tour."""
        league = session.query(League).filter_by(league_code='DPWORLD').first()
        if not league:
            # Create the league if it doesn't exist
            league = League(
                league_code='DPWORLD',
                league_name='DP World Tour',
                website_url='https://www.europeantour.com',
                is_active=True
            )
            session.add(league)
            session.flush()

        existing = session.query(PlayerLeague).filter_by(
            player_id=player.player_id, league_id=league.league_id
        ).first()

        if not existing:
            session.add(PlayerLeague(
                player_id=player.player_id,
                league_id=league.league_id,
                league_player_id=player.dpworld_id or player.espn_id,
                is_current_member=True
            ))


def scrape_dpworld_roster() -> Dict[str, Any]:
    """Convenience function to scrape DP World Tour roster."""
    return DPWorldRosterScraper().run()
