"""
1XBET LIVE DATA COLLECTOR - REALTIME MONITORING
===============================================
Collects live/in-play matches from 1xbet with scores and odds
Features realtime monitoring with 1-second intervals
"""

import asyncio
import aiohttp
import json
import zlib
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import zstandard
    HAS_ZSTD = True
    logger.debug("zstandard module imported successfully")
except ImportError:
    HAS_ZSTD = False
    logger.warning("zstandard not installed - install with: pip install zstandard")


class LiveCollector:
    """1xbet live matches collector"""
    
    def __init__(self, base_url="https://1xbet.com", data_dir: str = "."):
        self.base_url = base_url
        self.data_dir = Path(data_dir)
        # Don't create subdirectory - save in current directory
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {'new': 0, 'updated': 0, 'total': 0, 'sports': 0, 'time': 0.0}
        self.data_file = self.data_dir / "1xbet_live.json"
        self.history_file = self.data_dir / "1xbet_history.json"  # Unified history file
        self.matches = {}  # Store matches by ID
        self.previous_match_ids = set()  # Track matches from previous collection
    
    async def init(self):
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://1xbet.com',
            'Referer': 'https://1xbet.com/'
        }
        # Create connector that skips auto-decompression
        connector = aiohttp.TCPConnector()
        self.session = aiohttp.ClientSession(
            timeout=timeout, 
            headers=headers,
            connector=connector,
            auto_decompress=False  # Disable automatic decompression
        )
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    def decompress(self, data: bytes) -> Dict:
        """Decompress VZip response with gzip/zstd support"""
        try:
            logger.debug(f"Decompressing data, length: {len(data)}, first 20 bytes: {data[:20]}")
            
            # Check for gzip magic number (1f 8b) - 1xBet API returns gzip compressed data
            if len(data) >= 2 and data[0] == 0x1f and data[1] == 0x8b:
                try:
                    # Use zlib with gzip header (MAX_WBITS | 16)
                    decompressed = zlib.decompress(data, zlib.MAX_WBITS | 16)
                    result = json.loads(decompressed.decode('utf-8'))
                    logger.info("✓ Successfully decompressed with gzip")
                    return result
                except Exception as ge:
                    logger.debug(f"gzip decompression failed: {ge}")
            
            # Try zstd (in case API changes back)
            if HAS_ZSTD:
                try:
                    dctx = zstandard.ZstdDecompressor()
                    # Use decompressobj for streaming decompression (handles frames without content size)
                    dobj = dctx.decompressobj()
                    decompressed = dobj.decompress(data)
                    result = json.loads(decompressed.decode('utf-8'))
                    logger.info("✓ Successfully decompressed with zstd")
                    return result
                except zstandard.ZstdError as ze:
                    logger.debug(f"zstd error: {ze}")
                except Exception as ze:
                    logger.debug(f"zstd decompression failed: {ze}")
            else:
                logger.debug("zstandard not available")
            
            # Fallback to raw zlib
            try:
                decompressed = zlib.decompress(data)
                result = json.loads(decompressed.decode('utf-8'))
                logger.info("✓ Successfully decompressed with zlib")
                return result
            except Exception as zle:
                logger.debug(f"zlib decompression failed: {zle}")
                
            # Try direct JSON (uncompressed)
            try:
                result = json.loads(data.decode('utf-8'))
                logger.info("✓ Data was not compressed")
                return result
            except Exception as je:
                logger.debug(f"Direct JSON decode failed: {je}")
                
            logger.error("All decompression methods failed")
            return {}
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return {}
    
    def _convert_odds_to_readable(self, raw_odds: dict) -> dict:
        """Convert 1xbet's cryptic odds codes to readable format with American odds"""
        readable_odds = {}
        
        for key, value in raw_odds.items():
            try:
                group, bet_type = key.split('_')
                group = int(group)
                bet_type = int(bet_type)
                
                # Use American odds (CV) if available, otherwise use coefficient (C)
                american_odds = value.get('american_odds', '')
                coefficient = value.get('coefficient', 0)
                param = value.get('param')
                
                # Format odds string - show both American and decimal
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
    
    async def get_live_sports(self) -> List[Dict]:
        """Get all sports that have live matches"""
        try:
            # Use the VZip endpoint but headers will prevent compression
            url = f"{self.base_url}/service-api/LiveFeed/GetSportsShortZip"
            params = {
                'lng': 'en',
                'country': '19',
                'gr': '285'
            }
            
            logger.info(f"Fetching sports list from {url}")
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    try:
                        # Read raw bytes and decompress manually
                        raw_data = await resp.read()
                        data = self.decompress(raw_data)
                        
                        if data.get('Success'):
                            sports = data.get('Value', [])
                            logger.info(f"✓ Found {len(sports)} sports with live matches")
                            
                            # Filter sports that have visible/live matches (V > 0)
                            live_sports = [s for s in sports if s.get('V', 0) > 0]
                            logger.info(f"✓ {len(live_sports)} sports have active live matches")
                            return live_sports
                        else:
                            logger.error(f"API returned Success=False: {data.get('Error', 'Unknown error')}")
                    except Exception as json_err:
                        logger.error(f"JSON decode error: {json_err}")
                else:
                    logger.error(f"HTTP error: {resp.status}")
        except Exception as e:
            logger.error(f"Error getting live sports: {e}")
        
        return []
    
    async def get_matches_for_sport(self, sport_id: int, sport_name: str) -> List[Dict]:
        """Get all live matches for a specific sport"""
        try:
            # Use the exact endpoint format from working URL
            url = f"{self.base_url}/service-api/LiveFeed/Get1x2_VZip"
            params = {
                'sports': str(sport_id),
                'count': '40',
                'lng': 'en',
                'gr': '285',
                'cfview': '2',
                'mode': '4',
                'country': '19',
                'getEmpty': 'true',
                'virtualSports': 'true',
                'noFilterBlockEvent': 'true'
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    try:
                        # Read raw bytes and decompress manually
                        raw_data = await resp.read()
                        data = self.decompress(raw_data)
                        
                        if data.get('Success'):
                            matches = data.get('Value', [])
                            if matches:
                                logger.info(f"  ✓ {sport_name}: {len(matches)} matches")
                                return matches
                    except Exception as json_err:
                        logger.debug(f"JSON decode error for {sport_name}: {json_err}")
                else:
                    logger.debug(f"HTTP {resp.status} for {sport_name}")
        except Exception as e:
            logger.debug(f"Error getting matches for {sport_name}: {e}")
        
        return []
    
    async def get_all_matches_fallback(self) -> List[Dict]:
        """Fallback method: get matches with high count limit"""
        try:
            # Use the VZip endpoint with proper parameters
            url = f"{self.base_url}/service-api/LiveFeed/Get1x2_VZip"
            params = {
                'count': '100',
                'lng': 'en',
                'gr': '285',
                'cfview': '2',
                'mode': '4',
                'country': '19',
                'getEmpty': 'true',
                'virtualSports': 'true',
                'noFilterBlockEvent': 'true'
            }
            
            logger.info(f"Using fallback method with count=100")
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    try:
                        # Read raw bytes and decompress manually
                        raw_data = await resp.read()
                        data = self.decompress(raw_data)
                        
                        if data.get('Success'):
                            matches = data.get('Value', [])
                            logger.info(f"✓ Fallback method found {len(matches)} matches")
                            return matches
                    except Exception as json_err:
                        logger.error(f"JSON decode error in fallback: {json_err}")
                else:
                    logger.error(f"HTTP {resp.status} in fallback")
        except Exception as e:
            logger.error(f"Fallback method error: {e}")
        
        return []
    
    def parse_match(self, match_data: Dict, sport_id: int, sport_name: str) -> Dict:
        """Parse live match data with enhanced score extraction"""
        
        # Extract scores - different sports have different score structures
        score_data = match_data.get('SC', {}) or match_data.get('SS', {})
        
        # Initialize score variables
        score1 = 0
        score2 = 0
        detailed_score = {}
        
        # Extract main scores - try multiple fields
        if 'FS' in score_data:
            # FS = Full Score (main score)
            score1 = score_data['FS'].get('S1', 0)
            score2 = score_data['FS'].get('S2', 0)
        elif 'S1' in score_data and 'S2' in score_data:
            score1 = score_data.get('S1', 0)
            score2 = score_data.get('S2', 0)
        
        # Extract cricket-specific wickets data from the S array
        # Cricket scores are in format "runs/wickets" in Team1Scores/Team2Scores
        if 'S' in score_data and isinstance(score_data['S'], list):
            for score_item in score_data['S']:
                if isinstance(score_item, dict):
                    key = score_item.get('Key', '')
                    value = score_item.get('Value', '')
                    
                    if key == 'Team1Scores' and value:
                        # Parse "runs/wickets" format (e.g., "43/0")
                        if '/' in str(value):
                            try:
                                parts = str(value).split('/')
                                if len(parts) == 2:
                                    detailed_score['home_wickets'] = parts[1]
                            except:
                                pass
                    elif key == 'Team2Scores' and value:
                        if '/' in str(value):
                            try:
                                parts = str(value).split('/')
                                if len(parts) == 2:
                                    detailed_score['away_wickets'] = parts[1]
                            except:
                                pass
                    elif key == 'InnsStats':
                        # Extract innings statistics if needed
                        detailed_score['innings_stats'] = value
        
        # Extract period scores (PS) - for sports like basketball, tennis, etc.
        if 'PS' in score_data and isinstance(score_data['PS'], list):
            period_scores = []
            for period in score_data['PS']:
                if isinstance(period, dict) and 'Value' in period:
                    period_data = period['Value']
                    period_scores.append({
                        'period': period.get('Key', 0),
                        'period_name': period_data.get('NF', ''),
                        'score1': period_data.get('S1', 0),
                        'score2': period_data.get('S2', 0)
                    })
            if period_scores:
                detailed_score['periods'] = period_scores
        
        # Extract additional statistics (ST) - for detailed sport stats
        if 'ST' in score_data and isinstance(score_data['ST'], list):
            stats = []
            for stat_group in score_data['ST']:
                if isinstance(stat_group, dict) and 'Value' in stat_group:
                    for stat in stat_group['Value']:
                        if isinstance(stat, dict):
                            stats.append({
                                'stat_id': stat.get('ID'),
                                'name': stat.get('N', ''),
                                'value1': stat.get('S1', ''),
                                'value2': stat.get('S2', '')
                            })
            if stats:
                detailed_score['statistics'] = stats
        
        # Get time and period
        time_str = "LIVE"
        period = ""
        
        if 'CPS' in score_data:
            period = score_data.get('CPS', '')
        
        # Extract time remaining (TR) or time seconds (TS)
        if 'TS' in score_data:
            time_sec = score_data.get('TS', 0)
            if isinstance(time_sec, int) and time_sec > 0:
                mins = time_sec // 60
                secs = time_sec % 60
                time_str = f"{mins:02d}:{secs:02d}"
        elif 'TR' in score_data:
            time_remaining = score_data.get('TR', -1)
            if time_remaining >= 0:
                mins = time_remaining // 60
                secs = time_remaining % 60
                time_str = f"{mins:02d}:{secs:02d}"
        
        # Extract current period/phase
        if 'CPS' in score_data:
            period = score_data.get('CPS', '')
        
        # Extract current period number for better period display
        if 'CP' in score_data:
            current_period = score_data.get('CP', '')
            if current_period and not period:
                period = f"Period {current_period}"
        
        # Extract additional time info and status
        if 'SLS' in score_data:
            detailed_score['status_text'] = score_data['SLS']
        
        # Extract odds with American format
        raw_odds = {}
        for event in match_data.get('E', []):
            if 'C' in event:
                key = f"{event.get('G',0)}_{event.get('T',0)}"
                raw_odds[key] = {
                    'coefficient': event['C'],
                    'american_odds': event.get('CV', ''),  # CV contains American odds
                    'param': event.get('P')
                }
        
        # Convert to readable format
        odds = self._convert_odds_to_readable(raw_odds)
        
        # Build match dict
        match = {
            'match_id': match_data.get('I', 0),
            'sport_id': sport_id,
            'sport_name': sport_name,
            'league': match_data.get('L', ''),
            'team1': match_data.get('O1', ''),
            'team2': match_data.get('O2', ''),
            'score1': score1,
            'score2': score2,
            'time': time_str,
            'period': period,
            'start_time': match_data.get('S', 0),
            'odds': odds,
            'last_updated': int(time.time())
        }

        # Convert start_time from Unix timestamp to readable date/time format like bet365
        start_time_unix = match_data.get('S', 0)
        if isinstance(start_time_unix, (int, float)) and start_time_unix > 0:
            from datetime import datetime
            dt = datetime.fromtimestamp(start_time_unix)

            # Format date like bet365: "Thu Nov 06" - but use current year context
            match['date'] = dt.strftime("%a %b %d")

            # Format time like bet365: "9:10 PM" (12-hour format) with proper padding
            # Use cross-platform method to remove leading zero
            hour_str = dt.strftime("%I").lstrip('0') or '12'  # Handle midnight (00 -> 12)
            match['start_time_readable'] = f"{hour_str}:{dt.strftime('%M %p')}"

            # Keep original timestamp for compatibility
            match['start_time_unix'] = start_time_unix
        else:
            # Fallback values if no valid timestamp
            match['date'] = 'LIVE'
            match['start_time_readable'] = 'In Progress'
            match['start_time_unix'] = 0
        
        # Add detailed scores if available - always include it even if empty
        match['detailed_score'] = detailed_score if detailed_score else {}
        
        return match
    
    def save_data(self):
        """Save collected data to JSON and update statistics"""
        data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_matches': len(self.matches),
                'total_sports': self.stats['sports'],
                'collection_time': self.stats.get('time', 0)
            },
            'matches': list(self.matches.values())
        }

        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Data saved to {self.data_file}")

        # Update statistics file with live data
        self._update_statistics_file()

    def _update_statistics_file(self):
        """Update the statistics.json file with live match statistics"""
        stats_file = self.data_dir / "1xbet_statistics.json"

        # Load existing stats to preserve pregame data
        existing_stats = {}
        if stats_file.exists():
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    existing_stats = json.load(f)
            except:
                existing_stats = {}

        # Generate live statistics
        live_stats = self._generate_live_stats()

        # Preserve pregame stats if they exist
        pregame_stats = existing_stats.get('pregame', {})

        # Update the stats file
        stats_data = {
            "session_id": existing_stats.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S")),
            "timestamp": datetime.now().isoformat(),
            "pregame": pregame_stats,
            "live": live_stats,
            "total_matches": existing_stats.get("total_matches", 0),
            "total_sports": existing_stats.get("total_sports", 0),
            "total_leagues": existing_stats.get("total_leagues", 0),
            "new_matches": existing_stats.get("new_matches", 0),
            "updated_matches": existing_stats.get("updated_matches", 0),
            "collection_time_seconds": existing_stats.get("collection_time_seconds", 0)
        }

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Statistics updated in {stats_file}")

    def _generate_live_stats(self) -> dict:
        """Generate statistics for live matches"""
        try:
            total_matches = len(self.matches)
            sports_count = {}
            sports_names = {}

            for match in self.matches.values():
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
            logger.error(f"Error generating live stats: {e}")
            return {"total_matches": 0, "total_sports": 0, "sports": {}}
    
    def _save_removed_matches_to_history(self, removed_match_ids: set):
        """Save removed matches to unified history file"""
        if not removed_match_ids:
            return
        
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
        
        # Get removed matches from current matches dict
        removed_matches = []
        for match_id in removed_match_ids:
            if match_id in self.matches:
                match = self.matches[match_id].copy()
                match['removed_at'] = int(time.time())
                match['removed_at_readable'] = datetime.now().isoformat()
                match['status'] = 'completed'
                match['match_type'] = 'live'
                removed_matches.append(match)
        
        if removed_matches:
            # Add to live section of history
            history_data['live'].extend(removed_matches)
            
            # Update metadata
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
            
            logger.info(f"✓ Saved {len(removed_matches)} completed live matches to history")
    
    async def collect_all(self):
        """Collect all live matches from all sports"""
        start = time.time()
        logger.info("="*70)
        logger.info("Starting LIVE collection...")
        logger.info("="*70)
        
        self.stats = {'new': 0, 'updated': 0, 'total': 0, 'sports': 0, 'time': 0.0}
        
        # Step 1: Try to get all sports with live matches
        sports = await self.get_live_sports()
        
        all_matches = []
        sport_ids = set()
        
        if sports and len(sports) > 0:
            logger.info(f"Found {len(sports)} sports with live matches")
            logger.info("Collecting matches from each sport...")
            
            # Step 2: Get matches for each sport
            for sport in sports:
                sport_id = sport.get('I', 0)
                sport_name = sport.get('N', 'Unknown')
                visible_count = sport.get('V', 0)  # Number of visible/live matches
                
                if visible_count > 0:
                    # Fetch matches for this sport
                    matches = await self.get_matches_for_sport(sport_id, sport_name)
                    if matches:
                        all_matches.extend(matches)
                        sport_ids.add(sport_id)
        else:
            # Fallback: Use simple high-count query
            logger.info("Using fallback method to get all live matches...")
            all_matches = await self.get_all_matches_fallback()
        
        if not all_matches:
            logger.warning("No live matches found")
            return
        
        logger.info(f"\n✓ Total matches collected: {len(all_matches)}")
        
        # Step 3: Process all collected matches
        for match_data in all_matches:
            try:
                # Extract sport info from match data
                sport_id = match_data.get('SI', 0)  # Sport ID
                sport_name = match_data.get('SN', 'Unknown')  # Sport Name
                
                match = self.parse_match(match_data, sport_id, sport_name)
                match_id = match['match_id']
                
                sport_ids.add(sport_id)
                
                if match_id in self.matches:
                    # Check if updated
                    if match != self.matches[match_id]:
                        self.stats['updated'] += 1
                        self.matches[match_id] = match
                else:
                    self.stats['new'] += 1
                    self.matches[match_id] = match
                
                self.stats['total'] += 1
                
            except Exception as e:
                logger.error(f"Error parsing match: {e}")
        
        self.stats['sports'] = len(sport_ids)
        
        # Track removed matches and save to history
        current_match_ids = set(self.matches.keys())
        removed_match_ids = self.previous_match_ids - current_match_ids
        
        if removed_match_ids:
            self._save_removed_matches_to_history(removed_match_ids)
            logger.info(f"📋 Moved {len(removed_match_ids)} completed matches to history")
        
        # Update previous match IDs for next collection
        self.previous_match_ids = current_match_ids.copy()
        
        # Save data
        if self.matches:
            self.save_data()
        
        # Print summary
        duration = time.time() - start
        self.stats['time'] = duration
        
        logger.info("\n" + "="*70)
        logger.info("LIVE COLLECTION SUMMARY")
        logger.info("="*70)
        logger.info(f"Sports Found:        {self.stats['sports']}")
        logger.info(f"Live Matches Found:  {self.stats['total']}")
        logger.info(f"New Matches:         {self.stats['new']}")
        logger.info(f"Updated Matches:     {self.stats['updated']}")
        logger.info(f"Time:                {duration:.2f}s")
        logger.info("="*70)
    
    async def monitor(self, interval=1):
        """Monitor live matches continuously with realtime updates"""
        logger.info(f"\n🚀 Starting REALTIME LIVE monitoring (interval: {interval}s)")
        logger.info("Press Ctrl+C to stop\n")
        
        try:
            while True:
                await self.collect_all()
                
                if self.matches:
                    logger.info(f"\n📊 Currently tracking {len(self.matches)} live matches")
                    # Show sample
                    for i, match in enumerate(list(self.matches.values())[:5]):
                        logger.info(f"  {match['team1']} {match['score1']}-{match['score2']} {match['team2']} ({match['time']})")
                
                logger.info(f"\nNext update in {interval}s...\n")
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\nStopped by user")


async def main():
    """Main function with realtime monitoring support"""
    print("1XBET LIVE MATCHES COLLECTOR - REALTIME")
    print("="*45)
    print("Note: Live matches depend on actual games being played.")
    print("If no matches are found, it may be due to:")
    print("- No live matches currently happening")
    print("- API endpoint changes")
    print("- Regional restrictions")
    print()

    # Check command line arguments
    single_mode = len(sys.argv) > 1 and sys.argv[1] == "--single"

    collector = LiveCollector()
    await collector.init()

    try:
        if single_mode:
            # Single collection
            logger.info("Starting single live matches collection...")
            await collector.collect_all()

            if not collector.matches:
                logger.warning("No live matches found. This could be normal if no games are currently in progress.")
                logger.info("Try running again later or check 1xBet website for live matches.")
            else:
                logger.info(f"Successfully collected {len(collector.matches)} live matches!")
        else:
            # Start realtime monitoring (default)
            logger.info("🚀 Starting realtime monitoring mode (1s intervals)...")
            logger.info("Use --single flag for one-time collection only.")
            await collector.monitor(interval=1)

    except Exception as e:
        logger.error(f"Collection failed: {e}")
    finally:
        await collector.close()


if __name__ == "__main__":
    asyncio.run(main())