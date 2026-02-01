# College Golf Scrapers
# Uses Golfstat for NCAA Division I, II, III golf data
# Note: Full implementation requires parsing Golfstat HTML pages

from scrapers.college.roster_scraper import CollegeGolfRosterScraper
from scrapers.college.tournament_scraper import CollegeGolfTournamentScraper
__all__ = ['CollegeGolfRosterScraper', 'CollegeGolfTournamentScraper']
