# OddsMagnet Scraper System

## 🎉 Current Status: FULLY OPERATIONAL

**Last Updated:** December 29, 2025  
**Status:** ✅ Production-ready and running on VPS  
**Performance:** ~350 matches from 5 sports in 2 minutes

---

## Overview

The OddsMagnet scraper is a high-performance, parallel web scraping system that collects odds data from **OddsMagnet.com** - a comprehensive odds comparison platform featuring data from 20+ bookmakers.

### What is OddsMagnet?

OddsMagnet aggregates odds from multiple bookmakers for various sports:

- ⚽ **Football** (Soccer)
- 🏀 **Basketball**
- 🎾 **Tennis**
- 🏈 **American Football**
- 🏓 **Table Tennis**
- And more...

Our scraper extracts this pre-aggregated data, making it an efficient way to collect odds from many bookmakers at once.

---

## Architecture

### 1. Parallel Sports Scraper (`parallel_sports_scraper.py`)

**The main production scraper** that runs multiple sports simultaneously using Python multiprocessing.

#### Key Features:

- ✅ **True parallelism** - Each sport runs in a separate process
- ✅ **5x faster** than sequential scraping (2 min vs 10+ min)
- ✅ **CloudFront bypass** - Advanced anti-detection techniques
- ✅ **Headless Chrome** - Playwright-based browser automation
- ✅ **Configurable** - Customize sports, leagues, markets, and intervals

#### Performance:

```
Recent Run Results (Dec 29, 2025):
✅ FOOTBALL: 42 matches (75.99s)
✅ BASKETBALL: 3 matches (35.01s)
✅ TENNIS: 6 matches (29.01s)
✅ AMERICAN-FOOTBALL: 51 matches (62.25s)
✅ TABLE-TENNIS: 245 matches (126.51s)

Total: 347 matches in 127.19 seconds
```

#### Usage:

**Run once (VPS mode with anti-detection):**

```bash
python parallel_sports_scraper.py --mode vps
```

**Run continuously every 60 seconds:**

```bash
python parallel_sports_scraper.py --mode vps --continuous --interval 60
```

**Scrape specific sports only:**

```bash
python parallel_sports_scraper.py --mode vps --sports football basketball
```

**Local development (with remote debugging Chrome):**

```bash
python parallel_sports_scraper.py --mode local
```

### 2. Base Sport Scraper (`base_sport_scraper.py`)

The foundation class used by the parallel scraper for each sport.

#### Anti-Detection Features:

- **JavaScript Stealth:**

  - Overrides `navigator.webdriver` to hide automation
  - Mocks browser plugins and chrome object
  - Spoofs navigator properties (platform, vendor, hardwareConcurrency)

- **HTTP Headers:**

  - `Sec-Ch-Ua`: Chrome 120 brand hints
  - `Sec-Ch-Ua-Platform`: Windows
  - `Sec-Fetch-*`: Proper fetch metadata headers
  - `Accept-Language`: en-US, en

- **Browser Fingerprinting:**
  - Platform: Win32
  - Vendor: Google Inc.
  - Hardware Concurrency: 8 cores
  - Device Memory: 8 GB

#### How It Works:

1. **Connect to Chrome** (launches headless Chrome with anti-detection flags)
2. **Extract SSR Data** (Angular ng-state JSON embedded in HTML)
3. **Get Leagues** (fetch available leagues for the sport)
4. **Get Matches** (for top N leagues)
5. **Fetch Odds** (for each match, all configured markets)
6. **Transform to UI Format** (convert to standardized structure)
7. **Save Output** (JSON file for each sport)

### 3. Debug Script (`debug_chrome_vps.py`)

A diagnostic tool used to test CloudFront bypass techniques before applying to production.

#### What It Does:

- ✅ Validates anti-detection JavaScript
- ✅ Tests HTTP header configuration
- ✅ Takes screenshots for visual verification
- ✅ Saves HTML for inspection
- ✅ Checks if leagues and matches load

---

## Data Structure

### Output Format

Each sport produces a JSON file with this structure:

```json
{
  "name": "team1 v team2",
  "league_id": "football/league-name",
  "match_url": "football/league-name/team1-v-team2",
  "match_slug": "team1-v-team2",
  "datetime": "2026-01-02 20:00:00",
  "home": "team1",
  "home_team": "team1",
  "away": "team2",
  "away_team": "team2",
  "sport": "football",
  "league": "league name",
  "markets": {
    "popular markets": [
      {
        "name": "win market",
        "url": "...",
        "odds": [
          {
            "bookmaker_code": "bet365",
            "bookmaker_name": "Bet365",
            "decimal_odds": 2.10,
            "fractional_odds": "11/10",
            "selection": "team1",
            "bet_name": "team1",
            "clickout_url": "https://...",
            "last_decimal": "2.05"
          }
        ]
      }
    ],
    "over under betting": [...],
    "both teams to score": [...]
  }
}
```

### Field Descriptions:

- **`home_team` / `away_team`**: Team names (lowercase, normalized)
- **`datetime`**: Match start time (format: "YYYY-MM-DD HH:MM:SS")
- **`sport`**: Sport category (football, basketball, tennis, etc.)
- **`league`**: League/competition name
- **`markets`**: Object containing market categories
  - Each category has an array of market objects
  - Each market has `name`, `url`, and `odds` array
- **`odds`**: Array of bookmaker odds
  - `bookmaker_code`: 2-letter bookmaker identifier
  - `decimal_odds`: Decimal format (e.g., 2.10)
  - `fractional_odds`: Fractional format (e.g., "11/10")
  - `selection`: home/away/draw
  - `clickout_url`: Direct link to place bet

---

## Configuration

### Sports Config (`SPORTS_CONFIG` in `parallel_sports_scraper.py`)

```python
SPORTS_CONFIG = {
    'football': {
        'enabled': True,
        'top_leagues': 10,           # Scrape top 10 leagues
        'output': 'oddsmagnet_top10.json',
        'markets': [
            'win market',            # Home/Draw/Away
            'over under betting',    # Totals
            'both teams to score'    # BTTS
        ],
    },
    'basketball': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_basketball.json',
        'markets': ['win market', 'over under betting'],
    },
    # ... more sports
}
```

### Customization Options:

1. **Enable/Disable Sports**: Set `enabled: True/False`
2. **Number of Leagues**: Adjust `top_leagues` (1-50)
3. **Market Selection**: Add/remove market names from the list
4. **Concurrency**: Change `max_concurrent` in BaseSportScraper (default: 15)
5. **Update Interval**: Set `--interval` in continuous mode

---

## Anti-Detection System

### The CloudFront Challenge (Solved ✅)

OddsMagnet is protected by AWS CloudFront WAF, which was initially blocking our headless Chrome with HTTP 403 errors.

#### What We Did:

1. **Created Debug Script**

   - Isolated CloudFront blocking issue
   - Tested anti-detection incrementally
   - Achieved Status 200 (was 403)

2. **Implemented Stealth Techniques**

   - JavaScript injection to override automation signals
   - HTTP headers matching real Chrome browser
   - Browser fingerprint spoofing

3. **Applied to Production**
   - Integrated proven techniques into base scraper
   - All 5 sports now scraping successfully
   - No CloudFront blocks in production

### Technical Implementation:

**JavaScript Stealth:**

```javascript
// Hide webdriver property
Object.defineProperty(navigator, "webdriver", {
  get: () => undefined,
});

// Mock plugins
Object.defineProperty(navigator, "plugins", {
  get: () => [1, 2, 3, 4, 5],
});

// Add chrome object
window.chrome = {
  runtime: {},
  loadTimes: function () {},
  csi: function () {},
};
```

**HTTP Headers:**

```python
extra_http_headers={
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Accept-Language': 'en-US,en;q=0.9',
}
```

---

## VPS Deployment

### Prerequisites:

- Ubuntu server with Python 3.8+
- Google Chrome installed
- Git repository access
- Virtual environment

### Installation:

1. **Install Chrome:**

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f
```

2. **Install Python Dependencies:**

```bash
cd /path/to/unified-odds
python -m venv venv
source venv/bin/activate
pip install -r config/requirements.txt
playwright install chromium
```

3. **Run Scraper:**

```bash
cd bookmakers/oddsmagnet
python parallel_sports_scraper.py --mode vps --continuous --interval 60
```

### Systemd Service (Optional):

Create `/etc/systemd/system/oddsmagnet-scraper.service`:

```ini
[Unit]
Description=OddsMagnet Parallel Scraper
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/services/unified-odds/bookmakers/oddsmagnet
ExecStart=/home/ubuntu/services/unified-odds/venv/bin/python parallel_sports_scraper.py --mode vps --continuous --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable oddsmagnet-scraper
sudo systemctl start oddsmagnet-scraper
sudo systemctl status oddsmagnet-scraper
```

---

## Troubleshooting

### Issue: "No leagues found"

**Cause:** CloudFront blocking or incorrect mode  
**Solution:**

1. Ensure using `--mode vps` on VPS (not `--mode local`)
2. Check Chrome is running: `ps aux | grep chrome`
3. Test with debug script: `python debug_chrome_vps.py`

### Issue: HTTP 403 Errors

**Cause:** Anti-detection not working  
**Solution:**

1. Verify anti-detection code in `base_sport_scraper.py`
2. Check Chrome launch args include `--disable-blink-features=AutomationControlled`
3. Ensure `add_init_script()` is executed before page navigation

### Issue: Slow Performance

**Cause:** Too much concurrency or network throttling  
**Solution:**

1. Reduce `max_concurrent` (try 10 instead of 15)
2. Add delays between requests
3. Check network bandwidth

### Issue: Data Not Loading in UI

**Cause:** Data structure mismatch  
**Solution:**

1. Verify JSON output has `home_team`, `away_team`, `datetime` fields
2. Check `transform_odds_to_ui_format()` is being called
3. Ensure odds array has `bookmaker_code`, `decimal_odds`, `selection`

---

## Files Reference

| File                         | Purpose                        | Status         |
| ---------------------------- | ------------------------------ | -------------- |
| `parallel_sports_scraper.py` | Main production scraper        | ✅ Operational |
| `base_sport_scraper.py`      | Base class with anti-detection | ✅ Operational |
| `debug_chrome_vps.py`        | CloudFront bypass testing      | ✅ Working     |
| `PARALLEL_SCRAPER_README.md` | Performance documentation      | 📄 Reference   |
| `IMPLEMENTATION_COMPLETE.md` | Implementation history         | 📄 Archive     |
| `REALTIME_SCRAPER_README.md` | Realtime scraper docs          | 📄 Archive     |
| `MIGRATION_TO_PLAYWRIGHT.md` | Migration notes                | 📄 Archive     |

---

## Output Files

When you run the scraper, it generates these JSON files:

```
bookmakers/oddsmagnet/
├── oddsmagnet_top10.json          # Football (top 10 leagues)
├── oddsmagnet_basketball.json     # Basketball matches
├── oddsmagnet_tennis.json         # Tennis matches
├── oddsmagnet_americanfootball.json  # American Football
├── oddsmagnet_tabletennis.json    # Table Tennis
└── oddsmagnet_all_sports.json     # Combined metadata
```

### File Sizes (Typical):

- Football: 200-500 KB (40-120 matches)
- Basketball: 20-50 KB (3-10 matches)
- Tennis: 30-70 KB (6-15 matches)
- American Football: 100-300 KB (50-80 matches)
- Table Tennis: 500-1500 KB (200-300 matches)

---

## UI Integration

The scraped data is displayed using `html/oddsmagnet_viewer.html`.

### Features:

- 📊 **Real-time data loading** from JSON files
- 🔍 **Search & filter** by team, league, sport
- 📅 **Date picker** with calendar view
- 🔖 **Bookmark matches** for quick access
- 📱 **Responsive design** for mobile/desktop
- 🎨 **Dark theme** optimized for extended viewing

### Data Display:

- **Team Names:** `home_team vs away_team`
- **Date/Time:** Parsed from `datetime` field
- **Odds Grid:** Shows all bookmakers with best odds highlighted
- **Markets:** Tabs for different bet types (Win, Over/Under, BTTS)

---

## Future Enhancements

### Planned Features:

- [ ] **API endpoints** for programmatic access
- [ ] **Historical data tracking** (odds movements over time)
- [ ] **Alert system** for arbitrage opportunities
- [ ] **More sports** (cricket, ice hockey, rugby)
- [ ] **Live odds support** (currently pregame only)
- [ ] **Odds comparison graphs** (visual trends)

### Optimization Ideas:

- [ ] **Database storage** instead of JSON files
- [ ] **Redis caching** for faster data access
- [ ] **WebSocket updates** for real-time UI refresh
- [ ] **Distributed scraping** across multiple VPS instances

---

## Contributing

If you want to add a new sport or market:

1. **Add to `SPORTS_CONFIG`:**

   ```python
   'new-sport': {
       'enabled': True,
       'top_leagues': 5,
       'output': 'oddsmagnet_newsport.json',
       'markets': ['win market'],
   }
   ```

2. **Test in local mode first:**

   ```bash
   python parallel_sports_scraper.py --mode local --sports new-sport
   ```

3. **Deploy to VPS:**
   ```bash
   git push origin main
   ssh vps "cd /path/to/repo && git pull"
   ```

---

## License

Part of the Unified Odds System project.

---

## Support

For issues or questions:

1. Check **Troubleshooting** section above
2. Review logs: `journalctl -u oddsmagnet-scraper -f`
3. Test with debug script: `python debug_chrome_vps.py`
4. Check GitHub issues in the unified-odds-system repo

---

**Happy Scraping! ⚽🏀🎾**
