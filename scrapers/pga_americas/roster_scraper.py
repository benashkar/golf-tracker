"""
PGA Tour Americas Roster Scraper
=================================

Scrapes the PGA Tour Americas player roster using the PGA Tour GraphQL API.
PGA Tour Americas was formed in 2024 from the merger of PGA Tour Canada and
PGA Tour Latinoamerica. It's a developmental tour for the PGA Tour.

Tour Code: Y
"""

from typing import Dict, Any

from loguru import logger

from scrapers.pga_tour.base_pga_scraper import BasePGAEcosystemScraper
from database.models import Player, PlayerLeague, League


class PGAAmericasRosterScraper(BasePGAEcosystemScraper):
    """Scrapes PGA Tour Americas player roster."""

    league_code = 'PGAAMERICAS'
    tour_code = 'Y'  # Y = PGA Tour Americas in PGA API
    scrape_type = 'roster'

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """
        Scrape the PGA Tour Americas player roster.

        Returns:
            Dictionary with scrape results
        """
        self.logger.info("Starting PGA Tour Americas roster scrape")

        players_data = self.fetch_players()

        if not players_data:
            self.logger.error("Failed to fetch player data")
            return {
                'status': 'failed',
                'error': 'Could not fetch player data',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        for player_data in players_data:
            try:
                self._process_player(player_data)
                self._stats['records_processed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing player: {e}")
                self._stats['errors'].append(str(e))

        status = 'success' if not self._stats['errors'] else 'partial'

        return {
            'status': status,
            'records_processed': self._stats['records_processed'],
            'records_created': self._stats['records_created'],
            'records_updated': self._stats['records_updated'],
            'errors': self._stats['errors']
        }

    def _process_player(self, player_data: Dict[str, Any]):
        """Process and save a single player."""
        tour_id = player_data.get('tour_player_id', '')
        first_name = player_data.get('first_name', '').strip()
        last_name = player_data.get('last_name', '').strip()

        if not first_name or not last_name:
            return

        with self.db.get_session() as session:
            # Try to find by PGA Americas ID or name
            player = session.query(Player).filter_by(
                pga_americas_id=tour_id
            ).first() if tour_id else None

            if not player:
                player = session.query(Player).filter_by(
                    first_name=first_name,
                    last_name=last_name
                ).first()

            if player:
                if tour_id and not player.pga_americas_id:
                    player.pga_americas_id = tour_id
                if player_data.get('country') and not player.hometown_country:
                    player.hometown_country = player_data['country']
                self._stats['records_updated'] += 1
            else:
                player = Player(
                    first_name=first_name,
                    last_name=last_name,
                    pga_americas_id=tour_id,
                    hometown_country=player_data.get('country', ''),
                )
                session.add(player)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f"Created player: {first_name} {last_name}")

            # Link to PGA Tour Americas
            self._ensure_league_association(session, player)

    def _ensure_league_association(self, session, player: Player):
        """Ensure player is linked to PGA Tour Americas."""
        league = session.query(League).filter_by(
            league_code='PGAAMERICAS'
        ).first()

        if not league:
            self.logger.warning("PGA Tour Americas league not found in database")
            return

        existing = session.query(PlayerLeague).filter_by(
            player_id=player.player_id,
            league_id=league.league_id
        ).first()

        if not existing:
            player_league = PlayerLeague(
                player_id=player.player_id,
                league_id=league.league_id,
                league_player_id=player.pga_americas_id,
                is_current_member=True
            )
            session.add(player_league)


def scrape_pga_americas_roster() -> Dict[str, Any]:
    """Convenience function to scrape PGA Tour Americas roster."""
    scraper = PGAAmericasRosterScraper()
    return scraper.run()


if __name__ == '__main__':
    result = scrape_pga_americas_roster()
    print(f"Scrape complete: {result}")
