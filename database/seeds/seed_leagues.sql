-- ==============================================================================
-- Golf Tracker Database - Seed Data for Leagues
-- ==============================================================================
-- This file inserts the initial league data.
-- Run after the schema migration.
--
-- To run:
--   mysql -u username -p database_name < seed_leagues.sql
-- ==============================================================================

-- Insert all golf leagues we're tracking
INSERT INTO leagues (league_code, league_name, website_url, is_active)
VALUES
    ('PGA', 'PGA Tour', 'https://www.pgatour.com', TRUE),
    ('DPWORLD', 'DP World Tour', 'https://www.europeantour.com', TRUE),
    ('KORNFERRY', 'Korn Ferry Tour', 'https://www.pgatour.com/korn-ferry-tour', TRUE),
    ('LPGA', 'LPGA Tour', 'https://www.lpga.com', TRUE),
    ('LIV', 'LIV Golf', 'https://www.livgolf.com', TRUE),
    ('CHAMPIONS', 'PGA Tour Champions', 'https://www.pgatour.com/champions', TRUE)
ON DUPLICATE KEY UPDATE
    league_name = VALUES(league_name),
    website_url = VALUES(website_url),
    is_active = VALUES(is_active);

-- Verify the insert
SELECT * FROM leagues;
