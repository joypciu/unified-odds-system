# OddsMagnet Scraper Documentation

## Overview

A high-performance Python-based scraping solution for collecting betting odds data from OddsMagnet.com with **real-time updates every 30 seconds**. The system collects odds from **7 important betting markets** across **162 matches** from the **TOP 10 football leagues worldwide**.

### ✨ Key Features

- ✅ **Real-time data collection** (30-second updates, matches UI refresh)
- ✅ **Fast parallel fetching** (30 concurrent workers, 20 req/s)
- ✅ **Important markets only** (optimized for speed)
- ✅ **Automatic change detection** (tracks odds movements)
- ✅ **ETag caching** (efficient API responses)
- ✅ **162 matches** from TOP 10 leagues
- ✅ **~39,000 odds** collected per cycle

---

## 📁 Project Structure

### Core Production Files

```
bookmakers/oddsmagnet/
├── oddsmagnet_top10_realtime.py          # ⭐ TOP 10 leagues collector (30s updates)
├── oddsmagnet_master_realtime.py         # Master collector (all leagues)
├── oddsmagnet_basketball_realtime.py     # Basketball collector (60s updates)
├── oddsmagnet_baseball_realtime.py       # ⚾ Baseball collector (60s updates)
├── oddsmagnet_cricket_realtime.py        # Cricket collector (60s updates)
├── oddsmagnet_americanfootball_realtime.py # American Football collector (60s)
├── oddsmagnet_optimized_scraper.py       # Core scraper (concurrent)
├── oddsmagnet_optimized_collector.py     # Match fetcher
└── README_ODDSMAGNET.md                  # This file
```

### Data Output Files

```
├── oddsmagnet_top10.json                 # TOP 10 football leagues data (UI uses this)
├── oddsmagnet_basketball.json            # Basketball data
├── oddsmagnet_baseball.json              # ⚾ Baseball data (NEW!)
├── oddsmagnet_cricket.json               # Cricket data
├── oddsmagnet_americanfootball.json      # American Football data
└── oddsmagnet_realtime.json              # All leagues data (master)
```

### UI Integration

```
html/oddsmagnet_viewer.html               # Web UI (auto-refresh every 30s)
core/live_odds_viewer_clean.py            # Backend API server
```

---

## 🚀 Quick Start

### Installation

```bash
pip install requests beautifulsoup4
```

### TOP 10 Leagues Real-Time Collection (Recommended)

**Automatic 30-second updates optimized for UI:**

```bash
python bookmakers/oddsmagnet/oddsmagnet_top10_realtime.py
```

**Features:**

- **TOP 10 leagues**: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Europa League, Championship, Eredivisie, Primeira Liga
- **7 important markets**: Popular markets, Over/Under, Alternative goals, Corners, Cards, BTTS, HT/FT
- **30 concurrent workers** for fast parallel fetching
- **20 requests/second** rate limit
- **~39,000 odds** collected per cycle
- **98-second** average cycle time
- Graceful shutdown with Ctrl+C

**Output:**

- `oddsmagnet_top10.json` - Current odds (updated every 30 seconds)
- Atomic writes (prevents UI reading incomplete data)
- ETag support for efficient caching

### Master Collection (All Leagues)

**For collecting all available leagues:**

```bash
python bookmakers/oddsmagnet/oddsmagnet_master_realtime.py
```

**Features:**

- Collects from ALL available leagues
- Updates every 60 seconds
- Max 500 matches per update
- Same optimization (30 workers, 20 req/s)

---

## 📚 Detailed Usage

### TOP 10 Real-Time Collector (Primary Script)

**File:** `oddsmagnet_top10_realtime.py`

```python
# Run standalone
python bookmakers/oddsmagnet/oddsmagnet_top10_realtime.py
```

**Configuration:**

```python
class Top10RealtimeCollector:
    # Top 10 leagues
    TOP_10_LEAGUES = [
        'england-premier-league',
        'spain-laliga',
        'italy-serie-a',
        'germany-bundesliga',
        'france-ligue-1',
        'champions-league',
        'europe-uefa-europa-league',
        'england-championship',
        'netherlands-eredivisie',
        'portugal-primeira-liga'
    ]

    # Important markets (optimized for speed)
    IMPORTANT_MARKETS = [
        'popular markets',        # Match Winner, 1X2, BTTS
        'over under betting',     # Over/Under goals
        'alternative match goals',# Alternative goal lines
        'corners',               # Corner markets
        'cards',                 # Yellow/Red cards
        'both teams to score',   # BTTS
        'half time full time'    # HT/FT
    ]

# Performance settings
collector = Top10RealtimeCollector(
    max_workers=30,          # 30 concurrent workers
    requests_per_second=20.0 # 20 req/s rate limit
)

# Update interval: 30 seconds (matches UI refresh)
collector.run_realtime_loop(update_interval=30.0)
```

**Output Format:**

```json
{
  "timestamp": "2025-12-14T10:50:41.260448",
  "iteration": 1,
  "source": "oddsmagnet",
  "leagues": ["england-premier-league", "..."],
  "market_categories": ["popular markets", "..."],
  "total_matches": 162,
  "matches_processed": 162,
  "total_odds_collected": 39340,
  "matches": [
    {
      "match_name": "Manchester United v Liverpool",
      "league": "England Premier League",
      "match_uri": "football/england-premier-league/...",
      "match_date": "2025-12-15",
      "home_team": "Manchester United",
      "away_team": "Liverpool",
      "total_odds_collected": 245,
      "markets": {
        "popular markets": [...],
        "over under betting": [...],
        ...
      }
    }
  ]
}
```

### UI Integration

**Web UI:** `html/oddsmagnet_viewer.html`

**Features:**

- Auto-refresh every 30 seconds
- ETag caching for efficiency
- Progressive rendering
- Real-time odds change indicators
- League filtering
- Search functionality

**Start Full System:**

```bash
# Terminal 1: Start collector
python bookmakers/oddsmagnet/oddsmagnet_top10_realtime.py

# Terminal 2: Start backend API
python core/live_odds_viewer_clean.py

# Open browser
http://localhost:8000/oddsmagnet/top10
```

**Browser Console Logs:**

```javascript
// Initial load
⬇ Fetching fresh data from API...
📊 Data source: oddsmagnet
⏰ Data timestamp: 2025-12-14T10:50:41.260448
🔄 Iteration: 1
✓ Downloaded 162 matches - starting progressive render...
✓ Complete! Fresh data rendered in 245ms

// Subsequent refreshes (every 30s)
✓ 304 Not Modified - using cached data
✓ Loaded from cache in 12ms - 162 matches
```

### Verification

**Check Integration:**

```bash
python verify_ui_integration.py
```

This verifies:

- ✅ Data file exists and is fresh
- ✅ Backend API configured correctly
- ✅ UI uses correct endpoint
- ✅ Auto-refresh enabled
- ✅ Collector settings match UI

---

## 🔧 Advanced Usage

### 1. OddsMagnetMultiMarketScraper

**Purpose**: Scrape individual matches or leagues with full market control

#### Scrape Single Match with All Markets

```python
from oddsmagnet_multi_market_scraper import OddsMagnetMultiMarketScraper

scraper = OddsMagnetMultiMarketScraper()

match_data = scraper.scrape_match_all_markets(
    match_uri="football/spain-laliga/real-madrid-v-barcelona",
    match_name="Real Madrid v Barcelona",
    league_name="Spain La Liga",
    match_date="2025-12-20"
)

# Result: ~500-600 odds from ~68 markets
print(f"Collected {match_data['total_odds_collected']} odds")
```

#### Scrape League with Filtered Markets

```python
league_data = scraper.scrape_league(
    league_slug="spain-laliga",
    league_name="Spain La Liga",
    max_matches=10,
    market_filter=['popular markets', 'over under betting', 'both teams to score'],
    max_markets_per_category=5
)
```

#### Scrape Multiple Leagues

```python
data = scraper.scrape_multiple_leagues(
    league_list=['spain-laliga', 'england-premier-league', 'germany-bundesliga'],
    max_matches_per_league=5,
    market_filter=['popular markets'],
    max_markets_per_category=3
)
```

### 2. OddsMagnetCompleteCollector

**Purpose**: Comprehensive data collection across all leagues and matches

#### Get All Available Matches (No Odds)

```python
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector

collector = OddsMagnetCompleteCollector()

# Fast - just match metadata
all_matches = collector.get_all_matches_summary()

# Returns list of 807+ matches with:
# - league, league_slug
# - match_name, match_uri, match_slug
# - match_date
# - home_team, away_team
```

#### Filter Matches by Criteria

```python
# Get all matches from specific leagues
filtered = collector.filter_matches(
    matches=all_matches,
    leagues=['spain-laliga', 'england-premier-league'],
    date_from='2025-12-15',
    date_to='2025-12-31',
    limit=50
)
```

#### Collect Odds for All Matches

```python
# Collect from ALL leagues
data = collector.collect_all_matches_with_odds(
    leagues=None,  # None = all 117 leagues
    max_matches_per_league=None,  # None = all matches
    market_filter=None,  # None = all 69 markets
    max_markets_per_category=None,  # None = all markets
    save_interval=10  # Save progress every 10 matches
)

# Warning: This will take HOURS and collect 400,000+ odds!
```

#### Targeted Collection (Recommended)

```python
# Collect from major leagues only
data = collector.collect_all_matches_with_odds(
    leagues=[
        'spain-laliga',
        'england-premier-league',
        'germany-bundesliga',
        'italy-serie-a',
        'france-ligue-1'
    ],
    max_matches_per_league=10,
    market_filter=['popular markets', 'over under betting', 'both teams to score'],
    max_markets_per_category=5,
    save_interval=5
)

# More reasonable: ~50 matches × 15 markets × 8 odds = ~6,000 odds
```

#### Get Summary Organized by League

```python
summary = collector.get_matches_summary_by_league()

# Returns organized structure:
# {
#   'total_matches': 807,
#   'leagues': {
#     'spain laliga': {
#       'slug': 'spain-laliga',
#       'match_count': 20,
#       'matches': [...]
#     }
#   }
# }
```

---

## 🎯 Market Categories Available

OddsMagnet provides **69 betting markets** across **13 categories**:

| Category                  | Markets | Description                               |
| ------------------------- | ------- | ----------------------------------------- |
| **Popular Markets**       | 3       | Win Market, Draw No Bet, Correct Score    |
| **Handicap Betting**      | 8       | Asian Handicap, European, Timed Handicaps |
| **Over/Under Betting**    | 16      | Total Goals, Team Totals, Timed O/U       |
| **Both Teams to Score**   | 7       | Full Time, Half, Timed BTTS               |
| **Winner Sports Betting** | 7       | Win Both Halves, Win from Behind          |
| **Correct Score Betting** | 2       | 1st Half, 2nd Half Scores                 |
| **1st Half Markets**      | 6       | Winner, Totals, Team Scores               |
| **2nd Half Markets**      | 4       | Winner, Totals, Team Scores               |
| **Goals Exact Markets**   | 4       | Exact Home/Away/Half Goals                |

---

## 🎯 Tracked Bookmakers

OddsMagnet tracks **9 major bookmakers** with full name mapping:

| Code | Bookmaker Name | Type       |
| ---- | -------------- | ---------- |
| `bh` | Bet-at-Home    | Sportsbook |
| `eb` | 10Bet          | Sportsbook |
| `ee` | 888sport       | Sportsbook |
| `nt` | Netbet         | Sportsbook |
| `tn` | Tonybet        | Sportsbook |
| `vb` | Vbet           | Sportsbook |
| `vc` | BetVictor      | Sportsbook |
| `wh` | William Hill   | Sportsbook |
| `xb` | 1xBet          | Sportsbook |

**Total: 9 bookmakers per market**

---

## 📈 Market Categories

### Complete Market Coverage (69 Markets)

| Category               | Markets | Examples                              |
| ---------------------- | ------- | ------------------------------------- |
| **Popular Markets**    | 9       | Win Market, Both Teams to Score, etc. |
| **Over Under Betting** | 19      | Over 0.5-6.5 Goals, Asian Over/Under  |
| **Asian Handicap**     | 10      | Various handicap lines                |
| **European Handicap**  | 6       | +1, +2, +3 handicaps                  |
| **Correct Score**      | 5       | Exact Score, Score Bands              |
| **Halftime Betting**   | 2       | 1st Half Winner, Double Chance        |
| **Draw No Bet**        | 2       | Home/Away Draw No Bet                 |
| **To Score Odds**      | 5       | Team to Score, Both Halves            |
| **Win to Nil**         | 3       | Home/Away Win to Nil                  |
| **Odd/Even Betting**   | 3       | Full Time, 1st/2nd Half               |
| **Double Chance**      | 1       | Double Chance Market                  |

**Total: 69 markets per match**

---

## 📊 Data Output Structure

### Real-Time Odds Data (Enhanced)

```json
{
  "timestamp": "2025-12-11T10:30:15.123Z",
  "iteration": 42,
  "matches": [
    {
      "match_name": "Real Madrid v Barcelona",
      "league": "Spain La Liga",
      "match_date": "2025-12-20 20:00:00",
      "fetch_timestamp": "2025-12-11T10:30:15.123Z",
      "markets": {
        "popular markets": [
          {
            "market_name": "win market",
            "market_uri": "football/spain-laliga/real-madrid-v-barcelona/win-market",
            "selections_count": 3,
            "bookmakers_count": 9,
            "bookmakers": [
              { "code": "bh", "name": "Bet-at-Home" },
              { "code": "wh", "name": "William Hill" },
              { "code": "xb", "name": "1xBet" }
            ],
            "odds": [
              {
                "selection": "real madrid",
                "bookmaker_code": "bh",
                "bookmaker_name": "Bet-at-Home",
                "decimal_odds": 1.85,
                "fractional_odds": "17/20",
                "previous_odds": 1.9,
                "odds_movement": "down",
                "odds_change": 0.05,
                "is_best_odds": false,
                "clickout_url": "https://..."
              },
              {
                "selection": "real madrid",
                "bookmaker_code": "tn",
                "bookmaker_name": "Tonybet",
                "decimal_odds": 1.92,
                "previous_odds": 1.88,
                "odds_movement": "up",
                "odds_change": 0.04,
                "is_best_odds": true,
                "clickout_url": "https://..."
              }
            ],
            "market_best_odds": 1.92,
            "last_updated": "2025-12-11T10:30:00.000Z"
          }
        ]
      },
      "total_odds_collected": 580
    }
  ]
}
```

### Odds Change History

```json
{
  "total_changes": 847,
  "last_update": "2025-12-11T10:30:15.123Z",
  "changes": [
    {
      "timestamp": "2025-12-11T10:29:45.123Z",
      "match": "Real Madrid v Barcelona",
      "market": "win market",
      "selection": "real madrid",
      "bookmaker": "Tonybet",
      "previous_odds": 1.88,
      "current_odds": 1.92,
      "change": 0.04,
      "change_percent": 2.13
    }
  ]
}
```

### Match Summary (No Odds)

```json
{
  "league": "spain laliga",
  "league_slug": "spain-laliga",
  "match_name": "real madrid v barcelona",
  "match_uri": "football/spain-laliga/real-madrid-v-barcelona",
  "match_slug": "real-madrid-v-barcelona",
  "match_date": "2025-12-20 20:00:00",
  "home_team": "real madrid",
  "away_team": "barcelona",
  "sport": "football"
}
```

---

## 🔍 How It Works

### Architecture Overview

OddsMagnet uses a **pure API-driven architecture** (no HTML parsing needed):

```
1. Get Leagues → /api/events?sport_uri=football
   ↓
2. Get Matches → /api/subevents?event_uri=football/{league}
   ↓
3. Get Markets → /api/markets?subevent_uri=football/{league}/{match}
   ↓
4. Get Odds → /api/odds?market_uri={market_uri}
```

### API Endpoints

| Endpoint                                     | Purpose        | Returns      |
| -------------------------------------------- | -------------- | ------------ |
| `/api/events?sport_uri=football`             | All leagues    | 117 leagues  |
| `/api/subevents?event_uri=football/{league}` | League matches | 1-32 matches |
| `/api/markets?subevent_uri={match_uri}`      | Match markets  | 69 markets   |
| `/api/odds?market_uri={market_uri}`          | Market odds    | 1-200+ odds  |

### Session Management

The scraper uses proper session management to avoid 403 errors:

1. **Visit match page** to establish session
2. **Use persistent session** for all API calls
3. **Maintain proper headers** (User-Agent, Referer, etc.)
4. **Rate limiting** between requests

### Rate Limiting

To be server-friendly, the scraper implements delays:

- **0.3 seconds** between markets
- **1 second** between matches
- **2 seconds** between leagues

---

## ⚙️ Configuration Options

### Market Filtering

You can filter which market categories to collect:

```python
market_filter = [
    'popular markets',           # Main betting markets
    'over under betting',        # O/U markets
    'both teams to score',       # BTTS markets
    'handicap betting',          # Handicap markets
    # ... see full list above
]
```

### Limits

Control the scope of data collection:

```python
# Limit matches per league
max_matches_per_league = 10

# Limit markets per category
max_markets_per_category = 5

# Limit total matches
filtered_matches = collector.filter_matches(matches, limit=100)
```

### Progress Saving

For large collections, enable progress saving:

```python
data = collector.collect_all_matches_with_odds(
    save_interval=10  # Save every 10 matches
)

# Creates files: progress_10_matches.json, progress_20_matches.json, etc.
```

---

## 📈 Performance Metrics

### Speed

| Operation                        | Time      | Data Collected |
| -------------------------------- | --------- | -------------- |
| Get all leagues                  | ~2 sec    | 117 leagues    |
| Get all matches                  | ~25 sec   | 807 matches    |
| Single match (all markets)       | ~45 sec   | ~580 odds      |
| League (10 matches, all markets) | ~8 min    | ~5,800 odds    |
| Major 5 leagues (all markets)    | ~4 hours  | ~58,000 odds   |
| All leagues (all markets)        | ~36 hours | ~445,000 odds  |

### Data Volume

| Scope         | Matches | Markets | Odds     | File Size |
| ------------- | ------- | ------- | -------- | --------- |
| Single match  | 1       | 68      | ~580     | ~150 KB   |
| Single league | 20      | 1,360   | ~11,600  | ~3 MB     |
| Top 5 leagues | 100     | 6,800   | ~58,000  | ~15 MB    |
| All leagues   | 807     | 55,676  | ~445,000 | ~120 MB   |

---

## 🛠️ Advanced Features

### 1. Inspect OddsMagnet Structure

Use the inspector tool to analyze site structure:

```python
from deep_oddsmagnet_inspector import OddsMagnetInspector

inspector = OddsMagnetInspector()

# Deep inspect a match page
results = inspector.run_full_inspection(
    "https://oddsmagnet.com/football/spain-laliga/real-madrid-v-barcelona"
)

# Analyzes:
# - Page structure (HTML, JS, scripts)
# - API endpoints discovered
# - Market availability
# - JavaScript patterns
```

### 2. Custom Data Processing

Process collected data:

```python
import json

# Load collected data
with open('all_matches_summary.json', 'r') as f:
    matches = json.load(f)

# Find upcoming matches in next 7 days
from datetime import datetime, timedelta

now = datetime.now()
week_later = now + timedelta(days=7)

upcoming = [
    m for m in matches
    if now.isoformat() <= m['match_date'] <= week_later.isoformat()
]

# Group by date
by_date = {}
for match in upcoming:
    date = match['match_date'].split()[0]
    if date not in by_date:
        by_date[date] = []
    by_date[date].append(match)

for date, matches in sorted(by_date.items()):
    print(f"{date}: {len(matches)} matches")
```

### 3. Bookmaker Analysis

Analyze odds from specific bookmakers:

```python
def analyze_bookmaker_coverage(match_data):
    """Analyze which bookmakers have the most coverage"""
    bookmaker_counts = {}

    for category, markets in match_data['markets'].items():
        for market in markets:
            for odd in market['odds']:
                bookie = odd['bookmaker']
                bookmaker_counts[bookie] = bookmaker_counts.get(bookie, 0) + 1

    # Sort by coverage
    sorted_bookies = sorted(bookmaker_counts.items(), key=lambda x: x[1], reverse=True)

    for bookie, count in sorted_bookies:
        print(f"{bookie}: {count} odds")
```

---

## 🔧 Potential Improvements

### 1. Database Integration

**Current**: Saves to JSON files  
**Improvement**: Store in PostgreSQL/MongoDB

```python
# Suggested schema
matches_table:
  - id, league_id, match_uri, match_name, match_date
  - home_team, away_team, status

markets_table:
  - id, match_id, category, market_name, market_uri

odds_table:
  - id, market_id, bookmaker, selection, decimal_odds
  - fractional_odds, timestamp, clickout_url
```

**Benefits**:

- Efficient querying
- Historical tracking
- Relationship management
- Scalability

### 2. Incremental Updates

**Current**: Full re-scrape each time  
**Improvement**: Only update changed odds

```python
def get_updated_odds(previous_data, current_data):
    """Compare and return only changed odds"""
    changes = []

    for match in current_data:
        old_match = find_match(previous_data, match['match_uri'])
        if not old_match:
            changes.append({'type': 'new_match', 'data': match})
            continue

        # Compare odds
        old_odds = extract_all_odds(old_match)
        new_odds = extract_all_odds(match)

        if old_odds != new_odds:
            changes.append({
                'type': 'odds_update',
                'match': match['match_uri'],
                'changes': diff_odds(old_odds, new_odds)
            })

    return changes
```

**Benefits**:

- Faster updates
- Lower bandwidth
- Track changes over time

### 3. Parallel Processing

**Current**: Sequential scraping  
**Improvement**: Concurrent requests

```python
import asyncio
import aiohttp

async def scrape_multiple_matches_async(match_uris):
    """Scrape multiple matches concurrently"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            scrape_match_async(session, uri)
            for uri in match_uris
        ]
        results = await asyncio.gather(*tasks)
    return results

# Usage
matches = asyncio.run(scrape_multiple_matches_async(match_list))
```

**Benefits**:

- 5-10x faster
- Process multiple leagues simultaneously
- Better resource utilization

### 4. Caching Layer

**Current**: No caching  
**Improvement**: Redis/Memcached caching

```python
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def get_match_markets_cached(match_uri, ttl=300):
    """Get markets with 5-minute cache"""
    cache_key = f"markets:{match_uri}"

    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch fresh
    markets = api_get_markets(match_uri)

    # Cache for TTL seconds
    cache.setex(cache_key, ttl, json.dumps(markets))

    return markets
```

**Benefits**:

- Reduce API calls
- Faster responses
- Lower server load

### 5. Real-time Updates

**Current**: Manual trigger  
**Improvement**: WebSocket or polling

```python
class OddsMonitor:
    """Monitor odds changes in real-time"""

    def __init__(self, matches_to_monitor):
        self.matches = matches_to_monitor
        self.previous_odds = {}

    async def monitor_loop(self, interval=60):
        """Check for updates every interval seconds"""
        while True:
            for match_uri in self.matches:
                current_odds = await self.fetch_odds(match_uri)

                if match_uri in self.previous_odds:
                    changes = self.detect_changes(
                        self.previous_odds[match_uri],
                        current_odds
                    )

                    if changes:
                        await self.notify_changes(match_uri, changes)

                self.previous_odds[match_uri] = current_odds

            await asyncio.sleep(interval)
```

**Benefits**:

- Live odds tracking
- Immediate change notifications
- Arbitrage opportunities

### 6. Error Recovery

**Current**: Basic error handling  
**Improvement**: Comprehensive retry logic

```python
import tenacity

@tenacity.retry(
    retry=tenacity.retry_if_exception_type(requests.RequestException),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
    stop=tenacity.stop_after_attempt(3),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
)
def robust_api_call(url, **kwargs):
    """API call with exponential backoff retry"""
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.json()
```

**Benefits**:

- Handle temporary failures
- Automatic retry with backoff
- Better reliability

### 7. Data Validation

**Current**: Minimal validation  
**Improvement**: Schema validation

```python
from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime

class OddsData(BaseModel):
    selection: str
    bookmaker: str
    decimal_odds: float
    fractional_odds: Optional[str]

    @validator('decimal_odds')
    def validate_odds(cls, v):
        if v < 1.0:
            raise ValueError('Odds must be >= 1.0')
        return v

class MarketData(BaseModel):
    market_name: str
    market_uri: str
    selections_count: int
    odds: List[OddsData]

class MatchData(BaseModel):
    match_name: str
    match_date: datetime
    markets: dict
    total_odds_collected: int
```

**Benefits**:

- Data integrity
- Early error detection
- Type safety

### 8. Logging and Monitoring

**Current**: Print statements  
**Improvement**: Structured logging

```python
import logging
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Usage
logger.info(
    "match_scraped",
    match_uri=match_uri,
    odds_collected=len(odds),
    duration_seconds=elapsed_time,
    success=True
)
```

**Benefits**:

- Better debugging
- Performance tracking
- Error analysis

### 9. API Abstraction

**Current**: Direct API calls  
**Improvement**: API client class

```python
class OddsMagnetAPI:
    """Clean API abstraction layer"""

    def __init__(self, base_url="https://oddsmagnet.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_leagues(self, sport='football'):
        """Get all leagues for a sport"""
        return self._request(f'/api/events?sport_uri={sport}')

    def get_matches(self, league_slug):
        """Get matches for a league"""
        return self._request(f'/api/subevents?event_uri=football/{league_slug}')

    def get_markets(self, match_uri):
        """Get markets for a match"""
        return self._request(f'/api/markets?subevent_uri={match_uri}')

    def get_odds(self, market_uri):
        """Get odds for a market"""
        return self._request(f'/api/odds?market_uri={market_uri}')

    def _request(self, endpoint, **kwargs):
        """Internal request handler with error handling"""
        # Implementation with retries, logging, etc.
```

**Benefits**:

- Cleaner code
- Centralized error handling
- Easier testing

### 10. Configuration Management

**Current**: Hardcoded values  
**Improvement**: Config file

```yaml
# config.yaml
oddsmagnet:
  rate_limits:
    between_markets: 0.3
    between_matches: 1.0
    between_leagues: 2.0

  timeouts:
    session_establish: 15
    api_call: 10

  defaults:
    max_matches_per_league: 10
    save_interval: 10

  market_categories:
    priority:
      - popular markets
      - over under betting
      - both teams to score

    optional:
      - handicap betting
      - correct score betting
```

**Benefits**:

- Easy configuration changes
- Environment-specific settings
- No code modification needed

---

## 🐛 Troubleshooting

### Issue: 403 Forbidden Errors

**Cause**: Invalid session or missing headers  
**Solution**: Ensure session establishment before API calls

```python
# Always establish session first
scraper.establish_session(match_url)
```

### Issue: Timeout Errors

**Cause**: Slow network or server  
**Solution**: Increase timeout values

```python
response = requests.get(url, timeout=30)  # Increase from 10 to 30
```

### Issue: Empty Odds Data

**Cause**: Market not available or match past  
**Solution**: Check match date and market availability

```python
if match_date < datetime.now():
    print("Match already played - odds may be unavailable")
```

### Issue: Rate Limiting (429)

**Cause**: Too many requests  
**Solution**: Increase delays between requests

```python
time.sleep(2)  # Increase delay
```

---

## 📝 Best Practices

1. **Start Small**: Test with 1-2 matches before scaling up
2. **Use Filters**: Don't collect all 69 markets unless needed
3. **Save Progress**: Use `save_interval` for large collections
4. **Monitor Performance**: Track API response times
5. **Handle Errors**: Always wrap API calls in try-except
6. **Be Polite**: Respect rate limits and server resources
7. **Cache Data**: Don't re-fetch unchanged data
8. **Validate Output**: Check data quality after collection

---

## 📞 Support

For issues or questions:

1. Check this README
2. Review `ODDSMAGNET_SOLUTION_SUMMARY.md` for technical details
3. Examine the code comments
4. Use the inspector tool for debugging

---

## 📄 License

Part of the Unified Odds System project.

---

## 🔄 Version History

**v1.0** (December 2025)

- Initial release
- Multi-market scraping (69 markets)
- Complete collector (807+ matches, 117+ leagues)
- Deep inspection tools
- Comprehensive documentation

---

## 🎓 Learning Resources

### Understanding the API

1. Use `deep_oddsmagnet_inspector.py` to analyze site structure
2. Check browser DevTools Network tab when visiting OddsMagnet
3. Review API response JSON files in the data directory

### Code Examples

See the `__main__` sections in:

- `oddsmagnet_multi_market_scraper.py` - Basic scraping examples
- `oddsmagnet_complete_collector.py` - Advanced collection examples

### Data Structure

Refer to the JSON output files:

- `all_matches_summary.json` - Match metadata structure
- `all_leagues.json` - League structure
- `matches_by_league_summary.json` - Organized data structure

---

**Last Updated**: December 11, 2025  
**Tested With**: OddsMagnet.com as of December 2025
