#!/usr/bin/env python3
"""
Database Migration Runner
=========================

Run this script to apply pending database migrations.
Can be run from Render Shell: python run_migration.py

Uses DATABASE_URL environment variable for connection.
"""

import os
import sys

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from database.connection import DatabaseManager


def run_migration():
    """Add missing tour-specific ID columns to players and tournaments tables."""

    db = DatabaseManager()

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
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS dpworld_tournament_id VARCHAR(50)",

        # Tournament ID indexes
        "CREATE INDEX IF NOT EXISTS idx_korn_ferry_tournament_id ON tournaments(korn_ferry_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_champions_tournament_id ON tournaments(champions_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_lpga_tournament_id ON tournaments(lpga_tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_dpworld_tournament_id ON tournaments(dpworld_tournament_id)",
    ]

    print("Running database migrations...")

    with db.get_session() as session:
        for sql in migrations:
            try:
                print(f"  Running: {sql[:60]}...")
                session.execute(text(sql))
                session.commit()
                print("    ✓ Success")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"    - Already exists, skipping")
                else:
                    print(f"    ✗ Error: {e}")
                session.rollback()

    print("\nMigration complete!")


if __name__ == "__main__":
    run_migration()
