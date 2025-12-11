"""
Real-time Monitoring System for bet365 Pregame Data
Provides parallel monitoring of all sports with smart fetching and history tracking
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
import aiofiles
from concurrent.futures import ThreadPoolExecutor

from bet365_pregame_homepage_scraper import EnhancedIntelligentScraper, Game, GameOdds
from typing import Optional

@dataclass
class GameUpdate:
    """Represents a game update with change type"""
    game: Game
    change_type: str  # 'insert', 'update', 'delete'
    timestamp: str
    changes: Dict[str, Any] = None

@dataclass
class MonitoringStats:
    """Statistics for real-time monitoring"""
    total_games: int = 0
    active_games: int = 0
    completed_games: int = 0
    updates_count: int = 0
    last_update: str = ""
    uptime_seconds: float = 0.0

class RealTimeMonitor:
    """Real-time monitoring system with parallel processing"""
    
    def __init__(self, update_interval: float = 0.3):
        self.update_interval = max(0.1, min(update_interval, 1.0))  # Faster: 0.1-1.0s range
        self.scraper: Optional[EnhancedIntelligentScraper] = None
        self.is_running = False
        self.start_time = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")  # Add session ID
        
        # Data storage
        self.current_games: Dict[str, Game] = {}  # game_id -> Game
        self.game_history: List[Game] = []
        self.update_queue: asyncio.Queue = None
        
        # Monitoring state
        self.sports_tasks: Dict[str, asyncio.Task] = {}
        self.stats = MonitoringStats()
        
        # Real-time monitoring cycle tracking
        self.cycle_count = 0
        self.sport_update_counts = {}  # Track updates per sport
        self.cycle_history = []  # Track cycle performance
        self.current_cycle_start = None
        
        # File paths
        self.output_dir = Path(".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = self.output_dir / "bet365_current_pregame.json"
        self.pregame_history_file = self.output_dir / "pregame_history.json"
        self.statistic_file = self.output_dir / "bet365_pregame_statistic.json"
        
        # Pregame tracking storage
        self.previous_pregame_games: Dict[str, Dict] = {}  # Track pregame games for removal detection
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup dedicated logging for real-time monitoring"""
        import sys
        
        # Create separate logger
        self.logger = logging.getLogger('realtime_monitor')
        self.logger.setLevel(logging.INFO)
        
        # Console handler with UTF-8 encoding
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Configure UTF-8 encoding for Windows
        if sys.platform == 'win32':
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except AttributeError:
                # Python < 3.7
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)

    async def initialize(self):
        """Initialize the monitoring system"""
        try:
            self.logger.info("🚀 Initializing Real-time Monitor System...")

            # Read account credentials
            account_file = Path("bet365 account information.txt")
            email = None
            password = None
            if account_file.exists():
                async with aiofiles.open(account_file, 'r') as f:
                    content = await f.read()
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith('email:'):
                            email = line.split(':', 1)[1].strip()
                        elif line.startswith('pass:'):
                            password = line.split(':', 1)[1].strip()
                if email and password:
                    self.logger.info("Account credentials loaded")
                else:
                    self.logger.warning("Could not parse account credentials")
            else:
                self.logger.warning("Account information file not found")

            # Initialize scraper
            self.scraper = EnhancedIntelligentScraper(headless=True, load_wait=10000, email=email, password=password)
            await self.scraper.initialize()
            
            # Initialize update queue
            self.update_queue = asyncio.Queue(maxsize=1000)
            
            # Load existing data
            await self.load_existing_data()
            
            # Get initial data
            await self.initial_data_fetch()
            
            self.start_time = time.time()
            self.is_running = True
            
            self.logger.info("✅ Real-time Monitor System initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize monitor: {e}")
            raise

    async def load_existing_data(self):
        """Load existing games from files"""
        try:
            # Load current games
            if self.current_file.exists():
                async with aiofiles.open(self.current_file, 'r') as f:
                    data = json.loads(await f.read())
                    for game_data in data.get('games', []):
                        game = self.dict_to_game(game_data)
                        self.current_games[game.game_id] = game
                        
            # Load history
            if self.pregame_history_file.exists():
                async with aiofiles.open(self.pregame_history_file, 'r') as f:
                    data = json.loads(await f.read())
                    self.game_history = [self.dict_to_game(g) for g in data.get('games', [])]
            
            # Load current pregame data for comparison
            pregame_file = self.output_dir / "current_pregame_data.json"
            if pregame_file.exists():
                async with aiofiles.open(pregame_file, 'r') as f:
                    data = json.loads(await f.read())
                    if 'sports_data' in data:
                        for sport, sport_data in data['sports_data'].items():
                            for game_dict in sport_data.get('games', []):
                                if 'game_id' in game_dict and game_dict['game_id']:
                                    self.previous_pregame_games[game_dict['game_id']] = game_dict
                    
            self.logger.info(f"📂 Loaded {len(self.current_games)} current games, {len(self.game_history)} historical games, {len(self.previous_pregame_games)} pregame games")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Could not load existing data: {e}")

    async def initial_data_fetch(self):
        """Perform initial data fetch using enhanced scraper directly"""
        try:
            self.logger.info("🔄 Performing initial data fetch...")
            
            # Navigate to bet365 first
            await self.scraper.navigate_to_bet365()
            
            # Use the enhanced scraper's main method directly
            result = await self.scraper.scrape_all_sports()
            
            # Check for pregame game removals before processing new data
            await self.check_pregame_removals(result)
            
            # Process the results
            for sport, sport_data in result.get('sports_data', {}).items():
                games = sport_data.get('games', [])
                self.logger.info(f"📊 Found {len(games)} games in {sport}")
                
                for game_data in games:
                    # Convert dict to Game object for tracking
                    # Handle both dict format (from scrape_all_sports) and Game object format  
                    if isinstance(game_data, dict):
                        # This is a dict from scrape_all_sports
                        team1 = game_data.get('team1', game_data.get('player1_team1', ''))
                        team2 = game_data.get('team2', game_data.get('player2_team2', ''))
                        odds_data = game_data.get('odds', {})
                        date = game_data.get('date', '')
                        time = game_data.get('time', '')
                        sport_name = game_data.get('sport', sport)
                        original_fixture_id = game_data.get('fixture_id', f"{sport}_{game_data.get('game_index', 0)}_{hash(team1 + team2)}")
                        # Use game_id as fixture_id if original is empty or missing for consistent tracking
                        game_id = EnhancedIntelligentScraper.generate_game_id(team1, team2, date, time)
                        if not original_fixture_id or original_fixture_id.strip() == '':
                            fixture_id = game_id  # Use game_id for consistent tracking
                        else:
                            fixture_id = original_fixture_id
                    else:
                        # This is already a Game object
                        team1 = game_data.team1
                        team2 = game_data.team2  
                        odds_data = game_data.odds.to_dict() if game_data.odds else {}
                        date = game_data.date
                        time = game_data.time
                        sport_name = game_data.sport
                        # Use game_id as fixture_id if original is empty or missing for consistent tracking
                        original_fixture_id = game_data.fixture_id
                        game_id = EnhancedIntelligentScraper.generate_game_id(team1, team2, date, time)
                        if not original_fixture_id or original_fixture_id.strip() == '':
                            fixture_id = game_id  # Use game_id for consistent tracking
                        else:
                            fixture_id = original_fixture_id
                        
                    game = Game(
                        sport=sport_name,
                        team1=team1,
                        team2=team2,
                        date=date,
                        time=time,
                        odds=GameOdds(),  # Will be populated from odds_data
                        fixture_id=fixture_id,
                        game_id=game_id
                    )
                    
                    # Populate odds
                    if odds_data:
                        game.odds.spread = odds_data.get('spread', [])
                        game.odds.total = odds_data.get('total', [])
                        game.odds.moneyline = odds_data.get('moneyline', [])
                        game.odds.runline = odds_data.get('runline', [])
                        game.odds.puckline = odds_data.get('puckline', [])
                    
                    self.current_games[game.game_id] = game
            
            self.stats.active_games = len(self.current_games)
            self.logger.info(f"✅ Initial fetch complete: {len(self.current_games)} active games")
            
        except Exception as e:
            self.logger.error(f"❌ Initial data fetch failed: {e}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            self.logger.warning("⚠️ Continuing with empty initial state - monitoring will retry")

    async def check_pregame_removals(self, current_pregame_data: Dict[str, Any]):
        """Check for pregame games that were removed from the website and save to history"""
        try:
            # Get current pregame games
            current_games = {}
            if 'sports_data' in current_pregame_data:
                for sport, sport_data in current_pregame_data['sports_data'].items():
                    for game_dict in sport_data.get('games', []):
                        if 'game_id' in game_dict and game_dict['game_id']:
                            current_games[game_dict['game_id']] = game_dict
            
            # Find removed games (games that were in previous but not in current)
            removed_games = []
            for game_id, game_data in self.previous_pregame_games.items():
                if game_id not in current_games:
                    # Add removal timestamp
                    game_data_copy = game_data.copy()
                    game_data_copy['removed_timestamp'] = datetime.now().isoformat()
                    removed_games.append(game_data_copy)
            
            if removed_games:
                self.logger.info(f"📉 Detected {len(removed_games)} pregame games removed from website")
                
                # Load existing pregame history
                existing_history = []
                if self.pregame_history_file.exists():
                    try:
                        async with aiofiles.open(self.pregame_history_file, 'r') as f:
                            history_data = json.loads(await f.read())
                            existing_history = history_data.get('games', [])
                    except Exception as e:
                        self.logger.warning(f"Could not load existing pregame history: {e}")
                
                # Add new removed games to history
                existing_history.extend(removed_games)
                
                # Keep only last 1000 historical games to prevent file from growing too large
                if len(existing_history) > 1000:
                    existing_history = existing_history[-1000:]
                
                # Save updated history
                history_data = {
                    "timestamp": datetime.now().isoformat(),
                    "total_historical_games": len(existing_history),
                    "games": existing_history
                }
                
                async with aiofiles.open(self.pregame_history_file, 'w') as f:
                    await f.write(json.dumps(history_data, indent=2, ensure_ascii=False))
                
                self.logger.info(f"💾 Saved {len(removed_games)} removed pregame games to history")
                
                # Log sample of removed games
                for i, game in enumerate(removed_games[:3]):  # Show first 3
                    self.logger.info(f"   🗑️ Removed: {game.get('team1', 'N/A')} vs {game.get('team2', 'N/A')} ({game.get('sport', 'N/A')})")
                if len(removed_games) > 3:
                    self.logger.info(f"   ... and {len(removed_games) - 3} more")
            
            # Update our tracking with current games
            self.previous_pregame_games = current_games
            
        except Exception as e:
            self.logger.error(f"Error checking pregame removals: {e}")

    async def start_monitoring(self):
        """Start the real-time monitoring system"""
        try:
            await self.initialize()
            
            self.logger.info(f"🔥 Starting real-time monitoring (interval: {self.update_interval}s)")
            
            # Start background tasks
            tasks = []
            
            # Update processor task
            tasks.append(asyncio.create_task(self.process_updates()))
            
            # File writer task  
            tasks.append(asyncio.create_task(self.periodic_file_writer()))
            
            # Stats updater task
            tasks.append(asyncio.create_task(self.stats_updater()))
            
            # Pregame history checker task (runs every 30 seconds)
            tasks.append(asyncio.create_task(self.periodic_pregame_checker()))
            
            # Get sports to monitor from detected games using actual sport names
            sports_to_monitor = set()
            for game in self.current_games.values():
                if hasattr(game, 'sport') and game.sport:
                    sports_to_monitor.add(game.sport)
            
            if not sports_to_monitor:
                # Default sports list if no games found initially
                sports_to_monitor = {'NBA', 'NHL', 'NFL', 'MLB', 'NCAAF', 'Tennis', 'UFC', 'CFL', 'PGA', 'NCAAB'}
            
            self.logger.info(f"🚀 Will monitor {len(sports_to_monitor)} sports with FAST batch processing: {list(sports_to_monitor)}")
            
            # Start FAST batch monitor instead of sequential
            tasks.append(asyncio.create_task(self.batch_sport_monitor(sports_to_monitor, batch_size=3)))
            
            # Wait for all tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except KeyboardInterrupt:
            self.logger.info("⏹️ Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Monitoring error: {e}")
        finally:
            await self.shutdown()

    async def sequential_sport_monitor(self, sports_to_monitor: set):
        """Monitor sports sequentially using single shared browser with cycle tracking"""
        sports_list = list(sports_to_monitor)
        current_sport_index = 0
        
        self.logger.info(f"🔄 Starting sequential monitoring of {len(sports_list)} sports")
        
        # Initialize sport update counters
        for sport in sports_list:
            self.sport_update_counts[sport] = 0
        
        while self.is_running:
            try:
                # Start cycle tracking
                if current_sport_index == 0:  # Beginning of new cycle
                    self.current_cycle_start = time.time()
                    self.cycle_count += 1
                
                # Get current sport to monitor
                if not sports_list:
                    await asyncio.sleep(self.update_interval)
                    continue
                    
                sport = sports_list[current_sport_index]
                sport_start_time = time.time()
                self.logger.debug(f"🔍 Cycle {self.cycle_count}, Sport {current_sport_index + 1}/{len(sports_list)}: {sport}")
                
                # Extract just this sport to avoid conflicts
                if not self.scraper:
                    self.logger.error("❌ Scraper not initialized")
                    break
                    
                # Use the enhanced scraper's single sport method
                result = await self.scraper.extract_single_sport_realtime(sport)
                
                games_data = []
                if result and 'games' in result and not result.get('error'):
                    games_data = result.get('games', [])
                    
                    if games_data:
                        # Convert to Game objects - handle both formats
                        current_sport_games = []
                        for game_data in games_data:
                            # Handle both dict format and Game object format
                            if isinstance(game_data, Game):
                                # Already a Game object, use directly
                                current_sport_games.append(game_data)
                            else:
                                # Dict format, convert to Game object
                                team1 = game_data.get('team1', game_data.get('player1_team1', ''))
                                team2 = game_data.get('team2', game_data.get('player2_team2', ''))
                                
                                date_clean = game_data.get('date', '')
                                time_clean = game_data.get('time', '')
                                
                                # Generate consistent game_id first
                                game_id = EnhancedIntelligentScraper.generate_game_id(team1, team2, date_clean, time_clean)
                                
                                # Use game_id as fixture_id if original is empty or missing for consistent tracking
                                original_fixture_id = game_data.get('fixture_id', '')
                                if not original_fixture_id or original_fixture_id.strip() == '':
                                    fixture_id = game_id  # Use game_id for consistent tracking
                                else:
                                    fixture_id = original_fixture_id
                                
                                game = Game(
                                    sport=sport,
                                    team1=team1,
                                    team2=team2,
                                    date=date_clean,
                                    time=time_clean,
                                    odds=GameOdds(),
                                    fixture_id=fixture_id,
                                    game_id=game_id
                                )
                                
                                # Populate odds
                                odds_data = game_data.get('odds', {})
                                if odds_data:
                                    game.odds.spread = odds_data.get('spread', [])
                                    game.odds.total = odds_data.get('total', [])
                                    game.odds.moneyline = odds_data.get('moneyline', [])
                                    game.odds.runline = odds_data.get('runline', [])
                                    game.odds.puckline = odds_data.get('puckline', [])
                                
                                current_sport_games.append(game)
                        
                        # Process changes and track updates
                        changes_detected = await self.process_sport_changes(sport, current_sport_games)
                        if changes_detected:
                            self.sport_update_counts[sport] += 1
                        
                        sport_duration = time.time() - sport_start_time
                        self.logger.info(f"✅ {sport}: Found {len(current_sport_games)} games ({sport_duration:.2f}s)")
                        
                        # Log monitoring activity
                        await self.log_sport_activity(sport, len(current_sport_games), sport_duration, changes_detected)
                    else:
                        self.logger.debug(f"⚪ {sport}: No games found")
                        await self.log_sport_activity(sport, 0, time.time() - sport_start_time, False)
                
                # Move to next sport  
                current_sport_index = (current_sport_index + 1) % len(sports_list)
                
                # Complete cycle tracking
                if current_sport_index == 0 and self.current_cycle_start:  # End of cycle
                    cycle_duration = time.time() - self.current_cycle_start
                    self.cycle_history.append({
                        "cycle": self.cycle_count,
                        "duration": cycle_duration,
                        "timestamp": datetime.now().isoformat(),
                        "sports_checked": len(sports_list)
                    })
                    
                    # Keep only last 50 cycles
                    if len(self.cycle_history) > 50:
                        self.cycle_history = self.cycle_history[-50:]
                    
                    self.logger.info(f"🔄 Completed cycle {self.cycle_count} in {cycle_duration:.2f}s")
                
                # Wait between sport checks (shorter interval for sequential monitoring)
                await asyncio.sleep(self.update_interval / len(sports_list))
                
            except Exception as e:
                current_sport = sports_list[current_sport_index] if sports_list else 'unknown'
                self.logger.warning(f"⚠️ Sequential monitor error for {current_sport}: {e}")
                current_sport_index = (current_sport_index + 1) % len(sports_list)
                await asyncio.sleep(1.0)  # Brief pause on error


                


    async def batch_sport_monitor(self, sports_to_monitor: set, batch_size: int = 3):
        """FAST batch monitoring - check multiple sports with optimized timing"""
        sports_list = list(sports_to_monitor)
        current_batch_index = 0
        
        self.logger.info(f"🚀 Starting FAST batch monitoring of {len(sports_list)} sports (batch size: {batch_size})")
        
        # Initialize sport update counters
        for sport in sports_list:
            self.sport_update_counts[sport] = 0
        
        while self.is_running:
            try:
                # Start cycle tracking
                if current_batch_index == 0:  # Beginning of new cycle
                    self.current_cycle_start = time.time()
                    self.cycle_count += 1
                
                # Get current batch to monitor
                if not sports_list:
                    await asyncio.sleep(self.update_interval)
                    continue
                
                # Create batch
                batch_start = current_batch_index
                batch_end = min(current_batch_index + batch_size, len(sports_list))
                current_batch = sports_list[batch_start:batch_end]
                
                batch_start_time = time.time()
                self.logger.debug(f"🏃 Cycle {self.cycle_count}, Batch {batch_start//batch_size + 1}: {current_batch}")
                
                # Process batch concurrently with limited concurrency
                if not self.scraper:
                    self.logger.error("❌ Scraper not initialized")
                    break
                
                # Process sports in batch with minimal delay between checks
                batch_tasks = []
                for sport in current_batch:
                    task = asyncio.create_task(self.process_single_sport_fast(sport))
                    batch_tasks.append(task)
                
                # Wait for batch completion with timeout
                try:
                    await asyncio.wait_for(asyncio.gather(*batch_tasks), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.warning(f"⚠️ Batch timeout for {current_batch}")
                
                # Update batch index
                current_batch_index = batch_end
                if current_batch_index >= len(sports_list):
                    current_batch_index = 0
                    
                    # End of cycle
                    if self.current_cycle_start:
                        cycle_duration = time.time() - self.current_cycle_start
                        self.cycle_history.append({
                            "cycle": self.cycle_count,
                            "duration": cycle_duration,
                            "timestamp": datetime.now().isoformat(),
                            "sports_checked": len(sports_list)
                        })
                        
                        # Keep only last 10 cycles
                        if len(self.cycle_history) > 10:
                            self.cycle_history = self.cycle_history[-10:]
                        
                        self.logger.info(f"🔄 Completed cycle {self.cycle_count} in {cycle_duration:.2f}s")
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(max(0.1, self.update_interval))
                
            except Exception as e:
                self.logger.error(f"❌ Batch monitoring error: {e}")
                await asyncio.sleep(1.0)

    async def process_single_sport_fast(self, sport: str):
        """Fast processing of a single sport"""
        try:
            # Use the enhanced scraper's single sport method (is async)
            result = await self.scraper.extract_single_sport_realtime(sport)
            
            games_data = []
            if result and 'games' in result and not result.get('error'):
                games_data = result.get('games', [])
                
                if games_data:
                    # Convert to Game objects quickly
                    current_sport_games = []
                    for game_data in games_data:
                        if isinstance(game_data, Game):
                            current_sport_games.append(game_data)
                        else:
                            # Quick conversion for real-time
                            team1 = game_data.get('team1', game_data.get('player1_team1', ''))
                            team2 = game_data.get('team2', game_data.get('player2_team2', ''))
                            
                            if team1 and team2:
                                # Create Game object quickly
                                game_id = self._generate_game_id_from_dict(game_data)
                                
                                # Quick odds conversion
                                odds_data = game_data.get('odds', {})
                                odds_obj = GameOdds()
                                if odds_data:
                                    for bet_type, values in odds_data.items():
                                        if isinstance(values, list) and len(values) >= 2:
                                            setattr(odds_obj, bet_type, values)
                                
                                game = Game(
                                    sport=sport,
                                    team1=team1,
                                    team2=team2,
                                    date=game_data.get('date', ''),
                                    time=game_data.get('time', ''),
                                    odds=odds_obj,
                                    fixture_id=game_data.get('fixture_id', game_id)
                                )
                                game.game_id = game_id
                                current_sport_games.append(game)
                    
                    # Process changes quickly
                    if current_sport_games:
                        changes_detected = await self.process_sport_changes(sport, current_sport_games)
                        if changes_detected:
                            self.sport_update_counts[sport] += 1
                            
        except Exception as e:
            self.logger.warning(f"⚠️ Fast processing error for {sport}: {e}")

    async def navigate_to_sport_fast(self, sport: str, tab_name: str):
        """Fast navigation - not needed with direct extraction"""
        # This method is now unused since we use extract_single_sport_realtime
        pass

    async def get_sport_tab_element(self, sport: str, tab_name: str):
        """Get the current sport tab element - not needed with direct extraction"""
        # This method is now unused since we use extract_single_sport_realtime
        return None

    async def process_sport_changes(self, sport: str, current_games: List[Game]) -> bool:
        """Process changes for a specific sport, returns True if changes detected"""
        sport_current_games = {gid: game for gid, game in self.current_games.items()
                              if game.sport == sport}
        new_game_ids = {game.game_id for game in current_games}
        existing_game_ids = set(sport_current_games.keys())

        # Detect changes
        inserted_ids = new_game_ids - existing_game_ids
        deleted_ids = existing_game_ids - new_game_ids
        potential_updates = new_game_ids & existing_game_ids

        changes_detected = False

        # Process insertions - SAVE IMMEDIATELY
        for game in current_games:
            if game.game_id in inserted_ids:
                await self.queue_update(GameUpdate(
                    game=game,
                    change_type='insert',
                    timestamp=datetime.now().isoformat()
                ))
                changes_detected = True
                # Save immediately when new data is found
                await self.write_data_files()
                self.logger.info(f"💾 Saved immediately: New {sport} game {game.team1} vs {game.team2}")

        # Process deletions (move to history)
        for game_id in deleted_ids:
            game = sport_current_games[game_id]
            await self.queue_update(GameUpdate(
                game=game,
                change_type='delete',
                timestamp=datetime.now().isoformat()
            ))
            changes_detected = True

        # Process potential updates - SAVE IMMEDIATELY
        for game in current_games:
            if game.game_id in potential_updates:
                existing_game = sport_current_games[game.game_id]
                changes = self.detect_game_changes(existing_game, game)
                if changes:
                    await self.queue_update(GameUpdate(
                        game=game,
                        change_type='update',
                        timestamp=datetime.now().isoformat(),
                        changes=changes
                    ))
                    changes_detected = True
                    # Save immediately when odds change
                    await self.write_data_files()
                    self.logger.info(f"💾 Saved immediately: Updated {sport} odds for {game.team1} vs {game.team2}")

        return changes_detected

    async def log_sport_activity(self, sport: str, games_found: int, duration: float, changes_detected: bool):
        """Log sport monitoring activity for tracking"""
        activity_entry = {
            "timestamp": datetime.now().isoformat(),
            "sport": sport,
            "cycle": self.cycle_count,
            "games_found": games_found,
            "duration_seconds": round(duration, 2),
            "changes_detected": changes_detected,
            "total_sport_updates": self.sport_update_counts.get(sport, 0)
        }
        
        try:
            # Load existing activity log
            activity_log = []
            if self.statistic_file.exists():
                async with aiofiles.open(self.statistic_file, 'r') as f:
                    data = json.loads(await f.read())
                    activity_log = data.get('activities', [])
            
            # Add new entry
            activity_log.append(activity_entry)
            
            # Keep only last 200 entries to prevent file from growing too large
            if len(activity_log) > 200:
                activity_log = activity_log[-200:]
            
            # Write back to file
            log_data = {
                "monitoring_session": {
                    "started_at": self.start_time,
                    "current_cycle": self.cycle_count,
                    "total_activities": len(activity_log)
                },
                "activities": activity_log
            }
            
            async with aiofiles.open(self.statistic_file, 'w') as f:
                await f.write(json.dumps(log_data, indent=2))
                
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to log sport activity: {e}")

    def detect_game_changes(self, old_game: Game, new_game: Game) -> Dict[str, Any]:
        """Detect changes between two game instances"""
        changes = {}
        
        # Check odds changes
        old_odds = old_game.odds
        new_odds = new_game.odds
        
        if old_odds and new_odds:
            for odds_type in ['moneyline', 'spread', 'total', 'runline']:
                old_val = getattr(old_odds, odds_type, None)
                new_val = getattr(new_odds, odds_type, None)
                if old_val != new_val:
                    changes[f'odds_{odds_type}'] = {'old': old_val, 'new': new_val}
        
        # Check other fields
        for field in ['time', 'date']:
            old_val = getattr(old_game, field, None)
            new_val = getattr(new_game, field, None)
            if old_val != new_val:
                changes[field] = {'old': old_val, 'new': new_val}
        
        return changes

    async def queue_update(self, update: GameUpdate):
        """Queue a game update for processing"""
        try:
            await self.update_queue.put(update)
        except asyncio.QueueFull:
            self.logger.warning("⚠️ Update queue full, dropping oldest update")
            try:
                self.update_queue.get_nowait()
                await self.update_queue.put(update)
            except asyncio.QueueEmpty:
                pass

    async def process_updates(self):
        """Process queued updates"""
        self.logger.info("🔄 Update processor started")
        
        while self.is_running:
            try:
                # Get update with timeout
                update = await asyncio.wait_for(self.update_queue.get(), timeout=1.0)
                
                if update.change_type == 'insert':
                    self.current_games[update.game.game_id] = update.game
                    self.stats.active_games += 1
                    self.logger.info(f"➕ {update.game.sport}: New game {update.game.team1} vs {update.game.team2}")
                    
                elif update.change_type == 'update':
                    self.current_games[update.game.game_id] = update.game
                    self.stats.updates_count += 1
                    changes_str = ", ".join(update.changes.keys()) if update.changes else "unknown"
                    self.logger.info(f"🔄 {update.game.sport}: Updated {update.game.team1} vs {update.game.team2} ({changes_str})")
                    
                elif update.change_type == 'delete':
                    if update.game.game_id in self.current_games:
                        del self.current_games[update.game.game_id]
                        self.stats.active_games -= 1
                        
                    # Move to history
                    self.game_history.append(update.game)
                    self.stats.completed_games += 1
                    self.logger.info(f"🏁 {update.game.sport}: Completed {update.game.team1} vs {update.game.team2}")
                
                self.stats.total_games = len(self.current_games) + len(self.game_history)
                self.stats.last_update = update.timestamp
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"❌ Update processing error: {e}")

    async def periodic_file_writer(self):
        """Periodically write data to files"""
        self.logger.info("💾 File writer started")

        while self.is_running:
            try:
                await asyncio.sleep(5.0)  # Write every 5 seconds
                await self.write_data_files()
                self.logger.info(f"💾 Data saved: {len(self.current_games)} games")
            except Exception as e:
                self.logger.error(f"❌ File writing error: {e}")

    async def write_data_files(self):
        """Update existing pregame JSON with realtime odds data - SAVE IMMEDIATELY WHEN DATA IS FOUND"""
        try:
            # Always create/update the current file with latest data
            current_data = {
                "extraction_info": {
                    "timestamp": datetime.now().isoformat(),
                    "session_id": self.session_id,
                    "total_games": len(self.current_games),
                    "status": "active" if self.is_running else "completed"
                },
                "sports_data": {}
            }

            # Group games by sport
            for game in self.current_games.values():
                sport = game.sport
                if sport not in current_data["sports_data"]:
                    current_data["sports_data"][sport] = {"games": []}

                current_data["sports_data"][sport]["games"].append(self.game_to_dict(game))

            # Write current data immediately
            async with aiofiles.open(self.current_file, 'w') as f:
                await f.write(json.dumps(current_data, indent=2, ensure_ascii=False))

            # Write history (only if we have history items)
            if self.game_history:
                history_data = {
                    "timestamp": datetime.now().isoformat(),
                    "total_completed": len(self.game_history),
                    "games": [self.game_to_dict(game) for game in self.game_history]
                }

                async with aiofiles.open(self.pregame_history_file, 'w') as f:
                    await f.write(json.dumps(history_data, indent=2))

            # Write monitoring cycle stats
            cycle_data = {
                "monitoring_session": {
                    "timestamp": datetime.now().isoformat(),
                    "session_id": self.session_id,
                    "status": "active" if self.is_running else "stopped",
                    "uptime_seconds": round(self.stats.uptime_seconds, 2)
                },
                "cycle_statistics": {
                    "cycle_count": self.cycle_count,
                    "total_active_games": len(self.current_games),
                    "recent_cycles": self.cycle_history[-10:] if self.cycle_history else []
                },
                "sport_statistics": {
                    sport: {
                        "update_count": count,
                        "last_checked": datetime.now().isoformat()
                    }
                    for sport, count in self.sport_update_counts.items()
                }
            }

            async with aiofiles.open(self.statistic_file, 'w') as f:
                await f.write(json.dumps(cycle_data, indent=2, ensure_ascii=False))

        except Exception as e:
            self.logger.error(f"❌ Failed to write data files: {e}")

    async def periodic_pregame_checker(self):
        """Periodically check for pregame game removals"""
        while self.is_running:
            try:
                await asyncio.sleep(30.0)  # Check every 30 seconds
                
                if not self.scraper:
                    continue
                    
                self.logger.debug("🔍 Checking for pregame game removals...")
                
                # Get fresh pregame data
                result = await self.scraper.scrape_all_sports()
                
                if result and 'sports_data' in result:
                    await self.check_pregame_removals(result)
                    
            except Exception as e:
                self.logger.error(f"❌ Pregame checker error: {e}")
                await asyncio.sleep(30.0)  # Wait before retrying

    async def stats_updater(self):
        """Update monitoring statistics"""
        while self.is_running:
            try:
                if self.start_time:
                    self.stats.uptime_seconds = time.time() - self.start_time
                    
                # Log periodic status
                if int(self.stats.uptime_seconds) % 30 == 0:  # Every 30 seconds
                    self.logger.info(f"📊 Status: {self.stats.active_games} active, "
                                   f"{self.stats.completed_games} completed, "
                                   f"{self.stats.updates_count} updates, "
                                   f"uptime: {self.stats.uptime_seconds:.0f}s")
                
                await asyncio.sleep(1.0)
            except Exception as e:
                self.logger.error(f"❌ Stats update error: {e}")

    def game_to_dict(self, game: Game) -> Dict:
        """Convert Game object to dictionary"""
        return {
            "sport": game.sport,
            "team1": game.team1,
            "team2": game.team2,
            "date": game.date,
            "time": game.time,
            "fixture_id": game.fixture_id,
            "confidence_score": game.confidence_score,
            "game_id": game.game_id,
            "odds": {
                "moneyline": game.odds.moneyline if game.odds else [],
                "spread": game.odds.spread if game.odds else [],
                "total": game.odds.total if game.odds else [],
                "runline": game.odds.runline if game.odds else []
            }
        }

    def dict_to_game(self, data: Dict) -> Game:
        """Convert dictionary to Game object"""
        odds_data = data.get('odds', {})
        odds = GameOdds(
            moneyline=odds_data.get('moneyline', []),
            spread=odds_data.get('spread', []),
            total=odds_data.get('total', []),
            runline=odds_data.get('runline', [])
        )
        
        team1 = data['team1']
        team2 = data['team2']
        date = data.get('date')
        time = data.get('time')
        
        # Generate consistent game_id first
        game_id = data.get('game_id', EnhancedIntelligentScraper.generate_game_id(team1, team2, date, time))
        
        # Use game_id as fixture_id if original is empty or missing for consistent tracking
        original_fixture_id = data.get('fixture_id', '')
        if not original_fixture_id or original_fixture_id.strip() == '':
            fixture_id = game_id  # Use game_id for consistent tracking
        else:
            fixture_id = original_fixture_id
        
        return Game(
            sport=data['sport'],
            team1=team1,
            team2=team2,
            date=date,
            time=time,
            fixture_id=fixture_id,
            odds=odds,
            game_id=game_id
        )

    def _generate_game_id_from_dict(self, game_dict: Dict) -> str:
        """Generate game_id from game dictionary for matching"""
        team1 = game_dict.get('team1', '')
        team2 = game_dict.get('team2', '')
        date = game_dict.get('date', '')
        time = game_dict.get('time', '')
        return EnhancedIntelligentScraper.generate_game_id(team1, team2, date, time)

    async def shutdown(self):
        """Graceful shutdown of monitoring system"""
        self.logger.info("🛑 Shutting down monitoring system...")
        self.is_running = False
        
        # Cancel all sport tasks
        for sport, task in self.sports_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Final file write
        await self.write_data_files()
        
        # Close scraper
        if self.scraper:
            await self.scraper.close()
        
        self.logger.info("✅ Monitoring system shut down complete")


async def main():
    """Main function to start FAST real-time monitoring"""
    monitor = RealTimeMonitor(update_interval=0.2)  # FAST mode: 5x faster
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Real-time monitoring stopped by user")
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())