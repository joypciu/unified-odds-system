"""
OddsMagnet Boxing Real-Time Odds Collector
============================================

Collects live boxing odds from ALL boxing events and tournaments available on OddsMagnet.
Uses dynamic market discovery - fetches ALL markets without filtering.

Features:
- Real-time data collection (30-second intervals)
- Dynamic market discovery (ALL markets from API)
- Boxing/MMA/UFC events
- Multiple bookmakers comparison
- Event breakdown by category
- Concurrent scraping (20 workers, 15 req/s)

Output: oddsmagnet_boxing.json

Usage:
    python oddsmagnet_boxing_realtime.py
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


class BoxingRealtimeCollector(BaseCollector):
    """Real-time collector for Boxing odds from OddsMagnet"""
    
    def __init__(self, sport: str = 'boxing', output_file: str = 'oddsmagnet_boxing.json',
                 update_interval: float = 30.0, max_workers: int = 20, rate_limit: float = 15.0):
        """
        Initialize Boxing collector
        
        Args:
            sport: Sport identifier ('boxing')
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
        Collect boxing odds from OddsMagnet
        
        Returns:
            dict: Structured odds data with metadata
        """
        try:
            print(f"\n{'='*80}")
            print(f"🥊 Collecting Boxing Odds - Iteration {self.iteration}")
            print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}\n")
            
            # Scrape boxing odds using optimized scraper
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
            
            # Organize by event/category
            event_breakdown = {}
            for match in matches:
                league = match.get('league', 'Unknown')
                event_breakdown[league] = event_breakdown.get(league, 0) + 1
            
            print(f"\n📊 Boxing Events Summary:")
            print(f"   Total Events: {len(matches)}")
            print(f"   Event Categories: {len(event_breakdown)}")
            
            if event_breakdown:
                print(f"\n   Event Breakdown:")
                for event, count in sorted(event_breakdown.items(), key=lambda x: x[1], reverse=True):
                    print(f"      • {event}: {count} events")
            
            print(f"\n   Discovered Markets ({len(self.discovered_markets)}):")
            for market in sorted(self.discovered_markets):
                print(f"      • {market}")
            
            return {
                'source': 'oddsmagnet_boxing',
                'sport': self.sport,
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'total_matches': len(matches),
                'event_breakdown': event_breakdown,
                'discovered_markets': sorted(list(self.discovered_markets)),
                'matches': matches
            }
            
        except Exception as e:
            print(f"❌ Error collecting boxing odds: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'source': 'oddsmagnet_boxing',
                'sport': self.sport,
                'timestamp': datetime.now().isoformat(),
                'iteration': self.iteration,
                'error': str(e),
                'total_matches': 0,
                'event_breakdown': {},
                'discovered_markets': sorted(list(self.discovered_markets)),
                'matches': []
            }


async def run_realtime_loop(update_interval: float = 30.0):
    """
    Run boxing odds collector in continuous loop
    
    Args:
        update_interval: Seconds between updates (default: 30)
    """
    collector = BoxingRealtimeCollector(
        sport='boxing',
        output_file='oddsmagnet_boxing.json',
        update_interval=update_interval,
        max_workers=20,
        rate_limit=15.0
    )
    
    print("\n" + "="*80)
    print("🥊 OddsMagnet Boxing Real-Time Collector")
    print("="*80)
    print(f"Sport: Boxing (ALL events)")
    print(f"Update Interval: {update_interval} seconds")
    print(f"Output: oddsmagnet_boxing.json")
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
