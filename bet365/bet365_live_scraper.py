#!/usr/bin/env python3
"""
ULTIMATE INTELLIGENT LIVE BET365 SCRAPER
Enhanced with comprehensive extraction script supporting all sports including:
- Cricket (horizontal markets)
- Sets-based sports (Badminton, Volleyball, Table Tennis)
- Standard sports (Basketball, Baseball, Soccer, NFL, etc.)
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import time
import psutil
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from patchright.async_api import async_playwright
import hashlib

# Import dashboard broadcasting functions
try:
    from dashboard.live_dashboard import broadcast_to_dashboard, broadcast_status_to_dashboard
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    async def broadcast_to_dashboard(data):
        pass
    async def broadcast_status_to_dashboard(status, message=""):
        pass
    print("Warning: Dashboard not available. Install FastAPI and uvicorn for live UI support.")

class UltimateLiveScraper:
    """
    Advanced live betting data scraper for bet365.ca with comprehensive sport support.
    
    Features:
    - Comprehensive extraction for all sports
    - Cricket horizontal market support
    - Sets-based scoring (Badminton, Volleyball, Table Tennis)
    - Standard market structures
    - Live scores, status, and time tracking
    """

    # Updated BET365 odds layout matching bet365_odds_structure.py
    BET365_ODDS_LAYOUT = {
        # Sports with Spread, Total, Money columns
        'B151': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'Esports'},
        'B16': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'Baseball'},
        'B18': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'Basketball'},
        'B21': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'NFL'},
        'B12': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'American Football'},
        'B17': {'columns': ['spread', 'total', 'moneyline'], 'sport': 'NHL'},
        
        # Soccer: Home, Tie, Away
        'B1': {'columns': ['home', 'tie', 'away'], 'sport': 'Soccer'},
        
        # Two-way markets
        'B13': {'columns': ['player1', 'player2'], 'sport': 'Tennis'},
        'B3': {'columns': ['team1', 'draw', 'team2'], 'sport': 'Cricket', 'uses_horizontal_market': True},
        
        # Sets-based sports
        'B91': {'columns': ['match', 'set', 'set_total'], 'sport': 'Volleyball', 'uses_sets': True},
        'B92': {'columns': ['moneyline', 'game', 'game_total'], 'sport': 'Table Tennis', 'uses_sets': True},
        'B94': {'columns': ['moneyline', 'game', 'game_total'], 'sport': 'Badminton', 'uses_sets': True},
        
        # Other sports
        'B78': {'columns': ['spread', 'total', 'tie_no_bet'], 'sport': 'Handball'},
        'B1002': {'columns': ['spread', 'total', 'tie_no_bet'], 'sport': 'Futsal'},
    }

    def __init__(self, disable_broadcasting=False):
        """Initialize the Ultimate Live Scraper"""
        self.disable_broadcasting = disable_broadcasting
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # File paths - save to parent folder with clear bet365 naming
        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
        self.current_data_file = os.path.join(parent_dir, "bet365_live_current.json")
        self.history_data_file = os.path.join(parent_dir, "bet365_live_history.json")
        self.statistics_file = os.path.join(parent_dir, "bet365_live_statistics.json")

        self.setup_logging()
        
        # Load hierarchical cache for team name normalization
        self.load_hierarchical_cache()

        # Browser connection
        self.debug_port = 9222
        self.browser_process = None
        self.page = None
        self.isolated_profile_dir = None
        self.playwright_instance = None
        self.browser_instance = None

        # Tracking systems
        self.selector_database = self.load_selector_database()
        self.current_matches = {}
        self.match_history = self.load_match_history()
        self.data_changes_log = []
        
        # Session tracking
        self.session_start_time = datetime.now().isoformat()
        self.extraction_count = 0

        # Sport mappings for navigation
        self.sport_mappings = {
            'B1': {'name': 'Soccer', 'url_suffix': 'B1'},
            'B3': {'name': 'Cricket', 'url_suffix': 'B3'},
            'B7': {'name': 'Golf', 'url_suffix': 'B7'},
            'B8': {'name': 'Rugby Union', 'url_suffix': 'B8'},
            'B12': {'name': 'American Football', 'url_suffix': 'B12'},
            'B13': {'name': 'Tennis', 'url_suffix': 'B13'},
            'B16': {'name': 'Baseball', 'url_suffix': 'B16'},
            'B17': {'name': 'Hockey', 'url_suffix': 'B17'},
            'B18': {'name': 'Basketball', 'url_suffix': 'B18'},
            'B19': {'name': 'Rugby League', 'url_suffix': 'B19'},
            'B36': {'name': 'Australian Rules', 'url_suffix': 'B36'},
            'B78': {'name': 'Handball', 'url_suffix': 'B78'},
            'B83': {'name': 'Futsal', 'url_suffix': 'B83'},
            'B89': {'name': 'Bandy', 'url_suffix': 'B89'},
            'B84': {'name': 'Field Hockey', 'url_suffix': 'B84'},
            'B14': {'name': 'Snooker', 'url_suffix': 'B14'},
            'B91': {'name': 'Volleyball', 'url_suffix': 'B91'},
            'B92': {'name': 'Table Tennis', 'url_suffix': 'B92'},
            'B94': {'name': 'Badminton', 'url_suffix': 'B94'},
            'B110': {'name': 'Water Polo', 'url_suffix': 'B110'},
            'B151': {'name': 'Esports', 'url_suffix': 'B151'},
            'B162': {'name': 'MMA', 'url_suffix': 'B162'}
        }

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        # Console logging only - no file logging
    
    def load_hierarchical_cache(self):
        """Load hierarchical cache for team name normalization with O(1) indices"""
        self.hierarchical_cache = {}
        self.nickname_index = {}  # O(1) lookup by nickname
        self.sport_team_index = {}  # O(1) lookup by sport -> teams
        
        try:
            cache_file = Path("cache_data.json")
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.hierarchical_cache = data.get('alias_lookup', {})
                
                # Build O(1) lookup indices
                self._build_lookup_indices()
                
                self.logger.info(f"Loaded hierarchical cache with {len(self.hierarchical_cache)} aliases")
            else:
                self.logger.warning("cache_data.json not found, team names will not be normalized")
        except Exception as e:
            self.logger.warning(f"Could not load hierarchical cache: {e}")
    
    def _build_lookup_indices(self):
        """Build O(1) lookup indices for fast team name normalization"""
        for alias, path in self.hierarchical_cache.items():
            # Build nickname index (last word of alias)
            words = alias.split()
            if len(words) >= 2 and path.get('team'):
                nickname = words[-1]
                if nickname not in self.nickname_index:
                    self.nickname_index[nickname] = []
                self.nickname_index[nickname].append((alias, path))
            
            # Build sport/league index
            team = path.get('team')
            if team:
                sport = path.get('sport', '')
                league = path.get('league', '')
                
                # Index by sport
                if sport:
                    if sport not in self.sport_team_index:
                        self.sport_team_index[sport] = {}
                    canonical = path.get('canonical_name')
                    if canonical:
                        self.sport_team_index[sport][alias] = canonical
                
                # Index by league
                if league:
                    if league not in self.sport_team_index:
                        self.sport_team_index[league] = {}
                    canonical = path.get('canonical_name')
                    if canonical:
                        self.sport_team_index[league][alias] = canonical
        
        self.logger.info(f"Built lookup indices: {len(self.nickname_index)} nicknames, {len(self.sport_team_index)} sports/leagues")
    
    def normalize_team_name(self, team_name: str, sport: Optional[str] = None) -> str:
        """Normalize team name using hierarchical cache with O(1) lookups"""
        if not team_name or not self.hierarchical_cache:
            return team_name

        team_lower = team_name.lower().strip()
        
        # Remove common punctuation and extra spaces
        team_cleaned = re.sub(r'[^\w\s]', '', team_lower)
        team_cleaned = re.sub(r'\s+', ' ', team_cleaned).strip()

        # Stage 1: Direct exact match - O(1)
        if team_lower in self.hierarchical_cache:
            path = self.hierarchical_cache[team_lower]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical
        
        # Stage 2: Try cleaned version - O(1)
        if team_cleaned != team_lower and team_cleaned in self.hierarchical_cache:
            path = self.hierarchical_cache[team_cleaned]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical

        # Stage 3: Try without spaces - O(1)
        team_no_space = team_cleaned.replace(' ', '')
        if team_no_space != team_cleaned and team_no_space in self.hierarchical_cache:
            path = self.hierarchical_cache[team_no_space]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical

        # Stage 4: Nickname matching using pre-built index - O(1)
        words = team_cleaned.split()
        if len(words) >= 2:
            nickname = words[-1]
            
            # O(1) lookup in nickname index
            if nickname in self.nickname_index:
                candidates = self.nickname_index[nickname]
                
                # Check sport match if provided
                for alias, path in candidates:
                    if sport:
                        cache_sport = path.get('sport', '')
                        cache_league = path.get('league', '')
                        # Match either sport or league
                        if cache_sport and sport.upper() == cache_sport.upper():
                            return path.get('canonical_name')
                        if cache_league and sport.upper() == cache_league.upper():
                            return path.get('canonical_name')
                    else:
                        # No sport filter, return first match
                        return path.get('canonical_name')

        # Stage 5: Sport-specific lookup - O(1)
        if sport:
            # Check if sport has an index
            sport_index = self.sport_team_index.get(sport, {})
            
            # Try various formats
            for variant in [team_lower, team_cleaned, team_no_space]:
                if variant in sport_index:
                    return sport_index[variant]
            
            # Try with nickname if available
            if len(words) >= 2:
                nickname = words[-1]
                # Look for any alias ending with this nickname in this sport
                for alias, canonical in sport_index.items():
                    if alias.endswith(nickname):
                        return canonical

        # Stage 6: Fallback - Check if any word matches (still faster than full iteration)
        # Only do this for very short lookups to avoid performance issues
        if len(team_words := team_cleaned.split()) <= 3:
            # Try combining words in different ways
            for i in range(len(team_words)):
                for j in range(i + 1, len(team_words) + 1):
                    subset = ' '.join(team_words[i:j])
                    if subset in self.hierarchical_cache:
                        path = self.hierarchical_cache[subset]
                        if path.get('team'):  # Only return if it's a team
                            canonical = path.get('canonical_name')
                            if canonical:
                                return canonical

        # Return original if no match found
        return team_name

    def load_selector_database(self):
        """Load the detailed selector database - disabled to avoid extra files"""
        # Selector database disabled to keep only 3 JSON files
        return self._create_default_selector_database()
    
    def _create_default_selector_database(self):
        """Create default selector database"""
        db = {
            'last_updated': datetime.now().isoformat(),
            'sports': {},
            'global_selectors': {
                'match_containers': ['.ovm-Fixture', '.gl-Market'],
                'team_names': ['.ovm-FixtureDetailsTwoWay_TeamName', '[class*="TeamName"]'],
                'scores': ['.ovm-StandardScores_TeamOne', '.ovm-StandardScores_TeamTwo'],
                'odds': ['[class*="Odds"]', '.gl-Participant span'],
                'status': ['.ovm-InPlayTimer', '[class*="Timer"]']
            }
        }
        self.save_selector_database(db)
        return db

    def save_selector_database(self, db):
        """Save the selector database - disabled to keep only 3 JSON files"""
        # Selector database saving disabled
        pass

    def load_match_history(self):
        """Load match history data"""
        try:
            if os.path.exists(self.history_data_file):
                with open(self.history_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.logger.info("Loaded match history with %d completed matches", 
                               len(data.get('completed_matches', {})))
                return data
        except Exception as e:
            self.logger.debug("Error loading match history: %s", e)
        
        history = {
            'created': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'completed_matches': {},
            'removed_matches': {},
            'session_stats': {
                'total_completed': 0,
                'total_removed': 0,
                'sports_tracked': []
            }
        }
        self.save_match_history(history)
        return history

    def save_match_history(self, history):
        """Save match history data"""
        try:
            with open(self.history_data_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            self.logger.debug("Match history saved")
        except Exception as e:
            self.logger.error("Failed to save match history: %s", e)

    def generate_match_key(self, match):
        """Generate a unique key for a match"""
        if not isinstance(match, dict):
            return hashlib.md5(f"invalid_{str(match)[:20]}".encode()).hexdigest()[:16]
        
        teams = match.get('teams', {})
        sport = match.get('sport', 'Unknown')
        
        if isinstance(teams, dict):
            home = teams.get('home', '')
            away = teams.get('away', '')
        elif isinstance(teams, str):
            parts = teams.split(' vs ')
            home = parts[0] if len(parts) > 0 else ''
            away = parts[1] if len(parts) > 1 else ''
        else:
            home = away = ''
            
        return hashlib.md5(f"{sport}_{home}_{away}".encode()).hexdigest()[:16]

    def detect_data_changes(self, new_matches):
        """Detect changes in match data"""
        changes = {
            'new': [],
            'updated': [],
            'removed': []
        }

        current_keys = set()
        new_match_dict = {}

        for match in new_matches:
            match_key = self.generate_match_key(match)
            current_keys.add(match_key)
            new_match_dict[match_key] = match

            if match_key not in self.current_matches:
                match['first_seen'] = datetime.now().isoformat()
                match['last_updated'] = datetime.now().isoformat()
                changes['new'].append(match)
                self.logger.info("New match detected: %s vs %s (%s)",
                               match['teams'].get('home', 'Unknown'),
                               match['teams'].get('away', 'Unknown'),
                               match.get('sport', 'Unknown'))
            else:
                existing_match = self.current_matches[match_key]
                updates = self.compare_match_data(existing_match, match)
                if updates:
                    match['last_updated'] = datetime.now().isoformat()
                    changes['updated'].append({
                        'match_key': match_key,
                        'old_data': existing_match,
                        'new_data': match,
                        'changes': updates
                    })

        for match_key, match in self.current_matches.items():
            if match_key not in current_keys:
                changes['removed'].append(match)

        self.current_matches = new_match_dict
        return changes

    def compare_match_data(self, old_match, new_match):
        """Compare two match data objects and return list of changes"""
        changes = []

        old_scores = old_match.get('scores', {})
        new_scores = new_match.get('scores', {})
        if old_scores.get('home') != new_scores.get('home') or old_scores.get('away') != new_scores.get('away'):
            changes.append('score')

        if old_match.get('status') != new_match.get('status'):
            changes.append('status')

        if old_match.get('time') != new_match.get('time'):
            changes.append('time')

        old_odds = old_match.get('odds', {})
        new_odds = new_match.get('odds', {})
        odds_changed = (
            old_odds.get('home') != new_odds.get('home') or
            old_odds.get('away') != new_odds.get('away') or
            old_odds.get('tie') != new_odds.get('tie') or
            old_odds.get('over') != new_odds.get('over') or
            old_odds.get('under') != new_odds.get('under')
        )
        if odds_changed:
            changes.append('odds')

        return changes

    def process_data_changes(self, changes):
        """Process detected data changes and update history"""
        timestamp = datetime.now().isoformat()

        for match in changes['new']:
            if isinstance(match, dict):
                # Normalize team names before storing
                self._normalize_match_teams(match)
                match_key = self.generate_match_key(match)
                self.current_matches[match_key] = match

        for update in changes['updated']:
            match_key = update['match_key']
            if match_key in self.current_matches:
                # Normalize team names in updated data
                self._normalize_match_teams(update['new_data'])
                self.current_matches[match_key].update(update['new_data'])
                self.current_matches[match_key]['last_updated'] = timestamp

        for match in changes['removed']:
            match_key = self.generate_match_key(match)
            if match_key in self.current_matches:
                del self.current_matches[match_key]

            match['completed_at'] = timestamp
            self.match_history['completed_matches'][match_key] = match
            self.match_history['session_stats']['total_completed'] += 1

        self.save_current_data()
        self.save_match_history(self.match_history)
    
    def _normalize_match_teams(self, match: Dict):
        """Normalize team names in a match dictionary in-place"""
        if not isinstance(match, dict):
            return
        
        sport = match.get('sport', '')
        teams = match.get('teams', {})
        
        if isinstance(teams, dict):
            # Normalize home/away teams
            if 'home' in teams and teams['home']:
                teams['home'] = self.normalize_team_name(teams['home'], sport)
            if 'away' in teams and teams['away']:
                teams['away'] = self.normalize_team_name(teams['away'], sport)
            
            # Normalize team1/team2 (for sports like tennis)
            if 'team1' in teams and teams['team1']:
                teams['team1'] = self.normalize_team_name(teams['team1'], sport)
            if 'team2' in teams and teams['team2']:
                teams['team2'] = self.normalize_team_name(teams['team2'], sport)
    def save_current_data(self):
        """Save current live matches data"""
        try:
            sports_breakdown = {}
            for match in self.current_matches.values():
                if isinstance(match, dict):
                    sport = match.get('sport', 'Unknown')
                    sports_breakdown[sport] = sports_breakdown.get(sport, 0) + 1
            
            current_data = {
                'last_updated': datetime.now().isoformat(),
                'session_id': self.session_id,
                'total_matches': len(self.current_matches),
                'matches': list(self.current_matches.values()),
                'data_changes_log': self.data_changes_log[-100:],
                'sports_breakdown': sports_breakdown
            }

            with open(self.current_data_file, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False)
            
            if DASHBOARD_AVAILABLE and not self.disable_broadcasting:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(broadcast_to_dashboard(current_data))
                    else:
                        asyncio.run(broadcast_to_dashboard(current_data))
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.error("Error saving current data: %s", e)

    def load_current_data(self):
        """Load current live matches data"""
        try:
            if os.path.exists(self.current_data_file):
                with open(self.current_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.current_matches = {self.generate_match_key(m): m for m in data.get('matches', [])}
                self.data_changes_log = data.get('data_changes_log', [])
                self.logger.info("Loaded current data with %d matches", len(self.current_matches))
                return True
            else:
                self.current_matches = {}
                self.data_changes_log = []
                return False
        except Exception as e:
            self.logger.error("Error loading current data: %s", e)
            self.current_matches = {}
            self.data_changes_log = []
            return False

    def get_sport_selectors(self, sport_code):
        """Get sport-specific selectors from database"""
        sport_key = sport_code.lower()
        sport_data = self.selector_database.get('sports', {}).get(sport_key, {})
        sport_selectors = sport_data.get('successful_selectors', {})
        global_selectors = self.selector_database.get('global_selectors', {})

        combined_selectors = {}
        for selector_type in ['match_containers', 'team_names', 'scores', 'odds', 'status']:
            sport_specific = sport_selectors.get(selector_type, [])
            global_list = global_selectors.get(selector_type, [])
            
            if sport_specific:
                combined_selectors[selector_type] = sport_specific
            else:
                combined_selectors[selector_type] = global_list

        return combined_selectors

    def check_server_availability(self):
        """Quick check if bet365 server is responding"""
        import urllib.request
        import urllib.error
        import socket

        try:
            self.logger.info("Checking bet365 server availability...")
            req = urllib.request.Request("https://www.on.bet365.ca/")
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                if status_code in [200, 403]:
                    self.logger.info("Server is responding (HTTP %d)", status_code)
                    return True
                return True
        except urllib.error.HTTPError as e:
            if e.code == 403:
                self.logger.info("Server is responding (HTTP 403 - anti-bot protection)")
                return True
            else:
                self.logger.error(f"HTTP Error {e.code}: {e.reason}")
                return False
        except urllib.error.URLError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except socket.timeout:
            self.logger.error("Connection timeout")
            return False
        except Exception as e:
            self.logger.error(f"Server check failed: {e}")
            return False

    def find_chrome_executable(self):
        """Find Chrome executable path"""
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]

        for path in chrome_paths:
            if os.path.exists(path):
                return path
        return None

    def kill_existing_browsers(self):
        """Don't kill existing browsers - we use isolated instances"""
        self.logger.info("Using isolated browser - not affecting existing browser sessions")
        return True
    
    async def cleanup_isolated_browser(self):
        """Clean up the isolated browser instance"""
        try:
            self.logger.info("Cleaning up isolated browser...")
            
            if self.page:
                try:
                    await self.page.close()
                except:
                    pass
                self.page = None
            
            if self.browser_instance:
                try:
                    await self.browser_instance.close()
                except:
                    pass
                self.browser_instance = None
            
            if self.playwright_instance:
                try:
                    await self.playwright_instance.stop()
                except:
                    pass
                self.playwright_instance = None
            
            if self.browser_process:
                try:
                    self.browser_process.terminate()
                    import time
                    for _ in range(50):
                        if self.browser_process.poll() is not None:
                            break
                        time.sleep(0.1)
                    
                    if self.browser_process.poll() is None:
                        self.browser_process.kill()
                except:
                    pass
                self.browser_process = None
            
            if self.isolated_profile_dir and os.path.exists(self.isolated_profile_dir):
                try:
                    import shutil
                    import time
                    time.sleep(2)
                    shutil.rmtree(self.isolated_profile_dir, ignore_errors=True)
                except:
                    pass
                self.isolated_profile_dir = None
            
            self.logger.info("Isolated browser cleanup complete")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    async def extract_live_betting_data(self, page, sport_code='B1'):
        """Extract live betting data using comprehensive extraction script"""

        # Backward compatibility
        if isinstance(page, str):
            sport_code = page
            page = getattr(self, 'page', None)

        self.logger.info("Extracting live betting data for %s...", sport_code)

        if sport_code:
            if not page:
                self.logger.error("Page not connected - cannot navigate to sport")
                return {'matches': [], 'total_matches': 0, 'sport': sport_code}

            sport_url = f"https://www.on.bet365.ca/#/IP/{sport_code}/"
            current_url = page.url

            if sport_code not in current_url:
                try:
                    await page.goto(sport_url, wait_until='domcontentloaded', timeout=20000)
                    await asyncio.sleep(1.5)
                except Exception as e:
                    self.logger.warning(f"Navigation failed: {e}")

            # Wait for fixtures to load (more reliable than URL checking)
            try:
                # Wait for page to be ready first
                await page.wait_for_load_state('networkidle', timeout=10000)

                # Additional wait for dynamic content to load
                await asyncio.sleep(5)

                # Try multiple selectors that indicate live betting content
                selectors_to_try = [
                    '.ovm-Fixture',
                    '.gl-Market',
                    '.ovm-FixtureDetailsTwoWay_TeamName',
                    '[class*="Fixture"]',
                    '[class*="Market"]',
                    '.ovm-InPlayTimer',
                    '.ovm-StandardScores_TeamOne'
                ]

                fixture_found = False
                for selector in selectors_to_try:
                    try:
                        await page.wait_for_selector(selector, timeout=8000)
                        self.logger.info(f"Found fixtures using selector: {selector}")
                        fixture_found = True
                        break
                    except:
                        continue

                if not fixture_found:
                    # Check if page shows "no live matches" message
                    page_text = await page.inner_text('body')
                    if 'no live' in page_text.lower() or 'no matches' in page_text.lower() or 'no events' in page_text.lower():
                        self.logger.info(f"No live matches available for {sport_code}")
                        return {
                            'matches': [],
                            'total_matches': 0,
                            'sport': sport_code,
                            'redirected': True
                        }
                    else:
                        # Try to extract anyway - the extraction script will handle empty results
                        self.logger.info(f"No fixtures found for {sport_code}, but proceeding with extraction")
                        # Don't return early, let the extraction script run

            except Exception as e:
                self.logger.warning(f"Error waiting for fixtures: {e}")
                # Don't return early, let the extraction script run

        # Get sport-specific selectors
        sport_selectors = self.get_sport_selectors(sport_code)

        # Convert selectors to JavaScript arrays
        match_selectors_js = json.dumps(sport_selectors.get('match_containers', ['.ovm-Fixture']))
        team_selectors_js = json.dumps(sport_selectors.get('team_names', ['.ovm-FixtureDetailsTwoWay_TeamName']))
        score_selectors_js = json.dumps(sport_selectors.get('scores', [
            '.ovm-StandardScores_TeamOne', '.ovm-StandardScores_TeamTwo',
            '.ovm-StandardScoresSoccer_TeamOne', '.ovm-StandardScoresSoccer_TeamTwo',
            '.ovm-StandardScoresCricket_TeamOne', '.ovm-StandardScoresCricket_TeamTwo',
            '.ovm-SetsBasedScores_TeamOne', '.ovm-SetsBasedScores_TeamTwo'
        ]))
        odds_selectors_js = json.dumps(sport_selectors.get('odds', ['[class*="Odds"]']))
        status_selectors_js = json.dumps(sport_selectors.get('status', ['.ovm-InPlayTimer']))
        
        sport_mappings_for_js = {code: info['name'] for code, info in self.sport_mappings.items()}
        sport_mappings_js = json.dumps(sport_mappings_for_js)

        # Use comprehensive extraction script from bet365_extraction_template.py
        from bet365_extraction_template import get_comprehensive_extraction_script

        extraction_script = get_comprehensive_extraction_script(
            sport_code=sport_code,
            sport_mappings_js=sport_mappings_js,
            match_selectors_js=match_selectors_js,
            team_selectors_js=team_selectors_js,
            score_selectors_js=score_selectors_js,
            odds_selectors_js=odds_selectors_js,
            status_selectors_js=status_selectors_js
        )

        # Log that we're using the improved extraction script
        self.logger.info(f"Using comprehensive extraction script for sport {sport_code}")

        if not page:
            self.logger.error("Page not connected - cannot execute extraction script")
            return {'matches': [], 'total_matches': 0, 'sport': sport_code}

        result = await page.evaluate(extraction_script)

        self.logger.info(f"Extracted {len(result.get('matches', []))} live matches")
        
        debug_info = result.get('debug', {})
        if debug_info:
            self.logger.debug(f"Debug: {debug_info.get('page_elements_found', 0)} fixtures found")

        return result

    def save_live_results(self, results: Dict):
        """Save live extraction results to JSON file"""
        # Use processed matches from self.current_matches instead of raw results
        processed_matches = list(self.current_matches.values())

        sports_count = {}
        for match in processed_matches:
            if isinstance(match, dict):
                sport = match.get('sport', 'Unknown')
                sports_count[sport] = sports_count.get(sport, 0) + 1

        output = {
            'extraction_info': {
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'source': 'bet365.ca',
                'method': 'COMPREHENSIVE-LIVE-SCRAPER',
                'total_matches': len(processed_matches),
                'live_matches': results.get('summary', {}).get('live_matches', 0)
            },
            'sports_breakdown': sports_count,
            'matches_data': processed_matches,
            'summary': results.get('summary', {})
        }

        try:
            with open(self.statistics_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            self.logger.info("Results saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")

        dashboard_data = {
            'last_updated': datetime.now().isoformat(),
            'session_id': self.session_id,
            'total_matches': len(processed_matches),
            'matches': processed_matches,
            'sports_breakdown': sports_count
        }

        try:
            with open(self.current_data_file, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save dashboard data: {e}")

    async def run_live_extraction(self, sport_codes=None):
        """Run live extraction for multiple sports"""
        self.logger.info("Starting COMPREHENSIVE LIVE BET365 Extraction...")

        if sport_codes is None:
            sport_codes = list(self.sport_mappings.keys())

        try:
            if not self.check_server_availability():
                self.logger.error("Server unavailable")
                return None

            self.kill_existing_browsers()

            if not await self.launch_manual_browser():
                return None

            if not await self.connect_playwright_to_browser():
                return None

            if not await self.wait_for_bet365_load():
                self.logger.error("bet365 failed to load")
                return None

            all_matches = []
            validation_results = []

            for sport_code in sport_codes:
                sport_info = self.sport_mappings.get(sport_code, {})
                sport_name = sport_info.get('name', sport_code)

                self.logger.info(f"\nExtracting {sport_name}...")
                self.extraction_count += 1
                sport_data = await self.extract_live_betting_data(self.page, sport_code)

                actual_matches = len(sport_data.get('matches', [])) if sport_data else 0
                is_redirected = sport_data.get('redirected', False) if sport_data else False
                
                status = "ACTIVE" if actual_matches > 0 else ("REDIRECTED" if is_redirected else "NO MATCHES")

                validation_results.append({
                    'sport': sport_name,
                    'code': sport_code,
                    'matches_found': actual_matches,
                    'status': status,
                    'redirected': is_redirected
                })

                if sport_data and sport_data.get('matches'):
                    all_matches.extend(sport_data['matches'])
                    self.logger.info(f"[{status}] Found {actual_matches} matches")
                else:
                    self.logger.info(f"[{status}]")

            changes = self.detect_data_changes(all_matches)
            self.process_data_changes(changes)

            results = {
                'timestamp': datetime.now().isoformat(),
                'matches': all_matches,
                'validation_results': validation_results,
                'data_changes': changes,
                'summary': {
                    'total_matches': len(all_matches),
                    'live_matches': sum(1 for m in all_matches if m.get('live_fields', {}).get('is_live')),
                    'total_markets': sum(len(m.get('markets', [])) for m in all_matches),
                    'sports_processed': len(validation_results),
                    'active_sports': sum(1 for v in validation_results if v['status'] == 'ACTIVE'),
                    'redirected_sports': sum(1 for v in validation_results if v['status'] == 'REDIRECTED')
                }
            }

            self.save_live_results(results)
            return results

        except Exception as e:
            self.logger.error(f"Error during live extraction: {e}")
            return None

        finally:
            await self.cleanup_isolated_browser()

    async def launch_manual_browser(self, browser_type='chrome'):
        """Guide user through manual browser setup"""
        try:
            self.logger.info("Setting up manual browser connection...")

            if not self.check_server_availability():
                self.logger.error("Aborting browser launch - server not responding")
                return False

            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', self.debug_port))
            sock.close()

            if result == 0:
                self.logger.info(f"Found existing browser on port {self.debug_port}")
                return True
            else:
                self.logger.info(f"No browser found on port {self.debug_port}")
                return self.prompt_manual_browser_setup()

        except Exception as e:
            self.logger.error(f"Browser launch failed: {e}")
            return False

    def prompt_manual_browser_setup(self):
        """Launch isolated Chrome automatically"""
        print("\n" + "="*80)
        print("LAUNCHING ISOLATED CHROME FOR BET365")
        print("="*80)
        print("Starting isolated Chrome instance...")
        print("="*80)
        
        process = self.launch_isolated_chrome()
        if not process:
            print("ERROR: Failed to launch Chrome")
            return False
        
        print("Waiting for Chrome to start...")
        import time
        time.sleep(8)
        
        print("Chrome launched successfully!")
        print("Proceeding to connect...")
        time.sleep(3)
        return True

    def create_isolated_profile_dir(self):
        """Create a unique isolated profile directory"""
        import tempfile
        import shutil
        
        profile_dir = os.path.join(tempfile.gettempdir(), f"bet365_isolated_{self.session_id}")
        
        if os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir)
            except:
                pass
        
        os.makedirs(profile_dir, exist_ok=True)
        self.isolated_profile_dir = profile_dir
        return profile_dir

    def launch_isolated_chrome(self):
        """Launch Chrome with isolated profile"""
        chrome_exe = self.find_chrome_executable()
        if not chrome_exe:
            self.logger.error("Chrome executable not found")
            return None
        
        profile_dir = self.create_isolated_profile_dir()
        
        import socket
        self.debug_port = 9222
        
        for port in range(9222, 9232):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result != 0:
                self.debug_port = port
                break
        
        cmd = [
            chrome_exe,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={profile_dir}",
             # Complete isolation from other Chrome instances
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-sync",
            "--disable-translate",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            
            # Make it appear like a normal browser (not automated)
            "--disable-blink-features=AutomationControlled",
            "--disable-features=VizDisplayCompositor",
            
             # Window settings
            "--window-size=1366,768",
            "--start-maximized",
        ]
        
        try:
            self.logger.info(f"Launching isolated Chrome on port {self.debug_port}")
            
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.browser_process = process
            self.logger.info(f"Chrome launched with PID: {process.pid}")
            return process
            
        except Exception as e:
            self.logger.error(f"Failed to launch Chrome: {e}")
            return None

    async def connect_playwright_to_browser(self):
        """Connect Playwright to the isolated browser"""
        try:
            self.logger.info(f"Connecting to isolated browser on port {self.debug_port}...")

            import socket
            import time
            max_wait = 30
            waited = 0
            while waited < max_wait:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', self.debug_port))
                sock.close()
                if result == 0:
                    break
                await asyncio.sleep(0.4)
                waited += 1
            
            if waited >= max_wait:
                self.logger.error(f"CDP port {self.debug_port} not available")
                return False

            self.playwright_instance = await async_playwright().start()

            try:
                self.browser_instance = await asyncio.wait_for(
                    self.playwright_instance.chromium.connect_over_cdp(f"http://localhost:{self.debug_port}"),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                self.logger.error("CDP connection timed out")
                return False

            contexts = self.browser_instance.contexts if self.browser_instance else []
            if not contexts:
                self.logger.error("No browser contexts found")
                return False
                
            pages = contexts[0].pages if contexts else []
            if pages:
                self.page = pages[0]
            else:
                self.logger.error("No pages found")
                return False

            current_url = self.page.url

            if "bet365" not in current_url.lower():
                try:
                    await asyncio.wait_for(
                        self.page.goto("https://www.on.bet365.ca/#/IP/", wait_until='domcontentloaded'),
                        timeout=15.0
                    )
                    await asyncio.sleep(0.5)
                except asyncio.TimeoutError:
                    self.logger.error("Navigation timeout")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    async def wait_for_bet365_load(self, timeout=30):
        """Wait for bet365 to be loaded"""
        self.logger.info("Verifying bet365 is loaded...")

        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                if not self.page:
                    return False

                current_url = self.page.url
                page_source = await self.page.content()
                page_source_lower = page_source.lower()

                server_error_indicators = [
                    'server error', '500 internal', '503 service',
                    '502 bad gateway', '504 gateway timeout'
                ]

                has_server_error = any(indicator in page_source_lower for indicator in server_error_indicators)

                if has_server_error:
                    self.logger.error("Server error detected")
                    return False

                cloudflare_indicators = [
                    'just a moment', 'checking your browser', 'cloudflare',
                    'ray id', 'please wait'
                ]

                has_cloudflare = any(indicator in page_source_lower for indicator in cloudflare_indicators)
                has_bet365_content = ('bet365' in page_source_lower or 'bet365' in current_url.lower())
                has_basic_structure = ('<html' in page_source_lower and '<body' in page_source_lower)

                if has_cloudflare and not has_bet365_content:
                    if int(time.time() - start_time) % 10 == 0:
                        self.logger.info("Waiting for Cloudflare...")
                elif has_bet365_content and has_basic_structure:
                    self.logger.info("bet365 loaded and ready!")
                    return True
                elif 'access denied' in page_source_lower:
                    self.logger.error("Access denied")
                    return False

                await asyncio.sleep(0.4)

            except Exception:
                await asyncio.sleep(0.4)

        self.logger.error(f"Timeout: bet365 not loaded within {timeout}s")
        return False


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Comprehensive Live Bet365 Scraper')
    parser.add_argument('--mode', choices=['single', 'monitor'], default='single',
                       help='Run mode (default: single)')
    parser.add_argument('--sports', nargs='+',
                       help='Specific sports to monitor')

    args = parser.parse_args()

    scraper = UltimateLiveScraper()

    sport_codes = None
    if args.sports:
        valid_sports = []
        for sport in args.sports:
            if sport.upper() in scraper.sport_mappings:
                valid_sports.append(sport.upper())
        sport_codes = valid_sports if valid_sports else None

    print("COMPREHENSIVE LIVE BET365 SCRAPER")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Sports: {', '.join(sport_codes) if sport_codes else 'All'}")
    print("=" * 60)

    await scraper.run_live_extraction(sport_codes)


if __name__ == "__main__":
    asyncio.run(main())