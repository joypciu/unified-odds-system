# Parallel OddsMagnet Scraper

## Overview

High-performance parallel scraper that runs **multiple sports simultaneously** using Python multiprocessing. This is **dramatically faster** than the old sequential approach.

## ✅ FIXED: UI Data Structure Issue (Dec 29, 2025)

**Problem:** The UI was loading matches but showing "0 bookmakers found" because the data structure didn't match what the UI expected.

**Solution:** Added `transform_odds_to_ui_format()` function to convert Pandas DataFrame JSON format to UI-compatible format:

- **Old format:** `{schema: {...}, data: [{bet_name, vb: {back_decimal: ...}}]}`
- **New format:** `{odds: [{bookmaker_code, decimal_odds, bet_name, ...}]}`

**Changes made:**

- Updated `base_sport_scraper.py` to transform odds data
- Market structure now: `markets[category][] = {name, url, odds: [...]}`
- Each odd includes: `bookmaker_code`, `bookmaker_name`, `decimal_odds`, `bet_name`, `clickout_url`

Now the UI correctly displays all bookmakers! 🎉

## Performance Comparison

### Old Sequential Scraper

- Scrapes one sport at a time
- Takes 10-15 minutes to complete all sports
- Limited concurrency (20 tabs per sport)

### New Parallel Scraper ✨

- Scrapes all sports **simultaneously** in separate processes
- Completes in **~3 minutes** (175 seconds)
- True parallelism with multiprocessing
- Optimized concurrency (15 tabs per sport to avoid rate-limiting)

### Example Results

```
✅ Successful sports:
   • FOOTBALL: 119 matches (116.83s)
   • BASKETBALL: 6 matches (43.5s)
   • TENNIS: 6 matches (44.61s)
   • AMERICAN-FOOTBALL: 55 matches (86.41s)
   • TABLE-TENNIS: 251 matches (173.42s)

Total: 437 matches in 175.55 seconds
```

## Files

### 1. `base_sport_scraper.py`

Modular base class for individual sport scrapers. Can be used standalone or as part of parallel execution.

**Features:**

- Connects to Chrome remote debugging OR runs headless
- Extracts SSR data from OddsMagnet pages
- Fetches leagues, matches, markets, and odds
- Saves sport-specific JSON files

### 2. `parallel_sports_scraper.py`

Master script that runs all sport scrapers in parallel using multiprocessing.

**Features:**

- True parallel execution (one process per sport)
- CPU-optimized (uses up to CPU core count)
- Combines all sport data into unified file
- Detailed progress logging
- Graceful error handling per sport

### 3. `launch_parallel_scraper.py`

Simple interactive launcher with preset configurations.

## Usage

### Quick Start (Interactive)

```bash
python launch_parallel_scraper.py
```

Choose from menu:

1. **Run ONCE** - Single scrape, then exit
2. **Run CONTINUOUS (60s)** - Loop every 60 seconds
3. **Run CONTINUOUS FAST (30s)** - Loop every 30 seconds
4. **Run FOOTBALL ONLY** - Continuous football scraping
5. **Run CUSTOM** - Specify sports and interval

### Command Line Usage

#### Single Run (All Sports)

```bash
python parallel_sports_scraper.py --mode local
```

#### Continuous Mode (60s interval)

```bash
python parallel_sports_scraper.py --mode local --continuous --interval 60
```

#### Specific Sports Only

```bash
python parallel_sports_scraper.py --mode local --sports football basketball tennis
```

#### VPS Headless Mode

```bash
python parallel_sports_scraper.py --mode vps --continuous --interval 60
```

## Output Files

Each sport creates its own JSON file:

- `oddsmagnet_top10.json` - Football (top 10 leagues)
- `oddsmagnet_basketball.json` - Basketball
- `oddsmagnet_tennis.json` - Tennis
- `oddsmagnet_americanfootball.json` - American Football
- `oddsmagnet_tabletennis.json` - Table Tennis

Combined file:

- `oddsmagnet_all_sports.json` - All sports in one file

## Configuration

Edit `SPORTS_CONFIG` in `parallel_sports_scraper.py`:

```python
SPORTS_CONFIG = {
    'football': {
        'enabled': True,
        'top_leagues': 10,
        'output': 'oddsmagnet_top10.json',
        'markets': ['win market', 'over under betting', 'both teams to score'],
    },
    'basketball': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_basketball.json',
        'markets': ['win market', 'over under betting'],
    }
    # ... more sports
}
```

## Prerequisites

### Local Mode (Remote Debugging)

Chrome must be running with remote debugging enabled on port 9222:

```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:/chrome-debug"
```

Or use PowerShell:

```powershell
Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=C:/chrome-debug"
```

### VPS Mode (Headless)

No Chrome needed - Playwright launches headless browser automatically.

## Integration with Live Odds Viewer

The parallel scraper integrates seamlessly with `live_odds_viewer_clean.py`:

1. Files are watched for changes via WebSocket monitor
2. Updates are pushed to connected clients automatically
3. No code changes needed in the viewer

## Architecture

```
parallel_sports_scraper.py
  ├─ Process 1: Football Scraper
  │    └─ base_sport_scraper.py → oddsmagnet_top10.json
  ├─ Process 2: Basketball Scraper
  │    └─ base_sport_scraper.py → oddsmagnet_basketball.json
  ├─ Process 3: Tennis Scraper
  │    └─ base_sport_scraper.py → oddsmagnet_tennis.json
  ├─ Process 4: American Football Scraper
  │    └─ base_sport_scraper.py → oddsmagnet_americanfootball.json
  └─ Process 5: Table Tennis Scraper
       └─ base_sport_scraper.py → oddsmagnet_tabletennis.json
```

All processes run **simultaneously** → Combine results → Save unified file

## Optimization Tips

1. **Concurrency:** Adjust `max_concurrent` in `BaseSportScraper` (default: 15 tabs)
2. **Sports Selection:** Disable unused sports in config to speed up
3. **Update Interval:** For continuous mode, 30-60s is recommended
4. **CPU Cores:** More cores = better parallel performance

## Troubleshooting

### "Failed to connect to remote debugging"

- Ensure Chrome is running with `--remote-debugging-port=9222`
- Check if port 9222 is available: `netstat -ano | findstr :9222`
- Scraper will auto-fallback to headless mode

### Slow Performance

- Reduce `max_concurrent` (fewer tabs = less memory but slower)
- Disable unused sports
- Check network connection speed

### Rate Limiting

- Scraper already optimized with 15 concurrent tabs per sport
- If still rate-limited, reduce `max_concurrent` further

## Future Enhancements

- [ ] Add Hockey, Baseball, Cricket sports
- [ ] Implement distributed scraping across multiple machines
- [ ] Add Redis caching for faster re-scrapes
- [ ] Implement adaptive rate limiting
- [ ] Add proxy rotation support

## License

Same as parent project
