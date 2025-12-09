"""
Debug script to examine raw GetGameZip response structure
"""

import asyncio
import aiohttp
import gzip
import json


async def fetch_raw_event_data(event_id):
    """Fetch and display raw event data"""
    
    url = "https://1xbet.com/service-api/LineFeed/GetGameZip"
    params = {
        'id': str(event_id),
        'lng': 'en',
        'cfview': '2',
        'isSubGames': 'true'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                raw_data = await response.read()
                
                # Try to decompress
                try:
                    decompressed = gzip.decompress(raw_data)
                    data = json.loads(decompressed.decode('utf-8'))
                except:
                    data = json.loads(raw_data.decode('utf-8'))
                
                return data
            else:
                print(f"HTTP {response.status}")
                return None


async def main():
    # Use the first futures event ID from our data
    event_id = 676418798  # Spain Copa del Rey Winner
    
    print(f"Fetching raw data for event {event_id}...")
    print("=" * 70)
    
    data = await fetch_raw_event_data(event_id)
    
    if data:
        # Save to file for inspection
        with open('debug_raw_future_event.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print("✅ Raw data saved to: debug_raw_future_event.json")
        print()
        
        # Show structure
        if data.get('Success'):
            value = data.get('Value', {})
            game = value.get('Game', {})
            
            print("Available keys in response:")
            print(f"  Value keys: {list(value.keys())}")
            print(f"  Game keys: {list(game.keys())}")
            
            # Check for participant/team data
            if 'O' in game:
                print(f"\n  Game['O'] (participants): {len(game['O'])} items")
                if game['O']:
                    print(f"  Sample participant: {json.dumps(game['O'][0], indent=4)}")
            
            # Check odds data
            if 'E' in game:
                print(f"\n  Game['E'] (odds): {len(game['E'])} items")
                if game['E']:
                    print(f"  Sample odd: {json.dumps(game['E'][0], indent=4)}")
            
            # Check subgames
            if 'SG' in value:
                print(f"\n  Subgames: {len(value['SG'])} items")
                if value['SG']:
                    sg = value['SG'][0]
                    print(f"  Subgame keys: {list(sg.keys())}")
                    if 'O' in sg:
                        print(f"  Subgame['O']: {len(sg['O'])} items")
                        if sg['O']:
                            print(f"  Sample subgame participant: {json.dumps(sg['O'][0], indent=4)}")
        else:
            print(f"❌ API returned Success=False: {data.get('Error')}")
    else:
        print("❌ Failed to fetch data")


if __name__ == "__main__":
    asyncio.run(main())
