#!/usr/bin/env python3
"""
Truly Parallel Top10 Collector - Single JSON file with live updates
Updates ONE JSON file continuously as matches are collected
"""

import time
from datetime import datetime
from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from threading import Lock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.helpers.match_name_cleaner import clean_match_data

# Configure logging to be minimal
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)

class LiveParallelCollector:
    def __init__(self, max_workers=12, requests_per_second=20.0, output_file='oddsmagnet_top10.json'):
        # Ensure output file is in the correct directory
        if not Path(output_file).is_absolute():
            output_file = Path(__file__).parent / output_file
        self.output_file = str(output_file)
        self.scraper = OddsMagnetOptimizedScraper(
            max_workers=max_workers,
            requests_per_second=requests_per_second
        )
        self.max_workers = max_workers
        self.lock = Lock()
        
        # Initialize result structure
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'source': 'oddsmagnet',
            'status': 'in_progress',
            'total_matches_to_process': 0,
            'matches_processed': 0,
            'total_odds_collected': 0,
            'processing_start_time': time.time(),
            'processing_time_seconds': 0,
            'matches_per_minute': 0,
            'matches': []
        }
        
    def _update_json(self):
        """Update the single JSON file with current progress - atomic write for live UI updates"""
        with self.lock:
            # Update stats
            elapsed = time.time() - self.results['processing_start_time']
            self.results['processing_time_seconds'] = round(elapsed, 2)
            if elapsed > 0:
                self.results['matches_per_minute'] = round((self.results['matches_processed'] / elapsed) * 60, 2)
            
            # Atomic write: write to temp file then rename (prevents UI from reading incomplete JSON)
            try:
                temp_file = str(self.output_file) + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, indent=2, ensure_ascii=False)
                    f.flush()  # Ensure data is written to disk
                    os.fsync(f.fileno())  # Force OS to write to disk
                
                # Atomic rename - UI will always read complete valid JSON
                import os
                os.replace(temp_file, self.output_file)
            except Exception as e:
                print(f"⚠️ Error updating JSON: {e}")
    
    def _print_progress(self, completed, total, match_name, odds_count):
        """Print a live progress bar and stats"""
        with self.lock:
            percent = (completed / total) * 100
            filled = int(percent / 2)
            bar = '█' * filled + '░' * (50 - filled)
            
            # Clear line and print progress
            sys.stdout.write('\r\033[K')  # Clear line
            sys.stdout.write(f'  [{bar}] {percent:.1f}% | {completed}/{total} matches | {self.results["total_odds_collected"]:,} odds')
            sys.stdout.flush()
            
            # Print match details on new line every 10 matches or if it's special
            if completed % 10 == 0 or completed == 1 or completed == total:
                print(f'\n  ✓ [{completed}/{total}] {match_name[:50]}: {odds_count} odds')
    
    def process_match(self, match_info):
        """Process a single match and update JSON immediately"""
        i, total, match = match_info
        
        try:
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match['match_date'],
                market_filter=None,
                max_markets_per_category=None,
                use_concurrent=True
            )
            
            if match_data:
                match_data['home_team'] = match.get('home_team', '')
                match_data['away_team'] = match.get('away_team', '')
                match_data['league_slug'] = match.get('league_slug', '')
                
                # Clean match names to remove unnecessary suffixes like "Women"
                match_data = clean_match_data(match_data)
                
                odds_count = match_data.get('total_odds_collected', 0)
                
                # Update results and JSON file immediately
                with self.lock:
                    self.results['matches'].append(match_data)
                    self.results['matches_processed'] += 1
                    self.results['total_odds_collected'] += odds_count
                    completed = self.results['matches_processed']
                
                # Update JSON file
                self._update_json()
                
                # Print progress
                self._print_progress(completed, total, match['match_name'], odds_count)
                
                return match_data
            else:
                return None
                
        except Exception as e:
            return None
    
    def collect_all_parallel(self, matches):
        """Process ALL matches in true parallel fashion"""
        self.results['total_matches_to_process'] = len(matches)
        total_matches = len(matches)
        
        # Initial save
        self._update_json()
        
        print(f"\n🚀 Processing {total_matches} matches in parallel with {self.max_workers} workers...")
        print(f"📁 Live updates: {self.output_file}\n")
        
        # Prepare all match info tuples
        match_infos = [
            (i + 1, total_matches, match)
            for i, match in enumerate(matches)
        ]
        
        # Process ALL matches concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_match, match_info): match_info
                for match_info in match_infos
            }
            
            # Wait for all to complete
            for future in as_completed(futures):
                future.result()
        
        # Final update
        with self.lock:
            self.results['status'] = 'completed'
            elapsed = time.time() - self.results['processing_start_time']
            self.results['processing_time_seconds'] = round(elapsed, 2)
            self.results['matches_per_minute'] = round((self.results['matches_processed'] / elapsed) * 60, 2)
        
        self._update_json()
        print('\n')  # New line after progress bar
        
        return self.results

def main():
    print("\n" + "="*80)
    print("🔥 LIVE PARALLEL TOP 10 LEAGUES COLLECTOR 🔥")
    print("="*80)
    print("\n⚙️  Configuration:")
    print("  • Workers: 12")
    print("  • Rate: 20 req/s")
    print("  • Markets: ALL")
    print("  • Mode: TRUE PARALLEL")
    print("  • Live Updates: ONE JSON file")
    print("="*80 + "\n")
    
    # Top 10 leagues
    TOP_10_LEAGUES = [
        'england-premier-league',
        'spain-laliga',
        'italy-serie-a', 
        'germany-bundesliga',
        'france-ligue-1',
        'champions-league',  # Fixed: was 'uefa-champions-league'
        'europe-uefa-europa-league',  # Fixed: was 'uefa-europa-league'
        'england-championship',
        'netherlands-eredivisie',
        'portugal-primeira-liga'
    ]
    
    start_time = time.time()
    # Output file will be saved in bookmakers/oddsmagnet/ directory
    output_file = 'oddsmagnet_top10.json'
    
    # Create collector
    collector = LiveParallelCollector(
        max_workers=12,
        requests_per_second=20.0,
        output_file=output_file
    )
    
    print("📡 Fetching all matches...")
    from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
    temp_collector = OddsMagnetOptimizedCollector(max_workers=12, requests_per_second=20.0)
    all_matches = temp_collector.get_all_matches_summary(use_cache=False)
    print(f"  ✓ Found {len(all_matches)} total matches\n")
    
    # Filter for top 10 leagues
    top10_matches = [
        m for m in all_matches 
        if m.get('league_slug', '') in TOP_10_LEAGUES
    ]
    print(f"📊 Filtered to {len(top10_matches)} matches in top 10 leagues\n")
    
    # Count by league
    league_counts = {}
    for match in top10_matches:
        league = match.get('league', 'unknown')
        league_counts[league] = league_counts.get(league, 0) + 1
    
    print("🏆 Matches by league:")
    for league, count in sorted(league_counts.items()):
        print(f"  • {league}: {count}")
    
    print(f"\n⏱️  Started at {datetime.now().strftime('%H:%M:%S')}")
    print("="*80)
    
    # Process ALL matches in TRUE PARALLEL
    results = collector.collect_all_parallel(top10_matches)
    
    # Final stats
    elapsed = time.time() - start_time
    
    print("\n" + "="*80)
    print("✅ COLLECTION COMPLETE")
    print("="*80)
    print(f"  📊 Matches collected: {results['matches_processed']}/{len(top10_matches)}")
    print(f"  🎯 Total odds: {results['total_odds_collected']:,}")
    print(f"  📈 Avg odds/match: {int(results['total_odds_collected'] / results['matches_processed']) if results['matches_processed'] > 0 else 0}")
    print(f"  ⏱️  Time elapsed: {elapsed:.1f}s ({elapsed/60:.2f} min)")
    print(f"  🚀 Throughput: {results['matches_per_minute']:.1f} matches/min")
    print(f"  💾 Saved to: {output_file}")
    print("="*80)
    
    # Performance assessment
    target_time = 120
    if elapsed < target_time:
        print(f"\n🎉 AMAZING! Completed in {elapsed:.1f}s (target: {target_time}s)")
    else:
        over_by = elapsed - target_time
        print(f"\n📊 Completed in {elapsed:.1f}s (target: {target_time}s, +{over_by:.1f}s)")
        print(f"💡 Limited by API rate limiting - {results['matches_per_minute']:.1f} matches/min is excellent!")
    
    # Data quality check
    market_types = set()
    for match in results['matches'][:10]:  # Sample first 10
        if 'markets' in match and match['markets']:
            market_types.update(match['markets'].keys())
    
    print(f"\n✅ Data Quality:")
    print(f"  • Market types collected: {len(market_types)}")
    print(f"  • Sample types: {', '.join(list(market_types)[:5])}")
    print()

if __name__ == '__main__':
    main()
