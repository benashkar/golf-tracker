"""
League Configuration Module
============================

This module contains configuration for each golf league/tour that we track.
It defines URLs, scraping patterns, and league-specific settings.

For Junior Developers:
---------------------
Each golf tour has its own website with its own structure. This file
centralizes all the tour-specific information so our scrapers know:
1. Where to find player lists
2. Where to find tournament schedules
3. What format the data is in

When adding a new tour, add its configuration here first.

Usage:
    from config.leagues import LEAGUES, get_league_config

    # Get PGA Tour config
    pga_config = get_league_config('PGA')
    print(pga_config['base_url'])  # 'https://www.pgatour.com'
"""

from typing import Dict, Any, Optional

# ==============================================================================
# League Configuration Definitions
# ==============================================================================
# Each league has a dictionary with its configuration.
# The key is the league_code that matches our database.

LEAGUES: Dict[str, Dict[str, Any]] = {
    # ==========================================================================
    # PGA TOUR
    # ==========================================================================
    # The main professional golf tour in the United States
    'PGA': {
        'league_code': 'PGA',
        'league_name': 'PGA Tour',
        'base_url': 'https://www.pgatour.com',
        'is_active': True,

        # URLs for scraping
        'urls': {
            # Player roster/list page
            'players': 'https://www.pgatour.com/players',
            # Tournament schedule
            'schedule': 'https://www.pgatour.com/schedule',
            # Leaderboard (for in-progress tournaments)
            'leaderboard': 'https://www.pgatour.com/leaderboard',
            # Player profile URL template (replace {player_id} and {player_slug})
            'player_profile': 'https://www.pgatour.com/players/player.{player_id}.{player_slug}',
            # Tournament results URL template
            'tournament_results': 'https://www.pgatour.com/tournaments/{tournament_slug}/leaderboard',
        },

        # API endpoints (PGA Tour GraphQL API)
        'api': {
            'base': 'https://orchestrator.pgatour.com/graphql',
            'api_key': 'da2-gsrx5bibzbb4njvhl7t37wqyl4',
        },

        # Scraping settings
        'scraping': {
            'requires_selenium': False,  # Can use requests for most pages
            'delay_seconds': 2,
            'user_agent': 'GolfTracker/1.0',
        },

        # Data format hints
        'data_format': {
            'date_format': '%Y-%m-%d',
            'score_format': 'strokes',  # vs 'to_par'
        }
    },

    # ==========================================================================
    # DP WORLD TOUR (European Tour)
    # ==========================================================================
    # The main professional tour in Europe
    'DPWORLD': {
        'league_code': 'DPWORLD',
        'league_name': 'DP World Tour',
        'base_url': 'https://www.europeantour.com',
        'is_active': True,

        'urls': {
            'players': 'https://www.europeantour.com/dpworld-tour/players/',
            'schedule': 'https://www.europeantour.com/dpworld-tour/schedule/',
            'player_profile': 'https://www.europeantour.com/dpworld-tour/players/{player_id}/',
        },

        'scraping': {
            'requires_selenium': True,  # More JavaScript-heavy
            'delay_seconds': 3,
        },
    },

    # ==========================================================================
    # KORN FERRY TOUR
    # ==========================================================================
    # The developmental tour for the PGA Tour
    'KORNFERRY': {
        'league_code': 'KORNFERRY',
        'league_name': 'Korn Ferry Tour',
        'base_url': 'https://www.pgatour.com/korn-ferry-tour',
        'is_active': True,

        'urls': {
            'players': 'https://www.pgatour.com/korn-ferry-tour/players',
            'schedule': 'https://www.pgatour.com/korn-ferry-tour/schedule',
        },

        'scraping': {
            'requires_selenium': False,
            'delay_seconds': 2,
        },
    },

    # ==========================================================================
    # LPGA TOUR
    # ==========================================================================
    # The main professional women's golf tour
    'LPGA': {
        'league_code': 'LPGA',
        'league_name': 'LPGA Tour',
        'base_url': 'https://www.lpga.com',
        'is_active': True,

        'urls': {
            'players': 'https://www.lpga.com/players',
            'schedule': 'https://www.lpga.com/tournaments',
            'leaderboard': 'https://www.lpga.com/tournaments/leaderboard',
        },

        'scraping': {
            'requires_selenium': True,  # LPGA site is JavaScript-heavy
            'delay_seconds': 3,
        },
    },

    # ==========================================================================
    # LIV GOLF
    # ==========================================================================
    # The Saudi-backed golf league (team-based format)
    'LIV': {
        'league_code': 'LIV',
        'league_name': 'LIV Golf',
        'base_url': 'https://www.livgolf.com',
        'is_active': True,

        'urls': {
            'players': 'https://www.livgolf.com/players',
            'schedule': 'https://www.livgolf.com/schedule',
            'teams': 'https://www.livgolf.com/teams',
        },

        'scraping': {
            'requires_selenium': True,
            'delay_seconds': 3,
        },

        # LIV has a unique team-based format
        'special_format': {
            'has_teams': True,
            'individual_and_team_results': True,
        },
    },

    # ==========================================================================
    # PGA TOUR CHAMPIONS
    # ==========================================================================
    # The senior tour for players 50+
    'CHAMPIONS': {
        'league_code': 'CHAMPIONS',
        'league_name': 'PGA Tour Champions',
        'base_url': 'https://www.pgatour.com/champions',
        'is_active': True,

        'urls': {
            'players': 'https://www.pgatour.com/champions/players',
            'schedule': 'https://www.pgatour.com/champions/schedule',
        },

        'scraping': {
            'requires_selenium': False,
            'delay_seconds': 2,
        },
    },

    # ==========================================================================
    # PGA TOUR AMERICAS
    # ==========================================================================
    # Developmental tour formed from merger of PGA Tour Canada and
    # PGA Tour Latinoamerica in 2024
    'PGAAMERICAS': {
        'league_code': 'PGAAMERICAS',
        'league_name': 'PGA Tour Americas',
        'base_url': 'https://www.pgatour.com/pga-tour-americas',
        'is_active': True,

        'urls': {
            'players': 'https://www.pgatour.com/pga-tour-americas/players',
            'schedule': 'https://www.pgatour.com/pga-tour-americas/schedule',
        },

        # Uses PGA Tour GraphQL API with tour code Y
        'api': {
            'base': 'https://orchestrator.pgatour.com/graphql',
            'api_key': 'da2-gsrx5bibzbb4njvhl7t37wqyl4',
            'tour_code': 'Y',
        },

        'scraping': {
            'requires_selenium': False,
            'delay_seconds': 2,
        },
    },

    # ==========================================================================
    # USGA AMATEUR EVENTS
    # ==========================================================================
    # Amateur golf events including U.S. Amateur, U.S. Women's Amateur, etc.
    'USGA': {
        'league_code': 'USGA',
        'league_name': 'USGA Amateur Events',
        'base_url': 'https://www.usga.org',
        'is_active': True,

        'urls': {
            'championships': 'https://championships.usga.org/',
            'schedule': 'https://www.usga.org/championships.html',
        },

        'scraping': {
            'requires_selenium': True,
            'delay_seconds': 3,
        },

        'special_format': {
            'is_amateur': True,
            'events': [
                'U.S. Amateur',
                'U.S. Women\'s Amateur',
                'U.S. Junior Amateur',
                'U.S. Girls\' Junior',
                'U.S. Mid-Amateur',
                'U.S. Senior Amateur',
            ],
        },
    },
}


def get_league_config(league_code: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific league.

    Args:
        league_code: The code for the league (e.g., 'PGA', 'LPGA')

    Returns:
        Dictionary with league configuration, or None if not found

    Example:
        pga = get_league_config('PGA')
        if pga:
            print(pga['urls']['players'])
    """
    return LEAGUES.get(league_code.upper())


def get_active_leagues() -> Dict[str, Dict[str, Any]]:
    """
    Get all leagues that are currently being tracked.

    Returns:
        Dictionary of league configurations where is_active is True

    Example:
        for code, config in get_active_leagues().items():
            print(f"{code}: {config['league_name']}")
    """
    return {
        code: config
        for code, config in LEAGUES.items()
        if config.get('is_active', True)
    }


def get_league_url(league_code: str, url_type: str) -> Optional[str]:
    """
    Get a specific URL for a league.

    Args:
        league_code: The code for the league (e.g., 'PGA')
        url_type: The type of URL (e.g., 'players', 'schedule')

    Returns:
        The URL string, or None if not found

    Example:
        players_url = get_league_url('PGA', 'players')
        # Returns: 'https://www.pgatour.com/players'
    """
    config = get_league_config(league_code)
    if config and 'urls' in config:
        return config['urls'].get(url_type)
    return None


# ==============================================================================
# League Code Validation
# ==============================================================================
VALID_LEAGUE_CODES = list(LEAGUES.keys())


def is_valid_league_code(code: str) -> bool:
    """
    Check if a league code is valid.

    Args:
        code: The league code to check

    Returns:
        True if the code is valid, False otherwise

    Example:
        is_valid_league_code('PGA')  # True
        is_valid_league_code('XYZ')  # False
    """
    return code.upper() in VALID_LEAGUE_CODES
