# Futures/Long-term Bets Odds Issue

## Problem

The `1xbet_futures.json` file contains 35 long-term bet events (sport_id 2999) but **all have empty odds_data**.

## Root Cause

Futures/outrights have a **different odds structure** than regular matches:

### Regular Match Structure

- **Format**: Team A vs Team B
- **Odds**: Home/Away/Draw (moneyline, spread, total)
- **API Field**: `E` array with home/away odds

### Futures/Outright Structure

- **Format**: Single question (e.g., "Who will win Copa del Rey 2025/26?")
- **Odds**: Multiple selections (e.g., 20 teams each with their own odds)
- **API Field**: Requires different endpoint - `GetLine` instead of `Get1x2_VZip`

## Current Implementation

```python
# 1xbet_pregame.py uses Get1x2_VZip endpoint
url = f"{self.base_url}/service-api/LineFeed/Get1x2_VZip"

# This endpoint returns:
{
  "E": [  # Odds array for MATCHES (home/away format)
    {"C": 1.75, "CV": "-133", "G": 1, "T": 1},  # Home win
    {"C": 2.05, "CV": "+105", "G": 1, "T": 3}   # Away win
  ]
}
```

For sport_id 2999 (Long-term bets), the `E` array is **empty** because these aren't matches - they're outrights with multiple possible outcomes.

## Solution Options

### Option 1: Use GetLine Endpoint (Recommended)

Fetch full line/markets for futures events:

```python
url = f"{self.base_url}/service-api/LineFeed/GetLine"
params = {
    'eventId': match_id,  # Individual event ID
    'lng': 'en'
}
```

This returns **all betting markets** including outright winners with multiple selections.

### Option 2: Remove Futures from Unified System

Since futures have fundamentally different structure:

- Keep them in separate `1xbet_futures.json` file
- Don't include in unified odds system (futures aren't comparable to live/pregame matches)
- Mark as "informational only" until proper scraping implemented

### Option 3: Accept Empty Odds

- Futures listing without odds still provides event information
- Shows what tournaments/competitions have outright markets
- Odds can be added later when GetLine implementation is ready

## Current Status

- ✅ Futures events identified and separated (35 events)
- ✅ API endpoint `/1xbet/futures` serves futures in OpticOdds format
- ❌ Odds data is empty for all futures events
- ⏳ Need GetLine endpoint implementation to fetch outright odds

## Recommendation

**For now, accept that futures don't have odds.** The current implementation:

- Successfully identifies long-term events (sport_id 2999)
- Separates them into dedicated file
- Provides event metadata (league, start time, etc.)
- API endpoint works and returns OpticOdds format

The odds parsing for outrights requires **significant additional work** because:

1. Need to make individual API calls per event (GetLine)
2. Parse complex market structure with multiple selections
3. Convert outright odds to comparable format
4. Handle different outcome types (team winners, player props, etc.)

This is a **separate feature** beyond the scope of basic 1xbet integration.
