"""
PGA Tour Champions Tournament Scraper
======================================

Scrapes PGA Tour Champions tournament schedules and results using the PGA Tour GraphQL API.
Supports both completed tournaments and live/in-progress tournaments with round-by-round scores.
"""

from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from scrapers.pga_tour.base_pga_scraper import BasePGAEcosystemScraper
from database.models import Player, Tournament, TournamentResult, League


class ChampionsTournamentScraper(BasePGAEcosystemScraper):
    """Scrapes PGA Tour Champions tournament schedules and results."""

    league_code = 'CHAMPIONS'
    tour_code = 'S'
    scrape_type = 'tournaments'

    def scrape(self, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape PGA Tour Champions tournaments for a given year.

        Args:
            year: The season year to scrape (defaults to current year)

        Returns:
            Dictionary with scrape results
        """
        year = year or datetime.now().year
        self.logger.info(f'Starting PGA Tour Champions tournament scrape for {year}')

        tournaments = self.fetch_schedule(year)
        if not tournaments:
            return {
                'status': 'failed',
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': self._stats['errors']
            }

        # Determine in-progress tournaments based on dates
        today = date.today()
        for t in tournaments:
            start_date = t.get('start_date')
            if start_date:
                # Champions events are typically 3 days (Fri-Sun)
                end_date_estimate = start_date + timedelta(days=2)
                if start_date <= today <= end_date_estimate:
                    t['status'] = 'in_progress'
                elif today > end_date_estimate:
                    t['status'] = 'completed'

        for t in tournaments:
            try:
                tournament_id = self._process_tournament(t, year)
                self._stats['records_processed'] += 1

                # Fetch results for completed OR in-progress tournaments
                if tournament_id and t.get('status') in ['completed', 'in_progress']:
                    self._fetch_results(tournament_id, t)
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

    def _process_tournament(self, data: Dict, year: int) -> Optional[int]:
        """Process and save a tournament to the database. Returns tournament_id."""
        name = data.get('name', '').strip()
        if not name:
            return None

        with self.db.get_session() as session:
            league = session.query(League).filter_by(league_code='CHAMPIONS').first()
            if not league:
                return None

            tournament = session.query(Tournament).filter_by(
                league_id=league.league_id,
                tournament_name=name,
                tournament_year=year
            ).first()

            if tournament:
                tournament.status = data.get('status', tournament.status)
                self._stats['records_updated'] += 1
            else:
                tournament = Tournament(
                    league_id=league.league_id,
                    tournament_name=name,
                    tournament_year=year,
                    start_date=data.get('start_date'),
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    country=data.get('country', 'USA'),
                    purse_amount=data.get('purse'),
                    status=data.get('status', 'scheduled'),
                    champions_tournament_id=data.get('tournament_id', '')
                )
                session.add(tournament)
                session.flush()
                self._stats['records_created'] += 1

            # Return ID to avoid session detachment
            return tournament.tournament_id

    def _fetch_results(self, tournament_id: int, data: Dict):
        """Fetch and save results for a tournament with round-by-round scores."""
        pga_tid = data.get('tournament_id', '')
        if not pga_tid:
            return

        tournament_name = data.get('name', 'Unknown')

        # Use the enhanced leaderboard query with rounds
        query = """
        query Leaderboard($id: ID!) {
            leaderboardV2(id: $id) {
                id
                tournamentStatus
                players {
                    ... on PlayerRowV2 {
                        id
                        position
                        total
                        totalStrokes
                        score
                        thru
                        currentRound
                        rounds
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

        data_response = self._graphql_request(query, {'id': pga_tid})
        if not data_response or 'leaderboardV2' not in data_response:
            return

        leaderboard = data_response['leaderboardV2']
        players = leaderboard.get('players', [])
        tournament_status = leaderboard.get('tournamentStatus', 'COMPLETED')

        # Filter valid players
        players = [p for p in players if p and p.get('player')]

        self.logger.info(f"Found {len(players)} player results for {tournament_name} (status: {tournament_status})")

        with self.db.get_session() as session:
            tournament = session.query(Tournament).get(tournament_id)

            # Update tournament status
            if tournament_status == 'IN_PROGRESS':
                tournament.status = 'in_progress'
            elif tournament_status == 'COMPLETED':
                tournament.status = 'completed'

            for p in players:
                self._save_result(session, tournament, p, tournament_status)

    def _save_result(self, session, tournament, result, tournament_status='COMPLETED'):
        """Save a single player's result with round-by-round scores."""
        pi = result.get('player', {})
        if not pi:
            return

        tid = pi.get('id', '')
        if not tid:
            return

        first_name = pi.get('firstName', '')
        last_name = pi.get('lastName', '')

        # Find player by Champions ID
        player = session.query(Player).filter_by(champions_id=tid).first()
        if not player:
            player = session.query(Player).filter_by(
                first_name=first_name,
                last_name=last_name
            ).first()
        if not player:
            if not first_name or not last_name:
                return
            player = Player(first_name=first_name, last_name=last_name, champions_id=tid)
            session.add(player)
            session.flush()

        existing = session.query(TournamentResult).filter_by(
            tournament_id=tournament.tournament_id,
            player_id=player.player_id
        ).first()

        pos = result.get('position', '')
        pos_val = self._parse_position(pos)
        to_par = self._parse_to_par(result.get('total', ''))
        made_cut = pos not in ['CUT', 'WD', 'DQ', 'MDF']

        # Parse total strokes
        total_strokes = None
        total_strokes_str = result.get('totalStrokes', '')
        if total_strokes_str:
            try:
                total_strokes = int(total_strokes_str)
            except (ValueError, TypeError):
                pass

        # Parse round-by-round scores (Champions typically has 3 rounds)
        rounds = result.get('rounds', [])
        r1 = self._parse_round_score(rounds[0] if len(rounds) > 0 else None)
        r2 = self._parse_round_score(rounds[1] if len(rounds) > 1 else None)
        r3 = self._parse_round_score(rounds[2] if len(rounds) > 2 else None)
        r4 = self._parse_round_score(rounds[3] if len(rounds) > 3 else None)

        # Build round_scores dict
        round_scores_dict = {}
        if r1 is not None:
            round_scores_dict['R1'] = r1
        if r2 is not None:
            round_scores_dict['R2'] = r2
        if r3 is not None:
            round_scores_dict['R3'] = r3
        if r4 is not None:
            round_scores_dict['R4'] = r4

        # Determine status
        if not made_cut:
            player_status = 'cut'
        elif tournament_status == 'IN_PROGRESS':
            player_status = 'active'
        else:
            player_status = 'active'

        if existing:
            existing.final_position = pos_val
            existing.final_position_display = pos
            existing.total_to_par = to_par
            existing.total_score = total_strokes
            existing.made_cut = made_cut
            existing.status = player_status
            existing.round_1_score = r1
            existing.round_2_score = r2
            existing.round_3_score = r3
            existing.round_4_score = r4
            existing.round_scores = round_scores_dict if round_scores_dict else None
        else:
            session.add(TournamentResult(
                tournament_id=tournament.tournament_id,
                player_id=player.player_id,
                final_position=pos_val,
                final_position_display=pos,
                total_to_par=to_par,
                total_score=total_strokes,
                made_cut=made_cut,
                status=player_status,
                round_1_score=r1,
                round_2_score=r2,
                round_3_score=r3,
                round_4_score=r4,
                round_scores=round_scores_dict if round_scores_dict else None
            ))

    def _parse_round_score(self, score_str) -> Optional[int]:
        """Parse a round score string to integer."""
        if not score_str or score_str == '-':
            return None
        try:
            return int(score_str)
        except (ValueError, TypeError):
            return None


def scrape_champions_tournaments(year=None):
    """Convenience function to scrape Champions tournaments."""
    return ChampionsTournamentScraper().run(year=year)
