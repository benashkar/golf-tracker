# Golf Tournament Tracker - Project Specification for Local News

## Project Overview

This project creates a comprehensive golf data collection and display system for a local news site that publishes stories about former high school players who have gone on to play in professional golf leagues.

### Primary Goal
Enable writing stories like:
> "Scottie Scheffler, a 2014 graduate of Highland Park High School in Dallas, Texas, finished first in the American Express Championship on Sunday, January 25th. Here are his scores for each day he competed..."

### Key Features
1. **Player Roster Database** - Collect player info including high school, graduation year, hometown, and college
2. **Tournament Results** - Scrape and store tournament results with daily scores
3. **Multi-League Support** - PGA Tour, Korn Ferry Tour, Champions Tour, LPGA, DP World Tour, LIV Golf, College Golf, PGA Tour Americas (planned), USGA Amateur (planned)
4. **Web Dashboard** - View player history by event or event results by player
5. **Daily Automation** - GitHub Actions for scheduled scraping
6. **MySQL Database** - Hosted on Render for all leagues in one database

---

## Technical Stack

- **Language**: Python 3.11+
- **Database**: PostgreSQL (hosted on Render) - Note: Schema uses MySQL syntax for reference, but production uses PostgreSQL
- **ORM**: SQLAlchemy 2.0+
- **Web Framework**: Flask with Jinja2 templates
- **Scraping**: BeautifulSoup4, Requests, Selenium (for JS-heavy pages)
- **Data Sources**:
  - PGA Tour GraphQL API (PGA Tour, Korn Ferry, Champions, PGA Tour Americas)
  - ESPN API (LPGA, DP World Tour)
  - LIV Golf hardcoded schedule (no public API available)
  - Golfstat (College Golf)
  - Multi-source bio enrichment cascade: DuckDuckGo → Wikipedia → ESPN → Grokepedia
- **Deployment**: Render (cron job + PostgreSQL database)
- **CI/CD**: GitHub Actions + Render auto-deploy on push

---

## Database Schema

### Tables

```sql
-- ============================================================
-- LEAGUES TABLE
-- Stores information about each golf league/tour
-- ============================================================
CREATE TABLE leagues (
    league_id INT AUTO_INCREMENT PRIMARY KEY,
    league_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g., 'PGA', 'DPWORLD', 'KORNFERRY'
    league_name VARCHAR(100) NOT NULL,        -- e.g., 'PGA Tour', 'DP World Tour'
    website_url VARCHAR(255),                 -- Official website for scraping
    is_active BOOLEAN DEFAULT TRUE,           -- Whether we're actively tracking this league
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ============================================================
-- PLAYERS TABLE
-- Core player information - biographical data
-- ============================================================
CREATE TABLE players (
    player_id INT AUTO_INCREMENT PRIMARY KEY,

    -- Basic Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) GENERATED ALWAYS AS (CONCAT(first_name, ' ', last_name)) STORED,

    -- Biographical Info (KEY FOR LOCAL NEWS STORIES)
    birth_date DATE,
    age INT,                                  -- Calculated/updated periodically

    -- HIGH SCHOOL INFO (Critical for local news angle)
    high_school_name VARCHAR(200),            -- e.g., 'Highland Park High School'
    high_school_city VARCHAR(100),            -- e.g., 'Dallas'
    high_school_state VARCHAR(50),            -- e.g., 'Texas'
    high_school_graduation_year INT,          -- e.g., 2014

    -- HOMETOWN INFO
    hometown_city VARCHAR(100),               -- e.g., 'Dallas'
    hometown_state VARCHAR(100),              -- e.g., 'Texas'
    hometown_country VARCHAR(100),            -- e.g., 'USA'
    birthplace_city VARCHAR(100),             -- e.g., 'Ridgewood'
    birthplace_state VARCHAR(100),            -- e.g., 'New Jersey'
    birthplace_country VARCHAR(100),          -- e.g., 'USA'

    -- COLLEGE INFO
    college_name VARCHAR(200),                -- e.g., 'University of Texas'
    college_graduation_year INT,              -- e.g., 2018

    -- ==========================================================
    -- TOUR-SPECIFIC PLAYER IDs (Critical for data matching)
    -- ==========================================================
    -- Each tour has its own player ID system. A player may have
    -- different IDs on different tours. These are used to match
    -- leaderboard data to the correct player record.
    -- ==========================================================
    pga_tour_id VARCHAR(50),                  -- PGA Tour player ID (tour code: R)
    korn_ferry_id VARCHAR(50),                -- Korn Ferry Tour player ID (tour code: H)
    champions_id VARCHAR(50),                 -- PGA Tour Champions player ID (tour code: S)
    lpga_id VARCHAR(50),                      -- LPGA Tour player ID (from ESPN)
    espn_id VARCHAR(50),                      -- Generic ESPN ID
    wikipedia_url VARCHAR(500),

    -- Profile
    profile_image_url VARCHAR(500),

    -- Metadata
    bio_last_updated TIMESTAMP,               -- When we last scraped bio info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes for common queries
    INDEX idx_high_school (high_school_name, high_school_state),
    INDEX idx_hometown (hometown_city, hometown_state),
    INDEX idx_college (college_name),
    INDEX idx_last_name (last_name),
    INDEX idx_pga_tour_id (pga_tour_id),
    INDEX idx_korn_ferry_id (korn_ferry_id),
    INDEX idx_champions_id (champions_id),
    INDEX idx_lpga_id (lpga_id)
);

-- ============================================================
-- PLAYER_LEAGUES TABLE
-- Many-to-many relationship: players can be in multiple leagues
-- ============================================================
CREATE TABLE player_leagues (
    player_league_id INT AUTO_INCREMENT PRIMARY KEY,
    player_id INT NOT NULL,
    league_id INT NOT NULL,
    league_player_id VARCHAR(50),             -- Player's ID within that league
    is_current_member BOOLEAN DEFAULT TRUE,   -- Currently active in this league
    joined_date DATE,
    
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
    FOREIGN KEY (league_id) REFERENCES leagues(league_id) ON DELETE CASCADE,
    UNIQUE KEY unique_player_league (player_id, league_id)
);

-- ============================================================
-- TOURNAMENTS TABLE
-- Information about each tournament/event
-- ============================================================
CREATE TABLE tournaments (
    tournament_id INT AUTO_INCREMENT PRIMARY KEY,
    league_id INT NOT NULL,
    
    -- Tournament Info
    tournament_name VARCHAR(200) NOT NULL,    -- e.g., 'The American Express'
    tournament_year INT NOT NULL,             -- e.g., 2025
    
    -- Dates
    start_date DATE,
    end_date DATE,
    
    -- Location
    course_name VARCHAR(200),                 -- e.g., 'PGA West (Stadium Course)'
    city VARCHAR(100),                        -- e.g., 'La Quinta'
    state VARCHAR(100),                       -- e.g., 'California'
    country VARCHAR(100),                     -- e.g., 'USA'
    
    -- Tournament Details
    purse_amount DECIMAL(15, 2),              -- Total prize money
    purse_currency VARCHAR(10) DEFAULT 'USD',
    par INT,                                  -- Course par
    total_rounds INT DEFAULT 4,               -- Usually 4 for most tournaments
    
    -- Status
    status ENUM('scheduled', 'in_progress', 'completed', 'cancelled') DEFAULT 'scheduled',

    -- ==========================================================
    -- TOUR-SPECIFIC TOURNAMENT IDs
    -- ==========================================================
    -- Each tour has its own tournament ID system used in their APIs.
    -- These are needed to fetch leaderboard data from the correct API endpoint.
    -- ==========================================================
    pga_tour_tournament_id VARCHAR(50),       -- PGA Tour API tournament ID
    korn_ferry_tournament_id VARCHAR(50),     -- Korn Ferry API tournament ID
    champions_tournament_id VARCHAR(50),      -- Champions Tour API tournament ID
    lpga_tournament_id VARCHAR(50),           -- LPGA/ESPN API tournament ID
    espn_tournament_id VARCHAR(50),           -- Generic ESPN tournament ID

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    INDEX idx_dates (start_date, end_date),
    INDEX idx_year_league (tournament_year, league_id),
    INDEX idx_pga_tour_tournament_id (pga_tour_tournament_id),
    INDEX idx_korn_ferry_tournament_id (korn_ferry_tournament_id),
    INDEX idx_champions_tournament_id (champions_tournament_id),
    INDEX idx_lpga_tournament_id (lpga_tournament_id),
    UNIQUE KEY unique_tournament (league_id, tournament_name, tournament_year)
);

-- ============================================================
-- TOURNAMENT_RESULTS TABLE
-- Final results for each player in a tournament
-- ============================================================
CREATE TABLE tournament_results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    tournament_id INT NOT NULL,
    player_id INT NOT NULL,
    
    -- Final Position
    final_position INT,                       -- 1, 2, 3, etc. (NULL if missed cut)
    final_position_display VARCHAR(20),       -- 'T3', '1', 'CUT', 'WD', 'DQ'
    
    -- Scores
    total_score INT,                          -- Total strokes
    total_to_par INT,                         -- e.g., -15, +3, 0
    
    -- Round Scores (stored as JSON for flexibility)
    round_scores JSON,                        -- {"R1": 68, "R2": 65, "R3": 70, "R4": 67}
    round_to_par JSON,                        -- {"R1": -4, "R2": -7, "R3": -2, "R4": -5}
    
    -- Individual Round Scores (also as columns for easy querying)
    round_1_score INT,
    round_2_score INT,
    round_3_score INT,
    round_4_score INT,
    round_1_to_par INT,
    round_2_to_par INT,
    round_3_to_par INT,
    round_4_to_par INT,
    
    -- Status
    made_cut BOOLEAN,
    status ENUM('active', 'cut', 'withdrawn', 'disqualified') DEFAULT 'active',
    
    -- Earnings
    earnings DECIMAL(15, 2),
    earnings_currency VARCHAR(10) DEFAULT 'USD',
    
    -- FedEx Cup / Race to Dubai Points (depends on league)
    points_earned DECIMAL(10, 2),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
    UNIQUE KEY unique_player_tournament (tournament_id, player_id),
    INDEX idx_position (final_position),
    INDEX idx_player_results (player_id, tournament_id)
);

-- ============================================================
-- SCRAPE_LOG TABLE
-- Track all scraping operations for debugging and monitoring
-- ============================================================
CREATE TABLE scrape_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- What was scraped
    scrape_type ENUM('roster', 'tournament_list', 'tournament_results', 'player_bio') NOT NULL,
    league_id INT,
    tournament_id INT,
    player_id INT,
    
    -- Results
    status ENUM('started', 'success', 'partial', 'failed') NOT NULL,
    records_processed INT DEFAULT 0,
    records_created INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    error_stack_trace TEXT,
    
    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INT,
    
    -- Source info
    source_url VARCHAR(500),
    
    FOREIGN KEY (league_id) REFERENCES leagues(league_id) ON DELETE SET NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE SET NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE SET NULL,
    INDEX idx_scrape_date (started_at),
    INDEX idx_status (status)
);

-- ============================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================

-- View: Player with full location info for news stories
CREATE VIEW v_player_news_info AS
SELECT 
    p.player_id,
    p.full_name,
    p.high_school_name,
    p.high_school_city,
    p.high_school_state,
    p.high_school_graduation_year,
    p.hometown_city,
    p.hometown_state,
    p.college_name,
    p.college_graduation_year,
    CONCAT(p.high_school_name, ' in ', p.high_school_city, ', ', p.high_school_state) AS high_school_full,
    CONCAT('a ', p.high_school_graduation_year, ' graduate of ', p.high_school_name) AS news_blurb
FROM players p;

-- View: Tournament results with player info for news
CREATE VIEW v_tournament_results_for_news AS
SELECT 
    t.tournament_name,
    t.tournament_year,
    t.start_date,
    t.end_date,
    t.course_name,
    t.city AS tournament_city,
    t.state AS tournament_state,
    l.league_name,
    p.full_name AS player_name,
    p.high_school_name,
    p.high_school_graduation_year,
    p.high_school_city,
    p.high_school_state,
    p.college_name,
    tr.final_position,
    tr.final_position_display,
    tr.total_to_par,
    tr.round_1_score,
    tr.round_2_score,
    tr.round_3_score,
    tr.round_4_score,
    tr.earnings
FROM tournament_results tr
JOIN tournaments t ON tr.tournament_id = t.tournament_id
JOIN leagues l ON t.league_id = l.league_id
JOIN players p ON tr.player_id = p.player_id;
```

---

## Database Migrations

The project uses a simple SQL migration system. Migrations are stored in `database/migrations/` and numbered sequentially.

### Migration Files

```
database/migrations/
├── 001_initial_schema.sql              # Initial table creation
└── 002_add_tour_specific_player_ids.sql # Add korn_ferry_id, champions_id, lpga_id columns
```

### Running Migrations

**Option 1: Auto-Migration with run_scrape.py**

The `run_scrape.py` script automatically runs pending migrations before scraping:

```bash
python run_scrape.py --year 2026
```

This is the recommended approach for Render cron jobs.

**Option 2: Manual Migration**

```bash
# Run migration script directly
python run_migration.py

# Or run SQL file directly against PostgreSQL
psql $DATABASE_URL -f database/migrations/002_add_tour_specific_player_ids.sql
```

### Adding a New Migration

When adding new columns or tables:

1. Create a new migration file: `database/migrations/003_description.sql`
2. Add the SQL statements using PostgreSQL syntax
3. Add the same statements to `run_scrape.py` and `run_migration.py`
4. Update `database/models.py` with the new columns

Example migration for a new league:
```sql
-- 003_add_new_league_ids.sql
ALTER TABLE players ADD COLUMN IF NOT EXISTS new_league_id VARCHAR(50);
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS new_league_tournament_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_new_league_id ON players(new_league_id);
CREATE INDEX IF NOT EXISTS idx_new_league_tournament_id ON tournaments(new_league_tournament_id);
```

---

## Render Deployment

### Cron Job Configuration

The golf tracker runs as a Render cron job that scrapes all leagues every 2 hours.

**Cron Job Settings:**
- **Name**: `golf-tracker-all-leagues`
- **Schedule**: `0 */2 * * *` (every 2 hours)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python run_scrape.py --year 2026`
- **Plan**: Starter (recommended) or Free

**Required Environment Variables:**
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/dbname` |

### Setting Up DATABASE_URL

1. Go to your Render PostgreSQL database dashboard
2. Copy the "External Database URL"
3. Go to your cron job settings → Environment
4. Add `DATABASE_URL` with the copied value

**Important:** The DATABASE_URL must include `sslmode=require` for Render PostgreSQL:
```
postgresql://user:pass@host:5432/dbname?sslmode=require
```

### Manual Deploy Trigger

To manually trigger a scrape after making changes:
1. Go to Render Dashboard → Your Cron Job → Deploys
2. Click "Deploy Latest Commit" or "Manual Deploy"

---

## Project File Structure

```
golf-tracker/
├── README.md                           # Project overview and setup instructions
├── requirements.txt                    # Python dependencies
├── .env.example                        # Environment variable template
├── .gitignore                          # Git ignore file
├── Dockerfile                          # Container configuration
├── docker-compose.yml                  # Local development with PostgreSQL
├── render.yaml                         # Render deployment configuration
├── run_scrape.py                       # Main entry point with auto-migration
├── run_migration.py                    # Standalone migration runner
│
├── config/
│   ├── __init__.py
│   ├── settings.py                     # Configuration management
│   └── leagues.py                      # League-specific configurations
│
├── database/
│   ├── __init__.py
│   ├── connection.py                   # Database connection manager
│   ├── models.py                       # SQLAlchemy ORM models
│   ├── migrations/                     # Database migration scripts
│   │   ├── 001_initial_schema.sql      # Initial tables
│   │   └── 002_add_tour_specific_player_ids.sql  # Tour-specific ID columns
│   └── seeds/                          # Initial data
│       └── seed_leagues.sql
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py                 # Abstract base class for all scrapers
│   │
│   ├── pga_tour/                       # ✅ IMPLEMENTED - PGA Tour (tour code: R)
│   │   ├── __init__.py
│   │   ├── base_pga_scraper.py         # Base class for PGA ecosystem tours
│   │   ├── roster_scraper.py           # Scrape PGA Tour player roster
│   │   ├── tournament_scraper.py       # Scrape tournament schedule and results
│   │   └── bio_scraper.py              # Scrape player biographical info
│   │
│   ├── korn_ferry/                     # ✅ IMPLEMENTED - Korn Ferry Tour (tour code: H)
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Uses BasePGAEcosystemScraper
│   │   └── tournament_scraper.py       # Uses BasePGAEcosystemScraper
│   │
│   ├── champions/                      # ✅ IMPLEMENTED - PGA Tour Champions (tour code: S)
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Uses BasePGAEcosystemScraper
│   │   └── tournament_scraper.py       # Uses BasePGAEcosystemScraper
│   │
│   ├── lpga/                           # ✅ IMPLEMENTED - LPGA Tour (ESPN API)
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Uses ESPN API
│   │   └── tournament_scraper.py       # Uses ESPN API
│   │
│   ├── college/                        # 🚧 IN PROGRESS - NCAA College Golf
│   │   ├── __init__.py
│   │   └── tournament_scraper.py       # Uses Golfstat HTML scraping
│   │
│   ├── dp_world/                       # ✅ IMPLEMENTED - DP World Tour
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Uses ESPN API
│   │   └── tournament_scraper.py       # Uses ESPN API with round-by-round scores
│   │
│   ├── liv/                            # ✅ IMPLEMENTED - LIV Golf
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Hardcoded player data (no public API)
│   │   └── tournament_scraper.py       # Hardcoded schedule + results
│   │
│   ├── pga_americas/                   # 🚧 IN PROGRESS - PGA Tour Americas
│   │   ├── __init__.py
│   │   ├── roster_scraper.py           # Uses PGA GraphQL API (tour code: Y)
│   │   └── tournament_scraper.py       # Uses PGA GraphQL API
│   │
│   ├── bio/                            # ✅ IMPLEMENTED - Multi-source bio enrichment
│   │   ├── __init__.py
│   │   ├── multi_source_enricher.py    # Cascade: DDG → Wikipedia → ESPN → Grokepedia
│   │   └── duckduckgo_enricher.py      # DuckDuckGo search-based enrichment
│   │
│   └── wikipedia/
│       ├── __init__.py
│       └── bio_enricher.py             # Enrich player bios from Wikipedia
│
├── services/
│   ├── __init__.py
│   ├── player_service.py               # Business logic for players
│   ├── tournament_service.py           # Business logic for tournaments
│   ├── news_generator.py               # Generate news story snippets
│   └── notification_service.py         # Slack/email notifications
│
├── web/
│   ├── __init__.py
│   ├── app.py                          # Flask application factory
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── home.py                     # Home page routes
│   │   ├── players.py                  # Player-related routes
│   │   ├── tournaments.py              # Tournament-related routes
│   │   ├── search.py                   # Search functionality
│   │   └── api.py                      # JSON API endpoints
│   ├── templates/
│   │   ├── base.html                   # Base template with navigation
│   │   ├── home.html                   # Dashboard home page
│   │   ├── players/
│   │   │   ├── list.html               # List all players
│   │   │   ├── detail.html             # Player detail with tournament history
│   │   │   └── search.html             # Search players by high school, etc.
│   │   ├── tournaments/
│   │   │   ├── list.html               # List tournaments
│   │   │   ├── detail.html             # Tournament results
│   │   │   └── calendar.html           # Tournament calendar view
│   │   └── components/
│   │       ├── player_card.html        # Reusable player card
│   │       ├── result_table.html       # Reusable results table
│   │       └── pagination.html         # Pagination component
│   └── static/
│       ├── css/
│       │   └── styles.css              # Custom styles
│       └── js/
│           └── main.js                 # JavaScript functionality
│
├── cli/
│   ├── __init__.py
│   └── commands.py                     # CLI commands for running scrapers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Pytest fixtures
│   ├── test_scrapers/
│   │   ├── test_pga_tour_scraper.py
│   │   └── test_bio_enricher.py
│   ├── test_services/
│   │   ├── test_player_service.py
│   │   └── test_tournament_service.py
│   └── test_web/
│       └── test_routes.py
│
├── logs/                               # Log files (gitignored)
│   └── .gitkeep
│
├── docs/
│   ├── SETUP.md                        # Detailed setup instructions
│   ├── SCRAPING.md                     # How the scrapers work
│   ├── API.md                          # API documentation
│   └── CONTRIBUTING.md                 # Contribution guidelines
│
└── .github/
    └── workflows/
        ├── daily_scrape.yml            # Daily scraping workflow
        ├── test.yml                    # Run tests on PR
        └── deploy.yml                  # Deploy to Render
```

---

## Detailed Implementation Instructions

### Phase 1: Project Setup

#### Step 1.1: Initialize the Project
```bash
# Create project directory
mkdir golf-tracker
cd golf-tracker

# Initialize git
git init

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create requirements.txt
```

#### Step 1.2: Create requirements.txt
```
# Web Framework
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Jinja2==3.1.2

# Database
SQLAlchemy==2.0.23
PyMySQL==1.1.0
cryptography==41.0.7

# Scraping
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
selenium==4.15.2
webdriver-manager==4.0.1

# Data Processing
pandas==2.1.3
python-dateutil==2.8.2

# Configuration
python-dotenv==1.0.0
pyyaml==6.0.1

# Logging
loguru==0.7.2

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0
responses==0.24.1

# CLI
click==8.1.7

# Notifications (optional)
slack-sdk==3.23.0

# Utilities
tenacity==8.2.3
```

#### Step 1.3: Create .env.example
```bash
# Database Configuration
DATABASE_URL=mysql+pymysql://user:password@host:port/database_name
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=golf_tracker
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=golf_tracker

# Flask Configuration
FLASK_APP=web.app
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Scraping Configuration
SCRAPE_DELAY_SECONDS=2
USER_AGENT=GolfTracker/1.0 (Local News Research)

# Notification Configuration (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx
NOTIFICATION_EMAIL=your-email@example.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/golf_tracker.log
```

#### Step 1.4: Create .gitignore
```
# Virtual Environment
venv/
.venv/
env/

# Environment Variables
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/*.log
*.log

# Database
*.db
*.sqlite3

# Testing
.coverage
htmlcov/
.pytest_cache/

# OS
.DS_Store
Thumbs.db
```

---

### Phase 2: Database Layer

#### Step 2.1: Create config/settings.py
This file should:
- Load environment variables from .env file
- Provide configuration classes for different environments (dev, prod, test)
- Include extensive comments explaining each setting
- Handle default values gracefully

#### Step 2.2: Create database/connection.py
This file should:
- Create a DatabaseManager class that handles connections
- Support connection pooling
- Include retry logic for connection failures
- Log all connection events
- Provide context managers for transactions

#### Step 2.3: Create database/models.py
This file should:
- Use SQLAlchemy ORM to define all models matching the schema above
- Include relationship definitions between models
- Add helper methods for common queries
- Include docstrings for every class and method

---

### Phase 3: Scrapers

#### Step 3.1: Create scrapers/base_scraper.py
```python
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
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from loguru import logger
from datetime import datetime

from config.settings import Config
from database.connection import DatabaseManager
from database.models import ScrapeLog


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
        
        # Track the current scrape operation for logging
        self._current_scrape_log: Optional[ScrapeLog] = None
        
        # Logger for this specific scraper
        self.logger = logger.bind(scraper=self.__class__.__name__)
        
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
        """
        session = requests.Session()
        
        # Configure retry strategy
        # - total=3: Try up to 3 times
        # - backoff_factor=1: Wait 1, 2, 4 seconds between retries
        # - status_forcelist: Retry on these HTTP error codes
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Apply the retry strategy to the session
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set a user agent so websites know who we are
        session.headers.update({
            'User-Agent': self.user_agent
        })
        
        return session
    
    def get_page(self, url: str, params: Optional[Dict] = None) -> Optional[BeautifulSoup]:
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
            response = self.session.get(url, params=params, timeout=30)
            
            # Raise an exception if the request failed (4xx or 5xx status)
            response.raise_for_status()
            
            # Parse the HTML into a BeautifulSoup object
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Be polite: wait before making another request
            # This prevents us from overwhelming the website
            time.sleep(self.delay_seconds)
            
            return soup
            
        except requests.RequestException as e:
            # Log the error but don't crash
            self.logger.error(f"Failed to fetch {url}: {str(e)}")
            return None
    
    def start_scrape_log(self, scrape_type: str, source_url: str = None) -> ScrapeLog:
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
            The ScrapeLog object (which will be updated as we progress)
        """
        with self.db.get_session() as session:
            # Look up the league ID
            league = session.query(League).filter_by(league_code=self.league_code).first()
            
            # Create the log entry
            log = ScrapeLog(
                scrape_type=scrape_type,
                league_id=league.league_id if league else None,
                status='started',
                source_url=source_url,
                started_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
            
            self._current_scrape_log = log
            self.logger.info(f"Started {scrape_type} scrape for {self.league_code}")
            
            return log
    
    def complete_scrape_log(self, status: str, records_processed: int = 0,
                           records_created: int = 0, records_updated: int = 0,
                           error_message: str = None):
        """
        Mark a scrape operation as complete in the database.
        
        Args:
            status: Final status ('success', 'partial', 'failed')
            records_processed: Total records we looked at
            records_created: New records added to database
            records_updated: Existing records that were updated
            error_message: Error details if something went wrong
        """
        if not self._current_scrape_log:
            return
            
        with self.db.get_session() as session:
            log = session.query(ScrapeLog).get(self._current_scrape_log.log_id)
            if log:
                log.status = status
                log.records_processed = records_processed
                log.records_created = records_created
                log.records_updated = records_updated
                log.error_message = error_message
                log.completed_at = datetime.utcnow()
                
                # Calculate how long the scrape took
                if log.started_at:
                    duration = (log.completed_at - log.started_at).total_seconds()
                    log.duration_seconds = int(duration)
                
                session.commit()
                
        self.logger.info(
            f"Completed {self._current_scrape_log.scrape_type} scrape: "
            f"{status}, {records_processed} processed, "
            f"{records_created} created, {records_updated} updated"
        )
        self._current_scrape_log = None
    
    @abstractmethod
    def scrape(self) -> Dict[str, Any]:
        """
        Execute the scraping operation.
        
        This method MUST be implemented by every scraper class.
        It should:
        1. Fetch the necessary web pages
        2. Parse the data
        3. Save to the database
        4. Return a summary of what was done
        
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
```

#### Step 3.2: Create scrapers/pga_tour/roster_scraper.py
This file should:
- Inherit from BaseScraper
- Scrape the PGA Tour player roster page
- Extract player names, IDs, and basic info
- Save to the players and player_leagues tables
- Include extensive comments explaining the scraping logic
- Handle pagination if the roster spans multiple pages

#### Step 3.3: Create scrapers/pga_tour/tournament_scraper.py
This file should:
- Scrape the PGA Tour schedule page for tournament list
- Scrape individual tournament results pages
- Extract leaderboard data including round scores
- Save to tournaments and tournament_results tables
- Handle different tournament statuses (upcoming, in-progress, completed)

#### Step 3.4: Create scrapers/wikipedia/bio_enricher.py
This file should:
- Take a player name and search Wikipedia
- Extract high school, college, hometown information
- Parse infoboxes and biographical sections
- Update the players table with enriched data
- Handle cases where Wikipedia page doesn't exist

---

### Phase 4: Services Layer

#### Step 4.1: Create services/player_service.py
This file should provide methods for:
- Getting all players with filtering/pagination
- Getting player by ID with full details
- Searching players by high school, hometown, or college
- Getting player's tournament history for a given year

#### Step 4.2: Create services/tournament_service.py
This file should provide methods for:
- Getting all tournaments with filtering by league/year
- Getting tournament details with full results
- Getting upcoming tournaments
- Getting recent results

#### Step 4.3: Create services/news_generator.py
This file should:
- Generate news snippet text like "Scottie Scheffler, a 2014 graduate of Highland Park High School in Dallas, Texas..."
- Format tournament results for display
- Handle missing data gracefully (some players may not have high school info)

---

### Phase 5: Web Dashboard

#### Step 5.1: Create web/app.py (Flask Application Factory)
```python
"""
Flask Application Factory
=========================

This module creates and configures the Flask web application.

For Junior Developers:
---------------------
The "application factory" pattern means we have a function that creates
the Flask app, rather than creating it at module level. This makes testing
easier and allows us to create multiple instances with different configs.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config.settings import Config

# Create SQLAlchemy instance (but don't initialize yet)
db = SQLAlchemy()


def create_app(config_class=Config):
    """
    Create and configure the Flask application.
    
    Args:
        config_class: Configuration class to use (allows different configs for testing)
        
    Returns:
        Configured Flask application
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints (groups of routes)
    from web.routes.home import home_bp
    from web.routes.players import players_bp
    from web.routes.tournaments import tournaments_bp
    from web.routes.api import api_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(players_bp, url_prefix='/players')
    app.register_blueprint(tournaments_bp, url_prefix='/tournaments')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
```

#### Step 5.2: Create web/routes/players.py
Routes to implement:
- `GET /players` - List all players (paginated, filterable)
- `GET /players/<id>` - Player detail page with tournament history
- `GET /players/search` - Search page with filters for high school, hometown, college
- `GET /players/by-school/<school_name>` - Players from a specific high school

#### Step 5.3: Create web/routes/tournaments.py
Routes to implement:
- `GET /tournaments` - List tournaments (filterable by league, year)
- `GET /tournaments/<id>` - Tournament detail with full results
- `GET /tournaments/calendar` - Calendar view of tournaments
- `GET /tournaments/recent` - Recent results

#### Step 5.4: Create web/templates/base.html
The base template should:
- Include Bootstrap 5 for styling (via CDN)
- Have a navigation bar with links to main sections
- Include a search box in the header
- Use Jinja2 blocks for content, title, and extra JS/CSS

#### Step 5.5: Create web/templates/players/detail.html
The player detail page should show:
- Player photo and basic info
- HIGH SCHOOL, graduation year, city/state (prominently displayed)
- Hometown
- College
- Tournament history for selected year with scores
- Pre-formatted news snippet text that can be copied

#### Step 5.6: Create web/templates/tournaments/detail.html
The tournament detail page should show:
- Tournament name, dates, location
- Course information
- Full leaderboard with:
  - Position
  - Player name (linked to player detail)
  - Player's high school (for local news angle)
  - Round scores
  - Total score and to-par
  - Earnings

---

### Phase 6: CLI Commands

#### Step 6.1: Create cli/commands.py
```python
"""
CLI Commands for Golf Tracker
=============================

This module provides command-line interface commands for running scrapers
and managing the golf tracker system.

Usage:
    python -m cli.commands scrape --league PGA --type roster
    python -m cli.commands scrape --league PGA --type tournaments
    python -m cli.commands enrich-bios --limit 100

For Junior Developers:
---------------------
Click is a library that makes it easy to create command-line tools.
The @click.command() decorator turns a function into a CLI command.
The @click.option() decorator adds command-line flags/arguments.
"""

import click
from loguru import logger

# Import all scrapers
from scrapers.pga_tour.roster_scraper import PGATourRosterScraper
from scrapers.pga_tour.tournament_scraper import PGATourTournamentScraper
from scrapers.wikipedia.bio_enricher import WikipediaBioEnricher

# Map league codes to their scraper classes
ROSTER_SCRAPERS = {
    'PGA': PGATourRosterScraper,
    # Add more leagues here as they're implemented
    # 'DPWORLD': DPWorldTourRosterScraper,
    # 'KORNFERRY': KornFerryRosterScraper,
}

TOURNAMENT_SCRAPERS = {
    'PGA': PGATourTournamentScraper,
    # Add more leagues here
}


@click.group()
def cli():
    """Golf Tracker CLI - Manage golf data scraping and database."""
    pass


@cli.command()
@click.option('--league', required=True, help='League code (PGA, DPWORLD, KORNFERRY, etc.)')
@click.option('--type', 'scrape_type', required=True, 
              type=click.Choice(['roster', 'tournaments', 'results']),
              help='Type of data to scrape')
@click.option('--year', default=None, type=int, help='Year for tournament data')
def scrape(league: str, scrape_type: str, year: int):
    """
    Run a scraper for the specified league and data type.
    
    Examples:
        python -m cli.commands scrape --league PGA --type roster
        python -m cli.commands scrape --league PGA --type tournaments --year 2025
    """
    league = league.upper()
    
    logger.info(f"Starting {scrape_type} scrape for {league}")
    
    try:
        if scrape_type == 'roster':
            if league not in ROSTER_SCRAPERS:
                raise click.ClickException(f"No roster scraper available for {league}")
            
            scraper = ROSTER_SCRAPERS[league]()
            result = scraper.scrape()
            
        elif scrape_type in ['tournaments', 'results']:
            if league not in TOURNAMENT_SCRAPERS:
                raise click.ClickException(f"No tournament scraper available for {league}")
            
            scraper = TOURNAMENT_SCRAPERS[league]()
            result = scraper.scrape(year=year)
        
        # Print results
        click.echo(f"\nScrape Complete!")
        click.echo(f"  Status: {result.get('status')}")
        click.echo(f"  Records Processed: {result.get('records_processed', 0)}")
        click.echo(f"  Records Created: {result.get('records_created', 0)}")
        click.echo(f"  Records Updated: {result.get('records_updated', 0)}")
        
        if result.get('errors'):
            click.echo(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors'][:5]:  # Show first 5 errors
                click.echo(f"  - {error}")
                
    except Exception as e:
        logger.error(f"Scrape failed: {str(e)}")
        raise click.ClickException(str(e))


@cli.command()
@click.option('--limit', default=50, help='Maximum number of players to enrich')
@click.option('--force', is_flag=True, help='Re-enrich even if bio data exists')
def enrich_bios(limit: int, force: bool):
    """
    Enrich player biographical data from Wikipedia.
    
    This command finds players missing high school/college info and
    attempts to fill it in from Wikipedia.
    
    Examples:
        python -m cli.commands enrich-bios --limit 100
        python -m cli.commands enrich-bios --force
    """
    logger.info(f"Starting bio enrichment (limit: {limit}, force: {force})")
    
    try:
        enricher = WikipediaBioEnricher()
        result = enricher.enrich_missing_bios(limit=limit, force=force)
        
        click.echo(f"\nBio Enrichment Complete!")
        click.echo(f"  Players Processed: {result.get('processed', 0)}")
        click.echo(f"  Successfully Enriched: {result.get('enriched', 0)}")
        click.echo(f"  No Wikipedia Page Found: {result.get('not_found', 0)}")
        
    except Exception as e:
        logger.error(f"Bio enrichment failed: {str(e)}")
        raise click.ClickException(str(e))


@cli.command()
def init_db():
    """
    Initialize the database with tables and seed data.
    
    This command creates all tables and inserts the initial league data.
    """
    from database.connection import DatabaseManager
    
    logger.info("Initializing database...")
    
    try:
        db = DatabaseManager()
        db.create_all_tables()
        db.seed_leagues()
        
        click.echo("Database initialized successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise click.ClickException(str(e))


if __name__ == '__main__':
    cli()
```

---

### Phase 7: Testing

#### Step 7.1: Create tests/conftest.py
This file should:
- Set up pytest fixtures for database connections
- Create a test database (SQLite in-memory for speed)
- Provide sample data fixtures
- Configure mocking for HTTP requests

#### Step 7.2: Create tests/test_scrapers/test_pga_tour_scraper.py
Tests to include:
- Test parsing of sample HTML
- Test handling of missing data
- Test database saving
- Test error handling

#### Step 7.3: Create tests/test_services/test_player_service.py
Tests to include:
- Test player search by high school
- Test player detail retrieval
- Test tournament history retrieval

---

### Phase 8: Deployment and Automation

#### Step 8.1: Create Dockerfile
```dockerfile
# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "web.app:create_app()"]
```

#### Step 8.2: Create docker-compose.yml (for local development)
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=mysql+pymysql://golf:golf@db:3306/golf_tracker
    depends_on:
      - db
    volumes:
      - .:/app

  db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=rootpassword
      - MYSQL_DATABASE=golf_tracker
      - MYSQL_USER=golf
      - MYSQL_PASSWORD=golf
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

#### Step 8.3: Create render.yaml
```yaml
services:
  - type: web
    name: golf-tracker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn web.app:create_app()
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: golf-tracker-db
          property: connectionString
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true

databases:
  - name: golf-tracker-db
    databaseName: golf_tracker
    user: golf_user
    plan: starter
```

#### Step 8.4: Create .github/workflows/daily_scrape.yml

The workflow runs **3 times daily** to capture live tournament scores:
- 6 AM UTC (1 AM EST) - Morning scores
- 2 PM UTC (9 AM EST) - Early round updates
- 10 PM UTC (5 PM EST) - Late round updates

```yaml
name: Daily Golf Data Scrape

on:
  schedule:
    # Run 3 times daily for live tournament updates
    - cron: '0 6 * * *'   # 1 AM EST
    - cron: '0 14 * * *'  # 9 AM EST
    - cron: '0 22 * * *'  # 5 PM EST
  workflow_dispatch:  # Allow manual triggers
    inputs:
      year:
        description: 'Year to scrape (default: current year)'
        required: false
        type: string

jobs:
  scrape-all-leagues:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # Scrape all leagues at once (PGA, Korn Ferry, Champions, LPGA)
      - name: Scrape all leagues
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python -m cli.commands scrape-all

      - name: Enrich player bios from Wikipedia
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python -m cli.commands enrich-bios --limit 100

      - name: Show database statistics
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python -m cli.commands stats
        continue-on-error: true

      - name: Notify on failure
        if: failure()
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: |
          if [ -n "$SLACK_WEBHOOK_URL" ]; then
            curl -X POST -H 'Content-type: application/json' \
              --data '{"text":"⚠️ Golf Tracker daily scrape failed!"}' \
              $SLACK_WEBHOOK_URL
          fi
```

---

### Phase 9: Documentation

#### Step 9.1: Create README.md
The README should include:
- Project overview and purpose
- Quick start guide
- Screenshots of the web dashboard
- How to add a new league
- Troubleshooting common issues

#### Step 9.2: Create docs/SETUP.md
Detailed setup instructions including:
- Prerequisites (Python, MySQL, etc.)
- Local development setup
- Render deployment steps
- GitHub Actions configuration
- Environment variable reference

#### Step 9.3: Create docs/SCRAPING.md
Documentation explaining:
- How each scraper works
- Data sources for each league
- How to add a new league scraper
- Rate limiting and being a good citizen
- Troubleshooting scraping issues

---

## Additional Notes for Claude Code

### Important Implementation Details

1. **Be Extremely Verbose with Comments**
   - Every function needs a docstring
   - Complex logic needs inline comments
   - Add "For Junior Developers" sections explaining concepts
   - Include examples in docstrings

2. **Error Handling**
   - Never let exceptions crash the program
   - Log all errors with full context
   - Provide meaningful error messages
   - Use try/except with specific exception types

3. **Logging**
   - Use loguru for all logging
   - Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
   - Include context in log messages
   - Write logs to both console and file

4. **Data Sources Priority**
   For player biographical information:
   1. First try the official tour website (pgatour.com)
   2. Then try Wikipedia
   3. Then try ESPN
   4. Store the source of each piece of data

5. **Respect Rate Limits**
   - Wait 2 seconds between requests by default
   - Use exponential backoff on failures
   - Set a reasonable User-Agent header
   - Don't scrape more than necessary

6. **Database Best Practices**
   - Always use parameterized queries (SQLAlchemy handles this)
   - Use transactions for multiple related inserts
   - Add indexes for commonly queried columns
   - Use UPSERT patterns to handle duplicate data

### League-Specific Notes

**PGA Tour** ✅ IMPLEMENTED
- **API**: PGA Tour GraphQL API (`orchestrator.pgatour.com/graphql`)
- **Tour Code**: `R`
- **Features**: Live scores, round-by-round data, player directory
- **Player ID field**: `pga_tour_id`
- **Tournament ID field**: `pga_tour_tournament_id`

**Korn Ferry Tour** ✅ IMPLEMENTED
- **API**: PGA Tour GraphQL API (same as PGA Tour)
- **Tour Code**: `H`
- **Features**: Live scores, round-by-round data
- **Player ID field**: `korn_ferry_id`
- **Tournament ID field**: `korn_ferry_tournament_id`

**PGA Tour Champions** ✅ IMPLEMENTED
- **API**: PGA Tour GraphQL API (same as PGA Tour)
- **Tour Code**: `S`
- **Features**: Live scores, round-by-round data (typically 3 rounds)
- **Player ID field**: `champions_id`
- **Tournament ID field**: `champions_tournament_id`

**LPGA** ✅ IMPLEMENTED
- **API**: ESPN API (`site.web.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard`)
- **Features**: Live scores, round-by-round data via `linescores`
- **Player ID field**: `lpga_id`
- **Tournament ID field**: `lpga_tournament_id`

**NCAA College Golf** 🚧 IN PROGRESS
- **Data Source**: Golfstat (`www.golfstat.com/public/scoreboard`)
- **Divisions**: D1 Men's, D1 Women's, D2 Men's, D2 Women's, D3 Men's, D3 Women's
- **Features**: Live tournament scores, individual results
- **Note**: High hit rate for US high school data since most college golfers are American
- **Player ID field**: `college_id` (planned)
- **Tournament ID field**: `college_tournament_id` (planned)

**DP World Tour** ✅ IMPLEMENTED
- **API**: ESPN API (`site.web.api.espn.com/apis/site/v2/sports/golf/eur/scoreboard`)
- **Features**: Live scores, round-by-round data, player profiles
- **Player ID field**: `dp_world_id`
- **Tournament ID field**: `dp_world_tournament_id`
- **Note**: Formerly European Tour, now DP World Tour

**LIV Golf** ✅ IMPLEMENTED
- **API**: No public API available - uses hardcoded schedule data
- **Features**: Tournament schedule, player roster (known LIV players)
- **Player ID field**: `liv_id`
- **Tournament ID field**: `liv_tournament_id`
- **Note**: 54-hole (3 round) format, team-based structure

**PGA Tour Americas** 🚧 IN PROGRESS
- **API**: PGA Tour GraphQL API (same as PGA Tour)
- **Tour Code**: `Y`
- **Features**: Live scores, round-by-round data
- **Player ID field**: `pga_americas_id`
- **Tournament ID field**: `pga_americas_tournament_id`
- **Note**: Formed in 2024 from merger of PGA Tour Canada and PGA Tour Latinoamerica

**USGA Amateur Events** ❌ PLANNED
- **Potential Sources**: USGA, AmateurGolf.com, AJGA (American Junior Golf Association)
- **Events**: U.S. Amateur, U.S. Women's Amateur, U.S. Junior Amateur, etc.
- **Features**: Tournament results, player profiles with high school info
- **Note**: Excellent for local news since amateur golfers are typically local

---

## Success Criteria

The project is complete when:

1. ✅ Database is set up on Render with all tables
2. ✅ PGA Tour roster scraper works and populates players table
3. ✅ PGA Tour tournament scraper works and populates tournaments/results
4. ✅ Wikipedia bio enricher fills in high school/college data
5. ✅ Web dashboard shows player list with search/filter
6. ✅ Player detail page shows tournament history with news snippet
7. ✅ Tournament detail page shows full results with player info
8. ✅ GitHub Actions runs daily scrapes automatically
9. ✅ Slack notifications alert on failures
10. ✅ All code has extensive comments
11. ✅ Unit tests cover core functionality
12. ✅ Documentation is complete

---

## Sample Queries for Testing

```sql
-- Find all players from Texas high schools
SELECT full_name, high_school_name, high_school_city, high_school_graduation_year
FROM players
WHERE high_school_state = 'Texas'
ORDER BY high_school_graduation_year DESC;

-- Get Scottie Scheffler's 2025 tournament results
SELECT 
    t.tournament_name,
    t.start_date,
    tr.final_position_display,
    tr.total_to_par,
    tr.round_1_score, tr.round_2_score, tr.round_3_score, tr.round_4_score,
    tr.earnings
FROM tournament_results tr
JOIN tournaments t ON tr.tournament_id = t.tournament_id
JOIN players p ON tr.player_id = p.player_id
WHERE p.full_name = 'Scottie Scheffler'
  AND t.tournament_year = 2025
ORDER BY t.start_date;

-- Find all players who went to University of Texas
SELECT full_name, high_school_name, hometown_city, hometown_state
FROM players
WHERE college_name LIKE '%Texas%'
ORDER BY last_name;

-- Get leaderboard for a tournament with local news info
SELECT 
    tr.final_position_display AS pos,
    p.full_name,
    CONCAT('a ', p.high_school_graduation_year, ' graduate of ', p.high_school_name) AS local_angle,
    tr.total_to_par,
    tr.earnings
FROM tournament_results tr
JOIN players p ON tr.player_id = p.player_id
WHERE tr.tournament_id = 1
ORDER BY tr.final_position;
```

---

## Getting Started Command

To start building this project with Claude Code, use:

```
Build the golf-tracker project following the GOLF_TRACKER_PROJECT.md specification. Start with Phase 1 (project setup) and work through each phase in order. Create all files with extensive comments suitable for a junior developer. Test each component before moving to the next phase.
```

---

## ADDING A NEW LEAGUE - Quick Reference

### Currently Implemented Leagues

| League | Code | API | Tour Code | Live Scores | Round Scores |
|--------|------|-----|-----------|-------------|--------------|
| PGA Tour | `PGA` | PGA GraphQL | `R` | ✅ | ✅ |
| Korn Ferry Tour | `KORNFERRY` | PGA GraphQL | `H` | ✅ | ✅ |
| PGA Tour Champions | `CHAMPIONS` | PGA GraphQL | `S` | ✅ | ✅ |
| LPGA Tour | `LPGA` | ESPN API | N/A | ✅ | ✅ |
| DP World Tour | `DPWORLD` | ESPN API | N/A | ✅ | ✅ |
| LIV Golf | `LIV` | Hardcoded | N/A | ⚠️ | ✅ |
| PGA Tour Americas | `PGAAMERICAS` | PGA GraphQL | `Y` | 🚧 | 🚧 |

### API Details

#### PGA Tour GraphQL API (PGA, Korn Ferry, Champions)
```
Endpoint: https://orchestrator.pgatour.com/graphql
API Key: da2-gsrx5bibzbb4njvhl7t37wqyl4

Required Headers:
  Content-Type: application/json
  Accept: application/json
  x-api-key: da2-gsrx5bibzbb4njvhl7t37wqyl4
  Origin: https://www.pgatour.com
  Referer: https://www.pgatour.com/

Tour Codes:
  R = PGA Tour
  H = Korn Ferry Tour
  S = PGA Tour Champions
  Y = PGA Tour Americas
  C = PGA Tour Canada
```

#### ESPN API (LPGA, DP World Tour)
```
LPGA Scoreboard: https://site.web.api.espn.com/apis/site/v2/sports/golf/lpga/scoreboard
LPGA Athletes: https://sports.core.api.espn.com/v2/sports/golf/leagues/lpga/athletes

DP World Scoreboard: https://site.web.api.espn.com/apis/site/v2/sports/golf/eur/scoreboard
DP World Athletes: https://sports.core.api.espn.com/v2/sports/golf/leagues/eur/athletes

No authentication required.
```

#### Bio Enrichment Sources (Multi-Source Cascade)
```
The bio enrichment system tries multiple sources in order until data is found:

1. DuckDuckGo Search (first, most effective)
   - URL: https://html.duckduckgo.com/html/
   - Searches: "{player name} high school golf", "{player name} hometown"
   - Rate limited: 2 seconds between requests
   - No API key required

2. Wikipedia
   - URL: https://en.wikipedia.org/wiki/{player_name}
   - Parses infobox for biographical data

3. ESPN Player Pages
   - URL: https://www.espn.com/golf/player/_/id/{espn_id}
   - Parses player profile section

4. Grokepedia (fallback)
   - AI-powered Wikipedia alternative
```

### How to Add a New League

**Step 1: Create Database Migration** (`database/migrations/003_add_new_league.sql`)
```sql
-- Add player ID column
ALTER TABLE players ADD COLUMN IF NOT EXISTS new_league_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_new_league_id ON players(new_league_id);

-- Add tournament ID column
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS new_league_tournament_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_new_league_tournament_id ON tournaments(new_league_tournament_id);
```

**Step 2: Add to Database Models** (`database/models.py`)
```python
# Add new ID column to Player model
new_league_id = Column(String(50), index=True)

# Add new tournament ID column to Tournament model
new_league_tournament_id = Column(String(50))
```

**Step 3: Add to Migration Runner** (`run_scrape.py` and `run_migration.py`)
```python
migrations = [
    # ... existing migrations ...
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS new_league_id VARCHAR(50)",
    "CREATE INDEX IF NOT EXISTS idx_new_league_id ON players(new_league_id)",
    "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS new_league_tournament_id VARCHAR(50)",
    "CREATE INDEX IF NOT EXISTS idx_new_league_tournament_id ON tournaments(new_league_tournament_id)",
]
```

**Step 2: Add to League Config** (`config/leagues.py`)
```python
LEAGUE_CONFIGS = {
    'NEW_LEAGUE': {
        'name': 'New League Name',
        'base_url': 'https://www.newleague.com',
        'urls': {
            'roster': 'https://...',
            'schedule': 'https://...',
        }
    }
}
```

**Step 3: Create Scraper Files**

For PGA-ecosystem tours (using PGA GraphQL API):
```
scrapers/new_league/
├── __init__.py
├── roster_scraper.py      # Inherit from BasePGAEcosystemScraper
└── tournament_scraper.py  # Inherit from BasePGAEcosystemScraper
```

Example roster scraper:
```python
from scrapers.pga_tour.base_pga_scraper import BasePGAEcosystemScraper
from database.models import Player, PlayerLeague, League

class NewLeagueRosterScraper(BasePGAEcosystemScraper):
    league_code = 'NEW_LEAGUE'
    tour_code = 'X'  # Get from PGA API
    scrape_type = 'roster'

    def scrape(self, **kwargs):
        players_data = self.fetch_players()
        # Process and save players
        ...
```

For ESPN-based leagues:
```python
from scrapers.base_scraper import BaseScraper

class NewLeagueScraper(BaseScraper):
    espn_api = 'https://sports.core.api.espn.com/v2/sports/golf/leagues/xxx'

    def _fetch_players(self):
        data = self.get_json(f'{self.espn_api}/athletes')
        ...
```

**Step 4: Register in CLI Commands** (`cli/commands.py`)

Add to the `scrape` command:
```python
elif league == 'NEW_LEAGUE':
    from scrapers.new_league.roster_scraper import NewLeagueRosterScraper
    scraper = NewLeagueRosterScraper()
```

Add to `scrape-all` command:
```python
leagues = [
    ('PGA', 'PGA Tour'),
    ('KORNFERRY', 'Korn Ferry Tour'),
    ('CHAMPIONS', 'PGA Tour Champions'),
    ('LPGA', 'LPGA Tour'),
    ('NEW_LEAGUE', 'New League Name'),  # Add here
]
```

**Step 5: Add to GitHub Actions** (`.github/workflows/daily_scrape.yml`)

The `scrape-all` command automatically picks up leagues from `cli/commands.py`.
For manual triggers, add a new job if needed.

**Step 6: Seed the League** (`database/seeds/seed_leagues.sql`)
```sql
INSERT INTO leagues (league_code, league_name, website_url, is_active)
VALUES ('NEW_LEAGUE', 'New League Name', 'https://...', TRUE);
```

### Key GraphQL Queries

**Player Directory:**
```graphql
query {
    playerDirectory(tourCode: R) {
        players {
            id
            firstName
            lastName
            country
            isActive
        }
    }
}
```

**Tournament Schedule:**
```graphql
query {
    schedule(tourCode: "R", year: "2026") {
        completed { month tournaments { id tournamentName startDate } }
        upcoming { month tournaments { id tournamentName startDate } }
    }
}
```

**Live Leaderboard (with round scores):**
```graphql
query Leaderboard($id: ID!) {
    leaderboardV2(id: $id) {
        id
        tournamentStatus
        players {
            ... on PlayerRowV2 {
                position
                total
                totalStrokes
                rounds          # ['68', '65', '70', '-']
                player { id firstName lastName country }
            }
        }
    }
}
```

### Daily Scrape Schedule

The GitHub Actions workflow runs 3 times daily:
- **6 AM UTC** (1 AM EST) - Morning scores
- **2 PM UTC** (9 AM EST) - Early round updates
- **10 PM UTC** (5 PM EST) - Late round updates

This captures live tournament scores throughout the day for writing stories like:
> "Justin Rose shot a 68 on Saturday and is 21-under for the tournament, in 1st place."

### Testing a New League

```bash
# Test roster scrape
python -m cli.commands scrape --league NEW_LEAGUE --type roster

# Test tournament scrape
python -m cli.commands scrape --league NEW_LEAGUE --type tournaments --year 2026

# Run all leagues
python -m cli.commands scrape-all

# Check database stats
python -m cli.commands stats
```

### Prompt to Give Claude for Adding a League

```
I need to add [LEAGUE NAME] to the golf tracker.

Please:
1. Find the API/data source for this league
2. Create roster_scraper.py and tournament_scraper.py in scrapers/[league_name]/
3. Add the league to cli/commands.py (both scrape and scrape-all commands)
4. Test the scrapers work with live data
5. Ensure round-by-round scores are captured for live tournaments

The project is at C:\Users\cashk\OneDrive\Projects\golf\golf-tracker
Follow the patterns in the existing scrapers (PGA uses GraphQL, LPGA uses ESPN API).
```
