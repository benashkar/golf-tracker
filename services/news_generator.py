"""
News Generator Service
=======================

This module generates news-ready text snippets for local news stories.
It combines player biographical data with tournament results to create
text that can be used directly in news articles.

For Junior Developers:
---------------------
This is the CORE service for our use case. Local news sites want to write
stories like:

    "Scottie Scheffler, a 2014 graduate of Highland Park High School in
     Dallas, Texas, finished first in the American Express Championship
     on Sunday, January 25th. He shot rounds of 68-65-70-67 to finish
     at 18-under par, earning $1.4 million."

This service generates that text automatically by combining:
1. Player biographical data (high school, hometown)
2. Tournament information (name, dates, location)
3. Player results (scores, position, earnings)

Usage:
    from services.news_generator import NewsGenerator

    generator = NewsGenerator()

    # Generate a news snippet for a player's tournament result
    snippet = generator.generate_result_snippet(
        player_id=123,
        tournament_id=456
    )
    print(snippet)

    # Generate snippets for all players from a state
    snippets = generator.generate_local_news_package(
        tournament_id=456,
        state="Texas"
    )
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from loguru import logger

from database.connection import DatabaseManager
from database.models import Player, Tournament, TournamentResult


class NewsGenerator:
    """
    Generates news-ready text snippets for golf stories.

    This service creates pre-formatted text that local news organizations
    can use in their stories. It handles:
    - Player biographical blurbs
    - Tournament result summaries
    - Score formatting
    - Earnings formatting

    For Junior Developers:
    ---------------------
    The key insight here is that local news wants a "local angle" -
    they want to know which players have connections to their area.
    This could be:
    - Attended high school in the area
    - From a nearby hometown
    - Went to a local college

    We provide methods to:
    1. Generate individual player snippets
    2. Generate packages of all local players in a tournament
    3. Format data for easy copy/paste into articles
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initialize the news generator.

        Args:
            db: Optional database manager
        """
        self.db = db or DatabaseManager()
        self.logger = logger.bind(service='NewsGenerator')

    def generate_player_intro(self, player_id: int) -> Optional[str]:
        """
        Generate a biographical introduction for a player.

        Args:
            player_id: The player's database ID

        Returns:
            A news-ready introduction string, or None if player not found

        Example output:
            "Scottie Scheffler, a 2014 graduate of Highland Park High School
             in Dallas, Texas, who played college golf at the University of
             Texas,"
        """
        with self.db.get_session() as session:
            player = session.query(Player).filter(
                Player.player_id == player_id
            ).first()

            if not player:
                return None

            return self._format_player_intro(player)

    def _format_player_intro(self, player: Player) -> str:
        """
        Format a player introduction from their bio data.

        Args:
            player: Player model instance

        Returns:
            Formatted introduction string
        """
        parts = [player.full_name]

        # Add high school info
        if player.high_school_name and player.high_school_graduation_year:
            hs_part = f"a {player.high_school_graduation_year} graduate of {player.high_school_name}"

            if player.high_school_city and player.high_school_state:
                hs_part += f" in {player.high_school_city}, {player.high_school_state}"
            elif player.high_school_city:
                hs_part += f" in {player.high_school_city}"

            parts.append(hs_part)

        # Add college info
        if player.college_name:
            college_part = f"who played college golf at {player.college_name}"
            parts.append(college_part)

        # Join with commas
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]}, {parts[1]},"
        else:
            return f"{parts[0]}, {parts[1]}, {parts[2]},"

    def generate_result_snippet(
        self,
        player_id: int,
        tournament_id: int,
        include_bio: bool = True,
        include_scores: bool = True
    ) -> Optional[str]:
        """
        Generate a complete news snippet for a player's tournament result.

        Args:
            player_id: The player's database ID
            tournament_id: The tournament's database ID
            include_bio: Whether to include biographical intro
            include_scores: Whether to include round-by-round scores

        Returns:
            A complete news-ready snippet, or None if data not found

        Example output:
            "Scottie Scheffler, a 2014 graduate of Highland Park High School
             in Dallas, Texas, finished first in the American Express
             Championship on Sunday, January 25th. He shot rounds of
             68-65-70-67 to finish at 18-under par, earning $1,440,000."
        """
        with self.db.get_session() as session:
            result = session.query(TournamentResult).filter(
                TournamentResult.player_id == player_id,
                TournamentResult.tournament_id == tournament_id
            ).first()

            if not result:
                return None

            tournament = session.query(Tournament).filter(
                Tournament.tournament_id == tournament_id
            ).first()

            player = session.query(Player).filter(
                Player.player_id == player_id
            ).first()

            if not tournament or not player:
                return None

            return self._format_result_snippet(
                player, tournament, result,
                include_bio, include_scores
            )

    def _format_result_snippet(
        self,
        player: Player,
        tournament: Tournament,
        result: TournamentResult,
        include_bio: bool = True,
        include_scores: bool = True
    ) -> str:
        """
        Format a complete result snippet.

        Args:
            player: Player model
            tournament: Tournament model
            result: TournamentResult model
            include_bio: Include biographical intro
            include_scores: Include round scores

        Returns:
            Formatted news snippet
        """
        parts = []

        # Start with player intro
        if include_bio:
            intro = self._format_player_intro(player)
        else:
            intro = f"{player.full_name}"

        # Add result
        position_text = self._format_position(result)
        tournament_text = self._format_tournament_name(tournament)

        # Determine the day text
        if tournament.end_date:
            day_text = tournament.end_date.strftime("%A, %B %d")
        else:
            day_text = "this week"

        result_sentence = f"{intro} {position_text} in the {tournament_text} on {day_text}."
        parts.append(result_sentence)

        # Add scores
        if include_scores and result.made_cut:
            scores_text = self._format_scores(result)
            if scores_text:
                parts.append(scores_text)

        # Add earnings
        if result.earnings and float(result.earnings) > 0:
            earnings_text = self._format_earnings(result)
            parts.append(earnings_text)

        return " ".join(parts)

    def _format_position(self, result: TournamentResult) -> str:
        """
        Format the finishing position for news text.

        Args:
            result: TournamentResult model

        Returns:
            Position description (e.g., "finished first", "tied for third")
        """
        if not result.final_position:
            if result.status == 'cut':
                return "missed the cut"
            elif result.status == 'withdrawn':
                return "withdrew"
            elif result.status == 'disqualified':
                return "was disqualified"
            return "competed"

        position = result.final_position
        display = result.final_position_display or str(position)

        # Check for tie
        is_tied = display.startswith('T') or 'T' in display

        # Get ordinal
        ordinal = self._ordinal(position)

        if position == 1 and not is_tied:
            return "finished first"
        elif position == 1 and is_tied:
            return "tied for first"
        elif is_tied:
            return f"tied for {ordinal}"
        else:
            return f"finished {ordinal}"

    def _ordinal(self, n: int) -> str:
        """
        Convert number to ordinal string.

        Args:
            n: Number to convert

        Returns:
            Ordinal string (e.g., "1st", "2nd", "3rd", "4th")
        """
        if 11 <= n <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

        return f"{n}{suffix}"

    def _format_tournament_name(self, tournament: Tournament) -> str:
        """
        Format tournament name for news text.

        Args:
            tournament: Tournament model

        Returns:
            Tournament name, potentially with year
        """
        name = tournament.tournament_name

        # Add year if it's a multi-year event name
        if str(tournament.tournament_year) not in name:
            return f"{tournament.tournament_year} {name}"

        return name

    def _format_scores(self, result: TournamentResult) -> str:
        """
        Format round scores for news text.

        Args:
            result: TournamentResult model

        Returns:
            Score description or empty string
        """
        scores = []
        for i in range(1, 5):
            score = getattr(result, f'round_{i}_score')
            if score is not None:
                scores.append(str(score))

        if not scores:
            return ""

        # Use correct pronoun
        pronoun = "He"  # In a full implementation, we'd check player gender

        score_str = "-".join(scores)

        # Format to-par
        to_par = result.to_par_display

        return f"{pronoun} shot rounds of {score_str} to finish at {to_par}."

    def _format_earnings(self, result: TournamentResult) -> str:
        """
        Format earnings for news text.

        Args:
            result: TournamentResult model

        Returns:
            Earnings description
        """
        if not result.earnings:
            return ""

        amount = float(result.earnings)

        # Format with commas
        if amount >= 1_000_000:
            formatted = f"${amount:,.0f}"
        else:
            formatted = f"${amount:,.0f}"

        pronoun = "He"  # Would check gender in full implementation

        return f"{pronoun} earned {formatted}."

    def generate_local_news_package(
        self,
        tournament_id: int,
        state: Optional[str] = None,
        city: Optional[str] = None,
        high_school: Optional[str] = None,
        college: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate news snippets for all players with local connections.

        Args:
            tournament_id: The tournament's database ID
            state: Filter by high school state
            city: Filter by hometown city
            high_school: Filter by high school name
            college: Filter by college name

        Returns:
            List of dictionaries with player info and snippets

        Example:
            # Get all Texas connections for a tournament
            package = generator.generate_local_news_package(
                tournament_id=123,
                state="Texas"
            )
            for item in package:
                print(f"\\n{item['player_name']}:")
                print(item['snippet'])
        """
        self.logger.info(f"Generating local news package for tournament {tournament_id}")

        with self.db.get_session() as session:
            # Get all results for this tournament
            query = session.query(TournamentResult).join(
                Player
            ).filter(
                TournamentResult.tournament_id == tournament_id
            )

            # Apply filters
            if state:
                query = query.filter(
                    Player.high_school_state.ilike(f"%{state}%")
                )

            if city:
                query = query.filter(
                    Player.hometown_city.ilike(f"%{city}%")
                )

            if high_school:
                query = query.filter(
                    Player.high_school_name.ilike(f"%{high_school}%")
                )

            if college:
                query = query.filter(
                    Player.college_name.ilike(f"%{college}%")
                )

            results = query.order_by(
                TournamentResult.final_position.nullslast()
            ).all()

            tournament = session.query(Tournament).filter(
                Tournament.tournament_id == tournament_id
            ).first()

            package = []
            for result in results:
                player = result.player

                snippet = self._format_result_snippet(
                    player, tournament, result,
                    include_bio=True, include_scores=True
                )

                package.append({
                    'player_id': player.player_id,
                    'player_name': player.full_name,
                    'position': result.final_position_display,
                    'high_school': player.high_school_name,
                    'high_school_location': f"{player.high_school_city}, {player.high_school_state}" if player.high_school_city else None,
                    'college': player.college_name,
                    'hometown': f"{player.hometown_city}, {player.hometown_state}" if player.hometown_city else None,
                    'snippet': snippet,
                })

            return package

    def generate_leaderboard_summary(
        self,
        tournament_id: int,
        top_n: int = 10
    ) -> str:
        """
        Generate a summary of the top finishers with local angles.

        Args:
            tournament_id: The tournament's database ID
            top_n: Number of top finishers to include

        Returns:
            A multi-paragraph summary of the top finishers
        """
        with self.db.get_session() as session:
            tournament = session.query(Tournament).filter(
                Tournament.tournament_id == tournament_id
            ).first()

            if not tournament:
                return ""

            results = session.query(TournamentResult).join(
                Player
            ).filter(
                TournamentResult.tournament_id == tournament_id,
                TournamentResult.final_position.isnot(None),
                TournamentResult.final_position <= top_n
            ).order_by(
                TournamentResult.final_position
            ).all()

            paragraphs = []

            for result in results:
                player = result.player
                snippet = self._format_result_snippet(
                    player, tournament, result,
                    include_bio=True, include_scores=True
                )
                paragraphs.append(snippet)

            return "\n\n".join(paragraphs)
