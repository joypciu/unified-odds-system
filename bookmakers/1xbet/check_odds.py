import json

# Check pregame file
with open('1xbet_pregame.json', encoding='utf-8') as f:
    pregame = json.load(f)

all_matches = pregame.get('data', {}).get('matches', [])
has_odds = [m for m in all_matches if m.get('odds_data') and len(m.get('odds_data', {})) > 0]

print(f"Total pregame matches: {len(all_matches)}")
print(f"Matches with odds: {len(has_odds)}")

if has_odds:
    sample = has_odds[0]
    print(f"\nSample match WITH odds:")
    print(f"  Sport: {sample.get('sport_name')}")
    print(f"  Teams: {sample.get('team1')} vs {sample.get('team2')}")
    print(f"  Odds: {sample.get('odds_data')}")

# Check futures file
print("\n" + "="*60)
with open('1xbet_futures.json', encoding='utf-8') as f:
    futures = json.load(f)

futures_matches = futures.get('data', {}).get('matches', [])
futures_with_odds = [m for m in futures_matches if m.get('odds_data') and len(m.get('odds_data', {})) > 0]

print(f"Total futures: {len(futures_matches)}")
print(f"Futures with odds: {len(futures_with_odds)}")

if futures_matches:
    sample = futures_matches[0]
    print(f"\nSample future event:")
    print(f"  Event: {sample.get('team1')}")
    print(f"  League: {sample.get('league_name')}")
    print(f"  Odds: {sample.get('odds_data')}")
