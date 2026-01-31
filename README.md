# Golf Tracker

A comprehensive golf data collection and display system for local news sites that publish stories about former high school players who have gone on to play professional golf.

## Purpose

Enable writing local news stories like:

> "Scottie Scheffler, a 2014 graduate of Highland Park High School in Dallas, Texas, finished first in the American Express Championship on Sunday, January 25th. He shot rounds of 68-65-70-67 to finish at 18-under par, earning $1.4 million."

## Features

- **Player Database**: Track players with high school, college, and hometown information
- **Tournament Results**: Scrape and store tournament results with daily scores
- **Multi-League Support**: PGA Tour, DP World Tour, Korn Ferry Tour, LPGA, LIV Golf, Champions Tour
- **Web Dashboard**: Search players by location, view tournament results
- **News Generation**: Auto-generate news snippets with player background info
- **Daily Automation**: GitHub Actions for scheduled data updates

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
# Scrape PGA Tour player roster
python -m cli.commands scrape --league PGA --type roster

# Scrape PGA Tour tournaments for 2025
python -m cli.commands scrape --league PGA --type tournaments --year 2025

# Enrich player bios from Wikipedia
python -m cli.commands enrich-bios --limit 100
```

### Automated Daily Scraping

The project includes a GitHub Actions workflow that runs daily at 6 AM UTC:
- Updates player roster
- Scrapes latest tournament results
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

The project includes `render.yaml` for easy deployment to Render:

1. Connect your GitHub repository to Render
2. The service will automatically deploy

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
