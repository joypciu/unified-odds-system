#!/usr/bin/env python3
"""
OddPortal Collector - Wrapper for integration with unified odds system
Runs the OddPortal scraper and converts data to unified format
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add parent directory to path (bookmakers folder)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the working scraper
from bookmakers.oddportal.working_scraper import OddsPortalScraper


class OddPortalCollector:
    """Wrapper for OddPortal scraper to integrate with unified system"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.base_dir = self.script_dir.parent
        self.output_file = self.script_dir / "oddportal_unified.json"
        self.raw_data_file = self.script_dir / "matches_odds_data.json"
        self.sports_completed = set()  # Track completed sports
        
    def convert_to_unified_format(self, matches_data: List[Dict]) -> List[Dict]:
        """Convert OddPortal format to unified format compatible with oddsmagnet viewer"""
        unified_matches = []
        
        for match in matches_data:
            # Create market structure similar to oddsmagnet
            markets = {}
            
            # Group bookmakers by market type
            if match.get('bookmakers'):
                # Win market (1x2 or moneyline)
                win_market_odds = []
                for bookmaker in match['bookmakers']:
                    if bookmaker.get('available', False):
                        # Home odds
                        if bookmaker.get('home_odds'):
                            win_market_odds.append({
                                'bookmaker_code': bookmaker['name'].lower()[:2],
                                'bookmaker_name': bookmaker['name'],
                                'decimal_odds': bookmaker['home_odds'],
                                'selection': match['home'],
                                'bet_name': match['home'],
                                'fractional_odds': self._decimal_to_fractional(bookmaker['home_odds']),
                            })
                        
                        # Draw odds (if available)
                        if bookmaker.get('draw_odds'):
                            win_market_odds.append({
                                'bookmaker_code': bookmaker['name'].lower()[:2],
                                'bookmaker_name': bookmaker['name'],
                                'decimal_odds': bookmaker['draw_odds'],
                                'selection': 'Draw',
                                'bet_name': 'Draw',
                                'fractional_odds': self._decimal_to_fractional(bookmaker['draw_odds']),
                            })
                        
                        # Away odds
                        if bookmaker.get('away_odds'):
                            win_market_odds.append({
                                'bookmaker_code': bookmaker['name'].lower()[:2],
                                'bookmaker_name': bookmaker['name'],
                                'decimal_odds': bookmaker['away_odds'],
                                'selection': match['away'],
                                'bet_name': match['away'],
                                'fractional_odds': self._decimal_to_fractional(bookmaker['away_odds']),
                            })
                
                if win_market_odds:
                    markets['popular markets'] = [{
                        'name': 'win market',
                        'url': match['url'],
                        'odds': win_market_odds
                    }]
            
            # Create unified match structure
            unified_match = {
                'name': f"{match['home']} v {match['away']}".lower(),
                'league_id': f"{match['sport']}/{match['country']}-{match['league']}",
                'match_url': match['url'],
                'match_slug': f"{match['home']}-v-{match['away']}".lower().replace(' ', '-'),
                'datetime': match.get('match_time', 'Not available'),
                'home': match['home'],
                'home_team': match['home'],
                'away': match['away'],
                'away_team': match['away'],
                'sport': match['sport'],
                'league': f"{match['country']} {match['league']}",
                'country': match['country'],
                'markets': markets,
                'scraped_at': match.get('scraped_at', datetime.now().isoformat()),
                'source': 'oddportal'
            }
            
            unified_matches.append(unified_match)
        
        return unified_matches
    
    def _decimal_to_fractional(self, decimal_odds: float) -> str:
        """Convert decimal odds to fractional format"""
        try:
            decimal = float(decimal_odds)
            if decimal <= 1:
                return "0/1"
            
            # Convert to fraction
            numerator = int((decimal - 1) * 100)
            denominator = 100
            
            # Simplify fraction
            from math import gcd
            common = gcd(numerator, denominator)
            numerator //= common
            denominator //= common
            
            return f"{numerator}/{denominator}"
        except:
            return "1/1"
    
    def save_progressive_data(self, sport_name: str, matches_data: List[Dict]):
        """Save data progressively as each sport completes - for faster UI updates"""
        try:
            self.sports_completed.add(sport_name)
            
            # Convert to unified format immediately
            unified_data = {
                'sport': 'multi',
                'timestamp': datetime.now().isoformat(),
                'source': 'oddportal',
                'matches_count': len(matches_data),
                'sports_completed': list(self.sports_completed),
                'is_partial': True,  # Flag to indicate more data coming
                'matches': self.convert_to_unified_format(matches_data)
            }
            
            # Write to file immediately - UI can display partial data
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(unified_data, f, indent=2, ensure_ascii=False)
            
            print(f"  ⚡ Progressive save: {len(matches_data)} matches ({len(self.sports_completed)} sports completed)")
        except Exception as e:
            print(f"  Warning: Progressive save failed: {e}")
    
    def collect(self, continuous=False, interval=300):
        """
        Collect odds from OddPortal
        
        Args:
            continuous: If True, run continuously with interval
            interval: Seconds between collections (default 300 = 5 minutes)
        """
        while True:
            try:
                print("="*80)
                print("ODDPORTAL COLLECTOR - Starting collection")
                print("="*80)
                print()
                
                # Reset completion tracking
                self.sports_completed.clear()
                
                # Run scraper
                scraper = OddsPortalScraper()
                
                # Set up progressive save callback
                scraper.sport_complete_callback = self.save_progressive_data
                
                # Scrape all data
                print("Scraping OddPortal data...")
                print("⚡ Progressive updates enabled - data will appear on UI as each sport completes\n")
                scraper.scrape_all()
                
                # Save raw data
                scraper.save_to_json(filename=str(self.raw_data_file))
                
                # Convert to unified format (final complete version)
                print("\nConverting to unified format (final)...")
                unified_data = {
                    'sport': 'multi',
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddportal',
                    'matches_count': len(scraper.matches_data),
                    'sports_completed': list(self.sports_completed),
                    'is_partial': False,  # Final complete data
                    'matches': self.convert_to_unified_format(scraper.matches_data)
                }
                
                # Save unified format
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(unified_data, f, indent=2, ensure_ascii=False)
                
                print(f"✓ Saved {len(scraper.matches_data)} matches to {self.output_file}")
                print()
                
                # Print summary
                scraper.print_summary()
                
                if not continuous:
                    break
                
                print(f"\n⏰ Waiting {interval} seconds before next collection...")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Collection stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Error during collection: {e}")
                if not continuous:
                    raise
                print(f"⏰ Retrying in {interval} seconds...")
                time.sleep(interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='OddPortal Odds Collector')
    parser.add_argument('--continuous', action='store_true', 
                       help='Run continuously')
    parser.add_argument('--interval', type=int, default=300,
                       help='Collection interval in seconds (default: 300)')
    
    args = parser.parse_args()
    
    collector = OddPortalCollector()
    collector.collect(continuous=args.continuous, interval=args.interval)


if __name__ == "__main__":
    main()
