#!/usr/bin/env python3
"""
Sportbex Scraper V2 - Works with or without API keys
Falls back to web scraping when API keys are unavailable or expired
"""

import requests
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
    print("[WARN] Selenium not available - web scraping fallback disabled")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cache_auto_update_hook import on_data_saved


class SportbexScraperV2:
    """Dual-mode scraper: API with key rotation OR web scraping fallback"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.api_keys = []
        self.current_key_index = 0
        self.base_url = "https://trial-api.sportbex.com/api/betfair"
        self.output_file = self.base_dir / "sportbex_odds.json"
        self.driver = None
        self.api_mode = True  # Start with API mode
        
        # Load API keys
        self.load_api_keys()
        
        # Competition mappings
        self.competitions = {
            '1': 'Soccer', '4': 'Cricket', '5': 'Tennis',
            '7': 'Horse Racing', '4339': 'Greyhound Racing',
            '7522': 'Basketball', '6423': 'American Football',
            '7511': 'Baseball', '3988': 'Athletics',
            '998917': 'Volleyball', '468328': 'Handball'
        }
    
    def load_api_keys(self):
        """Load API keys from config - gracefully handle missing config"""
        try:
            config_file = self.base_dir.parent / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    sportbex_config = config.get('sportbex', {})
                    self.api_keys = sportbex_config.get('api_keys', [])
                    
                if self.api_keys:
                    print(f"[OK] Loaded {len(self.api_keys)} API key(s)")
                else:
                    print("[INFO] No API keys in config - will use web scraping")
                    self.api_mode = False
            else:
                print("[INFO] Config not found - will use web scraping")
                self.api_mode = False
        except Exception as e:
            print(f"[INFO] Config error: {e} - will use web scraping")
            self.api_mode = False
    
    def rotate_key(self) -> bool:
        """Rotate to next API key"""
        if len(self.api_keys) <= 1:
            print("[INFO] No more API keys - switching to web scraping")
            self.api_mode = False
            return False
        
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"[INFO] Rotated to key {self.current_key_index + 1}/{len(self.api_keys)}")
        return True
    
    def fetch_competition_api(self, comp_id: str, retries: int = 0) -> Optional[Dict]:
        """Fetch via API with key rotation"""
        if not self.api_keys or not self.api_mode:
            return None
        
        url = f"{self.base_url}/competitions/{comp_id}"
        headers = {'sportbex-api-key': self.api_keys[self.current_key_index]}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code in [401, 403]:
                print(f"[WARN] Key {self.current_key_index + 1} expired")
                if self.rotate_key() and retries < len(self.api_keys):
                    return self.fetch_competition_api(comp_id, retries + 1)
                return None
            
            if response.status_code == 429:
                time.sleep(2)
                return self.fetch_competition_api(comp_id, retries + 1) if retries < 2 else None
            
            if response.status_code == 200:
                return {
                    'competition_id': comp_id,
                    'sport': self.competitions.get(comp_id, 'Unknown'),
                    'data': response.json(),
                    'method': 'api',
                    'fetched_at': datetime.now().isoformat()
                }
        except Exception as e:
            print(f"[ERROR] API request failed: {e}")
        
        return None
    
    def init_driver(self):
        """Initialize Selenium driver for web scraping"""
        if not SELENIUM_AVAILABLE:
            print("[ERROR] Selenium not installed. Install with: pip install selenium webdriver-manager")
            return False
        
        if self.driver:
            return True
        
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            print("[OK] Initialized Selenium driver")
            return True
        except Exception as e:
            print(f"[ERROR] Driver initialization failed: {e}")
            return False
    
    def scrape_web(self, sport: str) -> Optional[Dict]:
        """Scrape Sportbex website directly (no API key needed)"""
        if not self.init_driver():
            return None
        
        try:
            # Try multiple URLs
            urls = [
                f"https://www.sportbex.com/{sport}",
                f"https://sportbex.com/sports/{sport}",
                f"https://www.sportbex.com/sports/{sport}/live"
            ]
            
            events = []
            for url in urls:
                try:
                    self.driver.get(url)
                    time.sleep(3)  # Wait for page load
                    
                    # Try different CSS selectors
                    selectors = [
                        '.event-row',
                        '.match-row',
                        '.game-row',
                        '[data-testid="event-row"]',
                        '.odds-row'
                    ]
                    
                    for selector in selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            for elem in elements[:15]:  # Limit to 15 events
                                try:
                                    text = elem.text
                                    if text and len(text) > 10:
                                        events.append({
                                            'raw_text': text,
                                            'source_url': url,
                                            'scraped_at': datetime.now().isoformat()
                                        })
                                except:
                                    continue
                            
                            if events:
                                break
                    
                    if events:
                        break
                        
                except Exception as e:
                    continue
            
            if events:
                return {
                    'sport': sport,
                    'events': events,
                    'method': 'web_scraping',
                    'fetched_at': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Web scraping failed for {sport}: {e}")
            return None
    
    def fetch_all(self) -> List[Dict]:
        """Fetch using API or web scraping"""
        results = []
        
        # Try API mode first
        if self.api_mode and self.api_keys:
            print(f"[INFO] Using API mode with {len(self.api_keys)} key(s)")
            for comp_id, sport_name in list(self.competitions.items())[:5]:  # Limit to 5
                print(f"  Fetching {sport_name} (ID: {comp_id})...")
                data = self.fetch_competition_api(comp_id)
                if data:
                    results.append(data)
                    print(f"    ✓ Success")
                else:
                    print(f"    ✗ Failed")
                time.sleep(1)
            
            # If API failed for all, switch to web scraping
            if not results:
                print("[INFO] API mode failed - switching to web scraping")
                self.api_mode = False
        
        # Web scraping mode
        if not self.api_mode or not results:
            if not SELENIUM_AVAILABLE:
                print("[ERROR] Cannot scrape - Selenium not available")
                print("[INFO] Install with: pip install selenium webdriver-manager")
                return results
            
            print("[INFO] Using web scraping mode (no API keys)")
            sports = ['soccer', 'cricket', 'tennis', 'basketball', 'football']
            
            for sport in sports:
                print(f"  Scraping {sport}...")
                data = self.scrape_web(sport)
                if data:
                    results.append(data)
                    print(f"    ✓ Found {len(data['events'])} events")
                else:
                    print(f"    ✗ No data")
                time.sleep(2)
            
            self.close_driver()
        
        return results
    
    def close_driver(self):
        """Close Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def save_data(self, data: List[Dict]):
        """Save to JSON and trigger cache update"""
        output = {
            'metadata': {
                'source': 'sportbex',
                'method': 'api' if self.api_mode else 'web_scraping',
                'generated_at': datetime.now().isoformat(),
                'total_competitions': len(data)
            },
            'competitions': data
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Saved to {self.output_file.name}")
        on_data_saved('sportbex', str(self.output_file))
    
    def run_once(self):
        """Run scraper once"""
        print("=" * 70)
        print("SPORTBEX SCRAPER V2 - DUAL MODE (API + WEB SCRAPING)")
        print("=" * 70)
        
        data = self.fetch_all()
        
        if data:
            self.save_data(data)
            print(f"\n✅ Success: {len(data)} competitions fetched")
            return True
        else:
            print("\n❌ Failed: No data collected")
            return False
    
    def run_continuous(self, interval: int = 300):
        """Run continuously"""
        print(f"[INFO] Continuous mode (interval: {interval}s)")
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[ERROR] {e}")
            print(f"\n[INFO] Waiting {interval}s...")
            time.sleep(interval)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sportbex Scraper V2')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once')
    parser.add_argument('--interval', type=int, default=300)
    args = parser.parse_args()
    
    scraper = SportbexScraperV2()
    
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


if __name__ == "__main__":
    sys.exit(main())
