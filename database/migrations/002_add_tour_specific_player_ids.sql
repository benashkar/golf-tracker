-- ==============================================================================
-- Golf Tracker Database - Add Tour-Specific Player IDs
-- ==============================================================================
-- This migration adds tour-specific ID columns to the players table
-- to support matching players across Korn Ferry, Champions, and LPGA tours.
--
-- PostgreSQL syntax for Render deployment.
--
-- To run this migration:
--   psql $DATABASE_URL -f 002_add_tour_specific_player_ids.sql
-- ==============================================================================

-- Add Korn Ferry Tour player ID
ALTER TABLE players
ADD COLUMN IF NOT EXISTS korn_ferry_id VARCHAR(50);

-- Add PGA Tour Champions player ID
ALTER TABLE players
ADD COLUMN IF NOT EXISTS champions_id VARCHAR(50);

-- Add LPGA Tour player ID
ALTER TABLE players
ADD COLUMN IF NOT EXISTS lpga_id VARCHAR(50);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_korn_ferry_id ON players(korn_ferry_id);
CREATE INDEX IF NOT EXISTS idx_champions_id ON players(champions_id);
CREATE INDEX IF NOT EXISTS idx_lpga_id ON players(lpga_id);

-- Also add missing tournament ID columns for each tour
ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS korn_ferry_tournament_id VARCHAR(50);

ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS champions_tournament_id VARCHAR(50);

ALTER TABLE tournaments
ADD COLUMN IF NOT EXISTS lpga_tournament_id VARCHAR(50);

-- Indexes for tournament lookups
CREATE INDEX IF NOT EXISTS idx_korn_ferry_tournament_id ON tournaments(korn_ferry_tournament_id);
CREATE INDEX IF NOT EXISTS idx_champions_tournament_id ON tournaments(champions_tournament_id);
CREATE INDEX IF NOT EXISTS idx_lpga_tournament_id ON tournaments(lpga_tournament_id);
