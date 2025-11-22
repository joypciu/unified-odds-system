"""
1XBET LIVE API NETWORK INSPECTOR
=================================
Tests all possible live endpoints and shows what data we get
"""

import asyncio
import aiohttp
import json
import zlib
import zstandard as zstd
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NetworkInspector:
    """Inspect 1xbet live API endpoints"""
    
    def __init__(self, base_url="https://1xlite-707953.top"):
        self.base_url = base_url
        self.session = None
        self.results = []
    
    async def init(self):
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    def decompress(self, data: bytes) -> Any:
        """Try to decompress VZip data using multiple methods"""
        # Try zstd decompression first (1xBet uses zstd)
        try:
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(data)
            try:
                return json.loads(decompressed)
            except:
                return decompressed.decode('utf-8', errors='ignore')
        except:
            pass
        
        # Try zlib decompression
        try:
            decompressed = zlib.decompress(data)
            try:
                return json.loads(decompressed)
            except:
                return decompressed.decode('utf-8', errors='ignore')
        except:
            pass
        
        # Try direct JSON
        try:
            return json.loads(data)
        except:
            pass
        
        # Return as text
        try:
            return data.decode('utf-8', errors='ignore')
        except:
            return data
    
    async def test_endpoint(self, endpoint: str, params: Optional[Dict[str, Any]] = None, method: str = "GET"):
        """Test a single endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        logger.info("\n" + "="*70)
        logger.info(f"Testing: {method} {endpoint}")
        logger.info(f"Full URL: {url}")
        if params:
            logger.info(f"Params: {params}")
        logger.info("="*70)
        
        result = {
            'endpoint': endpoint,
            'url': url,
            'params': params,
            'method': method,
            'timestamp': datetime.now().isoformat(),
            'status': None,
            'headers': {},
            'data_type': None,
            'data_size': 0,
            'success': False,
            'error': None,
            'sample_data': None
        }
        
        try:
            if method == "GET":
                async with self.session.get(url, params=params) as resp:
                    result['status'] = resp.status
                    result['headers'] = dict(resp.headers)
                    
                    logger.info(f"Status: {resp.status}")
                    logger.info(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
                    logger.info(f"Content-Length: {resp.headers.get('Content-Length', 'unknown')}")
                    
                    content = await resp.read()
                    result['data_size'] = len(content)
                    
                    # Try to parse the response
                    data = self.decompress(content)
                    result['data_type'] = type(data).__name__
                    
                    if isinstance(data, dict):
                        result['success'] = True
                        # Save structure
                        result['sample_data'] = {
                            'keys': list(data.keys()),
                            'success': data.get('Success'),
                            'error': data.get('Error'),
                            'error_code': data.get('ErrorCode'),
                            'value_type': type(data.get('Value')).__name__ if 'Value' in data else None,
                            'value_length': len(data.get('Value', [])) if isinstance(data.get('Value'), (list, dict)) else None
                        }
                        
                        # Log the structure
                        logger.info(f"✓ Parsed as JSON")
                        logger.info(f"Keys: {result['sample_data']['keys']}")
                        logger.info(f"Success: {data.get('Success')}")
                        logger.info(f"Error: {data.get('Error')}")
                        
                        if data.get('Value'):
                            value = data['Value']
                            logger.info(f"Value type: {type(value).__name__}")
                            logger.info(f"Value length: {len(value) if isinstance(value, (list, dict)) else 'N/A'}")
                            
                            # Show sample of first item
                            if isinstance(value, list) and len(value) > 0:
                                first_item = value[0]
                                logger.info(f"\nFirst item keys: {list(first_item.keys()) if isinstance(first_item, dict) else 'Not a dict'}")
                                logger.info(f"First item sample: {json.dumps(first_item, indent=2)[:500]}")
                                
                                result['sample_data']['first_item'] = first_item
                            elif isinstance(value, dict):
                                logger.info(f"Value is dict with keys: {list(value.keys())[:10]}")
                                result['sample_data']['value_sample'] = str(value)[:500]
                        
                        # Save full response for successful requests
                        if data.get('Success') and data.get('Value'):
                            filename = f"response_{endpoint.replace('/', '_')}_{datetime.now().strftime('%H%M%S')}.json"
                            with open(filename, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            logger.info(f"✓ Full response saved to: {filename}")
                            result['saved_file'] = filename
                    
                    elif isinstance(data, str):
                        logger.info(f"Response as text (first 500 chars):\n{data[:500]}")
                        result['sample_data'] = data[:500]
                    
                    else:
                        logger.info(f"Data type: {type(data)}")
                        logger.info(f"Data size: {len(content)} bytes")
            
            elif method == "POST":
                async with self.session.post(url, json=params) as resp:
                    result['status'] = resp.status
                    result['headers'] = dict(resp.headers)
                    
                    content = await resp.read()
                    data = self.decompress(content)
                    result['data_type'] = type(data).__name__
                    result['data_size'] = len(content)
                    
                    if isinstance(data, dict):
                        result['success'] = True
                        result['sample_data'] = data
        
        except Exception as e:
            logger.error(f"✗ Error: {e}")
            result['error'] = str(e)
        
        self.results.append(result)
        return result
    
    async def test_all_live_endpoints(self):
        """Test all possible live endpoints"""
        
        logger.info("\n" + "="*70)
        logger.info("1XBET LIVE API NETWORK INSPECTOR")
        logger.info("="*70)
        
        # List of endpoints to test
        endpoints = [
            # Working live endpoints from live.txt
            {
                'endpoint': '/service-api/LiveFeed/Get1x2_VZip',
                'params': {
                    'count': '40',
                    'lng': 'en',
                    'gr': '1741',
                    'cfview': '2',
                    'mode': '4',
                    'country': '17',
                    'ZVE': '1',
                    'virtualSports': 'true',
                    'noFilterBlockEvent': 'true'
                }
            },
            {
                'endpoint': '/service-api/LiveFeed/Get1x2_VZip',
                'params': {
                    'count': '10',
                    'lng': 'en',
                    'cfview': '2',
                    'mode': '4',
                    'country': '17',
                    'top': 'true',
                    'virtualSports': 'true',
                    'noFilterBlockEvent': 'true'
                }
            },
            
            # Live Feed endpoints
            {
                'endpoint': '/service-api/LiveFeed/Get1x2_VZip',
                'params': {'lng': 'en', 'country': '17'}
            },
            {
                'endpoint': '/LiveFeed/Get1x2_VZip',
                'params': {'lng': 'en', 'country': '17', 'mode': '4'}
            },
            {
                'endpoint': '/service-api/LiveFeed/GetSportsShortZip',
                'params': {'lng': 'en', 'country': '17'}
            },
            {
                'endpoint': '/service-api/live/GetSportsShortZip',
                'params': {'lng': 'en', 'country': '17'}
            },
            
            # Try with sports parameter
            {
                'endpoint': '/service-api/LiveFeed/Get1x2_VZip',
                'params': {'sports': '1', 'lng': 'en', 'country': '17'}
            },
            {
                'endpoint': '/service-api/LiveFeed/Get1x2_VZip',
                'params': {'sports': '1,2,3,4', 'lng': 'en', 'country': '17'}
            },
            
            # Line feed with live flag
            {
                'endpoint': '/service-api/LineFeed/Get1x2_VZip',
                'params': {'sports': '1', 'lng': 'en', 'country': '17', 'live': '1'}
            },
            {
                'endpoint': '/service-api/LineFeed/Get1x2_VZip',
                'params': {'lng': 'en', 'country': '17', 'live': 'true'}
            },
            
            # Top live games
            {
                'endpoint': '/service-api/LiveFeed/GetTopGames',
                'params': {'lng': 'en', 'country': '17'}
            },
            {
                'endpoint': '/service-api/LiveFeed/GetTopGamesZip',
                'params': {'lng': 'en', 'country': '17'}
            },
            
            # Express/Featured
            {
                'endpoint': '/service-api/LiveFeed/expressDay',
                'params': {'lng': 'en', 'country': '17'}
            },
            
            # Alternative formats
            {
                'endpoint': '/service-api/live-feed/get-1x2',
                'params': {'lng': 'en', 'country': '17'}
            },
            {
                'endpoint': '/live/Get1x2_VZip',
                'params': {'lng': 'en', 'country': '17'}
            },
            
            # Sports list to check for live indicators
            {
                'endpoint': '/service-api/LineFeed/GetSportsShortZip',
                'params': {'lng': 'en', 'country': '17', 'virtualSports': 'false'}
            },
        ]
        
        logger.info(f"\nTesting {len(endpoints)} endpoints...\n")
        
        for i, test in enumerate(endpoints, 1):
            logger.info(f"\n[{i}/{len(endpoints)}]")
            await self.test_endpoint(test['endpoint'], test['params'])
            await asyncio.sleep(0.5)  # Small delay between requests
        
        # Generate summary report
        self.generate_report()
    
    def generate_report(self):
        """Generate summary report"""
        logger.info("\n\n" + "="*70)
        logger.info("SUMMARY REPORT")
        logger.info("="*70)
        
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        logger.info(f"\nTotal Endpoints Tested: {len(self.results)}")
        logger.info(f"Successful: {len(successful)}")
        logger.info(f"Failed: {len(failed)}")
        
        if successful:
            logger.info("\n✓ SUCCESSFUL ENDPOINTS:")
            for r in successful:
                logger.info(f"\n  {r['endpoint']}")
                logger.info(f"    Status: {r['status']}")
                logger.info(f"    Data size: {r['data_size']} bytes")
                if r['sample_data']:
                    logger.info(f"    Has Value: {r['sample_data'].get('value_length', 0)} items")
                if r.get('saved_file'):
                    logger.info(f"    Saved to: {r['saved_file']}")
        
        if failed:
            logger.info("\n✗ FAILED ENDPOINTS:")
            for r in failed:
                logger.info(f"\n  {r['endpoint']}")
                logger.info(f"    Status: {r['status']}")
                logger.info(f"    Error: {r['error']}")
        
        # Save full report
        report_file = f"network_inspection_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'base_url': self.base_url,
                'total_tests': len(self.results),
                'successful': len(successful),
                'failed': len(failed),
                'results': self.results
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✓ Full report saved to: {report_file}")
        logger.info("="*70)


async def test_specific_sport_live(sport_id: int = 1):
    """Test getting live data for a specific sport"""
    logger.info("\n" + "="*70)
    logger.info(f"Testing LIVE data for Sport ID: {sport_id}")
    logger.info("="*70)
    
    inspector = NetworkInspector()
    await inspector.init()
    
    try:
        # Test multiple endpoints for football live
        endpoints = [
            f'/service-api/LiveFeed/Get1x2_VZip?sports={sport_id}&lng=en&country=17',
            f'/service-api/LineFeed/Get1x2_VZip?sports={sport_id}&lng=en&country=17&live=1',
            f'/LiveFeed/Get1x2_VZip?sports={sport_id}&lng=en',
        ]
        
        for endpoint in endpoints:
            await inspector.test_endpoint(endpoint, None)
            await asyncio.sleep(1)
    
    finally:
        await inspector.close()


async def main():
    """Main function"""
    inspector = NetworkInspector()
    await inspector.init()
    
    try:
        # Test all endpoints
        await inspector.test_all_live_endpoints()
        
        # Also test specific sports
        logger.info("\n\nTesting specific sports for live matches...")
        await test_specific_sport_live(sport_id=1)  # Football
        
    finally:
        await inspector.close()


if __name__ == "__main__":
    asyncio.run(main())