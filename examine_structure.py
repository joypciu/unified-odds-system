import json

with open('debug_raw_future_event.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

value = data['Value']
print("Top-level keys:", list(value.keys()))
print()

# Check if 'B' contains bets/selections
if 'B' in value:
    bets = value['B']
    print(f"Total bets (B): {len(bets)}")
    print("\nFirst 3 bets structure:")
    for i, bet in enumerate(bets[:3], 1):
        print(f"\n--- Bet {i} ---")
        print(json.dumps(bet, indent=2, ensure_ascii=False))
else:
    print("No 'B' field found")

# Check 'E' for odds
if 'E' in value:
    odds = value['E']
    print(f"\n\nTotal odds (E): {len(odds)}")
    print("\nFirst 3 odds:")
    for i, odd in enumerate(odds[:3], 1):
        print(f"\n--- Odd {i} ---")
        print(json.dumps(odd, indent=2, ensure_ascii=False))
