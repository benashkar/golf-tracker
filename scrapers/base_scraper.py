"""
Base Scraper Module
===================

This module provides the abstract base class that all league-specific scrapers
must inherit from. It handles common functionality like:
- HTTP request management with retries
- Rate limiting to be respectful to source websites
- Logging of all scraping operations
- Error handling and reporting

For Junior Developers:
---------------------
When creating a new scraper for a league, you'll inherit from BaseScraper
and implement the abstract methods. The base class handles the "plumbing"
so you can focus on the actual scraping logic.

Example:
    class PGATourRosterScraper(BaseScraper):
        def scrape(self):
            # Your scraping logic here
            pass

Design Pattern Used: Template Method Pattern
    The BaseScraper defines the skeleton of the scraping algorithm,
    and subclasses fill in the specific implementation details.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import time
from datetime import datetime
import traceback

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import Config
from database.connection import DatabaseManager
from database.models import ScrapeLog, League


class BaseScraper(ABC):
    """
    Abstract base class for all golf data scrapers.

    This class provides common functionality that all scrapers need:
    - Making HTTP requests with automatic retries
    - Rate limiting (pausing between requests)
    - Logging scrape operations to the database
    - Error handling and reporting

    Attributes:
        league_code (str): The code for the league being scraped (e.g., 'PGA')
        base_url (str): The base URL for the league's website
        session (requests.Session): Reusable HTTP session with retry logic
        db (DatabaseManager): Database connection manager

    For Junior Developers:
    ---------------------
    Think of this class as a "template" for scrapers. You don't use it directly,
    but you create new classes that inherit from it. The @abstractmethod decorator
    means "any class that inherits from me MUST implement this method."

    Methods you MUST implement in subclasses:
    - scrape(): The main scraping logic

    Methods you CAN override if needed:
    - get_headers(): Custom HTTP headers
    - parse_page(): Custom page parsing logic
    """

    def __init__(self, league_code: str, base_url: str):
        """
        Initialize the scraper with league information.

        Args:
            league_code: Short code for the league (e.g., 'PGA', 'DPWORLD')
            base_url: The main website URL for this league

        Example:
            scraper = PGATourRosterScraper('PGA', 'https://www.pgatour.com')
        """
        # Store the league information
        self.league_code = league_code
        self.base_url = base_url

        # Create a database connection manager
        self.db = DatabaseManager()

        # Create an HTTP session with retry logic
        # This means if a request fails, it will automatically retry
        self.session = self._create_session()

        # Get configuration values
        self.delay_seconds = Config.SCRAPE_DELAY_SECONDS
        self.user_agent = Config.USER_AGENT
        self.timeout = Config.REQUEST_TIMEOUT

        # Track the current scrape operation for logging
        self._current_scrape_log_id: Optional[int] = None

        # Statistics for the current scrape
        self._stats = {
            'records_processed': 0,
            'records_created': 0,
            'records_updated': 0,
            'errors': []
        }

        # Logger for this specific scraper
        self.logger = logger.bind(
            scraper=self.__class__.__name__,
            league=self.league_code
        )

    def _create_session(self) -> requests.Session:
        """
        Create an HTTP session with automatic retry logic.

        This is important because websites sometimes fail temporarily.
        Instead of crashing, we'll automatically retry the request.

        Returns:
            A configured requests.Session object

        For Junior Developers:
        ---------------------
        A "session" is like keeping a browser window open. It remembers
        cookies and other settings between requests, which is more efficient
        than opening a new connection every time.

        The retry strategy here means:
        - total=3: Try up to 3 times total
        - backoff_factor=1: Wait 1s, 2s, 4s between retries (exponential)
        - status_forcelist: Retry on these HTTP error codes
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=Config.MAX_RETRIES,
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        # Apply the retry strategy to the session
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for requests.

        Override this in subclasses if you need custom headers.

        Returns:
            Dictionary of HTTP headers

        For Junior Developers:
        ---------------------
        HTTP headers are like metadata sent with each request.
        The User-Agent tells the website what browser/tool is making the request.
        Some websites block requests without proper headers.
        """
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def get_page(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = 'GET',
        data: Optional[Dict] = None
    ) -> Optional[BeautifulSoup]:
        """
        Fetch a web page and return it as a BeautifulSoup object.

        This method handles:
        - Making the HTTP request
        - Checking for errors
        - Parsing the HTML
        - Rate limiting (waiting between requests)

        Args:
            url: The URL to fetch
            params: Optional query parameters (e.g., {'page': 1})
            method: HTTP method ('GET' or 'POST')
            data: Data for POST requests

        Returns:
            BeautifulSoup object if successful, None if failed

        Example:
            soup = self.get_page('https://www.pgatour.com/players')
            if soup:
                # Parse the page
                players = soup.find_all('div', class_='player-card')
        """
        try:
            # Log what we're doing
            self.logger.info(f"Fetching: {url}")

            # Make the HTTP request
            if method.upper() == 'POST':
                response = self.session.post(
                    url,
                    params=params,
                    data=data,
                    headers=self.get_headers(),
                    timeout=self.timeout
                )
            else:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self.get_headers(),
                    timeout=self.timeout
                )

            # Raise an exception if the request failed (4xx or 5xx status)
            response.raise_for_status()

            # Log the response size
            self.logger.debug(f"Received {len(response.content)} bytes")

            # Parse the HTML into a BeautifulSoup object
            soup = BeautifulSoup(response.text, 'lxml')

            # Be polite: wait before making another request
            # This prevents us from overwhelming the website
            self._rate_limit()

            return soup

        except requests.Timeout:
            self.logger.error(f"Timeout fetching {url}")
            self._stats['errors'].append(f"Timeout: {url}")
            return None

        except requests.HTTPError as e:
            self.logger.error(f"HTTP error fetching {url}: {e}")
            self._stats['errors'].append(f"HTTP {e.response.status_code}: {url}")
            return None

        except requests.RequestException as e:
            # Log the error but don't crash
            self.logger.error(f"Failed to fetch {url}: {str(e)}")
            self._stats['errors'].append(f"Request failed: {url} - {str(e)}")
            return None

    def get_json(
        self,
        url: str,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a URL that returns JSON data.

        Args:
            url: The URL to fetch
            params: Optional query parameters

        Returns:
            Parsed JSON as a dictionary, or None if failed

        Example:
            data = self.get_json('https://api.example.com/players')
            if data:
                for player in data['players']:
                    print(player['name'])
        """
        try:
            self.logger.info(f"Fetching JSON: {url}")

            response = self.session.get(
                url,
                params=params,
                headers={
                    **self.get_headers(),
                    'Accept': 'application/json',
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            self._rate_limit()

            return response.json()

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch JSON {url}: {str(e)}")
            self._stats['errors'].append(f"JSON request failed: {url}")
            return None

        except ValueError as e:
            self.logger.error(f"Invalid JSON from {url}: {str(e)}")
            self._stats['errors'].append(f"Invalid JSON: {url}")
            return None

    def _rate_limit(self):
        """
        Wait between requests to be respectful to websites.

        For Junior Developers:
        ---------------------
        Rate limiting is CRITICAL when scraping. Without it:
        1. You might get your IP blocked
        2. You could overload the server (which is rude)
        3. The website might think you're attacking them

        Always be a good internet citizen!
        """
        time.sleep(self.delay_seconds)

    def start_scrape_log(
        self,
        scrape_type: str,
        source_url: Optional[str] = None
    ) -> int:
        """
        Start logging a scrape operation in the database.

        This creates a record in the scrape_logs table so we can track:
        - When scrapes happen
        - Whether they succeed or fail
        - How many records were processed

        Args:
            scrape_type: Type of scrape ('roster', 'tournament_results', etc.)
            source_url: The URL being scraped

        Returns:
            The log ID for this scrape operation
        """
        with self.db.get_session() as session:
            # Look up the league ID
            league = session.query(League).filter_by(
                league_code=self.league_code
            ).first()

            # Create the log entry
            log = ScrapeLog(
                scrape_type=scrape_type,
                league_id=league.league_id if league else None,
                status='started',
                source_url=source_url,
                started_at=datetime.utcnow()
            )
            session.add(log)
            session.flush()  # Get the ID without committing

            self._current_scrape_log_id = log.log_id
            self.logger.info(f"Started {scrape_type} scrape (log_id={log.log_id})")

            # Reset stats for this scrape
            self._stats = {
                'records_processed': 0,
                'records_created': 0,
                'records_updated': 0,
                'errors': []
            }

            return log.log_id

    def complete_scrape_log(
        self,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Mark a scrape operation as complete in the database.

        Args:
            status: Final status ('success', 'partial', 'failed')
            error_message: Error details if something went wrong
        """
        if not self._current_scrape_log_id:
            return

        with self.db.get_session() as session:
            log = session.query(ScrapeLog).get(self._current_scrape_log_id)
            if log:
                log.status = status
                log.records_processed = self._stats['records_processed']
                log.records_created = self._stats['records_created']
                log.records_updated = self._stats['records_updated']
                log.completed_at = datetime.utcnow()

                # Calculate duration
                if log.started_at:
                    duration = (log.completed_at - log.started_at).total_seconds()
                    log.duration_seconds = int(duration)

                # Store error information
                if error_message:
                    log.error_message = error_message
                elif self._stats['errors']:
                    log.error_message = '\n'.join(self._stats['errors'][:10])  # First 10 errors

        self.logger.info(
            f"Completed scrape: {status}, "
            f"{self._stats['records_processed']} processed, "
            f"{self._stats['records_created']} created, "
            f"{self._stats['records_updated']} updated"
        )

        self._current_scrape_log_id = None

    def get_league_id(self) -> Optional[int]:
        """
        Get the database ID for this scraper's league.

        Returns:
            The league_id from the database, or None if not found
        """
        with self.db.get_session() as session:
            league = session.query(League).filter_by(
                league_code=self.league_code
            ).first()
            return league.league_id if league else None

    @abstractmethod
    def scrape(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the scraping operation.

        This method MUST be implemented by every scraper class.
        It should:
        1. Fetch the necessary web pages
        2. Parse the data
        3. Save to the database
        4. Return a summary of what was done

        Args:
            **kwargs: Scraper-specific arguments (e.g., year, tournament_id)

        Returns:
            Dictionary with scrape results:
            {
                'status': 'success' or 'failed',
                'records_processed': int,
                'records_created': int,
                'records_updated': int,
                'errors': list of error messages
            }

        For Junior Developers:
        ---------------------
        When you create a new scraper class, you MUST write this method.
        Python will give you an error if you try to create an instance
        of a class that doesn't implement all abstract methods.
        """
        pass

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        Run the scraper with full logging and error handling.

        This is the main entry point for running a scraper.
        It wraps the scrape() method with logging and error handling.

        Args:
            **kwargs: Arguments to pass to scrape()

        Returns:
            Dictionary with scrape results

        Example:
            scraper = PGATourRosterScraper()
            result = scraper.run()
            print(f"Created {result['records_created']} players")
        """
        scrape_type = getattr(self, 'scrape_type', 'roster')
        source_url = getattr(self, 'source_url', self.base_url)

        try:
            # Start logging
            self.start_scrape_log(scrape_type, source_url)

            # Run the scrape
            result = self.scrape(**kwargs)

            # Complete logging
            status = result.get('status', 'success')
            self.complete_scrape_log(status)

            return result

        except Exception as e:
            # Log the error with full stack trace
            error_msg = f"{type(e).__name__}: {str(e)}"
            stack_trace = traceback.format_exc()

            self.logger.error(f"Scrape failed: {error_msg}")
            self.logger.debug(f"Stack trace:\n{stack_trace}")

            self.complete_scrape_log('failed', error_msg)

            return {
                'status': 'failed',
                'error': error_msg,
                'records_processed': self._stats['records_processed'],
                'records_created': self._stats['records_created'],
                'records_updated': self._stats['records_updated'],
                'errors': self._stats['errors'] + [error_msg]
            }
