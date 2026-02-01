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
    from database.connection import DatabaseConnection

    db = DatabaseConnection()

    migrations = [
        # Player ID columns
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS korn_ferry_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS champions_id VARCHAR(50)",
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS lpga_id VARCHAR(50)",

        # Player ID indexes
        "CREATE INDEX IF NOT EXISTS idx_korn_ferry_id ON players(korn_ferry_id)",
        "CREATE INDEX IF NOT EXISTS idx_champions_id ON players(champions_id)",
        "CREATE INDEX IF NOT EXISTS idx_lpga_id ON players(lpga_id)",

        # Tournament ID columns
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS korn_ferry_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS champions_tournament_id VARCHAR(50)",
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS lpga_tournament_id VARCHAR(50)",

        # Tournament ID indexes
        "CREATE INDEX IF NOT EXISTS idx_korn_ferry_tournament_id ON tournaments(korn_ferry_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_champions_tournament_id ON tournaments(champions_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_lpga_tournament_id ON tournaments(lpga_tournament_id)",
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


def run_scrape(year: int):
    """Run the scrape-all command."""
    from cli.commands import scrape_all
    scrape_all(year=year)


def main():
    parser = argparse.ArgumentParser(description='Run golf tracker scrape with auto-migration')
    parser.add_argument('--year', type=int, default=2026, help='Year to scrape')
    args = parser.parse_args()

    print(f"Golf Tracker Scrape - Year {args.year}")
    print("=" * 40)

    # Run migrations first
    run_migrations()

    # Then run the scrape
    run_scrape(args.year)


if __name__ == "__main__":
    main()
