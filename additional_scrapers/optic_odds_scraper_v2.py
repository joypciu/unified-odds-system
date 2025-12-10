#!/usr/bin/env python3
"""
Optic Odds Scraper V2 - Works with or without API keys
Falls back to web scraping when API key is unavailable
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


class OpticOddsScraperV2:
    """Dual-mode scraper: API OR web scraping fallback"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.api_key = None
        self.base_url = "https://api.opticodds.com/api/v2"
        self.output_file = self.base_dir / "optic_odds.json"
        self.driver = None
        self.api_mode = True
        
        # Load API key
        self.load_api_key()
        
        # Sports mapping
        self.sports = {
            'americanfootball_nfl': 'NFL',
            'basketball_nba': 'NBA',
            'icehockey_nhl': 'NHL',
            'baseball_mlb': 'MLB',
            'soccer_epl': 'EPL',
            'soccer_uefa_champs_league': 'Champions League',
            'tennis_atp': 'ATP Tennis'
        }
    
    def load_api_key(self):
        """Load API key from config"""
        try:
            config_file = self.base_dir.parent / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    optic_config = config.get('optic_odds', {})
                    self.api_key = optic_config.get('api_key')
                    
                if self.api_key:
                    print(f"[OK] Loaded Optic Odds API key")
                else:
                    print("[INFO] No API key - will use web scraping")
                    self.api_mode = False
            else:
                print("[INFO] Config not found - will use web scraping")
                self.api_mode = False
        except Exception as e:
            print(f"[INFO] Config error: {e} - will use web scraping")
            self.api_mode = False
    
    def fetch_odds_api(self, sport_key: str) -> Optional[Dict]:
        """Fetch odds via API"""
        if not self.api_key or not self.api_mode:
            return None
        
        url = f"{self.base_url}/odds"
        params = {
            'apiKey': self.api_key,
            'sport': sport_key,
            'oddsFormat': 'decimal',
            'markets': 'h2h,spreads,totals'
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 401:
                print(f"[WARN] API key expired or invalid")
                self.api_mode = False
                return None
            
            if response.status_code == 429:
                print(f"[WARN] Rate limited")
                return None
            
            if response.status_code == 200:
                return {
                    'sport_key': sport_key,
                    'sport_name': self.sports.get(sport_key, sport_key),
                    'data': response.json(),
                    'method': 'api',
                    'fetched_at': datetime.now().isoformat()
                }
        except Exception as e:
            print(f"[ERROR] API request failed: {e}")
        
        return None
    
    def init_driver(self):
        """Initialize Selenium driver"""
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
    
    def scrape_web(self, sport_name: str) -> Optional[Dict]:
        """Scrape from odds comparison sites (no API key needed)"""
        if not self.init_driver():
            return None
        
        try:
            # Use free odds comparison sites
            urls = [
                f"https://www.oddschecker.com/{sport_name.lower()}",
                f"https://www.oddsportal.com/{sport_name.lower()}",
                f"https://www.flashscore.com/{sport_name.lower()}"
            ]
            
            events = []
            for url in urls:
                try:
                    self.driver.get(url)
                    time.sleep(3)
                    
                    # Generic selectors for odds
                    selectors = [
                        '.match-line',
                        '.event-line',
                        '.game-row',
                        '[class*="match"]',
                        '[class*="event"]'
                    ]
                    
                    for selector in selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            for elem in elements[:20]:
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
                    'sport': sport_name,
                    'events': events,
                    'method': 'web_scraping',
                    'fetched_at': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Web scraping failed for {sport_name}: {e}")
            return None
    
    def fetch_all(self) -> List[Dict]:
        """Fetch using API or web scraping"""
        results = []
        
        # Try API mode first
        if self.api_mode and self.api_key:
            print(f"[INFO] Using API mode")
            for sport_key, sport_name in list(self.sports.items())[:5]:
                print(f"  Fetching {sport_name}...")
                data = self.fetch_odds_api(sport_key)
                if data:
                    results.append(data)
                    matches = len(data.get('data', []))
                    print(f"    ✓ {matches} events")
                else:
                    print(f"    ✗ Failed")
                time.sleep(1)
            
            if not results:
                print("[INFO] API mode failed - switching to web scraping")
                self.api_mode = False
        
        # Web scraping mode
        if not self.api_mode or not results:
            if not SELENIUM_AVAILABLE:
                print("[ERROR] Cannot scrape - Selenium not available")
                print("[INFO] Install with: pip install selenium webdriver-manager")
                return results
            
            print("[INFO] Using web scraping mode (no API key)")
            sports = ['soccer', 'basketball', 'tennis', 'football', 'baseball']
            
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
                'source': 'optic_odds',
                'method': 'api' if self.api_mode else 'web_scraping',
                'generated_at': datetime.now().isoformat(),
                'total_sports': len(data)
            },
            'sports': data
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Saved to {self.output_file.name}")
        on_data_saved('optic_odds', str(self.output_file))
    
    def run_once(self):
        """Run scraper once"""
        print("=" * 70)
        print("OPTIC ODDS SCRAPER V2 - DUAL MODE (API + WEB SCRAPING)")
        print("=" * 70)
        
        data = self.fetch_all()
        
        if data:
            self.save_data(data)
            print(f"\n✅ Success: {len(data)} sports fetched")
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
    parser = argparse.ArgumentParser(description='Optic Odds Scraper V2')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='once')
    parser.add_argument('--interval', type=int, default=300)
    args = parser.parse_args()
    
    scraper = OpticOddsScraperV2()
    
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
