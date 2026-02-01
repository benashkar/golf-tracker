from typing import Dict, Any, List, Optional
from loguru import logger
from scrapers.base_scraper import BaseScraper
from database.models import Player, PlayerLeague, League
from config.leagues import get_league_config


class LPGARosterScraper(BaseScraper):
    """Scrapes LPGA Tour player roster using ESPN API."""

    league_code = 'LPGA'
    scrape_type = 'roster'

    def __init__(self):
        config = get_league_config('LPGA')
        base_url = config['base_url'] if config else 'https://www.lpga.com'
        super().__init__('LPGA', base_url)
        self.espn_api = 'https://sports.core.api.espn.com/v2/sports/golf/leagues/lpga'
        self.logger = logger.bind(scraper='LPGARosterScraper', league='LPGA')

    def scrape(self, **kwargs) -> Dict[str, Any]:
        self.logger.info('Starting LPGA Tour roster scrape')
        players_data = self._fetch_players()
        if not players_data:
            return {'status': 'failed', 'records_processed': 0, 'records_created': 0, 'records_updated': 0, 'errors': self._stats['errors']}
        for p in players_data:
            try:
                self._process_player(p)
                self._stats['records_processed'] += 1
            except Exception as e:
                self._stats['errors'].append(str(e))
        return {'status': 'success' if not self._stats['errors'] else 'partial', 'records_processed': self._stats['records_processed'], 'records_created': self._stats['records_created'], 'records_updated': self._stats['records_updated'], 'errors': self._stats['errors']}

    def _fetch_players(self) -> Optional[List[Dict]]:
        players = []
        page = 1
        while True:
            url = f'{self.espn_api}/athletes?limit=100&page={page}'
            data = self.get_json(url)
            if not data or 'items' not in data:
                break
            for item in data['items']:
                ref = item.get('$ref', '')
                if ref:
                    player_data = self.get_json(ref)
                    if player_data and player_data.get('status', {}).get('type') != 'inactive':
                        players.append(player_data)
            if page >= data.get('pageCount', 1):
                break
            page += 1
            if page > 10:  # Limit pages for safety
                break
        self.logger.info(f'Found {len(players)} LPGA players')
        return players

    def _process_player(self, data: Dict):
        espn_id = data.get('id', '')
        fn = data.get('firstName', '').strip()
        ln = data.get('lastName', '').strip()
        if not fn or not ln:
            return
        with self.db.get_session() as session:
            player = session.query(Player).filter_by(lpga_id=espn_id).first() if espn_id else None
            if not player:
                player = session.query(Player).filter_by(first_name=fn, last_name=ln).first()
            if player:
                if espn_id and not player.lpga_id:
                    player.lpga_id = espn_id
                if not player.espn_id:
                    player.espn_id = espn_id
                self._stats['records_updated'] += 1
            else:
                player = Player(first_name=fn, last_name=ln, lpga_id=espn_id, espn_id=espn_id)
                session.add(player)
                session.flush()
                self._stats['records_created'] += 1
                self.logger.info(f'Created player: {fn} {ln}')
            self._ensure_league(session, player)

    def _ensure_league(self, session, player):
        league = session.query(League).filter_by(league_code='LPGA').first()
        if not league:
            return
        existing = session.query(PlayerLeague).filter_by(player_id=player.player_id, league_id=league.league_id).first()
        if not existing:
            session.add(PlayerLeague(player_id=player.player_id, league_id=league.league_id, league_player_id=player.lpga_id, is_current_member=True))


def scrape_lpga_roster():
    return LPGARosterScraper().run()
