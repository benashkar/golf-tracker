from typing import Dict, Any
from scrapers.pga_tour.base_pga_scraper import BasePGAEcosystemScraper
from database.models import Player, PlayerLeague, League

class ChampionsRosterScraper(BasePGAEcosystemScraper):
    league_code = 'CHAMPIONS'
    tour_code = 'S'
    scrape_type = 'roster'

    def scrape(self, **kwargs) -> Dict[str, Any]:
        self.logger.info('Starting PGA Tour Champions roster scrape')
        players_data = self.fetch_players()
        if not players_data:
            return {'status': 'failed', 'records_processed': 0, 'records_created': 0, 'records_updated': 0, 'errors': self._stats['errors']}
        for p in players_data:
            try:
                self._process_player(p)
                self._stats['records_processed'] += 1
            except Exception as e:
                self._stats['errors'].append(str(e))
        return {'status': 'success' if not self._stats['errors'] else 'partial', 'records_processed': self._stats['records_processed'], 'records_created': self._stats['records_created'], 'records_updated': self._stats['records_updated'], 'errors': self._stats['errors']}

    def _process_player(self, data: Dict):
        tid = data.get('tour_player_id', '')
        fn = data.get('first_name', '').strip()
        ln = data.get('last_name', '').strip()
        if not fn or not ln: return
        with self.db.get_session() as session:
            player = session.query(Player).filter_by(champions_id=tid).first() if tid else None
            if not player:
                player = session.query(Player).filter_by(first_name=fn, last_name=ln).first()
            if player:
                if tid and not player.champions_id: player.champions_id = tid
                self._stats['records_updated'] += 1
            else:
                player = Player(first_name=fn, last_name=ln, champions_id=tid, hometown_country=data.get('country', ''))
                session.add(player)
                session.flush()
                self._stats['records_created'] += 1
            self._ensure_league(session, player)

    def _ensure_league(self, session, player):
        league = session.query(League).filter_by(league_code='CHAMPIONS').first()
        if not league: return
        existing = session.query(PlayerLeague).filter_by(player_id=player.player_id, league_id=league.league_id).first()
        if not existing:
            session.add(PlayerLeague(player_id=player.player_id, league_id=league.league_id, league_player_id=player.champions_id, is_current_member=True))

def scrape_champions_roster():
    return ChampionsRosterScraper().run()
