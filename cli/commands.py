"""
CLI Commands for Golf Tracker
==============================

This module provides command-line interface commands for running scrapers
and managing the golf tracker system.

Usage:
    python -m cli.commands scrape --league PGA --type roster
    python -m cli.commands scrape --league PGA --type tournaments --year 2025
    python -m cli.commands enrich-bios --limit 100
    python -m cli.commands init-db

For Junior Developers:
---------------------
Click is a library that makes it easy to create command-line tools.
The @click.command() decorator turns a function into a CLI command.
The @click.option() decorator adds command-line flags/arguments.
"""

import click
from loguru import logger
import sys

# Configure loguru for CLI
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


@click.group()
def cli():
    """Golf Tracker CLI - Manage golf data scraping and database."""
    pass


@cli.command()
@click.option('--league', required=True, help='League code (PGA, DPWORLD, KORNFERRY, LPGA, LIV, CHAMPIONS)')
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
    click.echo(f"\nStarting {scrape_type} scrape for {league}...")

    try:
        if scrape_type == 'roster':
            from scrapers.pga_tour.roster_scraper import PGATourRosterScraper

            if league != 'PGA':
                raise click.ClickException(f"Roster scraper not yet implemented for {league}")

            scraper = PGATourRosterScraper()
            result = scraper.run()

        elif scrape_type in ['tournaments', 'results']:
            from scrapers.pga_tour.tournament_scraper import PGATourTournamentScraper

            if league != 'PGA':
                raise click.ClickException(f"Tournament scraper not yet implemented for {league}")

            scraper = PGATourTournamentScraper()
            result = scraper.run(year=year)

        # Print results
        click.echo(f"\nScrape Complete!")
        click.echo(f"  Status: {result.get('status')}")
        click.echo(f"  Records Processed: {result.get('records_processed', 0)}")
        click.echo(f"  Records Created: {result.get('records_created', 0)}")
        click.echo(f"  Records Updated: {result.get('records_updated', 0)}")

        if result.get('errors'):
            click.echo(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors'][:5]:
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
    click.echo(f"\nStarting bio enrichment (limit: {limit}, force: {force})...")

    try:
        from scrapers.wikipedia.bio_enricher import WikipediaBioEnricher

        enricher = WikipediaBioEnricher()
        result = enricher.run(limit=limit, force=force)

        click.echo(f"\nBio Enrichment Complete!")
        click.echo(f"  Players Processed: {result.get('processed', 0)}")
        click.echo(f"  Successfully Enriched: {result.get('enriched', 0)}")
        click.echo(f"  No Wikipedia Page Found: {result.get('not_found', 0)}")

    except Exception as e:
        logger.error(f"Bio enrichment failed: {str(e)}")
        raise click.ClickException(str(e))


@cli.command('init-db')
def init_db():
    """
    Initialize the database with tables and seed data.

    This command creates all tables and inserts the initial league data.
    """
    click.echo("\nInitializing database...")

    try:
        from database.connection import DatabaseManager

        db = DatabaseManager()

        click.echo("  Testing connection...")
        db.test_connection()
        click.echo("  Connection successful!")

        click.echo("  Creating tables...")
        db.create_all_tables()
        click.echo("  Tables created!")

        click.echo("  Seeding leagues...")
        db.seed_leagues()
        click.echo("  Leagues seeded!")

        click.echo("\nDatabase initialized successfully!")

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise click.ClickException(str(e))


@cli.command('test-db')
def test_db():
    """
    Test the database connection.
    """
    click.echo("\nTesting database connection...")

    try:
        from database.connection import DatabaseManager

        db = DatabaseManager()
        db.test_connection()

        stats = db.get_stats()
        click.echo("Connection successful!")
        click.echo(f"  Pool Size: {stats['pool_size']}")
        click.echo(f"  Checked Out: {stats['checked_out']}")

    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        raise click.ClickException(str(e))


@cli.command('run-web')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=5000, type=int, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def run_web(host: str, port: int, debug: bool):
    """
    Run the Flask web application.

    Examples:
        python -m cli.commands run-web
        python -m cli.commands run-web --port 8080 --debug
    """
    click.echo(f"\nStarting web server on {host}:{port}...")

    try:
        from web.app import create_app

        app = create_app()
        app.run(host=host, port=port, debug=debug)

    except Exception as e:
        logger.error(f"Failed to start web server: {str(e)}")
        raise click.ClickException(str(e))


@cli.command()
def stats():
    """
    Show database statistics.
    """
    click.echo("\nDatabase Statistics:")

    try:
        from database.connection import DatabaseManager
        from database.models import Player, Tournament, TournamentResult, League

        db = DatabaseManager()

        with db.get_session() as session:
            leagues = session.query(League).count()
            players = session.query(Player).count()
            tournaments = session.query(Tournament).count()
            results = session.query(TournamentResult).count()

            players_with_hs = session.query(Player).filter(
                Player.high_school_name.isnot(None)
            ).count()

            click.echo(f"  Leagues: {leagues}")
            click.echo(f"  Players: {players}")
            click.echo(f"    With High School Info: {players_with_hs}")
            click.echo(f"  Tournaments: {tournaments}")
            click.echo(f"  Tournament Results: {results}")

    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise click.ClickException(str(e))


if __name__ == '__main__':
    cli()
