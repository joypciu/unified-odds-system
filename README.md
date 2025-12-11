# Unified Odds System

A comprehensive multi-bookmaker odds collection and monitoring system with real-time updates.

## Quick Start

```bash
# Install dependencies
pip install -r config/requirements.txt

# Configure system
cp config/config.json.template config/config.json
# Edit config/config.json with your settings

# Run the system
python core/launch_odds_system.py --include-live
```

## Supported Bookmakers

- **1xBet** (Live + Pregame + Futures)
- **FanDuel** (Live + Pregame)
- **Bet365** (Live + Pregame)
- **OddsMagnet** (Real-time, 117+ leagues, 9 bookmakers)

## API Endpoints

Access odds data via REST API:

- `http://localhost:8000/` - Web dashboard
- `http://localhost:8000/api/matches` - All matches
- `http://localhost:8000/1xbet/pregame` - 1xBet pregame odds
- `http://localhost:8000/fanduel/live` - FanDuel live odds
- `http://localhost:8000/oddsmagnet/football` - OddsMagnet all leagues
- `http://localhost:8000/oddsmagnet/football/top10` - Top 10 leagues only

## Project Structure

```
unified-odds-system/
├── bookmakers/      # Bookmaker-specific scrapers
├── core/            # Core system files
├── utils/           # Utility modules
├── config/          # Configuration files
├── deployment/      # Deployment scripts
├── docs/            # Documentation
├── data/            # Runtime data outputs
└── tests/           # Test files
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for detailed structure.

## Documentation

- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation
- [**Project Structure**](docs/PROJECT_STRUCTURE.md) - Folder organization
- [**Adding Bookmakers**](docs/ADDING_NEW_BOOKMAKERS.md) - Scalability guide
- [**Deployment Guide**](docs/GITHUB_DEPLOYMENT_GUIDE.md) - VPS deployment
- [**Documentation Index**](docs/DOCUMENTATION_INDEX.md) - All docs

## Configuration

Edit `config/config.json`:

```json
{
  "enabled_scrapers": {
    "1xbet": true,
    "fanduel": true,
    "bet365": false,
    "oddsmagnet": true
  }
}
```

## Deployment

```bash
# Deploy to VPS
bash deployment/deploy_unified_odds_auto.sh
```

System auto-deploys on git push to `main` branch via GitHub Actions.

## Features

- Real-time odds collection (1-second updates)
- Multi-bookmaker support
- Automated monitoring & health checks
- REST API with FastAPI
- Web dashboard UI
- Email alerts on failures
- Auto-restart on crashes
- Modular & scalable architecture

## Tech Stack

- **Backend**: Python, FastAPI
- **Scraping**: Selenium, Requests
- **Deployment**: GitHub Actions, Systemd
- **Monitoring**: Custom health monitoring system

## License

Private project - All rights reserved

---

**For detailed documentation, see [docs/](docs/) folder**
