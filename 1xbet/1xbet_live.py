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


class LiveCollector:
    """1xbet live matches collector"""
    
    def __init__(self, base_url="https://1xlite-707953.top", data_dir: str = "."):
        self.base_url = base_url
        self.data_dir = Path(data_dir)
        # Don't create subdirectory - save in current directory
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {'new': 0, 'updated': 0, 'total': 0, 'sports': 0, 'time': 0.0}
        self.data_file = self.data_dir / "1xbet_live.json"
        self.history_file = self.data_dir / "1xbet_live_history.json"
        self.matches = {}  # Store matches by ID
        self.previous_match_ids = set()  # Track matches from previous collection
    
    async def init(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    def decompress(self, data: bytes) -> Dict:
        """Decompress VZip response with zstd support"""
        try:
            # Try zstd first (1xBet uses zstd compression)
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(data)
                return json.loads(decompressed.decode('utf-8'))
            except ImportError:
                logger.warning("zstandard not installed, trying zlib")
            except:
                pass
            
            # Fallback to zlib
            try:
                decompressed = zlib.decompress(data)
                return json.loads(decompressed.decode('utf-8'))
            except:
                pass
                
            # Try direct JSON
            return json.loads(data.decode('utf-8'))
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
            url = f"{self.base_url}/service-api/LiveFeed/GetSportsShortZip"
            params = {
                'lng': 'en',
                'country': '17'
            }
            
            logger.info(f"Fetching sports list from {url}")
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('Success'):
                        sports = data.get('Value', [])
                        logger.info(f"✓ Found {len(sports)} sports with live matches")
                        
                        # Filter sports that have visible/live matches (V > 0)
                        live_sports = [s for s in sports if s.get('V', 0) > 0]
                        logger.info(f"✓ {len(live_sports)} sports have active live matches")
                        return live_sports
                    else:
                        logger.error(f"API returned Success=False: {data.get('Error', 'Unknown error')}")
                else:
                    logger.error(f"HTTP error: {resp.status}")
        except Exception as e:
            logger.error(f"Error getting live sports: {e}")
        
        return []
    
    async def get_matches_for_sport(self, sport_id: int, sport_name: str) -> List[Dict]:
        """Get all live matches for a specific sport"""
        try:
            url = f"{self.base_url}/service-api/LiveFeed/Get1x2_VZip"
            params = {
                'sports': str(sport_id),
                'count': '500',  # High count to get all matches
                'lng': 'en',
                'cfview': '2',
                'mode': '4',
                'country': '17',
                'virtualSports': 'true',
                'OddsType': '2',  # American odds format
                'partner': '154'  # Additional parameter that might help
            }
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('Success'):
                        matches = data.get('Value', [])
                        if matches:
                            logger.info(f"  ✓ {sport_name}: {len(matches)} matches")
                            return matches
                elif resp.status == 406:
                    # Retry without OddsType if 406 error
                    params.pop('OddsType', None)
                    params.pop('partner', None)
                    async with self.session.get(url, params=params) as resp2:
                        if resp2.status == 200:
                            data = await resp2.json()
                            if data.get('Success'):
                                matches = data.get('Value', [])
                                if matches:
                                    logger.info(f"  ✓ {sport_name}: {len(matches)} matches")
                                    return matches
        except Exception as e:
            logger.debug(f"Error getting matches for {sport_name}: {e}")
        
        return []
    
    async def get_all_matches_fallback(self) -> List[Dict]:
        """Fallback method: get matches with high count limit"""
        try:
            url = f"{self.base_url}/service-api/LiveFeed/Get1x2_VZip"
            params = {
                'count': '500',  # Try to get up to 500 matches
                'lng': 'en',
                'cfview': '2',
                'mode': '4',
                'country': '17',
                'virtualSports': 'true',
                'OddsType': '2'  # American odds format
            }
            
            logger.info(f"Using fallback method with count=500")
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('Success'):
                        matches = data.get('Value', [])
                        logger.info(f"✓ Fallback method found {len(matches)} matches")
                        return matches
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
        
        # Extract additional time info
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

            # Format date like bet365: "Thu Nov 06"
            match['date'] = dt.strftime("%a %b %d")

            # Format time like bet365: "9:10 PM" (12-hour format)
            match['start_time_readable'] = dt.strftime("%I:%M %p")

            # Keep original timestamp for compatibility
            match['start_time_unix'] = start_time_unix
        
        # Add detailed scores if available
        if detailed_score:
            match['detailed_score'] = detailed_score
        
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
        """Save removed matches to history file"""
        if not removed_match_ids:
            return
        
        # Load existing history
        history_data = {'metadata': {}, 'matches': []}
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history_data = {'metadata': {}, 'matches': []}
        
        # Get removed matches from current matches dict
        removed_matches = []
        for match_id in removed_match_ids:
            if match_id in self.matches:
                match = self.matches[match_id].copy()
                match['removed_at'] = int(time.time())
                match['status'] = 'completed'
                removed_matches.append(match)
        
        if removed_matches:
            # Add to history
            history_data['matches'].extend(removed_matches)
            
            # Update metadata
            history_data['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'total_matches': len(history_data['matches']),
                'last_updated': int(time.time())
            }
            
            # Save history
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ Saved {len(removed_matches)} completed matches to history")
    
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