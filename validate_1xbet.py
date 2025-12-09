"""Detailed 1xBet Endpoints Validation"""
import requests
import json

def validate_endpoint(url, name):
    print(f"\n{'='*80}")
    print(f"{name}")
    print('='*80)
    
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        
        print(f"✓ Status: {r.status_code}")
        print(f"✓ Total Games: {len(data.get('data', []))}")
        
        if data.get('metadata'):
            print(f"\nMetadata:")
            for key, value in data['metadata'].items():
                print(f"  {key}: {value}")
        
        if data.get('data') and len(data['data']) > 0:
            game = data['data'][0]
            print(f"\nSample Game:")
            print(f"  ID: {game.get('id')}")
            print(f"  Sport: {game.get('sport', {}).get('name')}")
            print(f"  League: {game.get('league', {}).get('name')}")
            print(f"  Home: {game.get('home_team_display')}")
            print(f"  Away: {game.get('away_team_display')}")
            print(f"  Start: {game.get('start_date')}")
            print(f"  Status: {game.get('status')}")
            print(f"  Is Live: {game.get('is_live')}")
            print(f"  Odds Count: {len(game.get('odds', []))}")
            
            if game.get('odds'):
                odd = game['odds'][0]
                print(f"\n  Sample Odds Entry:")
                print(f"    Sportsbook: {odd.get('sportsbook')}")
                print(f"    Market: {odd.get('market')}")
                print(f"    Selection: {odd.get('selection')}")
                print(f"    Price: {odd.get('price')}")
                print(f"    Timestamp: {odd.get('timestamp')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

BASE = "http://localhost:8000"

print("\n" + "="*80)
print("1XBET ENDPOINTS DETAILED VALIDATION")
print("="*80)

validate_endpoint(f"{BASE}/1xbet", "ALL 1XBET DATA (PREGAME + LIVE)")
validate_endpoint(f"{BASE}/1xbet/pregame", "1XBET PREGAME ONLY")
validate_endpoint(f"{BASE}/1xbet/live", "1XBET LIVE ONLY")
validate_endpoint(f"{BASE}/1xbet/history", "1XBET HISTORY")
validate_endpoint(f"{BASE}/1xbet/futures", "1XBET FUTURES")

print("\n" + "="*80)
print("VALIDATION COMPLETE ✓")
print("="*80)
