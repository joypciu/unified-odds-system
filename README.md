# Unified Odds System

A comprehensive Python-based system for collecting, merging, and monitoring betting odds from multiple sportsbooks (Bet365, FanDuel, 1xBet, and BetLink). The system provides real-time unified odds data with automatic team name normalization, caching, and alerting capabilities through REST API endpoints.

## Features

- **Multi-Bookmaker Support**: Collects odds from Bet365, FanDuel, 1xBet, and BetLink
- **Real-Time Monitoring**: Live odds updates with instant file change detection
- **Intelligent Team Matching**: O(1) cache-based team name normalization with fuzzy fallback
- **Unified Data Format**: Consistent odds structure across all bookmakers
- **OpticOdds Format API**: RESTful endpoints returning industry-standard OpticOdds format
- **Email Alerting**: Automated notifications for system issues and failures
- **Memory Optimization**: Efficient processing with garbage collection and streaming
- **Web UI**: Clean interface for viewing odds data with real-time updates
- **REST API Endpoints**: Comprehensive API for odds data access and system monitoring
- **Process Health Monitoring**: Automatic restart and memory usage tracking
- **Cross-Platform**: Windows, Linux, and macOS support

## Project Structure

```
├── bet365/                 # Bet365 scrapers and data
├── fanduel/               # FanDuel scrapers and data
├── 1xbet/                 # 1xBet scrapers and data
├── betlink/               # BetLink scrapers and data
├── config.json           # System configuration
├── requirements.txt      # Python dependencies
├── launch_odds_system.py # Main system runner
├── unified_odds_collector.py # Data merging logic
├── dynamic_cache_manager.py # Team name caching
├── monitoring_system.py  # System monitoring
├── live_odds_viewer_clean.py # Web UI
├── monitoring_status_api.py # REST API endpoints
├── unified_odds.json     # Unified odds data output
└── cache_data.json      # Team name mappings
```

## Installation

### Prerequisites

- Python 3.8+
- Chrome browser (for scraping)
- Gmail account (for email alerts)

### Setup

1. **Clone or download the project**
   ```bash
   # If using git
   git clone <repository-url>
   cd unified-odds-system
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure email settings**
   - Copy `config.json.template` to `config.json`
   - Set up Gmail app password (see Email Setup Guide)
   - Configure monitoring settings

4. **Build team cache** (optional, improves matching accuracy)
   ```bash
   python build_team_cache.py
   ```

## Configuration

Edit `config.json` to customize:

```json
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "admin_email": "admin@example.com",
    "alert_cooldown_minutes": 30,
    "enabled": true
  },
  "monitoring": {
    "check_interval_seconds": 300,
    "data_stale_threshold_minutes": 60,
    "failure_threshold": 3,
    "modules": ["bet365_pregame", "fanduel_pregame", "1xbet_pregame", "betlink_pregame"]
  },
  "cache": {
    "auto_update": true,
    "update_interval_minutes": 30
  }
}
```

## Usage

### Quick Start

Run the complete system with one command:

```bash
# Default: Run ALL modules (pregame + live from all sources)
python launch_odds_system.py

# One-time collection (collect data then merge)
python launch_odds_system.py --mode once --duration 120

# Continuous monitoring with periodic merges
python launch_odds_system.py --mode continuous

# Real-time monitoring with instant updates
python launch_odds_system.py --mode realtime
```

### Advanced Options

```bash
# Pregame matches only (no live)
python launch_odds_system.py --pregame-only

# Live matches only (no pregame)
python launch_odds_system.py --live-only

# Custom duration (seconds)
python launch_odds_system.py --mode once --duration 300

# Disable monitoring system
python launch_odds_system.py --no-monitoring

# Test email configuration
python launch_odds_system.py --alert-test
```

### Individual Components

```bash
# Run unified collector only
python unified_odds_collector.py

# Start web UI
python live_odds_viewer_clean.py

# Start monitoring API
python monitoring_status_api.py

# Build/update team cache
python build_team_cache.py
```

## Email Setup Guide

For email alerts to work, you need to configure Gmail with 2-step verification and an app password. 

**⚠️ IMPORTANT: Email alerts do NOT work with VPN enabled** (NordVPN, ExpressVPN, etc.)

VPNs block SSL/TLS handshakes with Gmail's SMTP servers, causing timeouts. Solutions:

1. **Disable VPN when running the system** (recommended)
2. **Add Python to VPN Split Tunneling** - Configure your VPN to bypass Python traffic
3. **Disable email alerts** - Set `"enabled": false` in config.json

See `EMAIL_SETUP_GUIDE.md` for detailed instructions including:
- Gmail app password setup
- VPN compatibility solutions
- Firewall configuration
- Troubleshooting steps

## Web Interface

The system includes a clean web interface for viewing odds with real-time updates:

```bash
python live_odds_viewer_clean.py
```

Then open `http://localhost:8000` in your browser.

Features:
- Real-time odds display with WebSocket updates
- Live match scores and status
- Multi-bookmaker comparison
- Sport filtering and search
- Responsive design
- Modal view for detailed odds

## OpticOdds Format API Endpoints

The system provides **OpticOdds-compatible REST API endpoints** for accessing odds data in industry-standard format:

### 1xBet Endpoints
- `GET /1xbet` - All 1xBet odds (pregame + live) in OpticOdds format
- `GET /1xbet/pregame` - 1xBet pregame odds only
- `GET /1xbet/live` - 1xBet live odds only

### FanDuel Endpoints  
- `GET /fanduel` - All FanDuel odds (pregame + live) in OpticOdds format
- `GET /fanduel/pregame` - FanDuel pregame odds only
- `GET /fanduel/live` - FanDuel live odds only

### Bet365 Endpoints
- `GET /bet365` - All Bet365 odds (pregame + live) in OpticOdds format
- `GET /bet365/pregame` - Bet365 pregame odds only
- `GET /bet365/live` - Bet365 live odds only
- `GET /bet365/soccer` - Bet365 soccer odds only

### Eternity Format Endpoints (Alternative Format)
- `GET /eternity/1xbet` - 1xBet odds in Eternity format
- `GET /eternity/fanduel` - FanDuel odds in Eternity format
- `GET /eternity/bet365` - Bet365 odds in Eternity format

### Legacy Endpoints (Unified Format)
- `GET /api/matches` - All unified odds data (pregame + live)
- `GET /api/matches/pregame` - Pregame matches only
- `GET /api/matches/live` - Live matches only
- `GET /api/matches/sport/{sport}` - Odds for specific sport
- `GET /api/matches/bookmaker/{bookmaker}` - Odds from specific bookmaker
- `GET /api/status` - File system status
- `GET /api/monitoring` - Monitoring system status

### OpticOdds Format Structure

All `/1xbet`, `/fanduel`, and `/bet365` endpoints return data in OpticOdds format:

```json
{
  "data": [
    {
      "id": "match_id",
      "game_id": "sport-match_id",
      "start_date": "2025-12-06T10:00:00Z",
      "home_competitors": [{"id": null, "name": "Team A", "abbreviation": "TA"}],
      "away_competitors": [{"id": null, "name": "Team B", "abbreviation": "TB"}],
      "home_team_display": "Team A",
      "away_team_display": "Team B",
      "status": "unplayed",
      "is_live": false,
      "sport": {"id": "basketball", "name": "Basketball"},
      "league": {"id": "nba", "name": "NBA"},
      "tournament": null,
      "odds": [
        {
          "id": "match_id:bet365:moneyline:home",
          "sportsbook": "Bet365",
          "market": "Moneyline",
          "name": "Team A",
          "is_main": true,
          "selection": "Team A",
          "normalized_selection": "team_a",
          "market_id": "moneyline",
          "selection_line": null,
          "player_id": null,
          "team_id": null,
          "price": -110,
          "timestamp": 1733472000.0,
          "grouping_key": "default",
          "points": null,
          "betlink": "",
          "limits": null
        }
      ]
    }
  ]
}
```

### Example API Usage

```bash
# Get all 1xBet pregame odds in OpticOdds format
curl "http://142.44.160.36:8000/1xbet/pregame"

# Get FanDuel live odds
curl "http://142.44.160.36:8000/fanduel/live"

# Get Bet365 soccer odds
curl "http://142.44.160.36:8000/bet365/soccer"

# Get all Bet365 odds
curl "http://142.44.160.36:8000/bet365"

# Legacy unified format
curl "http://142.44.160.36:8000/api/matches/live"
```

### Response Format

- **OpticOdds endpoints**: Return `{"data": [...]}` with game objects containing odds arrays
- **Market types**: Moneyline, Point Spread, Total Points
- **Price format**: American odds (e.g., -110, +150)
- **Timestamps**: ISO 8601 format with Unix timestamps

## Monitoring & Alerting

The system automatically monitors:

- **Process Health**: Detects crashed scrapers and sends alerts
- **Memory Usage**: Monitors RAM usage and alerts on high consumption
- **Data Freshness**: Checks if odds data is being updated
- **File Integrity**: Validates JSON data files

Alerts are sent via email when:
- Scrapers crash or fail to start
- Memory usage exceeds thresholds
- Data files become stale
- System errors occur

## Data Output

The system generates `unified_odds.json` with the following structure:

```json
{
  "metadata": {
    "generated_at": "2025-11-25T06:00:00.000Z",
    "sources": ["bet365", "fanduel", "1xbet", "betlink"],
    "total_pregame_matches": 150,
    "total_live_matches": 25,
    "api_endpoints": {
      "odds": "http://localhost:5000/odds",
      "pregame": "http://localhost:5000/odds/pregame",
      "live": "http://localhost:5000/odds/live",
      "health": "http://localhost:5000/health"
    }
  },
  "pregame_matches": [...],
  "live_matches": [...]
}
```

Each match includes:
- Sport and teams (with normalized names)
- Date/time information
- Odds from all available bookmakers (bet365, fanduel, 1xbet, betlink)
- Live scores and game status (for live matches)
- Match IDs and fixture identifiers
- League/competition information

### API Response Format

All API endpoints return data in the same unified JSON structure, making integration seamless for applications and services.

## Troubleshooting

### Common Issues

**Chrome not found**
```
Error: Chrome browser not detected
```
- Install Google Chrome
- Ensure Chrome is in PATH
- Check if Chrome is running with admin privileges

**Email alerts not working**
```
Email alert failed: Authentication failed
```
- Verify Gmail credentials in `config.json`
- Ensure 2-step verification is enabled
- Generate new app password
- **Check if VPN is enabled** - VPNs block SMTP connections (see Email Setup Guide)
- Check firewall settings

**Memory issues**
```
Process memory usage: 450 MB (threshold: 400 MB)
```
- Reduce concurrent scrapers
- Increase memory threshold in config
- Restart system to clear memory

**Data not updating**
```
Data file not updated for 15 minutes
```
- Check if scrapers are running
- Verify internet connection
- Check browser automation (may need reCAPTCHA solving)

### Logs

Check logs in each bookmaker directory:
- `bet365/logs/`
- `fanduel/logs/`
- `1xbet/` (check console output)

### Manual Testing

```bash
# Test email configuration
python launch_odds_system.py --alert-test

# Test individual scrapers
cd bet365 && python bet365_pregame_monitor.py --test
cd fanduel && python fanduel_master_collector.py 1
cd 1xbet && python 1xbet_pregame.py
```

## Development

### Adding New Bookmakers

1. Create new directory structure
2. Implement scraper scripts
3. Add loader methods to `UnifiedOddsCollector`
4. Update bookmaker registry in merge methods
5. Add configuration options

### Testing

Run the comprehensive test suite:

```bash
python test_all.py
```

Tests cover:
- Module imports
- Caching functionality
- Data merging logic
- Monitoring systems
- UI components
- Email alerting

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## GitHub-Based VPS Deployment

The system supports automatic deployment to VPS servers using GitHub Actions. Every push to the `main` branch will automatically deploy to your VPS and restart the service.

### Quick Setup Guide

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/unified-odds-system.git
   git push -u origin main
   ```

2. **Configure GitHub Secrets**
   
   Go to: `https://github.com/YOUR_USERNAME/unified-odds-system/settings/secrets/actions`
   
   Add these 4 secrets:
   
   | Secret Name | Value | Description |
   |------------|-------|-------------|
   | `VPS_HOST` | Your VPS IP address | e.g., `142.44.160.36` |
   | `VPS_USERNAME` | VPS SSH username | Usually `ubuntu` or `root` |
   | `VPS_PORT` | SSH port | Usually `22` |
   | `VPS_SSH_KEY` | SSH private key | See below |

3. **Get Your SSH Private Key**
   
   On your VPS, run:
   ```bash
   cat ~/.ssh/id_ed25519
   ```
   
   Copy the **entire output** including the BEGIN and END lines:
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   ...key content...
   -----END OPENSSH PRIVATE KEY-----
   ```
   
   If the key doesn't exist, create one:
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com" -f ~/.ssh/id_ed25519
   ```

4. **Add Public Key to authorized_keys**
   
   **CRITICAL STEP**: The public key must be in `~/.ssh/authorized_keys` on your VPS:
   
   ```bash
   # Display your public key
   cat ~/.ssh/id_ed25519.pub
   
   # Add it to authorized_keys
   cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
   
   # Set correct permissions
   chmod 600 ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   ```

5. **Run the automated deployment script**
   
   On your VPS:
   ```bash
   cd ~
   wget https://raw.githubusercontent.com/YOUR_USERNAME/unified-odds-system/main/deploy_unified_odds_auto.sh
   chmod +x deploy_unified_odds_auto.sh
   ./deploy_unified_odds_auto.sh
   ```
   
   This will:
   - Install all dependencies (Chrome, xvfb, Python packages)
   - Clone your repository
   - Set up systemd service
   - Configure automatic startup

6. **Test the deployment**
   
   Make a small change and push:
   ```bash
   echo "# Test" >> README.md
   git add README.md
   git commit -m "Test auto-deployment"
   git push origin main
   ```
   
   Check the Actions tab on GitHub to see the deployment: `https://github.com/YOUR_USERNAME/unified-odds-system/actions`

### How It Works

- GitHub Actions workflow (`.github/workflows/deploy.yml`) monitors pushes to `main`
- On push, it connects to your VPS via SSH
- Pulls latest code, installs dependencies, restarts service
- You get instant feedback on deployment success/failure

### Troubleshooting GitHub Actions

**Error: `ssh: unable to authenticate`**
- Solution: Make sure the SSH **public key** is in `~/.ssh/authorized_keys` on VPS
- Verify: `cat ~/.ssh/authorized_keys` should show your public key

**Error: `Permission denied (publickey)`**
- Check that VPS_SSH_KEY secret contains the **entire private key** with BEGIN/END lines
- Ensure no extra spaces or line breaks when pasting into GitHub

**Deployment not triggering**
- Check the `.github/workflows/deploy.yml` file exists in your repository
- Verify you're pushing to the `main` branch (not `master` or other)

**Service fails to start**
- SSH into VPS and check logs: `sudo journalctl -u unified-odds -n 50`
- Verify config.json is properly configured
- Check Chrome installation: `google-chrome --version`

For detailed deployment guides, see:
- `GITHUB_DEPLOYMENT_GUIDE.md` - Complete deployment documentation
- `AUTOMATED_DEPLOYMENT_GUIDE.md` - Using the automated setup script
- `QUICKSTART_GITHUB_DEPLOY.md` - 3-step quick setup

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs for error details
- Test individual components
- Verify configuration settings

## Changelog

### v2.0.0 (December 2025)
- **OpticOdds Format API**: Added industry-standard OpticOdds format endpoints
  - `/1xbet`, `/1xbet/pregame`, `/1xbet/live`
  - `/fanduel`, `/fanduel/pregame`, `/fanduel/live`
  - `/bet365`, `/bet365/pregame`, `/bet365/live`, `/bet365/soccer`
  - `/eternity/*` endpoints for alternative format
- **Format Converters**: New `odds_format_converters.py` module
  - OpticOdds format conversion
  - Eternity format conversion
  - Support for nested and flat odds structures
- **UI Improvements**: Better handling of matches with null odds
  - Shows informative message instead of blank modal
  - Sport filter dynamically populated from data
  - Real-time WebSocket updates
- **1xBet Domain Fix**: Changed from dead 1xlite-707953.top to working 1xbet.com
- **Enhanced Documentation**: Comprehensive API endpoint documentation with examples

### v1.1.0
- Added BetLink bookmaker support
- Enhanced REST API with comprehensive odds endpoints
- Improved homepage-first tab opening for FanDuel scraping
- Added concurrent Bet365 live scraper integration
- Expanded API endpoints for sport-specific and bookmaker-specific queries

### v1.0.0
- Initial release
- Support for Bet365, FanDuel, 1xBet
- Real-time monitoring
- Email alerting
- Web UI
- Basic REST API
- Team name caching
- Memory optimization#   T e s t   d e p l o y m e n t 
 
 #   T e s t   2 
 
 #   T e s t   3   -   S S H   k e y   f i x e d 
 
 