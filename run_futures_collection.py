"""
Standalone script to collect 1xbet futures with odds
Can be run independently or scheduled as a cron job
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Import futures scraper module
sys.path.insert(0, str(Path(__file__).parent))

import importlib.util
spec = importlib.util.spec_from_file_location("futures_scraper", Path(__file__).parent / "1xbet" / "1xbet_futures_scraper.py")
futures_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(futures_module)
FuturesScraper = futures_module.FuturesScraper


async def collect_futures():
    """Collect futures and provide detailed report"""
    
    print("\n" + "=" * 70)
    print("1xBet Futures Collection")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")
    
    scraper = FuturesScraper()
    
    try:
        await scraper.init_session()
        futures = await scraper.collect_futures()
        
        if futures:
            scraper.save_futures(futures)
            
            # Generate detailed report
            with_odds = [f for f in futures if f.selections]
            without_odds = [f for f in futures if not f.selections]
            total_selections = sum(f.total_selections for f in futures)
            
            print("\n" + "=" * 70)
            print("COLLECTION REPORT")
            print("=" * 70)
            print(f"\n📊 Statistics:")
            print(f"   Total futures events: {len(futures)}")
            print(f"   ✅ Events with odds: {len(with_odds)} ({len(with_odds)/len(futures)*100:.1f}%)")
            print(f"   ❌ Events without odds: {len(without_odds)} ({len(without_odds)/len(futures)*100:.1f}%)")
            print(f"   📈 Total selections: {total_selections}")
            
            if with_odds:
                avg_selections = total_selections / len(with_odds)
                print(f"   📊 Avg selections per event: {avg_selections:.1f}")
            
            # Group by league
            leagues = {}
            for f in with_odds:
                league = f.league_name
                if league not in leagues:
                    leagues[league] = []
                leagues[league].append(f)
            
            if leagues:
                print(f"\n🏆 Leagues with futures ({len(leagues)}):")
                for league, events in sorted(leagues.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                    print(f"   • {league}: {len(events)} events")
            
            # Show sample events
            if with_odds:
                print(f"\n✨ Sample Events with Odds:")
                for i, future in enumerate(with_odds[:3], 1):
                    print(f"\n   {i}. {future.event_name}")
                    print(f"      League: {future.league_name}")
                    print(f"      Selections: {future.total_selections}")
                    if future.selections:
                        top_3 = future.selections[:3]
                        for j, sel in enumerate(top_3, 1):
                            print(f"         {j}. {sel['selection_name']} - {sel['american_odds']}")
                        if future.total_selections > 3:
                            print(f"         ... and {future.total_selections - 3} more selections")
            
            print("\n" + "=" * 70)
            print(f"✅ Data saved to: 1xbet/1xbet_future.json")
            print("=" * 70)
            
            return True
        else:
            print("\n❌ No futures data collected")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during collection: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await scraper.close_session()


def check_existing_data():
    """Check if futures data already exists and show info"""
    futures_file = Path("1xbet/1xbet_futures_with_odds.json")
    
    if futures_file.exists():
        try:
            with open(futures_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            print("\n📁 Existing futures data found:")
            print(f"   Last updated: {metadata.get('timestamp', 'Unknown')}")
            print(f"   Total events: {metadata.get('total_events', 0)}")
            print(f"   Events with odds: {metadata.get('events_with_odds', 0)}")
            print(f"\n   File: {futures_file}")
            
            return True
        except:
            pass
    
    return False


async def main():
    """Main entry point"""
    
    # Check existing data
    has_existing = check_existing_data()
    
    if has_existing:
        print("\n" + "⚠" * 35)
        response = input("\n   Collect fresh futures data? (y/n): ").strip().lower()
        print()
        
        if response != 'y':
            print("   Cancelled. Using existing data.")
            return
    
    # Collect futures
    success = await collect_futures()
    
    if success:
        print("\n🎉 Futures collection completed successfully!")
        print("\n💡 Next steps:")
        print("   1. Restart the API server if running")
        print("   2. Access futures: http://localhost:8000/1xbet/future")
        print("   3. The endpoint will now serve futures with proper odds")
    else:
        print("\n❌ Futures collection failed. Check logs above.")


if __name__ == "__main__":
    asyncio.run(main())
