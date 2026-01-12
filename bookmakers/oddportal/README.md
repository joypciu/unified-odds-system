# OddsPortal Multi-Sport Scraper

A high-performance, parallel web scraper for OddsPortal.com that collects betting odds across multiple sports and bookmakers.

## 🚀 Features

- **Multi-Sport Support**: Scrapes 5 sports simultaneously

  - ⚽ Football (Premier League, La Liga, Bundesliga, Serie A)
  - 🏈 American Football (NFL, NCAA)
  - 🏀 Basketball (NBA, Euroleague)
  - 🏒 Hockey (NHL)
  - ⚾ Baseball (MLB)

- **Parallel Execution**: Each sport gets its own isolated browser for maximum speed
- **Auto-Save**: Progressive data saving every 2 seconds
- **Intelligent Extraction**: Handles hidden odds tables by clicking "Decimal Odds" button
- **Date Parsing**: Month-based selectors with validation
- **Dual Output**: CSV and JSON formats
- **Backend Integration**: Unified format compatible with oddsmagnet viewer

## 📊 Current Stats

- **108 matches** scraped across 4 active sports
- **20 bookmakers** tracked (1xBet, bet365, Pinnacle, Stake, etc.)
- **American Football**: 8 matches (6 NFL + 2 NCAA)
- **Basketball**: 30 matches (15 NBA + 15 Euroleague)
- **Football**: 55 matches (4 top leagues)
- **Hockey**: 15 matches (NHL)

## 🛠️ Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## 📦 Requirements

- Python 3.8+
- Playwright
- System Chrome browser (for headed mode)

## 🎯 Usage

### Basic Scraping

```bash
# Run the scraper
python working_scraper.py
```

### Backend Integration

```bash
# Run with backend integration (creates unified format)
python oddportal_collector.py

# Run continuously (updates every 5 minutes)
python oddportal_collector.py --continuous --interval 300
```

## 📁 Output Files

### CSV Format

`matches_odds_data.csv` - Flattened format with one row per bookmaker per match

| sport    | country | league         | home     | away       | match_time  | bookmaker | home_odds | draw_odds | away_odds |
| -------- | ------- | -------------- | -------- | ---------- | ----------- | --------- | --------- | --------- | --------- |
| football | england | premier-league | West Ham | Nottingham | 06 Jan 2026 | 1xBet     | 3.23      | 3.48      | 2.39      |

### JSON Format

`matches_odds_data.json` - Nested format with matches containing bookmaker arrays

```json
{
  "home": "West Ham",
  "away": "Nottingham",
  "sport": "football",
  "country": "england",
  "league": "premier-league",
  "match_time": "06 Jan 2026,",
  "bookmakers": [
    {
      "name": "1xBet",
      "home_odds": 3.23,
      "draw_odds": 3.48,
      "away_odds": 2.39
    }
  ]
}
```

### Unified Format

`oddportal_unified.json` - Backend-compatible format for oddsmagnet viewer

```json
{
  "sport": "multi",
  "timestamp": "2026-01-06T17:37:58.766896",
  "matches_count": 108,
  "matches": [
    {
      "home_team": "West Ham",
      "away_team": "Nottingham",
      "sport": "football",
      "league": "england premier-league",
      "markets": {
        "popular markets": [...]
      }
    }
  ]
}
```

## ⚙️ Configuration

Edit `working_scraper.py` to customize:

```python
self.leagues = {
    'football': [
        'https://www.oddsportal.com/football/england/premier-league/',
        # Add more leagues...
    ],
    'american-football': [
        'https://www.oddsportal.com/american-football/usa/nfl/',
        'https://www.oddsportal.com/american-football/usa/ncaa/',
    ],
    # ...
}

self.max_matches_per_league = 15  # Limit matches per league
```

## 🔧 Key Components

### `working_scraper.py`

Main scraper with parallel execution across sports.

**Key Features:**

- Parallel browser contexts (one per sport)
- Auto-save with thread-safe data management
- Intelligent odds extraction (clicks "Decimal Odds" button)
- Month-based date parsing
- Resource management (1.5s delay between matches)

### `oddportal_collector.py`

Backend integration wrapper that converts scraped data to unified format.

**Features:**

- Progressive data saving (updates UI as each sport completes)
- Decimal to fractional odds conversion
- Market structure compatible with oddsmagnet viewer
- Continuous mode with configurable intervals

## 🐛 Debugging Scripts

- `find_odds_button.py` - Verify "Decimal Odds" button detection
- `find_odds_selector.py` - Test odds element selectors
- `inspect_match_page.py` - Analyze match page structure
- `show_results.py` - Display scraped data summary

## 🔍 How It Works

1. **Parallel Launch**: Creates isolated browser context for each sport
2. **League Navigation**: Visits each league page and finds match links
3. **Match Scraping**: For each match:
   - Navigate to match page
   - Click "Decimal Odds" button to expand odds table
   - Extract bookmaker names and odds values
   - Parse match date using month-based selectors
4. **Auto-Save**: Saves progress every 2 seconds
5. **Final Export**: Generates CSV, JSON, and unified formats

## 🚦 Integration with Main System

The scraper integrates with the unified odds system via:

1. **API Endpoint**: `/oddsmagnet/api/oddportal`
2. **WebSocket**: Real-time updates to viewer
3. **Unified Format**: Compatible with existing bookmaker data structure

**Main System Files:**

- `core/unified_odds_collector.py` - Loads OddsPortal data
- `core/live_odds_viewer_clean.py` - API endpoint
- `html/oddsmagnet_viewer.html` - UI with OddPortal button and filters

## 📈 Performance

- **Parallel Execution**: 5 sports scraped simultaneously
- **Auto-Save**: Data available within 2 seconds of scraping
- **Progressive Updates**: UI displays partial data as sports complete
- **Resource Optimized**: 1.5s delays prevent browser crashes

## 🎨 UI Features (Main System)

When integrated with the main system:

- **OddPortal Button**: Orange button in oddsmagnet viewer
- **Sport Filter**: Filter by Football, Basketball, American Football, or Hockey
- **League Filter**: Filter by specific leagues
- **Date Filter**: Calendar-based date selection
- **Match Count Badge**: Shows total matches available

## 🔄 Continuous Mode

Run continuously for live data updates:

```bash
python oddportal_collector.py --continuous --interval 300
```

This will:

- Scrape all sports every 5 minutes
- Update unified format file
- Send progressive updates to UI as each sport completes
- Continue running until stopped (Ctrl+C)

## 📝 Notes

- **Tennis**: Removed (main page shows tournaments, not matches)
- **NCAA**: Added for American Football (College Football Playoff)
- **Delays**: 1.5s between matches prevents browser resource exhaustion
- **Browser**: Uses system Chrome via `channel='chrome'`

## 🤝 Contributing

This scraper is part of the unified odds system. For the main project, see:
https://github.com/joypciu/unified-odds-system

## 📄 License

Part of the unified odds system project.

## 🔗 Links

- **Main Repository**: [unified-odds-system](https://github.com/joypciu/unified-odds-system)
- **OddsPortal**: [oddsportal.com](https://www.oddsportal.com)

---

**Last Updated**: January 6, 2026
**Version**: 1.0.0
**Status**: ✅ Production Ready
