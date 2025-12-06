# API Reference - Unified Odds System

Complete reference for all API endpoints provided by the Unified Odds System.

## Base URL

- **Production VPS**: `http://142.44.160.36:8000`
- **Local Development**: `http://localhost:8000`

## OpticOdds Format Endpoints

All endpoints return data in OpticOdds-compatible format with the following structure:

```json
{
  "data": [
    {
      "id": "unique_match_id",
      "game_id": "sport-match_id",
      "start_date": "2025-12-06T10:00:00Z",
      "home_competitors": [{"id": null, "name": "Home Team", "abbreviation": "HT", "logo": null}],
      "away_competitors": [{"id": null, "name": "Away Team", "abbreviation": "AT", "logo": null}],
      "home_team_display": "Home Team",
      "away_team_display": "Away Team",
      "status": "unplayed" | "live",
      "is_live": false,
      "sport": {"id": "sport_id", "name": "Sport Name"},
      "league": {"id": "league_id", "name": "League Name"},
      "tournament": null,
      "odds": [...]
    }
  ]
}
```

### Odds Object Structure

Each odds object in the `odds` array:

```json
{
  "id": "match_id:sportsbook:market_id:selection",
  "sportsbook": "Bet365" | "FanDuel" | "1xBet",
  "market": "Moneyline" | "Point Spread" | "Total Points",
  "name": "Team Name" | "Over 200.5" | "Under 200.5",
  "is_main": true,
  "selection": "Team Name" | "" (for totals),
  "normalized_selection": "team_name",
  "market_id": "moneyline" | "spread" | "total",
  "selection_line": null | "over" | "under",
  "player_id": null,
  "team_id": null,
  "price": -110,  // American odds format
  "timestamp": 1733472000.0,
  "grouping_key": "default" | "default:7.5",
  "points": null | 7.5,  // Spread/total line value
  "betlink": "",
  "limits": null
}
```

---

## 1xBet Endpoints

### GET /1xbet
Returns all 1xBet odds (pregame + live matches).

**Response:**
- Total games: ~2,000-2,500
- Response time: 10-15 seconds

**Example:**
```bash
curl http://142.44.160.36:8000/1xbet
```

### GET /1xbet/pregame
Returns only 1xBet pregame matches.

**Response:**
- Total games: ~1,200-1,500
- Response time: 2-3 seconds

**Example:**
```bash
curl http://142.44.160.36:8000/1xbet/pregame
```

### GET /1xbet/live
Returns only 1xBet live matches.

**Response:**
- Total games: ~800-1,000
- Response time: 7-10 seconds

**Example:**
```bash
curl http://142.44.160.36:8000/1xbet/live
```

---

## FanDuel Endpoints

### GET /fanduel
Returns all FanDuel odds (pregame + live matches).

**Example:**
```bash
curl http://142.44.160.36:8000/fanduel
```

### GET /fanduel/pregame
Returns only FanDuel pregame matches.

**Example:**
```bash
curl http://142.44.160.36:8000/fanduel/pregame
```

### GET /fanduel/live
Returns only FanDuel live matches.

**Example:**
```bash
curl http://142.44.160.36:8000/fanduel/live
```

---

## Bet365 Endpoints

### GET /bet365
Returns all Bet365 odds (pregame + live matches).

**Example:**
```bash
curl http://142.44.160.36:8000/bet365
```

### GET /bet365/pregame
Returns only Bet365 pregame matches.

**Example:**
```bash
curl http://142.44.160.36:8000/bet365/pregame
```

### GET /bet365/live
Returns only Bet365 live matches.

**Example:**
```bash
curl http://142.44.160.36:8000/bet365/live
```

### GET /bet365/soccer
Returns only Bet365 soccer/football matches (pregame + live).

**Example:**
```bash
curl http://142.44.160.36:8000/bet365/soccer
```

---

## Eternity Format Endpoints

Alternative format for odds data.

### GET /eternity/1xbet
Returns all 1xBet odds in Eternity format.

**Example:**
```bash
curl http://142.44.160.36:8000/eternity/1xbet
```

### GET /eternity/fanduel
Returns all FanDuel odds in Eternity format.

**Example:**
```bash
curl http://142.44.160.36:8000/eternity/fanduel
```

### GET /eternity/bet365
Returns all Bet365 odds in Eternity format.

**Example:**
```bash
curl http://142.44.160.36:8000/eternity/bet365
```

---

## Legacy Unified Format Endpoints

Original unified format endpoints (still supported).

### GET /api/matches
Returns all matches in unified format.

**Response Structure:**
```json
{
  "metadata": {
    "generated_at": "2025-12-06T07:00:00Z",
    "sources": ["bet365", "fanduel", "1xbet"],
    "total_pregame_matches": 1200,
    "total_live_matches": 800
  },
  "pregame_matches": [...],
  "live_matches": [...]
}
```

### GET /api/matches/pregame
Returns only pregame matches.

### GET /api/matches/live
Returns only live matches.

### GET /api/matches/sport/{sport}
Returns matches for specific sport.

**Sports:** `basketball`, `football`, `soccer`, `hockey`, `baseball`, `tennis`, etc.

**Example:**
```bash
curl http://142.44.160.36:8000/api/matches/sport/basketball
```

### GET /api/matches/bookmaker/{bookmaker}
Returns matches from specific bookmaker.

**Bookmakers:** `1xbet`, `fanduel`, `bet365`

**Example:**
```bash
curl http://142.44.160.36:8000/api/matches/bookmaker/1xbet
```

---

## System Status Endpoints

### GET /api/status
Returns file system status for all data files.

**Response:**
```json
{
  "unified": {
    "exists": true,
    "size": 1845678,
    "modified": 1733472000
  },
  "bet365_pregame": {...},
  "bet365_live": {...},
  "fanduel_pregame": {...},
  "fanduel_live": {...},
  "1xbet_pregame": {...},
  "1xbet_live": {...}
}
```

### GET /api/monitoring
Returns monitoring system status.

**Response:**
```json
{
  "monitoring_active": true,
  "last_updated": "2025-12-06T07:00:00",
  "summary": {
    "healthy": 3,
    "warnings": 0,
    "errors": 0,
    "total": 3
  },
  "modules": {...}
}
```

---

## WebSocket Endpoint

### WS /ws
Real-time WebSocket connection for live updates.

**Messages:**
- `data_update`: New odds data available
- `status_update`: File status changed

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://142.44.160.36:8000/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'data_update') {
    console.log('New odds data:', message.data);
  }
};
```

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 404 | Endpoint not found |
| 500 | Internal server error |

---

## Rate Limiting

Currently no rate limiting implemented. Recommended:
- Max 60 requests per minute per IP
- Max 10 concurrent connections per IP

---

## Data Freshness

- **1xBet**: Updated every 30 seconds
- **FanDuel**: Updated every 60 seconds  
- **Bet365**: Updated every 60 seconds
- **Unified JSON**: Regenerated after each bookmaker update

---

## Performance Notes

### Response Times (Approximate)

| Endpoint | Games | Response Time |
|----------|-------|---------------|
| `/1xbet` | 2,000+ | 10-15s |
| `/1xbet/pregame` | 1,200+ | 2-3s |
| `/1xbet/live` | 800+ | 7-10s |
| `/fanduel/pregame` | 500+ | 2-3s |
| `/bet365/pregame` | 50+ | 1-2s |

**Note:** Large responses are slower due to JSON serialization. Use specific endpoints (pregame/live) for better performance.

---

## Example Integration (Python)

```python
import requests

# Get 1xBet pregame odds
response = requests.get('http://142.44.160.36:8000/1xbet/pregame')
data = response.json()

# Process games
for game in data['data']:
    print(f"{game['away_team_display']} @ {game['home_team_display']}")
    print(f"Sport: {game['sport']['name']}")
    print(f"League: {game['league']['name']}")
    
    # Process odds
    for odd in game['odds']:
        if odd['market'] == 'Moneyline':
            print(f"  {odd['name']}: {odd['price']}")
```

---

## Example Integration (JavaScript)

```javascript
// Fetch 1xBet pregame odds
fetch('http://142.44.160.36:8000/1xbet/pregame')
  .then(response => response.json())
  .then(data => {
    data.data.forEach(game => {
      console.log(`${game.away_team_display} @ ${game.home_team_display}`);
      
      game.odds.forEach(odd => {
        if (odd.market === 'Moneyline') {
          console.log(`  ${odd.name}: ${odd.price}`);
        }
      });
    });
  });
```

---

## Support

For issues or questions:
- GitHub: https://github.com/Eternity-Labs-BD/unified-odds-system
- Check logs: `sudo journalctl -u unified-odds-ui -n 50`
- Service status: `sudo systemctl status unified-odds-ui`
