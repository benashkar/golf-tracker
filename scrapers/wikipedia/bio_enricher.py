"""
Wikipedia Bio Enricher
=======================

This module enriches player biographical data by scraping Wikipedia.
It extracts high school, college, hometown, and other biographical
information that is critical for our local news angle.

For Junior Developers:
---------------------
This is the KEY scraper for our use case. Local news stories need to know:
- What high school did they attend?
- What year did they graduate?
- Where are they from?
- What college did they go to?

Wikipedia is a great source for this information because:
1. It's publicly available
2. It has structured infoboxes
3. It's frequently updated
4. It covers most professional golfers

The challenge is that Wikipedia pages aren't perfectly consistent,
so we need to handle various formats and missing data gracefully.

Usage:
    from scrapers.wikipedia.bio_enricher import WikipediaBioEnricher

    enricher = WikipediaBioEnricher()

    # Enrich a single player
    result = enricher.enrich_player("Scottie Scheffler")

    # Enrich all players missing bio data
    result = enricher.enrich_missing_bios(limit=100)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import urllib.parse

from loguru import logger
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from database.models import Player


class WikipediaBioEnricher(BaseScraper):
    """
    Enriches player biographical data from Wikipedia.

    This enricher:
    1. Searches Wikipedia for the player
    2. Finds their page if it exists
    3. Extracts biographical information from infoboxes
    4. Updates the player record in our database

    For Junior Developers:
    ---------------------
    Wikipedia parsing is tricky because:
    1. Infobox formats vary between articles
    2. Some players don't have Wikipedia pages
    3. Names might not match exactly (Jr., III, etc.)
    4. Information might be in different places

    We use multiple strategies to find information:
    1. Infobox (the box on the right side of articles)
    2. First paragraph (usually contains basic bio)
    3. Categories (can indicate college, etc.)
    """

    scrape_type = 'player_bio'

    def __init__(self):
        """Initialize the Wikipedia bio enricher."""
        super().__init__('WIKI', 'https://en.wikipedia.org')

        self.api_url = 'https://en.wikipedia.org/w/api.php'
        self.search_url = 'https://en.wikipedia.org/w/index.php'

        # Patterns for extracting information
        # These regex patterns help find structured data
        self.high_school_patterns = [
            r'attended\s+([A-Z][^,\n]+?)\s+High\s+School',
            r'graduated\s+from\s+([A-Z][^,\n]+?)\s+High\s+School',
            r'([A-Z][A-Za-z\s]+)\s+High\s+School\s+in\s+([A-Z][A-Za-z]+(?:,\s*[A-Z][A-Za-z]+)?)',
            r'([A-Z][A-Za-z\'\s]+)\s+High\s+School',
            r'high school[:\s]+([^,\n]+)',
        ]

        # Pattern to extract city/state after high school name
        self.high_school_location_pattern = r'High\s+School\s+in\s+([A-Z][A-Za-z\s]+),?\s*([A-Z][A-Za-z\s]+)?'

        self.college_patterns = [
            r'University\s+of\s+(\w+(?:\s+\w+)*)',
            r'(\w+(?:\s+\w+)*)\s+University',
            r'(\w+(?:\s+\w+)*)\s+College',
            r'college[:\s]+([^,\n]+)',
        ]

        # Pattern to find hometown from "from City, State" or "born in City, State"
        self.hometown_patterns = [
            r'(?:from|hails from|raised in|grew up in)\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
            r'born\s+(?:and raised\s+)?in\s+([A-Z][A-Za-z\s]+),\s+([A-Z][A-Za-z\s]+)',
        ]

        self.logger = logger.bind(
            scraper='WikipediaBioEnricher'
        )

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """
        Main scrape method - enriches players missing bio data.

        Args:
            limit: Maximum number of players to process
            force: Re-enrich even if bio data exists

        Returns:
            Dictionary with enrichment results
        """
        limit = kwargs.get('limit', 50)
        force = kwargs.get('force', False)

        return self.enrich_missing_bios(limit=limit, force=force)

    def enrich_missing_bios(
        self,
        limit: int = 50,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich players that are missing biographical data.

        Args:
            limit: Maximum number of players to process
            force: If True, re-enrich even if data exists

        Returns:
            Dictionary with results:
            - processed: Number of players we tried to enrich
            - enriched: Number successfully enriched
            - not_found: Number where we couldn't find Wikipedia page
        """
        self.logger.info(f"Starting bio enrichment (limit={limit}, force={force})")

        results = {
            'processed': 0,
            'enriched': 0,
            'not_found': 0,
            'errors': []
        }

        with self.db.get_session() as session:
            # Build query for players needing enrichment
            query = session.query(Player)

            if not force:
                # Only get players missing high school info
                query = query.filter(
                    Player.high_school_name.is_(None)
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
                    self.logger.error(
                        f"Error enriching {player.first_name} {player.last_name}: {e}"
                    )
                    results['errors'].append(str(e))

        self.logger.info(
            f"Enrichment complete: {results['enriched']}/{results['processed']} enriched"
        )

        return results

    def enrich_player(self, player_name: str) -> Dict[str, Any]:
        """
        Enrich a single player by name.

        Args:
            player_name: Full name of the player

        Returns:
            Dictionary with extracted biographical data
        """
        self.logger.info(f"Enriching player: {player_name}")

        # Search for the player on Wikipedia
        page_title = self._search_wikipedia(player_name)

        if not page_title:
            return {'found': False}

        # Fetch and parse the Wikipedia page
        soup = self._fetch_wikipedia_page(page_title)

        if not soup:
            return {'found': False}

        # Extract biographical data
        bio_data = self._extract_bio_data(soup)
        bio_data['found'] = True
        bio_data['wikipedia_url'] = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_title)}"

        return bio_data

    def _enrich_player(self, session, player: Player) -> bool:
        """
        Enrich a player record in the database.

        Args:
            session: Database session
            player: Player object to enrich

        Returns:
            True if enrichment was successful
        """
        full_name = f"{player.first_name} {player.last_name}"
        self.logger.debug(f"Enriching: {full_name}")

        bio_data = self.enrich_player(full_name)

        if not bio_data.get('found'):
            # Try adding "golfer" to disambiguate
            bio_data = self.enrich_player(f"{full_name} golfer")

        if not bio_data.get('found'):
            self.logger.debug(f"No Wikipedia page found for {full_name}")
            return False

        # Update player record
        self._update_player_bio(player, bio_data)
        self.logger.info(f"Enriched {full_name} with Wikipedia data")

        return True

    def _search_wikipedia(self, query: str) -> Optional[str]:
        """
        Search Wikipedia for a player page.

        Args:
            query: Search query (player name)

        Returns:
            Wikipedia page title if found, None otherwise

        For Junior Developers:
        ---------------------
        Wikipedia has an API that lets us search for pages.
        We use the 'opensearch' action which returns matching titles.
        """
        params = {
            'action': 'opensearch',
            'search': query,
            'limit': 5,
            'namespace': 0,
            'format': 'json',
        }

        data = self.get_json(f"{self.api_url}", params=params)

        if not data or len(data) < 2:
            return None

        titles = data[1]  # Second element contains the titles

        # Look for a page that's likely about a golfer
        for title in titles:
            if self._is_golfer_page(title):
                return title

        # Return first result if no golfer-specific match
        return titles[0] if titles else None

    def _is_golfer_page(self, title: str) -> bool:
        """
        Check if a Wikipedia title is likely about a golfer.

        Args:
            title: Wikipedia page title

        Returns:
            True if this looks like a golfer's page
        """
        # Check if title ends with "(golfer)" or similar
        golfer_indicators = ['(golfer)', '(golf)', '(professional golfer)']
        title_lower = title.lower()

        for indicator in golfer_indicators:
            if indicator in title_lower:
                return True

        return False

    def _fetch_wikipedia_page(self, title: str) -> Optional[BeautifulSoup]:
        """
        Fetch a Wikipedia page by title.

        Args:
            title: Wikipedia page title

        Returns:
            BeautifulSoup object of the page, or None
        """
        # Use the parse API to get the page content
        params = {
            'action': 'parse',
            'page': title,
            'format': 'json',
            'prop': 'text',
        }

        data = self.get_json(self.api_url, params=params)

        if not data or 'parse' not in data:
            return None

        html = data['parse'].get('text', {}).get('*', '')
        return BeautifulSoup(html, 'lxml')

    def _extract_bio_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract biographical data from a Wikipedia page.

        Args:
            soup: BeautifulSoup object of the Wikipedia page

        Returns:
            Dictionary with extracted data

        For Junior Developers:
        ---------------------
        Wikipedia infoboxes have a consistent structure:
        - They're in a table with class "infobox"
        - Each row has a label (th) and value (td)
        - Labels are things like "Born", "College", etc.

        We extract data from:
        1. The infobox (most reliable)
        2. The first paragraph (for additional context)
        3. Early life/Background sections (for high school)
        4. Links and categories (for school/college info)
        """
        bio_data = {}

        # Try to get data from infobox
        infobox = soup.find('table', class_='infobox')
        if infobox:
            bio_data.update(self._parse_infobox(infobox))

        # Try to get data from first paragraph
        first_para = soup.find('p', class_='')
        if first_para:
            para_text = first_para.get_text()
            bio_data.update(self._parse_paragraph(para_text))

        # Look in Early life/Background sections for high school info
        if 'high_school_name' not in bio_data:
            early_life_data = self._parse_early_life_section(soup)
            bio_data.update(early_life_data)

        # Try to extract hometown from paragraph if not found in infobox
        if 'hometown_city' not in bio_data:
            hometown_data = self._extract_hometown_from_text(soup)
            bio_data.update(hometown_data)

        return bio_data

    def _parse_early_life_section(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse Early life or Background section for high school information.

        Args:
            soup: BeautifulSoup object of the Wikipedia page

        Returns:
            Dictionary with extracted data
        """
        data = {}

        # Look for section headings that might contain early life info
        section_names = ['Early life', 'Background', 'Early life and education',
                        'Personal life', 'Biography', 'Early years']

        for heading in soup.find_all(['h2', 'h3']):
            heading_text = heading.get_text(strip=True)

            for section_name in section_names:
                if section_name.lower() in heading_text.lower():
                    # Get all paragraphs until next heading
                    section_text = self._get_section_text(heading)
                    if section_text:
                        data.update(self._parse_paragraph(section_text))
                        if 'high_school_name' in data:
                            return data

        return data

    def _get_section_text(self, heading) -> str:
        """Get all text from a section until the next heading."""
        text_parts = []
        sibling = heading.find_next_sibling()

        while sibling and sibling.name not in ['h2', 'h3']:
            if sibling.name == 'p':
                text_parts.append(sibling.get_text())
            sibling = sibling.find_next_sibling()

        return ' '.join(text_parts)

    def _extract_hometown_from_text(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract hometown from page text using patterns.

        Args:
            soup: BeautifulSoup object

        Returns:
            Dictionary with hometown_city and hometown_state if found
        """
        data = {}

        # Get all paragraph text
        paragraphs = soup.find_all('p')
        for para in paragraphs[:5]:  # Check first 5 paragraphs
            text = para.get_text()

            for pattern in self.hometown_patterns:
                match = re.search(pattern, text)
                if match:
                    data['hometown_city'] = match.group(1).strip()
                    if match.lastindex >= 2:
                        data['hometown_state'] = match.group(2).strip()
                    return data

        return data

    def _parse_infobox(self, infobox: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse the Wikipedia infobox for biographical data.

        Args:
            infobox: BeautifulSoup element for the infobox

        Returns:
            Dictionary with extracted data
        """
        data = {}

        rows = infobox.find_all('tr')

        for row in rows:
            label = row.find('th')
            value = row.find('td')

            if not label or not value:
                continue

            label_text = label.get_text(strip=True).lower()
            value_text = value.get_text(strip=True)

            # Birth information
            if 'born' in label_text:
                data.update(self._parse_birth_info(value_text, value))

            # Education/College
            elif label_text in ['college', 'alma mater', 'education']:
                data['college_name'] = self._clean_college_name(value_text)

            # Residence/Hometown
            elif label_text in ['residence', 'home town', 'hometown']:
                data.update(self._parse_location(value_text))

            # Amateur wins (can indicate college)
            elif 'amateur' in label_text:
                college = self._extract_college_from_text(value_text)
                if college and 'college_name' not in data:
                    data['college_name'] = college

        return data

    def _parse_birth_info(
        self,
        text: str,
        element: BeautifulSoup
    ) -> Dict[str, Any]:
        """
        Parse birth information from infobox.

        Args:
            text: Text content
            element: BeautifulSoup element (for extracting links)

        Returns:
            Dictionary with birth data
        """
        data = {}

        # Try to extract birth date
        date_match = re.search(r'\(born\s+([^)]+)\)', text)
        if not date_match:
            date_match = re.search(
                r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})',
                text
            )

        if date_match:
            try:
                from dateutil import parser
                birth_date = parser.parse(date_match.group(1))
                data['birth_date'] = birth_date.strftime('%Y-%m-%d')
            except:
                pass

        # Try to extract birthplace from links
        links = element.find_all('a')
        locations = []
        for link in links:
            title = link.get('title', '')
            if title and not any(x in title.lower() for x in ['age', 'born', 'year']):
                locations.append(link.get_text(strip=True))

        if len(locations) >= 2:
            data['birthplace_city'] = locations[0]
            data['birthplace_state'] = locations[1]
        elif len(locations) == 1:
            data['birthplace_city'] = locations[0]

        return data

    def _parse_location(self, text: str) -> Dict[str, Any]:
        """
        Parse a location string into city/state/country.

        Args:
            text: Location text (e.g., "Dallas, Texas, U.S.")

        Returns:
            Dictionary with location components
        """
        data = {}
        parts = [p.strip() for p in text.split(',')]

        if len(parts) >= 1:
            data['hometown_city'] = parts[0]
        if len(parts) >= 2:
            data['hometown_state'] = parts[1]
        if len(parts) >= 3:
            data['hometown_country'] = parts[2]

        return data

    def _parse_paragraph(self, text: str) -> Dict[str, Any]:
        """
        Extract biographical data from paragraph text.

        Args:
            text: Paragraph text

        Returns:
            Dictionary with extracted data
        """
        data = {}

        # Look for high school with location pattern first
        # e.g., "Highland Park High School in Dallas, Texas"
        location_pattern = r'([A-Z][A-Za-z\'\s]+)\s+High\s+School\s+in\s+([A-Z][A-Za-z\s]+),?\s*([A-Z][A-Za-z\s]+)?'
        location_match = re.search(location_pattern, text)
        if location_match:
            data['high_school_name'] = f"{location_match.group(1).strip()} High School"
            data['high_school_city'] = location_match.group(2).strip().rstrip(',')
            if location_match.group(3):
                data['high_school_state'] = location_match.group(3).strip()
        else:
            # Fallback to simpler patterns
            for pattern in self.high_school_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    school = match.group(1).strip() if match.lastindex else match.group(0)
                    if 'High School' not in school:
                        school = f"{school} High School"
                    data['high_school_name'] = school
                    break

        # Look for college
        if 'college_name' not in data:
            for pattern in self.college_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['college_name'] = self._clean_college_name(match.group(0))
                    break

        # Look for graduation year - try high school year first, then general
        hs_year_match = re.search(r'(?:graduated|class of)\s+(?:from\s+)?(?:\w+\s+)?High\s+School\s+in\s+(\d{4})', text, re.IGNORECASE)
        if hs_year_match:
            year = int(hs_year_match.group(1))
            if 1990 <= year <= 2030:
                data['high_school_graduation_year'] = year
        else:
            year_match = re.search(r'graduated?\s+(?:in\s+)?(\d{4})', text, re.IGNORECASE)
            if year_match:
                year = int(year_match.group(1))
                if 1990 <= year <= 2030:
                    if 'high_school_name' in data:
                        data['high_school_graduation_year'] = year

        return data

    def _clean_college_name(self, name: str) -> str:
        """
        Clean up a college/university name.

        Args:
            name: Raw college name

        Returns:
            Cleaned college name
        """
        # Remove common suffixes and clean up
        name = re.sub(r'\s*\([^)]+\)', '', name)  # Remove parenthetical
        name = re.sub(r'\s*\d{4}[-–]\d{4}', '', name)  # Remove year ranges
        name = name.strip()
        return name

    def _extract_college_from_text(self, text: str) -> Optional[str]:
        """
        Try to extract a college name from text.

        Args:
            text: Text that might contain a college name

        Returns:
            College name if found, None otherwise
        """
        for pattern in self.college_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._clean_college_name(match.group(0))
        return None

    def _update_player_bio(self, player: Player, bio_data: Dict[str, Any]):
        """
        Update a player record with biographical data.

        Args:
            player: Player object to update
            bio_data: Dictionary with biographical data
        """
        # Only update fields that are empty in the database
        # This prevents overwriting manually entered data

        if bio_data.get('high_school_name') and not player.high_school_name:
            player.high_school_name = bio_data['high_school_name']

        if bio_data.get('high_school_city') and not player.high_school_city:
            player.high_school_city = bio_data['high_school_city']

        if bio_data.get('high_school_state') and not player.high_school_state:
            player.high_school_state = bio_data['high_school_state']

        if bio_data.get('high_school_graduation_year') and not player.high_school_graduation_year:
            player.high_school_graduation_year = bio_data['high_school_graduation_year']

        if bio_data.get('college_name') and not player.college_name:
            player.college_name = bio_data['college_name']

        if bio_data.get('hometown_city') and not player.hometown_city:
            player.hometown_city = bio_data['hometown_city']

        if bio_data.get('hometown_state') and not player.hometown_state:
            player.hometown_state = bio_data['hometown_state']

        if bio_data.get('hometown_country') and not player.hometown_country:
            player.hometown_country = bio_data['hometown_country']

        if bio_data.get('birthplace_city') and not player.birthplace_city:
            player.birthplace_city = bio_data['birthplace_city']

        if bio_data.get('birthplace_state') and not player.birthplace_state:
            player.birthplace_state = bio_data['birthplace_state']

        if bio_data.get('wikipedia_url') and not player.wikipedia_url:
            player.wikipedia_url = bio_data['wikipedia_url']

        # Update the last enrichment timestamp
        player.bio_last_updated = datetime.utcnow()


def enrich_player_bios(limit: int = 50, force: bool = False) -> Dict[str, Any]:
    """
    Convenience function to enrich player bios.

    Args:
        limit: Maximum number of players to process
        force: Re-enrich even if bio data exists

    Returns:
        Dictionary with enrichment results
    """
    enricher = WikipediaBioEnricher()
    return enricher.run(limit=limit, force=force)


if __name__ == '__main__':
    result = enrich_player_bios(limit=10)
    print(f"Enrichment complete: {result}")
