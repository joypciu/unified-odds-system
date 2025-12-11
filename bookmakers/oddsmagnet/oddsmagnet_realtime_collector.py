#!/usr/bin/env python3
"""
OddsMagnet Real-Time Data Collector
Continuously fetches and updates odds data every 1 second
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
import signal
import sys
import argparse
from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper
from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector

class RealTimeOddsCollector:
    """Collects odds data in real-time with 1-second intervals"""
    
    def __init__(self, 
                 max_workers: int = 8,
                 requests_per_second: float = 5.0,
                 output_file: str = 'oddsmagnet_realtime.json',
                 history_file: str = 'oddsmagnet_history.json'):
        """
        Initialize real-time collector
        
        Args:
            max_workers: Number of concurrent threads
            requests_per_second: Rate limit
            output_file: Current odds output file
            history_file: Historical odds changes file
        """
        self.scraper = OddsMagnetOptimizedScraper(max_workers, requests_per_second)
        self.collector = OddsMagnetOptimizedCollector(max_workers, requests_per_second)
        
        self.output_file = output_file
        self.history_file = history_file
        
        self.running = True
        self.iteration = 0
        self.tracked_matches = []
        self.odds_history = []
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\n\n⚠ Shutdown signal received. Saving data...")
        self.running = False
    
    def select_matches_to_track(self, 
                                league_slugs: Optional[List[str]] = None,
                                matches_per_league: int = 1,
                                max_total_matches: Optional[int] = None) -> List[Dict]:
        """
        Select matches to track in real-time - one match from each league
        
        Args:
            league_slugs: Specific leagues to track (None = all available leagues)
            matches_per_league: Matches per league (default: 1)
            max_total_matches: Maximum total matches across all leagues (None = no limit)
        """
        print("\n" + "="*80)
        print("SELECTING MATCHES TO TRACK")
        print("="*80)
        
        # Get all available matches
        all_matches = self.collector.get_all_matches_summary(use_cache=True)
        
        # Filter by league if specified
        if league_slugs:
            all_matches = [m for m in all_matches if m['league_slug'] in league_slugs]
        
        # Group matches by league
        matches_by_league = {}
        for match in all_matches:
            league = match['league_slug']
            if league not in matches_by_league:
                matches_by_league[league] = []
            matches_by_league[league].append(match)
        
        # Select matches_per_league from each league
        selected_matches = []
        for league, matches in matches_by_league.items():
            selected_matches.extend(matches[:matches_per_league])
        
        # Apply total limit if specified
        if max_total_matches:
            selected_matches = selected_matches[:max_total_matches]
        
        print(f"\nSelected {len(selected_matches)} matches from {len(matches_by_league)} leagues:")
        print(f"  ({matches_per_league} match per league)")
        
        # Show sample
        for i, match in enumerate(selected_matches[:10], 1):
            print(f"  {i}. {match['match_name']} ({match['league']})")
        
        if len(selected_matches) > 10:
            print(f"  ... and {len(selected_matches) - 10} more matches")
        
        return selected_matches
    
    def fetch_current_odds(self, match: Dict, 
                          market_filter: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Fetch current odds for a match
        
        Args:
            match: Match information dictionary
            market_filter: Markets to track (None = popular markets only)
        """
        try:
            # Default to popular markets for speed
            if not market_filter:
                market_filter = ['popular markets']
            
            match_data = self.scraper.scrape_match_all_markets(
                match_uri=match['match_uri'],
                match_name=match['match_name'],
                league_name=match['league'],
                match_date=match['match_date'],
                market_filter=market_filter,
                max_markets_per_category=5,  # Limit for speed
                use_concurrent=True
            )
            
            if match_data:
                match_data['fetch_timestamp'] = datetime.now().isoformat()
                match_data['home_team'] = match.get('home_team', '')
                match_data['away_team'] = match.get('away_team', '')
                
            return match_data
            
        except Exception as e:
            print(f"  ✗ Error fetching {match['match_name']}: {e}")
            return None
    
    def detect_odds_changes(self, current_data: Dict, previous_data: Optional[Dict]) -> List[Dict]:
        """
        Detect significant odds changes between updates
        
        Returns list of changes with details
        """
        if not previous_data:
            return []
        
        changes = []
        
        # Compare odds in each market
        for category, markets in current_data.get('markets', {}).items():
            prev_markets = previous_data.get('markets', {}).get(category, [])
            
            for market in markets:
                market_name = market['market_name']
                
                # Find matching previous market
                prev_market = next(
                    (m for m in prev_markets if m['market_name'] == market_name),
                    None
                )
                
                if not prev_market:
                    continue
                
                # Compare odds
                for odd in market.get('odds', []):
                    # Find matching previous odd
                    prev_odd = next(
                        (o for o in prev_market.get('odds', [])
                         if o['selection'] == odd['selection'] 
                         and o['bookmaker_code'] == odd['bookmaker_code']),
                        None
                    )
                    
                    if prev_odd:
                        current_val = odd['decimal_odds']
                        prev_val = prev_odd['decimal_odds']
                        
                        # Detect change > 0.05
                        if abs(current_val - prev_val) > 0.05:
                            changes.append({
                                'timestamp': datetime.now().isoformat(),
                                'match': current_data['match_name'],
                                'market': market_name,
                                'selection': odd['selection'],
                                'bookmaker': odd['bookmaker_name'],
                                'previous_odds': prev_val,
                                'current_odds': current_val,
                                'change': round(current_val - prev_val, 3),
                                'change_percent': round(((current_val - prev_val) / prev_val) * 100, 2)
                            })
        
        return changes
    
    def start_realtime_collection(self,
                                  league_slugs: Optional[List[str]] = None,
                                  matches_per_league: int = 1,
                                  max_total_matches: Optional[int] = None,
                                  market_filter: Optional[List[str]] = None,
                                  update_interval: float = 1.0):
        """
        Start real-time odds collection with 1-second updates
        
        Args:
            league_slugs: Leagues to track (None = all leagues)
            matches_per_league: Matches per league (default: 1)
            max_total_matches: Maximum total matches (None = no limit)
            market_filter: Markets to track
            update_interval: Seconds between updates (default: 1.0)
        """
        print("\n" + "="*80)
        print("REAL-TIME ODDS COLLECTION STARTED")
        print("="*80)
        print(f"Update interval: {update_interval}s")
        print(f"Matches per league: {matches_per_league}")
        print(f"Press Ctrl+C to stop gracefully")
        print("="*80)
        
        # Select matches to track
        self.tracked_matches = self.select_matches_to_track(
            league_slugs, 
            matches_per_league,
            max_total_matches
        )
        
        if not self.tracked_matches:
            print("\n✗ No matches found to track")
            return
        
        # Store previous data for comparison
        previous_data = {}
        
        # Main collection loop
        while self.running:
            self.iteration += 1
            cycle_start = time.time()
            
            print(f"\n{'─'*80}")
            print(f"UPDATE #{self.iteration} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'─'*80}")
            
            current_snapshot = {
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'matches': []
            }
            
            all_changes = []
            
            # Fetch odds for each tracked match
            for i, match in enumerate(self.tracked_matches, 1):
                print(f"\n[{i}/{len(self.tracked_matches)}] {match['match_name']}")
                
                match_data = self.fetch_current_odds(match, market_filter)
                
                if match_data:
                    current_snapshot['matches'].append(match_data)
                    
                    # Detect changes
                    match_uri = match['match_uri']
                    if match_uri in previous_data:
                        changes = self.detect_odds_changes(match_data, previous_data[match_uri])
                        if changes:
                            all_changes.extend(changes)
                            print(f"  ⚠ {len(changes)} odds changes detected")
                    
                    previous_data[match_uri] = match_data
                    
                    odds_count = match_data.get('total_odds_collected', 0)
                    print(f"  ✓ {odds_count} odds fetched")
            
            # Save current snapshot
            try:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(current_snapshot, f, indent=2, ensure_ascii=False)
                print(f"\n✓ Snapshot saved to: {self.output_file}")
            except Exception as e:
                print(f"\n✗ Error saving snapshot: {e}")
            
            # Save changes to history
            if all_changes:
                self.odds_history.extend(all_changes)
                try:
                    with open(self.history_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'total_changes': len(self.odds_history),
                            'last_update': datetime.now().isoformat(),
                            'changes': self.odds_history[-100:]  # Keep last 100 changes
                        }, f, indent=2, ensure_ascii=False)
                    
                    print(f"\n⚠ {len(all_changes)} odds changes logged")
                    
                    # Display significant changes
                    for change in all_changes[:3]:  # Show first 3
                        direction = "↑" if change['change'] > 0 else "↓"
                        print(f"  {direction} {change['bookmaker']}: {change['selection']}")
                        print(f"     {change['previous_odds']} → {change['current_odds']} ({change['change']:+.3f})")
                
                except Exception as e:
                    print(f"\n✗ Error saving history: {e}")
            
            # Calculate sleep time to maintain interval
            cycle_duration = time.time() - cycle_start
            sleep_time = max(0, update_interval - cycle_duration)
            
            if sleep_time > 0:
                print(f"\n⏱ Waiting {sleep_time:.2f}s until next update...")
                time.sleep(sleep_time)
            else:
                print(f"\n⚠ Cycle took {cycle_duration:.2f}s (slower than {update_interval}s interval)")
        
        # Graceful shutdown
        print("\n" + "="*80)
        print("REAL-TIME COLLECTION STOPPED")
        print("="*80)
        print(f"Total iterations: {self.iteration}")
        print(f"Total odds changes tracked: {len(self.odds_history)}")
        print(f"Final snapshot: {self.output_file}")
        print(f"Change history: {self.history_file}")
        print("="*80)


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='OddsMagnet Real-Time Odds Collector')
    parser.add_argument('--auto', action='store_true',
                       help='Run in automated mode (production settings)')
    parser.add_argument('--leagues', type=str, nargs='+',
                       help='Specific league slugs to track (default: all leagues)')
    parser.add_argument('--matches-per-league', type=int, default=1,
                       help='Number of matches per league (default: 1)')
    parser.add_argument('--interval', type=float, default=1.0,
                       help='Update interval in seconds (default: 1.0)')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of concurrent workers (default: 10)')
    args = parser.parse_args()
    
    print("\n" + "#"*80)
    print("ODDSMAGNET REAL-TIME ODDS COLLECTOR")
    print("#"*80)
    
    # Configuration
    config = {
        'max_workers': args.workers,
        'requests_per_second': 8.0,  # Higher rate for real-time
        'matches_per_league': args.matches_per_league,
        'max_total_matches': None,  # No limit (track all available)
        'update_interval': args.interval,
        'market_filter': ['popular markets'],  # Only popular markets for speed
        'league_slugs': args.leagues  # None = ALL leagues (117+)
    }
    
    mode = "AUTOMATED" if args.auto else "MANUAL"
    print(f"\nMode: {mode}")
    print(f"\nConfiguration:")
    print(f"  Update interval: {config['update_interval']}s")
    print(f"  Matches per league: {config['matches_per_league']}")
    print(f"  Max total matches: {config['max_total_matches'] or 'No limit'}")
    print(f"  Concurrent workers: {config['max_workers']}")
    print(f"  Rate limit: {config['requests_per_second']} req/s")
    print(f"  Leagues: {'ALL available leagues' if not config['league_slugs'] else ', '.join(config['league_slugs'])}")
    
    # Create collector
    collector = RealTimeOddsCollector(
        max_workers=config['max_workers'],
        requests_per_second=config['requests_per_second']
    )
    
    # Start real-time collection
    collector.start_realtime_collection(
        league_slugs=config['league_slugs'],
        matches_per_league=config['matches_per_league'],
        max_total_matches=config['max_total_matches'],
        market_filter=config['market_filter'],
        update_interval=config['update_interval']
    )


if __name__ == "__main__":
    main()
