"""
Database Models (SQLAlchemy ORM)
=================================

This module defines all database models for the Golf Tracker application
using SQLAlchemy ORM (Object-Relational Mapper).

For Junior Developers:
---------------------
ORM lets you work with database tables using Python classes instead of
writing raw SQL. Each class here represents a database table, and each
instance of the class represents a row in that table.

Instead of:
    cursor.execute("INSERT INTO players (first_name, last_name) VALUES ('Scottie', 'Scheffler')")

You can write:
    player = Player(first_name='Scottie', last_name='Scheffler')
    session.add(player)
    session.commit()

This is easier to read, prevents SQL injection, and works with any database.

Usage:
    from database.models import Player, Tournament, TournamentResult

    # Create a new player
    player = Player(first_name='Scottie', last_name='Scheffler')

    # Query players
    with db.get_session() as session:
        texas_players = session.query(Player).filter_by(high_school_state='Texas').all()
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
import json

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    Numeric, Enum, ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.hybrid import hybrid_property

# ==============================================================================
# Base Class
# ==============================================================================
# All models inherit from this base class
Base = declarative_base()


class League(Base):
    """
    Represents a golf league/tour (e.g., PGA Tour, LPGA, LIV Golf).

    For Junior Developers:
    ---------------------
    This is the parent table for organizing data by tour.
    Each tournament and player is associated with one or more leagues.

    Attributes:
        league_id: Unique identifier (auto-generated)
        league_code: Short code like 'PGA', 'LPGA'
        league_name: Full name like 'PGA Tour'
        website_url: Official website URL
        is_active: Whether we're currently tracking this league
    """
    __tablename__ = 'leagues'

    # Primary key - auto-incrementing integer
    league_id = Column(Integer, primary_key=True, autoincrement=True)

    # League identification
    league_code = Column(String(20), unique=True, nullable=False, index=True)
    league_name = Column(String(100), nullable=False)
    website_url = Column(String(255))

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # These let you access related data easily, like league.tournaments
    tournaments = relationship('Tournament', back_populates='league')
    player_leagues = relationship('PlayerLeague', back_populates='league')

    def __repr__(self):
        """String representation for debugging."""
        return f"<League({self.league_code}: {self.league_name})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'league_id': self.league_id,
            'league_code': self.league_code,
            'league_name': self.league_name,
            'website_url': self.website_url,
            'is_active': self.is_active,
        }


class Player(Base):
    """
    Represents a golf player with biographical information.

    This is the CORE table for our local news angle - it stores the
    high school, hometown, and college information that makes our
    stories unique.

    For Junior Developers:
    ---------------------
    This table is designed for local news research. The key fields are:
    - high_school_name, high_school_city, high_school_state, high_school_graduation_year
    - hometown_city, hometown_state, hometown_country
    - college_name, college_graduation_year

    These let us write stories like:
    "Scottie Scheffler, a 2014 graduate of Highland Park High School
    in Dallas, Texas, won the Masters on Sunday..."

    Attributes:
        player_id: Unique identifier
        first_name, last_name: Player's name
        full_name: Auto-generated from first + last name
        high_school_*: High school information (critical for local news)
        hometown_*: Where the player is from
        college_*: College/university information
        pga_tour_id: ID on pgatour.com for matching
    """
    __tablename__ = 'players'

    # Primary key
    player_id = Column(Integer, primary_key=True, autoincrement=True)

    # ==========================================================================
    # Basic Information
    # ==========================================================================
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, index=True)

    # Birth information
    birth_date = Column(Date)
    age = Column(Integer)

    # ==========================================================================
    # HIGH SCHOOL INFO (Critical for local news)
    # ==========================================================================
    high_school_name = Column(String(200))
    high_school_city = Column(String(100))
    high_school_state = Column(String(50))
    high_school_graduation_year = Column(Integer)

    # ==========================================================================
    # HOMETOWN INFO
    # ==========================================================================
    hometown_city = Column(String(100))
    hometown_state = Column(String(100))
    hometown_country = Column(String(100))

    # Birthplace (can be different from hometown)
    birthplace_city = Column(String(100))
    birthplace_state = Column(String(100))
    birthplace_country = Column(String(100))

    # ==========================================================================
    # COLLEGE INFO
    # ==========================================================================
    college_name = Column(String(200))
    college_graduation_year = Column(Integer)

    # ==========================================================================
    # External IDs (for matching with source data)
    # ==========================================================================
    pga_tour_id = Column(String(50), index=True)
    espn_id = Column(String(50))
    wikipedia_url = Column(String(500))

    # Profile image
    profile_image_url = Column(String(500))

    # ==========================================================================
    # Metadata
    # ==========================================================================
    bio_last_updated = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    player_leagues = relationship('PlayerLeague', back_populates='player')
    tournament_results = relationship('TournamentResult', back_populates='player')

    # Indexes for common queries
    __table_args__ = (
        Index('idx_high_school', 'high_school_name', 'high_school_state'),
        Index('idx_hometown', 'hometown_city', 'hometown_state'),
        Index('idx_college', 'college_name'),
    )

    @hybrid_property
    def full_name(self) -> str:
        """
        Get the player's full name.

        For Junior Developers:
        ---------------------
        @hybrid_property lets you use this both in Python and in SQL queries.
        In Python: player.full_name
        In SQL: session.query(Player).filter(Player.full_name == 'Scottie Scheffler')
        """
        return f"{self.first_name} {self.last_name}"

    @property
    def high_school_full(self) -> Optional[str]:
        """
        Get formatted high school with location.

        Returns:
            String like "Highland Park High School in Dallas, Texas"
            or None if high school info is missing
        """
        if not self.high_school_name:
            return None

        parts = [self.high_school_name]
        if self.high_school_city:
            parts.append(f"in {self.high_school_city}")
            if self.high_school_state:
                parts.append(f", {self.high_school_state}")

        return " ".join(parts)

    @property
    def news_blurb(self) -> Optional[str]:
        """
        Generate a news-ready blurb about the player's background.

        Returns:
            String like "a 2014 graduate of Highland Park High School"
            or None if graduation info is missing

        Example:
            "Scottie Scheffler, {player.news_blurb}, finished first..."
        """
        if not self.high_school_name or not self.high_school_graduation_year:
            return None

        return f"a {self.high_school_graduation_year} graduate of {self.high_school_name}"

    def __repr__(self):
        return f"<Player({self.player_id}: {self.full_name})>"

    def to_dict(self, include_bio: bool = True) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Args:
            include_bio: Whether to include biographical details

        Returns:
            Dictionary with player data
        """
        data = {
            'player_id': self.player_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
        }

        if include_bio:
            data.update({
                'birth_date': self.birth_date.isoformat() if self.birth_date else None,
                'age': self.age,
                'high_school_name': self.high_school_name,
                'high_school_city': self.high_school_city,
                'high_school_state': self.high_school_state,
                'high_school_graduation_year': self.high_school_graduation_year,
                'hometown_city': self.hometown_city,
                'hometown_state': self.hometown_state,
                'hometown_country': self.hometown_country,
                'college_name': self.college_name,
                'college_graduation_year': self.college_graduation_year,
                'profile_image_url': self.profile_image_url,
            })

        return data


class PlayerLeague(Base):
    """
    Associates players with leagues (many-to-many relationship).

    A player can be in multiple leagues (e.g., played Korn Ferry,
    now on PGA Tour). This table tracks that relationship.

    For Junior Developers:
    ---------------------
    This is a "junction table" or "association table" - it connects
    two other tables (players and leagues) in a many-to-many relationship.
    One player can be in many leagues, and one league has many players.
    """
    __tablename__ = 'player_leagues'

    player_league_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    player_id = Column(Integer, ForeignKey('players.player_id', ondelete='CASCADE'), nullable=False)
    league_id = Column(Integer, ForeignKey('leagues.league_id', ondelete='CASCADE'), nullable=False)

    # Player's ID within that specific league
    league_player_id = Column(String(50))

    # Status
    is_current_member = Column(Boolean, default=True)
    joined_date = Column(Date)

    # Relationships
    player = relationship('Player', back_populates='player_leagues')
    league = relationship('League', back_populates='player_leagues')

    # Ensure a player can only be in each league once
    __table_args__ = (
        UniqueConstraint('player_id', 'league_id', name='unique_player_league'),
    )

    def __repr__(self):
        return f"<PlayerLeague(player={self.player_id}, league={self.league_id})>"


class Tournament(Base):
    """
    Represents a golf tournament/event.

    For Junior Developers:
    ---------------------
    This table stores information about each tournament:
    - What it's called
    - When it happened
    - Where it was played
    - How much prize money was available

    Tournaments are linked to leagues (each tournament belongs to one league)
    and have many results (one per player who participated).
    """
    __tablename__ = 'tournaments'

    tournament_id = Column(Integer, primary_key=True, autoincrement=True)

    # League this tournament belongs to
    league_id = Column(Integer, ForeignKey('leagues.league_id'), nullable=False)

    # ==========================================================================
    # Tournament Information
    # ==========================================================================
    tournament_name = Column(String(200), nullable=False)
    tournament_year = Column(Integer, nullable=False)

    # Dates
    start_date = Column(Date)
    end_date = Column(Date)

    # ==========================================================================
    # Location
    # ==========================================================================
    course_name = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))

    # ==========================================================================
    # Tournament Details
    # ==========================================================================
    purse_amount = Column(Numeric(15, 2))
    purse_currency = Column(String(10), default='USD')
    par = Column(Integer)
    total_rounds = Column(Integer, default=4)

    # Status
    status = Column(
        Enum('scheduled', 'in_progress', 'completed', 'cancelled', name='tournament_status'),
        default='scheduled'
    )

    # ==========================================================================
    # External IDs
    # ==========================================================================
    pga_tour_tournament_id = Column(String(50))
    espn_tournament_id = Column(String(50))

    # ==========================================================================
    # Metadata
    # ==========================================================================
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    league = relationship('League', back_populates='tournaments')
    results = relationship('TournamentResult', back_populates='tournament')

    # Indexes and constraints
    __table_args__ = (
        Index('idx_dates', 'start_date', 'end_date'),
        Index('idx_year_league', 'tournament_year', 'league_id'),
        UniqueConstraint('league_id', 'tournament_name', 'tournament_year',
                        name='unique_tournament'),
    )

    @property
    def date_range_display(self) -> str:
        """Format the tournament dates for display."""
        if not self.start_date:
            return "Dates TBD"

        if self.start_date == self.end_date or not self.end_date:
            return self.start_date.strftime('%B %d, %Y')

        # Same month
        if self.start_date.month == self.end_date.month:
            return (f"{self.start_date.strftime('%B %d')}-"
                   f"{self.end_date.strftime('%d, %Y')}")

        # Different months
        return (f"{self.start_date.strftime('%B %d')} - "
               f"{self.end_date.strftime('%B %d, %Y')}")

    def __repr__(self):
        return f"<Tournament({self.tournament_id}: {self.tournament_name} {self.tournament_year})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'tournament_id': self.tournament_id,
            'tournament_name': self.tournament_name,
            'tournament_year': self.tournament_year,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'course_name': self.course_name,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'purse_amount': float(self.purse_amount) if self.purse_amount else None,
            'purse_currency': self.purse_currency,
            'par': self.par,
            'status': self.status,
            'league_id': self.league_id,
        }


class TournamentResult(Base):
    """
    Stores a player's result in a specific tournament.

    For Junior Developers:
    ---------------------
    This table connects players to tournaments and stores their scores.
    Each row represents one player's performance in one tournament.

    Key fields:
    - final_position: Where they finished (1, 2, 3, etc.)
    - final_position_display: How it's shown ("T3" for tie, "CUT" for missed cut)
    - round_1_score through round_4_score: Score for each day
    - total_to_par: Overall score relative to par (-15, +3, E, etc.)
    - earnings: Prize money won
    """
    __tablename__ = 'tournament_results'

    result_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    tournament_id = Column(Integer, ForeignKey('tournaments.tournament_id', ondelete='CASCADE'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.player_id', ondelete='CASCADE'), nullable=False)

    # ==========================================================================
    # Final Position
    # ==========================================================================
    final_position = Column(Integer)  # 1, 2, 3, etc. (NULL if missed cut)
    final_position_display = Column(String(20))  # 'T3', '1', 'CUT', 'WD', 'DQ'

    # ==========================================================================
    # Scores
    # ==========================================================================
    total_score = Column(Integer)  # Total strokes
    total_to_par = Column(Integer)  # e.g., -15, +3, 0

    # Round scores stored as JSON for flexibility
    round_scores = Column(JSON)  # {"R1": 68, "R2": 65, "R3": 70, "R4": 67}
    round_to_par = Column(JSON)  # {"R1": -4, "R2": -7, "R3": -2, "R4": -5}

    # Individual round scores (also as columns for easy querying)
    round_1_score = Column(Integer)
    round_2_score = Column(Integer)
    round_3_score = Column(Integer)
    round_4_score = Column(Integer)

    round_1_to_par = Column(Integer)
    round_2_to_par = Column(Integer)
    round_3_to_par = Column(Integer)
    round_4_to_par = Column(Integer)

    # ==========================================================================
    # Status
    # ==========================================================================
    made_cut = Column(Boolean)
    status = Column(
        Enum('active', 'cut', 'withdrawn', 'disqualified', name='player_status'),
        default='active'
    )

    # ==========================================================================
    # Earnings & Points
    # ==========================================================================
    earnings = Column(Numeric(15, 2))
    earnings_currency = Column(String(10), default='USD')
    points_earned = Column(Numeric(10, 2))  # FedEx Cup / Race to Dubai points

    # ==========================================================================
    # Metadata
    # ==========================================================================
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tournament = relationship('Tournament', back_populates='results')
    player = relationship('Player', back_populates='tournament_results')

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('tournament_id', 'player_id', name='unique_player_tournament'),
        Index('idx_position', 'final_position'),
        Index('idx_player_results', 'player_id', 'tournament_id'),
    )

    @property
    def to_par_display(self) -> str:
        """
        Format the to-par score for display.

        Returns:
            String like '-15', '+3', or 'E' (for even par)
        """
        if self.total_to_par is None:
            return '-'

        if self.total_to_par == 0:
            return 'E'
        elif self.total_to_par > 0:
            return f'+{self.total_to_par}'
        else:
            return str(self.total_to_par)

    @property
    def round_scores_display(self) -> List[str]:
        """Get round scores as display strings."""
        scores = []
        for i in range(1, 5):
            score = getattr(self, f'round_{i}_score')
            scores.append(str(score) if score is not None else '-')
        return scores

    def __repr__(self):
        return f"<TournamentResult(tournament={self.tournament_id}, player={self.player_id}, pos={self.final_position_display})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'result_id': self.result_id,
            'tournament_id': self.tournament_id,
            'player_id': self.player_id,
            'final_position': self.final_position,
            'final_position_display': self.final_position_display,
            'total_score': self.total_score,
            'total_to_par': self.total_to_par,
            'to_par_display': self.to_par_display,
            'round_1_score': self.round_1_score,
            'round_2_score': self.round_2_score,
            'round_3_score': self.round_3_score,
            'round_4_score': self.round_4_score,
            'made_cut': self.made_cut,
            'status': self.status,
            'earnings': float(self.earnings) if self.earnings else None,
            'points_earned': float(self.points_earned) if self.points_earned else None,
        }


class ScrapeLog(Base):
    """
    Tracks all scraping operations for debugging and monitoring.

    For Junior Developers:
    ---------------------
    This table is like a diary of everything our scrapers do.
    When something goes wrong, we can look here to see:
    - What was being scraped
    - When it happened
    - What went wrong
    - How many records were processed

    This is essential for debugging and monitoring the system.
    """
    __tablename__ = 'scrape_logs'

    log_id = Column(Integer, primary_key=True, autoincrement=True)

    # What was scraped
    scrape_type = Column(
        Enum('roster', 'tournament_list', 'tournament_results', 'player_bio', name='scrape_type'),
        nullable=False
    )

    # Optional foreign keys to provide context
    league_id = Column(Integer, ForeignKey('leagues.league_id', ondelete='SET NULL'))
    tournament_id = Column(Integer, ForeignKey('tournaments.tournament_id', ondelete='SET NULL'))
    player_id = Column(Integer, ForeignKey('players.player_id', ondelete='SET NULL'))

    # Results
    status = Column(
        Enum('started', 'success', 'partial', 'failed', name='scrape_status'),
        nullable=False
    )
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text)
    error_stack_trace = Column(Text)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Source info
    source_url = Column(String(500))

    # Indexes for common queries
    __table_args__ = (
        Index('idx_scrape_date', 'started_at'),
        Index('idx_scrape_status', 'status'),
    )

    def __repr__(self):
        return f"<ScrapeLog({self.log_id}: {self.scrape_type} - {self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'log_id': self.log_id,
            'scrape_type': self.scrape_type,
            'status': self.status,
            'records_processed': self.records_processed,
            'records_created': self.records_created,
            'records_updated': self.records_updated,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'source_url': self.source_url,
        }
