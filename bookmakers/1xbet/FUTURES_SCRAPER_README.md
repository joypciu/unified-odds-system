# 1xBet Futures/Outrights Scraper

## Overview

This module collects **long-term betting markets** (futures/outrights) from 1xBet with proper odds and multiple selections. Unlike regular matches (home vs away), futures are events like "Who will win the Premier League?" with 20+ teams as selections.

## Features

✅ Fetches futures events for sport_id 2999 (Long-term bets)
✅ Collects detailed odds using GetGameZip endpoint  
✅ Parses multiple selections per event (e.g., 20 teams for league winner)
✅ Converts to OpticOdds format for API consumption
✅ Handles various market types: Winner, Top Scorer, Champion, etc.

## Data Structure

### Future Event Format

```json
{
  "event_id": 676418798,
  "sport_id": 2999,
  "sport_name": "Long-term bets",
  "league_id": 1753241,
  "league_name": "Spain. Winner",
  "event_name": "Spain Copa del Rey. 2025/26. Winner",
  "country": "Spain",
  "country_id": 78,
  "start_time": 1765278000,
  "start_time_readable": "2025-12-09T17:00:00",
  "market_type": "Winner",
  "selections": [
    {
      "selection_id": 12345,
      "selection_name": "Real Madrid",
      "coefficient": 2.71,
      "american_odds": "+171",
      "param": null,
      "group_id": 835,
      "type": 1
    },
    {
      "selection_name": "Barcelona",
      "coefficient": 2.77,
      "american_odds": "+177"
    }
    // ... 27 more selections
  ],
  "total_selections": 29,
  "last_updated": 1733733123
}
```

## Usage

### 1. Run Futures Collection

```bash
# Interactive script with confirmation
python run_futures_collection.py

# Or direct scraper
cd 1xbet
python 1xbet_futures_scraper.py
```

### 2. Output File

Data saved to: `1xbet/1xbet_futures_with_odds.json`

### 3. Access via API

```bash
# Start API server
python live_odds_viewer_clean.py

# Get futures with odds
curl http://localhost:8000/1xbet/futures
```

## API Endpoint

### GET /1xbet/futures

Returns futures in **OpticOdds format**:

```json
{
  "success": true,
  "data": [
    {
      "game_id": "1xbet_future_676418798",
      "sport": "Long-term bets",
      "league": "Spain. Winner",
      "event_name": "Spain Copa del Rey. 2025/26. Winner",
      "market_type": "Winner",
      "commence_time": "2025-12-09T17:00:00",
      "home_team": "Spain Copa del Rey. 2025/26. Winner",
      "away_team": "",
      "bookmakers": [
        {
          "key": "1xbet",
          "title": "1xBet",
          "markets": [
            {
              "key": "winner",
              "outcomes": [
                {
                  "selection_id": 12345,
                  "selection_name": "Real Madrid",
                  "price": 2.71,
                  "american_odds": "+171"
                }
                // ... more selections
              ]
            }
          ]
        }
      ],
      "metadata": {
        "event_id": 676418798,
        "total_selections": 29,
        "type": "future"
      }
    }
  ],
  "count": 35,
  "bookmaker": "1xbet",
  "type": "futures",
  "has_odds": true,
  "timestamp": "2025-12-09T11:27:03"
}
```

## Technical Details

### How It Works

1. **Fetch Events List**

   - Endpoint: `Get1x2_VZip?sports=2999`
   - Returns basic info for all futures events

2. **Fetch Detailed Odds**

   - Endpoint: `GetGameZip?id={event_id}`
   - Returns full line with selections and odds
   - Processes 5 concurrent requests (semaphore)

3. **Parse Selections**

   - Extracts odds from `E` array in Game/SubGames
   - Converts to structured selection format
   - Handles multiple market types

4. **Convert to OpticOdds**
   - Maps futures to standard format
   - Preserves all selections and odds
   - Adds metadata for filtering

### Current Stats (as of Dec 9, 2025)

- **Total futures events**: 35
- **Events with odds**: 35 (100%)
- **Total selections**: 1,174
- **Average selections per event**: 33.5

### Leagues Covered

| League                        | Events | Selections |
| ----------------------------- | ------ | ---------- |
| England. Winner               | 20     | 698        |
| UEFA Champions League. Winner | 8      | 291        |
| Spain. Winner                 | 1      | 29         |
| Awards                        | 1      | 74         |
| UEFA Champions League. Women  | 1      | 18         |
| Scotland. Winner              | 1      | 30         |
| Northern Ireland. Winner      | 1      | 12         |
| Wales. Winner                 | 1      | 12         |
| Slovakia. Winner              | 1      | 10         |

## Files

| File                           | Purpose                          |
| ------------------------------ | -------------------------------- |
| `1xbet_futures_scraper.py`     | Main scraper class               |
| `1xbet_futures_with_odds.json` | Output data with odds            |
| `1xbet_futures.json`           | Old format (basic info, no odds) |
| `run_futures_collection.py`    | User-friendly runner script      |
| `test_futures_scraper.py`      | Simple test script               |
| `validate_futures_odds.py`     | Data validation                  |

## Automation

### Schedule with Cron (Linux)

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/project && python run_futures_collection.py
```

### Schedule with Task Scheduler (Windows)

```powershell
# Run daily at 3 AM
$action = New-ScheduledTaskAction -Execute "python" -Argument "run_futures_collection.py" -WorkingDirectory "E:\vps deploy\combine 1xbet, fanduel and bet365 (main)"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "1xBet Futures Collection" -Action $action -Trigger $trigger
```

## Troubleshooting

### No Selections Found

```python
# Event has no odds in GetGameZip response
# Some futures might not have markets open yet
```

### Import Errors

```python
# Use importlib to load module dynamically
import importlib.util
spec = importlib.util.spec_from_file_location("futures_scraper", "1xbet/1xbet_futures_scraper.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
```

### API Endpoint Returns Old Data

```bash
# Restart the API server to load new data
# CTRL+C to stop, then restart
python live_odds_viewer_clean.py
```

## Differences from Regular Matches

| Aspect               | Regular Matches          | Futures                        |
| -------------------- | ------------------------ | ------------------------------ |
| **Structure**        | Team A vs Team B         | Single event with question     |
| **Selections**       | 2-3 (home/away/draw)     | 10-100+ (all possible winners) |
| **API Endpoint**     | Get1x2_VZip (sufficient) | GetGameZip (required for odds) |
| **Odds Format**      | Moneyline, spread, total | Outright odds per selection    |
| **Update Frequency** | Minutes                  | Hours/Days                     |

## Future Improvements

- [ ] Add selection name mapping (Selection 835 → "Real Madrid")
- [ ] Filter by specific leagues/competitions
- [ ] Track odds changes over time
- [ ] Add more market types (Top Scorer, Relegation, etc.)
- [ ] Implement delta updates (only changed odds)

## Example Output

```
📊 COLLECTION REPORT
════════════════════════════════════════════════════════════════════════

📊 Statistics:
   Total futures events: 35
   ✅ Events with odds: 35 (100.0%)
   📈 Total selections: 1174
   📊 Avg selections per event: 33.5

🏆 Leagues with futures (9):
   • England. Winner: 20 events
   • UEFA Champions League. Winner: 8 events
   • Spain. Winner: 1 events

✨ Sample Events with Odds:
   1. Spain Copa del Rey. 2025/26. Winner
      League: Spain. Winner
      Selections: 29
         1. Real Madrid - +171
         2. Barcelona - +177
         3. Atletico Madrid - +4900
```

## Related Documentation

- [API_ENDPOINTS.md](../API_ENDPOINTS.md) - All available endpoints
- [FUTURES_ODDS_INFO.md](FUTURES_ODDS_INFO.md) - Why futures need special handling
- [1xbet_pregame.py](1xbet_pregame.py) - Regular pregame scraper

---

**Last Updated**: December 9, 2025  
**Status**: ✅ Production Ready  
**Coverage**: 35 events, 1174 selections
