# 🎓 Unified Odds System - Complete Tutorial

A comprehensive guide to understanding how the Unified Odds System with OddsMagnet integration works.

---

## 📋 Table of Contents

1. [System Overview](#-system-overview)
2. [Architecture & Components](#-architecture--components)
3. [Data Flow](#-data-flow)
4. [How It Works Step-by-Step](#-how-it-works-step-by-step)
5. [Key Components Explained](#-key-components-explained)
6. [OddsMagnet Integration](#-oddsmagnet-integration)
7. [Running the System](#-running-the-system)
8. [API & Data Access](#-api--data-access)
9. [Monitoring & Health Checks](#-monitoring--health-checks)
10. [Troubleshooting](#-troubleshooting)

---

## 🎯 System Overview

### What is the Unified Odds System?

The Unified Odds System is a **real-time sports betting odds aggregator** that:

- **Scrapes odds** from multiple bookmakers (1xBet, FanDuel, Bet365, OddsMagnet)
- **Normalizes team names** to eliminate duplicates
- **Merges data** into a unified database where each match shows odds from all bookmakers
- **Updates in real-time** (1-second intervals for live matches)
- **Provides REST API** for easy data access
- **Monitors health** and sends alerts on failures

### Key Features

✅ **Multi-Bookmaker Support**: 1xBet, FanDuel, Bet365, OddsMagnet (9 bookmakers via OddsMagnet)  
✅ **117+ Leagues**: Football, Basketball, Tennis, Cricket, and more  
✅ **Real-Time Updates**: Live odds refresh every 1-2 seconds  
✅ **Smart Deduplication**: Handles "Man City" vs "Manchester City" automatically  
✅ **REST API**: FastAPI web server with JSON endpoints  
✅ **Web Dashboard**: Real-time UI for viewing odds  
✅ **Auto-Monitoring**: Health checks, email alerts, auto-restart  
✅ **Modular Design**: Easy to add new bookmakers

---

## 🏗️ Architecture & Components

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED ODDS SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │           LAUNCH SYSTEM (launch_odds_system.py)           │ │
│  │  • Master launcher - starts all components                │ │
│  │  • Process management & cleanup                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                            │                                    │
│          ┌─────────────────┼─────────────────┐                │
│          ▼                 ▼                 ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   SCRAPERS   │  │   UNIFIED    │  │  MONITORING  │        │
│  │              │  │   COLLECTOR  │  │    SYSTEM    │        │
│  │ • 1xBet      │  │              │  │              │        │
│  │ • FanDuel    │  │ • Merges     │  │ • Health     │        │
│  │ • Bet365     │  │   data       │  │   checks     │        │
│  │ • OddsMagnet │  │ • Normalizes │  │ • Alerts     │        │
│  │              │  │   teams      │  │              │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│          │                 │                 │                 │
│          └─────────────────┼─────────────────┘                │
│                            ▼                                    │
│                 ┌────────────────────┐                         │
│                 │   DATA OUTPUTS     │                         │
│                 │                    │                         │
│                 │ • unified_odds.json│                         │
│                 │ • cache_data.json  │                         │
│                 │ • status.json      │                         │
│                 └────────────────────┘                         │
│                            │                                    │
│                            ▼                                    │
│                 ┌────────────────────┐                         │
│                 │   WEB SERVER       │                         │
│                 │   (FastAPI)        │                         │
│                 │                    │                         │
│                 │ • REST API         │                         │
│                 │ • Dashboard UI     │                         │
│                 └────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### Folder Structure

```
unified-odds-system/
│
├── bookmakers/              # Individual bookmaker scrapers
│   ├── 1xbet/              # 1xBet scraper (pregame + live)
│   ├── bet365/             # Bet365 scraper (pregame + live)
│   ├── fanduel/            # FanDuel scraper (pregame + live)
│   └── oddsmagnet/         # OddsMagnet multi-sport scraper
│
├── core/                   # Core system components
│   ├── launch_odds_system.py       # Master launcher
│   ├── run_unified_system.py       # Main orchestrator
│   ├── unified_odds_collector.py   # Data merger
│   ├── monitoring_system.py        # Health monitoring
│   └── live_odds_viewer_clean.py   # FastAPI web server
│
├── utils/                  # Utility modules
│   ├── cache_manager/      # Smart caching & deduplication
│   ├── converters/         # Data format converters
│   ├── helpers/            # Helper functions
│   └── mappers/            # Team/sport name mappers
│
├── data/                   # Runtime data
│   ├── unified_odds.json   # Main output (all bookmakers merged)
│   ├── cache_data.json     # Team/sport name cache
│   └── monitoring_status.json  # Health status
│
└── config/                 # Configuration
    ├── config.json         # System settings (encrypted)
    └── requirements.txt    # Python dependencies
```

---

## 🔄 Data Flow

### Complete Data Pipeline

```
STEP 1: SCRAPING
┌──────────────┐
│  Bookmakers  │
└──────────────┘
       │
       ├─→ 1xBet Scraper ─────→ 1xbet_pregame.json
       │                        1xbet_live.json
       │
       ├─→ FanDuel Scraper ───→ fanduel_pregame.json
       │                        fanduel_live.json
       │
       ├─→ Bet365 Scraper ────→ bet365_current_pregame.json
       │                        bet365_live_current.json
       │
       └─→ OddsMagnet Scraper → oddsmagnet_football.json
                                oddsmagnet_basketball.json
                                (+ 7 more sports)

       ▼

STEP 2: MONITORING (Realtime File Watcher)
┌───────────────────────────┐
│ RealtimeUnifiedCollector  │
│ • Watches source files    │
│ • Detects changes (0.5s)  │
│ • Triggers updates        │
└───────────────────────────┘
       │
       ▼

STEP 3: NORMALIZATION & MERGING
┌───────────────────────────┐
│  UnifiedOddsCollector     │
│                           │
│ • Load all source files   │
│ • Normalize team names    │
│ • Deduplicate matches     │
│ • Merge bookmaker odds    │
└───────────────────────────┘
       │
       ├─→ Enhanced Cache Manager
       │   • Smart team matching
       │   • "Man City" → "Manchester City"
       │   • Fuzzy matching (80% threshold)
       │
       └─→ Sport Name Mapper
           • "Football" → "Soccer"
           • Cross-source standardization

       ▼

STEP 4: OUTPUT
┌───────────────────────────┐
│   unified_odds.json       │
│                           │
│ {                         │
│   "Liverpool vs Man Utd": │
│     {                     │
│       "sport": "Soccer",  │
│       "league": "EPL",    │
│       "odds": {           │
│         "1xbet": {...},   │
│         "fanduel": {...}, │
│         "bet365": {...}   │
│       }                   │
│     }                     │
│ }                         │
└───────────────────────────┘
       │
       ▼

STEP 5: WEB SERVER (FastAPI)
┌───────────────────────────┐
│  live_odds_viewer_clean   │
│                           │
│ • Serves unified_odds.json│
│ • REST API endpoints      │
│ • Web dashboard UI        │
│ • Real-time updates       │
└───────────────────────────┘
       │
       ▼

STEP 6: ACCESS
• http://localhost:8000/
• http://localhost:8000/api/matches
• http://localhost:8000/1xbet/pregame
• http://localhost:8000/oddsmagnet/football
```

---

## ⚙️ How It Works Step-by-Step

### Phase 1: System Launch

**File**: `core/launch_odds_system.py`

```bash
python core/launch_odds_system.py --include-live
```

**What happens:**

1. **Process Management Setup**

   - Registers signal handlers (CTRL+C cleanup)
   - Creates process tracker list
   - Sets up atexit cleanup hooks

2. **Launches Components** (in order):

   ```python
   # Component 1: Monitoring System
   processes.append(subprocess.Popen([python, "core/monitoring_system.py"]))

   # Component 2: Unified Collector (Main System)
   processes.append(subprocess.Popen([
       python, "core/run_unified_system.py",
       "--mode", "realtime",
       "--include-live"
   ]))

   # Component 3: Web Server (FastAPI)
   processes.append(subprocess.Popen([python, "core/live_odds_viewer_clean.py"]))
   ```

3. **Health Monitoring Loop**
   - Checks if processes are alive every 5 seconds
   - Auto-restarts crashed components
   - Logs process status

### Phase 2: Individual Scrapers Run

**Files**: Various scraper files in `bookmakers/*/`

#### 1xBet Scraper

- **File**: `bookmakers/1xbet/1xbet_pregame.py`, `1xbet_live.py`
- **Technology**: Selenium WebDriver
- **Update Frequency**:
  - Pregame: Every 60 seconds
  - Live: Every 1-2 seconds
- **Output**: `1xbet_pregame.json`, `1xbet_live.json`

#### FanDuel Scraper

- **File**: `bookmakers/fanduel/fanduel_scraper.py`
- **Technology**: Requests + JSON API
- **Update Frequency**: Every 30 seconds
- **Output**: `fanduel_pregame.json`, `fanduel_live.json`

#### Bet365 Scraper

- **File**: `bookmakers/bet365/bet365_scraper.py`
- **Technology**: Selenium WebDriver
- **Update Frequency**: Every 45 seconds
- **Output**: `bet365_current_pregame.json`, `bet365_live_current.json`

#### OddsMagnet Scraper

- **File**: `bookmakers/oddsmagnet/parallel_sports_scraper.py`
- **Technology**: Async HTTP + Multiprocessing
- **Update Frequency**: Every 60 seconds
- **Output**: One file per sport (9 sports total)
  - `oddsmagnet_football.json` (117 leagues)
  - `oddsmagnet_basketball.json`
  - `oddsmagnet_tennis.json`
  - etc.

**Example Scraper Output** (1xbet_pregame.json):

```json
{
  "metadata": {
    "last_update": "2025-12-31T10:30:00",
    "total_matches": 1250,
    "sport": "Soccer"
  },
  "matches": [
    {
      "match_id": "12345",
      "home_team": "Liverpool",
      "away_team": "Manchester United",
      "league": "Premier League",
      "start_time": "2025-12-31T15:00:00",
      "odds": {
        "home": 1.85,
        "draw": 3.4,
        "away": 4.2
      }
    }
  ]
}
```

### Phase 3: Real-Time File Monitoring

**File**: `core/run_unified_system.py` → `RealtimeUnifiedCollector`

**What happens:**

1. **File Watcher Initialization**

   ```python
   # Monitors these files:
   files_to_watch = [
       "bookmakers/1xbet/1xbet_pregame.json",
       "bookmakers/1xbet/1xbet_live.json",
       "bookmakers/fanduel/fanduel_pregame.json",
       "bookmakers/fanduel/fanduel_live.json",
       "bookmakers/bet365/bet365_current_pregame.json",
       "bookmakers/bet365/bet365_live_current.json",
       "bookmakers/oddsmagnet/oddsmagnet_football.json",
       # ... more files
   ]
   ```

2. **Change Detection** (every 0.5 seconds)

   ```python
   def check_for_updates(self):
       for file_path in files_to_watch:
           current_mtime = os.path.getmtime(file_path)
           if current_mtime > self.last_modified[file_path]:
               # File changed! Trigger update
               self.trigger_unified_update()
   ```

3. **Rate Limiting**
   - Minimum 0.5 seconds between updates
   - Prevents too-frequent rebuilds

### Phase 4: Data Normalization & Merging

**File**: `core/unified_odds_collector.py` → `UnifiedOddsCollector`

This is the **BRAIN** of the system!

#### Step 4.1: Load Source Data

```python
def collect_unified_odds(self):
    # Load all sources
    bet365_pregame = self.load_json(self.bet365_pregame_file)
    bet365_live = self.load_json(self.bet365_live_file)
    fanduel_pregame = self.load_json(self.fanduel_pregame_file)
    fanduel_live = self.load_json(self.fanduel_live_file)
    xbet_pregame = self.load_json(self.xbet_pregame_file)
    xbet_live = self.load_json(self.xbet_live_file)
```

#### Step 4.2: Normalize Team Names

**Problem**: Different bookmakers use different team names

- 1xBet: "Manchester City"
- FanDuel: "Man City"
- Bet365: "Man City FC"

**Solution**: Enhanced Cache Manager with intelligent matching

```python
def normalize_team_name(self, team_name: str, source: str) -> str:
    # Uses cache lookup (O(1) speed)
    canonical = self.cache_manager.get_canonical_name(team_name, source)

    # If not in cache, apply smart matching:
    # 1. Remove suffixes (FC, United, City, etc.)
    # 2. Expand abbreviations (Man → Manchester)
    # 3. Fuzzy match against known teams (80% threshold)
    # 4. Update cache with result

    return canonical  # All sources now use same name!
```

**Example Cache Entry**:

```json
{
  "teams": {
    "Manchester City": {
      "canonical_name": "Manchester City",
      "aliases": [
        "Man City",
        "Man City FC",
        "Manchester City FC",
        "Man City (W)"
      ],
      "sources": ["1xbet", "fanduel", "bet365"]
    }
  }
}
```

#### Step 4.3: Sport Name Normalization

```python
def normalize_sport_name(self, sport: str) -> str:
    # Maps across sources
    mappings = {
        "football": "Soccer",      # 1xBet uses "Football"
        "soccer": "Soccer",         # FanDuel uses "soccer"
        "basketball": "NBA",
        "ice hockey": "NHL"
    }
    return mappings.get(sport.lower(), sport)
```

#### Step 4.4: Match Deduplication

**Algorithm**:

```python
def create_match_key(self, home, away, sport, start_time):
    # Create unique key for matching
    # Same match from different bookmakers = same key

    home = self.normalize_team_name(home)
    away = self.normalize_team_name(away)
    sport = self.normalize_sport_name(sport)

    return f"{sport}|{home} vs {away}|{start_time}"
```

**Example**:

```
1xBet:   "Soccer|Manchester City vs Liverpool|2025-12-31T15:00"
FanDuel: "Soccer|Manchester City vs Liverpool|2025-12-31T15:00"
Bet365:  "Soccer|Manchester City vs Liverpool|2025-12-31T15:00"
         ↓
         SAME KEY → MERGED INTO ONE MATCH
```

#### Step 4.5: Merge Odds from All Sources

```python
def merge_match_data(self, match_key, sources):
    unified_match = {
        "match_id": match_key,
        "sport": normalized_sport,
        "home_team": canonical_home,
        "away_team": canonical_away,
        "league": league_name,
        "start_time": start_time,
        "odds": {}
    }

    # Add odds from each bookmaker
    if "1xbet" in sources:
        unified_match["odds"]["1xbet"] = {
            "home": 1.85,
            "draw": 3.40,
            "away": 4.20
        }

    if "fanduel" in sources:
        unified_match["odds"]["fanduel"] = {
            "home": 1.90,
            "draw": 3.30,
            "away": 4.10
        }

    if "bet365" in sources:
        unified_match["odds"]["bet365"] = {
            "home": 1.88,
            "draw": 3.35,
            "away": 4.15
        }

    return unified_match
```

#### Step 4.6: Generate Output

**Output File**: `data/unified_odds.json`

```json
{
  "metadata": {
    "last_update": "2025-12-31T10:35:00",
    "total_matches": 3420,
    "sources": ["1xbet", "fanduel", "bet365", "oddsmagnet"],
    "sports_count": 12
  },
  "matches": [
    {
      "match_id": "Soccer|Manchester City vs Liverpool|2025-12-31T15:00",
      "sport": "Soccer",
      "league": "Premier League",
      "home_team": "Manchester City",
      "away_team": "Liverpool",
      "start_time": "2025-12-31T15:00:00",
      "status": "upcoming",
      "odds": {
        "1xbet": {
          "home": 1.85,
          "draw": 3.4,
          "away": 4.2,
          "last_update": "2025-12-31T10:34:55"
        },
        "fanduel": {
          "home": 1.9,
          "draw": 3.3,
          "away": 4.1,
          "last_update": "2025-12-31T10:34:50"
        },
        "bet365": {
          "home": 1.88,
          "draw": 3.35,
          "away": 4.15,
          "last_update": "2025-12-31T10:34:48"
        }
      },
      "best_odds": {
        "home": { "bookmaker": "fanduel", "odds": 1.9 },
        "draw": { "bookmaker": "1xbet", "odds": 3.4 },
        "away": { "bookmaker": "1xbet", "odds": 4.2 }
      }
    }
  ]
}
```

### Phase 5: Web Server & API

**File**: `core/live_odds_viewer_clean.py`

**Technology**: FastAPI (Python web framework)

**Port**: 8000 (default)

**Endpoints**:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def dashboard():
    # Serves HTML dashboard UI
    return FileResponse("html/odds_viewer_template.html")

@app.get("/api/matches")
async def get_all_matches():
    # Returns all unified matches
    data = json.load(open("data/unified_odds.json"))
    return data["matches"]

@app.get("/api/matches/{sport}")
async def get_sport_matches(sport: str):
    # Filter by sport
    matches = load_unified_odds()
    return [m for m in matches if m["sport"].lower() == sport.lower()]

@app.get("/1xbet/pregame")
async def get_1xbet_pregame():
    # Raw 1xBet data
    return json.load(open("bookmakers/1xbet/1xbet_pregame.json"))

@app.get("/oddsmagnet/football")
async def get_oddsmagnet_football():
    # OddsMagnet football data
    return json.load(open("bookmakers/oddsmagnet/oddsmagnet_football.json"))
```

### Phase 6: Monitoring System

**File**: `core/monitoring_system.py`

**Functions**:

1. **Health Checks** (every 5 minutes)

   ```python
   def check_scraper_health(self):
       # Check if data files are updating
       for scraper in scrapers:
           last_update = get_file_mtime(scraper.output_file)
           age = now - last_update

           if age > threshold:  # e.g., 60 minutes
               send_alert(f"{scraper.name} is stale!")
   ```

2. **Email Alerts**

   ```python
   def send_alert(message):
       # Send email via SMTP
       smtp.sendmail(
           from_addr=config["sender_email"],
           to_addrs=config["admin_email"],
           msg=f"ALERT: {message}"
       )
   ```

3. **Cache Auto-Update**

   - Detects new teams/sports in scraper outputs
   - Automatically adds to cache
   - Prevents manual updates

4. **Status API**
   - Writes `monitoring_status.json` every check
   - Web UI reads this for dashboard

---

## 🔑 Key Components Explained

### 1. Enhanced Cache Manager

**File**: `utils/cache_manager/enhanced_cache_manager.py`

**Purpose**: Smart team name matching and deduplication

**Features**:

- **O(1) lookup speed** using hash tables
- **Fuzzy matching** for similar names (80% threshold)
- **Alias detection** ("Man City" → "Manchester City")
- **Cross-source normalization**
- **Automatic learning** from new data

**Cache Structure**:

```json
{
  "teams": {
    "Manchester City": {
      "canonical_name": "Manchester City",
      "aliases": ["Man City", "Man City FC", "Manchester City FC"],
      "sources": ["1xbet", "fanduel", "bet365"],
      "match_count": 450,
      "last_seen": "2025-12-31T10:30:00"
    }
  },
  "sports": {
    "Soccer": {
      "canonical_name": "Soccer",
      "aliases": ["Football", "soccer"],
      "sources": ["1xbet", "fanduel", "bet365"]
    }
  }
}
```

### 2. Real-Time Collector

**File**: `core/run_unified_system.py` → `RealtimeUnifiedCollector`

**How it works**:

```python
class RealtimeUnifiedCollector:
    def __init__(self):
        self.last_modified = {}  # Track file timestamps
        self.min_update_interval = 0.5  # Rate limit

    def monitor_loop(self):
        while True:
            for file_path in self.watch_files:
                if self.has_file_changed(file_path):
                    self.trigger_update()

            time.sleep(0.5)  # Check every 0.5s

    def trigger_update(self):
        # Collect and merge all data
        unified_data = self.collector.collect_unified_odds()

        # Save output
        self.save_json(unified_data, "data/unified_odds.json")
```

**Performance**:

- Detects changes in < 0.5 seconds
- Rebuilds unified database in 1-2 seconds
- Total latency: ~2 seconds from source update to API

### 3. Monitoring System

**File**: `core/monitoring_system.py`

**Responsibilities**:

1. **Scraper Health**

   - Checks if data files are fresh
   - Alerts if no updates in X minutes

2. **Process Monitoring**

   - Detects crashed scrapers
   - Can trigger auto-restart

3. **Cache Management**

   - Auto-updates cache with new teams
   - Prevents stale data

4. **Email Notifications**
   - Sends alerts on failures
   - Cooldown to prevent spam (30 min default)

---

## 🎨 OddsMagnet Integration

### What is OddsMagnet?

OddsMagnet is a **multi-bookmaker aggregator** that provides:

- **117+ football leagues**
- **9 different bookmakers** (bet365, 1xbet, pinnacle, etc.)
- **Real-time odds** via web scraping
- **Multiple sports** (football, basketball, tennis, etc.)

### How OddsMagnet Works in This System

**File**: `bookmakers/oddsmagnet/parallel_sports_scraper.py`

**Architecture**:

```
parallel_sports_scraper.py
   │
   ├─→ Football Scraper (Process 1) ─→ oddsmagnet_football.json
   ├─→ Basketball Scraper (Process 2) → oddsmagnet_basketball.json
   ├─→ Tennis Scraper (Process 3) ───→ oddsmagnet_tennis.json
   ├─→ Cricket Scraper (Process 4) ──→ oddsmagnet_cricket.json
   └─→ ... 5 more sports in parallel
```

**Technology**: Multiprocessing for true parallelism

```python
# Scrapes 9 sports in parallel
with multiprocessing.Pool(processes=9) as pool:
    results = pool.map(scrape_sport_worker, sports)
```

**Performance**:

- Sequential scraping: ~45 seconds (9 sports × 5s each)
- Parallel scraping: ~6 seconds (all at once!)

### OddsMagnet Data Structure

**Output**: `bookmakers/oddsmagnet/oddsmagnet_football.json`

```json
{
  "sport": "football",
  "last_update": "2025-12-31T10:30:00",
  "leagues_count": 117,
  "matches_count": 2500,
  "bookmakers": ["bet365", "1xbet", "pinnacle", "betway", ...],
  "matches": [
    {
      "league": "Premier League",
      "home_team": "Manchester City",
      "away_team": "Liverpool",
      "start_time": "2025-12-31T15:00:00",
      "odds": {
        "bet365": {"home": 1.85, "draw": 3.40, "away": 4.20},
        "1xbet": {"home": 1.87, "draw": 3.35, "away": 4.15},
        "pinnacle": {"home": 1.88, "draw": 3.38, "away": 4.18}
      }
    }
  ]
}
```

### Integration with Unified System

1. **OddsMagnet scrapes** → Saves to `oddsmagnet_football.json`
2. **File watcher detects change** (RealtimeUnifiedCollector)
3. **UnifiedOddsCollector loads OddsMagnet data**
4. **Merges with 1xBet, FanDuel, Bet365 data**
5. **Outputs to unified_odds.json** with ALL bookmakers

**Result**: Each match shows odds from up to 12 bookmakers!

- Direct scrapers: 1xBet, FanDuel, Bet365
- Via OddsMagnet: bet365, 1xbet, pinnacle, betway, etc.

---

## 🚀 Running the System

### Option 1: Full System Launch (Recommended)

```bash
# Activate virtual environment (if using one)
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Launch everything
python core/launch_odds_system.py --include-live
```

**What starts:**

1. Monitoring system (health checks)
2. Unified collector (data merging)
3. All scrapers (1xBet, FanDuel, Bet365, OddsMagnet)
4. Web server (FastAPI on port 8000)

### Option 2: Individual Components

```bash
# Just the unified collector
python core/run_unified_system.py --mode realtime --include-live

# Just the web server
python core/live_odds_viewer_clean.py

# Just monitoring
python core/monitoring_system.py

# Just 1xBet scraper
cd bookmakers/1xbet
python 1xbet_pregame.py --monitor
python 1xbet_live.py

# Just OddsMagnet
cd bookmakers/oddsmagnet
python parallel_sports_scraper.py --mode local --continuous
```

### Option 3: VPS Deployment (Production)

```bash
# On your local machine
bash deployment/deploy_unified_odds_auto.sh

# Or manually on VPS
sudo systemctl start unified-odds
sudo systemctl status unified-odds
```

---

## 📡 API & Data Access

### REST API Endpoints

**Base URL**: `http://localhost:8000`

#### Dashboard

```
GET /
→ Returns HTML web dashboard
```

#### All Matches

```
GET /api/matches
→ Returns all unified matches (all sports, all bookmakers)

Response:
{
  "matches": [...],
  "total": 3420,
  "sources": ["1xbet", "fanduel", "bet365", "oddsmagnet"]
}
```

#### Filter by Sport

```
GET /api/matches/soccer
GET /api/matches/basketball
GET /api/matches/tennis

→ Returns matches for specific sport
```

#### Bookmaker-Specific Data

```
GET /1xbet/pregame      → 1xBet pregame odds
GET /1xbet/live         → 1xBet live odds
GET /fanduel/pregame    → FanDuel pregame
GET /fanduel/live       → FanDuel live
GET /bet365/pregame     → Bet365 pregame
GET /bet365/live        → Bet365 live
```

#### OddsMagnet Data

```
GET /oddsmagnet/football        → All football leagues
GET /oddsmagnet/football/top10  → Top 10 leagues only
GET /oddsmagnet/basketball
GET /oddsmagnet/tennis
```

#### System Status

```
GET /api/status
→ Health status of all components

Response:
{
  "system_status": "healthy",
  "last_update": "2025-12-31T10:35:00",
  "scrapers": {
    "1xbet_pregame": {"status": "ok", "age": "30s"},
    "fanduel_live": {"status": "ok", "age": "15s"}
  }
}
```

### Direct File Access

All data is also available as JSON files:

```bash
# Unified data (all bookmakers merged)
cat data/unified_odds.json

# Individual bookmaker files
cat bookmakers/1xbet/1xbet_pregame.json
cat bookmakers/fanduel/fanduel_live.json
cat bookmakers/oddsmagnet/oddsmagnet_football.json

# Cache and metadata
cat data/cache_data.json
cat data/monitoring_status.json
```

---

## 🔍 Monitoring & Health Checks

### Monitoring Dashboard

Access via API:

```bash
curl http://localhost:8000/api/status
```

### Log Files

```bash
# System logs (systemd)
sudo journalctl -u unified-odds -f

# Individual component logs
tail -f logs/unified_collector.log
tail -f logs/monitoring.log
tail -f logs/scraper_1xbet.log
```

### Health Check Commands

```bash
# Check if services are running
systemctl status unified-odds

# Check data freshness
stat -c %y data/unified_odds.json

# Check scraper status
ps aux | grep python | grep -E '1xbet|fanduel|oddsmagnet'

# Monitor resource usage
htop -p $(pgrep -f 'run_unified_system')
```

### Email Alerts

Configure in `config/config.json`:

```json
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "admin_email": "admin@example.com",
    "alert_cooldown_minutes": 30
  }
}
```

**Alert Triggers**:

- Scraper hasn't updated in > 60 minutes
- Process crash detected
- Data file corruption
- API server unreachable

---

## 🛠️ Troubleshooting

### Issue: No data in unified_odds.json

**Diagnosis**:

```bash
# Check if scrapers are running
ps aux | grep python | grep scraper

# Check source files
ls -lh bookmakers/*/1xbet_pregame.json
```

**Solutions**:

1. Start scrapers manually
2. Check scraper logs for errors
3. Verify Chrome/Selenium is installed

### Issue: Duplicate matches with different team names

**Diagnosis**:

```bash
# Check cache file
cat data/cache_data.json | grep "Manchester"
```

**Solutions**:

1. Update team aliases in cache manually
2. Run cache auto-update:
   ```bash
   python utils/cache_manager/update_cache.py
   ```
3. Check name normalization in `unified_odds_collector.py`

### Issue: Web server not accessible

**Diagnosis**:

```bash
# Check if port 8000 is in use
lsof -i :8000

# Check FastAPI logs
python core/live_odds_viewer_clean.py
```

**Solutions**:

1. Change port in `live_odds_viewer_clean.py`
2. Kill conflicting process
3. Check firewall settings

### Issue: Scrapers crashing

**Diagnosis**:

```bash
# Check scraper logs
tail -f bookmakers/1xbet/logs/1xbet_scraper.log

# Check Chrome processes
ps aux | grep chrome
```

**Solutions**:

1. Update Selenium: `pip install --upgrade selenium`
2. Clear Chrome cache
3. Check website structure changes
4. Reduce scraping frequency

### Issue: High memory usage

**Diagnosis**:

```bash
# Check process memory
ps aux --sort=-%mem | head -20

# Check Chrome processes
ps aux | grep chrome
```

**Solutions**:

1. Limit concurrent Chrome instances
2. Kill zombie Chrome processes
3. Reduce OddsMagnet concurrent requests
4. Increase system swap

---

## 📚 Additional Resources

- **[API Reference](API_REFERENCE.md)** - Complete API documentation
- **[Project Structure](PROJECT_STRUCTURE.md)** - Detailed folder organization
- **[Adding Bookmakers](ADDING_NEW_BOOKMAKERS.md)** - How to add new sources
- **[Deployment Guide](GITHUB_DEPLOYMENT_GUIDE.md)** - VPS setup
- **[Security Guide](SECURITY_CONFIG_GUIDE.md)** - Config encryption

---

## 🎯 Quick Reference

### Start System

```bash
python core/launch_odds_system.py --include-live
```

### Access Dashboard

```
http://localhost:8000/
```

### Check Status

```bash
curl http://localhost:8000/api/status
```

### View Data

```bash
cat data/unified_odds.json | jq .
```

### Stop System

```bash
# Press CTRL+C in terminal
# OR
sudo systemctl stop unified-odds
```

---

## 💡 Key Takeaways

1. **Modular Design**: Each bookmaker is isolated, easy to add/remove
2. **Real-Time**: Updates propagate in < 2 seconds
3. **Smart Deduplication**: Handles team name variations automatically
4. **Scalable**: Can handle 100+ bookmakers with same architecture
5. **Reliable**: Auto-monitoring, alerts, and auto-restart
6. **Developer-Friendly**: REST API, clear documentation, simple structure

---

**Need help?** Check the other documentation files in `docs/` or review the code comments!
