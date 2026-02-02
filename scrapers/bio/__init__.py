"""
Bio Enrichment Scrapers
========================

Multi-source bio enrichment for player hometown and high school data.

Sources:
1. College golf rosters - Best source for high school data
2. Wikipedia - Good for college and birthplace
3. ESPN - Player profiles
4. DuckDuckGo - Search-based enrichment (may be rate-limited)
"""

from scrapers.bio.multi_source_enricher import MultiSourceBioEnricher, enrich_player_bios_multi_source
from scrapers.bio.college_roster_enricher import CollegeRosterBioEnricher, enrich_from_college_rosters

__all__ = [
    'MultiSourceBioEnricher',
    'enrich_player_bios_multi_source',
    'CollegeRosterBioEnricher',
    'enrich_from_college_rosters',
]
