# Bet365 Scrapers Structure

## Current Scrapers

### Pregame Scrapers

- **`bet365_pregame_homepage_scraper.py`** - Uses bet365 homepage to extract pregame odds
  - Output: `bet365_current_pregame.json`
  - Comprehensive multi-sport extraction from homepage
  - Supports: NBA, NHL, NFL, NCAAB, NCAAF, UFC, PGA, UCL, etc.

### Live Scrapers

- **`bet365_live_concurrent_scraper.py`** - Multi-sport concurrent live scraper
  - Output: `bet365_live_current.json`
  - Persistent tab pool for multiple sports
  - Concurrent extraction with timeout protection
  - Uses isolated Chrome browser
- **`bet365_live_scraper.py`** - Base live scraper class
  - Parent class for concurrent scraper
  - Provides core extraction functionality
  - Browser automation with Patchright

### Monitor Scripts

- **`bet365_pregame_monitor.py`** - Continuous pregame monitoring
  - Uses `bet365_pregame_homepage_scraper.py`

## Adding New Sport-Specific Scrapers

When adding individual sport scrapers to the `bet365/` folder:

1. **File naming convention**: `bet365_{sport}_{type}_scraper.py`

   - Example: `bet365_nba_pregame_scraper.py`
   - Example: `bet365_soccer_live_scraper.py`

2. **Output files**: `bet365_{sport}_{type}.json`

   - Example: `bet365_nba_pregame.json`
   - Example: `bet365_soccer_live.json`

3. **Integration with API**:

   - Add endpoint in `live_odds_viewer_clean.py`
   - Update file paths in `unified_odds_collector.py`
   - Add to `run_unified_system.py` for unified collection

4. **Data format**: Follow OpticOdds format structure
   ```json
   {
     "extraction_info": {},
     "sports_data": {
       "sport_name": {
         "games": []
       }
     }
   }
   ```

## File Structure

```
bet365/
├── bet365_pregame_homepage_scraper.py   # Homepage pregame scraper
├── bet365_live_concurrent_scraper.py    # Multi-sport live scraper
├── bet365_live_scraper.py               # Base live scraper class
├── bet365_pregame_monitor.py            # Pregame monitoring
├── bet365_current_pregame.json          # Pregame output
├── bet365_live_current.json             # Live output
└── [future sport-specific scrapers]     # Individual sport scrapers
```

## API Endpoints

### Current

- `/bet365/pregame` - Homepage scraper pregame data
- `/bet365/live` - Concurrent scraper live data

### Future (when adding sport-specific scrapers)

- `/bet365/{sport}/pregame` - Sport-specific pregame
- `/bet365/{sport}/live` - Sport-specific live
