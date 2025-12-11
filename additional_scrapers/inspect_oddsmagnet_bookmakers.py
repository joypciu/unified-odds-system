#!/usr/bin/env python3
"""
Inspect OddsMagnet to discover all tracked bookmakers
"""

import requests
import json
from bs4 import BeautifulSoup

def get_bookmakers_from_oddsmagnet():
    """Fetch a sample match to see which bookmakers are tracked"""
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    # First get the homepage to establish session
    print("Establishing session...")
    session.get('https://oddsmagnet.com', headers=headers)
    
    # Get football events
    print("\nFetching football leagues...")
    events_url = "https://oddsmagnet.com/api/events?sport_uri=football"
    events = session.get(events_url, headers=headers).json()
    
    if events and len(events) > 0:
        # Get first league
        first_league = events[0]
        league_slug = first_league.get('event_slug')
        print(f"League: {first_league.get('event_name')}")
        
        # Get matches from this league
        matches_url = f"https://oddsmagnet.com/api/subevents?event_uri=football/{league_slug}"
        matches_data = session.get(matches_url, headers=headers).json()
        
        if matches_data:
            league_key = list(matches_data.keys())[0]
            matches = matches_data[league_key]
            
            if matches and len(matches) > 0:
                # Get first match
                first_match = matches[0]
                match_uri = first_match[2] if len(first_match) > 2 else None
                match_name = first_match[0] if len(first_match) > 0 else None
                
                print(f"Match: {match_name}")
                print(f"URI: {match_uri}")
                
                # Get markets for this match
                markets_url = f"https://oddsmagnet.com/api/markets?subevent_uri={match_uri}"
                markets_data = session.get(markets_url, headers=headers).json()
                
                if markets_data:
                    # Get first available market
                    for category, markets_list in markets_data.items():
                        if markets_list and len(markets_list) > 0:
                            market_uri = markets_list[0][1]
                            market_name = markets_list[0][0]
                            
                            print(f"\nMarket: {market_name}")
                            print(f"Category: {category}")
                            
                            # Get odds to see bookmaker codes
                            odds_url = f"https://oddsmagnet.com/api/odds?market_uri={market_uri}"
                            odds_data = session.get(odds_url, headers=headers).json()
                            
                            if odds_data and 'schema' in odds_data:
                                schema = odds_data['schema']
                                fields = schema.get('fields', [])
                                
                                print("\n" + "="*80)
                                print("BOOKMAKERS FOUND IN ODDSMAGNET:")
                                print("="*80)
                                
                                bookmakers = []
                                for field in fields:
                                    field_name = field.get('name', '')
                                    if field_name not in ['bet_name', 'mode_date', 'best_back_decimal']:
                                        bookmakers.append(field_name)
                                
                                for i, bookie in enumerate(bookmakers, 1):
                                    print(f"{i:2d}. {bookie}")
                                
                                print(f"\nTotal: {len(bookmakers)} bookmakers")
                                
                                # Save to file
                                result = {
                                    'bookmakers': bookmakers,
                                    'total': len(bookmakers),
                                    'sample_match': match_name,
                                    'sample_market': market_name
                                }
                                
                                with open('oddsmagnet_bookmakers.json', 'w') as f:
                                    json.dump(result, f, indent=2)
                                
                                print("\n✓ Saved to: oddsmagnet_bookmakers.json")
                                
                                # Also check actual data to see bookmaker info
                                if 'data' in odds_data and len(odds_data['data']) > 0:
                                    first_row = odds_data['data'][0]
                                    print("\n" + "="*80)
                                    print("SAMPLE ODDS DATA:")
                                    print("="*80)
                                    
                                    for bookie in bookmakers[:5]:  # Show first 5
                                        if bookie in first_row and isinstance(first_row[bookie], dict):
                                            bookie_data = first_row[bookie]
                                            print(f"\n{bookie}:")
                                            print(f"  Current odds: {bookie_data.get('back_decimal')}")
                                            print(f"  Previous odds: {bookie_data.get('last_back_decimal')}")
                                            print(f"  Fractional: {bookie_data.get('back_fractional')}")
                                
                                return bookmakers
                            
                            break
    
    return []


if __name__ == "__main__":
    bookmakers = get_bookmakers_from_oddsmagnet()
    
    if bookmakers:
        print("\n" + "="*80)
        print("PYTHON DICT FORMAT:")
        print("="*80)
        print("BOOKMAKER_NAMES = {")
        for bookie in sorted(bookmakers):
            # Try to create a readable name
            name = bookie.replace('_', ' ').title()
            print(f"    '{bookie}': '{name}',")
        print("}")
