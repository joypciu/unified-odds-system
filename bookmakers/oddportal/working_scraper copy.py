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
        
        try:
            self.browser_process = subprocess.Popen(
                [
                    self.chrome_path,
                    f"--remote-debugging-port={debug_port}",
                    f"--user-data-dir={user_data_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
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
        # Start Chrome with remote debugging
        self.start_chrome_debug()
        
        try:
            # Prepare sport tasks for parallel execution
            sport_tasks = []
            for sport, league_urls in self.leagues.items():
                sport_tasks.append((sport, league_urls))
            
            print(f"\n{'='*80}")
            print(f"STARTING PARALLEL SCRAPING OF {len(sport_tasks)} SPORTS")
            print(f"{'='*80}")
            
            # Use ThreadPoolExecutor to scrape sports concurrently
            with ThreadPoolExecutor(max_workers=len(sport_tasks)) as executor:
                futures = {executor.submit(self.scrape_sport, sport, league_urls): sport for sport, league_urls in sport_tasks}
                
                for future in as_completed(futures):
                    sport = futures[future]
                    try:
                        matches_count = future.result()
                        print(f"\n✓ Completed {sport.upper()}: {matches_count} matches")
                    except Exception as e:
                        print(f"\n✗ Error scraping {sport.upper()}: {str(e)}")
            
            print(f"\n{'='*80}")
            print(f"TOTAL MATCHES SCRAPED: {len(self.matches_data)}")
            print(f"{'='*80}")
        
        finally:
            # Stop Chrome when done
            self.stop_chrome_debug()
    
    def scrape_sport(self, sport: str, league_urls: List[str]) -> int:
        """Scrape all leagues for a single sport."""
        print(f"\n{'#'*80}")
        print(f"SCRAPING {sport.upper()}")
        print(f"{'#'*80}")
        
        matches_count = 0
        
        # Process leagues sequentially but matches in parallel
        for league_url in league_urls:
            matches = self.scrape_league_parallel(league_url, sport)
            matches_count += len(matches)
        
        return matches_count
    
    def scrape_league_parallel(self, league_url: str, sport: str) -> List[Dict]:
        """Scrape a league with parallel match processing."""
        league_name = league_url.strip('/').split('/')[-1]
        country = league_url.strip('/').split('/')[-2]
        
        print(f"\n→ {country.title()} - {league_name.title()}")
        
        # Get match links first
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp('http://localhost:9222')
            context = browser.contexts[0] if browser.contexts else browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            try:
                page.goto(league_url, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(1000)
                
                match_links = []
                all_links = page.query_selector_all('a[href]')
                
                for link in all_links:
                    href = link.get_attribute('href')
                    text = link.inner_text() if link.is_visible() else ''
                    
                    if (href and 
                        f'/{sport}/' in href and 
                        '-' in href and 
                        len(href.split('/')) >= 5 and
                        len(text) > 3 and
                        not any(skip in href for skip in ['bookmaker', 'bonus', 'dropping', 'sure-bets', 
                                                          'inplay', 'manage', 'outrights', 'results', 'table',
                                                          'standings', 'archive', 'fixtures'])):
                        
                        url_parts = href.strip('/').split('/')
                        if len(url_parts) >= 4:
                            last_part = url_parts[-1]
                            if len(last_part) > 10 and last_part[-8:].isalnum():
                                full_url = f"https://www.oddsportal.com{href}" if href.startswith('/') else href
                                if full_url not in [m['url'] for m in match_links]:
                                    match_links.append({
                                        'url': full_url,
                                        'preview_text': text[:100]
                                    })
                
                print(f"  Found {len(match_links)} matches - scraping in parallel...")
                
            finally:
                page.close()
        
        # Scrape matches in parallel
        league_matches = []
        failed_matches = []
        if match_links:
            with ThreadPoolExecutor(max_workers=min(35, len(match_links))) as executor:
                futures = {executor.submit(self.scrape_match_standalone, m['url'], sport, country, league_name): (i, m) for i, m in enumerate(match_links, 1)}
                
                for future in as_completed(futures):
                    idx, match_info = futures[future]
                    try:
                        match_data = future.result()
                        if match_data:
                            league_matches.append(match_data)
                            with self.data_lock:
                                self.matches_data.append(match_data)
                            print(f"  [{idx}/{len(match_links)}] ✓ {match_data['home']} vs {match_data['away']} - {len(match_data['bookmakers'])} bookmakers")
                        else:
                            failed_matches.append(match_info)
                    except Exception as e:
                        failed_matches.append(match_info)
            
            # Retry failed matches with longer timeout
            if failed_matches:
                print(f"  Retrying {len(failed_matches)} failed matches...")
                with ThreadPoolExecutor(max_workers=min(8, len(failed_matches))) as executor:
                    retry_futures = {executor.submit(self.scrape_match_standalone, m['url'], sport, country, league_name, retry=True): m for m in failed_matches}
                    
                    for future in as_completed(retry_futures):
                        try:
                            match_data = future.result()
                            if match_data:
                                league_matches.append(match_data)
                                with self.data_lock:
                                    self.matches_data.append(match_data)
                                print(f"  ✓ Retry success: {match_data['home']} vs {match_data['away']}")
                        except:
                            pass
        
        print(f"\n  ✓ Scraped {len(league_matches)} matches from {league_name}")
        return league_matches
    
    def scrape_match_standalone(self, match_url: str, sport: str, country: str, league: str, retry: bool = False) -> Dict:
        """Scrape a single match with its own browser connection."""
        timeout = 15000 if retry else 8000
        wait_time = 1500 if retry else 800
        
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
            page.goto(match_url, wait_until='domcontentloaded', timeout=8000)
            page.wait_for_timeout(800)
            
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
            
            # Extract match time
            match_time = "Not available"
            try:
                time_elem = page.query_selector('time, .time, [class*="date"]')
                if time_elem:
                    match_time = time_elem.inner_text()
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
        seen_odds = set()  # Track seen odds combinations to avoid duplicates
        
        try:
            # Wait for odds to load
            page.wait_for_timeout(500)
            
            # Click decimal odds if available
            try:
                decimal_tab = page.locator('text=decimal odds').first
                decimal_tab.click(timeout=1500)
                page.wait_for_timeout(200)
            except:
                pass
            
            # Detect if it's a football match (has draw odds)
            page_html = page.content()
            has_draw = 'Draw' in page_html or 'X' in page_html[:5000]
            
            # List of bookmakers to look for (removed Betfair Exchange to avoid duplicates)
            bookmaker_names = ['bet365', '1xBet', 'Pinnacle', 'Betfair', 
                             'Betsson', '888sport', '22Bet', 'Cloudbet', 'Dafabet', 'Betway', 'Unibet']
            
            import re
            
            for bm_name in bookmaker_names:
                try:
                    # Find the bookmaker text element
                    bm_elements = page.locator(f'text="{bm_name}"').all()
                    if not bm_elements:
                        bm_elements = page.locator(f'text={bm_name}').all()
                    
                    if bm_elements:
                        for bm_elem in bm_elements[:1]:  # Take first occurrence
                            try:
                                # Get the parent row/container
                                # Try different parent levels to find the odds container
                                for ancestor_level in range(1, 6):
                                    try:
                                        # Correct xpath syntax: xpath=.. for level 1, xpath=../.. for level 2, etc.
                                        if ancestor_level == 1:
                                            xpath = 'xpath=..'
                                        else:
                                            xpath = 'xpath=..' + '/..' * (ancestor_level - 1)
                                        
                                        parent = bm_elem.locator(xpath).first
                                        parent_html = parent.inner_html()
                                        
                                        # Extract all decimal odds from this parent
                                        # Look for patterns like >2.70< or >3.45<
                                        odds_pattern = r'>(\d{1,2}\.\d{2})<'
                                        odds_matches = re.findall(odds_pattern, parent_html)
                                        
                                        if len(odds_matches) >= 2:
                                            # Filter to valid odds range
                                            valid_odds = []
                                            for odd_str in odds_matches:
                                                try:
                                                    odd_val = float(odd_str)
                                                    if 1.01 <= odd_val <= 100.0:
                                                        valid_odds.append(odd_val)
                                                except:
                                                    pass
                                            
                                            # Remove duplicates while preserving order
                                            unique_odds = []
                                            for odd in valid_odds:
                                                if odd not in unique_odds:
                                                    unique_odds.append(odd)
                                            
                                            if len(unique_odds) >= 2:
                                                bm_data = {
                                                    'name': bm_name,
                                                    'available': True
                                                }
                                                
                                                # For football: home, draw, away (3 odds)
                                                # For other sports: home, away (2 odds only)
                                                if has_draw and len(unique_odds) >= 3:
                                                    bm_data['home_odds'] = unique_odds[0]
                                                    bm_data['draw_odds'] = unique_odds[1]
                                                    bm_data['away_odds'] = unique_odds[2]
                                                    odds_signature = f"{unique_odds[0]}-{unique_odds[1]}-{unique_odds[2]}"
                                                elif len(unique_odds) >= 2:
                                                    # Non-football sports: only take first 2 odds
                                                    bm_data['home_odds'] = unique_odds[0]
                                                    bm_data['away_odds'] = unique_odds[1]
                                                    odds_signature = f"{unique_odds[0]}-{unique_odds[1]}"
                                                else:
                                                    continue
                                                
                                                # Check if we've seen these exact odds before (duplicate detection)
                                                if odds_signature in seen_odds:
                                                    continue
                                                
                                                seen_odds.add(odds_signature)
                                                bookmakers.append(bm_data)
                                                break  # Found odds at this level, stop checking parents
                                                
                                    except:
                                        continue
                                
                            except:
                                continue
                                
                except:
                    continue
            
        except Exception as e:
            pass
        
        return bookmakers
    
    def save_to_json(self, filename='matches_odds_data.json'):
        """Save to JSON."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.matches_data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to {filename}")
    
    def save_to_csv(self, filename='matches_odds_data.csv'):
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
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
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
