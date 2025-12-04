# Unified Odds System

A comprehensive Python-based system for collecting, merging, and monitoring betting odds from multiple sportsbooks (Bet365, FanDuel, 1xBet, and BetLink). The system provides real-time unified odds data with automatic team name normalization, caching, and alerting capabilities through REST API endpoints.

## Features

- **Multi-Bookmaker Support**: Collects odds from Bet365, FanDuel, 1xBet, and BetLink
- **Real-Time Monitoring**: Live odds updates with instant file change detection
- **Intelligent Team Matching**: O(1) cache-based team name normalization with fuzzy fallback
- **Unified Data Format**: Consistent odds structure across all bookmakers
- **Email Alerting**: Automated notifications for system issues and failures
- **Memory Optimization**: Efficient processing with garbage collection and streaming
- **Web UI**: Clean interface for viewing odds data
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

The system includes a clean web interface for viewing odds:

```bash
python live_odds_viewer_clean.py
```

Then open `http://localhost:8000` in your browser.

Features:
- Real-time odds display
- Live match scores
- Multi-bookmaker comparison
- Responsive design

## REST API Endpoints

The system provides comprehensive REST API endpoints for accessing odds data and monitoring system status:

```bash
python monitoring_status_api.py
```

### Odds Data Endpoints
- `GET /odds` - Get all unified odds data (pregame + live)
- `GET /odds/pregame` - Get pregame matches only
- `GET /odds/live` - Get live matches only
- `GET /odds/sport/{sport}` - Get odds for specific sport (basketball, soccer, football, etc.)
- `GET /odds/bookmaker/{bookmaker}` - Get odds from specific bookmaker (bet365, fanduel, 1xbet, betlink)

### System Monitoring Endpoints
- `GET /status` - System health status and uptime
- `GET /alerts` - Recent system alerts and notifications
- `GET /memory` - Memory usage statistics for all processes
- `GET /processes` - Running process information and PIDs
- `GET /health` - Quick health check endpoint

### Data Query Parameters
- `?limit=50` - Limit number of results
- `?sport=basketball` - Filter by sport
- `?bookmaker=bet365` - Filter by bookmaker
- `?live_only=true` - Show live matches only
- `?min_odds=1.5` - Filter by minimum odds value

### Example API Usage
```bash
# Get all live basketball odds
curl "http://localhost:5000/odds/live?sport=basketball"

# Get Bet365 odds for soccer
curl "http://localhost:5000/odds/bookmaker/bet365?sport=soccer"

# System health check
curl "http://localhost:5000/health"
```

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

## Support

For issues and questions:
- Check the troubleshooting section
- Review logs for error details
- Test individual components
- Verify configuration settings

## Changelog

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
- Memory optimization#   T e s t   d e p l o y m e n t  
 