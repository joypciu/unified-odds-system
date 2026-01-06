import json

with open('matches_odds_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("FINAL SCRAPER RESULTS - 6 SPORTS")
print("=" * 70)

print(f"\nTotal matches: {len(data)}")

# Sports breakdown
sports = {}
for match in data:
    sport = match.get('sport', 'Unknown')
    sports[sport] = sports.get(sport, 0) + 1

print("\nSports breakdown:")
for sport, count in sorted(sports.items()):
    print(f"  {sport}: {count} matches")

# American Football details
am_football = [m for m in data if 'American Football' in m.get('sport', '')]
print(f"\n{'='*70}")
print(f"🏈 AMERICAN FOOTBALL - {len(am_football)} matches")
print("=" * 70)
for match in am_football:
    teams = match.get('teams', 'N/A')
    bk_count = len(match.get('bookmakers', []))
    date = match.get('match_date', 'N/A')
    print(f"  {teams}")
    print(f"    📅 {date} | 📊 {bk_count} bookmakers")

# Tennis details
tennis = [m for m in data if 'Tennis' in m.get('sport', '')]
print(f"\n{'='*70}")
print(f"🎾 TENNIS - {len(tennis)} matches")
print("=" * 70)
if tennis:
    for match in tennis[:10]:
        teams = match.get('teams', 'N/A')
        bk_count = len(match.get('bookmakers', []))
        date = match.get('match_date', 'N/A')
        print(f"  {teams}")
        print(f"    📅 {date} | 📊 {bk_count} bookmakers")
else:
    print("  ⚠️  No tennis matches found")
    print("  ℹ️  Tennis main page shows tournament links, not direct matches")

print("\n" + "=" * 70)
print("QUALITY METRICS")
print("=" * 70)
with_bookmakers = [m for m in data if m.get('bookmakers')]
with_dates = [m for m in data if m.get('match_date') and m['match_date'] != 'Not available']
print(f"Matches with bookmakers: {len(with_bookmakers)}/{len(data)} ({len(with_bookmakers)*100//len(data) if data else 0}%)")
print(f"Matches with dates: {len(with_dates)}/{len(data)} ({len(with_dates)*100//len(data) if data else 0}%)")
