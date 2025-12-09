import json

# Load futures file
with open('1xbet/1xbet_futures.json', 'r', encoding='utf-8') as f:
    futures_data = json.load(f)

matches = futures_data['data']['matches']
print(f"Total futures: {len(matches)}")

# Check which ones have odds_data
has_odds = [m for m in matches if m.get('odds_data')]
print(f"Futures with non-empty odds_data: {len(has_odds)}")

# Look at sample
print("\n=== SAMPLE FUTURE EVENT ===")
sample = matches[0]
print(f"Event: {sample['team1']}")
print(f"League: {sample['league_name']}")
print(f"Sport ID: {sample['sport_id']}")
print(f"Odds data: {sample.get('odds_data')}")
print(f"Odds data type: {type(sample.get('odds_data'))}")

# Check if odds_data is empty dict or missing
print("\n=== CHECKING ALL FUTURES ===")
empty_odds = 0
for m in matches:
    odds = m.get('odds_data')
    if not odds or odds == {} or odds == '{}':
        empty_odds += 1
        
print(f"Futures with empty/missing odds: {empty_odds}/{len(matches)}")

# The issue is clear: odds_data is empty {} for all futures
# This means when the scraper parses these events, the 'E' field (odds array) is empty
# Let's check if this is because:
# 1. Futures don't have match odds (like moneyline)
# 2. Futures have different odds structure (outright winners with multiple selections)
print("\n=== CONCLUSION ===")
print("All futures have empty odds_data: {}")
print("This suggests sport_id 2999 events don't have the 'E' array in API response,")
print("or they have a different odds structure that needs special handling.")
print("\nFutures/outrights typically have:")
print("- Multiple selections (e.g., 20 teams to win a tournament)")
print("- Different odds format (not home/away, but individual selections)")
print("- May need a different API endpoint (GetLine instead of Get1x2_VZip)")
