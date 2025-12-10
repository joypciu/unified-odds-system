#!/usr/bin/env python3
"""
OddsMagnet.com Scraper - Working Version
Uses OddsMagnet's public API endpoints discovered through manual inspection
"""

import requests
import json
from datetime import datetime

def scrape_oddsmagnet():
    """
    Scrape odds from OddsMagnet using their API endpoints
    """
    print("="*70)
    print("ODDSMAGNET SCRAPER - API-BASED")
    print("="*70)
    
    results = {
        "source": "oddsmagnet",
        "timestamp": datetime.now().isoformat(),
        "matches": []
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://oddsmagnet.com/'
    }
    
    try:
        # Step 1: Get all football events
        print("\n[1] Fetching football events...")
        events_url = "https://oddsmagnet.com/api/events?sport_uri=football"
        response = requests.get(events_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        events_data = response.json()
        
        # API can return either a dict with 'b' key or a list directly
        if isinstance(events_data, dict):
            all_leagues = events_data.get('b', [])
        else:
            all_leagues = events_data if isinstance(events_data, list) else []
            
        print(f"    Found {len(all_leagues)} football leagues")
        
        # Step 2: Focus on major leagues (or all if you want)
        major_leagues = [
            'spain-laliga',
            'england-premier-league',
            'germany-bundesliga',
            'italy-serie-a',
            'france-ligue-1'
        ]
        
        matches_found = 0
        
        for league in all_leagues[:10]:  # Process first 10 leagues for testing
            league_slug = league.get('event_slug', '')
            league_name = league.get('event_name', '')
            
            if not league_slug:
                continue
                
            print(f"\n[2] Processing: {league_name}")
            
            # Step 3: Get matches for this league
            try:
                # Try to get subevents (matches) for this league
                subevents_url = f"https://oddsmagnet.com/api/subevents?event_uri=football/{league_slug}"
                sub_response = requests.get(subevents_url, headers=headers, timeout=10)
                sub_response.raise_for_status()
                
                subevents_data = sub_response.json()
                matches = subevents_data.get('b', [])
                
                if not matches:
                    print(f"    No matches found")
                    continue
                    
                print(f"    Found {len(matches)} matches")
                
                # Process each match
                for match in matches[:3]:  # Limit to 3 matches per league
                    match_slug = match.get('subevent_slug', '')
                    match_name = match.get('subevent_name', '')
                    match_date = match.get('subevent_date', '')
                    
                    if not match_slug:
                        continue
                    
                    print(f"      - {match_name}")
                    
                    # Step 4: Get markets for this match
                    try:
                        markets_url = f"https://oddsmagnet.com/api/markets?subevent_uri=football/{league_slug}/{match_slug}"
                        market_response = requests.get(markets_url, headers=headers, timeout=10)
                        market_response.raise_for_status()
                        
                        markets_data = market_response.json()
                        markets = markets_data.get('b', [])
                        
                        if not markets:
                            continue
                        
                        # Get first market (usually main market like win/draw/lose)
                        first_market = markets[0]
                        market_slug = first_market.get('market_slug', '')
                        market_name = first_market.get('market_name', '')
                        
                        # Step 5: Get odds for this market
                        odds_url = f"https://oddsmagnet.com/api/odds?market_uri=football/{league_slug}/{match_slug}/{market_slug}"
                        odds_response = requests.get(odds_url, headers=headers, timeout=10)
                        odds_response.raise_for_status()
                        
                        odds_data = odds_response.json()
                        odds_table = odds_data.get('b', {})
                        odds_rows = odds_table.get('data', [])
                        
                        if odds_rows:
                            match_result = {
                                "league": league_name,
                                "match": match_name,
                                "date": match_date,
                                "market": market_name,
                                "odds": []
                            }
                            
                            for row in odds_rows:
                                bet_name = row.get('bet_name', '')
                                
                                # Extract odds from available bookies
                                for bookie_code in ['vb', 'bb', 'pb', 'wh', 'ld']:  # Common bookies
                                    if bookie_code in row:
                                        bookie_data = row[bookie_code]
                                        if isinstance(bookie_data, dict):
                                            decimal_odds = bookie_data.get('back_decimal')
                                            fractional_odds = bookie_data.get('back_fractional')
                                            
                                            if decimal_odds:
                                                match_result["odds"].append({
                                                    "selection": bet_name,
                                                    "bookie": bookie_code.upper(),
                                                    "decimal": float(decimal_odds) if decimal_odds else None,
                                                    "fractional": fractional_odds
                                                })
                            
                            if match_result["odds"]:
                                results["matches"].append(match_result)
                                matches_found += 1
                    
                    except Exception as e:
                        print(f"        Error getting odds: {e}")
                        continue
            
            except Exception as e:
                print(f"    Error processing league: {e}")
                continue
        
        print(f"\n{'='*70}")
        print(f"SUMMARY: Collected odds for {matches_found} matches")
        print(f"{'='*70}")
        
        # Save to file
        output_file = "oddsmagnet_odds.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
        
        # Display sample
        if results["matches"]:
            print("\nSample data (first match):")
            print(json.dumps(results["matches"][0], indent=2))
        
        return results
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    scrape_oddsmagnet()
