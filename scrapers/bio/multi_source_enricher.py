"""
Multi-Source Bio Enricher
=========================

Enriches player biographical data from multiple sources:
1. DuckDuckGo Search (searches "player name high school" like a human would)
2. Wikipedia (primary structured source)
3. ESPN
4. Grokepedia

Saves the source URL where information was found for attribution.

For Junior Developers:
---------------------
When we can't find hometown/high school info from one source,
we try others. This increases our hit rate for local news data.

The DuckDuckGo search is particularly effective because it mimics
what a human would do - search for "Scottie Scheffler high school"
and find the info in search result snippets.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re
import time
import urllib.parse

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player


class MultiSourceBioEnricher(BaseScraper):
    """
    Enriches player bio data from multiple sources.

    Tries sources in order:
    1. DuckDuckGo - searches like a human, high success rate
    2. Wikipedia - most comprehensive for pro golfers
    3. ESPN - good for current players with profiles
    4. Grokepedia - alternative golf-specific source
    """

    scrape_type = 'player_bio'

    def __init__(self):
        super().__init__('BIO', 'https://en.wikipedia.org')
        self.logger = logger.bind(scraper='MultiSourceBioEnricher')

        # DuckDuckGo search settings
        self.ddg_search_url = 'https://html.duckduckgo.com/html/'
        self.ddg_request_delay = 2  # seconds between DDG requests
        self.last_ddg_request = 0

        # Source configurations
        self.sources = [
            {
                'name': 'duckduckgo',
                'search_url': 'https://html.duckduckgo.com/html/',
                'enabled': True,
            },
            {
                'name': 'wikipedia',
                'search_url': 'https://en.wikipedia.org/w/api.php',
                'enabled': True,
            },
            {
                'name': 'espn',
                'search_url': 'https://www.espn.com/golf/player/_/id/',
                'enabled': True,
            },
            {
                'name': 'grokepedia',
                'search_url': 'https://www.grokepedia.com/search',
                'enabled': True,
            },
        ]

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """Main scrape method - enriches players missing bio data."""
        limit = kwargs.get('limit', 50)
        force = kwargs.get('force', False)
        return self.enrich_missing_bios(limit=limit, force=force)

    def enrich_missing_bios(self, limit: int = 50, force: bool = False) -> Dict[str, Any]:
        """
        Enrich players missing hometown or high school info.

        Tries multiple sources until we find the data.
        """
        self.logger.info(f"Starting multi-source bio enrichment (limit={limit})")

        results = {
            'processed': 0,
            'enriched': 0,
            'not_found': 0,
            'errors': [],
            'sources_used': {'duckduckgo': 0, 'wikipedia': 0, 'espn': 0, 'grokepedia': 0}
        }

        with self.db.get_session() as session:
            # Get players missing high school OR hometown info
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
                    source_name, success = self._enrich_player_multi_source(session, player)
                    results['processed'] += 1

                    if success:
                        results['enriched'] += 1
                        if source_name:
                            results['sources_used'][source_name] = results['sources_used'].get(source_name, 0) + 1
                    else:
                        results['not_found'] += 1

                except Exception as e:
                    self.logger.error(f"Error enriching {player.first_name} {player.last_name}: {e}")
                    results['errors'].append(str(e))

        self.logger.info(f"Enrichment complete: {results['enriched']}/{results['processed']} enriched")
        return results

    def _enrich_player_multi_source(self, session, player: Player) -> tuple:
        """
        Try multiple sources to enrich a player.

        Returns:
            Tuple of (source_name, success_bool)
        """
        full_name = f"{player.first_name} {player.last_name}"
        self.logger.debug(f"Enriching: {full_name}")

        # Try DuckDuckGo search first (most effective - searches like a human)
        bio_data = self._try_duckduckgo(full_name)
        if bio_data and (bio_data.get('high_school_name') or bio_data.get('hometown_city')):
            self._update_player_bio(player, bio_data, 'duckduckgo')
            return ('duckduckgo', True)

        # Try Wikipedia
        bio_data = self._try_wikipedia(full_name)
        if bio_data and (bio_data.get('high_school_name') or bio_data.get('hometown_city')):
            self._update_player_bio(player, bio_data, 'wikipedia')
            return ('wikipedia', True)

        # Try ESPN
        bio_data = self._try_espn(full_name, player.espn_id)
        if bio_data and (bio_data.get('high_school_name') or bio_data.get('hometown_city')):
            self._update_player_bio(player, bio_data, 'espn')
            return ('espn', True)

        # Try Grokepedia
        bio_data = self._try_grokepedia(full_name)
        if bio_data and (bio_data.get('high_school_name') or bio_data.get('hometown_city')):
            self._update_player_bio(player, bio_data, 'grokepedia')
            return ('grokepedia', True)

        self.logger.debug(f"No bio data found for {full_name}")
        return (None, False)

    def _ddg_rate_limit(self):
        """Ensure we don't hit DuckDuckGo too fast."""
        elapsed = time.time() - self.last_ddg_request
        if elapsed < self.ddg_request_delay:
            time.sleep(self.ddg_request_delay - elapsed)
        self.last_ddg_request = time.time()

    def _try_duckduckgo(self, player_name: str) -> Optional[Dict[str, Any]]:
        """
        Search DuckDuckGo for player bio info.

        This mimics what a human would do - search for
        "Scottie Scheffler high school" and find the info.
        """
        try:
            bio_data = {}

            # Search for high school info
            self._ddg_rate_limit()
            hs_snippets = self._search_ddg(f"{player_name} high school golf")
            if hs_snippets:
                hs_data = self._extract_high_school_from_snippets(hs_snippets)
                bio_data.update(hs_data)

            # Search for hometown if not found
            if 'hometown_city' not in bio_data:
                self._ddg_rate_limit()
                hometown_snippets = self._search_ddg(f"{player_name} golfer hometown")
                if hometown_snippets:
                    hometown_data = self._extract_hometown_from_snippets(hometown_snippets)
                    bio_data.update(hometown_data)

            # Search for college if not found
            if 'college_name' not in bio_data:
                self._ddg_rate_limit()
                college_snippets = self._search_ddg(f"{player_name} college golf")
                if college_snippets:
                    college_data = self._extract_college_from_snippets(college_snippets)
                    bio_data.update(college_data)

            if bio_data:
                bio_data['source_url'] = f"https://duckduckgo.com/?q={urllib.parse.quote(player_name + ' golfer')}"

            return bio_data if bio_data else None

        except Exception as e:
            self.logger.debug(f"DuckDuckGo search failed for {player_name}: {e}")
            return None

    def _search_ddg(self, query: str) -> Optional[list]:
        """Search DuckDuckGo and return result snippets."""
        try:
            params = {'q': query, 'kl': 'us-en'}
            url = f"{self.ddg_search_url}?{urllib.parse.urlencode(params)}"

            soup = self.get_page(url)
            if not soup:
                return None

            snippets = []

            # Extract from result divs
            for result in soup.find_all('div', class_='result')[:10]:
                snippet = result.find('a', class_='result__snippet')
                if snippet:
                    snippets.append(snippet.get_text(strip=True))
                title = result.find('a', class_='result__a')
                if title:
                    snippets.append(title.get_text(strip=True))

            # Fallback selectors
            if not snippets:
                for elem in soup.find_all(['div', 'span'], class_=re.compile(r'snippet|abstract', re.I)):
                    text = elem.get_text(strip=True)
                    if len(text) > 20:
                        snippets.append(text)

            return snippets if snippets else None

        except Exception as e:
            self.logger.debug(f"DDG search error: {e}")
            return None

    def _extract_high_school_from_snippets(self, snippets: list) -> Dict[str, Any]:
        """Extract high school info from search snippets."""
        data = {}
        patterns = [
            r'attended\s+([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            r'graduated\s+(?:from\s+)?([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            r'([A-Z][A-Za-z\'\s]+)\s+High\s+School\s+in\s+([A-Z][A-Za-z\s]+)',
            r'([A-Z][A-Za-z\'\s]+)\s+High\s+School',
        ]

        for snippet in snippets:
            for pattern in patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    school = match.group(1).strip()
                    school = re.sub(r'\s+', ' ', school).rstrip('.,;:')
                    if school and len(school) > 2:
                        data['high_school_name'] = f"{school} High School"
                        if match.lastindex >= 2:
                            data['high_school_city'] = match.group(2).strip()
                        return data
        return data

    def _extract_hometown_from_snippets(self, snippets: list) -> Dict[str, Any]:
        """Extract hometown info from search snippets."""
        data = {}
        patterns = [
            r'(?:from|hails from|native of)\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            r'born\s+(?:and raised\s+)?in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            r'raised\s+in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            r'hometown[:\s]+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
        ]

        for snippet in snippets:
            for pattern in patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    city = match.group(1).strip()
                    if city and len(city) > 2:
                        data['hometown_city'] = city
                        if match.lastindex >= 2:
                            data['hometown_state'] = match.group(2).strip()
                        return data
        return data

    def _extract_college_from_snippets(self, snippets: list) -> Dict[str, Any]:
        """Extract college info from search snippets."""
        data = {}
        patterns = [
            r'played\s+(?:golf\s+)?(?:at|for)\s+([A-Z][A-Za-z\s]+(?:University|College|State))',
            r'attended\s+(University\s+of\s+[A-Za-z\s]+|[A-Z][A-Za-z\s]+\s+University)',
            r'(University\s+of\s+[A-Za-z\s]+)',
        ]

        for snippet in snippets:
            for pattern in patterns:
                match = re.search(pattern, snippet, re.IGNORECASE)
                if match:
                    college = match.group(1).strip()
                    college = re.sub(r'\s*\([^)]+\)', '', college)
                    if college and len(college) > 3:
                        data['college_name'] = college
                        return data
        return data

    def _try_wikipedia(self, player_name: str) -> Optional[Dict[str, Any]]:
        """Try to get bio data from Wikipedia."""
        try:
            # Search Wikipedia
            params = {
                'action': 'opensearch',
                'search': f"{player_name} golfer",
                'limit': 5,
                'namespace': 0,
                'format': 'json',
            }

            data = self.get_json('https://en.wikipedia.org/w/api.php', params=params)
            if not data or len(data) < 2 or not data[1]:
                # Try without "golfer"
                params['search'] = player_name
                data = self.get_json('https://en.wikipedia.org/w/api.php', params=params)

            if not data or len(data) < 2 or not data[1]:
                return None

            title = data[1][0]

            # Fetch the page
            parse_params = {
                'action': 'parse',
                'page': title,
                'format': 'json',
                'prop': 'text',
            }

            page_data = self.get_json('https://en.wikipedia.org/w/api.php', params=parse_params)
            if not page_data or 'parse' not in page_data:
                return None

            html = page_data['parse'].get('text', {}).get('*', '')
            soup = BeautifulSoup(html, 'lxml')

            bio_data = self._extract_bio_from_wikipedia(soup)
            bio_data['source_url'] = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"

            return bio_data

        except Exception as e:
            self.logger.debug(f"Wikipedia search failed for {player_name}: {e}")
            return None

    def _try_espn(self, player_name: str, espn_id: str = None) -> Optional[Dict[str, Any]]:
        """Try to get bio data from ESPN."""
        try:
            # If we have an ESPN ID, use it directly
            if espn_id:
                url = f"https://www.espn.com/golf/player/_/id/{espn_id}"
            else:
                # Search ESPN for the player
                search_url = f"https://www.espn.com/golf/player/_/name/{player_name.lower().replace(' ', '-')}"
                url = search_url

            soup = self.get_page(url)
            if not soup:
                return None

            bio_data = self._extract_bio_from_espn(soup)
            bio_data['source_url'] = url

            return bio_data

        except Exception as e:
            self.logger.debug(f"ESPN search failed for {player_name}: {e}")
            return None

    def _try_grokepedia(self, player_name: str) -> Optional[Dict[str, Any]]:
        """Try to get bio data from Grokepedia."""
        try:
            # Search Grokepedia
            search_name = player_name.replace(' ', '+')
            url = f"https://www.grokepedia.com/search?q={search_name}+golf"

            soup = self.get_page(url)
            if not soup:
                return None

            # Look for player page link
            player_link = soup.find('a', href=re.compile(r'/player/|/golfer/', re.I))
            if not player_link:
                return None

            player_url = player_link.get('href', '')
            if not player_url.startswith('http'):
                player_url = f"https://www.grokepedia.com{player_url}"

            # Fetch player page
            player_soup = self.get_page(player_url)
            if not player_soup:
                return None

            bio_data = self._extract_bio_from_grokepedia(player_soup)
            bio_data['source_url'] = player_url

            return bio_data

        except Exception as e:
            self.logger.debug(f"Grokepedia search failed for {player_name}: {e}")
            return None

    def _extract_bio_from_wikipedia(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract bio data from Wikipedia page."""
        data = {}

        # Parse infobox
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all('tr'):
                label = row.find('th')
                value = row.find('td')
                if not label or not value:
                    continue

                label_text = label.get_text(strip=True).lower()
                value_text = value.get_text(strip=True)

                if 'born' in label_text:
                    # Extract birthplace
                    links = value.find_all('a')
                    locations = [l.get_text(strip=True) for l in links
                                if l.get_text(strip=True) and
                                not any(x in l.get_text().lower() for x in ['age', 'born', 'year', '('])]
                    if len(locations) >= 2:
                        data['hometown_city'] = locations[0]
                        data['hometown_state'] = locations[1]
                    elif len(locations) == 1:
                        data['hometown_city'] = locations[0]

                elif label_text in ['college', 'alma mater', 'education']:
                    data['college_name'] = re.sub(r'\s*\([^)]+\)', '', value_text).strip()

                elif label_text in ['residence', 'hometown']:
                    parts = [p.strip() for p in value_text.split(',')]
                    if parts:
                        data['hometown_city'] = parts[0]
                    if len(parts) > 1:
                        data['hometown_state'] = parts[1]

        # Parse text for high school
        for para in soup.find_all('p')[:10]:
            text = para.get_text()

            # High school patterns
            hs_match = re.search(r'([A-Z][A-Za-z\'\s]+)\s+High\s+School(?:\s+in\s+([A-Z][A-Za-z\s]+),?\s*([A-Z]{2})?)?', text)
            if hs_match and 'high_school_name' not in data:
                data['high_school_name'] = f"{hs_match.group(1).strip()} High School"
                if hs_match.group(2):
                    data['high_school_city'] = hs_match.group(2).strip()
                if hs_match.group(3):
                    data['high_school_state'] = hs_match.group(3).strip()

            # Hometown patterns
            if 'hometown_city' not in data:
                hometown_match = re.search(r'(?:from|raised in|grew up in)\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)', text)
                if hometown_match:
                    data['hometown_city'] = hometown_match.group(1).strip()
                    data['hometown_state'] = hometown_match.group(2).strip()

        return data

    def _extract_bio_from_espn(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract bio data from ESPN player page."""
        data = {}

        # ESPN bio section
        bio_section = soup.find('section', class_=re.compile(r'PlayerHeader|Bio', re.I))
        if not bio_section:
            bio_section = soup

        # Look for birthplace/hometown
        for item in bio_section.find_all(['li', 'div', 'span']):
            text = item.get_text(strip=True)

            if 'Birthplace' in text or 'Hometown' in text:
                # Extract city, state after label
                match = re.search(r'(?:Birthplace|Hometown)[:\s]+([^,]+),\s*(\w+)', text)
                if match:
                    data['hometown_city'] = match.group(1).strip()
                    data['hometown_state'] = match.group(2).strip()

            if 'College' in text:
                match = re.search(r'College[:\s]+(.+?)(?:\s*\(|$)', text)
                if match:
                    data['college_name'] = match.group(1).strip()

        # Look in player info table
        info_table = soup.find('table', class_=re.compile(r'PlayerBio|info', re.I))
        if info_table:
            for row in info_table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'birth' in label or 'hometown' in label:
                        parts = value.split(',')
                        if parts:
                            data['hometown_city'] = parts[0].strip()
                        if len(parts) > 1:
                            data['hometown_state'] = parts[1].strip()

        return data

    def _extract_bio_from_grokepedia(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract bio data from Grokepedia player page."""
        data = {}

        # Look for bio info in various places
        for elem in soup.find_all(['p', 'div', 'li', 'td']):
            text = elem.get_text()

            # High school
            hs_match = re.search(r'([A-Z][A-Za-z\'\s]+)\s+High\s+School', text)
            if hs_match and 'high_school_name' not in data:
                data['high_school_name'] = f"{hs_match.group(1).strip()} High School"

            # Hometown
            hometown_match = re.search(r'(?:from|hometown|born in)\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)', text, re.I)
            if hometown_match and 'hometown_city' not in data:
                data['hometown_city'] = hometown_match.group(1).strip()
                data['hometown_state'] = hometown_match.group(2).strip()

            # College
            college_match = re.search(r'(?:attended|played for|college)\s+([A-Z][A-Za-z\s]+(?:University|College))', text, re.I)
            if college_match and 'college_name' not in data:
                data['college_name'] = college_match.group(1).strip()

        return data

    def _update_player_bio(self, player: Player, bio_data: Dict[str, Any], source_name: str):
        """Update player with bio data and source attribution."""
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

        # Track the source
        if updated and bio_data.get('source_url'):
            player.bio_source_url = bio_data['source_url']
            player.bio_source_name = source_name

        if source_name == 'wikipedia' and bio_data.get('source_url'):
            player.wikipedia_url = bio_data['source_url']

        player.bio_last_updated = datetime.utcnow()

        self.logger.info(f"Updated {player.first_name} {player.last_name} from {source_name}")


def enrich_player_bios_multi_source(limit: int = 50, force: bool = False) -> Dict[str, Any]:
    """Convenience function to enrich player bios from multiple sources."""
    enricher = MultiSourceBioEnricher()
    return enricher.run(limit=limit, force=force)
