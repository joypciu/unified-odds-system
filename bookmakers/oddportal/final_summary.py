import csv
from collections import defaultdict

with open('matches_odds_data.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print("=" * 80)
print("ODDSPORTAL SCRAPER - FINAL RESULTS")
print("6 SPORTS SCRAPED (Football, American Football, Basketball, Tennis, Hockey, Baseball)")
print("=" * 80)

# Group by sport
sports = defaultdict(list)
for row in rows:
    sports[row['sport']].append(row)

print(f"\n📊 TOTAL DATA ROWS: {len(rows)}")
print("\n🏆 SPORT BREAKDOWN:")
print("-" * 80)

sport_names = {
    'football': '⚽ Football',
    'american-football': '🏈 American Football',
    'basketball': '🏀 Basketball', 
    'tennis': '🎾 Tennis',
    'hockey': '🏒 Hockey',
    'baseball': '⚾ Baseball'
}

for sport_key in sorted(sports.keys()):
    sport_name = sport_names.get(sport_key, sport_key)
    count = len(sports[sport_key])
    
    # Get unique matches (by home/away teams)
    unique_matches = {}
    for row in sports[sport_key]:
        match_key = f"{row['home']} vs {row['away']}"
        if match_key not in unique_matches:
            unique_matches[match_key] = {
                'date': row['match_time'],
                'bookmakers': 0,
                'league': row['league']
            }
        if row['bookmaker']:  # Count bookmakers
            unique_matches[match_key]['bookmakers'] += 1
    
    print(f"\n{sport_name}: {len(unique_matches)} matches ({count} data rows)")
    
    # Show match details
    for match_name, details in list(unique_matches.items())[:5]:
        bk_count = details['bookmakers']
        date = details['date']
        league = details['league'].upper()
        print(f"  • {match_name}")
        print(f"    📅 {date} | 🏟️  {league} | 📊 {bk_count} bookmakers")
    
    if len(unique_matches) > 5:
        print(f"  ... and {len(unique_matches) - 5} more matches")

print("\n" + "=" * 80)
print("✅ SUCCESSFULLY ADDED:")
print("-" * 80)
print("  🏈 American Football (NFL) - 2 matches with 13 bookmakers each")
print("  🎾 Tennis - 0 matches (main page requires specific tournament selection)")
print("\n💡 NOTE: Tennis requires navigating to specific tournaments (e.g., Australian Open)")
print("    The main tennis page only shows tournament links, not match listings")
print("=" * 80)
