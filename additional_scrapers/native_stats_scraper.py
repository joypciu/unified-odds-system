#!/usr/bin/env python3
"""
Native-Stats.org Betting Scraper - NO API KEY NEEDED
Scrapes historical and pregame odds with calendar-based date selection
Supports collecting thousands of historical odds with match results
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[ERROR] Selenium not installed. Install with: pip install selenium webdriver-manager")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cache_auto_update_hook import on_data_saved


class NativeStatsScraper:
    """
    Scraper for native-stats.org/betting
    Features:
    - Calendar-based date selection
    - Historical odds data (with results)
    - Pregame odds data
    - No API key required
    """
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.base_url = "https://native-stats.org/betting"
        self.output_file = self.base_dir / "native_stats_odds.json"
        self.driver = None
    
    def init_driver(self):
        """Initialize Selenium WebDriver with stealth settings"""
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
            options.add_argument('--window-size=1920,1080')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Execute CDP commands to hide automation
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("[OK] Initialized Selenium driver")
            return True
        except Exception as e:
            print(f"[ERROR] Driver initialization failed: {e}")
            return False
    
    def navigate_to_date(self, target_date: str):
        """
        Navigate to specific date using calendar
        target_date format: YYYY-MM-DD
        """
        try:
            print(f"    Navigating to date: {target_date}...")
            
            # Wait for page to load
            time.sleep(3)
            
            # Try to find calendar/date selector
            calendar_selectors = [
                "input[type='date']",
                ".date-picker",
                ".calendar-input",
                "[class*='date']",
                "[id*='date']",
                ".datepicker",
                "input[placeholder*='date' i]"
            ]
            
            date_input = None
            for selector in calendar_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        date_input = elements[0]
                        print(f"      Found date input with selector: {selector}")
                        break
                except:
                    continue
            
            if date_input:
                # Clear and set date
                date_input.clear()
                date_input.send_keys(target_date)
                date_input.send_keys(Keys.RETURN)
                time.sleep(2)
                return True
            else:
                print(f"      Calendar not found, using URL params")
                # Try URL parameter approach
                url_with_date = f"{self.base_url}?date={target_date}"
                self.driver.get(url_with_date)
                time.sleep(3)
                return True
                
        except Exception as e:
            print(f"      [ERROR] Failed to navigate to date: {e}")
            return False
    
    def scrape_date(self, target_date: str) -> Optional[Dict]:
        """Scrape odds data for a specific date"""
        if not self.driver:
            if not self.init_driver():
                return None
        
        try:
            # Navigate to the page
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Navigate to specific date
            self.navigate_to_date(target_date)
            
            games = []
            
            # Try multiple selectors for game/match rows
            game_selectors = [
                ".game-row",
                ".match-row",
                ".event-row",
                ".betting-row",
                "tr[class*='game']",
                "tr[class*='match']",
                "div[class*='game']",
                "div[class*='match']",
                "[data-game-id]",
                "[data-match-id]"
            ]
            
            for selector in game_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and len(elements) > 2:
                        print(f"      Found {len(elements)} games with selector: {selector}")
                        
                        for elem in elements:
                            try:
                                text = elem.text.strip()
                                if not text or len(text) < 10:
                                    continue
                                
                                # Try to extract structured data
                                game_data = {
                                    'raw_text': text,
                                    'date': target_date
                                }
                                
                                # Try to find odds (decimal format)
                                import re
                                odds = re.findall(r'\b\d+\.\d{2}\b', text)
                                if odds:
                                    game_data['odds'] = odds
                                
                                # Try to find scores (for historical data)
                                scores = re.findall(r'\b\d+\s*-\s*\d+\b', text)
                                if scores:
                                    game_data['score'] = scores[0]
                                
                                # Try to get data attributes
                                try:
                                    for attr in ['data-game-id', 'data-match-id', 'data-event-id']:
                                        val = elem.get_attribute(attr)
                                        if val:
                                            game_data['game_id'] = val
                                            break
                                except:
                                    pass
                                
                                # Try to extract team names
                                team_elements = elem.find_elements(By.CSS_SELECTOR, "[class*='team'], .team-name, .competitor")
                                if team_elements and len(team_elements) >= 2:
                                    game_data['home_team'] = team_elements[0].text.strip()
                                    game_data['away_team'] = team_elements[1].text.strip()
                                
                                game_data['scraped_at'] = datetime.now().isoformat()
                                games.append(game_data)
                                
                            except Exception as e:
                                continue
                        
                        if games:
                            break  # Found data
                            
                except Exception as e:
                    continue
            
            # Also try table-based extraction
            if not games:
                try:
                    tables = self.driver.find_elements(By.TAG_NAME, 'table')
                    for table in tables:
                        rows = table.find_elements(By.TAG_NAME, 'tr')
                        if len(rows) > 2:
                            print(f"      Found table with {len(rows)} rows")
                            
                            for row in rows[1:]:  # Skip header
                                try:
                                    cells = row.find_elements(By.TAG_NAME, 'td')
                                    if not cells:
                                        cells = row.find_elements(By.TAG_NAME, 'th')
                                    
                                    if cells and len(cells) >= 3:
                                        row_data = []
                                        for cell in cells:
                                            cell_text = cell.text.strip()
                                            if cell_text:
                                                row_data.append(cell_text)
                                        
                                        if row_data:
                                            games.append({
                                                'date': target_date,
                                                'data': row_data,
                                                'scraped_at': datetime.now().isoformat()
                                            })
                                except:
                                    continue
                            
                            if games:
                                break
                except:
                    pass
            
            # If still no data, capture all visible text content
            if not games:
                try:
                    body = self.driver.find_element(By.TAG_NAME, 'body')
                    body_text = body.text
                    
                    # Split into lines and look for betting-related content
                    lines = body_text.split('\n')
                    for i, line in enumerate(lines):
                        if any(keyword in line.lower() for keyword in ['vs', 'v ', '-', 'odds', 'bet']):
                            if len(line) > 15:
                                games.append({
                                    'date': target_date,
                                    'text': line.strip(),
                                    'scraped_at': datetime.now().isoformat()
                                })
                except:
                    pass
            
            if games:
                return {
                    'date': target_date,
                    'games': games,
                    'total_games': len(games),
                    'fetched_at': datetime.now().isoformat()
                }
            else:
                print(f"      No games found for {target_date}")
                return None
            
        except Exception as e:
            print(f"[ERROR] Failed to scrape {target_date}: {e}")
            return None
    
    def scrape_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Scrape multiple dates
        Date format: YYYY-MM-DD
        """
        results = []
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            print(f"  Scraping {date_str}...")
            
            data = self.scrape_date(date_str)
            if data:
                results.append(data)
                print(f"    ✓ Found {len(data['games'])} games")
            else:
                print(f"    ✗ No data")
            
            current += timedelta(days=1)
            time.sleep(2)  # Be polite
        
        return results
    
    def scrape_today(self) -> Optional[Dict]:
        """Scrape today's pregame odds"""
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"[INFO] Scraping today's data: {today}")
        return self.scrape_date(today)
    
    def scrape_historical(self, days_back: int = 7) -> List[Dict]:
        """Scrape historical data (includes results)"""
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=days_back)
        
        print(f"[INFO] Scraping historical data: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        return self.scrape_date_range(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
    
    def close_driver(self):
        """Close Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("[OK] Closed driver")
            except:
                pass
            self.driver = None
    
    def save_data(self, data: List[Dict], data_type: str = 'mixed'):
        """Save to JSON and trigger cache update"""
        output = {
            'metadata': {
                'source': 'native_stats',
                'data_type': data_type,  # 'historical', 'pregame', or 'mixed'
                'generated_at': datetime.now().isoformat(),
                'total_dates': len(data),
                'api_key_required': False
            },
            'dates': data
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Saved to {self.output_file.name}")
        on_data_saved('native_stats', str(self.output_file))
    
    def run_once(self, mode: str = 'today'):
        """
        Run scraper once
        Modes: 'today', 'historical', 'both'
        """
        print("=" * 70)
        print("NATIVE-STATS BETTING SCRAPER - NO API KEY NEEDED")
        print("Historical & Pregame Odds with Calendar-Based Date Selection")
        print("=" * 70)
        print()
        
        all_data = []
        
        if mode in ['today', 'both']:
            print("[INFO] Fetching today's pregame odds...")
            today_data = self.scrape_today()
            if today_data:
                all_data.append(today_data)
        
        if mode in ['historical', 'both']:
            print("\n[INFO] Fetching historical odds (last 7 days)...")
            historical_data = self.scrape_historical(days_back=7)
            all_data.extend(historical_data)
        
        self.close_driver()
        
        if all_data:
            self.save_data(all_data, data_type=mode)
            total_games = sum(d['total_games'] for d in all_data)
            print()
            print(f"✅ Success: {len(all_data)} dates, {total_games} games")
            return True
        else:
            print()
            print("❌ No data collected")
            return False
    
    def run_continuous(self, interval: int = 3600, mode: str = 'today'):
        """Run continuously"""
        print(f"[INFO] Continuous mode (interval: {interval}s, mode: {mode})")
        
        while True:
            try:
                self.run_once(mode=mode)
            except Exception as e:
                print(f"[ERROR] {e}")
                self.close_driver()
            
            print(f"\n[INFO] Waiting {interval}s...")
            time.sleep(interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Native-Stats Betting Scraper')
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous'],
        default='once',
        help='Run mode'
    )
    parser.add_argument(
        '--data-type',
        choices=['today', 'historical', 'both'],
        default='today',
        help='Type of data to scrape'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Interval in seconds for continuous mode (default: 3600)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Specific date to scrape (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--date-range',
        nargs=2,
        metavar=('START', 'END'),
        help='Date range to scrape (YYYY-MM-DD YYYY-MM-DD)'
    )
    
    args = parser.parse_args()
    
    if not SELENIUM_AVAILABLE:
        print("[ERROR] Selenium is required. Install with:")
        print("  pip install selenium webdriver-manager")
        return 1
    
    scraper = NativeStatsScraper()
    
    try:
        # Custom date/range
        if args.date:
            print(f"[INFO] Scraping specific date: {args.date}")
            data = scraper.scrape_date(args.date)
            scraper.close_driver()
            if data:
                scraper.save_data([data], 'custom')
                return 0
            return 1
        
        if args.date_range:
            print(f"[INFO] Scraping date range: {args.date_range[0]} to {args.date_range[1]}")
            data = scraper.scrape_date_range(args.date_range[0], args.date_range[1])
            scraper.close_driver()
            if data:
                scraper.save_data(data, 'custom_range')
                return 0
            return 1
        
        # Standard modes
        if args.mode == 'once':
            return 0 if scraper.run_once(mode=args.data_type) else 1
        else:
            scraper.run_continuous(args.interval, mode=args.data_type)
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
