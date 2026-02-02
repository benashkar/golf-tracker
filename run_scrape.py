#!/usr/bin/env python3
"""
Scrape Runner with Auto-Migration
==================================

Runs database migrations before executing the scrape-all command.
Use this as the cron job start command:
    python run_scrape.py --year 2026

This ensures the database schema is always up to date before scraping.
"""

import os
import sys
import argparse

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_migrations():
    """Apply any pending database migrations."""
    from sqlalchemy import text
    from database.connection import DatabaseManager

    db = DatabaseManager()

    migrations = [
        # Player ID columns
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS korn_ferry_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS champions_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS lpga_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS dpworld_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS liv_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS pga_americas_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS usga_id VARCHAR(50)",

        # Player ID indexes
        "CREATE INDEX IF NOT EXISTS idx_korn_ferry_id ON players(korn_ferry_id)",
        "CREATE INDEX IF NOT EXISTS idx_champions_id ON players(champions_id)",
        "CREATE INDEX IF NOT EXISTS idx_lpga_id ON players(lpga_id)",
        "CREATE INDEX IF NOT EXISTS idx_dpworld_id ON players(dpworld_id)",
        "CREATE INDEX IF NOT EXISTS idx_liv_id ON players(liv_id)",
        "CREATE INDEX IF NOT EXISTS idx_pga_americas_id ON players(pga_americas_id)",
        "CREATE INDEX IF NOT EXISTS idx_usga_id ON players(usga_id)",

        # Tournament ID columns
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS korn_ferry_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS champions_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS lpga_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS dpworld_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS liv_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS pga_americas_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS usga_tournament_id VARCHAR(50)",

        # Tournament ID indexes
        "CREATE INDEX IF NOT EXISTS idx_korn_ferry_tournament_id ON tournaments(korn_ferry_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_champions_tournament_id ON tournaments(champions_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_lpga_tournament_id ON tournaments(lpga_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_dpworld_tournament_id ON tournaments(dpworld_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_liv_tournament_id ON tournaments(liv_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_pga_americas_tournament_id ON tournaments(pga_americas_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_usga_tournament_id ON tournaments(usga_tournament_id)",

        # Bio source tracking columns
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS bio_source_url VARCHAR(500)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS bio_source_name VARCHAR(50)",
    ]

    print("Checking database schema...")

    with db.get_session() as session:
        for sql in migrations:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception as e:
                # Ignore "already exists" errors
                session.rollback()

    print("Database schema up to date.")


def run_scrape(year: int, include_college: bool = False, include_amateur: bool = False):
    """Run the scrape-all command."""
    from click.testing import CliRunner
    from cli.commands import cli

    runner = CliRunner()

    # Build command arguments
    args = ['scrape-all', '--year', str(year)]
    if include_college:
        args.append('--include-college')
    if include_amateur:
        args.append('--include-amateur')

    # Invoke the CLI command
    result = runner.invoke(cli, args)

    # Print output
    print(result.output)

    if result.exit_code != 0:
        print(f"Scrape failed with exit code {result.exit_code}")
        if result.exception:
            raise result.exception


def main():
    parser = argparse.ArgumentParser(description='Run golf tracker scrape with auto-migration')
    parser.add_argument('--year', type=int, default=2026, help='Year to scrape')
    parser.add_argument('--include-college', action='store_true', help='Include NCAA college golf')
    parser.add_argument('--include-amateur', action='store_true', help='Include amateur golf (AJGA)')
    args = parser.parse_args()

    print(f"Golf Tracker Scrape - Year {args.year}")
    print("=" * 40)

    # Run migrations first
    run_migrations()

    # Then run the scrape
    run_scrape(args.year, args.include_college, args.include_amateur)


if __name__ == "__main__":
    main()
