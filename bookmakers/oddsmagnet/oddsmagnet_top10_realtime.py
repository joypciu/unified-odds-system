#!/usr/bin/env python3
"""
OddsMagnet TOP 10 Leagues Real-Time Collector
Dedicated script for continuously collecting odds from top 10 leagues
Updates oddsmagnet_top10.json every 30 seconds with ALL markets
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

class Top10RealtimeCollector:
    """Real-time collector dedicated to TOP 10 leagues"""
    
    # Top 10 leagues with correct slugs from OddsMagnet
    TOP_10_LEAGUES = [
        'england-premier-league',
        'spain-laliga',
        'italy-serie-a', 
        'germany-bundesliga',
        'france-ligue-1',
        'champions-league',
        'europe-uefa-europa-league',
        'england-championship',
        'netherlands-eredivisie',
        'portugal-primeira-liga'
    ]
    
    # Important market categories for fast fetching
    IMPORTANT_MARKETS = [
        'popular markets',           # Match Winner, 1X2, BTTS
        'over under betting',        # Over/Under goals
        'alternative match goals',   # Alternative goal lines
        'asian handicap',            # Asian handicap betting
        'double chance',             # Double chance markets
        'corners',                   # Corner markets
        'cards',                     # Yellow/Red cards
        'both teams to score',       # BTTS
        'half time full time',       # HT/FT
        'correct score',             # Correct score markets
        'goalscorer'                 # First/Anytime goalscorer
    ]
    
    def __init__(self, max_workers: int = 30, requests_per_second: float = 20.0):
        """Initialize the collector with faster parallel fetching"""
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.output_file = Path(__file__).parent / 'oddsmagnet_top10.json'
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
        """Get all available matches from OddsMagnet"""
        from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
        temp_collector = OddsMagnetOptimizedCollector(
            max_workers=self.max_workers,
            requests_per_second=self.requests_per_second
        )
        return temp_collector.get_all_matches_summary(use_cache=True)
    
    def filter_top10_matches(self, all_matches: List[Dict]) -> List[Dict]:
        """Filter matches to only top 10 leagues"""
        top10_matches = [
            m for m in all_matches 
            if m.get('league_slug', '') in self.TOP_10_LEAGUES
        ]
        
        # Count by league
        league_counts = {}
        for match in top10_matches:
            league = match.get('league', 'unknown')
            league_counts[league] = league_counts.get(league, 0) + 1
        
        print(f"\n📊 Filtered to {len(top10_matches)} matches in top 10 leagues\n")
        print("🏆 Matches by league:")
        for league in self.TOP_10_LEAGUES:
            # Find the display name from matches
            display_name = next(
                (m['league'] for m in top10_matches if m.get('league_slug') == league),
                league
            )
            count = league_counts.get(display_name, 0)
            if count > 0:
                print(f"  • {display_name}: {count}")
        
        return top10_matches
    
    def fetch_match_odds(self, match: Dict) -> Optional[Dict]:
        """Fetch odds for a single match (important markets only for speed)"""
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match.get('match_date'),
                market_filter=self.IMPORTANT_MARKETS,  # Filter to important markets only
                max_markets_per_category=5,  # Limit to 5 markets per category for speed
                use_concurrent=True  # Parallel fetching enabled
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
        """Save current snapshot to JSON file"""
        try:
            # Atomic write: write to temp file then rename
            temp_file = str(self.output_file) + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
                f.flush()
                import os
                os.fsync(f.fileno())
            
            # Atomic rename
            import os
            os.replace(temp_file, self.output_file)
            
            return True
        except Exception as e:
            print(f"⚠️ Error saving snapshot: {e}")
            return False
    
    def run_realtime_loop(self, update_interval: float = 30.0):
        """Main real-time collection loop"""
        print("\n" + "="*80)
        print("REAL-TIME COLLECTION STARTED - TOP 10 LEAGUES (FAST MODE)")
        print("="*80)
        print(f"Update interval: {update_interval}s")
        print(f"Output file: {self.output_file}")
        print(f"Markets: {len(self.IMPORTANT_MARKETS)} important categories (optimized)")
        print(f"  • " + ", ".join(self.IMPORTANT_MARKETS[:4]) + "...")
        print(f"Workers: {self.max_workers} concurrent (HIGH SPEED)")
        print(f"Rate limit: {self.requests_per_second} req/s")
        print("Press Ctrl+C to stop gracefully")
        print("="*80)
        
        while self.running:
            self.iteration += 1
            cycle_start = time.time()
            
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'─'*80}")
            
            # Step 1: Get all matches and filter to top 10
            print("\n📡 Fetching match list...")
            all_matches = self.get_all_matches()
            top10_matches = self.filter_top10_matches(all_matches)
            
            if not top10_matches:
                print("⚠️ No matches found in top 10 leagues")
                time.sleep(update_interval)
                continue
            
            # Step 2: Fetch odds for all matches in parallel (HIGH SPEED)
            print(f"\n🚀 Processing {len(top10_matches)} matches with {self.max_workers} workers...")
            print(f"   Markets: {len(self.IMPORTANT_MARKETS)} important categories only")
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'source': 'oddsmagnet',
                'leagues': self.TOP_10_LEAGUES,
                'market_categories': self.IMPORTANT_MARKETS,
                'total_matches': len(top10_matches),
                'matches': []
            }
            
            completed = 0
            total_odds = 0
            
            # Use higher worker count for maximum parallelism
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_match = {
                    executor.submit(self.fetch_match_odds, match): (i, match)
                    for i, match in enumerate(top10_matches, 1)
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
                            if completed % 20 == 0 or completed == len(top10_matches):
                                percent = (completed / len(top10_matches)) * 100
                                print(f"  [{completed}/{len(top10_matches)}] {percent:.1f}% - {match['match_name'][:50]}")
                    
                    except Exception as e:
                        print(f"  ✗ [{i}/{len(top10_matches)}] Error: {e}")
            
            # Step 3: Save snapshot
            snapshot['matches_processed'] = completed
            snapshot['total_odds_collected'] = total_odds
            
            saved = self.save_snapshot(snapshot)
            
            cycle_duration = time.time() - cycle_start
            
            # Step 4: Print summary
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} COMPLETE")
            print(f"{'─'*80}")
            print(f"  ✅ Matches processed: {completed}/{len(top10_matches)}")
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
    print("ODDSMAGNET TOP 10 LEAGUES REAL-TIME COLLECTOR - FAST MODE")
    print("#"*80)
    print("\nTop 10 Leagues:")
    for i, league in enumerate(Top10RealtimeCollector.TOP_10_LEAGUES, 1):
        print(f"  {i:2}. {league}")
    
    print(f"\nImportant Markets ({len(Top10RealtimeCollector.IMPORTANT_MARKETS)}):")
    for i, market in enumerate(Top10RealtimeCollector.IMPORTANT_MARKETS, 1):
        print(f"  {i}. {market}")
    print()
    
    # Create collector with optimized settings for speed
    collector = Top10RealtimeCollector(
        max_workers=30,          # 30 concurrent workers (increased from 20)
        requests_per_second=20.0 # 20 req/s (increased from 15)
    )
    
    # Start real-time loop (30s matches UI refresh)
    
    # Start real-time loop
    collector.run_realtime_loop(update_interval=30.0)


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
