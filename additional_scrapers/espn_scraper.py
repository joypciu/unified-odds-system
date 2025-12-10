#!/usr/bin/env python3
"""
ESPN Public API Scraper - NO API KEY NEEDED
Fetches scores and team data from ESPN's free public APIs
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from cache_auto_update_hook import on_data_saved


class ESPNScraper:
    """Scraper for ESPN's public APIs - completely free, no authentication"""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.base_url = "http://site.api.espn.com/apis/site/v2/sports"
        self.output_file = self.base_dir / "espn_data.json"
        
        # Sports endpoints (all FREE, no API key needed)
        self.sports_endpoints = {
            # Football
            'nfl': 'football/nfl',
            'college_football': 'football/college-football',
            
            # Basketball
            'nba': 'basketball/nba',
            'wnba': 'basketball/wnba',
            'mens_college_basketball': 'basketball/mens-college-basketball',
            'womens_college_basketball': 'basketball/womens-college-basketball',
            
            # Baseball
            'mlb': 'baseball/mlb',
            'college_baseball': 'baseball/college-baseball',
            
            # Hockey
            'nhl': 'hockey/nhl',
            
            # Soccer
            'epl': 'soccer/eng.1',  # English Premier League
            'mls': 'soccer/usa.1',  # MLS
            'la_liga': 'soccer/esp.1',  # La Liga
            'bundesliga': 'soccer/ger.1',  # Bundesliga
            'serie_a': 'soccer/ita.1',  # Serie A
            'ligue_1': 'soccer/fra.1',  # Ligue 1
            'champions_league': 'soccer/uefa.champions'
        }
    
    def fetch_scoreboard(self, sport: str, endpoint: str) -> Optional[Dict]:
        """Fetch scoreboard/scores for a sport"""
        url = f"{self.base_url}/{endpoint}/scoreboard"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract events/games
                events = data.get('events', [])
                
                games = []
                for event in events:
                    try:
                        competitions = event.get('competitions', [])
                        if competitions:
                            comp = competitions[0]
                            competitors = comp.get('competitors', [])
                            
                            if len(competitors) >= 2:
                                home_team = competitors[0]
                                away_team = competitors[1]
                                
                                game_info = {
                                    'event_id': event.get('id'),
                                    'name': event.get('name'),
                                    'date': event.get('date'),
                                    'home_team': home_team.get('team', {}).get('displayName'),
                                    'away_team': away_team.get('team', {}).get('displayName'),
                                    'home_score': home_team.get('score'),
                                    'away_team_score': away_team.get('score'),
                                    'status': event.get('status', {}).get('type', {}).get('description'),
                                    'venue': event.get('competitions', [{}])[0].get('venue', {}).get('fullName')
                                }
                                games.append(game_info)
                    except Exception as e:
                        continue
                
                if games:
                    return {
                        'sport': sport,
                        'endpoint': endpoint,
                        'games': games,
                        'total_games': len(games),
                        'fetched_at': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch {sport}: {e}")
            return None
    
    def fetch_teams(self, sport: str, endpoint: str) -> Optional[Dict]:
        """Fetch all teams for a sport"""
        url = f"{self.base_url}/{endpoint}/teams"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                teams = []
                sports_data = data.get('sports', [])
                
                for sport_data in sports_data:
                    leagues = sport_data.get('leagues', [])
                    for league in leagues:
                        team_list = league.get('teams', [])
                        for team_item in team_list:
                            team = team_item.get('team', {})
                            teams.append({
                                'id': team.get('id'),
                                'name': team.get('displayName'),
                                'abbreviation': team.get('abbreviation'),
                                'location': team.get('location')
                            })
                
                if teams:
                    return {
                        'sport': sport,
                        'teams': teams,
                        'total_teams': len(teams),
                        'fetched_at': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch teams for {sport}: {e}")
            return None
    
    def fetch_news(self, sport: str, endpoint: str) -> Optional[Dict]:
        """Fetch latest news for a sport"""
        url = f"{self.base_url}/{endpoint}/news"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                news_items = []
                for article in articles[:10]:  # Limit to 10
                    news_items.append({
                        'headline': article.get('headline'),
                        'description': article.get('description'),
                        'published': article.get('published')
                    })
                
                if news_items:
                    return {
                        'sport': sport,
                        'news': news_items,
                        'fetched_at': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch news for {sport}: {e}")
            return None
    
    def fetch_all_sports(self) -> Dict[str, List[Dict]]:
        """Fetch data for all configured sports"""
        results = {
            'scoreboards': [],
            'teams': [],
            'news': []
        }
        
        print(f"[INFO] Fetching {len(self.sports_endpoints)} sports from ESPN...")
        
        for sport, endpoint in self.sports_endpoints.items():
            print(f"  Fetching {sport}...")
            
            # Fetch scoreboard
            scoreboard = self.fetch_scoreboard(sport, endpoint)
            if scoreboard:
                results['scoreboards'].append(scoreboard)
                print(f"    ✓ Scoreboard: {len(scoreboard['games'])} games")
            
            time.sleep(0.5)  # Be polite with API
            
            # Fetch teams (only for major leagues, not all)
            if sport in ['nfl', 'nba', 'mlb', 'nhl', 'epl', 'mls']:
                teams = self.fetch_teams(sport, endpoint)
                if teams:
                    results['teams'].append(teams)
                    print(f"    ✓ Teams: {len(teams['teams'])} teams")
                
                time.sleep(0.5)
        
        return results
    
    def save_data(self, data: Dict):
        """Save fetched data to JSON file"""
        output = {
            'metadata': {
                'source': 'espn_public_api',
                'generated_at': datetime.now().isoformat(),
                'total_scoreboards': len(data['scoreboards']),
                'total_team_lists': len(data['teams']),
                'api_key_required': False
            },
            'data': data
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Saved to {self.output_file.name}")
        
        # Trigger cache auto-update
        on_data_saved('espn', str(self.output_file))
    
    def run_once(self):
        """Run scraper once"""
        print("=" * 70)
        print("ESPN PUBLIC API SCRAPER - NO API KEY NEEDED")
        print("=" * 70)
        print()
        
        data = self.fetch_all_sports()
        
        total_items = len(data['scoreboards']) + len(data['teams']) + len(data['news'])
        
        if total_items > 0:
            self.save_data(data)
            print()
            print(f"✅ Success: {len(data['scoreboards'])} scoreboards, {len(data['teams'])} team lists")
            return True
        else:
            print()
            print("❌ No data fetched")
            return False
    
    def run_continuous(self, interval: int = 300):
        """Run scraper continuously"""
        print(f"[INFO] Starting continuous mode (interval: {interval}s)")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[ERROR] Scraper error: {e}")
            
            print(f"\n[INFO] Waiting {interval} seconds...")
            time.sleep(interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ESPN Public API Scraper')
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous'],
        default='once',
        help='Run mode'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Interval in seconds for continuous mode (default: 300)'
    )
    
    args = parser.parse_args()
    
    scraper = ESPNScraper()
    
    try:
        if args.mode == 'once':
            success = scraper.run_once()
            return 0 if success else 1
        else:
            scraper.run_continuous(args.interval)
            return 0
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopped by user")
        return 0
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
