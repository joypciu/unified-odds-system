#!/usr/bin/env python3
"""
OddsMagnet Real-Time Parallel Scraper
Production-ready scraper with continuous updates using remote debugging
Works both locally (remote debugging) and on VPS (headless Chrome)
"""

import json
import time
import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import logging
from playwright.async_api import async_playwright, Page, Browser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class RealTimeParallelScraper:
    """High-performance real-time scraper for OddsMagnet"""
    
    # Sports configuration
    SPORTS_CONFIG = {
        'football': {
            'enabled': True,
            'top_leagues': 10,
            'output': 'oddsmagnet_football.json',
            'markets': ['win market', 'over under betting', 'both teams to score'],
            'update_interval': 30  # seconds
        },
        'basketball': {
            'enabled': True,
            'top_leagues': 5,
            'output': 'oddsmagnet_basketball.json',
            'markets': ['win market', 'over under betting'],
            'update_interval': 45
        },
        'tennis': {
            'enabled': True,
            'top_leagues': 10,
            'output': 'oddsmagnet_tennis.json',
            'markets': ['win market'],
            'update_interval': 60
        },
        'american-football': {
            'enabled': True,
            'top_leagues': 3,
            'output': 'oddsmagnet_americanfootball.json',
            'markets': ['win market', 'over under betting'],
            'update_interval': 60
        },
        'table-tennis': {
            'enabled': True,
            'top_leagues': 5,
            'output': 'oddsmagnet_tabletennis.json',
            'markets': ['win market'],
            'update_interval': 45
        }
    }
    
    def __init__(self, mode: str = 'local', max_concurrent: int = 20):
        """
        Initialize scraper
        
        Args:
            mode: 'local' (remote debugging) or 'vps' (headless)
            max_concurrent: Max concurrent browser tabs
        """
        self.mode = mode
        self.max_concurrent = max_concurrent
        self.playwright = None
        self.browser = None
        self.context = None
        self.semaphore = None
        self.running = True
        self.iteration = 0
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        logging.info("\n⚠️  Shutdown signal received. Finishing current iteration...")
        self.running = False
    
    async def connect(self):
        """Connect to browser (local debugging or headless)"""
        self.playwright = await async_playwright().start()
        
        if self.mode == 'local':
            # Connect to existing Chrome with remote debugging
            logging.info("Connecting to Chrome remote debugging on port 9222...")
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(
                    "http://localhost:9222"
                )
                self.context = self.browser.contexts[0]
                logging.info("✓ Connected to Chrome remote debugging")
            except Exception as e:
                logging.error(f"Failed to connect to remote debugging: {e}")
                logging.info("Starting headless browser instead...")
                self.mode = 'vps'
        
        if self.mode == 'vps':
            # Launch headless Chrome for VPS
            logging.info("Launching headless Chrome...")
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            logging.info("✓ Headless Chrome started")
        
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return True
    
    async def extract_ssr_data(self, page: Page) -> Optional[Dict]:
        """Extract SSR data from page"""
        try:
            ssr_data = await page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[type="application/json"]');
                for (let script of scripts) {
                    try {
                        return JSON.parse(script.textContent);
                    } catch(e) {}
                }
                return null;
            }""")
            return ssr_data
        except:
            return None
    
    async def fetch_page_data(self, url: str, timeout: int = 20000) -> Optional[Dict]:
        """Fetch SSR data from URL with timeout"""
        async with self.semaphore:
            page = await self.context.new_page()
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                await asyncio.sleep(0.2)  # Brief wait for JS
                ssr_data = await self.extract_ssr_data(page)
                return ssr_data
            except:
                return None
            finally:
                await page.close()
    
    async def get_leagues(self, sport: str) -> List[Dict]:
        """Get leagues for sport"""
        url = f"https://oddsmagnet.com/{sport}"
        ssr_data = await self.fetch_page_data(url)
        
        if not ssr_data:
            return []
        
        for key, value in ssr_data.items():
            if isinstance(value, dict) and 'b' in value:
                b_data = value.get('b', [])
                if isinstance(b_data, list) and len(b_data) > 0:
                    if isinstance(b_data[0], dict) and 'event_id' in b_data[0]:
                        return b_data
        return []
    
    async def get_matches(self, league: Dict) -> List[Dict]:
        """Get matches for league"""
        league_slug = league.get('event_slug', '')
        sport = league.get('event_id', '').split('/')[0]
        url = f"https://oddsmagnet.com/{sport}/{league_slug}"
        
        ssr_data = await self.fetch_page_data(url)
        if not ssr_data:
            return []
        
        for key, value in ssr_data.items():
            if isinstance(value, dict) and 'b' in value:
                b_data = value.get('b', {})
                if isinstance(b_data, dict):
                    for matches in b_data.values():
                        if isinstance(matches, list) and len(matches) > 0:
                            if isinstance(matches[0], list) and len(matches[0]) >= 8:
                                return [{
                                    'name': m[0], 'league_id': m[1], 'match_url': m[2],
                                    'match_slug': m[3], 'datetime': m[4], 'home': m[5],
                                    'away': m[6], 'sport': m[7], 'league': league.get('event_name', '')
                                } for m in matches]
        return []
    
    async def get_markets(self, match: Dict) -> Dict:
        """Get markets for match"""
        url = f"https://oddsmagnet.com/{match['match_url']}"
        ssr_data = await self.fetch_page_data(url)
        
        if not ssr_data:
            return {}
        
        for key, value in ssr_data.items():
            if isinstance(value, dict) and 'b' in value:
                b_data = value.get('b', {})
                if isinstance(b_data, dict):
                    markets = {}
                    for category, market_list in b_data.items():
                        if isinstance(market_list, list) and len(market_list) > 0:
                            if isinstance(market_list[0], list) and len(market_list[0]) >= 2:
                                markets[category] = market_list
                    if markets:
                        return markets
        return {}
    
    async def get_odds(self, market_url: str) -> Optional[Dict]:
        """Get odds from market"""
        url = f"https://oddsmagnet.com/{market_url}"
        ssr_data = await self.fetch_page_data(url, timeout=15000)
        
        if not ssr_data:
            return None
        
        for key, value in ssr_data.items():
            if isinstance(value, dict) and 'b' in value:
                b_data = value.get('b', {})
                if isinstance(b_data, dict) and 'schema' in b_data and 'data' in b_data:
                    return b_data
        return None
    
    async def scrape_sport(self, sport: str, config: Dict) -> Dict:
        """Scrape single sport"""
        start = time.time()
        
        # Get leagues
        leagues = await self.get_leagues(sport)
        if not leagues:
            return None
        
        leagues = leagues[:config.get('top_leagues', 5)]
        
        # Get matches in parallel
        match_tasks = [self.get_matches(league) for league in leagues]
        all_matches_nested = await asyncio.gather(*match_tasks)
        all_matches = [m for matches in all_matches_nested for m in matches if matches]
        
        if not all_matches:
            return None
        
        # Get markets (with rate limiting - max 50 concurrent)
        batch_size = 50
        all_markets = []
        for i in range(0, len(all_matches), batch_size):
            batch = all_matches[i:i+batch_size]
            market_tasks = [self.get_markets(match) for match in batch]
            markets_batch = await asyncio.gather(*market_tasks)
            all_markets.extend(markets_batch)
        
        # Extract odds from priority markets
        markets_to_fetch = config.get('markets', ['win market'])
        odds_tasks = []
        match_market_mapping = []
        
        for match, markets in zip(all_matches, all_markets):
            if not markets:
                continue
            
            for desired_market in markets_to_fetch:
                market_found = False
                
                for category, market_list in markets.items():
                    if not market_list:
                        continue
                    
                    for market_info in market_list:
                        market_name = market_info[0].lower()
                        
                        if (desired_market.lower() == market_name or 
                            desired_market.lower() == category.lower() or
                            (desired_market.lower() == 'win market' and 'win market' in market_name)):
                            
                            odds_tasks.append(self.get_odds(market_info[1]))
                            match_market_mapping.append({
                                'match': match,
                                'market_category': category,
                                'market_name': market_info[0],
                                'market_url': market_info[1]
                            })
                            market_found = True
                            break
                    
                    if market_found:
                        break
                
                if not market_found and desired_market.lower() in category.lower():
                    if market_list and len(market_list) > 0:
                        market_info = market_list[0]
                        odds_tasks.append(self.get_odds(market_info[1]))
                        match_market_mapping.append({
                            'match': match,
                            'market_category': category,
                            'market_name': market_info[0],
                            'market_url': market_info[1]
                        })
                        break
        
        # Fetch odds in batches
        batch_size = 30
        all_odds = []
        for i in range(0, len(odds_tasks), batch_size):
            batch = odds_tasks[i:i+batch_size]
            odds_batch = await asyncio.gather(*batch)
            all_odds.extend(odds_batch)
        
        # Combine results - merge odds back into matches
        # Group odds by match_slug
        match_odds_map = {}
        for mapping, odds in zip(match_market_mapping, all_odds):
            if not odds:
                continue
            
            # Extract bookmaker odds from the odds data
            # Data structure: {"schema": {...}, "data": [{bet_name: "...", bookmaker_code: {back_decimal: "..."}}]}
            bookmaker_odds = []
            
            if 'schema' in odds and 'data' in odds:
                schema = odds['schema']
                data_rows = odds['data']
                
                # Get bookmaker codes from schema fields (exclude special fields)
                excluded_fields = {'bet_name', 'mode_date', 'best_back_decimal', 'best_lay_decimal'}
                bookmaker_codes = [
                    field['name'] 
                    for field in schema.get('fields', [])
                    if field['name'] not in excluded_fields
                ]
                
                # Extract odds from each row
                for row in data_rows:
                    bet_name = row.get('bet_name', '')
                    
                    for bookie_code in bookmaker_codes:
                        if bookie_code in row and isinstance(row[bookie_code], dict):
                            bookie_data = row[bookie_code]
                            
                            # Get decimal odds value
                            odds_value = bookie_data.get('back_decimal')
                            if odds_value:
                                bookmaker_odds.append({
                                    'bookmaker_code': bookie_code,
                                    'bookmaker_name': bookie_code.upper(),  # Could map to full names later
                                    'value': odds_value,
                                    'bet_name': bet_name
                                })
            
            match_slug = mapping['match']['match_slug']
            market_category = mapping['market_category']
            market_name = mapping['market_name']
            
            if match_slug not in match_odds_map:
                match_odds_map[match_slug] = {}
            
            if market_category not in match_odds_map[match_slug]:
                match_odds_map[match_slug][market_category] = []

            
            match_odds_map[match_slug][market_category].append({
                'name': market_name,
                'odds': bookmaker_odds
            })
        
        # Merge odds into matches
        enriched_matches = []
        for match in all_matches:
            match_copy = match.copy()
            match_slug = match['match_slug']
            
            if match_slug in match_odds_map:
                match_copy['markets'] = match_odds_map[match_slug]
            
            enriched_matches.append(match_copy)
        
        elapsed = time.time() - start
        
        return {
            'sport': sport,
            'matches': enriched_matches,
            'scraped_at': datetime.now().isoformat(),
            'elapsed_seconds': elapsed,
            'iteration': self.iteration,
            'total_markets': sum(len(m.get('markets', {})) for m in enriched_matches)
        }
    
    async def run_iteration(self):
        """Run single scraping iteration for all enabled sports"""
        self.iteration += 1
        iteration_start = time.time()
        
        logging.info(f"\n{'='*80}")
        logging.info(f"ITERATION #{self.iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*80}\n")
        
        enabled_sports = {
            sport: config 
            for sport, config in self.SPORTS_CONFIG.items() 
            if config.get('enabled', True)
        }
        
        # Scrape all sports in parallel
        tasks = [self.scrape_sport(sport, config) for sport, config in enabled_sports.items()]
        results = await asyncio.gather(*tasks)
        
        # Save results
        total_markets = 0
        for sport_data in results:
            if sport_data:
                output_file = self.SPORTS_CONFIG[sport_data['sport']]['output']
                output_path = Path(__file__).parent / output_file
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(sport_data, f, indent=2, ensure_ascii=False)
                
                markets_count = sport_data.get('total_markets', 0)
                total_markets += markets_count
                logging.info(f"✓ {sport_data['sport']}: {len(sport_data['matches'])} matches, {markets_count} markets → {output_file}")
        
        elapsed = time.time() - iteration_start
        
        logging.info(f"\n{'='*80}")
        logging.info(f"Iteration #{self.iteration} complete: {total_markets} markets in {elapsed:.1f}s")
        logging.info(f"Speed: {total_markets/elapsed:.2f} markets/sec")
        logging.info(f"{'='*80}\n")
        
        return elapsed
    
    async def run_continuous(self, min_interval: int = 30):
        """Run continuous scraping with minimum interval"""
        logging.info(f"\n{'='*80}")
        logging.info(f"ODDSMAGNET REAL-TIME PARALLEL SCRAPER")
        logging.info(f"{'='*80}")
        logging.info(f"Mode: {self.mode.upper()}")
        logging.info(f"Max concurrent: {self.max_concurrent}")
        logging.info(f"Min interval: {min_interval}s")
        logging.info(f"{'='*80}\n")
        
        await self.connect()
        
        while self.running:
            try:
                elapsed = await self.run_iteration()
                
                # Wait before next iteration
                wait_time = max(0, min_interval - elapsed)
                if wait_time > 0 and self.running:
                    logging.info(f"⏱️  Waiting {wait_time:.1f}s before next iteration...\n")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logging.error(f"Error in iteration: {e}")
                if self.running:
                    logging.info("Retrying in 30 seconds...")
                    await asyncio.sleep(30)
        
        logging.info("\n✓ Shutting down gracefully...")
        await self.disconnect()
    
    async def disconnect(self):
        """Disconnect from browser"""
        if self.context and self.mode == 'vps':
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logging.info("✓ Disconnected")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OddsMagnet Real-Time Scraper')
    parser.add_argument('--mode', choices=['local', 'vps'], default='local',
                        help='local: remote debugging, vps: headless Chrome')
    parser.add_argument('--concurrent', type=int, default=20,
                        help='Max concurrent browser tabs')
    parser.add_argument('--interval', type=int, default=30,
                        help='Minimum seconds between iterations')
    parser.add_argument('--single', action='store_true',
                        help='Run single iteration and exit')
    
    args = parser.parse_args()
    
    scraper = RealTimeParallelScraper(
        mode=args.mode,
        max_concurrent=args.concurrent
    )
    
    if args.single:
        # Single iteration mode
        await scraper.connect()
        await scraper.run_iteration()
        await scraper.disconnect()
    else:
        # Continuous mode
        await scraper.run_continuous(min_interval=args.interval)


if __name__ == "__main__":
    asyncio.run(main())
