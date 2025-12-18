"""
OddsMagnet Volleyball Real-Time Odds Collector
================================================

Collects live volleyball odds from ALL volleyball leagues and tournaments available on OddsMagnet.
Uses dynamic market discovery - fetches ALL markets without filtering.

Features:
- Real-time data collection (30-second intervals)
- Dynamic market discovery (ALL markets from API)
- International leagues (Spain, Poland, Russia, Brazil, etc.)
- Multiple bookmakers comparison
- League breakdown by country
- Concurrent scraping (20 workers, 15 req/s)

Output: oddsmagnet_volleyball.json

Usage:
    python oddsmagnet_volleyball_realtime.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper
from oddsmagnet_optimized_collector import OddsMagnetRealtimeCollector as BaseCollector


class VolleyballRealtimeCollector(BaseCollector):
    """Real-time collector for Volleyball odds from OddsMagnet"""
    
    def __init__(self, sport: str = 'volleyball', output_file: str = 'oddsmagnet_volleyball.json',
                 update_interval: float = 30.0, max_workers: int = 20, rate_limit: float = 15.0):
        """
        Initialize Volleyball collector
        
        Args:
            sport: Sport identifier ('volleyball')
            output_file: Output JSON filename
            update_interval: Seconds between updates (default: 30)
            max_workers: Concurrent workers (default: 20)
            rate_limit: Max requests per second (default: 15)
        """
        super().__init__(
            sport=sport,
            output_file=output_file,
            update_interval=update_interval,
            max_workers=max_workers,
            rate_limit=rate_limit
        )
        
        # Dynamic market discovery - fetch ALL markets
        self.market_filter = None  # None means ALL markets
        
        # Track discovered markets
        self.discovered_markets = set()
    
    async def collect_odds(self) -> dict:
        """
        Collect volleyball odds from OddsMagnet
        
        Returns:
            dict: Structured odds data with metadata
        """
        try:
            print(f"\n{'='*80}")
            print(f"🏐 Collecting Volleyball Odds - Iteration {self.iteration}")
            print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}\n")
            
            # Scrape volleyball odds using optimized scraper
            scraper = OddsMagnetOptimizedScraper(
                sport=self.sport,
                max_workers=self.max_workers,
                rate_limit=self.rate_limit
            )
            
            result = await scraper.scrape_sport(market_filter=self.market_filter)
            
            matches = result.get('matches', [])
            
            # Track discovered markets
            for match in matches:
                for odd in match.get('odds', []):
                    market = odd.get('market', 'Unknown')
                    if market not in self.discovered_markets:
                        self.discovered_markets.add(market)
                        print(f"   🆕 New market discovered: {market}")
            
            # Organize by league
            league_breakdown = {}
            for match in matches:
                league = match.get('league', 'Unknown')
                league_breakdown[league] = league_breakdown.get(league, 0) + 1
            
            print(f"\n📊 Volleyball Leagues Summary:")
            print(f"   Total Matches: {len(matches)}")
            print(f"   Total Leagues: {len(league_breakdown)}")
            
            if league_breakdown:
                print(f"\n   League Breakdown:")
                for league, count in sorted(league_breakdown.items(), key=lambda x: x[1], reverse=True):
                    print(f"      • {league}: {count} matches")
            
            print(f"\n   Discovered Markets ({len(self.discovered_markets)}):")
            for market in sorted(self.discovered_markets):
                print(f"      • {market}")
            
            return {
                'source': 'oddsmagnet_volleyball',
                'sport': self.sport,
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'total_matches': len(matches),
                'league_breakdown': league_breakdown,
                'discovered_markets': sorted(list(self.discovered_markets)),
                'matches': matches
            }
            
        except Exception as e:
            print(f"❌ Error collecting volleyball odds: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'source': 'oddsmagnet_volleyball',
                'sport': self.sport,
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'error': str(e),
                'total_matches': 0,
                'league_breakdown': {},
                'discovered_markets': sorted(list(self.discovered_markets)),
                'matches': []
            }


async def run_realtime_loop(update_interval: float = 30.0):
    """
    Run volleyball odds collector in continuous loop
    
    Args:
        update_interval: Seconds between updates (default: 30)
    """
    collector = VolleyballRealtimeCollector(
        sport='volleyball',
        output_file='oddsmagnet_volleyball.json',
        update_interval=update_interval,
        max_workers=20,
        rate_limit=15.0
    )
    
    print("\n" + "="*80)
    print("🏐 OddsMagnet Volleyball Real-Time Collector")
    print("="*80)
    print(f"Sport: Volleyball (ALL leagues)")
    print(f"Update Interval: {update_interval} seconds")
    print(f"Output: oddsmagnet_volleyball.json")
    print(f"Market Discovery: Dynamic (ALL markets)")
    print(f"Workers: 20 concurrent")
    print(f"Rate Limit: 15 req/s")
    print("="*80 + "\n")
    
    try:
        await collector.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Collector stopped by user (Ctrl+C)")
        print("✅ Shutdown complete\n")
    except Exception as e:
        print(f"\n\n❌ Collector error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Default: 30 second updates
    asyncio.run(run_realtime_loop(update_interval=30.0))
