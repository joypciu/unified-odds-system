#!/usr/bin/env python3
"""
OddsMagnet Complete Multi-Market Scraper
Collects odds from ALL available markets for football matches
"""

import requests
import json
from datetime import datetime
import time
from typing import Dict, List, Optional

class OddsMagnetMultiMarketScraper:
    
    # Bookmaker code to full name mapping
    BOOKMAKER_NAMES = {
        'bh': 'Bet-at-Home',
        'eb': '10Bet',
        'ee': '888sport',
        'fr': 'Betfred',
        'nt': 'Netbet',
        'tn': 'Tonybet',
        'vb': 'Vbet',
        'vc': 'BetVictor',
        'wh': 'William Hill',
        'xb': '1xBet',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://oddsmagnet.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
    def establish_session(self, match_url: str):
        """Visit the match page to establish a valid session"""
        try:
            self.headers['Referer'] = match_url
            response = self.session.get(match_url, headers=self.headers, timeout=15)
            return response.status_code == 200
        except Exception as e:
            print(f"Error establishing session: {e}")
            return False
    
    def get_leagues(self) -> List[Dict]:
        """Get all football leagues"""
        print("\n[FETCHING LEAGUES]")
        
        url = f"{self.base_url}/api/events?sport_uri=football"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            leagues = response.json()
            
            if isinstance(leagues, list):
                print(f"  Found {len(leagues)} leagues")
                return leagues
            else:
                print(f"  Unexpected response format")
                return []
                
        except Exception as e:
            print(f"  Error: {e}")
            return []
    
    def get_matches_for_league(self, league_slug: str) -> List[Dict]:
        """Get all matches for a specific league"""
        print(f"\n[FETCHING MATCHES: {league_slug}]")
        
        url = f"{self.base_url}/api/subevents?event_uri=football/{league_slug}"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Response is a dict with league name as key
            if isinstance(data, dict):
                # Get first key (league name)
                league_key = list(data.keys())[0]
                matches = data[league_key]
                print(f"  Found {len(matches)} matches")
                return matches
            else:
                print(f"  No matches found")
                return []
                
        except Exception as e:
            print(f"  Error: {e}")
            return []
    
    def get_all_markets_for_match(self, match_uri: str) -> Dict[str, List]:
        """Get all available markets for a match"""
        print(f"\n[FETCHING MARKETS: {match_uri}]")
        
        url = f"{self.base_url}/api/markets?subevent_uri={match_uri}"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            markets_data = response.json()
            
            if isinstance(markets_data, dict):
                total_markets = sum(len(v) for v in markets_data.values())
                print(f"  Found {len(markets_data)} categories with {total_markets} total markets")
                return markets_data
            else:
                print(f"  Unexpected response format")
                return {}
                
        except Exception as e:
            print(f"  Error: {e}")
            return {}
    
    def get_odds_for_market(self, market_uri: str, market_name: str) -> Optional[Dict]:
        """Get odds for a specific market"""
        url = f"{self.base_url}/api/odds?market_uri={market_uri}"
        
        # Update referer for this specific market
        self.headers['Referer'] = f"{self.base_url}/{market_uri}"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            odds_data = response.json()
            
            # New API format: {"schema": {...}, "data": [...]}
            if isinstance(odds_data, dict) and 'data' in odds_data:
                odds_rows = odds_data['data']
                
                if not odds_rows:
                    return None
                
                # Extract bookmaker codes from schema
                schema = odds_data.get('schema', {})
                fields = schema.get('fields', [])
                bookie_codes = [f['name'] for f in fields 
                               if f['name'] not in ['bet_name', 'mode_date', 'best_back_decimal']]
                
                # Process odds with bookmaker names and comparison
                processed_odds = []
                
                for row in odds_rows:
                    bet_name = row.get('bet_name', '')
                    best_odds_value = row.get('best_back_decimal')
                    
                    # Extract odds from each bookmaker
                    for bookie_code in bookie_codes:
                        if bookie_code in row and isinstance(row[bookie_code], dict):
                            bookie_data = row[bookie_code]
                            
                            current_odds = bookie_data.get('back_decimal')
                            last_odds = bookie_data.get('last_back_decimal')
                            
                            if current_odds:
                                current_value = float(current_odds)
                                last_value = float(last_odds) if last_odds else None
                                
                                # Determine odds movement
                                odds_movement = None
                                odds_change = None
                                if last_value:
                                    if current_value > last_value:
                                        odds_movement = 'up'
                                        odds_change = round(current_value - last_value, 2)
                                    elif current_value < last_value:
                                        odds_movement = 'down'
                                        odds_change = round(last_value - current_value, 2)
                                    else:
                                        odds_movement = 'unchanged'
                                        odds_change = 0
                                
                                # Check if this is the best odds
                                is_best_odds = False
                                if best_odds_value:
                                    is_best_odds = abs(current_value - float(best_odds_value)) < 0.01
                                
                                # Get bookmaker display name
                                bookmaker_name = self.BOOKMAKER_NAMES.get(
                                    bookie_code.lower(), 
                                    bookie_code.upper()
                                )
                                
                                processed_odds.append({
                                    'selection': bet_name,
                                    'bookmaker_code': bookie_code,
                                    'bookmaker_name': bookmaker_name,
                                    'decimal_odds': current_value,
                                    'fractional_odds': bookie_data.get('back_fractional'),
                                    'previous_odds': last_value,
                                    'odds_movement': odds_movement,
                                    'odds_change': odds_change,
                                    'is_best_odds': is_best_odds,
                                    'clickout_url': bookie_data.get('back_clickout')
                                })
                
                # Get unique bookmakers summary
                unique_bookmakers = list(set(o['bookmaker_code'] for o in processed_odds))
                bookmaker_summary = []
                for bookie_code in unique_bookmakers:
                    bookie_name = self.BOOKMAKER_NAMES.get(
                        bookie_code.lower(),
                        bookie_code.upper()
                    )
                    bookmaker_summary.append({
                        'code': bookie_code,
                        'name': bookie_name
                    })
                
                return {
                    'market_name': market_name,
                    'market_uri': market_uri,
                    'selections_count': len(odds_rows),
                    'bookmakers_count': len(unique_bookmakers),
                    'bookmakers': bookmaker_summary,
                    'odds': processed_odds,
                    'market_best_odds': float(best_odds_value) if best_odds_value else None,
                    'last_updated': odds_rows[0].get('mode_date') if odds_rows else None
                }
            
            # Old API format fallback: {"b": {"data": [...]}}
            elif isinstance(odds_data, dict) and 'b' in odds_data:
                odds_table = odds_data['b']
                if isinstance(odds_table, dict) and 'data' in odds_table:
                    odds_rows = odds_table['data']
                    
                    if not odds_rows:
                        return None
                    
                    processed_odds = []
                    
                    for row in odds_rows:
                        bet_name = row.get('bet_name', '')
                        
                        for key, value in row.items():
                            if key not in ['bet_name', 'mode_date', 'best_back_decimal']:
                                if isinstance(value, dict) and 'back_decimal' in value:
                                    decimal_odds = value.get('back_decimal')
                                    if decimal_odds:
                                        processed_odds.append({
                                            'selection': bet_name,
                                            'bookmaker': key.upper(),
                                            'decimal_odds': float(decimal_odds) if decimal_odds else None,
                                            'fractional_odds': value.get('back_fractional')
                                        })
                    
                    return {
                        'market_name': market_name,
                        'market_uri': market_uri,
                        'odds': processed_odds
                    }
            
            return None
            
        except Exception as e:
            print(f"    Error fetching odds for {market_name}: {e}")
            return None
    
    def scrape_match_all_markets(self, match_uri: str, match_name: str, 
                                 league_name: str, match_date: str,
                                 market_filter: Optional[List[str]] = None,
                                 max_markets_per_category: Optional[int] = None) -> Dict:
        """
        Scrape all markets for a single match
        
        Args:
            match_uri: Full URI like "football/spain-laliga/real-madrid-v-seville"
            match_name: Display name of match
            league_name: League name
            match_date: Match date/time
            market_filter: Optional list of market categories to include (e.g., ['popular markets', 'over under betting'])
            max_markets_per_category: Optional limit on markets per category
        """
        print(f"\n{'='*80}")
        print(f"SCRAPING: {match_name}")
        print(f"{'='*80}")
        
        # Establish session by visiting match page
        match_url = f"{self.base_url}/{match_uri}"
        if not self.establish_session(match_url):
            print("  Failed to establish session")
            return None
        
        time.sleep(0.5)  # Be polite
        
        # Get all markets
        markets_data = self.get_all_markets_for_match(match_uri)
        
        if not markets_data:
            print("  No markets found")
            return None
        
        result = {
            'match_name': match_name,
            'league': league_name,
            'match_date': match_date,
            'match_uri': match_uri,
            'markets': {}
        }
        
        total_odds_collected = 0
        
        # Iterate through each category
        for category, markets_list in markets_data.items():
            
            # Apply filter if specified
            if market_filter and category not in market_filter:
                continue
            
            print(f"\n  Category: {category} ({len(markets_list)} markets)")
            
            result['markets'][category] = []
            
            # Limit markets per category if specified
            markets_to_process = markets_list[:max_markets_per_category] if max_markets_per_category else markets_list
            
            for market_info in markets_to_process:
                # Each market is [name, full_uri, slug]
                market_name = market_info[0]
                market_uri = market_info[1]
                market_slug = market_info[2]
                
                print(f"    - {market_name}...", end=" ")
                
                # Get odds for this market
                odds_data = self.get_odds_for_market(market_uri, market_name)
                
                if odds_data:
                    odds_count = len(odds_data.get('odds', []))
                    print(f"✓ {odds_count} odds")
                    result['markets'][category].append(odds_data)
                    total_odds_collected += odds_count
                else:
                    print("✗ No data")
                
                time.sleep(0.3)  # Be polite between requests
        
        result['total_odds_collected'] = total_odds_collected
        
        print(f"\n  {'─'*76}")
        print(f"  Total odds collected: {total_odds_collected}")
        
        return result
    
    def scrape_league(self, league_slug: str, league_name: str,
                     max_matches: Optional[int] = None,
                     market_filter: Optional[List[str]] = None,
                     max_markets_per_category: Optional[int] = None) -> Dict:
        """
        Scrape all matches from a league with all their markets
        
        Args:
            league_slug: League slug like "spain-laliga"
            league_name: Display name of league
            max_matches: Optional limit on number of matches to process
            market_filter: Optional list of market categories to include
            max_markets_per_category: Optional limit on markets per category
        """
        print(f"\n{'#'*80}")
        print(f"SCRAPING LEAGUE: {league_name}")
        print(f"{'#'*80}")
        
        matches = self.get_matches_for_league(league_slug)
        
        if not matches:
            return None
        
        # Limit matches if specified
        matches_to_process = matches[:max_matches] if max_matches else matches
        
        results = {
            'league': league_name,
            'league_slug': league_slug,
            'total_matches': len(matches),
            'processed_matches': len(matches_to_process),
            'timestamp': datetime.now().isoformat(),
            'matches': []
        }
        
        for match in matches_to_process:
            # Match format: [name, league_uri, full_match_uri, match_slug, date, home, away, sport]
            # Index 0: match name
            # Index 2: full match URI (e.g., "football/spain-laliga/sociedad-v-girona")
            # Index 4: match date
            match_name = match[0]
            match_uri = match[2] if len(match) > 2 else None
            match_date = match[4] if len(match) > 4 else None
            
            if not match_uri:
                print(f"  Skipping {match_name} - no URI found")
                continue
            
            # Scrape this match
            match_data = self.scrape_match_all_markets(
                match_uri, 
                match_name, 
                league_name, 
                match_date,
                market_filter=market_filter,
                max_markets_per_category=max_markets_per_category
            )
            
            if match_data:
                results['matches'].append(match_data)
            
            time.sleep(1)  # Be polite between matches
        
        return results
    
    def scrape_multiple_leagues(self, league_list: List[str],
                               max_matches_per_league: Optional[int] = 3,
                               market_filter: Optional[List[str]] = None,
                               max_markets_per_category: Optional[int] = None) -> Dict:
        """
        Scrape multiple leagues
        
        Args:
            league_list: List of league slugs like ["spain-laliga", "england-premier-league"]
            max_matches_per_league: Max matches to process per league
            market_filter: Optional list of market categories to include
            max_markets_per_category: Optional limit on markets per category
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'source': 'oddsmagnet',
            'leagues': []
        }
        
        for league_slug in league_list:
            league_name = league_slug.replace('-', ' ').title()
            
            league_data = self.scrape_league(
                league_slug,
                league_name,
                max_matches=max_matches_per_league,
                market_filter=market_filter,
                max_markets_per_category=max_markets_per_category
            )
            
            if league_data:
                results['leagues'].append(league_data)
            
            time.sleep(2)  # Be polite between leagues
        
        return results


def main():
    """Example usage"""
    scraper = OddsMagnetMultiMarketScraper()
    
    # Example 1: Scrape a single match with ALL markets
    print("\n" + "="*80)
    print("EXAMPLE 1: Single match, all markets")
    print("="*80)
    
    match_data = scraper.scrape_match_all_markets(
        match_uri="football/spain-laliga/real-madrid-v-seville",
        match_name="Real Madrid v Seville",
        league_name="Spain La Liga",
        match_date="2025-12-20"
    )
    
    if match_data:
        # Save to file
        filename = "oddsmagnet_single_match_all_markets.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(match_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to: {filename}")
    
    # Example 2: Scrape league with filtered markets
    print("\n" + "="*80)
    print("EXAMPLE 2: League with popular markets only")
    print("="*80)
    
    league_data = scraper.scrape_league(
        league_slug="spain-laliga",
        league_name="Spain La Liga",
        max_matches=2,
        market_filter=['popular markets', 'over under betting'],
        max_markets_per_category=3
    )
    
    if league_data:
        filename = "oddsmagnet_league_filtered_markets.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(league_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to: {filename}")
    
    # Example 3: Scrape multiple leagues
    print("\n" + "="*80)
    print("EXAMPLE 3: Multiple leagues")
    print("="*80)
    
    multi_league_data = scraper.scrape_multiple_leagues(
        league_list=["spain-laliga", "england-premier-league"],
        max_matches_per_league=1,
        market_filter=['popular markets'],
        max_markets_per_category=2
    )
    
    if multi_league_data:
        filename = "oddsmagnet_multi_league.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(multi_league_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to: {filename}")
    
    print("\n" + "="*80)
    print("SCRAPING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
