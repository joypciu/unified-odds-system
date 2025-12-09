"""
1XBET PREGAME DATA COLLECTOR - ADVANCED VERSION
================================================
Features:
- Multi-sport support (all available sports)
- Real-time monitoring with insert/update operations
- JSON file storage for data persistence
- Concurrent request handling for faster collection
- Smart delta updates (only changed data)
- Comprehensive logging and statistics
"""

import asyncio
import aiohttp
import json
import zlib
import base64
from datetime import datetime
from typing import Dict, List, Set, Any
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('1xbet_collector.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    import zstandard
    HAS_ZSTD = True
    logger.debug("zstandard module imported successfully")
except ImportError:
    HAS_ZSTD = False
    logger.warning("zstandard not installed - install with: pip install zstandard")


@dataclass
class Match:
    """Match data structure"""
    match_id: int
    sport_id: int
    sport_name: str
    league_id: int
    league_name: str
    team1: str
    team1_id: int
    team2: str
    team2_id: int
    start_time: int
    country: str
    country_id: int
    odds_data: str  # JSON string of all odds
    last_updated: int
    
    def to_dict(self):
        return asdict(self)


class JsonDataManager:
    """Manages JSON file data operations"""
    
    def __init__(self, data_dir: str = ""):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.main_file = self.data_dir / "1xbet_pregame.json"
        self.stats_file = self.data_dir / "1xbet_statistics.json"
        self.history_file = self.data_dir / "1xbet_history.json"  # Unified history file
        self.futures_file = self.data_dir / "1xbet_futures.json"  # Separate futures/long-term events
        self.init_data_files()

    
    def init_data_files(self):
        """Initialize JSON data files"""
        # Initialize empty data structures
        if not self.main_file.exists():
            self._save_main_data({})
        if not self.stats_file.exists():
            self._save_stats_data({})
        
        logger.info(f"JSON data files initialized in: {self.data_dir}")
    
    def _load_json(self, file_path: Path) -> dict:
        """Load data from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_json(self, file_path: Path, data: dict):
        """Save data to JSON file with atomic write"""
        import tempfile
        import shutil
        
        # Write to temporary file first
        temp_file = file_path.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Replace original file with temp file (atomic on most systems)
            shutil.move(str(temp_file), str(file_path))
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()
            logger.error(f"Error saving JSON to {file_path}: {e}")
            raise
    
    def _save_main_data(self, data: dict):
        """Save main data with metadata structure"""
        from datetime import datetime
        import uuid
        
        main_data = {
            "metadata": {
                "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "timestamp": datetime.now().isoformat(),
                "collector_version": "pregame_v2.0",
                "total_records": len(data),
                "data_type": "pregame",
                "source": "1xbet"
            },
            "data": {
                "matches": list(data.values())
            }
        }
        self._save_json(self.main_file, main_data)
    
    def _save_stats_data(self, stats: dict):
        """Save statistics data with pregame and live breakdowns"""
        from datetime import datetime

        # Load existing stats to preserve live data
        existing_stats = {}
        if self.stats_file.exists():
            try:
                existing_stats = self._load_json(self.stats_file)
            except:
                existing_stats = {}

        # Generate pregame statistics
        pregame_stats = self._generate_pregame_stats()

        # Preserve live stats if they exist
        live_stats = existing_stats.get('live', {})

        stats_data = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.now().isoformat(),
            "pregame": pregame_stats,
            "live": live_stats,
            "total_matches": stats.get('total_matches', 0),
            "total_sports": stats.get('total_sports', 0),
            "total_leagues": stats.get('total_leagues', 0),
            "new_matches": stats.get('new_matches', 0),
            "updated_matches": stats.get('updated_matches', 0),
            "collection_time_seconds": stats.get('collection_time', 0)
        }
        self._save_json(self.stats_file, stats_data)

    def _generate_pregame_stats(self) -> dict:
        """Generate statistics for pregame matches"""
        try:
            main_data = self._load_json(self.main_file)
            matches = main_data.get('data', {}).get('matches', [])

            total_matches = len(matches)
            sports_count = {}
            sports_names = {}

            for match in matches:
                sport_name = match.get('sport_name', 'Unknown')
                if sport_name not in sports_count:
                    sports_count[sport_name] = 0
                    sports_names[sport_name] = sport_name
                sports_count[sport_name] += 1

            return {
                "total_matches": total_matches,
                "total_sports": len(sports_count),
                "sports": sports_count
            }
        except Exception as e:
            logger.error(f"Error generating pregame stats: {e}")
            return {"total_matches": 0, "total_sports": 0, "sports": {}}
    
    def _convert_odds_to_readable(self, raw_odds: dict) -> dict:
        """Convert 1xbet's cryptic odds codes to readable format with American odds"""
        readable_odds = {}
        
        for key, value in raw_odds.items():
            try:
                group, bet_type = key.split('_')
                group = int(group)
                bet_type = int(bet_type)
                
                # Use American odds if available, otherwise use coefficient
                american_odds = value.get('american_odds', '')
                coefficient = value.get('coefficient', 0)
                param = value.get('param')
                
                # Format odds string - use American odds format
                odds_str = f"{american_odds}" if american_odds else str(coefficient)
                
                if group == 1:  # Moneyline
                    if bet_type == 1:
                        readable_odds['moneyline_home'] = odds_str
                    elif bet_type == 3:
                        readable_odds['moneyline_away'] = odds_str
                    elif bet_type == 2:
                        readable_odds['moneyline_draw'] = odds_str
                        
                elif group == 2:  # Spread/Handicap
                    if bet_type == 7:  # Home handicap
                        readable_odds['spread_home'] = f"{param} ({odds_str})"
                    elif bet_type == 8:  # Away handicap
                        readable_odds['spread_away'] = f"{param} ({odds_str})"
                        
                elif group == 15:  # Totals/Over-Under
                    if bet_type == 11:  # Over
                        readable_odds['total_over'] = f"O {param} ({odds_str})"
                    elif bet_type == 12:  # Under
                        readable_odds['total_under'] = f"U {param} ({odds_str})"
                        
                elif group == 17:  # Game totals (sets, etc.)
                    if bet_type == 9:  # Over
                        readable_odds['sets_over'] = f"O {param} ({odds_str})"
                    elif bet_type == 10:  # Under
                        readable_odds['sets_under'] = f"U {param} ({odds_str})"
                        
                elif group == 62:  # Additional totals
                    if bet_type == 13:  # Over
                        readable_odds['points_over'] = f"O {param} ({odds_str})"
                    elif bet_type == 14:  # Under
                        readable_odds['points_under'] = f"U {param} ({odds_str})"
                        
            except (ValueError, AttributeError):
                # Keep original format for unrecognized codes
                readable_odds[key] = value
                
        return readable_odds
    
    def upsert_match(self, match: Match) -> str:
        """Insert or update a match. Returns 'insert' or 'update'"""
        main_data = self._load_json(self.main_file)
        matches = main_data.get('data', {}).get('matches', [])

        match_dict = match.to_dict()
        match_id = match.match_id

        # Check for duplicates by team names and sport (not just match_id)
        # This prevents the same match from being added multiple times with different IDs
        existing_index = None
        duplicate_found = False

        for i, m in enumerate(matches):
            if m.get('match_id') == match_id:
                existing_index = i
                break
            # Check for duplicate by teams and sport
            elif (m.get('sport_name') == match_dict.get('sport_name') and
                  m.get('team1') == match_dict.get('team1') and
                  m.get('team2') == match_dict.get('team2')):
                # Found duplicate match - skip adding
                duplicate_found = True
                logger.warning(f"Duplicate match detected: {match_dict.get('team1')} vs {match_dict.get('team2')} ({match_dict.get('sport_name')}) - skipping")
                return 'duplicate'

        if duplicate_found:
            return 'duplicate'

        now = int(time.time())
        match_dict['last_updated'] = now

        # Parse odds_data from JSON string to object and convert to readable format
        if isinstance(match_dict.get('odds_data'), str):
            try:
                raw_odds = json.loads(match_dict['odds_data'])
                match_dict['odds_data'] = self._convert_odds_to_readable(raw_odds)
            except json.JSONDecodeError:
                match_dict['odds_data'] = {}
        elif isinstance(match_dict.get('odds_data'), dict):
            match_dict['odds_data'] = self._convert_odds_to_readable(match_dict['odds_data'])

        # Convert start_time from Unix timestamp to readable date/time format like bet365
        if isinstance(match_dict.get('start_time'), (int, float)):
            from datetime import datetime
            dt = datetime.fromtimestamp(match_dict['start_time'])

            # Format date like bet365: "Thu Nov 06"
            match_dict['date'] = dt.strftime("%a %b %d")

            # Format time like bet365: "9:10 PM" (12-hour format)
            match_dict['time'] = dt.strftime("%I:%M %p")

            # Keep ISO format for compatibility
            match_dict['scheduled_time'] = dt.isoformat() + 'Z'
            # Keep original timestamp for compatibility
            match_dict['start_time_unix'] = match_dict['start_time']

        if existing_index is not None:
            # Check if odds changed
            if matches[existing_index].get('odds_data') != match_dict.get('odds_data'):
                match_dict['created_at'] = matches[existing_index].get('created_at', now)
                matches[existing_index] = match_dict
                main_data['data']['matches'] = matches
                main_data['metadata']['total_records'] = len(matches)
                self._save_json(self.main_file, main_data)
                return 'update'
            return 'no_change'
        else:
            # Insert new match
            match_dict['created_at'] = now
            matches.append(match_dict)
            main_data['data']['matches'] = matches
            main_data['metadata']['total_records'] = len(matches)
            self._save_json(self.main_file, main_data)
            return 'insert'
    
    def update_sport_stats(self, sport_id: int, sport_name: str, match_count: int):
        """Update sport statistics - stored in main file"""
        pass  # Sports stats are derived from matches
    
    def update_league_stats(self, league_id: int, league_name: str, sport_id: int, 
                           country: str, match_count: int):
        """Update league statistics - stored in main file"""
        pass  # League stats are derived from matches
    
    def save_collection_stats(self, stats: dict):
        """Save collection statistics"""
        self._save_stats_data(stats)
    
    def separate_futures_from_pregame(self):
        """
        Separate future/long-term events (sport_id 2999) into separate file
        
        NOTE: This method separates futures but they won't have odds because
        futures use a different API structure (outrights with multiple selections).
        Use 1xbet_futures_scraper.py to fetch futures with proper odds.
        """
        main_data = self._load_json(self.main_file)
        matches = main_data.get('data', {}).get('matches', [])
        
        # Separate matches into futures and regular pregame
        futures_matches = []
        pregame_matches = []
        
        for match in matches:
            # Sport ID 2999 is 'Long-term bets' or future events
            if match.get('sport_id') == 2999 or match.get('sport_name') == 'Long-term bets':
                futures_matches.append(match)
            else:
                pregame_matches.append(match)
        
        if futures_matches:
            # Save futures to separate file (without odds - use futures_scraper for odds)
            futures_data = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'total_records': len(futures_matches),
                    'data_type': 'futures_basic',
                    'source': '1xbet',
                    'description': 'Long-term bets and future events (basic info only - use 1xbet_futures_scraper.py for odds)',
                    'note': 'These events have empty odds_data. Run 1xbet_futures_scraper.py to fetch proper outright odds.'
                },
                'data': {
                    'matches': futures_matches
                }
            }
            
            with open(self.futures_file, 'w', encoding='utf-8') as f:
                json.dump(futures_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🔮 Separated {len(futures_matches)} future/long-term events to {self.futures_file.name}")
            
            # Update main file with only pregame matches
            main_data['data']['matches'] = pregame_matches
            main_data['metadata']['total_records'] = len(pregame_matches)
            main_data['metadata']['futures_count'] = len(futures_matches)
            self._save_json(self.main_file, main_data)
            
            return len(futures_matches)
        
        return 0
    
    def move_removed_matches_to_history(self, current_match_ids: set):
        """Move matches that are no longer in current collection to unified history"""
        main_data = self._load_json(self.main_file)
        matches = main_data.get('data', {}).get('matches', [])
        
        # Get existing match IDs
        existing_match_ids = {match.get('match_id') for match in matches}
        
        # Find removed matches
        removed_match_ids = existing_match_ids - current_match_ids
        
        if not removed_match_ids:
            return 0
        
        # Load existing history
        history_data = {'metadata': {}, 'live': [], 'pregame': []}
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                # Ensure both sections exist
                if 'live' not in history_data:
                    history_data['live'] = []
                if 'pregame' not in history_data:
                    history_data['pregame'] = []
            except (json.JSONDecodeError, FileNotFoundError):
                history_data = {'metadata': {}, 'live': [], 'pregame': []}
        
        # Find and move removed matches
        removed_matches = []
        updated_matches = []
        
        for match in matches:
            if match.get('match_id') in removed_match_ids:
                # Add to history
                match_copy = match.copy()
                match_copy['removed_at'] = int(time.time())
                match_copy['removed_at_readable'] = datetime.now().isoformat()
                match_copy['status'] = 'expired'
                match_copy['match_type'] = 'pregame'
                removed_matches.append(match_copy)
            else:
                # Keep in main data
                updated_matches.append(match)
        
        if removed_matches:
            # Update pregame section of history
            history_data['pregame'].extend(removed_matches)
            history_data['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'total_live_matches': len(history_data['live']),
                'total_pregame_matches': len(history_data['pregame']),
                'total_matches': len(history_data['live']) + len(history_data['pregame']),
                'last_updated': int(time.time())
            }
            
            # Save history
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            # Update main data (remove expired matches)
            main_data['data']['matches'] = updated_matches
            main_data['metadata']['total_records'] = len(updated_matches)
            self._save_json(self.main_file, main_data)
            
            logger.info(f"📋 Moved {len(removed_matches)} expired pregame matches to history")
            return len(removed_matches)
        
        return 0


class XBetCollector:
    """Advanced 1xbet data collector"""
    
    def __init__(self, base_url: str = "https://1xbet.com"):
        self.base_url = base_url
        self.db = JsonDataManager()
        self.session = None
        self.semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent requests
        self.current_match_ids = set()  # Track current match IDs for history management
        self.stats = {
            'new_matches': 0,
            'updated_matches': 0,
            'total_matches': 0,
            'total_sports': 0,
            'total_leagues': 0,
            'collection_time': 0.0
        }
        
        # Sport IDs mapping (from the data)
        self.sport_ids = {
            1: 'Football',
            2: 'Ice Hockey',
            3: 'Basketball',
            4: 'Tennis',
            6: 'Volleyball',
            10: 'Table Tennis',
            13: 'American Football',
            40: 'Esports',
            # Add more as needed
        }
    
    async def init_session(self):
        """Initialize aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://1xbet.com',
            'Referer': 'https://1xbet.com/'
        }
        connector = aiohttp.TCPConnector()
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=connector,
            auto_decompress=False
        )
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
    
    def decompress_response(self, data: bytes) -> Dict:
        """Decompress VZip response with support for gzip, zstd, and zlib"""
        try:
            logger.debug(f"Decompressing data, length: {len(data)}")
            
            # Check for gzip magic number (1f 8b)
            if len(data) >= 2 and data[0] == 0x1f and data[1] == 0x8b:
                try:
                    decompressed = zlib.decompress(data, zlib.MAX_WBITS | 16)  # 16 for gzip
                    result = json.loads(decompressed.decode('utf-8'))
                    logger.debug("✓ Successfully decompressed with gzip")
                    return result
                except Exception as ge:
                    logger.debug(f"gzip decompression failed: {ge}")
            
            # Try zstd (1xBet sometimes uses zstd compression)
            if HAS_ZSTD:
                try:
                    dctx = zstandard.ZstdDecompressor()
                    dobj = dctx.decompressobj()
                    decompressed = dobj.decompress(data)
                    result = json.loads(decompressed.decode('utf-8'))
                    logger.debug("✓ Successfully decompressed with zstd")
                    return result
                except zstandard.ZstdError as ze:
                    logger.debug(f"zstd error: {ze}")
                except Exception as ze:
                    logger.debug(f"zstd decompression failed: {ze}")
            
            # Fallback to zlib (raw deflate)
            try:
                decompressed = zlib.decompress(data)
                result = json.loads(decompressed.decode('utf-8'))
                logger.debug("✓ Successfully decompressed with zlib")
                return result
            except Exception as zle:
                logger.debug(f"zlib decompression failed: {zle}")
            
            # Try direct JSON (uncompressed)
            try:
                result = json.loads(data.decode('utf-8'))
                logger.debug("✓ Data was not compressed")
                return result
            except Exception as je:
                logger.debug(f"Direct JSON decode failed: {je}")
            
            logger.error("All decompression methods failed")
            return {}
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return {}
    
    async def fetch_sports_list(self) -> List[Dict]:
        """Fetch list of all available sports with pregame matches"""
        async with self.semaphore:
            url = f"{self.base_url}/service-api/LineFeed/GetSportsShortZip"
            params = {
                'lng': 'en',
                'country': '19',
                'gr': '285'
            }
            
            try:
                logger.info(f"Fetching pregame sports list from {url}")
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        # Read raw bytes and manually decompress
                        raw_data = await response.read()
                        data = self.decompress_response(raw_data)
                        
                        if data.get('Success') and data.get('Value'):
                            sports = data['Value']
                            logger.info(f"✓ Found {len(sports)} sports with pregame matches")
                            
                            # Filter sports that have visible pregame matches (C > 0 or V > 0)
                            pregame_sports = [s for s in sports if s.get('C', 0) > 0 or s.get('CC', 0) > 0]
                            logger.info(f"✓ {len(pregame_sports)} sports have active pregame matches")
                            return pregame_sports
                        else:
                            logger.error(f"API returned Success=False: {data.get('Error', 'Unknown error')}")
                    else:
                        logger.warning(f"HTTP {response.status} for sports list")
            except Exception as e:
                logger.error(f"Error fetching sports list: {e}")
            
            return []
    
    async def fetch_sport_data(self, sport_id: int) -> Dict:
        """Fetch all pregame matches for a specific sport"""
        async with self.semaphore:
            url = f"{self.base_url}/service-api/LineFeed/Get1x2_VZip"
            params = {
                'sports': str(sport_id),
                'count': '500',
                'lng': 'en',
                'cfview': '2',  # Required for pregame
                'mode': '4'      # Required for pregame
            }
            
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        # Read raw bytes and manually decompress
                        raw_data = await response.read()
                        data = self.decompress_response(raw_data)
                        if data.get('Success'):
                            matches_count = len(data.get('Value', []))
                            if matches_count > 0:
                                logger.info(f"✓ Sport {sport_id}: Found {matches_count} pregame matches")
                            return data
                        else:
                            logger.debug(f"Sport {sport_id}: API returned Success=False")
                    else:
                        logger.warning(f"HTTP {response.status} for sport {sport_id}")
            except Exception as e:
                logger.error(f"Error fetching sport {sport_id}: {e}")
            
            return {}
    
    def parse_match(self, match_data: Dict, sport_id: int, sport_name: str) -> Match:
        """Parse match data into Match object"""
        
        # Extract odds with American format
        odds = {}
        if 'E' in match_data:
            for odd in match_data['E']:
                odds[f"{odd.get('G', 0)}_{odd.get('T', 0)}"] = {
                    'coefficient': odd.get('C', 0),
                    'american_odds': odd.get('CV', ''),  # CV contains American odds
                    'param': odd.get('P', None)
                }
        
        return Match(
            match_id=match_data.get('I', 0),
            sport_id=sport_id,
            sport_name=sport_name,
            league_id=match_data.get('LI', 0),
            league_name=match_data.get('L', ''),
            team1=match_data.get('O1', ''),
            team1_id=match_data.get('O1I', 0),
            team2=match_data.get('O2', ''),
            team2_id=match_data.get('O2I', 0),
            start_time=match_data.get('S', 0),
            country=match_data.get('CN', ''),
            country_id=match_data.get('COI', 0),
            odds_data=json.dumps(odds),
            last_updated=int(time.time())
        )
    
    async def collect_all_sports(self):
        """Collect pregame data from all available sports"""
        start_time = time.time()
        
        logger.info("=" * 70)
        logger.info("Starting PREGAME collection...")
        logger.info("=" * 70)
        
        # Reset statistics
        self.stats = {
            'new_matches': 0,
            'updated_matches': 0,
            'total_matches': 0,
            'total_sports': 0,
            'total_leagues': 0,
            'collection_time': 0.0
        }
        
        # Reset current match IDs tracking
        self.current_match_ids = set()
        
        # Get all sports with pregame matches
        sports_list = await self.fetch_sports_list()
        
        if not sports_list:
            logger.warning("No sports with pregame matches found")
            return
        
        logger.info(f"Found {len(sports_list)} sports with pregame matches")
        logger.info("Collecting pregame matches from each sport...")
        
        sport_stats = {}
        league_stats = {}
        
        # Collect data for each sport concurrently
        tasks = []
        for sport in sports_list:
            sport_id = sport.get('I', 0)
            sport_name = sport.get('N', 'Unknown')
            
            if sport_id > 0:
                tasks.append(self.process_sport(sport_id, sport_name, sport_stats, league_stats))
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks)
        
        logger.info(f"\n✓ Total pregame matches collected: {self.stats['total_matches']}")
        
        # Update sport statistics
        for sport_id, data in sport_stats.items():
            self.db.update_sport_stats(sport_id, data['name'], data['count'])
        
        # Update league statistics
        for league_id, data in league_stats.items():
            self.db.update_league_stats(
                league_id, data['name'], data['sport_id'],
                data['country'], data['count']
            )
        
        # Calculate final statistics
        self.stats['collection_time'] = time.time() - start_time
        self.stats['total_sports'] = len(sport_stats)
        self.stats['total_leagues'] = len(league_stats)
        
        # Save collection statistics
        self.db.save_collection_stats(self.stats)
        
        # Move expired matches to history
        removed_count = self.db.move_removed_matches_to_history(self.current_match_ids)
        if removed_count > 0:
            logger.info(f"📋 Moved {removed_count} expired pregame matches to history")
        
        # Separate future/long-term events to dedicated file
        futures_count = self.db.separate_futures_from_pregame()
        if futures_count > 0:
            logger.info(f"🔮 {futures_count} future/long-term events in separate file")
        
        # Print summary
        self.print_summary()
    
    async def process_sport(self, sport_id: int, sport_name: str,
                            sport_stats: Dict, league_stats: Dict):
        """Process a single sport"""
        data = await self.fetch_sport_data(sport_id)

        if not data.get('Success') or not data.get('Value'):
            return

        matches = data['Value']
        match_count = len(matches)

        if match_count > 0:
            logger.info(f"  ✓ {sport_name}: {match_count} pregame matches")

        # Update sport stats
        sport_stats[sport_id] = {
            'name': sport_name,
            'count': match_count
        }

        # Process each match
        for match_data in matches:
            try:
                match = self.parse_match(match_data, sport_id, sport_name)

                # Track current match ID for history management
                self.current_match_ids.add(match.match_id)

                # Upsert match
                result = self.db.upsert_match(match)

                if result == 'insert':
                    self.stats['new_matches'] += 1
                    self.stats['total_matches'] += 1
                elif result == 'update':
                    self.stats['updated_matches'] += 1
                    self.stats['total_matches'] += 1
                elif result == 'duplicate':
                    pass  # Silently skip duplicates

                # Update league stats
                league_id = match.league_id
                if league_id not in league_stats:
                    league_stats[league_id] = {
                        'name': match.league_name,
                        'sport_id': sport_id,
                        'country': match.country,
                        'count': 0
                    }
                league_stats[league_id]['count'] += 1

            except Exception as e:
                logger.error(f"Error processing match: {e}")
    
    def print_summary(self):
        """Print collection summary"""
        logger.info("\n" + "=" * 70)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total Sports:        {self.stats['total_sports']}")
        logger.info(f"Total Leagues:       {self.stats['total_leagues']}")
        logger.info(f"Total Matches:       {self.stats['total_matches']}")
        logger.info(f"New Matches:         {self.stats['new_matches']}")
        logger.info(f"Updated Matches:     {self.stats['updated_matches']}")
        logger.info(f"Collection Time:     {self.stats['collection_time']:.2f} seconds")
        logger.info("=" * 70)
    
    async def monitor_realtime(self, interval_seconds: int = 30):
        """Monitor and update data in real-time"""
        logger.info(f"\nStarting real-time monitoring (interval: {interval_seconds}s)")
        logger.info("Press Ctrl+C to stop\n")
        
        try:
            while True:
                await self.collect_all_sports()
                logger.info(f"\nWaiting {interval_seconds} seconds until next update...")
                await asyncio.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user")


async def main():
    """Main function"""
    import sys
    
    print("1XBET PREGAME MATCHES COLLECTOR")
    print("="*45)
    print()
    
    # Check command line arguments
    monitor_mode = len(sys.argv) > 1 and sys.argv[1] == "--monitor"
    
    collector = XBetCollector()
    
    try:
        await collector.init_session()
        
        if monitor_mode:
            # Real-time monitoring (update every 30 seconds)
            logger.info("🚀 Starting realtime monitoring mode (30s intervals)...")
            logger.info("Use without --monitor flag for one-time collection only.")
            await collector.monitor_realtime(interval_seconds=30)
        else:
            # Single collection (default)
            logger.info("Starting single pregame matches collection...")
            await collector.collect_all_sports()
            
            if collector.stats['total_matches'] > 0:
                logger.info(f"\n✓ Successfully collected {collector.stats['total_matches']} pregame matches!")
            else:
                logger.warning("\nNo pregame matches found.")
        
    finally:
        await collector.close_session()


if __name__ == "__main__":
    asyncio.run(main())