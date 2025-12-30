#!/usr/bin/env python3
"""
Base Sport Scraper - Modular scraper for individual sports
Can be run independently or as part of parallel collection
"""

import json
import time
import asyncio
import logging
import subprocess
import socket
import os
import signal
import psutil
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Lock file for single instance
LOCK_FILE = Path('/tmp/oddsmagnet_scraper.lock')
CHROME_USER_DATA_DIR = Path('/tmp/chrome_oddsmagnet')


def cleanup_chrome_processes():
    """Kill all Chrome processes related to oddsmagnet"""
    try:
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'chrome_oddsmagnet' in cmdline or 'chrome' in proc.info['name'].lower():
                    # Kill Chrome process
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                pass
        
        if killed_count > 0:
            logging.info(f"🧹 Killed {killed_count} Chrome processes")
        
        # Clean up Chrome user data directory
        if CHROME_USER_DATA_DIR.exists():
            try:
                import shutil
                shutil.rmtree(CHROME_USER_DATA_DIR, ignore_errors=True)
                logging.info(f"🧹 Cleaned up Chrome user data directory")
            except:
                pass
                
    except Exception as e:
        logging.warning(f"Error during Chrome cleanup: {e}")


def acquire_lock() -> bool:
    """Acquire lock file to prevent multiple instances"""
    try:
        if LOCK_FILE.exists():
            # Check if process is still running
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())
                
                if psutil.pid_exists(old_pid):
                    logging.error(f"Another instance is running (PID: {old_pid})")
                    return False
                else:
                    logging.info(f"Removing stale lock file (PID {old_pid} no longer exists)")
                    LOCK_FILE.unlink()
            except:
                LOCK_FILE.unlink()
        
        # Create lock file with current PID
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        logging.info(f"✓ Acquired lock (PID: {os.getpid()})")
        return True
        
    except Exception as e:
        logging.error(f"Failed to acquire lock: {e}")
        return False


def release_lock():
    """Release lock file"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logging.info("✓ Released lock")
    except Exception as e:
        logging.warning(f"Error releasing lock: {e}")


class BaseSportScraper:
    """Base class for sport-specific scrapers"""
    
    def __init__(self, sport: str, config: Dict, mode: str = 'local', max_concurrent: int = 20):
        """
        Initialize sport scraper
        
        Args:
            sport: Sport name (football, basketball, tennis, etc.)
            config: Sport configuration dict
            mode: 'local' (remote debugging) or 'vps' (headless)
            max_concurrent: Max concurrent browser tabs
        """
        self.sport = sport
        self.config = config
        self.mode = mode
        self.max_concurrent = max_concurrent
        self.playwright = None
        self.browser = None
        self.context = None
        self.semaphore = None
        self.chrome_process = None
        self.output_file = Path(__file__).parent / config.get('output', f'oddsmagnet_{sport}.json')
        
        logging.info(f"🎯 Initialized {sport.upper()} scraper")
    
    def _is_port_open(self, port: int, host: str = 'localhost') -> bool:
        """Check if a port is open"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _start_chrome_debug(self):
        """Start Chrome with remote debugging if not already running (single instance only)"""
        if self._is_port_open(9222):
            logging.info(f"✓ Chrome already running on port 9222")
            return True
        
        # Check if there are any existing Chrome processes and kill them
        cleanup_chrome_processes()
        
        try:
            logging.info(f"🚀 Starting Chrome with remote debugging on port 9222...")
            
            # Try to find Chrome executable
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
            ]
            
            chrome_exe = None
            for path in chrome_paths:
                if Path(path).exists():
                    chrome_exe = path
                    break
            
            if not chrome_exe:
                logging.warning("Chrome executable not found")
                return False
            
            # Ensure clean Chrome user data directory
            if CHROME_USER_DATA_DIR.exists():
                import shutil
                shutil.rmtree(CHROME_USER_DATA_DIR, ignore_errors=True)
            CHROME_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            
            # Start Chrome in background
            cmd = [
                chrome_exe,
                '--remote-debugging-port=9222',
                f'--user-data-dir={CHROME_USER_DATA_DIR}',
                '--no-first-run',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--headless=new'
            ]
            
            self.chrome_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait for Chrome to start
            for _ in range(10):
                time.sleep(0.5)
                if self._is_port_open(9222):
                    logging.info(f"✓ Chrome started successfully on port 9222 (PID: {self.chrome_process.pid})")
                    return True
            
            logging.warning("Chrome started but port 9222 not accessible")
            return False
            
        except Exception as e:
            logging.warning(f"Failed to start Chrome: {e}")
            return False
    
    async def connect(self):
        """Connect to browser (local debugging or headless)"""
        self.playwright = await async_playwright().start()
        
        if self.mode == 'local':
            # Ensure Chrome with remote debugging is running
            self._start_chrome_debug()
            
            # Connect to existing Chrome with remote debugging
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(
                    "http://localhost:9222"
                )
                self.context = self.browser.contexts[0]
                logging.info(f"✓ {self.sport}: Connected to Chrome remote debugging")
            except Exception as e:
                logging.warning(f"{self.sport}: Remote debugging failed, switching to headless")
                self.mode = 'vps'
        
        if self.mode == 'vps':
            # Launch headless Chrome
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create context with anti-detection headers
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            # Inject stealth JavaScript on every page
            await self.context.add_init_script("""
                // Override navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock navigator.plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock navigator.languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock navigator properties
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
                
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
            """)
            
            logging.info(f"✓ {self.sport}: Headless Chrome started with anti-detection")
        
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return True
    
    async def disconnect(self):
        """Disconnect from browser and cleanup Chrome"""
        try:
            if self.mode == 'vps' and self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            # Kill Chrome process if we started it
            if self.chrome_process and self.chrome_process.poll() is None:
                self.chrome_process.kill()
                logging.info("✓ Killed Chrome debug process")
                
        except Exception as e:
            logging.warning(f"Error during disconnect: {e}")
        finally:
            # Always cleanup Chrome processes to be safe
            cleanup_chrome_processes()
    
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
    
    async def fetch_page_data(self, url: str, timeout: int = 20000, retries: int = 2) -> Optional[Dict]:
        """Fetch SSR data from URL with timeout and retry logic"""
        async with self.semaphore:
            page = await self.context.new_page()
            
            for attempt in range(retries):
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                    await asyncio.sleep(0.8)  # Give page time to render (increased for slow pages)
                    ssr_data = await self.extract_ssr_data(page)
                    
                    if ssr_data:
                        return ssr_data
                    
                    # If no data on first attempt, retry
                    if attempt < retries - 1:
                        logging.debug(f"{self.sport}: No SSR data found, retrying ({attempt + 1}/{retries})...")
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    if attempt < retries - 1:
                        logging.debug(f"{self.sport}: Failed to fetch (attempt {attempt + 1}/{retries}): {e}")
                        await asyncio.sleep(0.5)
                    else:
                        logging.warning(f"{self.sport}: Failed to fetch {url} after {retries} attempts: {e}")
                        
            await page.close()
            return None
    
    async def get_leagues(self) -> List[Dict]:
        """Get leagues for sport"""
        url = f"https://oddsmagnet.com/{self.sport}"
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
        sport_id = league.get('event_id', '').split('/')[0]
        url = f"https://oddsmagnet.com/{sport_id}/{league_slug}"
        
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
                                    'name': m[0], 
                                    'league_id': m[1], 
                                    'match_url': m[2],
                                    'match_slug': m[3], 
                                    'datetime': m[4], 
                                    'home': m[5],
                                    'home_team': m[5],  # UI expects home_team
                                    'away': m[6], 
                                    'away_team': m[6],  # UI expects away_team
                                    'sport': m[7], 
                                    'league': league.get('event_name', '')
                                } for m in matches]
        return []
    
    async def get_markets(self, match: Dict) -> Dict:
        """Get markets for match"""
        url = f"https://oddsmagnet.com/{match['match_url']}"
        ssr_data = await self.fetch_page_data(url, retries=3)  # More retries for markets
        
        if not ssr_data:
            logging.debug(f"{self.sport}: No SSR data for match: {match.get('name', 'unknown')}")
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
                    else:
                        logging.debug(f"{self.sport}: Match has SSR data but no valid markets: {match.get('name', 'unknown')}")
        
        logging.debug(f"{self.sport}: No market structure found for: {match.get('name', 'unknown')}")
        return {}
    
    async def get_odds(self, market_url: str) -> Optional[Dict]:
        """Get odds from market"""
        url = f"https://oddsmagnet.com/{market_url}"
        # Longer timeout for odds pages (basketball/tennis can be slow)
        ssr_data = await self.fetch_page_data(url, timeout=30000, retries=3)
        
        if not ssr_data:
            return None
        
        for key, value in ssr_data.items():
            if isinstance(value, dict) and 'b' in value:
                b_data = value.get('b', {})
                if isinstance(b_data, dict) and 'schema' in b_data and 'data' in b_data:
                    return b_data
        return None
    
    def extract_players_from_odds(self, odds_data: Dict) -> List[str]:
        """
        Extract player/fighter names from odds data for tournament events.
        Returns list of unique player names (typically 2 for tennis/boxing).
        """
        if not odds_data or 'data' not in odds_data:
            return []
        
        players = []
        seen = set()
        
        for row in odds_data.get('data', []):
            bet_name = row.get('bet_name', '').strip()
            if bet_name and bet_name.lower() not in ['draw', ''] and bet_name not in seen:
                players.append(bet_name)
                seen.add(bet_name)
                if len(players) >= 2:
                    break
        
        return players
    
    def transform_odds_to_ui_format(self, odds_data: Dict) -> List[Dict]:
        """
        Transform Pandas DataFrame JSON format to UI-expected format
        
        Input (Pandas DataFrame JSON):
        {
            "schema": {"fields": [{"name": "bet_name"}, {"name": "vb"}, ...]},
            "data": [
                {
                    "bet_name": "home",
                    "vb": {"back_decimal": "1.50", ...},
                    "xb": {"back_decimal": "1.55", ...}
                }
            ]
        }
        
        Output (UI format):
        [
            {
                "bookmaker_code": "vb",
                "bookmaker_name": "VB", 
                "decimal_odds": "1.50",
                "bet_name": "home"
            },
            ...
        ]
        """
        if not odds_data or 'schema' not in odds_data or 'data' not in odds_data:
            return []
        
        schema = odds_data['schema']
        data_rows = odds_data['data']
        
        # Get bookmaker codes from schema (exclude metadata fields)
        excluded_fields = {'bet_name', 'mode_date', 'best_back_decimal', 'best_lay_decimal'}
        bookmaker_codes = [
            field['name'] 
            for field in schema.get('fields', [])
            if field['name'] not in excluded_fields
        ]
        
        # Extract odds for each bookmaker
        transformed_odds = []
        for row in data_rows:
            bet_name = row.get('bet_name', '')
            
            for bookie_code in bookmaker_codes:
                if bookie_code in row and isinstance(row[bookie_code], dict):
                    bookie_data = row[bookie_code]
                    decimal_odds = bookie_data.get('back_decimal')
                    
                    if decimal_odds:
                        # Convert string to float for UI compatibility
                        try:
                            decimal_odds_float = float(decimal_odds)
                        except (ValueError, TypeError):
                            continue  # Skip invalid odds
                        
                        transformed_odds.append({
                            'bookmaker_code': bookie_code,
                            'bookmaker_name': bookie_code.upper(),
                            'decimal_odds': decimal_odds_float,  # Must be a number, not string
                            'selection': bet_name,  # UI expects 'selection' not 'bet_name'
                            'bet_name': bet_name,  # Keep for backward compatibility
                            'clickout_url': bookie_data.get('back_clickout', ''),
                            'fractional_odds': bookie_data.get('back_fractional', ''),
                            'last_decimal': bookie_data.get('last_back_decimal', '0')
                        })
        
        return transformed_odds
    
    async def scrape_once(self) -> Optional[Dict]:
        """Scrape sport once"""
        start = time.time()
        logging.info(f"🔄 {self.sport.upper()}: Starting scrape...")
        
        # Get leagues
        leagues = await self.get_leagues()
        if not leagues:
            logging.warning(f"❌ {self.sport.upper()}: No leagues found")
            return None
        
        top_leagues = self.config.get('top_leagues', 5)
        leagues = leagues[:top_leagues]
        logging.info(f"  ↳ {self.sport}: Found {len(leagues)} leagues")
        
        # Get matches in parallel
        match_tasks = [self.get_matches(league) for league in leagues]
        all_matches_nested = await asyncio.gather(*match_tasks)
        all_matches = [m for matches in all_matches_nested for m in matches if matches]
        
        if not all_matches:
            logging.warning(f"❌ {self.sport.upper()}: No matches found")
            return None
        
        logging.info(f"  ↳ {self.sport}: Found {len(all_matches)} matches")
        
        # Get markets (batched to avoid overwhelming)
        batch_size = 30
        all_markets = []
        for i in range(0, len(all_matches), batch_size):
            batch = all_matches[i:i+batch_size]
            market_tasks = [self.get_markets(match) for match in batch]
            markets_batch = await asyncio.gather(*market_tasks)
            all_markets.extend(markets_batch)
        
        # Count how many matches have markets
        matches_with_markets = sum(1 for m in all_markets if m)
        if matches_with_markets < len(all_matches):
            logging.info(f"  ↳ {self.sport}: {matches_with_markets}/{len(all_matches)} matches have market data")
        
        # Extract odds from priority markets
        markets_to_fetch = self.config.get('markets', ['win market'])
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
        
        logging.info(f"  ↳ {self.sport}: Fetching odds for {len(odds_tasks)} markets...")
        
        # Fetch all odds in parallel (batched)
        batch_size = 40
        all_odds = []
        for i in range(0, len(odds_tasks), batch_size):
            batch = odds_tasks[i:i+batch_size]
            odds_batch = await asyncio.gather(*batch)
            all_odds.extend(odds_batch)
        
        # Build final structure with transformed odds
        # Group by match to combine multiple markets
        matches_map = {}
        for mapping, odds in zip(match_market_mapping, all_odds):
            if not odds:
                continue
            
            match_slug = mapping['match']['match_slug']
            
            # Initialize match if not exists
            if match_slug not in matches_map:
                matches_map[match_slug] = {
                    **mapping['match'],
                    'markets': {}
                }
            
            # Transform odds from Pandas format to UI format
            transformed_odds = self.transform_odds_to_ui_format(odds)
            
            # For tournament events (tennis, boxing), extract player names from odds
            # and populate home_team/away_team if they're currently null
            match_data = matches_map[match_slug]
            if not match_data.get('home_team') and not match_data.get('away_team'):
                # This is a tournament event - extract player names
                players = self.extract_players_from_odds(odds)
                if len(players) >= 2:
                    match_data['home_team'] = players[0]
                    match_data['home'] = players[0]
                    match_data['away_team'] = players[1]
                    match_data['away'] = players[1]
                    logging.debug(f"{self.sport}: Tournament event - extracted players: {players[0]} vs {players[1]}")
                elif len(players) == 1:
                    # Single player (rare case)
                    match_data['home_team'] = players[0]
                    match_data['home'] = players[0]
            
            # Add market to match
            category = mapping['market_category']
            if category not in matches_map[match_slug]['markets']:
                matches_map[match_slug]['markets'][category] = []
            
            matches_map[match_slug]['markets'][category].append({
                'name': mapping['market_name'],
                'url': mapping['market_url'],
                'odds': transformed_odds  # UI-compatible format
            })
        
        final_matches = list(matches_map.values())
        
        # Build output
        result = {
            'sport': self.sport,
            'timestamp': datetime.now().isoformat(),
            'leagues_count': len(leagues),
            'matches_count': len(final_matches),
            'matches': final_matches,
            'scrape_time_seconds': round(time.time() - start, 2)
        }
        
        logging.info(f"✅ {self.sport.upper()}: Scraped {len(final_matches)} matches in {result['scrape_time_seconds']}s")
        
        # Save to file
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        return result
    
    async def run(self):
        """Run scraper once"""
        await self.connect()
        try:
            result = await self.scrape_once()
            return result
        finally:
            await self.disconnect()


async def main(sport: str, config: Dict, mode: str = 'local'):
    """Main entry point for individual sport scraper"""
    scraper = BaseSportScraper(sport, config, mode)
    result = await scraper.run()
    return result


if __name__ == "__main__":
    # Example usage
    import sys
    
    SPORTS_CONFIG = {
        'football': {
            'enabled': True,
            'top_leagues': 10,
            'output': 'oddsmagnet_top10.json',
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
        }
    }
    
    sport = sys.argv[1] if len(sys.argv) > 1 else 'football'
    mode = sys.argv[2] if len(sys.argv) > 2 else 'local'
    
    if sport not in SPORTS_CONFIG:
        print(f"Invalid sport: {sport}")
        sys.exit(1)
    
    asyncio.run(main(sport, SPORTS_CONFIG[sport], mode))
