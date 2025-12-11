#!/usr/bin/env python3
"""
Auto Cache Updater - Runs quietly in the background
Automatically collects data from all sources and updates cache
Filters out esports/virtual teams automatically
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
import logging

# Configure quiet logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    from enhanced_cache_manager import EnhancedCacheManager
    USE_ENHANCED = True
except ImportError:
    logger.warning("Enhanced cache not available, using legacy cache")
    from dynamic_cache_manager import DynamicCacheManager
    USE_ENHANCED = False


class AutoCacheUpdater:
    """Automatic cache updater that runs quietly in background"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.log_file = self.base_dir / "auto_cache_updater.log"
        
        # Initialize cache manager
        if USE_ENHANCED:
            self.cache_manager = EnhancedCacheManager(self.base_dir)
        else:
            self.cache_manager = DynamicCacheManager(self.base_dir)
        
        # Source files to monitor
        self.sources = [
            (self.base_dir / "1xbet" / "1xbet_pregame.json", "1xbet"),
            (self.base_dir / "1xbet" / "1xbet_live.json", "1xbet"),
            (self.base_dir / "bet365" / "bet365_current_pregame.json", "bet365"),
            (self.base_dir / "bet365" / "bet365_live_current.json", "bet365"),
            (self.base_dir / "fanduel" / "fanduel_pregame.json", "fanduel"),
            (self.base_dir / "fanduel" / "fanduel_live.json", "fanduel"),
        ]
        
        self.stats = {
            'total_updates': 0,
            'total_teams_added': 0,
            'total_sports_added': 0,
            'total_esports_filtered': 0,
            'last_update': None,
            'errors': []
        }
    
    def update_from_sources(self, quiet: bool = True) -> dict:
        """Update cache from all available sources"""
        results = {
            'success': True,
            'sources_processed': 0,
            'new_teams': 0,
            'new_sports': 0,
            'esports_filtered': 0,
            'errors': []
        }
        
        for file_path, source in self.sources:
            if not file_path.exists():
                if not quiet:
                    logger.debug(f"Skipping {file_path.name} (not found)")
                continue
            
            try:
                if USE_ENHANCED:
                    summary = self.cache_manager.auto_update_from_json(
                        file_path, source, quiet=quiet
                    )
                else:
                    summary = self.cache_manager.auto_update_from_file(
                        file_path, source
                    )
                
                if summary.get('success'):
                    results['sources_processed'] += 1
                    results['new_teams'] += summary.get('new_teams', 0)
                    results['new_sports'] += summary.get('new_sports', 0)
                    results['esports_filtered'] += summary.get('esports_filtered', 0)
                else:
                    results['errors'].extend(summary.get('errors', []))
            
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                results['errors'].append(error_msg)
                if not quiet:
                    logger.error(error_msg)
        
        # Update stats
        self.stats['total_updates'] += 1
        self.stats['total_teams_added'] += results['new_teams']
        self.stats['total_sports_added'] += results['new_sports']
        self.stats['total_esports_filtered'] += results['esports_filtered']
        self.stats['last_update'] = datetime.now().isoformat()
        
        if results['errors']:
            self.stats['errors'].extend(results['errors'])
            results['success'] = False
        
        return results
    
    def run_once(self, quiet: bool = True) -> dict:
        """Run a single update cycle"""
        if not quiet:
            logger.info("Starting cache update cycle...")
        
        results = self.update_from_sources(quiet=quiet)
        
        if not quiet:
            if results['success']:
                logger.info(f"Update complete: +{results['new_teams']} teams, "
                          f"+{results['new_sports']} sports, "
                          f"{results['esports_filtered']} esports filtered")
            else:
                logger.warning(f"Update completed with errors: {len(results['errors'])} errors")
        
        # Save stats
        self._save_stats()
        
        return results
    
    def run_continuous(self, interval_seconds: int = 300, quiet: bool = True):
        """Run continuous updates at specified interval"""
        logger.info(f"Starting continuous cache updater (interval: {interval_seconds}s)")
        
        try:
            while True:
                try:
                    results = self.run_once(quiet=quiet)
                    
                    if not quiet and results['new_teams'] > 0:
                        logger.info(f"Cache updated: +{results['new_teams']} teams")
                
                except Exception as e:
                    logger.error(f"Update cycle failed: {e}")
                
                # Wait for next cycle
                time.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Continuous updater stopped by user")
    
    def _save_stats(self):
        """Save updater statistics"""
        try:
            stats_file = self.base_dir / "cache_updater_stats.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def get_stats(self) -> dict:
        """Get current statistics"""
        cache_stats = self.cache_manager.get_stats()
        
        return {
            'updater': self.stats,
            'cache': cache_stats
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automatic cache updater - runs quietly in background"
    )
    parser.add_argument(
        '--mode', 
        choices=['once', 'continuous'],
        default='once',
        help="Run mode: 'once' for single update, 'continuous' for background monitoring"
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help="Update interval in seconds for continuous mode (default: 300)"
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Enable verbose logging (default: quiet mode)"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Initialize updater
    updater = AutoCacheUpdater()
    
    try:
        if args.mode == 'once':
            # Single update
            results = updater.run_once(quiet=not args.verbose)
            
            if args.verbose:
                print(f"\nUpdate Results:")
                print(f"  Sources processed: {results['sources_processed']}")
                print(f"  New teams: {results['new_teams']}")
                print(f"  New sports: {results['new_sports']}")
                print(f"  Esports filtered: {results['esports_filtered']}")
                
                if results['errors']:
                    print(f"\nErrors:")
                    for error in results['errors']:
                        print(f"  - {error}")
            
            return 0 if results['success'] else 1
        
        else:
            # Continuous mode
            updater.run_continuous(
                interval_seconds=args.interval,
                quiet=not args.verbose
            )
            return 0
    
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
