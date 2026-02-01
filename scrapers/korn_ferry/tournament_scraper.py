
from typing import Dict, Any, Optional
from datetime import datetime
from scrapers.pga_tour.base_pga_scraper import BasePGAEcosystemScraper
from database.models import Player, Tournament, TournamentResult, League

class KornFerryTournamentScraper(BasePGAEcosystemScraper):
    league_code = 'KORNFERRY'
    tour_code = 'H'
    scrape_type = 'tournaments'

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        year = year or datetime.now().year
        self.logger.info(f'Starting Korn Ferry Tour tournament scrape for {year}')
        tournaments = self.fetch_schedule(year)
        if not tournaments:
            return {'status': 'failed', 'records_processed': 0, 'records_created': 0, 'records_updated': 0, 'errors': self._stats['errors']}
        for t in tournaments:
            try:
                tournament = self._process_tournament(t, year)
                self._stats['records_processed'] += 1
                if tournament and t.get('status') == 'completed':
                    self._fetch_and_save_results(tournament, t)
            except Exception as e:
                self._stats['errors'].append(str(e))
        return {'status': 'success' if not self._stats['errors'] else 'partial', 'records_processed': self._stats['records_processed'], 'records_created': self._stats['records_created'], 'records_updated': self._stats['records_updated'], 'errors': self._stats['errors']}

    def _process_tournament(self, data: Dict, year: int) -> Optional[Tournament]:
        name = data.get('name', '').strip()
        if not name: return None
        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='KORNFERRY').first()
            if not league: return None
            tournament = session.query(Tournament).filter_by(league_id=league.league_id, tournament_name=name, tournament_year=year).first()
            if tournament:
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(league_id=league.league_id, tournament_name=name, tournament_year=year, start_date=data.get('start_date'), city=data.get('city', ''), state=data.get('state', ''), country=data.get('country', 'USA'), purse_amount=data.get('purse'), status=data.get('status', 'scheduled'))
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1
            return tournament

    def _fetch_and_save_results(self, tournament: Tournament, data: Dict):
        tid = data.get('tournament_id', '')
        if not tid: return
        players = self.fetch_leaderboard(tid)
        if not players: return
        with self.db.get_session() as session:
            tournament = session.query(Tournament).get(tournament.tournament_id)
            for p in players:
                self._save_result(session, tournament, p)

    def _save_result(self, session, tournament, result):
        pi = result.get('player', {})
        if not pi: return
        tid = pi.get('id', '')
        if not tid: return
        player = session.query(Player).filter_by(korn_ferry_id=tid).first()
        if not player:
            player = session.query(Player).filter_by(first_name=pi.get('firstName',''), last_name=pi.get('lastName','')).first()
        if not player:
            fn, ln = pi.get('firstName',''), pi.get('lastName','')
            if not fn or not ln: return
            player = Player(first_name=fn, last_name=ln, korn_ferry_id=tid)
            session.add(player)
            session.flush()
        existing = session.query(TournamentResult).filter_by(tournament_id=tournament.tournament_id, player_id=player.player_id).first()
        pos = result.get('position', '')
        pos_val = self._parse_position(pos)
        to_par = self._parse_to_par(result.get('total', ''))
        made_cut = pos not in ['CUT', 'WD', 'DQ']
        if existing:
            existing.final_position = pos_val
            existing.final_position_display = pos
            existing.total_to_par = to_par
            existing.made_cut = made_cut
        else:
            session.add(TournamentResult(tournament_id=tournament.tournament_id, player_id=player.player_id, final_position=pos_val, final_position_display=pos, total_to_par=to_par, made_cut=made_cut))

def scrape_korn_ferry_tournaments(year=None):
    return KornFerryTournamentScraper().run(year=year)
