# OddPortal Integration - Testing Guide

## Overview

OddPortal has been successfully integrated into the main unified odds system. The integration allows OddPortal data to be automatically collected and displayed in the OddsMagnet viewer UI.

## What Was Changed

### 1. New OddPortal Collector (`oddportal/oddportal_collector.py`)

- Wrapper script that runs the OddPortal scraper
- Converts OddPortal data format to unified format compatible with OddsMagnet viewer
- Supports continuous mode with configurable intervals (default: 5 minutes)
- Saves data to `oddportal/oddportal_unified.json`

### 2. Unified Odds Collector (`core/unified_odds_collector.py`)

- Added `oddportal_file` path configuration
- Created `load_oddportal()` method to load OddPortal data
- Integrated OddPortal data into the main collection and merge process
- OddPortal data is normalized and merged with other bookmaker data

### 3. Launch Script (`core/launch_odds_system.py`)

- Added OddPortal collector to startup sequence
- Runs automatically with continuous mode (5-minute intervals)
- Includes OddPortal in system status messages

### 4. Web Viewer API (`core/live_odds_viewer_clean.py`)

- Added `/oddsmagnet/api/oddportal` endpoint
- Also accessible via `/oddportal/api/matches`
- Supports pagination, filtering by sport/league, and search
- ETag caching for performance

### 5. OddsMagnet Viewer UI (`html/oddsmagnet_viewer.html`)

- Added "OddPortal (Multi-Sport)" option to sport selector
- Configured API endpoint mapping for oddportal
- Added sport label and icon for oddportal section
- Supports 3-way betting display (home/draw/away)

## How to Test

### 1. Start the System

```powershell
cd "e:\vps deploy\combine 1xbet, fanduel and bet365 (main)"
python core/launch_odds_system.py
```

The system will automatically start:

- Unified Odds Collector
- OddsMagnet Parallel Scraper
- **OddPortal Collector** (NEW)
- Web Viewer

### 2. Verify OddPortal is Running

Check the console output for:

```
📊 Starting OddPortal Collector...
   - Scraping odds from OddPortal
   - Multiple sports and leagues coverage
   - Update interval: 300 seconds (5 minutes)
   - Output: bookmakers/oddportal/oddportal_unified.json

✅ OddPortal collector started (PID: XXXX)
```

### 3. Check OddPortal Data File

After the first collection cycle (may take a few minutes):

```powershell
# Check if the file exists
Test-Path "bookmakers/oddportal/oddportal_unified.json"

# View the file content
Get-Content "bookmakers/oddportal/oddportal_unified.json" | ConvertFrom-Json | Format-List
```

# View the file content

Get-Content "oddportal/oddportal_unified.json" | ConvertFrom-Json | Format-List

````

### 4. Access OddPortal Data via Web UI

1. Open browser: http://localhost:8000
2. Click on the sport selector dropdown
3. Select "OddPortal (Multi-Sport)" from the list
4. You should see matches from various sports scraped from OddPortal

### 5. Access OddPortal Data via API

```powershell
# Get all OddPortal matches
Invoke-RestMethod -Uri "http://localhost:8000/oddsmagnet/api/oddportal"

# Filter by sport
Invoke-RestMethod -Uri "http://localhost:8000/oddsmagnet/api/oddportal?sport=basketball"

# Filter by league
Invoke-RestMethod -Uri "http://localhost:8000/oddsmagnet/api/oddportal?league=nba"

# Search for specific teams
Invoke-RestMethod -Uri "http://localhost:8000/oddsmagnet/api/oddportal?search=lakers"
````

## Manual Testing (Without Full System)

### Run OddPortal Collector Standalone

```powershell
cd bookmakers/oddportal
python oddportal_collector.py --continuous --interval 300
```

### Run OddPortal Collector Once

```powershell
cd bookmakers/oddportal
python oddportal_collector.py
```

## Data Flow

```
OddPortal Website
    ↓
bookmakers/oddportal/working_scraper.py (Playwright scraper)
    ↓
bookmakers/oddportal/matches_odds_data.json (raw format)
    ↓
bookmakers/oddportal/oddportal_collector.py (converter)
    ↓
bookmakers/oddportal/oddportal_unified.json (unified format)
    ↓
core/unified_odds_collector.py (merger)
    ↓
data/unified_odds.json (all bookmakers combined)
    ↓
core/live_odds_viewer_clean.py (API endpoint)
    ↓
html/oddsmagnet_viewer.html (UI display)
```

## File Locations

- **Raw OddPortal Data**: `bookmakers/oddportal/matches_odds_data.json`
- **Unified OddPortal Data**: `bookmakers/oddportal/oddportal_unified.json`
- **Combined Data**: `data/unified_odds.json`
- **Collector Script**: `bookmakers/oddportal/oddportal_collector.py`

## Configuration

### Collection Interval

Default: 300 seconds (5 minutes)

To change:

```powershell
# Edit launch_odds_system.py, line ~268
["--interval", "300"]  # Change 300 to desired seconds
```

### Sports Covered

OddPortal scraper covers:

- Football (Soccer)
- Basketball
- Tennis
- Hockey
- Baseball

## Troubleshooting

### OddPortal Not Showing Data

1. Check if Chrome is running on port 9222:

   ```powershell
   Get-NetTCPConnection -LocalPort 9222 -ErrorAction SilentlyContinue
   ```

2. Check OddPortal process is running:

   ```powershell
   Get-Process | Where-Object { $_.ProcessName -like "*python*" }
   ```

3. Check the log output for errors

### No Matches Displayed in UI

1. Verify data file exists and has content
2. Check API endpoint is working:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/oddsmagnet/api/oddportal"
   ```
3. Check browser console for JavaScript errors

### Chrome Connection Issues

OddPortal scraper requires Chrome with remote debugging. If not started:

```powershell
cd bookmakers/oddportal
python working_scraper.py
```

## Next Steps

1. **Monitor Performance**: Check collection times and system resource usage
2. **Adjust Intervals**: Modify collection intervals based on needs
3. **Add More Leagues**: Edit `bookmakers/oddportal/working_scraper.py` to add more leagues
4. **Custom Filters**: Add sport-specific filters in the UI

## Support

For issues or questions:

- Check logs in the terminal where you started the system
- Review `bookmakers/oddportal/README.md` for scraper-specific documentation
- Check `docs/UNIFIED_SYSTEM_TUTORIAL.md` for system architecture
