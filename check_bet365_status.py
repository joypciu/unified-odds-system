"""
Bet365 Scraper Status Check
Tests both pregame and live scrapers
"""
import json
import os
from datetime import datetime
from pathlib import Path

print("="*70)
print("BET365 SCRAPER STATUS CHECK")
print("="*70)

# Check pregame data
pregame_file = Path("bet365/bet365_current_pregame.json")
if pregame_file.exists():
    with open(pregame_file, 'r', encoding='utf-8') as f:
        pregame_data = json.load(f)
    
    timestamp = pregame_data.get('extraction_info', {}).get('timestamp', 'Unknown')
    total_games = pregame_data.get('extraction_info', {}).get('total_games', 0)
    sports = list(pregame_data.get('sports_data', {}).keys())
    
    print(f"\n✅ PREGAME DATA FOUND:")
    print(f"   Last updated: {timestamp}")
    print(f"   Total games: {total_games}")
    print(f"   Sports: {', '.join(sports)}")
    
    # Sample game
    if sports:
        first_sport = sports[0]
        games = pregame_data['sports_data'][first_sport]['games']
        if games:
            sample = games[0]
            print(f"\n   Sample ({first_sport}):")
            print(f"     {sample.get('team1', 'N/A')} vs {sample.get('team2', 'N/A')}")
            print(f"     Time: {sample.get('time', 'N/A')}")
            print(f"     Odds: {sample.get('odds', {})}")
else:
    print(f"\n❌ PREGAME DATA NOT FOUND")

# Check live data
live_file = Path("bet365/bet365_live_current.json")
if live_file.exists():
    with open(live_file, 'r', encoding='utf-8') as f:
        live_data = json.load(f)
    
    last_updated = live_data.get('last_updated', 'Unknown')
    total_matches = live_data.get('total_matches', 0)
    
    print(f"\n✅ LIVE DATA FOUND:")
    print(f"   Last updated: {last_updated}")
    print(f"   Total live matches: {total_matches}")
else:
    print(f"\n⚠️  LIVE DATA NOT FOUND (may not have been run yet)")

print(f"\n{'='*70}")
print(f"RECOMMENDATION:")
print(f"{'='*70}")

# Calculate data age
try:
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    age_hours = (datetime.now() - dt).total_seconds() / 3600
    
    if age_hours > 48:
        print(f"⚠️  Pregame data is {age_hours:.1f} hours old")
        print(f"   Consider running: python bet365/bet365_pregame_homepage_scraper.py")
    else:
        print(f"✅ Pregame data is fresh ({age_hours:.1f} hours old)")
except:
    print(f"⚠️  Could not determine data age")

if not live_file.exists():
    print(f"💡 To test live scraper: python bet365/bet365_live_scraper.py")

print(f"\n{'='*70}")
