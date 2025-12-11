#!/usr/bin/env python3

import asyncio
import json
import time
import os
import subprocess
import tempfile
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Set
from playwright.async_api import async_playwright

class FanDuelLiveMonitor:
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_port = 9229
        
        self.playwright = None
        self.browser = None
        self.chrome_process = None
        self.context = None
        
        self.api_urls = {}
        self.live_matches = {}
        self.event_details = {}
        self.market_data = {}
        self.event_to_markets = {}  # NEW: Mapping from events to their market IDs
        
        # Track save timing (simple time-based, not delta)
        self.last_save_time = 0
        
        # Track discovered API endpoints for concurrent polling
        self.discovered_apis = set()
        self.api_polling_tasks = [] 
        
        self.data_lock = asyncio.Lock()
        self.setup_logging()
        
        print(f"[INIT] Real-Time Live Monitor - Session: {self.session_id}")
    
    def setup_logging(self):
        self.logger = logging.getLogger('live_monitor')
        self.logger.setLevel(logging.INFO)
        
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        log_file = os.path.join(logs_dir, f'live_monitor_{self.session_id}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info("="*80)
        self.logger.info("REAL-TIME LIVE MONITOR WITH ODDS")
        self.logger.info("="*80)
    
    def launch_chrome(self):
        chrome_exe = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        
        if not os.path.exists(chrome_exe):
            raise Exception(f"Chrome not found at {chrome_exe}")
        
        profile_dir = os.path.join(tempfile.gettempdir(), f"fd_live_{self.session_id}")
        os.makedirs(profile_dir, exist_ok=True)
        
        cmd = [
            chrome_exe,
            f'--remote-debugging-port={self.debug_port}',
            f'--user-data-dir={profile_dir}',
            '--no-first-run',
            '--disable-blink-features=AutomationControlled',
            '--start-maximized'
        ]
        
        self.logger.info("Launching Chrome...")
        self.chrome_process = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.logger.info(f"Chrome launched (PID: {self.chrome_process.pid})")
    
    async def setup_browser(self):
        self.logger.info("Connecting to Chrome...")
        
        self.playwright = await async_playwright().start()
        self.launch_chrome()
        await asyncio.sleep(3)
        
        self.browser = await self.playwright.chromium.connect_over_cdp(
            f"http://localhost:{self.debug_port}"
        )
        self.context = self.browser.contexts[0]
        self.context.on('response', self.response_handler)
        
        self.logger.info("Connected - Capturing all APIs")
    
    async def response_handler(self, response):
        try:
            url = response.url
            
            if 'fanduel.com' in url and response.status == 200:
                if not any(ext in url for ext in ['.png', '.jpg', '.css', '.js', '.woff', '.ttf', '.svg', '.ico', '.woff2', '.gif', '.webp']):
                    
                    # Track ALL sportsbook API endpoints for polling (not just in-play)
                    if 'api.sportsbook.fanduel.com' in url:
                        # Extract base URL without dynamic query parameters  
                        base_url = url.split('?')[0] if '?' in url else url
                        if base_url not in self.discovered_apis:
                            self.discovered_apis.add(base_url)
                            self.logger.info(f"📡 Discovered API: {base_url}")
                    
                    try:
                        body = await response.body()
                        data = json.loads(body.decode('utf-8'))
                        
                        async with self.data_lock:
                            self._process_api_response(url, data)
                    
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        pass
        
        except Exception as e:
            pass
    
    def _process_api_response(self, url: str, data: Any):
        event_ids = self._extract_event_ids(data)
        
        for event_id in event_ids:
            if event_id not in self.api_urls:
                self.api_urls[event_id] = []
            
            if url not in [entry['url'] for entry in self.api_urls[event_id]]:
                self.api_urls[event_id].append({
                    'url': url,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        
        if '/sbapi/in-play' in url:
            self._process_in_play_api(data)
        
        if 'inplayservice/v1.0/livedata' in url:
            self._process_live_score_data(data)
        
        self._merge_and_save()
    
    def _extract_event_ids(self, data: Any, event_ids: Set[int] = None) -> Set[int]:
        if event_ids is None:
            event_ids = set()

        if isinstance(data, dict):
            if 'eventId' in data:
                try:
                    event_ids.add(int(data['eventId']))
                except:
                    pass

            for value in data.values():
                self._extract_event_ids(value, event_ids)

        elif isinstance(data, list):
            for item in data:
                self._extract_event_ids(item, event_ids)

        return event_ids

    def _generate_game_id(self, event_data: Dict) -> str:
        """Generate a unique game_id in the format: home_team:away_team:YYYYMMDD:HHMM"""
        try:
            # Extract teams from event name or details
            event_name = ''
            if 'eventId' in event_data and event_data['eventId'] in self.event_details:
                event_name = self.event_details[event_data['eventId']].get('name', '')
            else:
                # Try to get from the event_data itself
                event_name = event_data.get('name', '')

            home_team = ''
            away_team = ''

            # Parse team names from event name
            if ' @ ' in event_name:
                parts = event_name.split(' @ ')
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].strip()
            elif ' v ' in event_name:
                parts = event_name.split(' v ')
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()
            elif ' vs ' in event_name:
                parts = event_name.split(' vs ')
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()

            # Clean team names (remove special characters, limit length)
            def clean_team_name(name: str) -> str:
                # Remove common separators and clean up
                name = name.replace(' vs ', '').replace(' v ', '').replace(' @ ', '')
                name = ''.join(c for c in name if c.isalnum() or c in ' _-').strip()
                # Replace spaces with underscores and limit length
                return name.replace(' ', '_')[:20]

            home_team_clean = clean_team_name(home_team)
            away_team_clean = clean_team_name(away_team)

            # Extract date and time from openDate or current time
            date_str = '00000000'  # Default
            time_str = '0000'      # Default

            # Try to get from event details first
            if 'eventId' in event_data and event_data['eventId'] in self.event_details:
                open_date = self.event_details[event_data['eventId']].get('openDate', '')
                if open_date:
                    try:
                        # Parse ISO format date
                        dt = datetime.fromisoformat(open_date.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y%m%d')
                        time_str = dt.strftime('%H%M')
                    except:
                        pass

            # Fallback to current time if no openDate
            if date_str == '00000000':
                now = datetime.now(timezone.utc)
                date_str = now.strftime('%Y%m%d')
                time_str = now.strftime('%H%M')

            # Generate game_id
            game_id = f"{home_team_clean}:{away_team_clean}:{date_str}:{time_str}"
            return game_id

        except Exception as e:
            self.logger.error(f"Error generating game_id for event {event_data.get('eventId', 'unknown')}: {e}")
            return f"unknown:unknown:00000000:0000"
    
    def _extract_odds_from_runners(self, runners: List[Dict]) -> Dict:
        """Extract odds from FanDuel's winRunnerOdds format"""
        odds_info = {}
        
        for runner in runners:
            selection_id = runner.get('selectionId')
            runner_name = runner.get('runnerName', '')
            runner_status = runner.get('runnerStatus', '')
            handicap = runner.get('handicap', 0)
            
            if selection_id and 'winRunnerOdds' in runner:
                win_odds = runner['winRunnerOdds']
                
                odds_data = {
                    'selection_id': selection_id,
                    'name': runner_name,
                    'status': runner_status,
                    'handicap': handicap
                }
                
                # Extract American odds
                if 'americanDisplayOdds' in win_odds:
                    american_odds = win_odds['americanDisplayOdds']
                    odds_data['american_odds'] = american_odds.get('americanOdds', 0)
                
                # Extract decimal odds
                if 'trueOdds' in win_odds and 'decimalOdds' in win_odds['trueOdds']:
                    decimal_odds = win_odds['trueOdds']['decimalOdds']
                    odds_data['decimal_odds'] = decimal_odds.get('decimalOdds', 0)
                
                # Extract fractional odds
                if 'trueOdds' in win_odds and 'fractionalOdds' in win_odds['trueOdds']:
                    frac_odds = win_odds['trueOdds']['fractionalOdds']
                    odds_data['fractional_odds'] = f"{frac_odds.get('numerator', 0)}/{frac_odds.get('denominator', 1)}"
                
                odds_info[str(selection_id)] = odds_data
        
        return odds_info
    
    def _process_layout_section(self, layout_data: Dict):
        """Extract event-to-market mappings from the layout section"""
        try:
            if 'cards' not in layout_data:
                return
            
            cards = layout_data['cards']
            
            for card_id, card_data in cards.items():
                if not isinstance(card_data, dict) or 'display' not in card_data:
                    continue
                
                display_sections = card_data['display']
                if not isinstance(display_sections, list):
                    continue
                
                for display_section in display_sections:
                    if 'rows' not in display_section:
                        continue
                    
                    rows = display_section['rows']
                    for row in rows:
                        if 'eventId' in row and 'marketIds' in row:
                            event_id = int(row['eventId'])
                            market_ids = row['marketIds']
                            
                            if event_id not in self.event_to_markets:
                                self.event_to_markets[event_id] = []
                            
                            # Add market IDs if not already present
                            for market_id in market_ids:
                                if market_id not in self.event_to_markets[event_id]:
                                    self.event_to_markets[event_id].append(market_id)
        
        except Exception as e:
            self.logger.error(f"Error processing layout section: {e}")
    
    def _process_in_play_api(self, data: Dict):
        try:
            # First, extract event-to-market mappings from layout
            if 'layout' in data:
                self._process_layout_section(data['layout'])
            
            if 'attachments' not in data:
                return
            
            attachments = data['attachments']
            
            # Process events
            if 'events' in attachments and isinstance(attachments['events'], dict):
                for event_id, event_data in attachments['events'].items():
                    try:
                        event_id = int(event_id)
                        
                        if event_id not in self.event_details:
                            self.event_details[event_id] = {}
                        
                        # Get market IDs from layout mapping
                        market_ids = self.event_to_markets.get(event_id, [])
                        
                        self.event_details[event_id].update({
                            'name': event_data.get('name', ''),
                            'openDate': event_data.get('openDate', ''),
                            'marketIds': market_ids,
                            'competitionId': event_data.get('competitionId', ''),
                            'eventTypeId': event_data.get('eventTypeId', '')
                        })
                    except Exception as e:
                        pass
            
            # Process markets with odds
            if 'markets' in attachments and isinstance(attachments['markets'], dict):
                for market_id, market_data in attachments['markets'].items():
                    self.market_data[market_id] = market_data
                    
                    # Extract odds from runners
                    if 'runners' in market_data:
                        runners = market_data['runners']
                        odds = self._extract_odds_from_runners(runners)
                        
                        if odds:
                            market_data['extracted_odds'] = odds
                            
                            # Link to event if event ID is present
                            event_id = market_data.get('eventId')
                            if event_id and event_id in self.live_matches:
                                if not self.live_matches[event_id]['odds_data']:
                                    self.live_matches[event_id]['odds_data'] = {}
                                
                                market_name = market_data.get('marketName', market_id)
                                self.live_matches[event_id]['odds_data'][market_name] = {
                                    'market_id': market_id,
                                    'market_type': market_data.get('marketType', ''),
                                    'market_status': market_data.get('marketStatus', ''),
                                    'in_play': market_data.get('inPlay', False),
                                    'odds': odds
                                }
                                self.live_matches[event_id]['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        except Exception as e:
            self.logger.error(f"Error processing in-play API: {e}")
    
    def _process_live_score_data(self, data: Any):
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'eventId' in item:
                    self._parse_and_store_match(item)
        
        elif isinstance(data, dict):
            if 'eventId' in data:
                self._parse_and_store_match(data)
    
    def _parse_and_store_match(self, event_data: Dict):
        event_id = event_data.get('eventId')

        if event_id not in self.live_matches:
            # Generate game_id for the match
            game_id = self._generate_game_id(event_data)

            self.live_matches[event_id] = {
                'event_id': event_id,
                'game_id': game_id,
                'home_team': '',
                'away_team': '',
                'time': '',
                'sport': '',
                'league': '',
                'score': {},
                'live_details': {},
                'odds_data': {},
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

        match = self.live_matches[event_id]
        
        if event_id in self.event_details:
            details = self.event_details[event_id]
            match['event_name'] = details.get('name', '')
            
            if ' @ ' in details.get('name', ''):
                parts = details.get('name', '').split(' @ ')
                if len(parts) == 2:
                    match['away_team'] = parts[0].strip()
                    match['home_team'] = parts[1].strip()
            elif ' v ' in details.get('name', ''):
                parts = details.get('name', '').split(' v ')
                if len(parts) == 2:
                    match['home_team'] = parts[0].strip()
                    match['away_team'] = parts[1].strip()
        
        if 'basketballDetails' in event_data:
            details = event_data['basketballDetails']
            match['sport'] = 'Basketball'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'soccerDetails' in event_data:
            details = event_data['soccerDetails']
            match['sport'] = 'Soccer'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'tennisDetails' in event_data:
            details = event_data['tennisDetails']
            match['sport'] = 'Tennis'
            match['score'] = details.get('score', {})
            match['live_details'] = details
        
        elif 'baseballDetails' in event_data:
            details = event_data['baseballDetails']
            match['sport'] = 'Baseball'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'cricketDetails' in event_data:
            details = event_data['cricketDetails']
            match['sport'] = 'Cricket'
            match['score'] = details.get('score', {})
            match['live_details'] = details
        
        elif 'dartDetails' in event_data:
            match['sport'] = 'Darts'
            match['live_details'] = event_data.get('dartDetails', {})
        
        elif 'tableTennisDetails' in event_data:
            match['sport'] = 'Table Tennis'
            match['live_details'] = event_data.get('tableTennisDetails', {})
        
        elif 'iceHockeyDetails' in event_data:
            details = event_data['iceHockeyDetails']
            match['sport'] = 'Ice Hockey'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'golfDetails' in event_data:
            match['sport'] = 'Golf'
            match['live_details'] = event_data.get('golfDetails', {})
        
        elif 'americanFootballDetails' in event_data:
            details = event_data['americanFootballDetails']
            match['sport'] = 'American Football'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'rugbyLeagueDetails' in event_data:
            details = event_data['rugbyLeagueDetails']
            match['sport'] = 'Rugby League'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'rugbyUnionDetails' in event_data:
            details = event_data['rugbyUnionDetails']
            match['sport'] = 'Rugby Union'
            match['score'] = {
                'home': details.get('home', {}).get('score', 0),
                'away': details.get('away', {}).get('score', 0)
            }
            match['live_details'] = details
        
        elif 'mmaDetails' in event_data:
            match['sport'] = 'MMA'
            match['live_details'] = event_data.get('mmaDetails', {})
        
        elif 'boxingDetails' in event_data:
            match['sport'] = 'Boxing'
            match['live_details'] = event_data.get('boxingDetails', {})
        
        match['last_updated'] = datetime.now(timezone.utc).isoformat()
    
    def _merge_and_save(self):
        """Merge market data with live matches using the event-to-market mapping"""
        for event_id in self.live_matches:
            match = self.live_matches[event_id]
            
            # Get market IDs for this event
            market_ids = self.event_to_markets.get(event_id, [])
            
            if not market_ids and event_id in self.event_details:
                # Fallback to event_details if layout mapping didn't work
                market_ids = self.event_details[event_id].get('marketIds', [])
            
            if market_ids:
                for market_id in market_ids:
                    market_id_str = str(market_id)
                    if market_id_str in self.market_data:
                        market = self.market_data[market_id_str]
                        
                        if not match['odds_data']:
                            match['odds_data'] = {}
                        
                        # Extract odds
                        odds = {}
                        if 'extracted_odds' in market:
                            odds = market['extracted_odds']
                        elif 'runners' in market:
                            odds = self._extract_odds_from_runners(market['runners'])
                        
                        if odds:
                            market_name = market.get('marketName', f'Market_{market_id_str}')
                            match['odds_data'][market_name] = {
                                'market_id': market_id_str,
                                'market_type': market.get('marketType', ''),
                                'market_status': market.get('marketStatus', ''),
                                'in_play': market.get('inPlay', False),
                                'odds': odds
                            }
        
        # Trigger fast async save every 1 second (no expensive comparisons)
        current_time = time.time()
        if current_time - self.last_save_time >= 1.0:  # Save every 1 second
            self.last_save_time = current_time
            asyncio.create_task(self._async_save())
    
    async def _async_save(self):
        """Fast non-blocking save every 1 second"""
        try:
            await asyncio.to_thread(self._save_all_data)
        except Exception as e:
            self.logger.error(f"Error in async save: {e}")
    
    def _save_all_data(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            urls_file = os.path.join(script_dir, "urls_with_ids.json")
            urls_data = {
                'session_id': self.session_id,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'total_events': len(self.api_urls),
                'api_urls': self.api_urls
            }
            
            with open(urls_file, 'w', encoding='utf-8') as f:
                json.dump(urls_data, f, indent=2, ensure_ascii=False)
            
            # Calculate statistics by sport
            sports_stats = {}
            matches_with_odds_by_sport = {}
            
            for match in self.live_matches.values():
                sport = match.get('sport', 'Unknown')
                if sport not in sports_stats:
                    sports_stats[sport] = 0
                    matches_with_odds_by_sport[sport] = 0
                
                sports_stats[sport] += 1
                if match.get('odds_data'):
                    matches_with_odds_by_sport[sport] += 1
            
            live_file = os.path.join(script_dir, "fanduel_live.json")
            live_data = {
                'session_id': self.session_id,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'total_live_matches': len(self.live_matches),
                'matches_with_odds': sum(1 for m in self.live_matches.values() if m['odds_data']),
                'statistics_by_sport': {
                    sport: {
                        'total_matches': count,
                        'matches_with_odds': matches_with_odds_by_sport.get(sport, 0)
                    }
                    for sport, count in sorted(sports_stats.items())
                },
                'matches': list(self.live_matches.values())
            }
            
            with open(live_file, 'w', encoding='utf-8') as f:
                json.dump(live_data, f, indent=2, ensure_ascii=False)
            
            # Save statistics file separately for easy viewing
            stats_file = os.path.join(script_dir, "fanduel_live_statistics.json")
            stats_data = {
                'session_id': self.session_id,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'total_matches': len(self.live_matches),
                'matches_with_odds': sum(1 for m in self.live_matches.values() if m['odds_data']),
                'by_sport': {
                    sport: {
                        'total_matches': count,
                        'matches_with_odds': matches_with_odds_by_sport.get(sport, 0),
                        'percentage_with_odds': round(matches_with_odds_by_sport.get(sport, 0) / count * 100, 1) if count > 0 else 0
                    }
                    for sport, count in sorted(sports_stats.items())
                }
            }
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
    
    async def discover_and_click_tabs(self, page):
        self.logger.info("Discovering sport tabs...")
        
        try:
            await asyncio.sleep(3)
            
            tabs = await page.query_selector_all('a[href*="/live?tab="]')
            
            discovered_tabs = []
            
            for tab in tabs:
                try:
                    href = await tab.get_attribute('href')
                    text = await tab.inner_text()
                    
                    if href and '/live' in href and '?tab=' in href:
                        tab_name = href.split('tab=')[-1].split('&')[0]
                        discovered_tabs.append({
                            'name': tab_name,
                            'text': text.strip(),
                            'element': tab
                        })
                except:
                    continue
            
            if not discovered_tabs:
                all_links = await page.query_selector_all('a')
                
                for link in all_links:
                    try:
                        href = await link.get_attribute('href')
                        if href and '/live?tab=' in href:
                            tab_name = href.split('tab=')[-1].split('&')[0]
                            if not any(t['name'] == tab_name for t in discovered_tabs):
                                text = await link.inner_text()
                                discovered_tabs.append({
                                    'name': tab_name,
                                    'text': text.strip(),
                                    'element': link
                                })
                    except:
                        continue
            
            self.logger.info(f"Found {len(discovered_tabs)} tabs")
            return discovered_tabs
        
        except Exception as e:
            self.logger.error(f"Error discovering tabs: {e}")
            return []
    
    async def poll_api_endpoint(self, api_url: str):
        """Continuously poll a discovered API endpoint every 1 second using Playwright's request context"""
        
        poll_count = 0
        last_data_hash = None
        
        try:
            while True:
                try:
                    if not self.context:
                        await asyncio.sleep(2)
                        continue
                    
                    # Use Playwright's request API which shares the browser context and cookies
                    response = await self.context.request.get(api_url)
                    
                    if response.ok:
                        data = await response.json()
                        
                        # Check if data actually changed
                        import hashlib
                        data_str = json.dumps(data, sort_keys=True)
                        current_hash = hashlib.md5(data_str.encode()).hexdigest()
                        
                        poll_count += 1
                        
                        # Log when data changes or every 10 polls
                        if current_hash != last_data_hash:
                            event_count = len(self._extract_event_ids(data))
                            if poll_count % 10 == 0 or last_data_hash is not None:
                                self.logger.info(f"📊 API data changed! Poll #{poll_count}: {event_count} events")
                            last_data_hash = current_hash
                            
                            async with self.data_lock:
                                self._process_api_response(api_url, data)
                        elif poll_count % 60 == 0:
                            self.logger.debug(f"Poll #{poll_count}: No change in data")
                    
                    elif response.status == 403:
                        self.logger.warning(f"API returned 403 Forbidden: {api_url}")
                        await asyncio.sleep(5)
                    
                    await asyncio.sleep(1)  # Poll every 1 second
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Log errors to help debug
                    if poll_count % 30 == 0:
                        self.logger.warning(f"API poll error for {api_url[:60]}: {type(e).__name__} - {str(e)}")
                    
                    await asyncio.sleep(2)  # Wait longer on error
        
        except Exception as e:
            self.logger.error(f"Error in API polling for {api_url}: {e}")
    
    async def start_api_polling(self):
        """Start concurrent polling of all discovered API endpoints"""
        if not self.discovered_apis:
            self.logger.warning("No APIs discovered to poll")
            return
        
        # Find new APIs that aren't being polled yet
        current_apis = {task.get_name() for task in self.api_polling_tasks if not task.done()}
        new_apis = self.discovered_apis - current_apis
        
        if new_apis:
            self.logger.info(f"Starting polling for {len(new_apis)} new API endpoint(s)...")
            
            for api_url in new_apis:
                task = asyncio.create_task(self.poll_api_endpoint(api_url), name=api_url)
                self.api_polling_tasks.append(task)
            
            self.logger.info(f"✓ Total active API polling tasks: {len([t for t in self.api_polling_tasks if not t.done()])}")
    
    async def stop_api_polling(self):
        """Stop all API polling tasks"""
        self.logger.info("Stopping API polling tasks...")
        
        for task in self.api_polling_tasks:
            if not task.done():
                task.cancel()
        
        if self.api_polling_tasks:
            await asyncio.gather(*self.api_polling_tasks, return_exceptions=True)
        
        self.api_polling_tasks.clear()
        self.logger.info("✓ All API polling tasks stopped")
    
    async def initial_load_all_tabs(self):
        self.logger.info("Initial load - capturing all sports...")

        try:
            if self.context is None:
                raise Exception("Browser context not initialized")
            live_page = await self.context.new_page()
            
            # Increased timeout and more lenient loading
            await live_page.goto('https://sportsbook.fanduel.com/live', wait_until='domcontentloaded', timeout=60000)
            
            # Don't wait for networkidle - it may never happen with live data
            try:
                await live_page.wait_for_load_state('networkidle', timeout=10000)
            except:
                self.logger.info("Network not idle, continuing anyway (normal for live data)")
            
            await asyncio.sleep(3)
            
            for scroll in range(5):
                await live_page.mouse.wheel(0, 800)
                await asyncio.sleep(0.5)
            
            await asyncio.sleep(2)
            
            tabs = await self.discover_and_click_tabs(live_page)
            
            if tabs:
                for tab in tabs:
                    try:
                        self.logger.info(f"Loading tab: {tab['name']}")
                        await tab['element'].click()
                        await asyncio.sleep(2)
                        
                        for scroll in range(3):
                            await live_page.mouse.wheel(0, 800)
                            await asyncio.sleep(0.5)
                        
                        await asyncio.sleep(2)
                        
                        async with self.data_lock:
                            matches_with_odds = sum(1 for m in self.live_matches.values() if m['odds_data'])
                            self.logger.info(f"📊 Events: {len(self.api_urls)} | Matches: {len(self.live_matches)} | With Odds: {matches_with_odds}")
                    
                    except Exception as e:
                        self.logger.error(f"Error with tab {tab['name']}: {e}")
            
            else:
                tab_urls = ['watch-live', 'baseball', 'basketball', 'tennis', 'soccer', 'ice-hockey', 'golf', 'cricket', 'table-tennis', 'darts', 'american-football', 'rugby-league', 'rugby-union', 'mma', 'boxing']
                
                for tab_name in tab_urls:
                    try:
                        self.logger.info(f"Loading tab: {tab_name}")
                        url = f"https://sportsbook.fanduel.com/live?tab={tab_name}"
                        await live_page.goto(url, wait_until='domcontentloaded', timeout=60000)
                        await asyncio.sleep(2)
                        
                        for scroll in range(3):
                            await live_page.mouse.wheel(0, 800)
                            await asyncio.sleep(0.5)
                        
                        await asyncio.sleep(2)
                        
                        async with self.data_lock:
                            matches_with_odds = sum(1 for m in self.live_matches.values() if m['odds_data'])
                            self.logger.info(f"📊 Events: {len(self.api_urls)} | Matches: {len(self.live_matches)} | With Odds: {matches_with_odds}")
                    
                    except Exception as e:
                        self.logger.warning(f"Could not load {tab_name}: {e}")
            
            self.logger.info("✓ Initial load complete")
            
            return live_page
        
        except Exception as e:
            self.logger.error(f"Error in initial load: {e}")
            return None
    
    async def run(self):
        try:
            await self.setup_browser()
            
            # Phase 1: Sequential initial load to discover all API endpoints
            self.logger.info("PHASE 1: Sequential discovery of all sports...")
            live_page = await self.initial_load_all_tabs()
            
            if not live_page:
                self.logger.error("Failed to complete initial load")
                return
            
            self.logger.info("="*80)
            self.logger.info("PHASE 2: FAST TAB ROTATION FOR CONCURRENT-LIKE UPDATES")
            self.logger.info("Rapidly switching tabs to keep all sports updating frequently")
            self.logger.info("Press Ctrl+C to stop")
            self.logger.info("="*80)
            
            # Phase 2: Ultra-fast tab rotation on single page
            start_time = time.time()
            update_count = 0
            
            # ULTRA-FAST ROTATION: 0.2s interval for maximum speed (7 tabs × 0.2s = ~1.4s full cycle)
            tab_rotation_interval = 0.2  # Ultra-fast rotation for real-time live betting data
            last_tab_rotation = time.time()
            current_tab_index = 0
            
            # Periodic re-discovery of new sports tabs
            rediscovery_interval = 600  # 10 minutes
            last_rediscovery = time.time()
            
            # Get available tabs
            discovered_tabs = await self.discover_and_click_tabs(live_page)
            
            if not discovered_tabs:
                self.logger.warning("No tabs discovered, using fallback")
            
            cycle_time = tab_rotation_interval * len(discovered_tabs) if discovered_tabs else 1.4
            self.logger.info(f"Ultra-fast rotation: {tab_rotation_interval}s interval × {len(discovered_tabs) if discovered_tabs else 7} tabs = ~{cycle_time:.1f}s full cycle")
            self.logger.info(f"Will check for new sports every {rediscovery_interval // 60} minutes")
            
            while True:
                await asyncio.sleep(0.05)  # Very short sleep for maximum responsiveness
                
                update_count += 1
                current_time = time.time()
                elapsed = int(current_time - start_time)
                
                # Check for new sports tabs every 10 minutes
                if current_time - last_rediscovery >= rediscovery_interval:
                    self.logger.info("🔍 Checking for new sports tabs...")
                    try:
                        new_tabs = await self.discover_and_click_tabs(live_page)
                        if new_tabs and len(new_tabs) != len(discovered_tabs):
                            old_count = len(discovered_tabs)
                            discovered_tabs = new_tabs
                            new_count = len(discovered_tabs)
                            cycle_time = tab_rotation_interval * new_count
                            self.logger.info(f"✓ Updated tabs: {old_count} → {new_count} (new cycle: ~{cycle_time:.1f}s)")
                        else:
                            self.logger.info(f"✓ No new sports found ({len(discovered_tabs)} tabs)")
                    except Exception as e:
                        self.logger.warning(f"Rediscovery error: {e}")
                    
                    last_rediscovery = current_time
                
                # Ultra-fast tab rotation
                if current_time - last_tab_rotation >= tab_rotation_interval and discovered_tabs:
                    try:
                        # Switch to next tab instantly
                        tab = discovered_tabs[current_tab_index % len(discovered_tabs)]
                        await tab['element'].click()
                        # No sleep after click - maximum speed!
                        
                        # Fast multiple scrolls to trigger updates and load all content
                        await live_page.mouse.wheel(0, 800)
                        await live_page.mouse.wheel(0, 800)
                        await live_page.mouse.wheel(0, -1600)  # Scroll back up
                        
                        current_tab_index += 1
                        last_tab_rotation = current_time
                        
                        if update_count % 50 == 0:
                            self.logger.debug(f"↻ Switched to: {tab['name']}")
                    
                    except Exception as e:
                        self.logger.debug(f"Tab rotation error: {e}")
                        # Re-discover tabs if rotation fails
                        try:
                            discovered_tabs = await self.discover_and_click_tabs(live_page)
                            current_tab_index = 0
                        except:
                            pass
                
                # Status update every 1 second
                if update_count % 20 == 0:
                    async with self.data_lock:
                        matches_with_odds = sum(1 for m in self.live_matches.values() if m['odds_data'])
                        actual_cycle = tab_rotation_interval * len(discovered_tabs) if discovered_tabs else 1.4
                        time_until_rediscovery = int(rediscovery_interval - (current_time - last_rediscovery))
                        mins_until = time_until_rediscovery // 60
                        secs_until = time_until_rediscovery % 60
                        self.logger.info(
                            f"⏱️  {elapsed}s | Cycle: ~{actual_cycle:.1f}s | "
                            f"Events: {len(self.api_urls)} | Matches: {len(self.live_matches)} | "
                            f"With Odds: {matches_with_odds} | Next check: {mins_until}m {secs_until}s"
                        )
        
        except KeyboardInterrupt:
            self.logger.info("\n" + "="*80)
            self.logger.info("MONITORING STOPPED BY USER")
            self.logger.info("="*80)
        
        except Exception as e:
            self.logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            async with self.data_lock:
                matches_with_odds = sum(1 for m in self.live_matches.values() if m['odds_data'])
                self.logger.info(f"Final - Events: {len(self.api_urls)} | Matches: {len(self.live_matches)} | With Odds: {matches_with_odds}")
                self.logger.info("Files: urls_with_ids.json, fanduel_live.json")
            
            await self.cleanup()
    
    async def cleanup(self):
        self.logger.info("Cleaning up...")
        
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
        
        self.logger.info("Cleanup complete")

async def main():
    monitor = FanDuelLiveMonitor()
    await monitor.run()

if __name__ == "__main__":
    asyncio.run(main())
    
    
    
    