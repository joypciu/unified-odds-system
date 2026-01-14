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
from typing import Dict, List, Set

# Add parent directory to path (bookmakers folder)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the working scraper
from bookmakers.oddportal.working_scraper import OddsPortalScraper


class OddPortalCollector:
    """Wrapper for OddPortal scraper to integrate with unified system"""

    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.output_file = self.script_dir / "oddportal_unified.json"
        self.raw_data_file = self.script_dir / "matches_odds_data.json"
        self.sports_completed: Set[str] = set()

    def convert_to_unified_format(self, matches_data: List[Dict]) -> List[Dict]:
        """Convert OddPortal format to unified format compatible with oddsmagnet viewer"""
        unified_matches = []

        for match in matches_data:
            markets = {}
            win_market_odds = []

            if match.get('bookmakers'):
                for bookmaker in match['bookmakers']:
                    if not bookmaker.get('available', False):
                        continue

                    code = bookmaker['name'].lower()[:2]
                    name = bookmaker['name']

                    # Home
                    if bookmaker.get('home_odds'):
                        win_market_odds.append({
                            'bookmaker_code': code,
                            'bookmaker_name': name,
                            'decimal_odds': bookmaker['home_odds'],
                            'selection': match['home'],
                            'bet_name': match['home'],
                            'fractional_odds': self._decimal_to_fractional(bookmaker['home_odds']),
                        })

                    # Draw
                    if bookmaker.get('draw_odds'):
                        win_market_odds.append({
                            'bookmaker_code': code,
                            'bookmaker_name': name,
                            'decimal_odds': bookmaker['draw_odds'],
                            'selection': 'Draw',
                            'bet_name': 'Draw',
                            'fractional_odds': self._decimal_to_fractional(bookmaker['draw_odds']),
                        })

                    # Away
                    if bookmaker.get('away_odds'):
                        win_market_odds.append({
                            'bookmaker_code': code,
                            'bookmaker_name': name,
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

    @staticmethod
    def _decimal_to_fractional(decimal_odds: float) -> str:
        """Convert decimal odds to simplified fractional format"""
        try:
            decimal = float(decimal_odds)
            if decimal <= 1.0:
                return "0/1"

            numerator = int((decimal - 1) * 100)
            denominator = 100

            from math import gcd
            common = gcd(numerator, denominator)
            numerator //= common
            denominator //= common

            return f"{numerator}/{denominator}"
        except (ValueError, TypeError):
            return "1/1"

    def save_progressive_data(self, sport_name: str, matches_data: List[Dict]):
        """Save data progressively as each sport completes"""
        try:
            self.sports_completed.add(sport_name)

            unified_data = {
                'sport': 'multi',
                'timestamp': datetime.now().isoformat(),
                'source': 'oddportal',
                'matches_count': len(matches_data),
                'sports_completed': sorted(self.sports_completed),
                'is_partial': True,
                'matches': self.convert_to_unified_format(matches_data)
            }

            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(unified_data, f, indent=2, ensure_ascii=False)

            print(f"  Progressive save: {len(matches_data)} matches "
                  f"({len(self.sports_completed)} sports completed)")

        except Exception as e:
            print(f"  Warning: Progressive save failed: {e}")

    def collect(self, continuous: bool = False, interval: int = 300):
        """Main collection loop"""
        while True:
            print("=" * 80)
            print("ODDPORTAL COLLECTOR - Starting collection")
            print("=" * 80)
            print()

            self.sports_completed.clear()

            try:
                scraper = OddsPortalScraper()
                scraper.sport_complete_callback = self.save_progressive_data

                print("Scraping OddPortal data...")
                print("Progressive updates enabled - data will appear as each sport completes\n")

                # Add timeout for scrape_all to prevent hanging
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Scraping took too long (>1800s)")
                
                # Set 30-minute timeout for the entire scraping process
                if hasattr(signal, 'SIGALRM'):  # Unix only
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(1800)  # 30 minutes
                
                try:
                    scraper.scrape_all()
                finally:
                    if hasattr(signal, 'SIGALRM'):
                        signal.alarm(0)  # Cancel alarm

                # Final raw save
                scraper.save_to_json(filename=str(self.raw_data_file))

                # Final unified save
                print("\nConverting to unified format (final)...")
                final_data = {
                    'sport': 'multi',
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddportal',
                    'matches_count': len(scraper.matches_data),
                    'sports_completed': sorted(self.sports_completed),
                    'is_partial': False,
                    'matches': self.convert_to_unified_format(scraper.matches_data)
                }

                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, indent=2, ensure_ascii=False)

                print(f"✓ Saved {len(scraper.matches_data)} matches to {self.output_file}")
                print()

                scraper.print_summary()

                if not continuous:
                    break

                print(f"\nWaiting {interval} seconds before next collection...")
                time.sleep(interval)

            except TimeoutError as te:
                print(f"\n⚠️ Scraping timeout: {te}")
                print(f"Saving partial data ({len(getattr(scraper, 'matches_data', []))} matches)...")
                
                # Save what we have
                if hasattr(scraper, 'matches_data') and scraper.matches_data:
                    scraper.save_to_json(filename=str(self.raw_data_file))
                    
                    partial_data = {
                        'sport': 'multi',
                        'timestamp': datetime.now().isoformat(),
                        'source': 'oddportal',
                        'matches_count': len(scraper.matches_data),
                        'sports_completed': sorted(self.sports_completed),
                        'is_partial': True,
                        'matches': self.convert_to_unified_format(scraper.matches_data)
                    }
                    
                    with open(self.output_file, 'w', encoding='utf-8') as f:
                        json.dump(partial_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"✓ Saved partial data: {len(scraper.matches_data)} matches")
                
                if not continuous:
                    break
                print(f"Retrying in {interval} seconds...")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\nCollection stopped by user")
                break
            except Exception as e:
                print(f"\nError during collection: {e}")
                import traceback
                traceback.print_exc()
                
                if not continuous:
                    raise
                print(f"Retrying in {interval} seconds...")
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
    # Optional: force UTF-8 output on Windows
    if sys.platform == "win32":
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    main()