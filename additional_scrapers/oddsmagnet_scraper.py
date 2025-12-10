#!/usr/bin/env python3
"""
OddsMagnet Web Scraper - NO API KEY NEEDED
Scrapes odds data directly from oddsmagnet.com website
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[ERROR] Selenium not installed. Install with: pip install selenium webdriver-manager")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cache_auto_update_hook import on_data_saved


class OddsMagnetScraper:
    """Web scraper for oddsmagnet.com - completely free, no API needed"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.base_url = "https://oddsmagnet.com"
        self.output_file = self.base_dir / "oddsmagnet_odds.json"
        self.driver = None
        
        # Sports available on oddsmagnet
        self.sports = {
            'football': 'Football',
            'horse-racing': 'Horse Racing',
            'tennis': 'Tennis',
            'cricket': 'Cricket',
            'basketball': 'Basketball',
            'american-football': 'American Football',
            'ice-hockey': 'Ice Hockey',
            'rugby-union': 'Rugby Union',
            'boxing': 'Boxing',
            'darts': 'Darts',
            'snooker': 'Snooker',
            'volleyball': 'Volleyball',
            'handball': 'Handball',
            'table-tennis': 'Table Tennis',
            'motorsport': 'Motorsport',
            'greyhounds': 'Greyhounds',
            'esports': 'Esports'
        }
    
    def init_driver(self):
        """Initialize Selenium WebDriver"""
        if self.driver:
            return True
        
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Execute script to hide automation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("[OK] Initialized Selenium driver")
            return True
        except Exception as e:
            print(f"[ERROR] Driver initialization failed: {e}")
            return False
    
    def extract_match_urls(self, sport_slug: str) -> List[str]:
        """Extract match URLs from sport page"""
        match_urls = []
        
        try:
            url = f"{self.base_url}/{sport_slug}"
            print(f"    Accessing {url}...")
            
            self.driver.get(url)
            
            # Wait longer for dynamic content
            time.sleep(5)
            
            # Scroll to load lazy content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            # Try to find all links on the page
            all_links = self.driver.find_elements(By.TAG_NAME, 'a')
            
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if href and sport_slug in href:
                        # Get the match-specific URLs (with team names in path)
                        # Skip: win-market, odds-movement, etc.
                        path_parts = href.split('/')
                        
                        if len(path_parts) >= 5:  # Has sport/league/match structure
                            if not any(x in href for x in ['/win-market', '/odds-movement', '/api/', '#']):
                                if href not in match_urls:
                                    match_urls.append(href)
                except:
                    continue
            
            print(f"      Found {len(match_urls)} match URLs")
            
        except Exception as e:
            print(f"      [ERROR] Failed to extract match URLs: {e}")
        
        return match_urls[:10]  # Limit to 10 matches
    
    def scrape_match(self, match_url: str) -> Optional[Dict]:
        """Scrape odds for a specific match"""
        try:
            print(f"      Scraping {match_url}...")
            self.driver.get(match_url)
            time.sleep(3)
            
            match_data = {
                'url': match_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract match title/teams
            title_selectors = ['h1', '.match-title', '.event-title', 'title']
            for selector in title_selectors:
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if title_elem:
                        match_data['match_title'] = title_elem.text.strip()
                        break
                except:
                    continue
            
            # Extract odds from tables
            odds_data = []
            try:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                
                for table in tables:
                    rows = table.find_elements(By.TAG_NAME, 'tr')
                    
                    for row in rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if not cells:
                                cells = row.find_elements(By.TAG_NAME, 'th')
                            
                            if cells and len(cells) >= 2:
                                row_data = []
                                for cell in cells:
                                    cell_text = cell.text.strip()
                                    if cell_text:
                                        row_data.append(cell_text)
                                
                                if row_data and len(row_data) >= 2:
                                    # Look for odds (decimal format)
                                    import re
                                    has_odds = any(re.match(r'\d+\.\d{2}', item) for item in row_data)
                                    
                                    if has_odds:
                                        odds_data.append(row_data)
                        except:
                            continue
            except:
                pass
            
            if odds_data:
                match_data['odds'] = odds_data
            
            # Try to get win-market specific data
            win_market_url = match_url.rstrip('/') + '/win-market'
            try:
                self.driver.get(win_market_url)
                time.sleep(2)
                
                win_odds = []
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                
                for table in tables[:2]:  # First 2 tables
                    rows = table.find_elements(By.TAG_NAME, 'tr')
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, 'td')
                        if cells and len(cells) >= 3:
                            row_text = [cell.text.strip() for cell in cells if cell.text.strip()]
                            if row_text:
                                win_odds.append(row_text)
                
                if win_odds:
                    match_data['win_market'] = win_odds
            except:
                pass
            
            return match_data if ('odds' in match_data or 'win_market' in match_data) else None
            
        except Exception as e:
            print(f"        [ERROR] Failed to scrape match: {e}")
            return None
    
    def scrape_sport(self, sport_slug: str, sport_name: str) -> Optional[Dict]:
        """Scrape odds for a specific sport"""
        if not self.driver:
            if not self.init_driver():
                return None
        
        try:
            # Step 1: Get match URLs from sport page
            match_urls = self.extract_match_urls(sport_slug)
            
            if not match_urls:
                print(f"      No matches found for {sport_name}")
                return None
            
            # Step 2: Scrape each match
            events = []
            
            for match_url in match_urls:
                match_data = self.scrape_match(match_url)
                if match_data:
                    events.append(match_data)
                time.sleep(1)  # Be polite
            
            if events:
                return {
                    'sport': sport_name,
                    'sport_slug': sport_slug,
                    'base_url': f"{self.base_url}/{sport_slug}",
                    'events': events,
                    'total_events': len(events),
                    'fetched_at': datetime.now().isoformat()
                }
            else:
                print(f"      No events found for {sport_name}")
                return None
            
        except Exception as e:
            print(f"[ERROR] Failed to scrape {sport_name}: {e}")
            return None
    
    def fetch_all_sports(self) -> List[Dict]:
        """Scrape all configured sports"""
        results = []
        
        print(f"[INFO] Scraping {len(self.sports)} sports from OddsMagnet...")
        
        for sport_slug, sport_name in list(self.sports.items())[:8]:  # Limit to 8 sports
            print(f"  Scraping {sport_name}...")
            data = self.scrape_sport(sport_slug, sport_name)
            
            if data:
                results.append(data)
                print(f"    ✓ Found {len(data['events'])} events")
            else:
                print(f"    ✗ No data")
            
            time.sleep(2)  # Be polite
        
        return results
    
    def close_driver(self):
        """Close Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("[OK] Closed driver")
            except:
                pass
            self.driver = None
    
    def save_data(self, data: List[Dict]):
        """Save to JSON and trigger cache update"""
        output = {
            'metadata': {
                'source': 'oddsmagnet',
                'method': 'web_scraping',
                'generated_at': datetime.now().isoformat(),
                'total_sports': len(data),
                'api_key_required': False
            },
            'sports': data
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Saved to {self.output_file.name}")
        on_data_saved('oddsmagnet', str(self.output_file))
    
    def run_once(self):
        """Run scraper once"""
        print("=" * 70)
        print("ODDSMAGNET SCRAPER - NO API KEY NEEDED")
        print("=" * 70)
        print()
        
        data = self.fetch_all_sports()
        
        self.close_driver()
        
        if data:
            self.save_data(data)
            print()
            print(f"✅ Success: {len(data)} sports scraped")
            return True
        else:
            print()
            print("❌ No data collected")
            return False
    
    def run_continuous(self, interval: int = 600):
        """Run continuously"""
        print(f"[INFO] Continuous mode (interval: {interval}s)")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[ERROR] {e}")
                self.close_driver()
            
            print(f"\n[INFO] Waiting {interval}s...")
            time.sleep(interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='OddsMagnet Web Scraper')
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous'],
        default='once',
        help='Run mode'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=600,
        help='Interval in seconds for continuous mode (default: 600)'
    )
    
    args = parser.parse_args()
    
    if not SELENIUM_AVAILABLE:
        print("[ERROR] Selenium is required. Install with:")
        print("  pip install selenium webdriver-manager")
        return 1
    
    scraper = OddsMagnetScraper()
    
    try:
        if args.mode == 'once':
            return 0 if scraper.run_once() else 1
        else:
            scraper.run_continuous(args.interval)
            return 0
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
        scraper.close_driver()
        return 0
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        scraper.close_driver()
        return 1


if __name__ == "__main__":
    sys.exit(main())
