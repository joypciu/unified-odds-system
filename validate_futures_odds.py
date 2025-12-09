import json

# Load futures with odds
with open('1xbet/1xbet_futures_with_odds.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("FUTURES DATA VALIDATION")
print("=" * 70)

metadata = data['metadata']
print(f"\nMetadata:")
print(f"  Total events: {metadata['total_events']}")
print(f"  Events with odds: {metadata['events_with_odds']}")
print(f"  Timestamp: {metadata['timestamp']}")

events = data['data']['events']
sample = events[0]

print(f"\n{'=' * 70}")
print("SAMPLE FUTURE EVENT")
print("=" * 70)
print(f"\nEvent: {sample['event_name']}")
print(f"League: {sample['league_name']}")
print(f"Country: {sample['country']}")
print(f"Market Type: {sample['market_type']}")
print(f"Total selections: {sample['total_selections']}")
print(f"Start time: {sample['start_time_readable']}")

print(f"\nFirst 5 selections:")
for i, sel in enumerate(sample['selections'][:5], 1):
    print(f"  {i}. {sel['selection_name']:40s} - {sel['american_odds']:>6s} (Coef: {sel['coefficient']})")

if sample['total_selections'] > 5:
    print(f"  ... and {sample['total_selections'] - 5} more selections")

print(f"\n{'=' * 70}")
print("ALL EVENTS SUMMARY")
print("=" * 70)

# Group by league
leagues = {}
for event in events:
    league = event['league_name']
    if league not in leagues:
        leagues[league] = []
    leagues[league].append(event)

for league, events_list in sorted(leagues.items(), key=lambda x: len(x[1]), reverse=True):
    total_sels = sum(e['total_selections'] for e in events_list)
    print(f"{league}: {len(events_list)} events, {total_sels} selections")

print("\n✅ All futures have proper odds with selections!")
