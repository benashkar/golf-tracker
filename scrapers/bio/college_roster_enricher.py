"""
College Golf Roster Bio Enricher
================================

Scrapes college golf team rosters to get high school and hometown data.

College athletic websites list players with their hometown and high school,
which is exactly what we need for local news stories.

Format on most college sites: "Dallas, Texas / Highland Park"
This tells us: hometown = Dallas, Texas; high school = Highland Park High School

Data Sources:
- NCAA D1 golf program athletic websites
- Uses standardized athletic site formats (SideArm, StatBroadcast, etc.)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import time

from loguru import logger

from scrapers.base_scraper import BaseScraper
from database.models import Player


class CollegeRosterBioEnricher(BaseScraper):
    """
    Enriches player bio data from college golf team rosters.

    Many PGA Tour players have college backgrounds, and college rosters
    typically list hometown and high school information.
    """

    scrape_type = 'player_bio'

    def __init__(self):
        super().__init__('BIO', 'https://www.ncaa.com')
        self.logger = logger.bind(scraper='CollegeRosterBioEnricher')

        # Major college golf programs that produce PGA Tour players
        # Format: (name, roster_url, school_name)
        self.college_rosters = [
            ('Texas', 'https://texaslonghorns.com/sports/mens-golf/roster', 'University of Texas'),
            ('Oklahoma State', 'https://okstate.com/sports/mens-golf/roster', 'Oklahoma State'),
            ('Arizona State', 'https://thesundevils.com/sports/mens-golf/roster', 'Arizona State'),
            ('Georgia', 'https://georgiadogs.com/sports/mens-golf/roster', 'University of Georgia'),
            ('Alabama', 'https://rolltide.com/sports/mens-golf/roster', 'University of Alabama'),
            ('Florida', 'https://floridagators.com/sports/mens-golf/roster', 'University of Florida'),
            ('Stanford', 'https://gostanford.com/sports/mens-golf/roster', 'Stanford University'),
            ('USC', 'https://usctrojans.com/sports/mens-golf/roster', 'USC'),
            ('Duke', 'https://goduke.com/sports/mens-golf/roster', 'Duke University'),
            ('Vanderbilt', 'https://vucommodores.com/sports/mens-golf/roster', 'Vanderbilt University'),
            ('Wake Forest', 'https://godeacs.com/sports/mens-golf/roster', 'Wake Forest University'),
            ('Texas Tech', 'https://texastech.com/sports/mens-golf/roster', 'Texas Tech'),
            ('Pepperdine', 'https://pepperdinewaves.com/sports/mens-golf/roster', 'Pepperdine University'),
            ('Illinois', 'https://fightingillini.com/sports/mens-golf/roster', 'University of Illinois'),
            ('North Carolina', 'https://goheels.com/sports/mens-golf/roster', 'UNC'),
            ('LSU', 'https://lsusports.net/sports/mens-golf/roster', 'LSU'),
            ('Clemson', 'https://clemsontigers.com/sports/mens-golf/roster', 'Clemson University'),
            ('Texas A&M', 'https://12thman.com/sports/mens-golf/roster', 'Texas A&M'),
            ('Auburn', 'https://auburntigers.com/sports/mens-golf/roster', 'Auburn University'),
            ('UCLA', 'https://uclabruins.com/sports/mens-golf/roster', 'UCLA'),
        ]

        self.request_delay = 2  # seconds between requests

    def scrape(self, **kwargs) -> Dict[str, Any]:
        """Scrape college rosters and match to existing players."""
        return self.enrich_from_college_rosters()

    def enrich_from_college_rosters(self) -> Dict[str, Any]:
        """
        Fetch college rosters and match players to our database.

        For each roster player, try to find them in our database
        and update their high school/hometown info.
        """
        self.logger.info("Starting college roster bio enrichment")

        results = {
            'processed': 0,
            'enriched': 0,
            'not_found': 0,
            'errors': [],
            'colleges_scraped': 0,
        }

        all_roster_data = []

        # Scrape each college roster
        for college_name, roster_url, school_name in self.college_rosters:
            try:
                self.logger.info(f"Scraping {college_name} roster...")
                roster_data = self._scrape_roster(roster_url, school_name)

                if roster_data:
                    all_roster_data.extend(roster_data)
                    results['colleges_scraped'] += 1
                    self.logger.info(f"  Found {len(roster_data)} players")

                time.sleep(self.request_delay)

            except Exception as e:
                self.logger.error(f"Error scraping {college_name}: {e}")
                results['errors'].append(f"{college_name}: {str(e)}")

        self.logger.info(f"Collected {len(all_roster_data)} players from {results['colleges_scraped']} colleges")

        # Match roster players to our database
        with self.db.get_session() as session:
            for player_data in all_roster_data:
                try:
                    success = self._match_and_update_player(session, player_data)
                    results['processed'] += 1

                    if success:
                        results['enriched'] += 1
                    else:
                        results['not_found'] += 1

                except Exception as e:
                    self.logger.error(f"Error matching player: {e}")
                    results['errors'].append(str(e))

        self.logger.info(f"Enrichment complete: {results['enriched']}/{results['processed']} players updated")
        return results

    def _scrape_roster(self, url: str, school_name: str) -> List[Dict]:
        """
        Scrape a college roster page.

        Returns list of player dictionaries with:
        - first_name, last_name
        - hometown_city, hometown_state
        - high_school_name
        - college_name
        """
        players = []

        soup = self.get_page(url)
        if not soup:
            return players

        # Common roster table/list formats
        # SideArm sports format (most common)
        roster_items = soup.find_all('li', class_=re.compile(r'roster', re.I))
        if not roster_items:
            roster_items = soup.find_all('div', class_=re.compile(r'roster.*player|player.*item', re.I))
        if not roster_items:
            # Try table format
            roster_items = soup.find_all('tr', class_=re.compile(r'roster', re.I))
        if not roster_items:
            # Just find all roster-related sections
            roster_items = soup.find_all(['li', 'div', 'tr'],
                attrs={'class': re.compile(r'roster|player', re.I)})

        for item in roster_items:
            player_data = self._parse_roster_item(item, school_name)
            if player_data:
                players.append(player_data)

        # Fallback: look for hometown patterns anywhere on page
        if not players:
            text = soup.get_text()
            # Pattern: "Name ... Hometown/HS" or similar
            patterns = [
                r'([A-Z][a-z]+)\s+([A-Z][a-z]+).*?([A-Z][a-z]+,\s*[A-Z][a-z]+)\s*/\s*([A-Z][A-Za-z\s]+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches[:20]:  # Limit matches
                    if len(match) >= 4:
                        hometown_parts = match[2].split(',')
                        players.append({
                            'first_name': match[0].strip(),
                            'last_name': match[1].strip(),
                            'hometown_city': hometown_parts[0].strip() if hometown_parts else '',
                            'hometown_state': hometown_parts[1].strip() if len(hometown_parts) > 1 else '',
                            'high_school_name': f"{match[3].strip()} High School" if 'high school' not in match[3].lower() else match[3].strip(),
                            'college_name': school_name,
                        })

        return players

    def _parse_roster_item(self, item, school_name: str) -> Optional[Dict]:
        """Parse a single roster item (player row/card)."""
        try:
            # Extract name
            name_elem = item.find(['a', 'span', 'div'], class_=re.compile(r'name|player', re.I))
            if not name_elem:
                name_elem = item.find('a')

            if not name_elem:
                return None

            full_name = name_elem.get_text(strip=True)
            name_parts = full_name.split()
            if len(name_parts) < 2:
                return None

            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])

            # Extract hometown/high school
            # Common format: "Dallas, Texas / Highland Park"
            hometown_elem = item.find(['span', 'div', 'td'],
                class_=re.compile(r'hometown|hs|high.?school|location', re.I))

            if not hometown_elem:
                # Look in text
                item_text = item.get_text()
                hometown_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]+)\s*/\s*([A-Za-z\s\'-]+)', item_text)
                if hometown_match:
                    return {
                        'first_name': first_name,
                        'last_name': last_name,
                        'hometown_city': hometown_match.group(1).strip(),
                        'hometown_state': hometown_match.group(2).strip(),
                        'high_school_name': self._format_high_school(hometown_match.group(3).strip()),
                        'college_name': school_name,
                    }
                return None

            hometown_text = hometown_elem.get_text(strip=True)

            # Parse "City, State / High School" format
            if '/' in hometown_text:
                parts = hometown_text.split('/')
                location = parts[0].strip()
                hs_name = parts[1].strip() if len(parts) > 1 else ''

                loc_parts = location.split(',')
                city = loc_parts[0].strip() if loc_parts else ''
                state = loc_parts[1].strip() if len(loc_parts) > 1 else ''

                return {
                    'first_name': first_name,
                    'last_name': last_name,
                    'hometown_city': city,
                    'hometown_state': state,
                    'high_school_name': self._format_high_school(hs_name),
                    'college_name': school_name,
                }

            return None

        except Exception as e:
            self.logger.debug(f"Error parsing roster item: {e}")
            return None

    def _format_high_school(self, name: str) -> str:
        """Ensure high school name ends with 'High School'."""
        if not name:
            return ''
        name = name.strip()
        if 'high school' not in name.lower():
            return f"{name} High School"
        return name

    def _match_and_update_player(self, session, roster_data: Dict) -> bool:
        """
        Try to find a player in our database and update their bio.

        Returns True if player was found and updated.
        """
        first_name = roster_data.get('first_name', '')
        last_name = roster_data.get('last_name', '')

        if not first_name or not last_name:
            return False

        # Find player by name
        player = session.query(Player).filter_by(
            first_name=first_name,
            last_name=last_name
        ).first()

        if not player:
            # Try partial match (some names might have middle names)
            player = session.query(Player).filter(
                Player.first_name == first_name,
                Player.last_name.ilike(f"%{last_name}%")
            ).first()

        if not player:
            return False

        # Update bio data
        updated = False

        if roster_data.get('high_school_name') and not player.high_school_name:
            player.high_school_name = roster_data['high_school_name']
            updated = True
            self.logger.info(f"Updated {first_name} {last_name} high school: {roster_data['high_school_name']}")

        if roster_data.get('hometown_city') and not player.hometown_city:
            player.hometown_city = roster_data['hometown_city']
            updated = True

        if roster_data.get('hometown_state') and not player.hometown_state:
            player.hometown_state = roster_data['hometown_state']
            updated = True

        if roster_data.get('college_name') and not player.college_name:
            player.college_name = roster_data['college_name']
            updated = True

        if updated:
            player.bio_source_name = 'college_roster'
            player.bio_last_updated = datetime.utcnow()

        return updated


def enrich_from_college_rosters() -> Dict[str, Any]:
    """Convenience function to run college roster enrichment."""
    enricher = CollegeRosterBioEnricher()
    return enricher.run()


if __name__ == '__main__':
    result = enrich_from_college_rosters()
    print(f"Enrichment complete: {result}")
