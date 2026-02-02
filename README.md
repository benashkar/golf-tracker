# Golf Tracker

A comprehensive golf data collection and display system for local news sites that publish stories about former high school players who have gone on to play professional golf.

## Purpose

Enable writing local news stories like:

> "Scottie Scheffler, a 2014 graduate of Highland Park High School in Dallas, Texas, finished first in the American Express Championship on Sunday, January 25th. He shot rounds of 68-65-70-67 to finish at 18-under par, earning $1.4 million."

## Features

- **Player Database**: Track players with high school, college, and hometown information
- **Tournament Results**: Scrape and store tournament results with round-by-round scores
- **Multi-League Support**:
  - ✅ PGA Tour, Korn Ferry Tour, Champions Tour (PGA GraphQL API)
  - ✅ LPGA Tour, DP World Tour (ESPN API)
  - ✅ LIV Golf (hardcoded schedule)
  - 🚧 PGA Tour Americas, College Golf (in progress)
  - ❌ USGA Amateur Events (planned)
- **Bio Enrichment**: Multi-source cascade (DuckDuckGo → Wikipedia → ESPN → Grokepedia)
- **Web Dashboard**: Search players by location, view tournament results
- **News Generation**: Auto-generate news snippets with player background info
- **Automated Scraping**: Render cron job runs every 2 hours

## Quick Start

### Prerequisites

- Python 3.11+
- MySQL database (or use Docker)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/golf-tracker.git
cd golf-tracker
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

5. Initialize the database:
```bash
python -m cli.commands init-db
```

6. Run the web application:
```bash
python -m cli.commands run-web
```

Visit http://localhost:5000 to access the dashboard.

## Data Collection

### Run Scrapers Manually

```bash
# Scrape all leagues at once
python -m cli.commands scrape-all --year 2026

# Scrape specific league roster
python -m cli.commands scrape --league PGA --type roster
python -m cli.commands scrape --league DPWORLD --type roster
python -m cli.commands scrape --league LIV --type roster

# Scrape tournaments for a specific year
python -m cli.commands scrape --league PGA --type tournaments --year 2026
python -m cli.commands scrape --league LPGA --type tournaments --year 2026

# Enrich player bios (uses DuckDuckGo → Wikipedia → ESPN → Grokepedia cascade)
python -m cli.commands enrich-bios --limit 100
python -m cli.commands enrich-bios --source ddg --limit 50  # DuckDuckGo only

# View database statistics
python -m cli.commands stats
```

### Supported Leagues

| League | Code | Command Example |
|--------|------|-----------------|
| PGA Tour | `PGA` | `--league PGA` |
| Korn Ferry Tour | `KORNFERRY` | `--league KORNFERRY` |
| Champions Tour | `CHAMPIONS` | `--league CHAMPIONS` |
| LPGA Tour | `LPGA` | `--league LPGA` |
| DP World Tour | `DPWORLD` | `--league DPWORLD` |
| LIV Golf | `LIV` | `--league LIV` |

### Automated Scraping

The project uses a Render cron job that runs every 2 hours:
- Updates all player rosters
- Scrapes latest tournament results with round-by-round scores
- Enriches missing player biographical data

## Project Structure

```
golf-tracker/
├── config/              # Configuration settings
├── database/            # Database models and migrations
├── scrapers/            # Web scrapers for each tour
├── services/            # Business logic layer
├── web/                 # Flask web application
├── cli/                 # Command-line interface
└── tests/               # Unit tests
```

## API Endpoints

The application provides a JSON API:

- `GET /api/players` - List players
- `GET /api/players/<id>` - Get player details
- `GET /api/players/search` - Search by high school/college
- `GET /api/tournaments` - List tournaments
- `GET /api/tournaments/<id>` - Get tournament results
- `GET /api/news/player-intro/<id>` - Generate news intro
- `GET /api/news/local-package/<tournament_id>?state=Texas` - Get local news package

## Deployment

### Render

The project is deployed on Render with:
- **Cron Job**: Runs `python run_scrape.py --year 2026` every 2 hours
- **PostgreSQL Database**: Stores all player and tournament data
- **Auto-Deploy**: Pushes to `main` branch trigger automatic deploys

To deploy:
1. Connect your GitHub repository to Render
2. Create a PostgreSQL database
3. Create a cron job with schedule `0 */2 * * *`
4. Set `DATABASE_URL` environment variable

### Docker

```bash
docker-compose up -d
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.
