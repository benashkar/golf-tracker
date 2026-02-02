"""
USGA Amateur Events Scrapers
=============================

Scrapers for USGA amateur golf championships including:
- U.S. Amateur
- U.S. Women's Amateur
- U.S. Junior Amateur
- U.S. Girls' Junior
- U.S. Mid-Amateur
- U.S. Senior Amateur

Note: USGA does not have a public API. Data is scraped from:
- AmateurGolf.com for results and participant lists
- USGA championship website for schedule and leaderboards
"""

from scrapers.usga.roster_scraper import USGARosterScraper, scrape_usga_roster
from scrapers.usga.tournament_scraper import USGATournamentScraper, scrape_usga_tournaments

__all__ = [
    'USGARosterScraper',
    'scrape_usga_roster',
    'USGATournamentScraper',
    'scrape_usga_tournaments',
]
