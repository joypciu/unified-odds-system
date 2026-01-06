"""
OddsPortal Match & Odds Scraper - Working Version
Scrapes match data and bookmaker odds from OddsPortal for 5 sports.
"""

from playwright.sync_api import sync_playwright
import json
import csv
import time
import re
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import subprocess
import os
import sys


class OddsPortalScraper:
    """Working scraper for OddsPortal."""
    
    def __init__(self):
        self.matches_data = []
        self.data_lock = threading.Lock()  # Thread-safe access to matches_data
        self.browser_process = None
        self.chrome_path = self._find_chrome_path()
        self.last_save_time = 0
        self.save_interval = 2  # Save every 2 seconds
        self.auto_save_active = True
        self.sport_complete_callback = None  # Callback when sport completes
        self.max_matches_per_league = 15  # Limit to recent matches for faster loading
        
        # Popular leagues that are active
        self.leagues = {
            'football': [
                'https://www.oddsportal.com/football/england/premier-league/',
                'https://www.oddsportal.com/football/spain/laliga/',
                'https://www.oddsportal.com/football/germany/bundesliga/',
                'https://www.oddsportal.com/football/italy/serie-a/',
            ],
            'basketball': [
                'https://www.oddsportal.com/basketball/usa/nba/',
                'https://www.oddsportal.com/basketball/europe/euroleague/',
            ],
            'tennis': [
                'https://www.oddsportal.com/tennis/',
            ],
            'hockey': [
                'https://www.oddsportal.com/hockey/usa/nhl/',
            ],
            'baseball': [
                'https://www.oddsportal.com/baseball/usa/mlb/',
            ],
        }
    
    def auto_save_worker(self):
        """Background worker that saves data every 2 seconds."""
        while self.auto_save_active:
            time.sleep(self.save_interval)
            try:
                if len(self.matches_data) > 0:
                    current_time = time.time()
                    if current_time - self.last_save_time >= self.save_interval:
                        self.save_to_json(silent=True)
                        self.save_to_csv(silent=True)
                        self.last_save_time = current_time
                        print(f"\r[AUTO-SAVE] Saved {len(self.matches_data)} matches at {datetime.now().strftime('%H:%M:%S')}        ", end='', flush=True)
            except Exception as e:
                pass  # Ignore save errors in background thread
    
    def _find_chrome_path(self):
        """Find Chrome or Opera executable path."""
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Opera\launcher.exe",
            r"C:\Program Files (x86)\Opera\launcher.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If not found, try to get from environment
        return "chrome.exe"  # Fallback to PATH
    
    def start_chrome_debug(self):
        """Start Chrome with remote debugging enabled."""
        if self.browser_process:
            return  # Already started
        
        debug_port = 9222
        user_data_dir = os.path.join(os.environ.get('TEMP', '/tmp'), 'chrome-debug-scraper')
        
        print(f"\nStarting Chrome with remote debugging on port {debug_port}...")
        print(f"Chrome path: {self.chrome_path}")
        
        # Kill any existing Chrome processes on the debug port
        try:
            import psutil
            print("🧹 Cleaning up any existing Chrome processes...")
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and any('remote-debugging-port' in str(arg) for arg in cmdline):
                            proc.kill()
                            killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if killed_count > 0:
                print(f"🧹 Killed {killed_count} Chrome processes")
                time.sleep(2)  # Wait for cleanup
        except ImportError:
            print("⚠️  psutil not installed - skipping Chrome cleanup")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
        
        try:
            self.browser_process = subprocess.Popen(
                [
                    self.chrome_path,
                    f"--remote-debugging-port={debug_port}",
                    f"--user-data-dir={user_data_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-gpu",
                    "--headless=new",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for Chrome to start
            print("Waiting for Chrome to start...")
            time.sleep(3)
            print("✓ Chrome started with remote debugging\n")
            
        except Exception as e:
            print(f"✗ Error starting Chrome: {e}")
            print("Please start Chrome manually with: chrome.exe --remote-debugging-port=9222")
            sys.exit(1)
    
    def stop_chrome_debug(self):
        """Stop the Chrome debug process."""
        if self.browser_process:
            try:
                self.browser_process.terminate()
                self.browser_process.wait(timeout=5)
                print("\n✓ Chrome closed")
            except:
                self.browser_process.kill()
    
    def scrape_all(self):
        """Scrape all configured leagues in parallel."""
        # Start auto-save background thread
        auto_save_thread = threading.Thread(target=self.auto_save_worker, daemon=True)
        auto_save_thread.start()
        print("\n✓ Auto-save enabled (updates every 2 seconds)\n")
        
        try:
            # Prepare sport tasks for parallel execution
            sport_tasks = []
            for sport, league_urls in self.leagues.items():
                sport_tasks.append((sport, league_urls))
            
            print(f"\n{'='*80}")
            print(f"STARTING PARALLEL SCRAPING OF {len(sport_tasks)} SPORTS")
            print(f"Each sport gets its own isolated browser for maximum speed")
            print(f"{'='*80}")
            
            # Use ThreadPoolExecutor to scrape sports concurrently
            # Each sport will create its own browser instance
            with ThreadPoolExecutor(max_workers=len(sport_tasks)) as executor:
                futures = {executor.submit(self.scrape_sport, sport, league_urls): sport for sport, league_urls in sport_tasks}
                
                for future in as_completed(futures):
                    sport = futures[future]
                    try:
                        matches_count = future.result()
                        print(f"\n✓ Completed {sport.upper()}: {matches_count} matches")
                        
                        # Trigger callback for progressive updates
                        if self.sport_complete_callback:
                            try:
                                self.sport_complete_callback(sport, self.matches_data.copy())
                            except Exception as cb_err:
                                print(f"Warning: Callback error for {sport}: {cb_err}")
                    except Exception as e:
                        print(f"\n✗ Error scraping {sport.upper()}: {str(e)}")
            
            print(f"\n{'='*80}")
            print(f"TOTAL MATCHES SCRAPED: {len(self.matches_data)}")
            print(f"{'='*80}")
        
        finally:
            # Stop auto-save thread
            self.auto_save_active = False
            time.sleep(0.5)
            
            # Final save
            print("\n\nPerforming final save...")
            self.save_to_json()
            self.save_to_csv()
    
    def scrape_sport(self, sport: str, league_urls: List[str]) -> int:
        """Scrape all leagues for a single sport with dedicated browser."""
        print(f"\n{'#'*80}")
        print(f"SCRAPING {sport.upper()} - Dedicated Browser Context")
        print(f"{'#'*80}")
        
        matches_count = 0
        
        # Create dedicated browser instance for this sport (isolated, no shared Chrome)
        with sync_playwright() as p:
            try:
                # Launch isolated system Chrome browser (better anti-detection)
                print(f"[{sport.upper()}] Launching isolated browser...")
                
                # Uses system Chrome installation for better anti-detection
                browser = p.chromium.launch(
                    headless=False,  # Use headed mode - OddPortal blocks headless
                    channel='chrome',  # Use system Chrome
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-infobars',
                        '--window-position=-2400,-2400'  # Hide off-screen
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                    },
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                print(f"[{sport.upper()}] Browser context created")
                
                # Process leagues sequentially but matches in parallel
                for league_url in league_urls:
                    matches = self.scrape_league_parallel(context, league_url, sport)
                    matches_count += len(matches)
                
                context.close()
                browser.close()
                print(f"[{sport.upper()}] Browser closed")
            except Exception as e:
                print(f"[{sport.upper()}] Browser error: {str(e)}")
        
        return matches_count
    
    def scrape_league_parallel(self, context, league_url: str, sport: str) -> List[Dict]:
        """Scrape a league with parallel match processing."""
        league_name = league_url.strip('/').split('/')[-1]
        country = league_url.strip('/').split('/')[-2]
        
        print(f"\n→ {country.title()} - {league_name.title()}")
        
        # Get match links using provided context
        page = context.new_page()
        
        
        try:
            page.goto(league_url, wait_until='domcontentloaded', timeout=45000)
            # Wait longer for dynamic content to load
            page.wait_for_timeout(2000)
            
            # Try to wait for match links to appear
            try:
                page.wait_for_selector('a[href*="/football/"], a[href*="/basketball/"], a[href*="/tennis/"], a[href*="/hockey/"], a[href*="/baseball/"]', timeout=3000)
            except:
                print(f"  ⚠️  No match links found with selector, trying all links...")
            
            match_links = []
            all_links = page.query_selector_all('a[href]')
            print(f"  📊 Found {len(all_links)} total links on page")
            
            for link in all_links:
                href = link.get_attribute('href')
                
                # Match valid game URLs: /sport/country/league/team1-team2-MATCHID/
                if (href and 
                    f'/{sport}/' in href and 
                    '-' in href and 
                    len(href.split('/')) >= 5 and
                    not any(skip in href for skip in ['bookmaker', 'bonus', 'dropping', 'sure-bets', 
                                                      'inplay', 'manage', 'outrights', 'results', 'table',
                                                      'standings', 'archive', 'fixtures', 'next-matches'])):
                    
                    url_parts = href.strip('/').split('/')
                    if len(url_parts) >= 4:
                        last_part = url_parts[-1]
                        # Match IDs are alphanumeric strings (like IJV01CBb, Ovaio0L0)
                        # Team names contain hyphens, match ID is after last hyphen
                        if len(last_part) > 5 and any(c.isalpha() for c in last_part) and any(c.isdigit() or c.isupper() for c in last_part[-8:]):
                            full_url = f"https://www.oddsportal.com{href}" if href.startswith('/') else href
                            if full_url not in [m['url'] for m in match_links]:
                                # Extract team names from URL for preview
                                try:
                                    match_name = url_parts[-1].rsplit('-', 1)[0].replace('-', ' vs ')
                                except:
                                    match_name = last_part
                                    
                                match_links.append({
                                    'url': full_url,
                                    'preview_text': match_name
                                })  
            
            # Debug: Show what we found
            if len(match_links) == 0:
                print(f"  ❌ No match links detected - page might not have loaded properly")
                # Try to get page title to verify page loaded
                try:
                    page_title = page.title()
                    print(f"  📄 Page title: {page_title[:100]}")
                except:
                    pass
            
            # Limit to most recent matches for faster loading
            if self.max_matches_per_league and len(match_links) > self.max_matches_per_league:
                original_count = len(match_links)
                match_links = match_links[:self.max_matches_per_league]
                print(f"  ✂️  Limited from {original_count} to {self.max_matches_per_league} most recent matches")
            
            if len(match_links) > 0:
                print(f"  ✓ Found {len(match_links)} matches - scraping in parallel...")
            else:
                print(f"  ⚠️  0 matches found - skipping this league")
            
        finally:
            page.close()
        
        # Scrape matches sequentially (Playwright sync API is not thread-safe)
        league_matches = []
        if match_links:
            for i, match_info in enumerate(match_links, 1):
                try:
                    # Add small delay to avoid browser resource exhaustion
                    if i > 1:
                        time.sleep(0.5)
                    
                    match_data = self.scrape_match(context, match_info['url'], sport, country, league_name)
                    if match_data:
                        league_matches.append(match_data)
                        with self.data_lock:
                            self.matches_data.append(match_data)
                        print(f"  [{i}/{len(match_links)}] ✓ {match_data['home']} vs {match_data['away']} - {len(match_data['bookmakers'])} bookmakers")
                    else:
                        print(f"  [{i}/{len(match_links)}] ✗ Failed to scrape {match_info['url']}")
                except Exception as e:
                    print(f"  [{i}/{len(match_links)}] ✗ Error: {str(e)[:50]}")
        
        print(f"\n  ✓ Scraped {len(league_matches)} matches from {league_name}")
        return league_matches
    
    def scrape_match_standalone(self, match_url: str, sport: str, country: str, league: str, retry: bool = False, final_attempt: bool = False) -> Dict:
        """Scrape a single match with its own browser connection."""
        if final_attempt:
            timeout = 20000
            wait_time = 2000
        elif retry:
            timeout = 15000
            wait_time = 1500
        else:
            timeout = 8000
            wait_time = 800
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp('http://localhost:9222')
                context = browser.contexts[0] if browser.contexts else browser.new_context(
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()
                
                try:
                    page.goto(match_url, wait_until='domcontentloaded', timeout=timeout)
                    page.wait_for_timeout(wait_time)
                    
                    return self._extract_match_data(page, match_url, sport, country, league)
                finally:
                    page.close()
            except Exception as e:
                return None
    
    def scrape_match(self, context, match_url: str, sport: str, country: str, league: str) -> Dict:
        """Scrape individual match page."""
        page = context.new_page()
        
        try:
            page.goto(match_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)  # Wait longer for dynamic content
            
            return self._extract_match_data(page, match_url, sport, country, league)
            
        except Exception as e:
            return None
        
        finally:
            page.close()
    
    def _extract_match_data(self, page, match_url: str, sport: str, country: str, league: str) -> Dict:
        """Extract match data from page."""
        try:
            home_team = "Unknown"
            away_team = "Unknown"
            
            try:
                title = page.title()
                # Title format: "Team A - Team B Odds, Predictions and H2H | OddsPortal"
                if ' - ' in title:
                    # Split by ' - ' and clean up
                    parts = title.split(' - ')
                    if len(parts) >= 2:
                        home_team = parts[0].strip()
                        # Remove everything after "Odds" from away team
                        away_part = parts[1].split('Odds')[0].strip()
                        if away_part:
                            away_team = away_part
            except:
                pass
            
            # If still unknown, try h1
            if home_team == "Unknown" or away_team == "Unknown":
                try:
                    h1 = page.query_selector('h1')
                    if h1:
                        h1_text = h1.inner_text()
                        if ' - ' in h1_text:
                            parts = h1_text.split(' - ')
                            if len(parts) >= 2:
                                home_team = parts[0].strip()
                                away_team = parts[1].strip()
                except:
                    pass
            
            # Last resort: extract from URL
            if home_team == "Unknown" or away_team == "Unknown":
                url_parts = match_url.strip('/').split('/')
                match_slug = url_parts[-1] if len(url_parts) > 0 else ''
                
                # Teams are in the slug: team1-team2-ID
                # Remove ID (last 8 chars after dash)
                teams_part = '-'.join(match_slug.split('-')[:-1])
                teams = teams_part.split('-')
                
                # Split teams (usually middle point)
                mid = len(teams) // 2
                home_team = ' '.join(teams[:mid]).title()
                away_team = ' '.join(teams[mid:]).title()
            
            # Extract match time/date
            match_time = "Not available"
            try:
                # Try multiple selectors for date
                date_selectors = [
                    'p:has-text("Jan")', 'p:has-text("Feb")', 'p:has-text("Mar")', 
                    'p:has-text("Apr")', 'p:has-text("May")', 'p:has-text("Jun")',
                    'p:has-text("Jul")', 'p:has-text("Aug")', 'p:has-text("Sep")',
                    'p:has-text("Oct")', 'p:has-text("Nov")', 'p:has-text("Dec")',
                    'time', '[datetime]'
                ]
                
                for selector in date_selectors:
                    try:
                        elem = page.query_selector(selector)
                        if elem:
                            text = elem.inner_text().strip()
                            # Check if it looks like a date (contains year or month)
                            if '202' in text or any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                                match_time = text
                                break
                    except:
                        continue
            except:
                pass
            
            # Extract bookmakers and odds
            bookmakers = self.extract_bookmakers_and_odds(page)
            
            # Skip non-match pages
            if not bookmakers and (home_team == "Unknown" or away_team == "Unknown"):
                return None
            
            match_data = {
                'url': match_url,
                'sport': sport,
                'country': country,
                'league': league,
                'home': home_team,
                'away': away_team,
                'match_time': match_time,
                'scraped_at': datetime.now().isoformat(),
                'bookmakers': bookmakers
            }
            
            return match_data
            
        except Exception as e:
            return None
    
    def extract_bookmakers_and_odds(self, page) -> List[Dict]:
        """Extract bookmaker names and their specific odds from match page."""
        bookmakers = []
        seen_bookmakers = set()  # Track seen bookmakers to avoid duplicates
        
        try:
            # Wait for content to load
            page.wait_for_timeout(2000)
            
            # CRITICAL: Click to expand odds table if not already expanded
            # Some matches have hidden odds by default
            try:
                # Try clicking "Decimal Odds" button or any odds format button
                decimal_btn = page.locator('button:has-text("Decimal")').first
                if decimal_btn:
                    decimal_btn.click(timeout=2000)
                    page.wait_for_timeout(1000)
            except:
                # If decimal button not found, try other odds format buttons
                try:
                    odds_btn = page.locator('button:has-text("Odds")').first
                    if odds_btn:
                        odds_btn.click(timeout=2000)
                        page.wait_for_timeout(1000)
                except:
                    pass
            
            # Find all rows with bookmaker data (based on actual HTML structure)
            # Each row has: div with img[alt="BookmakerName"] and p.odds-text elements
            try:
                # Target the specific row structure from OddPortal
                rows = page.locator('div[data-testid*="expanded-row"], div[provider-name]').all()
                
                for row in rows:
                    try:
                        # Get bookmaker name from img alt
                        img_elem = row.locator('img.bookmaker-logo, img[alt][title]').first
                        if not img_elem:
                            continue
                        
                        bm_name = img_elem.get_attribute('alt') or img_elem.get_attribute('title')
                        
                        # Skip invalid names
                        if not bm_name or bm_name in ['img', ''] or bm_name in seen_bookmakers:
                            continue
                        
                        # Extract odds - OddsPortal uses 'a.odds-link' elements
                        odds_elements = row.locator('a.odds-link, p.odds-text, p[class*="odds-text"]').all()
                        odds_values = []
                        
                        for odd_elem in odds_elements:
                            try:
                                text = odd_elem.inner_text().strip()
                                # Clean text and extract number
                                text = re.sub(r'[^\d.]', '', text)
                                if text and '.' in text:
                                    odd_float = float(text)
                                    if 1.0 <= odd_float <= 100.0:
                                        odds_values.append(odd_float)
                            except:
                                pass
                        
                        # Need at least 2 odds
                        if len(odds_values) >= 2:
                            seen_bookmakers.add(bm_name)
                            
                            bookmaker_data = {
                                'name': bm_name,
                                'available': True
                            }
                            
                            # Assign odds
                            if len(odds_values) >= 3:
                                bookmaker_data['home_odds'] = odds_values[0]
                                bookmaker_data['draw_odds'] = odds_values[1]
                                bookmaker_data['away_odds'] = odds_values[2]
                            else:
                                bookmaker_data['home_odds'] = odds_values[0]
                                bookmaker_data['away_odds'] = odds_values[1]
                            
                            bookmakers.append(bookmaker_data)
                            
                    except:
                        continue
                        
            except Exception as e:
                pass
        
        except Exception as e:
            pass
        
        return bookmakers
    
    def save_to_json(self, filename='matches_odds_data.json', silent=False):
        """Save to JSON."""
        with self.data_lock:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.matches_data, f, indent=2, ensure_ascii=False)
        if not silent:
            print(f"\n✓ Saved to {filename}")
    
    def save_to_csv(self, filename='matches_odds_data.csv', silent=False):
        """Save to CSV."""
        if not self.matches_data:
            return
        
        rows = []
        for match in self.matches_data:
            # Create one row per bookmaker
            if match['bookmakers']:
                for bm in match['bookmakers']:
                    row = {
                        'sport': match['sport'],
                        'country': match['country'],
                        'league': match['league'],
                        'home': match['home'],
                        'away': match['away'],
                        'match_time': match['match_time'],
                        'bookmaker': bm['name'],
                        'home_odds': bm.get('home_odds', ''),
                        'draw_odds': bm.get('draw_odds', ''),
                        'away_odds': bm.get('away_odds', ''),
                        'url': match['url'],
                        'scraped_at': match['scraped_at'],
                    }
                    rows.append(row)
            else:
                # Match with no bookmakers
                row = {
                    'sport': match['sport'],
                    'country': match['country'],
                    'league': match['league'],
                    'home': match['home'],
                    'away': match['away'],
                    'match_time': match['match_time'],
                    'bookmaker': '',
                    'home_odds': '',
                    'draw_odds': '',
                    'away_odds': '',
                    'url': match['url'],
                    'scraped_at': match['scraped_at'],
                }
                rows.append(row)
        
        fieldnames = ['sport', 'country', 'league', 'home', 'away', 'match_time', 
                     'bookmaker', 'home_odds', 'draw_odds', 'away_odds', 'url', 'scraped_at']
        
        with self.data_lock:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        if not silent:
            print(f"✓ Saved to {filename}")
    
    def print_summary(self):
        """Print summary."""
        if not self.matches_data:
            print("No data scraped")
            return
        
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        # By sport
        sport_counts = {}
        for match in self.matches_data:
            sport = match['sport']
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
        
        print("\nMatches by Sport:")
        for sport, count in sorted(sport_counts.items()):
            print(f"  {sport.title()}: {count}")
        
        # Bookmakers
        all_bookmakers = set()
        for match in self.matches_data:
            for bm in match['bookmakers']:
                all_bookmakers.add(bm['name'])
        
        print(f"\nUnique Bookmakers Found: {len(all_bookmakers)}")
        print(f"Bookmakers: {', '.join(sorted(all_bookmakers))}")


def main():
    print("="*80)
    print("ODDSPORTAL SCRAPER - Working Version")
    print("="*80)
    
    start_time = time.time()
    
    scraper = OddsPortalScraper()
    scraper.scrape_all()
    
    # Print summary
    scraper.print_summary()
    
    # Save data
    scraper.save_to_json()
    scraper.save_to_csv()
    
    elapsed = time.time() - start_time
    print(f"\n✓ Completed in {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
