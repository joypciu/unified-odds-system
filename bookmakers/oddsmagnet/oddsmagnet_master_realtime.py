#!/usr/bin/env python3
"""
OddsMagnet MASTER Real-Time Collector
Dedicated script for continuously collecting odds from ALL leagues
Updates oddsmagnet_realtime.json every 60 seconds with ALL markets
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

class MasterRealtimeCollector:
    """Real-time collector for ALL leagues"""
    
    def __init__(self, max_workers: int = 20, requests_per_second: float = 15.0):
        """Initialize the collector"""
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.output_file = Path(__file__).parent / 'oddsmagnet_realtime.json'
        self.running = True
        self.iteration = 0
        
        # Import scraper
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
        """Get all available matches from OddsMagnet"""
        from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
        temp_collector = OddsMagnetOptimizedCollector(
            max_workers=self.max_workers,
            requests_per_second=self.requests_per_second
        )
        return temp_collector.get_all_matches_summary(use_cache=True)
    
    def fetch_match_odds(self, match: Dict) -> Optional[Dict]:
        """Fetch odds for a single match (ALL markets)"""
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match.get('match_date'),
                market_filter=None,  # None = ALL markets
                max_markets_per_category=None,  # None = all markets per category
                use_concurrent=True
            )
            
            if match_data:
                match_data['home_team'] = match.get('home_team', '')
                match_data['away_team'] = match.get('away_team', '')
                match_data['league_slug'] = match.get('league_slug', '')
                match_data['fetch_timestamp'] = datetime.now().isoformat()
                
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
            from pathlib import Path
            
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
    
    def run_realtime_loop(self, update_interval: float = 30.0, max_matches: int = 500):
        """Main real-time collection loop"""
        print("\n" + "="*80)
        print("REAL-TIME COLLECTION STARTED - ALL LEAGUES (MASTER)")
        print("="*80)
        print(f"Update interval: {update_interval}s")
        print(f"Max matches per update: {max_matches}")
        print(f"Output file: {self.output_file}")
        print(f"Markets: ALL (no filtering)")
        print(f"Workers: {self.max_workers} concurrent")
        print("Press Ctrl+C to stop gracefully")
        print("="*80)
        
        while self.running:
            self.iteration += 1
            cycle_start = time.time()
            
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'─'*80}")
            
            # Step 1: Get all matches
            print("\n📡 Fetching match list from ALL leagues...")
            all_matches = self.get_all_matches()
            
            # Limit to max_matches for performance
            matches_to_process = all_matches[:max_matches] if max_matches else all_matches
            
            print(f"   Total available: {len(all_matches)} matches")
            print(f"   Processing: {len(matches_to_process)} matches")
            
            if not matches_to_process:
                print("⚠️ No matches found")
                time.sleep(update_interval)
                continue
            
            # Step 2: Fetch odds for all matches in parallel
            print(f"\n🚀 Processing {len(matches_to_process)} matches in parallel...")
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'source': 'oddsmagnet',
                'scope': 'all_leagues',
                'total_available': len(all_matches),
                'total_matches': len(matches_to_process),
                'matches': []
            }
            
            completed = 0
            total_odds = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_match = {
                    executor.submit(self.fetch_match_odds, match): (i, match)
                    for i, match in enumerate(matches_to_process, 1)
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
                            
                            # Show progress every 50 matches
                            if completed % 50 == 0 or completed == len(matches_to_process):
                                percent = (completed / len(matches_to_process)) * 100
                                print(f"  [{completed}/{len(matches_to_process)}] {percent:.1f}% - {match['match_name'][:50]}")
                    
                    except Exception as e:
                        print(f"  ✗ [{i}/{len(matches_to_process)}] Error: {e}")
            
            # Step 3: Save snapshot
            snapshot['matches_processed'] = completed
            snapshot['total_odds_collected'] = total_odds
            
            saved = self.save_snapshot(snapshot)
            
            cycle_duration = time.time() - cycle_start
            
            # Step 4: Print summary
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} COMPLETE")
            print(f"{'─'*80}")
            print(f"  ✅ Matches processed: {completed}/{len(matches_to_process)}")
            print(f"  🎯 Total odds collected: {total_odds:,}")
            print(f"  ⏱️  Cycle duration: {cycle_duration:.1f}s")
            if saved:
                print(f"  💾 Saved to: {self.output_file.name}")
            print(f"{'─'*80}")
            
            # Sleep until next update
            if self.running:
                sleep_time = max(0, update_interval - cycle_duration)
                if sleep_time > 0:
                    print(f"\n😴 Sleeping {sleep_time:.1f}s until next update...")
                    time.sleep(sleep_time)
                else:
                    print(f"\n⚠️ Cycle took {cycle_duration:.1f}s (longer than {update_interval}s interval)")
        
        print("\n✅ Collector stopped gracefully")


def main():
    """Main entry point"""
    print("\n" + "#"*80)
    print("ODDSMAGNET MASTER REAL-TIME COLLECTOR - ALL LEAGUES")
    print("#"*80)
    print("\nCollecting odds from ALL available leagues")
    print()
    
    # Create collector
    collector = MasterRealtimeCollector(
        max_workers=20,
        requests_per_second=15.0
    )
    
    # Start real-time loop (30 second updates, max 500 matches)
    collector.run_realtime_loop(
        update_interval=30.0,
        max_matches=500  # Limit for performance
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
