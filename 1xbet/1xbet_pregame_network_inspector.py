"""
1XBET PREGAME API NETWORK INSPECTOR
====================================
Tests pregame endpoints to find correct parameters
"""

import asyncio
import aiohttp
import json
import zstandard as zstd
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PregameNetworkInspector:
    """Inspect 1xbet pregame API endpoints"""
    
    def __init__(self, base_url="https://1xbet.com"):
        self.base_url = base_url
        self.session = None
    
    async def init(self):
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
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    def decompress(self, data: bytes):
        """Decompress zstd data"""
        try:
            dctx = zstd.ZstdDecompressor()
            dobj = dctx.decompressobj()
            decompressed = dobj.decompress(data)
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return None
    
    async def test_endpoint(self, endpoint_name: str, url: str, params: dict):
        """Test a specific endpoint with parameters"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing: {endpoint_name}")
        logger.info(f"URL: {url}")
        logger.info(f"Params: {json.dumps(params, indent=2)}")
        logger.info(f"{'='*70}")
        
        try:
            async with self.session.get(url, params=params) as response:
                logger.info(f"Status: {response.status}")
                logger.info(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    raw_data = await response.read()
                    logger.info(f"Raw data length: {len(raw_data)} bytes")
                    logger.info(f"First 50 bytes: {raw_data[:50]}")
                    
                    data = self.decompress(raw_data)
                    if data:
                        logger.info(f"✓ Successfully decompressed")
                        logger.info(f"Success: {data.get('Success')}")
                        
                        if data.get('Value'):
                            matches = data['Value']
                            logger.info(f"✓✓✓ FOUND {len(matches)} MATCHES! ✓✓✓")
                            
                            if matches:
                                # Show first match details
                                first = matches[0]
                                logger.info(f"\nFirst match sample:")
                                logger.info(f"  League: {first.get('L', 'N/A')}")
                                logger.info(f"  Team1: {first.get('O1', 'N/A')}")
                                logger.info(f"  Team2: {first.get('O2', 'N/A')}")
                                logger.info(f"  Start time: {first.get('S', 'N/A')}")
                                
                                return True, len(matches), params
                        else:
                            logger.warning("Value is empty")
                            return False, 0, params
                    else:
                        logger.error("Failed to decompress")
                else:
                    logger.warning(f"HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error: {e}")
        
        return False, 0, params
    
    async def find_working_params(self):
        """Test various parameter combinations to find what works"""
        
        # First get a sport that has pregame matches
        logger.info("\n" + "="*70)
        logger.info("Step 1: Getting sports list")
        logger.info("="*70)
        
        sports_url = f"{self.base_url}/service-api/LineFeed/GetSportsShortZip"
        sports_params = {'lng': 'en', 'country': '19', 'gr': '285'}
        
        try:
            async with self.session.get(sports_url, params=sports_params) as response:
                if response.status == 200:
                    raw_data = await response.read()
                    sports_data = self.decompress(raw_data)
                    
                    if sports_data and sports_data.get('Success'):
                        sports = sports_data['Value']
                        logger.info(f"✓ Found {len(sports)} sports")
                        
                        # Get sports with pregame matches (C > 0 or CC > 0)
                        pregame_sports = [s for s in sports if s.get('C', 0) > 0 or s.get('CC', 0) > 0]
                        logger.info(f"✓ {len(pregame_sports)} sports have pregame matches")
                        
                        # Show top 10 sports with most matches
                        pregame_sports.sort(key=lambda x: x.get('C', 0) + x.get('CC', 0), reverse=True)
                        logger.info("\nTop sports with pregame matches:")
                        for sport in pregame_sports[:10]:
                            logger.info(f"  Sport {sport.get('I')}: {sport.get('N')} - {sport.get('C', 0)} matches")
                        
                        # Test with the sport that has most matches
                        if pregame_sports:
                            test_sport = pregame_sports[0]
                            sport_id = test_sport['I']
                            sport_name = test_sport['N']
                            match_count = test_sport.get('C', 0)
                            
                            logger.info(f"\nStep 2: Testing sport {sport_id} ({sport_name}) with {match_count} matches")
                            logger.info("="*70)
                            
                            # Test various parameter combinations
                            base_url = f"{self.base_url}/service-api/LineFeed/Get1x2_VZip"
                            
                            param_combinations = [
                                {
                                    "name": "Minimal params",
                                    "params": {
                                        'sports': str(sport_id),
                                        'lng': 'en'
                                    }
                                },
                                {
                                    "name": "With count",
                                    "params": {
                                        'sports': str(sport_id),
                                        'count': '50',
                                        'lng': 'en'
                                    }
                                },
                                {
                                    "name": "With country and gr",
                                    "params": {
                                        'sports': str(sport_id),
                                        'count': '50',
                                        'lng': 'en',
                                        'country': '19',
                                        'gr': '285'
                                    }
                                },
                                {
                                    "name": "With cfview and mode",
                                    "params": {
                                        'sports': str(sport_id),
                                        'count': '50',
                                        'lng': 'en',
                                        'cfview': '2',
                                        'mode': '4'
                                    }
                                },
                                {
                                    "name": "Full params (all combined)",
                                    "params": {
                                        'sports': str(sport_id),
                                        'count': '50',
                                        'lng': 'en',
                                        'country': '19',
                                        'gr': '285',
                                        'cfview': '2',
                                        'mode': '4'
                                    }
                                },
                                {
                                    "name": "With getEmpty and noFilterBlockEvent",
                                    "params": {
                                        'sports': str(sport_id),
                                        'count': '50',
                                        'lng': 'en',
                                        'getEmpty': 'true',
                                        'noFilterBlockEvent': 'true'
                                    }
                                }
                            ]
                            
                            working_params = []
                            
                            for combo in param_combinations:
                                success, count, params = await self.test_endpoint(
                                    combo['name'],
                                    base_url,
                                    combo['params']
                                )
                                
                                if success and count > 0:
                                    working_params.append({
                                        'name': combo['name'],
                                        'params': params,
                                        'match_count': count
                                    })
                                
                                await asyncio.sleep(0.5)  # Rate limiting
                            
                            # Summary
                            logger.info("\n" + "="*70)
                            logger.info("SUMMARY OF WORKING PARAMETERS")
                            logger.info("="*70)
                            
                            if working_params:
                                logger.info(f"\n✓✓✓ Found {len(working_params)} working parameter combinations! ✓✓✓\n")
                                for wp in working_params:
                                    logger.info(f"✓ {wp['name']}: {wp['match_count']} matches")
                                    logger.info(f"  Params: {json.dumps(wp['params'], indent=4)}")
                                    logger.info("")
                            else:
                                logger.error("\n✗ No working parameter combinations found")
                                logger.error("This could mean:")
                                logger.error("  - API requires authentication")
                                logger.error("  - Different endpoint needed")
                                logger.error("  - Regional restrictions")
                        
        except Exception as e:
            logger.error(f"Error in find_working_params: {e}")


async def main():
    inspector = PregameNetworkInspector()
    await inspector.init()
    
    try:
        await inspector.find_working_params()
    finally:
        await inspector.close()


if __name__ == "__main__":
    print("\n1XBET PREGAME NETWORK INSPECTOR")
    print("="*70)
    print("Testing various API endpoints and parameters...")
    print("="*70 + "\n")
    
    asyncio.run(main())
