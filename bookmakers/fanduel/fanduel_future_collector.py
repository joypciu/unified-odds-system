#!/usr/bin/env python3
"""
Combined Future Events Collector - Collects events from all sports
"""
import asyncio
import json
import time
import os
import subprocess
import tempfile
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

class CombinedFutureEventsCollector:
    """Collector for future events from all sports"""

    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_port = 9229

        # Browser
        self.playwright = None
        self.browser = None
        self.chrome_process = None
        self.context = None

        # Combined future events
        self.future_events = []

        # Monitoring state
        self.current_sport_index = 0

        # Logging
        self.setup_logging()
        print(f"[INIT] Combined Future Events Collector - Session: {self.session_id}")

    def setup_logging(self):
        """Setup logging"""
        self.logger = logging.getLogger('combined_future')
        self.logger.setLevel(logging.INFO)

        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        log_file = os.path.join(logs_dir, f'combined_future_{self.session_id}.log')
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
        self.logger.info("COMBINED FUTURE EVENTS COLLECTOR STARTED")
        self.logger.info("="*80)

    def launch_chrome(self):
        """Launch Chrome"""
        chrome_exe = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

        if not os.path.exists(chrome_exe):
            raise Exception(f"Chrome not found at {chrome_exe}")

        profile_dir = os.path.join(tempfile.gettempdir(), f"fd_future_{self.session_id}")
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            chrome_exe,
            f'--remote-debugging-port={self.debug_port}',
            f'--user-data-dir={profile_dir}',
            '--no-first-run',
            '--disable-blink-features=AutomationControlled',
            '--start-maximized'
        ]

        self.logger.info("Launching Chrome for combined future events collection...")
        self.chrome_process = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.logger.info(f"Chrome launched (PID: {self.chrome_process.pid})")

    async def setup_browser(self):
        """Setup browser connection"""
        self.logger.info("Connecting to Chrome...")

        self.playwright = await async_playwright().start()
        self.launch_chrome()
        await asyncio.sleep(5)  # Wait longer for Chrome to start

        self.browser = await self.playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self.debug_port}"
        )
        self.context = self.browser.contexts[0]

        # Set up response handler
        self.context.on('response', self.combined_response_handler)

        self.logger.info("Connected with combined response handler!")

    async def combined_response_handler(self, response):
        """Handle API responses for both sports"""
        try:
            url = response.url

            # Filter for APIs - broader capture
            if ('fanduel.com' in url and
                response.status == 200 and
                ('sbapi' in url or 'sportsbook' in url or 'content-managed-page' in url) and
                not any(ext in url for ext in ['.png', '.jpg', '.css', '.js', '.woff', '.ttf', '.svg', '.ico', '.woff2'])):

                try:
                    body = await response.body()
                    data = json.loads(body.decode('utf-8'))

                    # Check if this has event data
                    if self._has_event_data(data):
                        async with asyncio.Lock():
                            self._process_event_data(data)
                            self._save_future_events()

                        self.logger.info(f"📅 FUTURE EVENTS API captured | Total Events: {len(self.future_events)}")

                except Exception as e:
                    pass

        except Exception as e:
            pass

    def _has_event_data(self, data: Dict) -> bool:
        """Check if data has event information"""
        if not isinstance(data, dict):
            return False

        attachments = data.get('attachments', {})
        if not isinstance(attachments, dict):
            return False

        return ('events' in attachments or 'markets' in attachments or
                'competitions' in attachments)

    def _process_event_data(self, data: Dict):
        """Process event data from both sports"""
        try:
            attachments = data.get('attachments', {})

            # Process markets to build events
            if 'markets' in attachments:
                markets = attachments['markets']
                if isinstance(markets, dict):
                    for market_id, market_data in markets.items():
                        self._build_future_event_from_market(market_data)

        except Exception as e:
            self.logger.error(f"Error processing event data: {e}")

    def _build_future_event_from_market(self, market_data: Dict):
        """Build future event from market data"""
        try:
            event_id = str(market_data.get('eventId', ''))
            if not event_id:
                return

            # Find or create event
            existing_event = self._find_existing_future_event(event_id)
            if not existing_event:
                # Determine sport type from market name or other indicators
                sport = self._determine_sport(market_data)
                participants_key = 'drivers' if sport == 'motorsport' else 'players'

                existing_event = {
                    'event_id': event_id,
                    'event_name': market_data.get('marketName', ''),
                    'competition_id': market_data.get('competitionId'),
                    'scheduled_time': market_data.get('marketTime'),
                    'status': 'live' if market_data.get('inPlay', False) else 'upcoming',
                    'sport': sport,
                    participants_key: [],
                    'market_types': []
                }
                self.future_events.append(existing_event)

            # Parse market for participants
            self._parse_market_participants(market_data, existing_event)

        except Exception as e:
            self.logger.error(f"Error building future event from market: {e}")

    def _determine_sport(self, market_data: Dict) -> str:
        """Determine sport type from market data"""
        market_name = market_data.get('marketName', '').lower()
        if any(keyword in market_name for keyword in ['formula', 'motogp', 'nascar', 'f1', 'driver']):
            return 'motorsport'
        elif any(keyword in market_name for keyword in ['tennis', 'wimbledon', 'us open', 'player']):
            return 'tennis'
        elif any(keyword in market_name for keyword in ['soccer', 'football', 'premier league', 'champions league', 'serie a', 'bundesliga', 'laliga']):
            return 'soccer'
        elif any(keyword in market_name for keyword in ['basketball', 'nba', 'college basketball', 'wnba']):
            return 'basketball'
        elif any(keyword in market_name for keyword in ['football', 'nfl', 'super bowl', 'touchdown']):
            return 'football'
        elif any(keyword in market_name for keyword in ['baseball', 'mlb', 'world series', 'dodgers', 'yankees']):
            return 'baseball'
        elif any(keyword in market_name for keyword in ['boxing', 'mma', 'ufc', 'wrestling']):
            return 'mma'
        elif any(keyword in market_name for keyword in ['golf', 'pga', 'masters']):
            return 'golf'
        elif any(keyword in market_name for keyword in ['table-tennis', 'table tennis', 'ping pong']):
            return 'table-tennis'
        elif any(keyword in market_name for keyword in ['cricket', 'ipl', 'world cup cricket']):
            return 'cricket'
        elif any(keyword in market_name for keyword in ['darts', 'pdc', 'world darts']):
            return 'darts'
        elif any(keyword in market_name for keyword in ['ice-hockey', 'ice hockey', 'nhl', 'stanley cup']):
            return 'hockey'
        elif any(keyword in market_name for keyword in ['aussie-rules', 'aussie rules', 'afl']):
            return 'aussie-rules'
        elif any(keyword in market_name for keyword in ['lacrosse', 'nll']):
            return 'lacrosse'
        elif any(keyword in market_name for keyword in ['cycling', 'tour de france']):
            return 'cycling'
        elif any(keyword in market_name for keyword in ['rugby-league', 'rugby league', 'nrl', 'super league']):
            return 'rugby-league'
        elif any(keyword in market_name for keyword in ['rugby-union', 'rugby union', 'six nations', 'rugby world cup']):
            return 'rugby-union'
        else:
            # Default to tennis if uncertain
            return 'tennis'

    def _parse_market_participants(self, market: Dict, event: Dict):
        """Parse market for participants (drivers or players)"""
        try:
            market_name = market.get('marketName', '').lower()
            runners = market.get('runners', [])
            sport = event.get('sport', 'tennis')
            participants_key = 'drivers' if sport == 'motorsport' else 'players'

            if not runners:
                return

            # Add market type if not already present
            if market_name not in event['market_types']:
                event['market_types'].append(market_name)

            # Process each runner (participant)
            for runner in runners:
                if isinstance(runner, dict):
                    participant_name = runner.get('runnerName', '').strip()
                    odds = self._extract_odds(runner)

                    if participant_name and odds is not None:
                        # Check if participant already exists
                        existing_participant = None
                        for participant in event[participants_key]:
                            if participant['name'] == participant_name:
                                existing_participant = participant
                                break

                        if existing_participant:
                            # Update existing participant with new market odds
                            existing_participant[market_name] = odds
                        else:
                            # Add new participant
                            participant = {
                                'name': participant_name,
                                market_name: odds
                            }
                            event[participants_key].append(participant)

        except Exception as e:
            self.logger.error(f"Error parsing market participants: {e}")

    def _extract_odds(self, runner: Dict) -> Optional[float]:
        """Extract odds from runner"""
        try:
            if 'winRunnerOdds' in runner:
                odds_data = runner['winRunnerOdds']
                american_odds = odds_data.get('americanDisplayOdds', {}).get('americanOdds')
                if american_odds is not None:
                    return float(american_odds)
        except:
            pass
        return None

    def _find_existing_future_event(self, event_id: str) -> Optional[Dict]:
        """Find existing future event"""
        for event in self.future_events:
            if event.get('event_id') == event_id:
                return event
        return None

    def _save_future_events(self):
        """Save future events to JSON in current folder"""
        try:
            # Current folder path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = datetime.now(timezone.utc).isoformat()

            # Save events
            events_file = os.path.join(script_dir, "fanduel_future.json")
            events_data = {
                'metadata': {
                    'session_id': self.session_id,
                    'timestamp': timestamp,
                    'total_events': len(self.future_events)
                },
                'events': self.future_events
            }
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"💾 Saved {len(self.future_events)} future events to {events_file}")

        except Exception as e:
            self.logger.error(f"Error saving future events: {e}")

    async def collect_future_events(self, monitoring_duration: int = 0):
        """Collect future events from all sports: motorsport, tennis, soccer, basketball, football
        Args:
            monitoring_duration: Duration in minutes for realtime monitoring (0 = infinite)
        """
        try:
            await self.setup_browser()

            sports = [
                ('motorsport', 'https://sportsbook.fanduel.com/motorsport'),
                ('tennis', 'https://sportsbook.fanduel.com/tennis'),
                ('soccer', 'https://sportsbook.fanduel.com/soccer'),
                ('basketball', 'https://sportsbook.fanduel.com/basketball'),
                ('football', 'https://sportsbook.fanduel.com/football'),
                ('baseball', 'https://sportsbook.fanduel.com/baseball'),
                ('boxing', 'https://sportsbook.fanduel.com/boxing'),
                ('golf', 'https://sportsbook.fanduel.com/golf'),
                ('table-tennis', 'https://sportsbook.fanduel.com/table-tennis'),
                ('cricket', 'https://sportsbook.fanduel.com/cricket'),
                ('darts', 'https://sportsbook.fanduel.com/darts'),
                ('ice-hockey', 'https://sportsbook.fanduel.com/ice-hockey'),
                ('aussie-rules', 'https://sportsbook.fanduel.com/aussie-rules'),
                ('lacrosse', 'https://sportsbook.fanduel.com/lacrosse'),
                ('cycling', 'https://sportsbook.fanduel.com/cycling'),
                ('rugby-league', 'https://sportsbook.fanduel.com/rugby-league'),
                ('rugby-union', 'https://sportsbook.fanduel.com/rugby-union')
            ]

            # PHASE 1: Initial collection - create all pages first, then navigate sequentially
            if self.context is None:
                raise Exception("Browser context not initialized")

            # Create all pages first
            sport_pages = {}
            for sport_name, sport_url in sports:
                try:
                    sport_page = await self.context.new_page()
                    sport_pages[sport_name] = sport_page
                except Exception as e:
                    self.logger.error(f"Error creating page for {sport_name}: {e}")

            self.logger.info(f"All sport pages created - {len(sport_pages)} sports ready")

            # Now navigate to each page sequentially with delays to avoid detection
            for sport_name, sport_url in sports:
                if sport_name in sport_pages:
                    try:
                        self.logger.info(f"Collecting from {sport_name}...")
                        page = sport_pages[sport_name]
                        await page.goto(sport_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_load_state('domcontentloaded', timeout=30000)
                        await asyncio.sleep(5)

                        # Scroll to trigger API calls
                        for scroll in range(3):
                            await page.mouse.wheel(0, 400)
                            await asyncio.sleep(1)

                        await asyncio.sleep(15)  # Wait for data

                    except Exception as e:
                        self.logger.error(f"Error loading {sport_name}: {e}")

                    # Wait between sports to avoid triggering verification
                    await asyncio.sleep(2.5)

            # Close all collection pages
            for page in sport_pages.values():
                try:
                    await page.close()
                except:
                    pass

            self.logger.info("Initial future events collection complete!")

            # PHASE 2: Realtime monitoring - create all monitoring pages first, then cycle through them
            monitoring_duration_seconds = monitoring_duration * 60 if monitoring_duration > 0 else float('inf')
            self.logger.info(f"Starting continuous realtime monitoring for future events... (Duration: {'infinite' if monitoring_duration == 0 else f'{monitoring_duration} minutes'})")
            start_time = time.time()
            update_count = 0

            # Create all monitoring pages first
            monitoring_pages = {}
            for sport_name, sport_url in sports:
                try:
                    monitoring_page = await self.context.new_page()
                    monitoring_pages[sport_name] = monitoring_page
                except Exception as e:
                    self.logger.error(f"Error creating monitoring page for {sport_name}: {e}")

            self.logger.info(f"All monitoring pages created - {len(monitoring_pages)} sports ready for cycling")

            while time.time() - start_time < monitoring_duration_seconds:
                await asyncio.sleep(3)  # Update every 3 seconds for faster cycling
                update_count += 1
                elapsed = int(time.time() - start_time)

                # Cycle to next sport
                sport_name, sport_url = sports[self.current_sport_index]
                try:
                    if sport_name in monitoring_pages:
                        self.logger.debug(f"Loading {sport_name} for monitoring...")
                        page = monitoring_pages[sport_name]
                        await page.goto(sport_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_load_state('domcontentloaded', timeout=30000)
                        await asyncio.sleep(2)  # Wait for page to load

                        # Scroll to trigger API calls
                        for scroll in range(3):
                            await page.mouse.wheel(0, 300)
                            await asyncio.sleep(0.5)

                        await asyncio.sleep(1)  # Brief pause for API processing

                except Exception as e:
                    self.logger.warning(f"Error loading {sport_name} page: {e}")

                # Move to next sport
                self.current_sport_index = (self.current_sport_index + 1) % len(sports)

                # Log progress every 10 cycles (every 30 seconds)
                if update_count % 10 == 0:
                    self.logger.info(f"⏱️  {elapsed}s | Cycle: {update_count} | Future Events: {len(self.future_events)} | Current Sport: {sport_name}")

            # Close all monitoring pages
            for page in monitoring_pages.values():
                try:
                    await page.close()
                except:
                    pass

            if monitoring_duration > 0:
                self.logger.info(f"⏰ Future events monitoring duration ({monitoring_duration} minutes) completed!")

        except Exception as e:
            self.logger.error(f"Error in future events collection: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup"""
        self.logger.info("Cleaning up combined future events collection...")

        # No monitoring page to close since we create new pages each time

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

        self.logger.info("Combined future events collection cleanup complete")

async def main():
    import sys
    duration = 0  # Default to infinite
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration argument: {sys.argv[1]}. Using infinite monitoring.")
            duration = 0

    collector = CombinedFutureEventsCollector()
    await collector.collect_future_events(monitoring_duration=duration)

if __name__ == "__main__":
    asyncio.run(main())