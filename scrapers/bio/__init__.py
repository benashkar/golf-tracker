"""
Bio Enrichment Scrapers
========================

Multi-source bio enrichment for player hometown and high school data.
Now includes DuckDuckGo search which mimics how a human would search
for "player name high school" to find the information.
"""

from scrapers.bio.multi_source_enricher import MultiSourceBioEnricher, enrich_player_bios_multi_source
from scrapers.bio.duckduckgo_enricher import DuckDuckGoEnricher, enrich_player_bios_ddg

__all__ = [
    'MultiSourceBioEnricher',
    'enrich_player_bios_multi_source',
    'DuckDuckGoEnricher',
    'enrich_player_bios_ddg',
]
