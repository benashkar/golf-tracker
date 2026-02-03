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
@click.option('--league', required=True, help='League code (PGA, DPWORLD, KORNFERRY, LPGA, LIV, CHAMPIONS, PGAAMERICAS, USGA, EPSON)')
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
            if league == 'PGA':
                from scrapers.pga_tour.roster_scraper import PGATourRosterScraper
                scraper = PGATourRosterScraper()
            elif league == 'KORNFERRY':
                from scrapers.korn_ferry.roster_scraper import KornFerryRosterScraper
                scraper = KornFerryRosterScraper()
            elif league == 'CHAMPIONS':
                from scrapers.champions.roster_scraper import ChampionsRosterScraper
                scraper = ChampionsRosterScraper()
            elif league == 'LPGA':
                from scrapers.lpga.roster_scraper import LPGARosterScraper
                scraper = LPGARosterScraper()
            elif league == 'DPWORLD':
                from scrapers.dp_world.roster_scraper import DPWorldRosterScraper
                scraper = DPWorldRosterScraper()
            elif league == 'LIV':
                from scrapers.liv.roster_scraper import LIVRosterScraper
                scraper = LIVRosterScraper()
            elif league == 'PGAAMERICAS':
                from scrapers.pga_americas.roster_scraper import PGAAmericasRosterScraper
                scraper = PGAAmericasRosterScraper()
            elif league == 'USGA':
                from scrapers.usga.roster_scraper import USGARosterScraper
                scraper = USGARosterScraper()
            elif league == 'EPSON':
                from scrapers.epson.roster_scraper import EpsonRosterScraper
                scraper = EpsonRosterScraper()
            else:
                raise click.ClickException(f"Roster scraper not yet implemented for {league}")

            result = scraper.run()

        elif scrape_type in ['tournaments', 'results']:
            if league == 'PGA':
                from scrapers.pga_tour.tournament_scraper import PGATourTournamentScraper
                scraper = PGATourTournamentScraper()
            elif league == 'KORNFERRY':
                from scrapers.korn_ferry.tournament_scraper import KornFerryTournamentScraper
                scraper = KornFerryTournamentScraper()
            elif league == 'CHAMPIONS':
                from scrapers.champions.tournament_scraper import ChampionsTournamentScraper
                scraper = ChampionsTournamentScraper()
            elif league == 'LPGA':
                from scrapers.lpga.tournament_scraper import LPGATournamentScraper
                scraper = LPGATournamentScraper()
            elif league == 'DPWORLD':
                from scrapers.dp_world.tournament_scraper import DPWorldTournamentScraper
                scraper = DPWorldTournamentScraper()
            elif league == 'LIV':
                from scrapers.liv.tournament_scraper import LIVTournamentScraper
                scraper = LIVTournamentScraper()
            elif league == 'PGAAMERICAS':
                from scrapers.pga_americas.tournament_scraper import PGAAmericasTournamentScraper
                scraper = PGAAmericasTournamentScraper()
            elif league == 'USGA':
                from scrapers.usga.tournament_scraper import USGATournamentScraper
                scraper = USGATournamentScraper()
            elif league == 'EPSON':
                from scrapers.epson.tournament_scraper import EpsonTournamentScraper
                scraper = EpsonTournamentScraper()
            else:
                raise click.ClickException(f"Tournament scraper not yet implemented for {league}")

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


@cli.command('scrape-all')
@click.option('--year', default=None, type=int, help='Year for tournament data')
@click.option('--include-college', is_flag=True, help='Include NCAA college golf')
@click.option('--include-amateur', is_flag=True, help='Include amateur golf (AJGA)')
def scrape_all(year: int, include_college: bool, include_amateur: bool):
    """
    Scrape all configured leagues (PGA, Korn Ferry, Champions, LPGA).

    This is the main command for the cron job - it scrapes rosters and
    tournaments for all active leagues.

    Examples:
        python -m cli.commands scrape-all
        python -m cli.commands scrape-all --year 2026
        python -m cli.commands scrape-all --include-college --include-amateur
    """
    from datetime import datetime
    year = year or datetime.now().year

    # Professional tour leagues (always scraped)
    leagues = [
        ('PGA', 'PGA Tour'),
        ('KORNFERRY', 'Korn Ferry Tour'),
        ('CHAMPIONS', 'PGA Tour Champions'),
        ('LPGA', 'LPGA Tour'),
        ('EPSON', 'Epson Tour'),  # LPGA developmental - high US player %
        ('DPWORLD', 'DP World Tour'),
        ('LIV', 'LIV Golf'),
        ('PGAAMERICAS', 'PGA Tour Americas'),
        ('USGA', 'USGA Amateur Events'),
    ]

    # College golf divisions (optional - scrape if flag set)
    college_divisions = [
        ('NCAA_D1_MENS', 'NCAA D1 Men\'s Golf'),
        ('NCAA_D1_WOMENS', 'NCAA D1 Women\'s Golf'),
    ]

    # Amateur leagues (optional - scrape if flag set)
    amateur_leagues = [
        ('AJGA', 'American Junior Golf Association'),
    ]

    total_results = {
        'players_created': 0,
        'players_updated': 0,
        'tournaments_created': 0,
        'tournaments_updated': 0,
        'errors': []
    }

    for league_code, league_name in leagues:
        click.echo(f"\n{'='*50}")
        click.echo(f"Scraping {league_name}...")
        click.echo('='*50)

        try:
            # Roster scrape
            click.echo(f"\n  Fetching {league_name} roster...")
            roster_scraper = None
            if league_code == 'PGA':
                from scrapers.pga_tour.roster_scraper import PGATourRosterScraper
                roster_scraper = PGATourRosterScraper()
            elif league_code == 'KORNFERRY':
                from scrapers.korn_ferry.roster_scraper import KornFerryRosterScraper
                roster_scraper = KornFerryRosterScraper()
            elif league_code == 'CHAMPIONS':
                from scrapers.champions.roster_scraper import ChampionsRosterScraper
                roster_scraper = ChampionsRosterScraper()
            elif league_code == 'LPGA':
                from scrapers.lpga.roster_scraper import LPGARosterScraper
                roster_scraper = LPGARosterScraper()
            elif league_code == 'DPWORLD':
                from scrapers.dp_world.roster_scraper import DPWorldRosterScraper
                roster_scraper = DPWorldRosterScraper()
            elif league_code == 'LIV':
                from scrapers.liv.roster_scraper import LIVRosterScraper
                roster_scraper = LIVRosterScraper()
            elif league_code == 'PGAAMERICAS':
                from scrapers.pga_americas.roster_scraper import PGAAmericasRosterScraper
                roster_scraper = PGAAmericasRosterScraper()
            elif league_code == 'USGA':
                from scrapers.usga.roster_scraper import USGARosterScraper
                roster_scraper = USGARosterScraper()
            elif league_code == 'EPSON':
                from scrapers.epson.roster_scraper import EpsonRosterScraper
                roster_scraper = EpsonRosterScraper()

            roster_result = roster_scraper.run() if roster_scraper else {'records_created': 0, 'records_updated': 0}
            total_results['players_created'] += roster_result.get('records_created', 0)
            total_results['players_updated'] += roster_result.get('records_updated', 0)
            click.echo(f"    Created: {roster_result.get('records_created', 0)}, Updated: {roster_result.get('records_updated', 0)}")

            # Tournament scrape
            click.echo(f"\n  Fetching {league_name} tournaments for {year}...")
            tournament_scraper = None
            if league_code == 'PGA':
                from scrapers.pga_tour.tournament_scraper import PGATourTournamentScraper
                tournament_scraper = PGATourTournamentScraper()
            elif league_code == 'KORNFERRY':
                from scrapers.korn_ferry.tournament_scraper import KornFerryTournamentScraper
                tournament_scraper = KornFerryTournamentScraper()
            elif league_code == 'CHAMPIONS':
                from scrapers.champions.tournament_scraper import ChampionsTournamentScraper
                tournament_scraper = ChampionsTournamentScraper()
            elif league_code == 'LPGA':
                from scrapers.lpga.tournament_scraper import LPGATournamentScraper
                tournament_scraper = LPGATournamentScraper()
            elif league_code == 'DPWORLD':
                from scrapers.dp_world.tournament_scraper import DPWorldTournamentScraper
                tournament_scraper = DPWorldTournamentScraper()
            elif league_code == 'LIV':
                from scrapers.liv.tournament_scraper import LIVTournamentScraper
                tournament_scraper = LIVTournamentScraper()
            elif league_code == 'PGAAMERICAS':
                from scrapers.pga_americas.tournament_scraper import PGAAmericasTournamentScraper
                tournament_scraper = PGAAmericasTournamentScraper()
            elif league_code == 'USGA':
                from scrapers.usga.tournament_scraper import USGATournamentScraper
                tournament_scraper = USGATournamentScraper()
            elif league_code == 'EPSON':
                from scrapers.epson.tournament_scraper import EpsonTournamentScraper
                tournament_scraper = EpsonTournamentScraper()

            tournament_result = tournament_scraper.run(year=year) if tournament_scraper else {'records_created': 0, 'records_updated': 0}
            total_results['tournaments_created'] += tournament_result.get('records_created', 0)
            total_results['tournaments_updated'] += tournament_result.get('records_updated', 0)
            click.echo(f"    Created: {tournament_result.get('records_created', 0)}, Updated: {tournament_result.get('records_updated', 0)}")

        except Exception as e:
            error_msg = f"{league_name}: {str(e)}"
            total_results['errors'].append(error_msg)
            click.echo(f"  ERROR: {e}")

    # College golf (optional)
    if include_college:
        click.echo(f"\n{'='*50}")
        click.echo("Scraping College Golf...")
        click.echo('='*50)

        for division_code, division_name in college_divisions:
            try:
                click.echo(f"\n  Fetching {division_name} tournaments...")
                from scrapers.college.tournament_scraper import CollegeGolfTournamentScraper
                college_scraper = CollegeGolfTournamentScraper(division=division_code)
                college_result = college_scraper.run(year=year)
                total_results['tournaments_created'] += college_result.get('records_created', 0)
                total_results['tournaments_updated'] += college_result.get('records_updated', 0)
                click.echo(f"    Created: {college_result.get('records_created', 0)}, Updated: {college_result.get('records_updated', 0)}")
            except Exception as e:
                error_msg = f"{division_name}: {str(e)}"
                total_results['errors'].append(error_msg)
                click.echo(f"  ERROR: {e}")

    # Amateur golf (optional)
    if include_amateur:
        click.echo(f"\n{'='*50}")
        click.echo("Scraping Amateur Golf...")
        click.echo('='*50)

        for league_code, league_name in amateur_leagues:
            try:
                if league_code == 'AJGA':
                    click.echo(f"\n  Fetching {league_name} tournaments...")
                    from scrapers.amateur.ajga_scraper import AJGATournamentScraper
                    ajga_scraper = AJGATournamentScraper()
                    ajga_result = ajga_scraper.run(year=year)
                    total_results['tournaments_created'] += ajga_result.get('records_created', 0)
                    total_results['tournaments_updated'] += ajga_result.get('records_updated', 0)
                    click.echo(f"    Created: {ajga_result.get('records_created', 0)}, Updated: {ajga_result.get('records_updated', 0)}")
            except Exception as e:
                error_msg = f"{league_name}: {str(e)}"
                total_results['errors'].append(error_msg)
                click.echo(f"  ERROR: {e}")

    # Bio enrichment from college rosters (best source for high school data)
    click.echo(f"\n{'='*50}")
    click.echo("Enriching player bios from college golf rosters...")
    click.echo('='*50)

    try:
        from scrapers.bio.college_roster_enricher import CollegeRosterBioEnricher
        college_enricher = CollegeRosterBioEnricher()
        college_result = college_enricher.run()
        click.echo(f"  Colleges scraped: {college_result.get('colleges_scraped', 0)}")
        click.echo(f"  Players enriched: {college_result.get('enriched', 0)}")
    except Exception as e:
        total_results['errors'].append(f"College roster enrichment: {str(e)}")
        click.echo(f"  ERROR: {e}")

    # Bio enrichment from multiple sources (Wikipedia, ESPN, Grokepedia)
    click.echo(f"\n{'='*50}")
    click.echo("Enriching player bios from Wikipedia/ESPN...")
    click.echo('='*50)

    try:
        from scrapers.bio.multi_source_enricher import MultiSourceBioEnricher
        enricher = MultiSourceBioEnricher()
        bio_result = enricher.run(limit=500, force=False)  # Increased from 100 to cover more players
        click.echo(f"  Enriched: {bio_result.get('enriched', 0)} players")
        click.echo(f"  Sources: DuckDuckGo={bio_result.get('sources_used', {}).get('duckduckgo', 0)}, "
                   f"Wikipedia={bio_result.get('sources_used', {}).get('wikipedia', 0)}, "
                   f"ESPN={bio_result.get('sources_used', {}).get('espn', 0)}, "
                   f"Grokepedia={bio_result.get('sources_used', {}).get('grokepedia', 0)}")
    except Exception as e:
        total_results['errors'].append(f"Bio enrichment: {str(e)}")
        click.echo(f"  ERROR: {e}")

    # Summary
    click.echo(f"\n{'='*50}")
    click.echo("SCRAPE COMPLETE - Summary")
    click.echo('='*50)
    click.echo(f"  Players Created: {total_results['players_created']}")
    click.echo(f"  Players Updated: {total_results['players_updated']}")
    click.echo(f"  Tournaments Created: {total_results['tournaments_created']}")
    click.echo(f"  Tournaments Updated: {total_results['tournaments_updated']}")

    if total_results['errors']:
        click.echo(f"\n  Errors ({len(total_results['errors'])}):")
        for error in total_results['errors']:
            click.echo(f"    - {error}")


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
