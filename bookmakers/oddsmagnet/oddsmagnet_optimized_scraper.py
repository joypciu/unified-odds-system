#!/usr/bin/env python3
"""
OddsMagnet Optimized Multi-Market Scraper
High-performance version with concurrent requests and intelligent rate limiting
"""

import requests
import json
from datetime import datetime
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

class RateLimiter:
    """Thread-safe token bucket rate limiter with burst support"""
    def __init__(self, requests_per_second: float = 3.0, burst_size: int = 10):
        self.rate = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self.lock = Lock()
    
    def wait(self):
        """Wait if necessary to respect rate limit (token bucket algorithm)"""
        with self.lock:
            current_time = time.time()
            
            # Refill tokens based on time elapsed
            time_passed = current_time - self.last_update
            self.tokens = min(self.burst_size, self.tokens + time_passed * self.rate)
            self.last_update = current_time
            
            # If we have tokens, consume one and proceed
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            
            # Otherwise wait until we have a token
            wait_time = (1.0 - self.tokens) / self.rate
            time.sleep(wait_time)
            self.tokens = 0
            self.last_update = time.time()


class OddsMagnetOptimizedScraper:
    """Optimized scraper with concurrent requests and connection pooling"""
    
    # Bookmaker code to full name mapping (based on OddsMagnet's actual codes)
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
    
    def __init__(self, max_workers: int = 5, requests_per_second: float = 3.0):
        """
        Initialize optimized scraper
        
        Args:
            max_workers: Number of concurrent threads (default: 5)
            requests_per_second: Rate limit (default: 3.0)
        """
        self.max_workers = max_workers
        # Token bucket with burst capacity for better throughput
        self.rate_limiter = RateLimiter(requests_per_second, burst_size=max_workers * 2)
        self.base_url = "https://oddsmagnet.com"
        
        # Enhanced session with larger connection pool
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers * 2,
            pool_maxsize=max_workers * 4,
            max_retries=2,
            pool_block=False
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
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
        
        # Enhanced cache with TTL
        self._cache = {}
        self._cache_ttl = {}  # Timestamp for cache expiry
        self._cache_lock = Lock()
        self._cache_max_age = 300  # 5 minutes cache
    
    def _make_request(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """Make rate-limited request with retry logic"""
        self.rate_limiter.wait()
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout for {url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error for {url}: {e}")
            return None
        except json.JSONDecodeError:
            logging.error(f"JSON decode error for {url}")
            return None
    
    def get_all_markets_for_match(self, match_uri: str) -> Dict[str, List]:
        """Get all available markets for a match (cached with TTL)"""
        # Check cache with TTL validation
        with self._cache_lock:
            if match_uri in self._cache:
                cache_time = self._cache_ttl.get(match_uri, 0)
                if time.time() - cache_time < self._cache_max_age:
                    return self._cache[match_uri]
                else:
                    # Cache expired, remove it
                    del self._cache[match_uri]
                    del self._cache_ttl[match_uri]
        
        url = f"{self.base_url}/api/markets?subevent_uri={match_uri}"
        markets_data = self._make_request(url)
        
        if markets_data and isinstance(markets_data, dict):
            # Cache result with timestamp
            with self._cache_lock:
                self._cache[match_uri] = markets_data
                self._cache_ttl[match_uri] = time.time()
            return markets_data
        
        return {}
    
    def get_odds_for_market(self, market_uri: str, market_name: str) -> Optional[Dict]:
        """Get odds for a specific market with bookmaker names and comparison indicators"""
        url = f"{self.base_url}/api/odds?market_uri={market_uri}"
        odds_data = self._make_request(url)
        
        if not odds_data or not isinstance(odds_data, dict):
            return None
        
        # Process new API format
        if 'data' in odds_data:
            odds_rows = odds_data['data']
            
            if not odds_rows:
                return None
            
            # Extract bookmaker codes from schema
            schema = odds_data.get('schema', {})
            fields = schema.get('fields', [])
            bookie_codes = [f['name'] for f in fields 
                           if f['name'] not in ['bet_name', 'mode_date', 'best_back_decimal']]
            
            # Process odds with comparison
            processed_odds = []
            
            for row in odds_rows:
                bet_name = row.get('bet_name', '')
                best_odds_value = row.get('best_back_decimal')
                
                # Collect all odds for this selection
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
                            
                            odds_entry = {
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
                            }
                            
                            processed_odds.append(odds_entry)
            
            # Count unique bookmakers
            unique_bookmakers = list(set(o['bookmaker_code'] for o in processed_odds))
            
            # Get bookmaker summary
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
        
        return None
    
    def scrape_markets_concurrent(self, markets_list: List[tuple], 
                                  match_name: str) -> List[Dict]:
        """
        Scrape multiple markets concurrently
        
        Args:
            markets_list: List of (market_name, market_uri, market_slug) tuples
            match_name: Name of the match for logging
        
        Returns:
            List of market odds data
        """
        results = []
        
        def fetch_market(market_info):
            market_name, market_uri, market_slug = market_info
            return self.get_odds_for_market(market_uri, market_name)
        
        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_market = {
                executor.submit(fetch_market, market): market 
                for market in markets_list
            }
            
            for future in as_completed(future_to_market):
                market_info = future_to_market[future]
                try:
                    odds_data = future.result()
                    if odds_data:
                        results.append(odds_data)
                except Exception as e:
                    logging.error(f"Error fetching {market_info[0]}: {e}")
        
        return results
    
    def scrape_match_all_markets(self, match_uri: str, match_name: str,
                                 league_name: str, match_date: str,
                                 market_filter: Optional[List[str]] = None,
                                 max_markets_per_category: Optional[int] = None,
                                 use_concurrent: bool = True) -> Dict:
        """
        Scrape all markets for a match with optional concurrency
        
        Args:
            match_uri: Full URI like "football/spain-laliga/real-madrid-v-seville"
            match_name: Display name of match
            league_name: League name
            match_date: Match date/time
            market_filter: Optional list of market categories to include
            max_markets_per_category: Optional limit on markets per category
            use_concurrent: Use concurrent requests (default: True)
        """
        # Get all markets
        markets_data = self.get_all_markets_for_match(match_uri)
        
        if not markets_data:
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
            
            # Limit markets per category if specified
            markets_to_process = markets_list[:max_markets_per_category] if max_markets_per_category else markets_list
            
            if use_concurrent:
                # Concurrent processing
                category_results = self.scrape_markets_concurrent(markets_to_process, match_name)
                result['markets'][category] = category_results
                total_odds_collected += sum(len(m.get('odds', [])) for m in category_results)
            else:
                # Sequential processing (fallback)
                result['markets'][category] = []
                for market_info in markets_to_process:
                    market_name = market_info[0]
                    market_uri = market_info[1]
                    
                    odds_data = self.get_odds_for_market(market_uri, market_name)
                    
                    if odds_data:
                        result['markets'][category].append(odds_data)
                        total_odds_collected += len(odds_data.get('odds', []))
        
        result['total_odds_collected'] = total_odds_collected
        
        return result
    
    def scrape_league(self, league_slug: str, league_name: str,
                     max_matches: Optional[int] = None,
                     market_filter: Optional[List[str]] = None,
                     max_markets_per_category: Optional[int] = None,
                     use_concurrent: bool = True) -> Dict:
        """
        Scrape all matches from a league
        
        Args:
            league_slug: League slug like "spain-laliga"
            league_name: Display name of league
            max_matches: Optional limit on number of matches to process
            market_filter: Optional list of market categories to include
            max_markets_per_category: Optional limit on markets per category
            use_concurrent: Use concurrent requests (default: True)
        """
        # Get matches
        url = f"{self.base_url}/api/subevents?event_uri=football/{league_slug}"
        matches_data = self._make_request(url)
        
        if not matches_data or not isinstance(matches_data, dict):
            return None
        
        league_key = list(matches_data.keys())[0]
        matches = matches_data[league_key]
        
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
            match_name = match[0] if len(match) > 0 else ''
            match_uri = match[2] if len(match) > 2 else ''
            match_date = match[4] if len(match) > 4 else ''
            
            if not match_uri:
                continue
            
            match_data = self.scrape_match_all_markets(
                match_uri,
                match_name,
                league_name,
                match_date,
                market_filter=market_filter,
                max_markets_per_category=max_markets_per_category,
                use_concurrent=use_concurrent
            )
            
            if match_data:
                results['matches'].append(match_data)
        
        return results
    
    def clear_cache(self):
        """Clear the markets cache"""
        with self._cache_lock:
            self._cache.clear()
    
    def get_cache_stats(self):
        """Get cache statistics"""
        with self._cache_lock:
            return {
                'cached_items': len(self._cache),
                'cache_keys': list(self._cache.keys())
            }


def benchmark_comparison():
    """Compare optimized vs original scraper performance"""
    import sys
    sys.path.append('.')
    from oddsmagnet_multi_market_scraper import OddsMagnetMultiMarketScraper
    
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON: Optimized vs Original")
    print("="*80)
    
    # Test match
    test_match_uri = "football/spain-laliga/barcelona-v-atletico-madrid"
    test_match_name = "Barcelona v Atletico Madrid"
    test_league = "Spain La Liga"
    test_date = "2025-12-21"
    
    # Test with filtered markets to keep it reasonable
    market_filter = ['popular markets', 'over under betting']
    max_per_category = 3
    
    # Original scraper
    print("\n[1] Testing ORIGINAL scraper...")
    original = OddsMagnetMultiMarketScraper()
    
    start_time = time.time()
    try:
        original_result = original.scrape_match_all_markets(
            test_match_uri,
            test_match_name,
            test_league,
            test_date,
            market_filter=market_filter,
            max_markets_per_category=max_per_category
        )
        original_time = time.time() - start_time
        original_odds = original_result['total_odds_collected'] if original_result else 0
    except Exception as e:
        print(f"Original scraper error: {e}")
        original_time = 0
        original_odds = 0
    
    print(f"  Time: {original_time:.2f} seconds")
    print(f"  Odds collected: {original_odds}")
    
    # Optimized scraper
    print("\n[2] Testing OPTIMIZED scraper...")
    optimized = OddsMagnetOptimizedScraper(max_workers=5, requests_per_second=3.0)
    
    start_time = time.time()
    try:
        optimized_result = optimized.scrape_match_all_markets(
            test_match_uri,
            test_match_name,
            test_league,
            test_date,
            market_filter=market_filter,
            max_markets_per_category=max_per_category,
            use_concurrent=True
        )
        optimized_time = time.time() - start_time
        optimized_odds = optimized_result['total_odds_collected'] if optimized_result else 0
    except Exception as e:
        print(f"Optimized scraper error: {e}")
        optimized_time = 0
        optimized_odds = 0
    
    print(f"  Time: {optimized_time:.2f} seconds")
    print(f"  Odds collected: {optimized_odds}")
    
    # Comparison
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    if original_time > 0 and optimized_time > 0:
        speedup = original_time / optimized_time
        time_saved = original_time - optimized_time
        
        print(f"\nOriginal time:   {original_time:.2f}s")
        print(f"Optimized time:  {optimized_time:.2f}s")
        print(f"Time saved:      {time_saved:.2f}s ({time_saved/original_time*100:.1f}%)")
        print(f"Speed increase:  {speedup:.2f}x faster")
        print(f"\nOdds collected:  {original_odds} vs {optimized_odds}")
    else:
        print("\nComparison failed - one or both scrapers encountered errors")
    
    # Cache stats
    print(f"\nCache stats: {optimized.get_cache_stats()}")


if __name__ == "__main__":
    # Run benchmark
    benchmark_comparison()
