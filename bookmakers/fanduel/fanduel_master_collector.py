#!/usr/bin/env python3
"""
FanDuel Master Sports Data Collector - STANDARDIZED VERSION
Uses consistent schema for UI integration and database management
"""

import asyncio
import json
import time
import os
import subprocess
import tempfile
import logging
import signal
import atexit
import psutil
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# Lock file for single instance
LOCK_FILE = Path('/tmp/fanduel_collector.lock')

def cleanup_chrome_processes():
    """Kill all Chrome processes related to FanDuel collector"""
    try:
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                # Kill Chrome processes with FanDuel profile
                if 'fd_master_' in cmdline or ('chrome' in proc.info['name'].lower() and 'fanduel' in cmdline.lower()):
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                pass
        
        if killed_count > 0:
            logging.info(f"🧹 Killed {killed_count} Chrome processes")
        
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
                    logging.error(f"Another FanDuel instance is running (PID: {old_pid})")
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

class FanDuelMasterCollector:
    """Master collector with standardized schema for UI/database integration"""

    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use a random port to avoid conflicts when multiple instances run
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            self.debug_port = s.getsockname()[1]

        # Browser
        self.playwright = None
        self.browser = None
        self.chrome_process = None
        self.context = None

        # All sport pages
        self.sport_pages = {}

        # Master data storage - using DICTS for fast lookup
        self.events_data = {}  # event_id: full_event_data
        self.markets_data = {}  # market_id: market_data
        self.competitions_data = {}  # comp_id: comp_data

        # Standardized data structures
        self.matches = []  # List of standardized match objects (pregame only)
        # self.live_matches = []  # DISABLED - dedicated script handles live matches
        # self.futures = []  # REMOVED - no futures collected
        self.leagues = []  # List of league info
        self.teams = []   # List of team info

        # History tracking - DISABLED to prevent false positives
        # self.match_history = {}  # match_id: full_match_data for removed matches
        # self.seen_match_ids = set()  # Track all match IDs we've ever seen
        # self.consecutive_missing_count = {}  # Track how many times a match has been missing

        # Captured raw API data
        self.captured_apis = []

        # Thread-safe locks
        self.data_lock = asyncio.Lock()

        # Track what we've seen
        self.processed_events = set()

        # Logging
        self.setup_logging()
        print(f"[INIT] Master Collector - Session: {self.session_id}")

    def setup_logging(self):
        """Setup logging"""
        self.logger = logging.getLogger('master_collector')
        self.logger.setLevel(logging.INFO)

        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        log_file = os.path.join(logs_dir, f'master_{self.session_id}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("="*80)
        self.logger.info("MASTER COLLECTOR STARTED")
        self.logger.info("="*80)

    def launch_chrome(self):
        """Launch Chrome - works on both Windows and Linux"""
        # Detect Chrome path based on OS
        if os.name == 'nt':  # Windows
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            ]
        else:  # Linux/Ubuntu
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
            ]
        
        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break
        
        if not chrome_exe:
            raise Exception(f"Chrome not found in any of the expected locations: {chrome_paths}")

        profile_dir = os.path.join(tempfile.gettempdir(), f"fd_master_{self.session_id}")
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            chrome_exe,
            f'--remote-debugging-port={self.debug_port}',
            f'--user-data-dir={profile_dir}',
            '--no-first-run',
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--no-sandbox'  # Required for VPS/Docker environments
        ]
        
        # Add display-specific options for Linux
        if os.name != 'nt':
            cmd.extend([
                '--disable-setuid-sandbox',
                '--disable-software-rasterizer'
            ])
        else:
            cmd.append('--start-maximized')

        self.logger.info("Launching Chrome...")
        self.logger.info(f"Debug port: {self.debug_port}")
        self.logger.info(f"Command: {' '.join(cmd)}")

        try:
            self.chrome_process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.logger.info(f"Chrome launched (PID: {self.chrome_process.pid})")
        except Exception as e:
            self.logger.error(f"Failed to launch Chrome: {e}")
            raise

    async def setup_browser(self):
        """Setup browser connection"""
        self.logger.info("Connecting to Chrome...")

        try:
            self.playwright = await async_playwright().start()
            self.logger.info("Playwright started")

            self.launch_chrome()
            self.logger.info("Waiting for Chrome to be ready...")
            await asyncio.sleep(3)

            self.logger.info(f"Attempting to connect to Chrome on port {self.debug_port}")
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.debug_port}",
                timeout=10000
            )
            self.logger.info("Connected to Chrome successfully")

            self.context = self.browser.contexts[0]
            self.logger.info(f"Got browser context with {len(self.context.pages)} existing pages")

            # Set up unified response handler
            self.context.on('response', self.unified_response_handler)

            self.logger.info("Connected with unified response handler!")

        except Exception as e:
            self.logger.error(f"Failed to setup browser: {e}")
            raise

    async def unified_response_handler(self, response):
        """Unified response handler that captures ALL data and IMMEDIATELY saves - only after page fully loads"""
        try:
            url = response.url

            # Filter for FanDuel API calls - expanded to catch more APIs
            if ('fanduel.com' in url and
                response.status == 200 and
                ('sbapi' in url or 'boapi' in url or 'sportsbook' in url or 'content-managed-page' in url) and
                not any(ext in url for ext in ['.png', '.jpg', '.css', '.js', '.woff', '.ttf', '.svg', '.ico', '.woff2'])):

                try:
                    body = await response.body()
                    data = json.loads(body.decode('utf-8'))

                    # Check if this has attachments with events/markets
                    if self._has_sports_data(data):
                        sport = self._identify_sport(data, url)

                        async with self.data_lock:
                            self.captured_apis.append({
                                'url': url,
                                'sport': sport,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            })

                            # Process the data IMMEDIATELY
                            self._process_api_data(data, sport)

                            # SAVE IMMEDIATELY after processing
                            self._save_all_data()

                        self.logger.info(f"📡 {sport.upper()} API captured | Events: {len(self.events_data)} | Markets: {len(self.markets_data)} | SAVED")

                except Exception as e:
                    pass

        except Exception as e:
            pass

    def _has_sports_data(self, data: Dict) -> bool:
        """Check if data has sports information"""
        if not isinstance(data, dict):
            return False
        
        attachments = data.get('attachments', {})
        if not isinstance(attachments, dict):
            return False
            
        return ('events' in attachments or 'markets' in attachments or 
                'competitions' in attachments or 'events' in data)

    def _identify_sport(self, data: Dict, url: str) -> str:
        """Identify sport from URL or data"""
        url_lower = url.lower()

        # Check URL first - most reliable
        if 'basketball' in url_lower or 'eventTypeId=7522' in url:
            return 'basketball'
        elif 'soccer' in url_lower or 'eventTypeId=1' in url:
            return 'soccer'
        elif 'rugby-union' in url_lower or 'rugby_union' in url_lower or 'eventTypeId=8' in url:
            return 'rugby-union'
        elif 'rugby-league' in url_lower or 'rugby_league' in url_lower or 'eventTypeId=12' in url:
            return 'rugby-league'
        elif 'motorsport' in url_lower or 'motor-sport' in url_lower or 'eventTypeId=1477' in url:
            return 'motorsport'
        elif 'table-tennis' in url_lower or 'table_tennis' in url_lower or 'eventTypeId=6' in url:
            return 'table-tennis'
        elif 'boxing' in url_lower or 'eventTypeId=3' in url:
            return 'mma'
        elif 'golf' in url_lower or 'eventTypeId=5' in url:
            return 'golf'
        elif 'tennis' in url_lower or 'eventTypeId=2' in url:
            return 'tennis'
        elif 'cricket' in url_lower or 'eventTypeId=4' in url:
            return 'cricket'
        elif 'darts' in url_lower or 'eventTypeId=7' in url:
            return 'darts'
        elif 'ice-hockey' in url_lower or 'ice_hockey' in url_lower or 'eventTypeId=7524' in url:
            return 'hockey'
        elif 'aussie-rules' in url_lower or 'aussie_rules' in url_lower or 'eventTypeId=61420' in url:
            return 'aussie-rules'
        elif 'lacrosse' in url_lower or 'eventTypeId=7514' in url:
            return 'lacrosse'
        elif 'cycling' in url_lower or 'eventTypeId=11' in url:
            return 'cycling'
        elif ('football' in url_lower and 'soccer' not in url_lower) or 'nfl' in url_lower or 'eventTypeId=6423' in url:
            return 'football'

        # Check attachments for competitions and events
        attachments = data.get('attachments', {})

        # Check competitions
        if 'competitions' in attachments:
            comps = attachments['competitions']
            if isinstance(comps, dict):
                comp_str = json.dumps(comps).lower()
                # Soccer indicators
                if any(x in comp_str for x in ['premier league', 'la liga', 'serie a', 'bundesliga', 'champions league', 'world cup', 'euro', 'copa', 'mls']):
                    return 'soccer'
                # Rugby Union indicators
                elif any(x in comp_str for x in ['rugby union', 'rugby championship', 'six nations', 'rugby world cup', 'super rugby']):
                    return 'rugby-union'
                # Rugby League indicators
                elif any(x in comp_str for x in ['rugby league', 'nrl', 'super league', 'rugby league world cup']):
                    return 'rugby-league'
                # Motorsport indicators
                elif any(x in comp_str for x in ['motorsport', 'formula 1', 'f1', 'moto gp', 'nascar', 'indycar', 'rally']):
                    return 'motorsport'
                # Basketball indicators
                elif any(x in comp_str for x in ['nba', 'ncaa basketball', 'wnba', 'euroleague', 'cbb']):
                    return 'basketball'
                # Football indicators
                elif any(x in comp_str for x in ['nfl', 'ncaaf', 'college football', 'super bowl']):
                    return 'football'
                # Baseball indicators
                elif any(x in comp_str for x in ['mlb', 'baseball', 'dodgers', 'yankees', 'red sox']):
                    return 'baseball'

        # Check events for eventTypeId - more reliable than competition names
        if 'events' in attachments:
            events = attachments['events']
            if isinstance(events, dict):
                # Check first few events for eventTypeId
                for event_id, event_data in list(events.items())[:3]:
                    if isinstance(event_data, dict):
                        event_type_id = event_data.get('eventTypeId')
                        if event_type_id:
                            event_type_str = str(event_type_id)
                            if event_type_str == '1':
                                return 'soccer'
                            elif event_type_str == '7522':
                                return 'basketball'
                            elif event_type_str == '6423':
                                return 'football'
                            elif event_type_str == '7511':
                                return 'baseball'
                            elif event_type_str == '2':
                                return 'tennis'
                            elif event_type_str == '3':
                                return 'mma'
                            elif event_type_str == '4':
                                return 'cricket'
                            elif event_type_str == '5':
                                return 'golf'
                            elif event_type_str == '6':
                                return 'table-tennis'
                            elif event_type_str == '7':
                                return 'darts'
                            elif event_type_str == '8':
                                return 'rugby-union'
                            elif event_type_str == '11':
                                return 'cycling'
                            elif event_type_str == '12':
                                return 'rugby-league'
                            elif event_type_str == '7524':
                                return 'hockey'
                            elif event_type_str == '7514':
                                return 'lacrosse'
                            elif event_type_str == '61420':
                                return 'aussie-rules'
                            elif event_type_str == '1477':
                                return 'motorsport'

        # Check events
        if 'events' in attachments:
            events = attachments['events']
            if isinstance(events, dict):
                # Sample a few events
                event_sample = list(events.values())[:5]
                event_str = json.dumps(event_sample).lower()

                # Soccer check
                if any(x in event_str for x in ['premier league', 'la liga', 'serie a', 'bundesliga', 'champions league']):
                    return 'soccer'
                # Rugby Union check
                elif any(x in event_str for x in ['rugby union', 'rugby championship', 'six nations', 'all blacks', 'wallabies']):
                    return 'rugby-union'
                # Rugby League check
                elif any(x in event_str for x in ['rugby league', 'nrl', 'super league', 'roosters', 'storm']):
                    return 'rugby-league'
                # Motorsport check
                elif any(x in event_str for x in ['motorsport', 'formula 1', 'f1', 'moto gp', 'nascar', 'indycar', 'rally']):
                    return 'motorsport'
                # Basketball check
                elif any(x in event_str for x in ['nba', 'ncaa', 'wnba', 'basketball']):
                    return 'basketball'
                # Football check
                elif any(x in event_str for x in ['nfl', 'ncaaf', 'college football']):
                    return 'football'
                # Baseball check
                elif any(x in event_str for x in ['mlb', 'dodgers', 'yankees', 'blue jays', 'ohtani', 'bieber']):
                    return 'baseball'

        # Last resort - check entire data
        data_str = json.dumps(data).lower()

        if any(x in data_str for x in ['premier league', 'la liga', 'serie a', 'bundesliga']):
            return 'soccer'
        elif any(x in data_str for x in ['rugby union', 'rugby championship', 'six nations']):
            return 'rugby-union'
        elif any(x in data_str for x in ['rugby league', 'nrl', 'super league']):
            return 'rugby-league'
        elif any(x in data_str for x in ['motorsport', 'formula 1', 'f1', 'moto gp', 'nascar']):
            return 'motorsport'
        elif any(x in data_str for x in ['nba', 'ncaa basketball']):
            return 'basketball'
        elif any(x in data_str for x in ['nfl', 'ncaaf']):
            return 'football'
        elif any(x in data_str for x in ['mlb', 'dodgers', 'yankees', 'baseball']):
            return 'baseball'

        return 'unknown'

    def _process_api_data(self, data: Dict, sport: str):
        """Process API data - store events and markets, then build standardized matches"""
        try:
            attachments = data.get('attachments', {})

            # STEP 1: Store markets first (these have the ODDS!)
            if 'markets' in attachments:
                markets = attachments['markets']
                if isinstance(markets, dict):
                    for market_id, market_data in markets.items():
                        # Store market with its ID
                        self.markets_data[str(market_id)] = market_data

            # STEP 2: Store competitions and build leagues list
            if 'competitions' in attachments:
                comps = attachments['competitions']
                if isinstance(comps, dict):
                    for comp_id, comp_data in comps.items():
                        comp_id_str = str(comp_id)
                        self.competitions_data[comp_id_str] = comp_data

                        # Build standardized league object from competition data
                        league = self._build_standardized_league(comp_id_str, comp_data, sport)
                        if league:
                            # Check if league already exists (avoid duplicates)
                            existing_league = self._find_existing_league(comp_id_str)
                            if not existing_league:
                                self.leagues.append(league)

            # STEP 3: Store events
            if 'events' in attachments:
                events = attachments['events']
                if isinstance(events, dict):
                    for event_id, event_data in events.items():
                        if isinstance(event_data, dict):
                            # Store raw event
                            self.events_data[str(event_id)] = event_data

            # STEP 4: Build standardized matches and track history
            if 'events' in attachments:
                events = attachments['events']
                if isinstance(events, dict):
                    current_match_ids = set()

                    for event_id, event_data in events.items():
                        if isinstance(event_data, dict):
                            event_id_str = str(event_id)
                            current_match_ids.add(event_id_str)

                            # Build standardized match object
                            match = self._build_standardized_match(event_id_str, event_data, sport)

                            if match:
                                # Determine if match is live or pregame
                                is_live = event_data.get('inPlay', False)

                                # Track that we've seen this match (disabled history tracking)
                                # self.seen_match_ids.add(event_id_str)

                                # Future detection removed - no futures collected from any sports
                                # Determine if it's a future - use more comprehensive detection
                                # is_future = self._is_future(event_data)

                                # if is_future:
                                #     # Add only if not duplicate
                                #     event_key = f"{match['sport']}_{event_id}"  # Use match sport, not API sport
                                #     if event_key not in self.processed_events:
                                #         self.futures.append(match)
                                #         self.processed_events.add(event_key)
                                #         self.logger.info(f"✅ FUTURE ADDED: {match['event_name']} ({match['sport']})")

                                if is_live:
                                    # SKIP LIVE MATCHES - dedicated script handles them
                                    self.logger.debug(f"⏭️  SKIPPING LIVE MATCH: {match['event_name']} ({match['sport']}) - handled by dedicated script")
                                else:
                                    # Add to pregame matches
                                    existing_match = self._find_existing_match(event_id_str)
                                    if existing_match:
                                        # Update existing match
                                        self._update_existing_match(existing_match, match)
                                    else:
                                        # Add new match
                                        self.matches.append(match)

                    # STEP 5: Check for removed matches and move to history
                    self._check_for_removed_matches(current_match_ids)

        except Exception as e:
            self.logger.error(f"Error processing API data: {e}")
            import traceback
            traceback.print_exc()

    def _identify_sport_from_event(self, event_data: Dict) -> str:
        """Identify sport from event data using competition name with enhanced accuracy"""
        try:
            # First priority: Check eventTypeId if available in event data
            event_type_id = event_data.get('eventTypeId')
            if event_type_id:
                event_type_str = str(event_type_id)
                if event_type_str == '1':
                    return 'soccer'
                elif event_type_str == '7522':
                    return 'basketball'
                elif event_type_str == '6423':
                    return 'football'
                elif event_type_str == '7511':
                    return 'baseball'
                elif event_type_str == '2':
                    return 'tennis'

            # Second priority: Competition name analysis with more specific keywords
            comp_id = event_data.get('competitionId')
            if comp_id:
                comp_id_str = str(comp_id)
                if comp_id_str in self.competitions_data:
                    comp_name = self.competitions_data[comp_id_str].get('name', '').lower()

                    # Rugby Union - specific first
                    if any(x in comp_name for x in ['rugby union', 'rugby championship', 'six nations', 'rugby world cup', 'super rugby', 'premiership rugby', 'top 14']):
                        return 'rugby-union'
                    # Rugby League - specific first
                    elif any(x in comp_name for x in ['rugby league', 'nrl', 'super league', 'rugby league world cup', 'challenge cup']):
                        return 'rugby-league'
                    # Soccer - specific league names first, then general terms
                    elif any(x in comp_name for x in ['premier league', 'la liga', 'serie a', 'bundesliga', 'liga mx', 'champions league', 'world cup', 'euro', 'copa america', 'mls', 'eredivisie', 'primeira liga', 'ligue 1', 'europa league', 'copa libertadores']):
                        return 'soccer'
                    # Basketball - specific leagues
                    elif any(x in comp_name for x in ['nba', 'wnba', 'euroleague', 'ncaa basketball', 'college basketball', 'cbb', 'nbl', 'liga acb', 'basketball champions league']):
                        return 'basketball'
                    # Football - American football specific
                    elif any(x in comp_name for x in ['nfl', 'ncaaf', 'college football', 'super bowl', 'cfb', 'american football', 'xfl', 'usfl']):
                        return 'football'
                    # Baseball - MLB specific
                    elif any(x in comp_name for x in ['mlb', 'baseball', 'world series', 'american league', 'national league']):
                        return 'baseball'
                    # Tennis - specific tournaments and organizations
                    elif any(x in comp_name for x in ['itf', 'atp', 'wta', 'tennis', 'us open', 'wimbledon', 'french open', 'australian open', 'roland garros', 'us open tennis', 'grand slam']):
                        return 'tennis'
                    # Hockey
                    elif any(x in comp_name for x in ['nhl', 'stanley cup', 'ice hockey', 'khl']):
                        return 'hockey'
                    # Other sports
                    elif any(x in comp_name for x in ['ufc', 'mma', 'boxing', 'wrestling']):
                        return 'mma'
                    elif any(x in comp_name for x in ['golf', 'pga', 'masters']):
                        return 'golf'

            # Third priority: Event name analysis with context
            event_name = event_data.get('name', '').lower()

            # Rugby Union patterns
            if any(x in event_name for x in ['rugby union', 'all blacks', 'wallabies', 'springboks', 'england rugby', 'france rugby', 'ireland rugby', 'italy rugby', 'wales rugby']):
                return 'rugby-union'
            # Rugby League patterns
            elif any(x in event_name for x in ['rugby league', 'roosters', 'storm', 'broncos', 'cowboys', 'warriors', 'eels', 'panthers', 'rabbitohs']):
                return 'rugby-league'
            # Motorsport patterns
            elif any(x in event_name for x in ['motorsport', 'formula 1', 'f1', 'moto gp', 'nascar', 'indycar', 'rally', 'grand prix']):
                return 'motorsport'
            # Table Tennis patterns
            elif any(x in event_name for x in ['table tennis', 'ping pong', 'tt']):
                return 'table-tennis'
            # Soccer patterns
            elif any(x in event_name for x in ['premier league', 'la liga', 'serie a', 'bundesliga', 'champions league', 'manchester', 'barcelona', 'real madrid', 'bayern', 'juventus', 'psg', 'chelsea', 'arsenal', 'liverpool']):
                return 'soccer'
            # Basketball patterns
            elif any(x in event_name for x in ['nba', 'wnba', 'lakers', 'celtics', 'warriors', 'bulls', 'bucks', 'basketball']):
                return 'basketball'
            # Football patterns
            elif any(x in event_name for x in ['nfl', 'patriots', 'cowboys', 'packers', 'chiefs', 'eagles', 'football']):
                return 'football'
            # Baseball patterns
            elif any(x in event_name for x in ['mlb', 'dodgers', 'yankees', 'red sox', 'mets', 'baseball']):
                return 'baseball'
            # Tennis patterns
            elif any(x in event_name for x in ['tennis', 'federer', 'nadal', 'djokovic', 'serena', 'venus']):
                return 'tennis'

            # Fourth priority: Check for team name patterns that indicate sport
            # This is a fallback for when names are ambiguous
            if ' v ' in event_name or ' vs ' in event_name or ' @ ' in event_name:
                # Look for sport-specific team name patterns
                if any(team in event_name for team in ['manchester', 'barcelona', 'bayern', 'juventus', 'psg', 'chelsea', 'arsenal', 'liverpool', 'inter', 'milan', 'roma']):
                    return 'soccer'
                elif any(team in event_name for team in ['lakers', 'celtics', 'warriors', 'bulls', 'bucks', 'heat', 'nets', 'knicks']):
                    return 'basketball'
                elif any(team in event_name for team in ['patriots', 'cowboys', 'packers', 'chiefs', 'eagles', 'falcons', 'bears']):
                    return 'football'
                elif any(team in event_name for team in ['dodgers', 'yankees', 'red sox', 'mets', 'phillies', 'cardinals']):
                    return 'baseball'

            return 'unknown'
        except Exception as e:
            self.logger.error(f"Error identifying sport from event: {e}")
            return 'unknown'

    def _build_standardized_match(self, event_id: str, event_data: Dict, api_sport: str) -> Optional[Dict]:
        """Build standardized match object for UI/database integration"""
        try:
            # Identify sport from event data, not API
            sport = self._identify_sport_from_event(event_data)
            if sport == 'unknown':
                sport = api_sport  # Fallback to API sport

            # Initialize odds structure based on sport
            if sport.lower() == 'soccer':
                odds_structure = {
                    'moneyline_home': None,
                    'moneyline_draw': None,
                    'moneyline_away': None
                }
            elif sport.lower() in ['rugby-union', 'rugby-league']:
                # Rugby sports only have spread markets, no moneyline
                odds_structure = {
                    'spread_home_line': None,
                    'spread_home_odds': None,
                    'spread_away_line': None,
                    'spread_away_odds': None,
                    'total_line': None,
                    'total_over_odds': None,
                    'total_under_odds': None
                }
            elif sport.lower() == 'motorsport':
                # Motorsport has different structure - drivers with multiple market types
                odds_structure = {
                    'drivers': [],  # List of drivers with their market odds
                    'market_types': []  # Types of markets available
                }
            elif sport.lower() in ['mma', 'tennis', 'table-tennis']:
                # MMA, Tennis, and Table Tennis don't have spread/total markets - only moneyline
                odds_structure = {
                    'moneyline_home': None,
                    'moneyline_away': None
                }
            else:
                # All other sports (baseball, basketball, football) have full odds structure
                odds_structure = {
                    'moneyline_home': None,
                    'moneyline_away': None,
                    'spread_home_line': None,
                    'spread_home_odds': None,
                    'spread_away_line': None,
                    'spread_away_odds': None,
                    'total_line': None,
                    'total_over_odds': None,
                    'total_under_odds': None
                }

            # Generate game_id based on teams and date
            game_id = self._generate_game_id(event_data)

            match = {
                'match_id': event_id,
                'game_id': game_id,
                'sport': sport,
                'home_team': '',
                'away_team': '',
                'scheduled_time': '',
                'status': 'upcoming',
                'league': '',
                'odds': odds_structure,
                'metadata': {
                    'event_id': event_id,
                    'competition_id': '',
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }
            }

            # Basic info
            if 'name' in event_data:
                name = event_data['name']
                match['event_name'] = name

                # Special handling for motorsport - single competitor events
                if sport.lower() == 'motorsport':
                    # Motorsport events are like "Lewis Hamilton to Win" - single competitor
                    match['home_team'] = name.split(' to ')[0].strip()  # Competitor name
                    match['away_team'] = 'N/A'  # No opponent in motorsport
                else:
                    # Traditional head-to-head sports
                    if ' @ ' in name:
                        parts = name.split(' @ ')
                        match['away_team'] = parts[0].strip()
                        match['home_team'] = parts[1].strip()
                    elif ' vs ' in name:
                        parts = name.split(' vs ')
                        match['home_team'] = parts[0].strip()
                        match['away_team'] = parts[1].strip()
                    elif ' v ' in name:
                        parts = name.split(' v ')
                        match['home_team'] = parts[0].strip()
                        match['away_team'] = parts[1].strip()

            # Special handling for tennis
            if sport.lower() == 'tennis' and 'players' in event_data:
                players = event_data['players']
                if len(players) == 2:
                    # Pregame match
                    match['home_team'] = players[0]['name']
                    match['away_team'] = players[1]['name']
                elif len(players) > 2:
                    # Future
                    match['home_team'] = event_data.get('name', 'Unknown')
                    match['away_team'] = 'N/A'

            if 'openDate' in event_data:
                match['scheduled_time'] = event_data['openDate']

            if 'inPlay' in event_data:
                match['status'] = 'live' if event_data['inPlay'] else 'upcoming'

            # Competition info
            comp_id = event_data.get('competitionId')
            if comp_id:
                match['metadata']['competition_id'] = str(comp_id)
                comp_id_str = str(comp_id)
                if comp_id_str in self.competitions_data:
                    comp = self.competitions_data[comp_id_str]
                    if 'name' in comp:
                        match['league'] = comp['name']

            # Extract and flatten odds
            self._extract_flattened_odds(event_id, event_data, match)

            # For motorsport, we always return since it's single competitor
            # For tennis, return if we have players
            # For traditional sports, only return if we have both teams
            if sport.lower() == 'motorsport':
                return match if match['home_team'] else None
            elif sport.lower() == 'tennis':
                return match if match['home_team'] else None
            else:
                return match if (match['home_team'] and match['away_team']) else None

        except Exception as e:
            self.logger.error(f"Error building standardized match {event_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_flattened_odds(self, event_id: str, event_data: Dict, match: Dict):
        """Extract and flatten odds into standardized format"""
        try:
            # Method 1: Use marketIds from event (preferred)
            market_ids = event_data.get('marketIds', [])

            if market_ids:
                for market_id in market_ids:
                    market_id_str = str(market_id)
                    if market_id_str in self.markets_data:
                        market = self.markets_data[market_id_str]
                        self._parse_market_odds(market, match)

            # Method 2: Fallback - find markets by eventId
            if not any(match['odds'].values()):
                for market_id_str, market in self.markets_data.items():
                    market_event_id = str(market.get('eventId', ''))
                    if market_event_id == event_id:
                        self._parse_market_odds(market, match)

        except Exception as e:
            self.logger.error(f"Error extracting flattened odds for {event_id}: {e}")

    def _parse_market_odds(self, market: Dict, match: Dict):
        """Parse market odds and flatten into standardized format"""
        try:
            market_name = market.get('marketName', '').lower()
            runners = market.get('runners', [])
            sport = match.get('sport', '').lower()

            if not runners:
                return

            # Sport-specific handling
            if sport == 'soccer':
                self._parse_soccer_odds(market_name, runners, match)
            elif sport == 'baseball':
                self._parse_baseball_odds(market_name, runners, match)
            elif sport == 'motorsport':
                self._parse_motorsport_odds(market_name, runners, match)
            else:
                self._parse_standard_odds(market_name, runners, match)

        except Exception as e:
            self.logger.error(f"Error parsing market odds: {e}")

    def _parse_soccer_odds(self, market_name: str, runners: List, match: Dict):
        """Parse soccer odds - only match result (home/draw/away)"""
        try:
            # Only process match result markets for soccer
            if any(x in market_name for x in ['moneyline', 'money line', 'winner', 'match result', 'result']):
                home_odds, draw_odds, away_odds = None, None, None

                for runner in runners:
                    if isinstance(runner, dict):
                        runner_name = runner.get('runnerName', '').lower()
                        odds = self._extract_american_odds(runner)

                        # Identify home/draw/away based on runner name
                        if any(x in runner_name for x in [match['home_team'].lower(), 'home', '1']):
                            home_odds = odds
                        elif any(x in runner_name for x in ['draw', 'tie', 'x', '2']):
                            draw_odds = odds
                        elif any(x in runner_name for x in [match['away_team'].lower(), 'away', '3']):
                            away_odds = odds

                # Update soccer-specific odds structure
                match['odds']['moneyline_home'] = home_odds
                match['odds']['moneyline_draw'] = draw_odds  # Soccer specific
                match['odds']['moneyline_away'] = away_odds

        except Exception as e:
            self.logger.error(f"Error parsing soccer odds: {e}")

    def _parse_baseball_odds(self, market_name: str, runners: List, match: Dict):
        """Parse baseball odds - typically only moneyline"""
        try:
            # Baseball usually only has moneyline markets
            if any(x in market_name for x in ['moneyline', 'money line', 'winner', 'match result']):
                for runner in runners:
                    if isinstance(runner, dict):
                        runner_name = runner.get('runnerName', '')
                        odds = self._extract_american_odds(runner)

                        if runner_name == match['home_team']:
                            match['odds']['moneyline_home'] = odds
                        elif runner_name == match['away_team']:
                            match['odds']['moneyline_away'] = odds

        except Exception as e:
            self.logger.error(f"Error parsing baseball odds: {e}")

    def _parse_standard_odds(self, market_name: str, runners: List, match: Dict):
        """Parse standard odds for non-soccer sports (basketball, football, rugby, etc.)"""
        try:
            sport = match.get('sport', '').lower()

            # Moneyline markets - only for non-rugby sports
            if sport not in ['rugby-union', 'rugby-league'] and any(x in market_name for x in ['moneyline', 'money line', 'winner', 'match result']):
                for runner in runners:
                    if isinstance(runner, dict):
                        runner_name = runner.get('runnerName', '')
                        odds = self._extract_american_odds(runner)

                        # Simple team name matching (avoiding the missing method)
                        runner_lower = runner_name.lower().strip()
                        home_lower = match['home_team'].lower().strip()
                        away_lower = match['away_team'].lower().strip()

                        # Check similarity for tennis and other sports with abbreviated names
                        if sport == 'tennis':
                            # For tennis, check if runner name is contained in match team name or vice versa
                            if (runner_lower in home_lower or home_lower in runner_lower):
                                match['odds']['moneyline_home'] = odds
                            elif (runner_lower in away_lower or away_lower in runner_lower):
                                match['odds']['moneyline_away'] = odds
                        else:
                            # For other sports, use exact match first
                            if runner_name == match['home_team']:
                                match['odds']['moneyline_home'] = odds
                            elif runner_name == match['away_team']:
                                match['odds']['moneyline_away'] = odds

            # Spread/Handicap markets - available for all sports including rugby
            elif any(x in market_name for x in ['spread', 'handicap', 'point spread']):
                home_line, home_odds, away_line, away_odds = None, None, None, None

                for runner in runners:
                    if isinstance(runner, dict):
                        runner_name = runner.get('runnerName', '')
                        handicap = runner.get('handicap')
                        odds = self._extract_american_odds(runner)

                        if runner_name == match['home_team']:
                            home_line = handicap
                            home_odds = odds
                        elif runner_name == match['away_team']:
                            away_line = handicap
                            away_odds = odds

                match['odds']['spread_home_line'] = home_line
                match['odds']['spread_home_odds'] = home_odds
                match['odds']['spread_away_line'] = away_line
                match['odds']['spread_away_odds'] = away_odds

            # Total/Over-Under markets - available for all sports including rugby
            elif any(x in market_name for x in ['total', 'over/under', 'over under']):
                total_line, over_odds, under_odds = None, None, None

                for runner in runners:
                    if isinstance(runner, dict):
                        runner_name = runner.get('runnerName', '')
                        handicap = runner.get('handicap')
                        odds = self._extract_american_odds(runner)

                        if 'over' in runner_name.lower():
                            total_line = handicap
                            over_odds = odds
                        elif 'under' in runner_name.lower():
                            under_odds = odds

                match['odds']['total_line'] = total_line
                match['odds']['total_over_odds'] = over_odds
                match['odds']['total_under_odds'] = under_odds

        except Exception as e:
            self.logger.error(f"Error parsing standard odds: {e}")

    def _parse_motorsport_odds(self, market_name: str, runners: List, match: Dict):
        """Parse motorsport odds - drivers with multiple market types"""
        try:
            market_lower = market_name.lower()

            # Add market type if not already present
            if market_lower not in match['odds']['market_types']:
                match['odds']['market_types'].append(market_lower)

            # Process each runner (driver)
            for runner in runners:
                if isinstance(runner, dict):
                    driver_name = runner.get('runnerName', '').strip()
                    odds = self._extract_american_odds(runner)

                    if driver_name and odds is not None:
                        # Check if driver already exists
                        existing_driver = None
                        for driver in match['odds']['drivers']:
                            if driver['name'] == driver_name:
                                existing_driver = driver
                                break

                        if existing_driver:
                            # Update existing driver with new market odds
                            existing_driver[market_lower] = odds
                        else:
                            # Add new driver
                            driver = {
                                'name': driver_name,
                                market_lower: odds
                            }
                            match['odds']['drivers'].append(driver)

        except Exception as e:
            self.logger.error(f"Error parsing motorsport odds: {e}")

    def _extract_american_odds(self, runner: Dict) -> Optional[int]:
        """Extract American odds from runner"""
        try:
            if 'winRunnerOdds' in runner:
                odds_data = runner['winRunnerOdds']
                american_odds = odds_data.get('americanDisplayOdds', {}).get('americanOdds')
                if american_odds is not None:
                    return int(american_odds)
        except:
            pass
        return None

    def _generate_game_id(self, event_data: Dict) -> str:
        """Generate a unique game_id in the format: home_team:away_team:YYYYMMDD:HHMM"""
        try:
            # Extract teams from event name
            event_name = event_data.get('name', '')
            home_team = ''
            away_team = ''

            # Parse team names from event name
            if ' @ ' in event_name:
                parts = event_name.split(' @ ')
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].strip()
            elif ' vs ' in event_name:
                parts = event_name.split(' vs ')
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()
            elif ' v ' in event_name:
                parts = event_name.split(' v ')
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()

            # Special handling for tennis
            if 'players' in event_data:
                players = event_data['players']
                if len(players) == 2:
                    home_team = players[0]['name']
                    away_team = players[1]['name']

            # Special handling for motorsport
            if ' to ' in event_name:
                home_team = event_name.split(' to ')[0].strip()
                away_team = 'N/A'
            elif not home_team and event_name:
                # Fallback for motorsport or other single competitor events
                home_team = event_name
                away_team = 'N/A'

            # Clean team names (remove special characters, limit length)
            def clean_team_name(name: str) -> str:
                # Remove common separators and clean up
                name = name.replace(' vs ', '').replace(' v ', '').replace(' @ ', '')
                name = ''.join(c for c in name if c.isalnum() or c in ' _-').strip()
                # Replace spaces with underscores and limit length
                return name.replace(' ', '_')[:20]

            home_team_clean = clean_team_name(home_team)
            away_team_clean = clean_team_name(away_team)

            # Extract date and time from openDate
            open_date = event_data.get('openDate', '')
            date_str = '00000000'  # Default
            time_str = '0000'      # Default

            if open_date:
                try:
                    # Parse ISO format date
                    dt = datetime.fromisoformat(open_date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y%m%d')
                    time_str = dt.strftime('%H%M')
                except:
                    pass

            # Generate game_id
            game_id = f"{home_team_clean}:{away_team_clean}:{date_str}:{time_str}"
            return game_id

        except Exception as e:
            self.logger.error(f"Error generating game_id for event {event_data.get('name', 'unknown')}: {e}")
            return f"unknown:unknown:00000000:0000"

    def _find_existing_match(self, match_id: str) -> Optional[Dict]:
        """Find existing match in current matches list"""
        for match in self.matches:
            if match.get('match_id') == match_id:
                return match
        return None

    # def _find_existing_live_match(self, match_id: str) -> Optional[Dict]:
    #     """Find existing match in live matches list - DISABLED"""
    #     return None

    def _build_standardized_league(self, comp_id: str, comp_data: Dict, sport: str) -> Optional[Dict]:
        """Build standardized league object from competition data"""
        try:
            league = {
                'league_id': comp_id,
                'sport': sport,
                'name': comp_data.get('name', ''),
                'country': comp_data.get('country', ''),
                'region': comp_data.get('region', ''),
                'metadata': {
                    'competition_id': comp_id,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }
            }

            # Only return if we have a name
            if league['name']:
                return league

            return None

        except Exception as e:
            self.logger.error(f"Error building standardized league {comp_id}: {e}")
            return None

    def _find_existing_league(self, league_id: str) -> Optional[Dict]:
        """Find existing league in current leagues list"""
        for league in self.leagues:
            if league.get('league_id') == league_id:
                return league
        return None

    def _update_existing_match(self, existing_match: Dict, new_match: Dict):
        """Update existing match with new data"""
        # Update odds and other changing data
        existing_match['odds'] = new_match['odds']
        existing_match['metadata']['last_updated'] = new_match['metadata']['last_updated']
        existing_match['status'] = new_match['status']

    def _check_for_removed_matches(self, current_match_ids: set):
        """Check for matches that were removed from the website and move to history"""
        try:
            # DISABLED: History tracking is causing false positives
            # Only enable this when we need to track actual game deletions from FanDuel
            # For now, we keep all matches in current_matches.json until manually removed

            # This prevents the system from incorrectly moving active matches to history
            # due to API pagination, filtering, or temporary unavailability

            pass  # No history tracking for now

        except Exception as e:
            self.logger.error(f"Error checking for removed matches: {e}")



    # REMOVED: _is_future method - no futures collected

    def _filter_active_leagues(self):
        """Filter leagues to only include those that have active matches"""
        try:
            # Get all competition IDs that have matches (pregame only - no live matches, no futures)
            active_comp_ids = set()
            for match in self.matches:  # Only pregame matches
                comp_id = match.get('metadata', {}).get('competition_id')
                if comp_id:
                    active_comp_ids.add(str(comp_id))

            self.logger.info(f"Found {len(active_comp_ids)} active competition IDs from matches")

            # Filter leagues to only include active ones
            filtered_leagues = []
            for league in self.leagues:
                league_id = league.get('league_id')
                if league_id and str(league_id) in active_comp_ids:
                    filtered_leagues.append(league)
                else:
                    # Debug: log why league was filtered out
                    if league_id:
                        league_name = league.get('name', 'Unknown')
                        sport = league.get('sport', 'unknown')
                        self.logger.debug(f"Filtered out league {league_id} ({league_name}) sport: {sport} - no active matches")

            self.logger.info(f"Filtered leagues: {len(self.leagues)} total -> {len(filtered_leagues)} active")
            return filtered_leagues

        except Exception as e:
            self.logger.error(f"Error filtering leagues: {e}")
            return self.leagues  # Return all leagues if filtering fails

    # def _remove_duplicate_matches(self):
    #     """Remove matches that appear in both live and pregame lists - DISABLED (no live matches)"""
    #     pass

    def _save_all_data(self):
        """Save all data to JSON files with standardized schema"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = datetime.now(timezone.utc).isoformat()

            # Remove duplicate matches between live and pregame - DISABLED (no live matches)
            # self._remove_duplicate_matches()

            # Filter leagues to only include active ones
            active_leagues = self._filter_active_leagues()

            # Count totals
            total_pregame_matches = len(self.matches)
            total_live_matches = 0  # DISABLED - dedicated script handles live matches
            total_futures = 0  # REMOVED - no futures collected
            total_history = 0  # Disabled history tracking

            # 1. PREGAME MATCHES
            pregame_file = os.path.join(script_dir, "fanduel_pregame.json")
            pregame_data = {
                'metadata': {
                    'session_id': self.session_id,
                    'timestamp': timestamp,
                    'collector_version': 'master_v2.0',
                    'total_records': total_pregame_matches,
                    'data_type': 'pregame'
                },
                'data': {
                    'matches': self.matches,
                    'leagues': active_leagues,  # Use filtered active leagues
                    'teams': self.teams
                },
                'pagination': {
                    'page': 1,
                    'limit': 1000,
                    'total_pages': 1
                }
            }
            with open(pregame_file, 'w', encoding='utf-8') as f:
                json.dump(pregame_data, f, indent=2, ensure_ascii=False)

            # 2. LIVE MATCHES - DISABLED (dedicated script handles live matches)
            # live_file = os.path.join(script_dir, "fanduel_live.json")
            # ... live matches file creation disabled ...

            # 3. FUTURES FILE REMOVED - no futures collected

            # 4. MATCH HISTORY (REMOVED GAMES) - DISABLED
            # Only create history file when we actually have removed matches
            # history_file = os.path.join(script_dir, "fanduel_history.json")
            # ... history saving code disabled ...

            # 5. STATISTICS - Enhanced with cycle analysis
            stats_file = os.path.join(script_dir, "fanduel_statistics.json")

            # Analyze API calls by sport and URL patterns
            sport_api_counts = {}
            url_cycle_counts = {}
            sport_update_frequency = {}

            for api in self.captured_apis:
                sport = api.get('sport', 'unknown')
                url = api.get('url', '')

                # Count APIs per sport
                if sport not in sport_api_counts:
                    sport_api_counts[sport] = 0
                sport_api_counts[sport] += 1

                # Count URL patterns
                url_key = url.split('?')[0]  # Remove query params for grouping
                if url_key not in url_cycle_counts:
                    url_cycle_counts[url_key] = 0
                url_cycle_counts[url_key] += 1

            # Calculate update frequency (APIs per minute based on session duration)
            session_start = datetime.strptime(self.session_id, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            session_duration_minutes = (datetime.now(timezone.utc) - session_start).total_seconds() / 60
            if session_duration_minutes > 0:
                for sport, count in sport_api_counts.items():
                    sport_update_frequency[sport] = round(count / session_duration_minutes, 2)

            # Find most and least active sports
            most_active_sport = max(sport_api_counts.items(), key=lambda x: x[1]) if sport_api_counts else ('none', 0)
            least_active_sport = min(sport_api_counts.items(), key=lambda x: x[1]) if sport_api_counts else ('none', 0)

            stats_data = {
                'session_id': self.session_id,
                'timestamp': timestamp,
                'total_api_calls': len(self.captured_apis),
                'total_events': len(self.events_data),
                'total_markets': len(self.markets_data),
                'total_pregame_matches': total_pregame_matches,
                'total_live_matches': total_live_matches,
                'total_futures': 0,
                'total_history': total_history,
                'api_calls': self.captured_apis[-10:] if self.captured_apis else [],  # Last 10

                # Enhanced analytics
                'sport_api_breakdown': sport_api_counts,
                'url_pattern_counts': url_cycle_counts,
                'sport_update_frequency_per_minute': sport_update_frequency,
                'most_active_sport': {
                    'sport': most_active_sport[0],
                    'api_calls': most_active_sport[1]
                },
                'least_active_sport': {
                    'sport': least_active_sport[0],
                    'api_calls': least_active_sport[1]
                },
                'session_duration_minutes': round(session_duration_minutes, 2)
            }
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Error saving data: {e}")

    async def open_sport_tabs_and_capture_all_apis_parallel(self):
        """Open homepage first in separate tab, then trigger sport tabs sequentially to avoid verification blocks"""
        self.logger.info("Opening homepage first, then triggering sport tabs sequentially...")

        # Define all sport URLs
        sport_urls = [
            ('soccer', 'https://sportsbook.fanduel.com/soccer'),
            ('basketball', 'https://sportsbook.fanduel.com/basketball'),
            ('football', 'https://sportsbook.fanduel.com/football'),
            ('baseball', 'https://sportsbook.fanduel.com/baseball'),
            ('boxing', 'https://sportsbook.fanduel.com/boxing'),
            ('golf', 'https://sportsbook.fanduel.com/golf'),
            ('table-tennis', 'https://sportsbook.fanduel.com/table-tennis'),
            ('tennis', 'https://sportsbook.fanduel.com/tennis'),
            ('cricket', 'https://sportsbook.fanduel.com/cricket'),
            ('darts', 'https://sportsbook.fanduel.com/darts'),
            ('ice-hockey', 'https://sportsbook.fanduel.com/ice-hockey'),
            ('aussie-rules', 'https://sportsbook.fanduel.com/aussie-rules'),
            ('lacrosse', 'https://sportsbook.fanduel.com/lacrosse'),
            ('cycling', 'https://sportsbook.fanduel.com/cycling'),
            ('motorsport', 'https://sportsbook.fanduel.com/motorsport'),
            ('rugby-league', 'https://sportsbook.fanduel.com/rugby-league'),
            ('rugby-union', 'https://sportsbook.fanduel.com/rugby-union')
        ]

        # PHASE 1: Create and navigate to homepage first to establish session
        if self.context is None:
            raise Exception("Browser context not initialized")

        self.logger.info("Creating homepage tab...")
        try:
            homepage_page = await self.context.new_page()
            self.sport_pages['homepage'] = homepage_page
            self.logger.info("Homepage tab created")
        except Exception as e:
            self.logger.error(f"Error creating homepage page: {e}")
            return

        # Navigate to homepage first
        homepage_url = 'https://sportsbook.fanduel.com/'
        self.logger.info("Attempting homepage navigation for session establishment...")
        success = await self._navigate_sport_page('homepage', homepage_url, delay=0)
        if not success:
            self.logger.warning("⚠️ Homepage navigation failed - this may affect session establishment")
            self.logger.warning("Continuing with sport tabs, but verification blocks are more likely")
        else:
            self.logger.info("✅ Homepage loaded successfully - session established for better access")

        # Wait a bit after homepage loads before opening sport tabs
        await asyncio.sleep(3)

        # PHASE 2: Create all sport pages
        for sport_name, sport_url in sport_urls:
            try:
                sport_page = await self.context.new_page()
                self.sport_pages[sport_name] = sport_page
            except Exception as e:
                self.logger.error(f"Error creating page for {sport_name}: {e}")

        self.logger.info(f"All sport tabs created - {len(self.sport_pages)} total tabs ready (including homepage)")

        # Now navigate to all pages sequentially with 2-3 second delays to avoid detection
        verification_blocked = False
        blocked_sport = None
        blocked_index = -1
        successfully_loaded = []

        for i, (sport_name, sport_url) in enumerate(sport_urls):
            if sport_name in self.sport_pages:
                self.logger.info(f"Opening {sport_name.upper()} tab ({i+1}/{len(sport_urls)})")
                success = await self._navigate_sport_page(sport_name, sport_url, delay=0)  # No delay since we're doing sequentially

                if not success:
                    verification_blocked = True
                    blocked_sport = sport_name
                    blocked_index = i
                    self.logger.warning(f"🚫 PAGE LOAD BLOCK DETECTED ON {sport_name.upper()}")
                    self.logger.warning("⏳ WAITING FOR PAGE TO LOAD...")

                    # Wait for page to load
                    resolution_success = await self._wait_for_verification_resolution(sport_name)

                    if resolution_success:
                        successfully_loaded.append(sport_name)
                        self.logger.info(f"✅ PAGE LOADED SUCCESSFULLY: {sport_name.upper()}")
                        verification_blocked = False  # Reset flag since it's resolved
                    else:
                        self.logger.error(f"❌ PAGE LOAD FAILED: {sport_name.upper()} - SKIPPING")
                        # Continue with next tab instead of stopping completely

                else:
                    successfully_loaded.append(sport_name)
                    self.logger.info(f"✅ {sport_name.upper()} loaded immediately")

                # Wait 2-3 seconds between each tab to avoid triggering verification
                if i < len(sport_urls) - 1:
                    await asyncio.sleep(2.5)  # 2.5 seconds between tabs

        # Report final status
        total_sports_attempted = len(sport_urls)
        total_sports_loaded = len(successfully_loaded)

        if total_sports_loaded == 0:
            self.logger.error("❌ NO SPORT TABS LOADED SUCCESSFULLY")
            self.logger.error("This indicates a fundamental connection or verification issue")
            return  # Exit early if no tabs loaded
        elif total_sports_loaded < total_sports_attempted:
            self.logger.warning(f"⚠️  PARTIAL SUCCESS: {total_sports_loaded}/{total_sports_attempted} sports loaded")
            self.logger.warning(f"Successfully loaded: {', '.join(successfully_loaded)}")
            self.logger.warning("Script will continue with available tabs")
        else:
            self.logger.info(f"✅ ALL TABS LOADED: {total_sports_loaded}/{total_sports_attempted} sports ready for API capture")

    async def _navigate_sport_page(self, sport_name: str, sport_url: str, delay: int = 0):
        """Navigate to a single sport page with proper loading waits and verification detection"""
        try:
            # Staggered delay to avoid simultaneous requests
            if delay > 0:
                await asyncio.sleep(delay)

            page = self.sport_pages[sport_name]
            self.logger.info(f"Loading {sport_name} tab: {sport_url}")

            # Navigate with proper waiting
            await page.goto(sport_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            await asyncio.sleep(3)  # Wait for API loading

            # Check for verification blocks or queries
            verification_detected = await self._check_for_verification_block(page, sport_name)
            if verification_detected:
                self.logger.warning(f"⚠️  VERIFICATION BLOCK DETECTED on {sport_name.upper()} - pausing tab opening")
                return False  # Return False to indicate verification block

            # Scroll to trigger API calls
            for scroll in range(2):
                await page.mouse.wheel(0, 300)
                await asyncio.sleep(0.5)

            self.logger.info(f"✓ {sport_name.upper()} loaded and ready")
            return True  # Success

        except Exception as e:
            self.logger.error(f"Error loading {sport_name} tab: {e}")
            return False

    async def _check_for_verification_block(self, page, sport_name: str) -> bool:
        """Check if the page has actual verification blocks or challenges"""
        try:
            # Check page title for verification indicators - be more specific
            title = await page.title()
            title_lower = title.lower()

            # More specific title indicators that indicate actual blocks
            title_verification_indicators = [
                'verification required', 'verify your identity', 'security verification',
                'access verification', 'verification challenge', 'blocked', 'access denied',
                'rate limit exceeded', 'too many requests', 'suspicious activity detected'
            ]

            if any(indicator in title_lower for indicator in title_verification_indicators):
                self.logger.warning(f"Verification detected in title: '{title}' for {sport_name}")
                return True

            # Check for specific verification elements first (more reliable)
            verification_selectors = [
                '.recaptcha', '#recaptcha', '[class*="recaptcha"]', '[id*="recaptcha"]',
                '.hcaptcha', '#hcaptcha', '[class*="hcaptcha"]', '[id*="hcaptcha"]',
                '.captcha', '#captcha', '[class*="captcha"]', '[id*="captcha"]',
                '[class*="verify"]', '[id*="verify"]', '[class*="verification"]',
                '[data-testid*="captcha"]', '[data-testid*="verify"]',
                '.robot', '#robot', '[class*="robot"]', '[id*="robot"]',
                '.challenge', '#challenge', '[class*="challenge"]'
            ]

            for selector in verification_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # Double-check by getting element text to confirm it's a verification element
                        element_text = await element.inner_text()
                        element_text_lower = element_text.lower()
                        if any(word in element_text_lower for word in ['verify', 'robot', 'captcha', 'challenge', 'prove']):
                            self.logger.warning(f"Verification element found ({selector}) for {sport_name}")
                            return True
                except:
                    pass

            # Check page content for specific verification phrases (less likely to cause false positives)
            body_text = await page.inner_text('body')
            body_lower = body_text.lower()

            # More specific content indicators that indicate actual verification challenges
            content_verification_indicators = [
                'are you a robot', 'prove you are human', 'complete the captcha',
                'security verification required', 'verification challenge',
                'access has been blocked', 'rate limit exceeded',
                'too many requests from your network', 'suspicious activity detected',
                'please verify you are not a robot', 'human verification required'
            ]

            if any(indicator in body_lower for indicator in content_verification_indicators):
                self.logger.warning(f"Verification challenge detected in page content for {sport_name}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking for verification on {sport_name}: {e}")
            return False

    async def _wait_for_verification_resolution(self, sport_name: str):
        """Wait for page to actually load by checking content and network status"""
        self.logger.info(f"⏳ Waiting for {sport_name.upper()} page to load...")
        self.logger.info("Checking page content and network status")

        max_wait_time = 60  # 1 minute max wait (reduced from 5 minutes)
        check_interval = 3   # Check every 3 seconds

        page = self.sport_pages[sport_name]

        for waited in range(0, max_wait_time, check_interval):
            await asyncio.sleep(check_interval)

            try:
                # Check if page has actual content (not just error page)
                body_text = await page.inner_text('body')
                title = await page.title()

                # Check for successful page load indicators
                content_length = len(body_text)
                has_sports_content = any(keyword in body_text.lower() for keyword in [
                    'odds', 'bet', 'sports', 'football', 'basketball', 'soccer', 'baseball',
                    'moneyline', 'spread', 'total', 'fanduel'
                ])

                # Check if title indicates successful load (not error)
                title_lower = title.lower()
                is_error_page = any(error in title_lower for error in [
                    'error', 'blocked', 'access denied', 'verification required',
                    'connection aborted', 'site cannot be reached'
                ])

                self.logger.debug(f"{sport_name}: Content length={content_length}, Has sports content={has_sports_content}, Title='{title}', Is error={is_error_page}")

                # Consider page loaded if it has substantial content and sports-related text
                if content_length > 1000 and has_sports_content and not is_error_page:
                    self.logger.info(f"✅ PAGE LOADED SUCCESSFULLY: {sport_name.upper()} (Content: {content_length} chars, Title: '{title}')")
                    return True

                # If we have some content but it's an error page, wait longer
                elif content_length > 100 and is_error_page:
                    self.logger.debug(f"Error page detected for {sport_name}, waiting...")
                    continue

                # If page has minimal content, it might still be loading
                elif content_length < 100:
                    self.logger.debug(f"Minimal content for {sport_name}, still loading...")
                    continue

            except Exception as check_error:
                self.logger.debug(f"Error checking page status for {sport_name}: {check_error}")
                continue

            if waited % 15 == 0:  # Log every 15 seconds
                remaining = max_wait_time - waited
                self.logger.info(f"Still waiting for {sport_name} to load... ({remaining}s remaining)")

        # If we get here, page didn't load properly
        try:
            final_title = await page.title()
            final_content = await page.inner_text('body')
            self.logger.error(f"❌ PAGE LOAD FAILED: {sport_name.upper()}")
            self.logger.error(f"   Final title: '{final_title}'")
            self.logger.error(f"   Content length: {len(final_content)} chars")
            if len(final_content) < 500:
                self.logger.error(f"   Content preview: {final_content[:200]}...")
        except Exception as e:
            self.logger.error(f"❌ Could not get final page status for {sport_name}: {e}")

        return False

    def _load_leagues_analysis(self):
        """Load leagues analysis JSON to understand data structure"""
        try:
            analysis_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fanduel_leagues_analysis.json")
            if os.path.exists(analysis_file):
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning("Leagues analysis file not found, proceeding without it")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading leagues analysis: {e}")
            return {}

    async def interact_with_tabs(self):
        """Minimal interaction - just scroll to trigger some API calls without clicking tabs"""
        self.logger.info("Minimal interaction - scrolling sport tabs to trigger API calls...")

        # Just scroll on each sport page to trigger some API calls (skip homepage)
        for sport_name, page in self.sport_pages.items():
            if sport_name == 'homepage':
                continue  # Skip homepage for scrolling interactions
            try:
                # Scroll down to load more content and trigger some API calls
                for _ in range(5):
                    await page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.5)
                self.logger.info(f"✓ {sport_name} scrolled")
            except Exception as e:
                self.logger.error(f"Error scrolling {sport_name}: {e}")

        self.logger.info("Minimal interactions complete")

    async def monitor(self, duration: int = 45):
        """Enhanced monitoring for maximum API capture"""
        self.logger.info(f"Starting {duration}s enhanced monitoring for maximum API capture...")

        start_time = time.time()
        cycle = 0

        while time.time() - start_time < duration:
            cycle += 1
            elapsed = int(time.time() - start_time)

            # Dynamic interaction based on analysis findings
            if cycle % 8 == 0:  # More frequent interaction
                sport_names = [name for name in self.sport_pages.keys() if name != 'homepage']  # Exclude homepage
                if sport_names:
                    page = self.sport_pages[sport_names[cycle % len(sport_names)]]
                    try:
                        # Varied scrolling patterns to trigger different API calls
                        if cycle % 16 == 0:
                            # Deep scroll for more data
                            await page.mouse.wheel(0, 500)
                        else:
                            # Light scroll to trigger updates
                            await page.mouse.wheel(0, 200)
                    except:
                        pass

            await asyncio.sleep(1.5)  # Slightly faster cycle

            if elapsed % 10 == 0 and elapsed > 0:  # More frequent status updates
                async with self.data_lock:
                    total_matches = len(self.matches)
                    total_events = len(self.events_data)
                    total_markets = len(self.markets_data)
                    self.logger.info(f"⏱️  {elapsed}s | APIs: {len(self.captured_apis)} | Events: {total_events} | Markets: {total_markets} | Matches: {total_matches}")

        self.logger.info("Enhanced monitoring complete - maximum API capture achieved")

    async def fetch_api_parallel(self, url: str, sport: str):
        """Fetch a single API endpoint and process it"""
        try:
            self.logger.info(f"🔗 Fetching {sport.upper()} API: {url}")

            # Use browser context to fetch the API (bypasses CORS)
            if self.context is None:
                raise Exception("Browser context not initialized")
            response = await self.context.request.get(url)
            if response.status == 200:
                data = await response.json()

                # Check if this has attachments with events/markets
                if self._has_sports_data(data):
                    async with self.data_lock:
                        self.captured_apis.append({
                            'url': url,
                            'sport': sport,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })

                        # Process the data IMMEDIATELY
                        self._process_api_data(data, sport)

                        # SAVE IMMEDIATELY after processing
                        self._save_all_data()
                        self.logger.info(f"💾 FanDuel data saved immediately: {len(self.matches)} matches")

                    self.logger.info(f"📡 {sport.upper()} API captured | Events: {len(self.events_data)} | Markets: {len(self.markets_data)} | SAVED")

        except Exception as e:
            self.logger.error(f"Error fetching {sport} API {url}: {e}")

    async def fetch_all_apis_parallel(self):
        """Fetch all known API endpoints in parallel for maximum league capture - fast and efficient"""
        self.logger.info("🚀 Starting parallel API fetching for all league data...")

        # Define all API endpoints from the leagues analysis and additional patterns
        api_endpoints = [
            # Main sport pages (from leagues analysis)
            ('soccer', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=1&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('basketball', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7522&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('football', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=6423&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('baseball', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7511&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('mma', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=3&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('golf', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=5&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('tennis', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=2&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('cricket', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=4&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('darts', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('hockey', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7524&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('aussie-rules', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=61420&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('lacrosse', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7514&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('cycling', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=11&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('rugby-league', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=12&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('rugby-union', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=8&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('table-tennis', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=6&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),

            # Additional API patterns that may contain more league data
            ('homepage', 'https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=HOMEPAGE&prominentCard=false&pulseScalingEnable=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York'),
            ('context', 'https://api.sportsbook.fanduel.com/sbapi/application-context?dataEntries=POPULAR_BETTING,QUICK_LINKS,AZ_BETTING,EVENT_TYPES,TEASER_COMPS&_ak=FhMFpcPWXMeyZxOx')
        ]

        # Fetch all APIs in parallel for maximum speed
        tasks = [self.fetch_api_parallel(url, sport) for sport, url in api_endpoints]
        await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.info("✅ Parallel API fetching complete - all league data captured quickly")

    async def run(self, monitoring_duration: int = 0):
        """Optimized main run method - parallel API fetching first, then browser navigation for additional coverage
        Args:
            monitoring_duration: Duration in minutes for realtime monitoring (0 = infinite)
        """
        try:
            await self.setup_browser()

            # PHASE 1: Parallel API fetching for maximum league capture
            await self.fetch_all_apis_parallel()

            # PHASE 2: Browser navigation for any additional APIs
            await self.open_sport_tabs_and_capture_all_apis_parallel()
            await self.monitor(duration=45)  # Extended monitoring for parallel tabs

            # Enhanced final summary based on analysis insights
            async with self.data_lock:
                total_matches = len(self.matches)
                total_apis = len(self.captured_apis)
                total_events = len(self.events_data)
                total_markets = len(self.markets_data)

                self.logger.info("="*90)
                self.logger.info("COLLECTION COMPLETE - PARALLEL API CAPTURE MODE")
                self.logger.info("="*90)
                self.logger.info(f"Total API Calls Captured: {total_apis}")
                self.logger.info(f"Total Events Processed: {total_events}")
                self.logger.info(f"Total Markets Processed: {total_markets}")
                self.logger.info(f"Total Matches: {total_matches}")
                self.logger.info("")

                # Enhanced sports breakdown
                sports_count = {}
                api_sports = {}

                # Count APIs by sport
                for api in self.captured_apis:
                    sport = api.get('sport', 'unknown')
                    if sport not in api_sports:
                        api_sports[sport] = 0
                    api_sports[sport] += 1

                # Count matches by sport (no futures)
                for match in self.matches:
                    sport = match.get('sport', 'unknown')
                    if sport not in sports_count:
                        sports_count[sport] = {'matches': 0}

                    sports_count[sport]['matches'] += 1

                self.logger.info("API CAPTURE BREAKDOWN:")
                for sport, api_count in api_sports.items():
                    matches = sports_count.get(sport, {}).get('matches', 0)
                    self.logger.info(f"  {sport.upper()}: {api_count} APIs | {matches} matches")

                self.logger.info("")
                self.logger.info("MATCH TYPE BREAKDOWN:")
                self.logger.info(f"  Live Matches: 0 (handled by dedicated script)")
                self.logger.info(f"  Pregame Matches: {len(self.matches)}")
                self.logger.info(f"  Total Matches: {len(self.matches)} (pregame only)")

                self.logger.info("")

                self.logger.info("OPTIMIZATION RESULTS:")
                self.logger.info(f"  - Parallel API fetching for all league data capture")
                self.logger.info(f"  - Direct endpoint access bypassing browser limitations")
                self.logger.info(f"  - Browser navigation for additional coverage")
                self.logger.info(f"  - Real-time data processing and immediate saving")
                self.logger.info("")

                self.logger.info("Files saved with comprehensive data:")
                self.logger.info("  - fanduel_pregame.json (upcoming matches)")
                self.logger.info("  - fanduel_statistics.json (detailed stats)")
                self.logger.info("="*90)

            monitoring_duration_seconds = monitoring_duration * 60 if monitoring_duration > 0 else float('inf')
            self.logger.info(f"Starting continuous realtime monitoring for pregame updates... (Duration: {'infinite' if monitoring_duration == 0 else f'{monitoring_duration} minutes'})")
            start_time = time.time()
            update_count = 0

            while time.time() - start_time < monitoring_duration_seconds:
                await asyncio.sleep(2.5)  # Update every 2.5 seconds for faster pregame data
                update_count += 1
                elapsed = int(time.time() - start_time)

                # Trigger potential updates by scrolling on sport pages (skip homepage)
                for sport_name, page in self.sport_pages.items():
                    if sport_name == 'homepage':
                        continue  # Skip homepage for scrolling
                    try:
                        await page.mouse.wheel(0, 100)
                        await asyncio.sleep(0.3)
                    except:
                        pass

                # Log progress immediately every cycle
                async with self.data_lock:
                    total_matches = len(self.matches)
                    total_events = len(self.events_data)
                    total_markets = len(self.markets_data)
                    self.logger.info(f"⏱️  {elapsed}s | Cycle: {update_count} | Events: {total_events} | Markets: {total_markets} | Matches: {total_matches}")

            if monitoring_duration > 0:
                self.logger.info(f"⏰ Monitoring duration ({monitoring_duration} minutes) completed!")

        except KeyboardInterrupt:
            self.logger.info("\n" + "="*80)
            self.logger.info("REALTIME MONITORING STOPPED BY USER")
            self.logger.info("="*80)
            async with self.data_lock:
                total_matches = len(self.matches)
                total_apis = len(self.captured_apis)
                total_events = len(self.events_data)
                total_markets = len(self.markets_data)

                self.logger.info("="*90)
                self.logger.info("MONITORING COMPLETE - REALTIME PREGAME MONITORING")
                self.logger.info("="*90)
                self.logger.info(f"Total API Calls Captured: {total_apis}")
                self.logger.info(f"Total Events Processed: {total_events}")
                self.logger.info(f"Total Markets Processed: {total_markets}")
                self.logger.info(f"Total Matches: {total_matches}")
                self.logger.info("")

                sports_count = {}
                api_sports = {}

                for api in self.captured_apis:
                    sport = api.get('sport', 'unknown')
                    if sport not in api_sports:
                        api_sports[sport] = 0
                    api_sports[sport] += 1

                for match in self.matches:
                    sport = match.get('sport', 'unknown')
                    if sport not in sports_count:
                        sports_count[sport] = {'matches': 0}

                    sports_count[sport]['matches'] += 1

                self.logger.info("API CAPTURE BREAKDOWN:")
                for sport, api_count in api_sports.items():
                    matches = sports_count.get(sport, {}).get('matches', 0)
                    self.logger.info(f"  {sport.upper()}: {api_count} APIs | {matches} matches")

                self.logger.info("")
                self.logger.info("MATCH TYPE BREAKDOWN:")
                self.logger.info(f"  Live Matches: 0 (handled by dedicated script)")
                self.logger.info(f"  Pregame Matches: {len(self.matches)}")
                self.logger.info(f"  Total Matches: {len(self.matches)} (pregame only)")

                self.logger.info("")
                self.logger.info("REALTIME MONITORING RESULTS:")
                self.logger.info(f"  - Continuous monitoring for pregame updates")
                self.logger.info(f"  - Real-time data processing and saving")
                self.logger.info("")

                self.logger.info("Files saved with comprehensive data:")
                self.logger.info("  - fanduel_pregame.json (upcoming matches)")
                self.logger.info("  - fanduel_statistics.json (detailed stats)")
                self.logger.info("="*90)

        except Exception as e:
            self.logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup browser and Chrome processes"""
        self.logger.info("Cleaning up...")
        
        for page in self.sport_pages.values():
            try:
                await page.close()
            except:
                pass

        try:
            if self.browser:
                await self.browser.close()
        except:
            pass

        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

        try:
            if self.chrome_process:
                self.chrome_process.terminate()
                self.chrome_process.wait(timeout=5)
        except:
            pass
        
        # Kill any remaining Chrome processes
        cleanup_chrome_processes()

        self.logger.info("Cleanup complete")

async def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='FanDuel Master Collector')
    parser.add_argument('duration', nargs='?', type=int, default=0,
                       help='Monitoring duration in minutes (0 = infinite)')
    parser.add_argument('--headless', action='store_true',
                       help='Run Chrome in headless mode')

    args = parser.parse_args()
    
    # Clean up any zombie Chrome processes from previous runs
    logging.info("🧹 Cleaning up any existing Chrome processes...")
    cleanup_chrome_processes()
    
    # Acquire lock to prevent multiple instances
    if not acquire_lock():
        logging.error("❌ Another instance is already running. Exiting.")
        sys.exit(1)
    
    # Register cleanup handlers
    def signal_handler(sig, frame):
        logging.info(f"\n⚠️ Received signal {sig}, cleaning up...")
        cleanup_chrome_processes()
        release_lock()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(lambda: (cleanup_chrome_processes(), release_lock()))

    # Set headless mode if requested
    if args.headless:
        os.environ['PLAYWRIGHT_HEADLESS'] = '1'

    try:
        collector = FanDuelMasterCollector()
        await collector.run(monitoring_duration=args.duration)
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
    finally:
        cleanup_chrome_processes()
        release_lock()

if __name__ == "__main__":
    asyncio.run(main())