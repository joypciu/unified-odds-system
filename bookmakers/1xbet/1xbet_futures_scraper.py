"""
1xBet Futures/Outrights Scraper
Fetches long-term betting markets with proper odds structure
"""

import asyncio
import aiohttp
import json
import gzip
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class OutrightSelection:
    """Single selection in an outright market"""
    selection_id: int
    selection_name: str
    coefficient: float
    american_odds: str
    param: Optional[int] = None


@dataclass
class FutureEvent:
    """Future/Outright betting event with multiple selections"""
    event_id: int
    sport_id: int
    sport_name: str
    league_id: int
    league_name: str
    event_name: str
    country: str
    country_id: int
    start_time: int
    market_type: str  # "Winner", "Top Scorer", etc.
    selections: List[Dict]  # List of OutrightSelection dicts
    total_selections: int
    last_updated: int
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'event_id': self.event_id,
            'sport_id': self.sport_id,
            'sport_name': self.sport_name,
            'league_id': self.league_id,
            'league_name': self.league_name,
            'event_name': self.event_name,
            'country': self.country,
            'country_id': self.country_id,
            'start_time': self.start_time,
            'start_time_readable': datetime.fromtimestamp(self.start_time).isoformat(),
            'market_type': self.market_type,
            'selections': self.selections,
            'total_selections': self.total_selections,
            'last_updated': self.last_updated
        }


class FuturesScraper:
    """Scraper for 1xBet futures/outright markets"""
    
    def __init__(self, base_url: str = "https://1xbet.com"):
        self.base_url = base_url
        self.data_dir = Path(__file__).parent
        self.futures_file = self.data_dir / "1xbet_future.json"
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
    async def init_session(self):
        """Initialize aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Origin': 'https://1xbet.com',
            'Referer': 'https://1xbet.com/'
        }
        connector = aiohttp.TCPConnector()
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=connector
        )
        
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            
    def decompress_response(self, data: bytes) -> Dict:
        """Decompress gzipped response"""
        try:
            decompressed = gzip.decompress(data)
            return json.loads(decompressed.decode('utf-8'))
        except gzip.BadGzipFile:
            try:
                return json.loads(data.decode('utf-8'))
            except:
                return {}
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return {}
    
    async def fetch_sport_futures(self, sport_id: int = 2999) -> List[Dict]:
        """
        Fetch all futures events for sport_id 2999 (Long-term bets)
        This gets the list of future events
        """
        async with self.semaphore:
            url = f"{self.base_url}/service-api/LineFeed/Get1x2_VZip"
            params = {
                'sports': str(sport_id),
                'count': '500',
                'lng': 'en',
                'cfview': '2',
                'mode': '4'
            }
            
            try:
                logger.info(f"Fetching futures list for sport_id {sport_id}...")
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        raw_data = await response.read()
                        data = self.decompress_response(raw_data)
                        
                        if data.get('Success') and data.get('Value'):
                            events = data['Value']
                            logger.info(f"✓ Found {len(events)} futures events")
                            return events
                        else:
                            logger.warning(f"API returned Success=False")
                    else:
                        logger.warning(f"HTTP {response.status}")
            except Exception as e:
                logger.error(f"Error fetching futures list: {e}")
            
            return []
    
    async def fetch_event_line(self, event_id: int) -> Optional[Dict]:
        """
        Fetch detailed line/markets for a specific event
        This includes all betting markets with selections and odds
        """
        async with self.semaphore:
            url = f"{self.base_url}/service-api/LineFeed/GetGameZip"
            params = {
                'id': str(event_id),
                'lng': 'en',
                'cfview': '2',
                'isSubGames': 'true'
            }
            
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        raw_data = await response.read()
                        data = self.decompress_response(raw_data)
                        
                        if data.get('Success') and data.get('Value'):
                            return data['Value']
                        else:
                            logger.debug(f"Event {event_id}: No line data")
                    else:
                        logger.debug(f"Event {event_id}: HTTP {response.status}")
            except Exception as e:
                logger.debug(f"Event {event_id}: Error - {e}")
            
            return None
    
    def parse_future_event(self, event_data: Dict, line_data: Optional[Dict]) -> Optional[FutureEvent]:
        """
        Parse futures event with selections and odds
        
        Args:
            event_data: Basic event info from Get1x2_VZip
            line_data: Detailed line from GetGameZip (contains PL field with names)
        """
        try:
            event_id = event_data.get('I', 0)
            sport_id = event_data.get('SI', 2999)
            
            # Extract basic info
            event_name = event_data.get('O1', '') or event_data.get('L', '')
            league_name = event_data.get('L', '')
            league_id = event_data.get('LI', 0)
            
            # Parse selections from line data
            selections = []
            
            if line_data:
                # GetGameZip response is flat, not nested in 'Game'
                # The line_data IS the game data
                value = line_data
                
                # Parse odds which contain PL (Player/Team) with name
                if 'E' in value and value['E']:
                    for odd_item in value['E']:
                        # Extract team/player info from PL field
                        player_info = odd_item.get('PL', {})
                        selection_name = player_info.get('N', f"Selection {odd_item.get('T', 0)}")
                        player_id = player_info.get('I', 0)
                        
                        selection = {
                            'selection_id': odd_item.get('I', 0),
                            'selection_name': selection_name,
                            'player_id': player_id,
                            'coefficient': odd_item.get('C', 0),
                            'american_odds': odd_item.get('CV', ''),
                            'param': odd_item.get('P'),
                            'group_id': odd_item.get('G', 0),
                            'type': odd_item.get('T', 0)
                        }
                        selections.append(selection)
            
            # If no selections found from line data, try basic odds from event_data
            if not selections and 'E' in event_data and event_data['E']:
                for odd_item in event_data['E']:
                    player_info = odd_item.get('PL', {})
                    selection_name = player_info.get('N', f"Selection {odd_item.get('T', 0)}")
                    
                    selection = {
                        'selection_id': odd_item.get('I', 0),
                        'selection_name': selection_name,
                        'player_id': player_info.get('I', 0),
                        'coefficient': odd_item.get('C', 0),
                        'american_odds': odd_item.get('CV', ''),
                        'param': odd_item.get('P'),
                        'group_id': odd_item.get('G', 0),
                        'type': odd_item.get('T', 0)
                    }
                    selections.append(selection)
            
            # Determine market type from event name
            market_type = "Winner"
            if "winner" in event_name.lower():
                market_type = "Winner"
            elif "top scorer" in event_name.lower():
                market_type = "Top Scorer"
            elif "champion" in event_name.lower():
                market_type = "Champion"
            
            return FutureEvent(
                event_id=event_id,
                sport_id=sport_id,
                sport_name=event_data.get('SN', 'Long-term bets'),
                league_id=league_id,
                league_name=league_name,
                event_name=event_name,
                country=event_data.get('CN', ''),
                country_id=event_data.get('COI', 0),
                start_time=event_data.get('S', 0),
                market_type=market_type,
                selections=selections,
                total_selections=len(selections),
                last_updated=int(time.time())
            )
            
        except Exception as e:
            logger.error(f"Error parsing future event {event_data.get('I', 0)}: {e}")
            return None
    
    async def collect_futures(self) -> List[FutureEvent]:
        """
        Main collection method:
        1. Fetch list of futures events
        2. For each event, fetch detailed line with odds
        3. Parse and return structured data
        """
        futures_list = await self.fetch_sport_futures(sport_id=2999)
        
        if not futures_list:
            logger.warning("No futures events found")
            return []
        
        logger.info(f"Processing {len(futures_list)} futures events...")
        
        futures_data = []
        tasks = []
        
        # Create tasks to fetch line data for each event
        for event in futures_list:
            event_id = event.get('I', 0)
            if event_id:
                tasks.append(self.fetch_event_line(event_id))
        
        # Fetch all line data concurrently
        logger.info(f"Fetching detailed odds for {len(tasks)} events...")
        line_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Parse each event with its line data
        events_with_odds = 0
        for event, line_data in zip(futures_list, line_results):
            if isinstance(line_data, Exception):
                line_data = None
                
            future_event = self.parse_future_event(event, line_data)
            
            if future_event:
                futures_data.append(future_event)
                if future_event.selections:
                    events_with_odds += 1
        
        logger.info(f"✓ Collected {len(futures_data)} futures events")
        logger.info(f"✓ {events_with_odds} events have odds/selections")
        
        return futures_data
    
    def save_futures(self, futures: List[FutureEvent]):
        """Save futures data to JSON file"""
        data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_events': len(futures),
                'events_with_odds': sum(1 for f in futures if f.selections),
                'data_type': 'futures_with_odds',
                'source': '1xbet',
                'description': 'Long-term bets and outright markets with selections'
            },
            'data': {
                'events': [f.to_dict() for f in futures]
            }
        }
        
        with open(self.futures_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved to {self.futures_file}")
    
    async def run(self):
        """Main execution method"""
        try:
            await self.init_session()
            
            logger.info("=" * 60)
            logger.info("1xBet Futures Scraper - Starting Collection")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Collect futures with odds
            futures = await self.collect_futures()
            
            # Save to file
            if futures:
                self.save_futures(futures)
            else:
                logger.warning("No futures data collected")
            
            elapsed = time.time() - start_time
            
            logger.info("=" * 60)
            logger.info(f"Collection completed in {elapsed:.2f}s")
            logger.info("=" * 60)
            
            # Print summary
            if futures:
                with_odds = sum(1 for f in futures if f.selections)
                total_selections = sum(f.total_selections for f in futures)
                
                print(f"\n📊 SUMMARY:")
                print(f"   Total futures events: {len(futures)}")
                print(f"   Events with odds: {with_odds}")
                print(f"   Events without odds: {len(futures) - with_odds}")
                print(f"   Total selections: {total_selections}")
                
                if with_odds > 0:
                    print(f"\n✅ Sample event with odds:")
                    sample = next((f for f in futures if f.selections), None)
                    if sample:
                        print(f"   Event: {sample.event_name}")
                        print(f"   League: {sample.league_name}")
                        print(f"   Selections: {sample.total_selections}")
                        if sample.selections:
                            print(f"   Sample selection: {sample.selections[0]['selection_name']} - {sample.selections[0]['american_odds']}")
            
        finally:
            await self.close_session()


async def main():
    """Entry point"""
    scraper = FuturesScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
