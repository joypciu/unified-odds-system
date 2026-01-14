#!/usr/bin/env python3
"""
Parallel Sports Scraper - Run all sport scrapers in parallel using multiprocessing
Dramatically faster than sequential scraping
"""

import json
import time
import asyncio
import logging
import multiprocessing as mp
import signal
import sys
import atexit
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from base_sport_scraper import BaseSportScraper, cleanup_chrome_processes, acquire_lock, release_lock

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Sports configuration
SPORTS_CONFIG = {
    'football': {
        'enabled': True,
        'top_leagues': 10,
        'output': 'oddsmagnet_football.json',
        'markets': ['win market', 'over under betting', 'both teams to score'],
    },
    'basketball': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_basketball.json',
        'markets': ['win market', 'over under betting'],
    },
    'tennis': {
        'enabled': True,
        'top_leagues': 10,
        'output': 'oddsmagnet_tennis.json',
        'markets': ['win market'],
    },
    'american-football': {
        'enabled': True,
        'top_leagues': 3,
        'output': 'oddsmagnet_americanfootball.json',
        'markets': ['win market', 'over under betting'],
    },
    'table-tennis': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_tabletennis.json',
        'markets': ['win market'],
    },
    'volleyball': {
        'enabled': True,
        'top_leagues': 8,
        'output': 'oddsmagnet_volleyball.json',
        'markets': ['win market'],
    },
    'cricket': {
        'enabled': True,
        'top_leagues': 6,
        'output': 'oddsmagnet_cricket.json',
        'markets': ['win market'],
    },
    'boxing': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_boxing.json',
        'markets': ['win market'],
    },
    'baseball': {
        'enabled': True,
        'top_leagues': 5,
        'output': 'oddsmagnet_baseball.json',
        'markets': ['win market', 'over under betting'],
    }
}


def scrape_sport_worker(sport: str, config: Dict, mode: str = 'local') -> Dict:
    """
    Worker function to scrape a single sport (runs in separate process)
    
    Args:
        sport: Sport name
        config: Sport configuration
        mode: 'local' or 'vps'
    
    Returns:
        Scrape result dict or None
    """
    try:
        async def run_scraper():
            # Reduce concurrency for VPS to avoid overwhelming system
            # VPS sequential mode can handle more concurrent browsers per sport
            max_concurrent = 3 if mode == 'vps' else 15
            scraper = BaseSportScraper(sport, config, mode, max_concurrent=max_concurrent)
            return await scraper.run()
        
        result = asyncio.run(run_scraper())
        return {'sport': sport, 'success': True, 'data': result}
    except Exception as e:
        logging.error(f"❌ {sport.upper()}: Error - {e}")
        return {'sport': sport, 'success': False, 'error': str(e)}


class ParallelSportsScraper:
    """Run multiple sport scrapers in parallel"""
    
    def __init__(self, mode: str = 'local', sports_config: Dict = None):
        """
        Initialize parallel scraper
        
        Args:
            mode: 'local' (remote debugging) or 'vps' (headless)
            sports_config: Optional custom sports configuration
        """
        self.mode = mode
        self.sports_config = sports_config or SPORTS_CONFIG
        self.output_dir = Path(__file__).parent
    
    def run_once(self) -> Dict:
        """
        Run all enabled sports scrapers in parallel
        
        Returns:
            Combined results from all sports
        """
        start_time = time.time()
        
        # Filter enabled sports
        enabled_sports = {
            sport: config for sport, config in self.sports_config.items()
            if config.get('enabled', True)
        }
        
        if not enabled_sports:
            logging.warning("No enabled sports to scrape")
            return {}
        
        logging.info(f"🚀 Starting parallel scrape for {len(enabled_sports)} sports...")
        logging.info(f"   Sports: {', '.join(s.upper() for s in enabled_sports.keys())}")
        
        # VPS Mode: Run sequentially to avoid browser crashes
        # Local Mode: Run in parallel for speed
        if self.mode == 'vps':
            logging.info("🔄 VPS Mode: Running sports sequentially to prevent browser crashes")
            results = []
            for sport, config in enabled_sports.items():
                logging.info(f"   → Starting {sport.upper()}...")
                result = scrape_sport_worker(sport, config, self.mode)
                results.append(result)
        else:
            # Local mode - use parallel processing for speed
            num_processes = min(len(enabled_sports), mp.cpu_count())
            with mp.Pool(processes=num_processes) as pool:
                # Launch all sport scrapers in parallel
                tasks = [
                    pool.apply_async(scrape_sport_worker, (sport, config, self.mode))
                    for sport, config in enabled_sports.items()
                ]
                
                # Wait for all to complete
                results = [task.get() for task in tasks]
        
        # Process results
        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if not r.get('success')]
        
        total_time = round(time.time() - start_time, 2)
        
        # Log summary
        logging.info(f"\n{'='*60}")
        logging.info(f"📊 PARALLEL SCRAPE COMPLETE")
        logging.info(f"{'='*60}")
        logging.info(f"Total time: {total_time}s")
        logging.info(f"Successful: {len(successful)}/{len(enabled_sports)} sports")
        
        if successful:
            logging.info(f"\n✅ Successful sports:")
            for r in successful:
                data = r.get('data', {})
                matches = data.get('matches_count', 0) if data else 0
                scrape_time = data.get('scrape_time_seconds', 0) if data else 0
                logging.info(f"   • {r['sport'].upper()}: {matches} matches ({scrape_time}s)")
        
        if failed:
            logging.info(f"\n❌ Failed sports:")
            for r in failed:
                logging.info(f"   • {r['sport'].upper()}: {r.get('error', 'Unknown error')}")
        
        logging.info(f"{'='*60}\n")
        
        # Combine all data
        combined = {
            'timestamp': datetime.now().isoformat(),
            'total_scrape_time': total_time,
            'sports_scraped': len(successful),
            'sports_failed': len(failed),
            'sports': {}
        }
        
        for result in successful:
            if result.get('data'):
                combined['sports'][result['sport']] = result['data']
        
        # Save combined file
        combined_file = self.output_dir / 'oddsmagnet_all_sports.json'
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)
        
        logging.info(f"💾 Combined data saved to: {combined_file}")
        
        return combined
    
    def run_continuous(self, interval: int = 60):
        """
        Run scrapers continuously with interval between iterations
        
        Args:
            interval: Seconds between iterations
        """
        iteration = 0
        
        while True:
            iteration += 1
            logging.info(f"\n{'#'*60}")
            logging.info(f"ITERATION {iteration}")
            logging.info(f"{'#'*60}\n")
            
            try:
                self.run_once()
            except KeyboardInterrupt:
                logging.info("\n⚠️ Interrupted by user")
                break
            except Exception as e:
                logging.error(f"❌ Error in iteration {iteration}: {e}")
            
            if iteration == 1:
                # After first iteration, show how to access data
                logging.info(f"\n{'='*60}")
                logging.info("🌐 ACCESS YOUR DATA:")
                logging.info("   Local: http://localhost:8000/html/oddsmagnet.html")
                logging.info("   Files: Check oddsmagnet_*.json in current directory")
                logging.info(f"{'='*60}\n")
            
            logging.info(f"⏸️  Waiting {interval}s before next iteration...")
            time.sleep(interval)


def signal_handler(signum, frame):
    """Handle termination signals"""
    logging.info(f"\n⚠️ Received signal {signum}, cleaning up...")
    cleanup_chrome_processes()
    release_lock()
    sys.exit(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parallel OddsMagnet Sports Scraper')
    parser.add_argument('--mode', choices=['local', 'vps'], default='local',
                       help='Scraper mode (local=remote debugging, vps=headless)')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously instead of once')
    parser.add_argument('--interval', type=int, default=60,
                       help='Seconds between iterations (for continuous mode)')
    parser.add_argument('--sports', nargs='+',
                       choices=['football', 'basketball', 'tennis', 'american-football', 'table-tennis'],
                       help='Specific sports to scrape (default: all enabled)')
    
    args = parser.parse_args()
    
    # Clean up any zombie Chrome processes from previous runs
    logging.info("🧹 Cleaning up any existing Chrome processes...")
    cleanup_chrome_processes()
    
    # Acquire lock to prevent multiple instances
    if not acquire_lock():
        logging.error("❌ Another instance is already running. Exiting.")
        sys.exit(1)
    
    # Register cleanup handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(lambda: (cleanup_chrome_processes(), release_lock()))
    
    try:
        # Filter sports if specified
        config = SPORTS_CONFIG.copy()
        if args.sports:
            for sport in config:
                config[sport]['enabled'] = sport in args.sports
        
        scraper = ParallelSportsScraper(mode=args.mode, sports_config=config)
        
        if args.continuous:
            scraper.run_continuous(interval=args.interval)
        else:
            scraper.run_once()
    except KeyboardInterrupt:
        logging.info("\n⚠️ Interrupted by user")
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
    finally:
        cleanup_chrome_processes()
        release_lock()


if __name__ == "__main__":
    # Required for Windows multiprocessing
    mp.freeze_support()
    main()
