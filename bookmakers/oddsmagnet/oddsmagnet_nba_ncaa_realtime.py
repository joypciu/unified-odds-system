#!/usr/bin/env python3
"""
OddsMagnet NBA & NCAA Real-Time Collector
Dedicated script for continuously collecting basketball odds from NBA and NCAA only
Updates oddsmagnet_nba_ncaa.json every 60 seconds
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

class NBANCAARealtimeCollector:
    """Real-time collector dedicated to NBA and NCAA basketball"""
    
    # Target leagues
    TARGET_LEAGUES = [
        'usa-nba',
        'usa-ncaa'
    ]
    
    # Important market categories for basketball
    IMPORTANT_MARKETS = [
        'popular markets',           # Contains: win market, handicaps, totals
        'over under betting',        # Total over/under markets
        'handicap betting',          # Point spread markets  
        '1st half markets',          # First half betting markets
        'total markets'              # Total points markets
    ]
    
    def __init__(self, max_workers: int = 20, requests_per_second: float = 15.0):
        """Initialize the collector with optimized settings for basketball"""
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.output_file = Path(__file__).parent / 'oddsmagnet_nba_ncaa.json'
        self.running = True
        self.iteration = 0
        
        # Import scraper with performance settings
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
    
    def get_all_basketball_matches(self) -> List[Dict]:
        """Get all basketball matches from OddsMagnet"""
        from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
        temp_collector = OddsMagnetOptimizedCollector(
            max_workers=self.max_workers,
            requests_per_second=self.requests_per_second
        )
        return temp_collector.get_all_matches_summary(sport='basketball', use_cache=True)
    
    def filter_nba_ncaa_matches(self, all_matches: List[Dict]) -> List[Dict]:
        """Filter matches to only NBA and NCAA"""
        filtered_matches = [
            m for m in all_matches 
            if m.get('league_slug', '') in self.TARGET_LEAGUES
        ]
        
        # Count by league
        league_counts = {}
        for match in filtered_matches:
            league = match.get('league', 'unknown')
            league_counts[league] = league_counts.get(league, 0) + 1
        
        print(f"\n🏀 Filtered to {len(filtered_matches)} matches in NBA & NCAA\n")
        print("🏆 Matches by league:")
        for league_slug in self.TARGET_LEAGUES:
            # Find the display name from matches
            display_name = next(
                (m['league'] for m in filtered_matches if m.get('league_slug') == league_slug),
                league_slug
            )
            count = league_counts.get(display_name, 0)
            if count > 0:
                print(f"  • {display_name}: {count}")
        
        return filtered_matches
    
    def fetch_match_odds(self, match: Dict) -> Optional[Dict]:
        """Fetch odds for a single basketball match"""
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match.get('match_date', ''),
                market_filter=self.IMPORTANT_MARKETS
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
            print(f"⚠️ Error fetching {match.get('match_name', 'unknown')}: {e}")
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
            Path(self.output_file).touch(exist_ok=True)
            
            return True
        except Exception as e:
            print(f"⚠️ Error saving snapshot: {e}")
            return False
    
    def run_realtime_loop(self, update_interval: float = 30.0):
        """Main real-time collection loop"""
        print("\n" + "="*80)
        print("REAL-TIME COLLECTION STARTED - NBA & NCAA BASKETBALL")
        print("="*80)
        print(f"Update interval: {update_interval}s")
        print(f"Output file: {self.output_file}")
        print(f"Leagues: {', '.join([l.replace('usa-', 'USA ').upper() for l in self.TARGET_LEAGUES])}")
        print(f"Markets: {len(self.IMPORTANT_MARKETS)} important categories")
        print(f"  • " + ", ".join(self.IMPORTANT_MARKETS[:3]) + "...")
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
            
            # Step 1: Get all basketball matches and filter to NBA/NCAA
            print("\n📡 Fetching basketball match list...")
            all_matches = self.get_all_basketball_matches()
            matches_to_process = self.filter_nba_ncaa_matches(all_matches)
            
            if not matches_to_process:
                print("⚠️ No NBA/NCAA matches found")
                time.sleep(update_interval)
                continue
            
            # Step 2: Fetch odds for all NBA/NCAA matches concurrently
            print(f"\n🚀 Processing {len(matches_to_process)} matches...")
            
            matches_with_odds = []
            total_odds = 0
            processed = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_match = {
                    executor.submit(self.fetch_match_odds, match): match 
                    for match in matches_to_process
                }
                
                for future in as_completed(future_to_match):
                    if not self.running:
                        break
                    
                    processed += 1
                    match_data = future.result()
                    
                    if match_data:
                        matches_with_odds.append(match_data)
                        odds_count = match_data.get('total_odds_collected', 0)
                        total_odds += odds_count
                    
                    # Progress indicator
                    if processed % 5 == 0 or processed == len(matches_to_process):
                        progress = (processed / len(matches_to_process)) * 100
                        sample_match = future_to_match[future]
                        print(f"  [{processed}/{len(matches_to_process)}] {progress:.1f}% - {sample_match.get('match_name', '')}")
            
            if not self.running:
                break
            
            # Step 3: Build snapshot
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'source': 'oddsmagnet_nba_ncaa',
                'sport': 'basketball',
                'scope': 'nba_ncaa_only',
                'market_categories': self.IMPORTANT_MARKETS,
                'total_available': len(all_matches),
                'total_matches': len(matches_with_odds),
                'update_interval': update_interval,
                'leagues_tracked': [
                    l.replace('usa-', 'USA ').upper() for l in self.TARGET_LEAGUES
                ],
                'total_leagues': len(self.TARGET_LEAGUES),
                'matches': matches_with_odds
            }
            
            # Step 4: Save snapshot
            cycle_duration = time.time() - cycle_start
            self.save_snapshot(snapshot)
            
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} COMPLETE")
            print(f"{'─'*80}")
            print(f"  ✅ Matches processed: {len(matches_with_odds)}/{len(matches_to_process)}")
            print(f"  🎯 Total odds collected: {total_odds:,}")
            print(f"  ⏱️  Cycle duration: {cycle_duration:.1f}s")
            print(f"  💾 Saved to: {self.output_file.name}")
            print(f"{'─'*80}")
            
            # Sleep until next update
            time_to_sleep = max(0, update_interval - cycle_duration)
            if time_to_sleep > 0:
                print(f"\n😴 Sleeping {time_to_sleep:.1f}s until next update...")
                time.sleep(time_to_sleep)
            else:
                print(f"\n⚠️ Cycle took {cycle_duration:.1f}s (longer than {update_interval}s interval)")


def main():
    """Main entry point"""
    print("\n" + "#"*80)
    print("ODDSMAGNET NBA & NCAA REAL-TIME COLLECTOR")
    print("#"*80)
    
    print("\nTarget Leagues (2):")
    for i, league in enumerate(NBANCAARealtimeCollector.TARGET_LEAGUES, 1):
        display_name = league.replace('usa-', 'USA ').upper()
        print(f"  {i}. {display_name}")
    
    print(f"\nImportant Markets ({len(NBANCAARealtimeCollector.IMPORTANT_MARKETS)}):")
    for i, market in enumerate(NBANCAARealtimeCollector.IMPORTANT_MARKETS, 1):
        print(f"  {i}. {market}")
    
    # Initialize and run collector
    collector = NBANCAARealtimeCollector(
        max_workers=20,
        requests_per_second=15.0
    )
    
    collector.run_realtime_loop(update_interval=30.0)


if __name__ == '__main__':
    main()
