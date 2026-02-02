"""
DuckDuckGo Search Bio Enricher
===============================

Uses DuckDuckGo search to find player biographical data.
Searches for "{player name} high school" and parses results.

This is effective because:
1. No API key required
2. Search results often contain the info directly in snippets
3. Can search specifically for "high school" or "hometown"
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import time
import urllib.parse

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player


class DuckDuckGoEnricher(BaseScraper):
    """
    Enriches player bio data by searching DuckDuckGo.

    Searches for:
    1. "{player name} high school golf" - to find high school info
    2. "{player name} hometown" - to find hometown info
    3. "{player name} college golf" - to find college info

    Parses search result snippets to extract information.
    """

    scrape_type = 'player_bio'

    def __init__(self):
        super().__init__('DDG', 'https://html.duckduckgo.com')
        self.logger = logger.bind(scraper='DuckDuckGoEnricher')

        # DuckDuckGo HTML search endpoint (no API key needed)
        self.search_url = 'https://html.duckduckgo.com/html/'

        # Rate limiting - be respectful
        self.request_delay = 2  # seconds between requests
        self.last_request_time = 0

        # Patterns for extracting information from search snippets
        self.high_school_patterns = [
            # "attended Highland Park High School"
            r'attended\s+([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            # "graduated from Highland Park High School"
            r'graduated\s+(?:from\s+)?([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            # "Highland Park High School in Dallas"
            r'([A-Z][A-Za-z\'\s]+)\s+High\s+School\s+in\s+([A-Z][A-Za-z\s]+)',
            # Just "Highland Park High School"
            r'([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            # "went to Highland Park HS"
            r'(?:went to|attended)\s+([A-Z][A-Za-z\'\s]+)\s+(?:HS|H\.S\.)',
        ]

        self.hometown_patterns = [
            # "from Dallas, Texas"
            r'(?:from|hails from|native of)\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            # "born in Dallas, Texas"
            r'born\s+(?:and raised\s+)?in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            # "raised in Dallas, Texas"
            r'raised\s+in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            # "grew up in Dallas, Texas"
            r'grew\s+up\s+in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            # "hometown of Dallas, Texas" or "hometown: Dallas, Texas"
            r'hometown\s*(?:of|:)\s*([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            # "Dallas, Texas native"
            r'([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)\s+native',
        ]

        self.college_patterns = [
            # "played golf at Texas"
            r'played\s+(?:golf\s+)?(?:at|for)\s+([A-Z][A-Za-z\s]+(?:University|College|State))',
            # "attended University of Texas"
            r'attended\s+(University\s+of\s+[A-Za-z\s]+|[A-Z][A-Za-z\s]+\s+University)',
            # "Texas Longhorns golf"
            r'([A-Z][A-Za-z\s]+)\s+(?:Longhorns|Bulldogs|Tigers|Gators|Wildcats)\s+golf',
            # Just "University of Texas" or "Texas A&M"
            r'(University\s+of\s+[A-Za-z\s]+)',
            r'([A-Z][A-Za-z\s]+(?:University|College|State))',
        ]

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """Main scrape method."""
        limit = kwargs.get('limit', 50)
        force = kwargs.get('force', False)
        return self.enrich_missing_bios(limit=limit, force=force)

    def enrich_missing_bios(self, limit: int = 50, force: bool = False) -> Dict[str, Any]:
        """Enrich players missing bio data using DuckDuckGo search."""
        self.logger.info(f"Starting DuckDuckGo bio enrichment (limit={limit})")

        results = {
            'processed': 0,
            'enriched': 0,
            'not_found': 0,
            'errors': [],
        }

        with self.db.get_session() as session:
            query = session.query(Player)

            if not force:
                query = query.filter(
                    (Player.high_school_name.is_(None)) |
                    (Player.hometown_city.is_(None))
                )

            players = query.limit(limit).all()
            self.logger.info(f"Found {len(players)} players to enrich")

            for player in players:
                try:
                    success = self._enrich_player(session, player)
                    results['processed'] += 1

                    if success:
                        results['enriched'] += 1
                    else:
                        results['not_found'] += 1

                except Exception as e:
                    self.logger.error(f"Error enriching {player.first_name} {player.last_name}: {e}")
                    results['errors'].append(str(e))

        self.logger.info(f"Enrichment complete: {results['enriched']}/{results['processed']} enriched")
        return results

    def _rate_limit(self):
        """Ensure we don't hit DuckDuckGo too fast."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def search_player(self, player_name: str) -> Dict[str, Any]:
        """
        Search DuckDuckGo for player bio information.

        Args:
            player_name: Full name of the player

        Returns:
            Dictionary with extracted bio data
        """
        bio_data = {}

        # Search for high school info
        hs_results = self._search_ddg(f"{player_name} high school golf")
        if hs_results:
            hs_data = self._extract_high_school(hs_results)
            bio_data.update(hs_data)

        # Search for hometown if not found from high school search
        if 'hometown_city' not in bio_data:
            self._rate_limit()
            hometown_results = self._search_ddg(f"{player_name} golfer hometown")
            if hometown_results:
                hometown_data = self._extract_hometown(hometown_results)
                bio_data.update(hometown_data)

        # Search for college if not found
        if 'college_name' not in bio_data:
            self._rate_limit()
            college_results = self._search_ddg(f"{player_name} college golf")
            if college_results:
                college_data = self._extract_college(college_results)
                bio_data.update(college_data)

        return bio_data

    def _search_ddg(self, query: str) -> Optional[List[str]]:
        """
        Search DuckDuckGo and return result snippets.

        Args:
            query: Search query

        Returns:
            List of result snippets, or None if failed
        """
        self._rate_limit()

        try:
            # Use DuckDuckGo HTML search
            params = {
                'q': query,
                'b': '',  # Start from beginning
                'kl': 'us-en',  # US English
            }

            # Build URL with params
            url = f"{self.search_url}?{urllib.parse.urlencode(params)}"

            self.logger.debug(f"Searching DDG: {query}")

            soup = self.get_page(url)
            if not soup:
                return None

            # Extract result snippets
            snippets = []

            # DuckDuckGo HTML results are in divs with class "result"
            results = soup.find_all('div', class_='result')

            for result in results[:10]:  # Check first 10 results
                # Get the snippet text
                snippet_elem = result.find('a', class_='result__snippet')
                if snippet_elem:
                    snippets.append(snippet_elem.get_text(strip=True))

                # Also check result title
                title_elem = result.find('a', class_='result__a')
                if title_elem:
                    snippets.append(title_elem.get_text(strip=True))

            # Also try alternative selectors
            if not snippets:
                for elem in soup.find_all(['div', 'span'], class_=re.compile(r'snippet|abstract|desc', re.I)):
                    text = elem.get_text(strip=True)
                    if len(text) > 20:
                        snippets.append(text)

            return snippets if snippets else None

        except Exception as e:
            self.logger.debug(f"DDG search failed for '{query}': {e}")
            return None

    def _extract_high_school(self, snippets: List[str]) -> Dict[str, Any]:
        """Extract high school info from search snippets."""
        data = {}

        for snippet in snippets:
            # Try each pattern
            for pattern in self.high_school_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    school_name = match.group(1).strip()

                    # Clean up the name
                    school_name = self._clean_school_name(school_name)

                    if school_name and len(school_name) > 2:
                        data['high_school_name'] = f"{school_name} High School"

                        # Try to get location if pattern captured it
                        if match.lastindex and match.lastindex >= 2:
                            city = match.group(2).strip()
                            if city and len(city) > 2:
                                data['high_school_city'] = city

                        # Also try to extract location from the same snippet
                        location_data = self._extract_location_near_school(snippet, school_name)
                        if location_data:
                            data.update(location_data)

                        return data

        return data

    def _extract_hometown(self, snippets: List[str]) -> Dict[str, Any]:
        """Extract hometown info from search snippets."""
        data = {}

        for snippet in snippets:
            for pattern in self.hometown_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    city = match.group(1).strip()

                    # Clean up
                    city = re.sub(r'\s+', ' ', city).strip()

                    if city and len(city) > 2 and not self._is_invalid_city(city):
                        data['hometown_city'] = city

                        if match.lastindex >= 2:
                            state = match.group(2).strip()
                            state = re.sub(r'\s+', ' ', state).strip()
                            if state and len(state) >= 2:
                                data['hometown_state'] = state

                        return data

        return data

    def _extract_college(self, snippets: List[str]) -> Dict[str, Any]:
        """Extract college info from search snippets."""
        data = {}

        for snippet in snippets:
            for pattern in self.college_patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    college = match.group(1).strip()

                    # Clean up
                    college = re.sub(r'\s+', ' ', college).strip()
                    college = re.sub(r'\s*\([^)]+\)', '', college)  # Remove parenthetical

                    if college and len(college) > 3:
                        data['college_name'] = college
                        return data

        return data

    def _extract_location_near_school(self, text: str, school_name: str) -> Dict[str, Any]:
        """Try to extract location mentioned near the school name."""
        data = {}

        # Pattern: "School Name in City, State"
        pattern = rf'{re.escape(school_name)}.*?(?:High School\s+)?in\s+([A-Z][A-Za-z\s]+),\s*([A-Z][A-Za-z]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['high_school_city'] = match.group(1).strip()
            data['high_school_state'] = match.group(2).strip()

        return data

    def _clean_school_name(self, name: str) -> str:
        """Clean up a school name."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^(the|a)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(high school|hs|h\.s\.).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip()

        # Remove trailing punctuation
        name = name.rstrip('.,;:')

        return name

    def _is_invalid_city(self, city: str) -> bool:
        """Check if a string is unlikely to be a valid city name."""
        invalid_words = [
            'the', 'and', 'high', 'school', 'golf', 'tour', 'pga',
            'lpga', 'college', 'university', 'played', 'born', 'raised'
        ]
        city_lower = city.lower()
        return any(word == city_lower for word in invalid_words)

    def _enrich_player(self, session, player: Player) -> bool:
        """Enrich a single player record."""
        full_name = f"{player.first_name} {player.last_name}"
        self.logger.debug(f"Enriching via DDG: {full_name}")

        bio_data = self.search_player(full_name)

        if not bio_data:
            return False

        # Update player record
        updated = False

        if bio_data.get('high_school_name') and not player.high_school_name:
            player.high_school_name = bio_data['high_school_name']
            updated = True

        if bio_data.get('high_school_city') and not player.high_school_city:
            player.high_school_city = bio_data['high_school_city']

        if bio_data.get('high_school_state') and not player.high_school_state:
            player.high_school_state = bio_data['high_school_state']

        if bio_data.get('hometown_city') and not player.hometown_city:
            player.hometown_city = bio_data['hometown_city']
            updated = True

        if bio_data.get('hometown_state') and not player.hometown_state:
            player.hometown_state = bio_data['hometown_state']

        if bio_data.get('college_name') and not player.college_name:
            player.college_name = bio_data['college_name']

        if updated:
            player.bio_source_name = 'duckduckgo'
            player.bio_last_updated = datetime.utcnow()
            self.logger.info(f"Enriched {full_name} via DuckDuckGo search")

        return updated


def enrich_player_bios_ddg(limit: int = 50, force: bool = False) -> Dict[str, Any]:
    """Convenience function to enrich player bios using DuckDuckGo."""
    enricher = DuckDuckGoEnricher()
    return enricher.run(limit=limit, force=force)
