#!/usr/bin/env python3
"""
OddsMagnet.com Scraper - Final Working Version
Combines web scraping for match URLs with API calls for odds data
"""

import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

def scrape_oddsmagnet():
    """
    Scrape odds from OddsMagnet
    """
    print("="*70)
    print("ODDSMAGNET SCRAPER - HYBRID APPROACH")
    print("="*70)
    
    results = {
        "source": "oddsmagnet",
        "timestamp": datetime.now().isoformat(),
        "matches": []
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    try:
        # Step 1: Scrape football page to get league/match structure
        print("\n[1] Scraping football page...")
        football_url = "https://oddsmagnet.com/football"
        response = requests.get(football_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all match links (pattern: /football/league/team-v-team/market)
        # These appear when accordions are expanded
        all_links = soup.find_all('a', href=True)
        
        match_urls = {}
        for link in all_links:
            href = link.get('href', '')
            
            # Match links follow pattern: /football/league-name/team-v-team/market-name
            if href.startswith('/football/') and href.count('/') >= 4:
                parts = href.strip('/').split('/')
                if len(parts) >= 4 and (' v ' in link.get_text() or '-v-' in href):
                    league = parts[1]
                    match = parts[2]
                    market = parts[3]
                    
                    key = f"{league}/{match}"
                    if key not in match_urls:
                        match_urls[key] = {
                            'league': league.replace('-', ' ').title(),
                            'match': match.replace('-v-', ' v ').replace('-', ' ').title(),
                            'markets': []
                        }
                    
                    match_urls[key]['markets'].append(market)
        
        print(f"    Found {len(match_urls)} unique matches from HTML")
        
        if len(match_urls) == 0:
            print("    No matches found in HTML. Trying direct API approach...")
            
            # Fallback: Try some known match URLs from manual testing
            # Build URLs from typical La Liga matches
            test_matches = [
                "football/spain-laliga/sociedad-v-girona/winner-in-first-15-min",
                "football/england-premier-league/liverpool-v-manchester-city/match-winner",
            ]
            
            for test_url in test_matches:
                parts = test_url.split('/')
                if len(parts) == 4:
                    league = parts[1]
                    match = parts[2]
                    market = parts[3]
                    
                    key = f"{league}/{match}"
                    match_urls[key] = {
                        'league': league.replace('-', ' ').title(),
                        'match': match.replace('-v-', ' v ').replace('-', ' ').title(),
                        'markets': [market]
                    }
        
        # Step 2: Get odds for each match
        matches_found = 0
        
        for key, match_info in list(match_urls.items())[:10]:  # Limit to first 10 matches
            league_slug, match_slug = key.split('/')
            
            print(f"\n[2] Processing: {match_info['match']}")
            print(f"    League: {match_info['league']}")
            
            # Use first market (usually main market)
            if not match_info['markets']:
                continue
                
            market_slug = match_info['markets'][0]
            
            try:
                # Get odds via API
                odds_url = f"https://oddsmagnet.com/api/odds?market_uri=football/{league_slug}/{match_slug}/{market_slug}"
                
                print(f"    Calling: {odds_url}")
                
                api_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': f'https://oddsmagnet.com/football/{league_slug}/{match_slug}/{market_slug}'
                }
                
                odds_response = requests.get(odds_url, headers=api_headers, timeout=10)
                print(f"    Status: {odds_response.status_code}")
                odds_response.raise_for_status()
                
                odds_data = odds_response.json()
                print(f"    Response keys: {odds_data.keys() if isinstance(odds_data, dict) else type(odds_data)}")
                
                # API returns data directly at top level or in 'b' key
                if 'data' in odds_data:
                    odds_rows = odds_data['data']
                elif 'b' in odds_data:
                    odds_table = odds_data.get('b', {})
                    odds_rows = odds_table.get('data', []) if isinstance(odds_table, dict) else []
                else:
                    odds_rows = []
                
                print(f"    Found {len(odds_rows)} odds rows")
                
                if odds_rows:
                    match_result = {
                        "league": match_info['league'],
                        "match": match_info['match'],
                        "market": market_slug.replace('-', ' ').title(),
                        "odds": []
                    }
                    
                    for row in odds_rows:
                        bet_name = row.get('bet_name', '').title()
                        
                        # Extract odds from all available bookies
                        for key_name, value in row.items():
                            if key_name not in ['bet_name', 'mode_date', 'best_back_decimal']:
                                if isinstance(value, dict):
                                    decimal_odds = value.get('back_decimal')
                                    fractional_odds = value.get('back_fractional')
                                    
                                    if decimal_odds:
                                        match_result["odds"].append({
                                            "selection": bet_name,
                                            "bookie": key_name.upper(),
                                            "decimal": float(decimal_odds) if decimal_odds else None,
                                            "fractional": fractional_odds
                                        })
                    
                    if match_result["odds"]:
                        results["matches"].append(match_result)
                        matches_found += 1
                        print(f"    ✓ Found {len(match_result['odds'])} odds")
                    else:
                        print(f"    ✗ No odds available")
            
            except Exception as e:
                print(f"    Error: {e}")
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
