-- ==============================================================================
-- Golf Tracker Database - Initial Schema
-- ==============================================================================
-- This migration creates all the tables needed for the Golf Tracker application.
--
-- To run this migration:
--   mysql -u username -p database_name < 001_initial_schema.sql
--
-- For Junior Developers:
-- ----------------------
-- This file contains raw SQL to create our database structure.
-- While SQLAlchemy can create tables automatically, having SQL migrations
-- gives us more control and is the standard practice in production.
-- ==============================================================================

-- ============================================================
-- LEAGUES TABLE
-- Stores information about each golf league/tour
-- ============================================================
CREATE TABLE IF NOT EXISTS leagues (
    league_id INT AUTO_INCREMENT PRIMARY KEY,
    league_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g., 'PGA', 'DPWORLD', 'KORNFERRY'
    league_name VARCHAR(100) NOT NULL,        -- e.g., 'PGA Tour', 'DP World Tour'
    website_url VARCHAR(255),                 -- Official website for scraping
    is_active BOOLEAN DEFAULT TRUE,           -- Whether we're actively tracking this league
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_league_code (league_code),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- PLAYERS TABLE
-- Core player information - biographical data
-- ============================================================
CREATE TABLE IF NOT EXISTS players (
    player_id INT AUTO_INCREMENT PRIMARY KEY,

    -- Basic Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

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

    -- External IDs for data matching
    pga_tour_id VARCHAR(50),                  -- ID used on pgatour.com
    espn_id VARCHAR(50),
    wikipedia_url VARCHAR(500),

    -- Profile
    profile_image_url VARCHAR(500),

    -- Metadata
    bio_last_updated TIMESTAMP,               -- When we last scraped bio info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes for common queries
    INDEX idx_last_name (last_name),
    INDEX idx_high_school (high_school_name, high_school_state),
    INDEX idx_hometown (hometown_city, hometown_state),
    INDEX idx_college (college_name),
    INDEX idx_pga_tour_id (pga_tour_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- PLAYER_LEAGUES TABLE
-- Many-to-many relationship: players can be in multiple leagues
-- ============================================================
CREATE TABLE IF NOT EXISTS player_leagues (
    player_league_id INT AUTO_INCREMENT PRIMARY KEY,
    player_id INT NOT NULL,
    league_id INT NOT NULL,
    league_player_id VARCHAR(50),             -- Player's ID within that league
    is_current_member BOOLEAN DEFAULT TRUE,   -- Currently active in this league
    joined_date DATE,

    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
    FOREIGN KEY (league_id) REFERENCES leagues(league_id) ON DELETE CASCADE,
    UNIQUE KEY unique_player_league (player_id, league_id),

    INDEX idx_player_id (player_id),
    INDEX idx_league_id (league_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TOURNAMENTS TABLE
-- Information about each tournament/event
-- ============================================================
CREATE TABLE IF NOT EXISTS tournaments (
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

    -- External IDs
    pga_tour_tournament_id VARCHAR(50),
    espn_tournament_id VARCHAR(50),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    UNIQUE KEY unique_tournament (league_id, tournament_name, tournament_year),

    INDEX idx_dates (start_date, end_date),
    INDEX idx_year_league (tournament_year, league_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TOURNAMENT_RESULTS TABLE
-- Final results for each player in a tournament
-- ============================================================
CREATE TABLE IF NOT EXISTS tournament_results (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- SCRAPE_LOG TABLE
-- Track all scraping operations for debugging and monitoring
-- ============================================================
CREATE TABLE IF NOT EXISTS scrape_logs (
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
    completed_at TIMESTAMP NULL,
    duration_seconds INT,

    -- Source info
    source_url VARCHAR(500),

    FOREIGN KEY (league_id) REFERENCES leagues(league_id) ON DELETE SET NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE SET NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE SET NULL,

    INDEX idx_scrape_date (started_at),
    INDEX idx_status (status),
    INDEX idx_scrape_type (scrape_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================

-- View: Player with full location info for news stories
CREATE OR REPLACE VIEW v_player_news_info AS
SELECT
    p.player_id,
    CONCAT(p.first_name, ' ', p.last_name) AS full_name,
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
FROM players p
WHERE p.high_school_name IS NOT NULL;

-- View: Tournament results with player info for news
CREATE OR REPLACE VIEW v_tournament_results_for_news AS
SELECT
    t.tournament_name,
    t.tournament_year,
    t.start_date,
    t.end_date,
    t.course_name,
    t.city AS tournament_city,
    t.state AS tournament_state,
    l.league_name,
    CONCAT(p.first_name, ' ', p.last_name) AS player_name,
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
