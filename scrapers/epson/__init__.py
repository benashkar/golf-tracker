"""
Epson Tour Scrapers
===================

Scrapers for the Epson Tour (LPGA Developmental Tour).
Excellent source for American player data - most players attended US high schools.
"""

from scrapers.epson.roster_scraper import EpsonRosterScraper
from scrapers.epson.tournament_scraper import EpsonTournamentScraper

__all__ = ['EpsonRosterScraper', 'EpsonTournamentScraper']
