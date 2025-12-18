#!/usr/bin/env python3
"""
OddsMagnet Baseball Real-Time Collector
Continuously collects baseball odds from all leagues (MLB, NPB, KBO, etc.)
Updates oddsmagnet_baseball.json every 60 seconds
"""

import requests
import json
from datetime import datetime
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import signal
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.helpers.match_name_cleaner import clean_match_data

class BaseballRealtimeCollector:
    """Real-time collector for baseball odds"""
    
    # Market discovery settings
    # NOTE: Markets are discovered dynamically from the API
    # Set market_filter=None to collect ALL available markets
    # Or provide a list to filter specific categories
    MARKET_FILTER = None  # None = Collect ALL markets from API (dynamic)
    MAX_MARKETS_PER_CATEGORY = None  # None = Collect all markets in each category
    
    # Track discovered market categories across all matches
    discovered_markets = set()
    
    def __init__(self, max_workers: int = 20, requests_per_second: float = 15.0):
        """Initialize the collector with fast parallel fetching"""
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.output_file = Path(__file__).parent / 'oddsmagnet_baseball.json'
        self.running = True
        self.iteration = 0
        
        # Import scraper with higher performance settings
        from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper
        self.scraper = OddsMagnetOptimizedScraper(
            max_workers=max_workers,
            requests_per_second=requests_per_second
        )
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        print("\n\n⚠ Shutdown signal received. Saving data...")
        self.running = False
    
    def get_all_matches(self) -> List[Dict]:
        """Get all available baseball matches from OddsMagnet"""
        from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
        temp_collector = OddsMagnetOptimizedCollector(
            max_workers=self.max_workers,
            requests_per_second=self.requests_per_second
        )
        return temp_collector.get_all_matches_summary(sport='baseball', use_cache=True)
    
    def fetch_match_odds(self, match: Dict) -> Optional[Dict]:
        """Fetch odds for a single baseball match with dynamic market discovery"""
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match.get('match_date'),
                market_filter=self.MARKET_FILTER,  # Dynamic: None = ALL markets
                max_markets_per_category=self.MAX_MARKETS_PER_CATEGORY,
                use_concurrent=True
            )
            
            if match_data:
                match_data['home_team'] = match.get('home_team', '')
                match_data['away_team'] = match.get('away_team', '')
                match_data['league_slug'] = match.get('league_slug', '')
                match_data['fetch_timestamp'] = datetime.now().isoformat()
                
                # Track discovered market categories
                if 'markets' in match_data:
                    for category in match_data['markets'].keys():
                        self.discovered_markets.add(category)
                
                # Clean match data
                match_data = clean_match_data(match_data)
                
                return match_data
            
            return None
        except Exception as e:
            return None
    
    def save_snapshot(self, snapshot: Dict):
        """Save current snapshot to JSON file with proper cache busting"""
        try:
            import os
            
            # Atomic write: write to temp file then rename
            temp_file = str(self.output_file) + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename (replaces old file)
            os.replace(temp_file, self.output_file)
            
            # CRITICAL: Touch the file to update mtime for cache busting
            # os.replace() may not update mtime on all systems
            Path(self.output_file).touch(exist_ok=True)
            
            return True
        except Exception as e:
            print(f"⚠️ Error saving snapshot: {e}")
            return False
    
    def run_realtime_loop(self, update_interval: float = 30.0):
        """Main real-time collection loop"""
        print("\n" + "="*80)
        print("REAL-TIME COLLECTION STARTED - BASEBALL (ALL LEAGUES)")
        print("="*80)
        print(f"Update interval: {update_interval}s")
        print(f"Output file: {self.output_file}")
        print(f"Market Discovery: DYNAMIC (from API)")
        if self.MARKET_FILTER:
            print(f"  • Filtered to: {', '.join(self.MARKET_FILTER[:5])}...")
        else:
            print(f"  • Collecting ALL available markets")
        print(f"Workers: {self.max_workers} concurrent")
        print(f"Rate limit: {self.requests_per_second} req/s")
        print("Press Ctrl+C to stop gracefully")
        print("="*80)
        
        while self.running:
            self.iteration += 1
            cycle_start = time.time()
            
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'─'*80}")
            
            # Step 1: Get all baseball matches
            print("\n⚾ Fetching baseball match list...")
            all_matches = self.get_all_matches()
            
            if not all_matches:
                print("⚠️ No baseball matches found")
                time.sleep(update_interval)
                continue
            
            # Count matches by league
            league_counts = {}
            for match in all_matches:
                league = match.get('league', 'Unknown')
                league_counts[league] = league_counts.get(league, 0) + 1
            
            print(f"   Total matches: {len(all_matches)}")
            print(f"\n⚾ Matches by league:")
            for league, count in sorted(league_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {league}: {count}")
            
            # Step 2: Fetch odds for all matches in parallel
            print(f"\n🚀 Processing {len(all_matches)} matches with {self.max_workers} workers...")
            print(f"   Market Discovery: Dynamic (fetching from API)")
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'source': 'oddsmagnet',
                'sport': 'baseball',
                'scope': 'all_leagues',
                'total_matches': len(all_matches),
                'league_breakdown': league_counts,
                'market_discovery': 'dynamic',  # Indicates dynamic discovery
                'market_filter': self.MARKET_FILTER or 'all',
                'discovered_market_categories': sorted(list(self.discovered_markets)),
                'matches': []
            }
            
            completed = 0
            total_odds = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_match = {
                    executor.submit(self.fetch_match_odds, match): (i, match)
                    for i, match in enumerate(all_matches, 1)
                }
                
                for future in as_completed(future_to_match):
                    i, match = future_to_match[future]
                    try:
                        match_data = future.result()
                        
                        if match_data:
                            snapshot['matches'].append(match_data)
                            odds_count = match_data.get('total_odds_collected', 0)
                            total_odds += odds_count
                            completed += 1
                            
                            # Show progress every 20 matches
                            if completed % 20 == 0 or completed == len(all_matches):
                                percent = (completed / len(all_matches)) * 100
                                print(f"  [{completed}/{len(all_matches)}] {percent:.1f}% - {match['match_name'][:60]}")
                    
                    except Exception as e:
                        pass  # Silent fail for individual matches
            
            # Step 3: Save snapshot
            snapshot['matches_processed'] = completed
            snapshot['total_odds_collected'] = total_odds
            
            saved = self.save_snapshot(snapshot)
            
            cycle_duration = time.time() - cycle_start
            
            # Step 4: Print summary
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} COMPLETE")
            print(f"{'─'*80}")
            print(f"  ✅ Matches processed: {completed}/{len(all_matches)}")
            print(f"  📊 Total odds collected: {total_odds:,}")
            print(f"  📋 Market categories discovered: {len(self.discovered_markets)}")
            if self.discovered_markets:
                print(f"     {', '.join(sorted(list(self.discovered_markets))[:8])}...")
            print(f"  ⏱️  Cycle duration: {cycle_duration:.1f}s")
            print(f"  💾 File saved: {'✅' if saved else '❌'}")
            
            # Calculate wait time
            wait_time = max(0, update_interval - cycle_duration)
            if wait_time > 0:
                print(f"  ⏳ Next update in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                print(f"  ⚠️  Cycle took longer than interval ({cycle_duration:.1f}s > {update_interval}s)")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OddsMagnet Baseball Real-Time Collector')
    parser.add_argument('--interval', type=float, default=30.0,
                       help='Update interval in seconds (default: 30)')
    parser.add_argument('--workers', type=int, default=20,
                       help='Number of concurrent workers (default: 20)')
    parser.add_argument('--rate', type=float, default=15.0,
                       help='Requests per second (default: 15)')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("ODDSMAGNET BASEBALL COLLECTOR - DYNAMIC MARKET DISCOVERY")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Update interval: {args.interval}s")
    print(f"  Workers: {args.workers}")
    print(f"  Rate limit: {args.rate} req/s")
    print(f"\nMarket Discovery Mode:")
    print(f"  ✅ DYNAMIC - Markets discovered from API in real-time")
    print(f"  ✅ Collects ALL available market categories")
    print(f"  ✅ Adapts to OddsMagnet's current offerings")
    print("\n" + "="*80)
    
    collector = BaseballRealtimeCollector(
        max_workers=args.workers,
        requests_per_second=args.rate
    )
    
    try:
        collector.run_realtime_loop(update_interval=args.interval)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    finally:
        print("\n✅ Collector stopped")


if __name__ == "__main__":
    main()
