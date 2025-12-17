#!/usr/bin/env python3
"""
OddsMagnet Optimized Complete Collector
High-performance bulk collection with concurrent processing
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.helpers.match_name_cleaner import clean_match_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class OddsMagnetOptimizedCollector:
    """Optimized collector for bulk data collection"""
    
    def __init__(self, max_workers: int = 5, requests_per_second: float = 3.0):
        """
        Initialize optimized collector
        
        Args:
            max_workers: Number of concurrent threads
            requests_per_second: Rate limit (3.0 = 3 requests/second)
        """
        self.scraper = OddsMagnetOptimizedScraper(max_workers, requests_per_second)
        self.max_workers = max_workers
        self.cache = {}
    
    def get_all_matches_summary(self, sport: str = 'football',
                               use_cache: bool = True) -> List[Dict]:
        """
        Get summary of all available matches (optimized with caching)
        
        Args:
            sport: Sport type (default: football)
            use_cache: Load from cache file if available (default: True)
        """
        cache_file = f"{sport}_matches_cache.json"
        
        # Try to load from cache
        if use_cache:
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Check if cache is recent (less than 1 hour old)
                cache_time = datetime.fromisoformat(cache_data['timestamp'])
                age_minutes = (datetime.now() - cache_time).total_seconds() / 60
                
                if age_minutes < 60:
                    logging.info(f"Using cached data ({age_minutes:.1f} min old)")
                    return cache_data['matches']
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass
        
        # Fetch fresh data
        logging.info("Fetching fresh match data...")
        
        # Get all leagues
        url = f"https://oddsmagnet.com/api/events?sport_uri={sport}"
        leagues = self.scraper._make_request(url, timeout=15)
        
        if not leagues or not isinstance(leagues, list):
            return []
        
        all_matches = []
        
        def fetch_league_matches(league):
            """Fetch matches for a single league"""
            league_slug = league.get('event_slug', '')
            league_name = league.get('event_name', '')
            
            if not league_slug:
                return []
            
            url = f"https://oddsmagnet.com/api/subevents?event_uri={sport}/{league_slug}"
            matches_data = self.scraper._make_request(url)
            
            if not matches_data or not isinstance(matches_data, dict):
                return []
            
            league_key = list(matches_data.keys())[0]
            matches = matches_data[league_key]
            
            # Process matches
            processed = []
            for match in matches:
                match_info = {
                    'league': league_name,
                    'league_slug': league_slug,
                    'match_name': match[0] if len(match) > 0 else '',
                    'match_uri': match[2] if len(match) > 2 else '',
                    'match_slug': match[3] if len(match) > 3 else '',
                    'match_date': match[4] if len(match) > 4 else '',
                    'home_team': match[5] if len(match) > 5 else '',
                    'away_team': match[6] if len(match) > 6 else '',
                    'sport': match[7] if len(match) > 7 else sport,
                }
                # Clean match names to remove unnecessary suffixes like "Women"
                match_info = clean_match_data(match_info)
                processed.append(match_info)
            
            return processed
        
        # Fetch leagues concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers * 2) as executor:
            future_to_league = {
                executor.submit(fetch_league_matches, league): league
                for league in leagues
            }
            
            for i, future in enumerate(as_completed(future_to_league), 1):
                league = future_to_league[future]
                try:
                    matches = future.result()
                    all_matches.extend(matches)
                    logging.info(f"[{i}/{len(leagues)}] {league.get('event_name', 'Unknown')}: {len(matches)} matches")
                except Exception as e:
                    logging.error(f"Error fetching {league.get('event_name', 'Unknown')}: {e}")
        
        # Save to cache
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'sport': sport,
            'total_matches': len(all_matches),
            'total_leagues': len(leagues),
            'matches': all_matches
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Cached {len(all_matches)} matches to {cache_file}")
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")
        
        return all_matches
    
    def _process_single_match(self, match_info: tuple) -> Optional[Dict]:
        """Process a single match - designed for parallel execution"""
        i, total, match, market_filter, max_markets = match_info
        
        logging.info(f"\n[{i}/{total}] Processing: {match['match_name']}")
        
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match['match_date'],
                market_filter=market_filter,
                max_markets_per_category=max_markets,
                use_concurrent=True
            )
            
            if match_data:
                # Add extra info
                match_data['home_team'] = match.get('home_team', '')
                match_data['away_team'] = match.get('away_team', '')
                match_data['league_slug'] = match.get('league_slug', '')
                
                odds_count = match_data.get('total_odds_collected', 0)
                logging.info(f"  ✓ [{i}/{total}] Collected {odds_count} odds")
                return match_data
            else:
                logging.warning(f"  ✗ [{i}/{total}] No data collected")
                return None
                
        except Exception as e:
            logging.error(f"  Error processing match [{i}/{total}]: {e}")
            return None
    
    def collect_matches_with_odds(self,
                                  matches: List[Dict],
                                  market_filter: Optional[List[str]] = None,
                                  max_markets_per_category: Optional[int] = None,
                                  save_interval: int = 10,
                                  output_file: str = 'oddsmagnet_collection.json') -> Dict:
        """
        Collect odds for a list of matches with parallel processing and progress tracking
        
        Args:
            matches: List of match dictionaries
            market_filter: Which market categories to collect
            max_markets_per_category: Limit markets per category
            save_interval: Save progress every N matches
            output_file: Output filename
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'source': 'oddsmagnet',
            'total_matches_to_process': len(matches),
            'matches_processed': 0,
            'matches': []
        }
        
        start_time = time.time()
        total_matches = len(matches)
        
        # Parallel batch processing with ThreadPoolExecutor
        batch_size = self.scraper.max_workers * 3  # Process 3 batches per worker
        processed_count = 0
        
        logging.info(f"\n{'='*80}")
        logging.info(f"Starting parallel collection with batch size: {batch_size}")
        logging.info(f"Total matches: {total_matches}")
        logging.info(f"{'='*80}\n")
        
        # Process in batches
        for batch_start in range(0, total_matches, batch_size):
            batch_end = min(batch_start + batch_size, total_matches)
            batch_matches = matches[batch_start:batch_end]
            
            logging.info(f"\nProcessing batch {batch_start+1}-{batch_end} of {total_matches}")
            
            # Prepare match info tuples for parallel processing
            match_infos = [
                (batch_start + i + 1, total_matches, match, market_filter, max_markets_per_category)
                for i, match in enumerate(batch_matches)
            ]
            
            # Execute batch in parallel
            with ThreadPoolExecutor(max_workers=self.scraper.max_workers) as executor:
                future_to_match = {
                    executor.submit(self._process_single_match, match_info): match_info
                    for match_info in match_infos
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_match):
                    match_data = future.result()
                    if match_data:
                        results['matches'].append(match_data)
                        results['matches_processed'] += 1
                        processed_count += 1
                        
                        # Save progress at intervals
                        if processed_count % save_interval == 0:
                            self._save_progress(results, f"progress_{processed_count}_matches.json")
            
            # Save progress after each batch
            self._save_progress(results, f"progress_batch_{batch_end}.json")
        
        # Final stats
        elapsed = time.time() - start_time
        total_odds = sum(m.get('total_odds_collected', 0) for m in results['matches'])
        
        results['total_odds_collected'] = total_odds
        results['processing_time_seconds'] = elapsed
        results['matches_per_minute'] = (len(matches) / elapsed) * 60 if elapsed > 0 else 0
        
        # Save final results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logging.info(f"\n{'='*80}")
        logging.info(f"COLLECTION COMPLETE")
        logging.info(f"{'='*80}")
        logging.info(f"Matches processed: {results['matches_processed']}/{len(matches)}")
        logging.info(f"Total odds: {total_odds:,}")
        logging.info(f"Time: {elapsed:.1f}s ({results['matches_per_minute']:.1f} matches/min)")
        logging.info(f"Saved to: {output_file}")
        
        return results
    
    def _save_progress(self, data: Dict, filename: str):
        """Save intermediate results"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.info(f"  💾 Progress saved to: {filename}")
        except Exception as e:
            logging.error(f"  ✗ Error saving progress: {e}")
    
    def collect_by_leagues(self,
                          league_slugs: List[str],
                          max_matches_per_league: Optional[int] = None,
                          market_filter: Optional[List[str]] = None,
                          max_markets_per_category: Optional[int] = None,
                          output_file: str = 'leagues_collection.json') -> Dict:
        """
        Collect odds for specific leagues
        
        Args:
            league_slugs: List of league slugs to process
            max_matches_per_league: Limit matches per league
            market_filter: Which market categories to collect
            max_markets_per_category: Limit markets per category
            output_file: Output filename
        """
        # Get all matches
        all_matches = self.get_all_matches_summary()
        
        # Filter by league
        filtered_matches = [
            m for m in all_matches 
            if m['league_slug'] in league_slugs
        ]
        
        # Apply per-league limit
        if max_matches_per_league:
            limited_matches = []
            league_counts = {}
            
            for match in filtered_matches:
                league = match['league_slug']
                count = league_counts.get(league, 0)
                
                if count < max_matches_per_league:
                    limited_matches.append(match)
                    league_counts[league] = count + 1
            
            filtered_matches = limited_matches
        
        logging.info(f"\nCollecting {len(filtered_matches)} matches from {len(league_slugs)} leagues")
        
        # Collect odds
        return self.collect_matches_with_odds(
            filtered_matches,
            market_filter=market_filter,
            max_markets_per_category=max_markets_per_category,
            output_file=output_file
        )


def example_usage():
    """Example usage of optimized collector"""
    
    # Initialize with custom settings
    collector = OddsMagnetOptimizedCollector(
        max_workers=5,  # 5 concurrent threads
        requests_per_second=3.0  # 3 requests/second max
    )
    
    print("\n" + "="*80)
    print("EXAMPLE 1: Get all available matches (with caching)")
    print("="*80)
    
    # Get matches (uses cache if available)
    matches = collector.get_all_matches_summary(use_cache=True)
    print(f"\nFound {len(matches)} total matches")
    
    print("\n" + "="*80)
    print("EXAMPLE 2: Collect odds from major leagues")
    print("="*80)
    
    # Collect from specific leagues
    results = collector.collect_by_leagues(
        league_slugs=[
            'spain-laliga',
            'england-premier-league',
            'germany-bundesliga'
        ],
        max_matches_per_league=2,  # Only 2 matches per league for demo
        market_filter=['popular markets', 'over under betting'],
        max_markets_per_category=3,
        output_file='optimized_collection_example.json'
    )
    
    print(f"\nCollected {results['total_odds_collected']:,} odds")
    print(f"Processing speed: {results['matches_per_minute']:.1f} matches/min")


if __name__ == "__main__":
    example_usage()
