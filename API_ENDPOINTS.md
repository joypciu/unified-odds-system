# API Endpoints Documentation

## Web Server Configuration
- **Host**: 142.44.160.36
- **Port**: 8000
- **Base URL**: http://142.44.160.36:8000

---

## 📊 API Endpoints Overview

### Default Format: **OpticOdds** (similar to bet365 nba_optic_odds_format.json)
### Alternative Format: **EternityLabs** (similar to bet365 nba_eternity_format.json)

---

## 🎯 1xBet Endpoints

### OpticOdds Format (Default)
```
GET /1xbet                   - All 1xBet odds (pregame + live)
GET /1xbet/pregame           - 1xBet pregame odds only
GET /1xbet/live              - 1xBet live odds only
```

### EternityLabs Format
```
GET /1xbet/eternity          - All 1xBet odds in EternityLabs format
```

**Example URLs:**
- http://142.44.160.36:8000/1xbet
- http://142.44.160.36:8000/1xbet/pregame
- http://142.44.160.36:8000/1xbet/live
- http://142.44.160.36:8000/1xbet/eternity

---

## 🎲 FanDuel Endpoints

### OpticOdds Format (Default)
```
GET /fanduel                 - All FanDuel odds (pregame + live)
GET /fanduel/pregame         - FanDuel pregame odds only
GET /fanduel/live            - FanDuel live odds only
```

### EternityLabs Format
```
GET /fanduel/eternity        - All FanDuel odds in EternityLabs format
```

**Example URLs:**
- http://142.44.160.36:8000/fanduel
- http://142.44.160.36:8000/fanduel/pregame
- http://142.44.160.36:8000/fanduel/live
- http://142.44.160.36:8000/fanduel/eternity

---

## 🎰 Bet365 Endpoints

### OpticOdds Format (Default)
```
GET /bet365                  - All Bet365 odds (pregame + live)
GET /bet365/pregame          - Bet365 pregame odds only
GET /bet365/live             - Bet365 live odds only
```

### EternityLabs Format
```
GET /bet365/eternity         - All Bet365 odds in EternityLabs format
```

**Example URLs:**
- http://142.44.160.36:8000/bet365
- http://142.44.160.36:8000/bet365/pregame
- http://142.44.160.36:8000/bet365/live
- http://142.44.160.36:8000/bet365/eternity

---

## 📱 General API Endpoints

### Unified Data (All Bookmakers Combined)
```
GET /api/matches             - All matches from all bookmakers
GET /api/matches/live        - Live matches only
GET /api/matches/pregame     - Pregame matches only
GET /api/matches/sport/{sport}       - Filter by sport (e.g., /api/matches/sport/NBA)
GET /api/matches/bookmaker/{bookmaker} - Filter by bookmaker (e.g., /api/matches/bookmaker/1xbet)
```

### History (Completed/Old Matches)
```
GET /history                 - All completed matches from all bookmakers
GET /history/{bookmaker}     - Completed matches for specific bookmaker (1xbet, fanduel, bet365)
POST /api/clean-history      - Manually trigger history cleanup
```

**Example History URLs:**
- http://142.44.160.36:8000/history
- http://142.44.160.36:8000/history/1xbet
- http://142.44.160.36:8000/history/fanduel

### System Status
```
GET /api/status              - File status for all data sources
GET /api/monitoring          - Monitoring system health status
```

### Utilities
```
GET /api/betlink             - Format betlinks for specific regions
```

---

## 📝 Data Format Examples

### OpticOdds Format Structure
```json
{
  "data": [
    {
      "id": "185508415",
      "game_id": "nba-185508415",
      "start_date": "2025-11-29T02:40:00Z",
      "home_competitors": [{"name": "DEN Nuggets", "abbreviation": "NUGGETS"}],
      "away_competitors": [{"name": "SA Spurs", "abbreviation": "SPURS"}],
      "home_team_display": "DEN Nuggets",
      "away_team_display": "SA Spurs",
      "status": "unplayed",
      "is_live": false,
      "sport": {"id": "basketball", "name": "Basketball"},
      "league": {"id": "nba", "name": "NBA"},
      "odds": [
        {
          "sportsbook": "1xBet",
          "market": "Moneyline",
          "selection": "DEN Nuggets",
          "price": -150
        }
      ]
    }
  ]
}
```

### EternityLabs Format Structure
```json
{
  "data": [
    {
      "league": "NBA",
      "start_date": "2025-11-29T22:10:00Z",
      "book": "1xBet",
      "home": "MIN Timberwolves",
      "away": "BOS Celtics",
      "bet_team": "MIN Timberwolves",
      "market": "Point Spread",
      "line": 7.0,
      "am_odds": -109.0,
      "home_brief": "MT",
      "away_brief": "BC",
      "betlink": "https://..."
    }
  ]
}
```

---

## 🚀 How to Start the Web Server

### On VPS (Ubuntu):
```bash
cd /path/to/combine\ 1xbet,\ fanduel\ and\ bet365\ \(main\)
python3 live_odds_viewer_clean.py
```

### On Windows (Local):
```powershell
cd "c:\Users\User\Desktop\thesis\work related task\vps deploy\combine 1xbet, fanduel and bet365 (main)"
python live_odds_viewer_clean.py
```

The server will start on port 8000 and be accessible at:
- **Local**: http://localhost:8000
- **VPS**: http://142.44.160.36:8000

---

## 🔄 Data Update Frequency

The web server monitors the following files and updates automatically:
- `unified_odds.json` - Combined data from all sources
- `1xbet/1xbet_pregame.json` - 1xBet pregame data
- `1xbet/1xbet_live.json` - 1xBet live data
- `fanduel/fanduel_pregame.json` - FanDuel pregame data
- `fanduel/fanduel_live.json` - FanDuel live data
- `bet365/bet365_current_pregame.json` - Bet365 pregame data
- `bet365/bet365_live_current.json` - Bet365 live data
- `history.json` - Completed/historical matches

Updates are processed every 2 seconds when files change.

### 🧹 Automatic History Management

The system automatically cleans old/completed matches every 5 minutes:

**Pregame Matches** are moved to history when:
- Start time has passed (match should have started)

**Live Matches** are moved to history when:
- Status is "completed", "finished", "ended", or "final"
- Match hasn't been updated in 30 minutes (considered stale)

This keeps the main endpoints (/1xbet, /fanduel, etc.) showing only **active** matches and prevents duplicates or bloated data.

**Benefits:**
- ✅ Clean, current data on main endpoints
- ✅ No duplicate matches
- ✅ Historical data preserved in /history endpoint
- ✅ Automatic cleanup prevents 8000+ match issues

---

## 📊 Web UI

Access the interactive web interface at:
**http://142.44.160.36:8000/**

The UI provides:
- Real-time odds updates via WebSocket
- Filter by sport, bookmaker, and match type
- Visual comparison of odds across bookmakers
- File monitoring status
- System health dashboard

---

## ⚙️ Configuration

Current enabled scrapers (from `config.json`):
```json
{
  "enabled_scrapers": {
    "1xbet": true,      ✅ Active
    "fanduel": true,    ✅ Active
    "bet365": false     ❌ Disabled
  }
}
```

To enable/disable bookmakers, edit `config.json` and restart the unified system.

---

## 🔍 Testing Endpoints

Test if endpoints are working:

```bash
# Test 1xBet endpoint
curl http://142.44.160.36:8000/1xbet

# Test FanDuel pregame
curl http://142.44.160.36:8000/fanduel/pregame

# Test FanDuel live
curl http://142.44.160.36:8000/fanduel/live

# Test Eternity format
curl http://142.44.160.36:8000/1xbet/eternity
```

---

## 📝 Notes

1. **Default Format**: All `/1xbet`, `/fanduel`, `/bet365` endpoints return OpticOdds format by default
2. **Eternity Format**: Add `/eternity` suffix to get EternityLabs format
3. **Live Data**: Requires `--include-live` flag when starting the unified system
4. **Pregame Data**: Always collected by default
5. **CORS**: Server accepts requests from all origins for API access

---

## 🛠️ Troubleshooting

### No data returned?
- Check if scrapers are running: `ps aux | grep python`
- Check if data files exist in the respective folders
- Verify unified system is running with correct config

### Outdated data?
- Check `/api/status` to see when files were last updated
- Check `/api/monitoring` for scraper health status
- Restart scrapers if needed

### Server not accessible?
- Verify server is running on port 8000
- Check firewall rules allow port 8000
- Use `netstat -tulpn | grep 8000` to verify port is open

---

**Last Updated**: December 7, 2025
**Server Version**: 1.0.0
