#!/usr/bin/env python3
"""
Build Team Name Cache - Creates unified team/sport/player name mappings
Database-ready structure with hierarchical organization:
- Sports → Teams → Aliases (many-to-many ready)
- Optimized for O(1) lookups and future database migration
- Now uses DynamicCacheManager for incremental updates
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import re
from datetime import datetime
from dynamic_cache_manager import DynamicCacheManager


class TeamCacheBuilder:
    """Build comprehensive team/sport name cache from all sources using DynamicCacheManager"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        
        # Use DynamicCacheManager for incremental updates
        self.cache_manager = DynamicCacheManager(self.base_dir)
    
    def normalize_name(self, name: str) -> str:
        """Basic normalization for comparison"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def add_sport(self, canonical_sport: str, alias: str = ""):
        """Add sport to cache with database-ready structure"""
        if not canonical_sport:
            return
        
        normalized_canonical = self.normalize_name(canonical_sport)
        
        if canonical_sport not in self.cache_structure['sports']:
            self.cache_structure['sports'][canonical_sport] = {
                'id': self.sport_id_counter,
                'canonical_name': canonical_sport,
                'normalized_name': normalized_canonical,
                'aliases': set(),
                'teams': {},
                'metadata': {
                    'sources': set(),
                    'match_count': 0
                }
            }
            self.sport_id_counter += 1
        
        if alias:
            normalized_alias = self.normalize_name(alias)
            self.cache_structure['sports'][canonical_sport]['aliases'].add(alias)
            self.cache_structure['sports'][canonical_sport]['aliases'].add(normalized_alias)
            self.cache_structure['lookups']['sport_alias_to_canonical'][normalized_alias] = canonical_sport
        
        self.cache_structure['lookups']['sport_alias_to_canonical'][normalized_canonical] = canonical_sport
    
    def add_team(self, sport_canonical: str, team_canonical: str, alias: str = "", source: str = ""):
        """Add team to cache under a sport"""
        if not sport_canonical or not team_canonical:
            return
        
        if sport_canonical not in self.cache_structure['sports']:
            self.add_sport(sport_canonical)
        
        normalized_team = self.normalize_name(team_canonical)
        
        if team_canonical not in self.cache_structure['sports'][sport_canonical]['teams']:
            self.cache_structure['sports'][sport_canonical]['teams'][team_canonical] = {
                'id': self.team_id_counter,
                'canonical_name': team_canonical,
                'normalized_name': normalized_team,
                'sport': sport_canonical,
                'sport_id': self.cache_structure['sports'][sport_canonical]['id'],
                'aliases': set(),
                'metadata': {
                    'sources': set(),
                    'match_count': 0
                }
            }
            self.team_id_counter += 1
            
            self.cache_structure['teams_global'][team_canonical] = {
                'id': self.cache_structure['sports'][sport_canonical]['teams'][team_canonical]['id'],
                'sport': sport_canonical,
                'canonical_name': team_canonical,
                'normalized_name': normalized_team
            }
        
        team_data = self.cache_structure['sports'][sport_canonical]['teams'][team_canonical]
        
        if source:
            team_data['metadata']['sources'].add(source)
        
        if alias:
            normalized_alias = self.normalize_name(alias)
            team_data['aliases'].add(alias)
            team_data['aliases'].add(normalized_alias)
            self.cache_structure['lookups']['team_alias_to_canonical'][normalized_alias] = team_canonical
        
        self.cache_structure['lookups']['team_alias_to_canonical'][normalized_team] = team_canonical
    
    def find_canonical_team(self, team_name: str) -> str:
        """Find canonical team name (O(1))"""
        normalized = self.normalize_name(team_name)
        return self.cache_structure['lookups']['team_alias_to_canonical'].get(normalized, "")
    
    def find_canonical_sport(self, sport_name: str) -> str:
        """Find canonical sport name (O(1))"""
        normalized = self.normalize_name(sport_name)
        return self.cache_structure['lookups']['sport_alias_to_canonical'].get(normalized, "")
    
    def scan_bet365_data(self):
        """Scan Bet365 files for team names"""
        print("Scanning Bet365 data...")
        
        pregame_file = self.base_dir / "bet365" / "bet365_current_pregame.json"
        if pregame_file.exists():
            with open(pregame_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                match_count = 0
                
                # Bet365 pregame uses 'sports_data' structure
                sports_data = data.get('sports_data', {})
                for sport_name, sport_info in sports_data.items():
                    games = sport_info.get('games', [])
                    for game in games:
                        sport = game.get('sport', sport_name)
                        home = game.get('team1', '')
                        away = game.get('team2', '')
                        
                        if sport:
                            self.add_sport(sport, sport)
                        if home and sport:
                            self.add_team(sport, home, home, 'bet365')
                        if away and sport:
                            self.add_team(sport, away, away, 'bet365')
                        match_count += 1
                
                print(f"  ✓ Bet365 pregame: {match_count} matches")
        
        live_file = self.base_dir / "bet365" / "bet365_live_current.json"
        if live_file.exists():
            with open(live_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                matches = data.get('matches', [])
                for match in matches:
                    sport = match.get('sport', '')
                    home = match.get('home_team', '')
                    away = match.get('away_team', '')
                    
                    if sport:
                        self.add_sport(sport, sport)
                    if home and sport:
                        self.add_team(sport, home, home, 'bet365')
                    if away and sport:
                        self.add_team(sport, away, away, 'bet365')
                
                print(f"  ✓ Bet365 live: {len(matches)} matches")
    
    def scan_fanduel_data(self):
        """Scan FanDuel files for team names"""
        print("Scanning FanDuel data...")
        
        pregame_file = self.base_dir / "fanduel" / "fanduel_pregame.json"
        if pregame_file.exists():
            with open(pregame_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                matches = data.get('data', {}).get('matches', [])
                for match in matches:
                    sport = match.get('sport', '')
                    home = match.get('home_team', '')
                    away = match.get('away_team', '')
                    
                    sport_canonical = self.find_canonical_sport(sport) or sport
                    if sport_canonical:
                        self.add_sport(sport_canonical, sport)
                    
                    if home and sport_canonical:
                        canonical_home = self.find_canonical_team(home) or home
                        self.add_team(sport_canonical, canonical_home, home, 'fanduel')
                    
                    if away and sport_canonical:
                        canonical_away = self.find_canonical_team(away) or away
                        self.add_team(sport_canonical, canonical_away, away, 'fanduel')
                
                print(f"  ✓ FanDuel pregame: {len(matches)} matches")
        
        live_file = self.base_dir / "fanduel" / "fanduel_live.json"
        if live_file.exists():
            with open(live_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                matches = data.get('matches', [])
                for match in matches:
                    sport = match.get('sport', '')
                    home = match.get('home_team', '')
                    away = match.get('away_team', '')
                    
                    sport_canonical = self.find_canonical_sport(sport) or sport
                    if sport_canonical:
                        self.add_sport(sport_canonical, sport)
                    
                    if home and sport_canonical:
                        canonical_home = self.find_canonical_team(home) or home
                        self.add_team(sport_canonical, canonical_home, home, 'fanduel')
                    
                    if away and sport_canonical:
                        canonical_away = self.find_canonical_team(away) or away
                        self.add_team(sport_canonical, canonical_away, away, 'fanduel')
                
                print(f"  ✓ FanDuel live: {len(matches)} matches")
    
    def scan_1xbet_data(self):
        """Scan 1xBet files for team names"""
        print("Scanning 1xBet data...")
        
        pregame_file = self.base_dir / "1xbet" / "1xbet_pregame.json"
        if pregame_file.exists():
            with open(pregame_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                matches = data.get('data', {}).get('matches', [])
                for match in matches:
                    sport = match.get('sport_name', '')
                    home = match.get('team1', '')
                    away = match.get('team2', '')
                    
                    sport_canonical = self.find_canonical_sport(sport) or sport
                    if sport_canonical:
                        self.add_sport(sport_canonical, sport)
                    
                    if home and sport_canonical:
                        canonical_home = self.find_canonical_team(home) or home
                        self.add_team(sport_canonical, canonical_home, home, '1xbet')
                    
                    if away and sport_canonical:
                        canonical_away = self.find_canonical_team(away) or away
                        self.add_team(sport_canonical, canonical_away, away, '1xbet')
                
                print(f"  ✓ 1xBet pregame: {len(matches)} matches")
        
        live_file = self.base_dir / "1xbet" / "1xbet_live.json"
        if live_file.exists():
            with open(live_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                matches = data.get('matches', [])
                for match in matches:
                    sport = match.get('sport_name', '')
                    home = match.get('team1', '')
                    away = match.get('team2', '')
                    
                    sport_canonical = self.find_canonical_sport(sport) or sport
                    if sport_canonical:
                        self.add_sport(sport_canonical, sport)
                    
                    if home and sport_canonical:
                        canonical_home = self.find_canonical_team(home) or home
                        self.add_team(sport_canonical, canonical_home, home, '1xbet')
                    
                    if away and sport_canonical:
                        canonical_away = self.find_canonical_team(away) or away
                        self.add_team(sport_canonical, canonical_away, away, '1xbet')
                
                print(f"  ✓ 1xBet live: {len(matches)} matches")
    
    def save_cache(self):
        """Save cache to JSON file in database-ready format"""
        output_file = self.base_dir / "cache_data.json"
        
        # Convert sets to sorted lists for JSON
        serializable_data = {
            'sports': {},
            'teams_global': self.cache_structure['teams_global'],
            'players': self.cache_structure['players'],
            'lookups': self.cache_structure['lookups'],
            'metadata': self.cache_structure['metadata']
        }
        
        # Convert sports structure
        for sport_name, sport_data in self.cache_structure['sports'].items():
            serializable_data['sports'][sport_name] = {
                'id': sport_data['id'],
                'canonical_name': sport_data['canonical_name'],
                'normalized_name': sport_data['normalized_name'],
                'aliases': sorted(list(sport_data['aliases'])),
                'teams': {},
                'metadata': {
                    'sources': sorted(list(sport_data['metadata']['sources'])),
                    'match_count': sport_data['metadata']['match_count']
                }
            }
            
            # Convert teams under each sport
            for team_name, team_data in sport_data['teams'].items():
                serializable_data['sports'][sport_name]['teams'][team_name] = {
                    'id': team_data['id'],
                    'canonical_name': team_data['canonical_name'],
                    'normalized_name': team_data['normalized_name'],
                    'sport': team_data['sport'],
                    'sport_id': team_data['sport_id'],
                    'aliases': sorted(list(team_data['aliases'])),
                    'metadata': {
                        'sources': sorted(list(team_data['metadata']['sources'])),
                        'match_count': team_data['metadata']['match_count']
                    }
                }
        
        # Update metadata
        serializable_data['metadata']['total_sports'] = len(self.cache_structure['sports'])
        serializable_data['metadata']['total_teams'] = len(self.cache_structure['teams_global'])
        serializable_data['metadata']['total_aliases'] = len(self.cache_structure['lookups']['team_alias_to_canonical'])
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Cache saved to: {output_file}")
        print(f"   Canonical sports: {serializable_data['metadata']['total_sports']}")
        print(f"   Canonical teams: {serializable_data['metadata']['total_teams']}")
        print(f"   Team aliases: {serializable_data['metadata']['total_aliases']}")
        print(f"\n📊 Database-ready structure:")
        print(f"   - Sports table: {serializable_data['metadata']['total_sports']} records")
        print(f"   - Teams table: {serializable_data['metadata']['total_teams']} records")
        print(f"   - Team-Aliases junction: {serializable_data['metadata']['total_aliases']} mappings")
    
    def add_manual_sport_mappings(self):
        """Add manual sport name aliases for better cross-source matching"""
        print("\nAdding manual sport name mappings...")
        
        # Basketball mappings
        if 'Basketball' in self.cache_structure['sports']:
            self.add_sport('Basketball', 'NBA')
            self.add_sport('Basketball', 'NCAAB')
            self.add_sport('Basketball', 'basketball')
            print("  ✓ Mapped NBA, NCAAB → Basketball")
        
        # Ice Hockey mappings
        if 'Ice Hockey' in self.cache_structure['sports']:
            self.add_sport('Ice Hockey', 'NHL')
            self.add_sport('Ice Hockey', 'hockey')
            print("  ✓ Mapped NHL → Ice Hockey")
        
        # American Football mappings
        if 'American Football' in self.cache_structure['sports']:
            self.add_sport('American Football', 'NFL')
            self.add_sport('American Football', 'NCAAF')
            self.add_sport('American Football', 'football')
            print("  ✓ Mapped NFL, NCAAF → American Football")
        
        # Tennis mappings (already common but normalize)
        if 'Tennis' in self.cache_structure['sports']:
            self.add_sport('Tennis', 'tennis')
            print("  ✓ Mapped tennis → Tennis")
        
        # Table Tennis mappings
        if 'Table Tennis' in self.cache_structure['sports']:
            self.add_sport('Table Tennis', 'table tennis')
            self.add_sport('Table Tennis', 'tabletennis')
            print("  ✓ Mapped table tennis → Table Tennis")
        
        # Cricket mappings
        if 'Cricket' in self.cache_structure['sports']:
            self.add_sport('Cricket', 'cricket')
            print("  ✓ Mapped cricket → Cricket")
        
        # Soccer/Football mappings
        if 'Football' in self.cache_structure['sports']:
            self.add_sport('Football', 'Soccer')
            self.add_sport('Football', 'soccer')
            print("  ✓ Mapped Soccer → Football")
        elif 'Soccer' in self.cache_structure['sports']:
            self.add_sport('Soccer', 'Football')
            self.add_sport('Soccer', 'football')
            print("  ✓ Mapped Football → Soccer")
    
    def build(self):
        """Build the complete cache using DynamicCacheManager"""
        print("=" * 80)
        print("BUILDING TEAM NAME CACHE - Incremental Updates with DynamicCacheManager")
        print("=" * 80)
        print()
        
        sources = [
            (self.base_dir / "bet365" / "bet365_current_pregame.json", "bet365"),
            (self.base_dir / "bet365" / "bet365_live_current.json", "bet365"),
            (self.base_dir / "fanduel" / "fanduel_pregame.json", "fanduel"),
            (self.base_dir / "fanduel" / "fanduel_live.json", "fanduel"),
            (self.base_dir / "1xbet" / "1xbet_pregame.json", "1xbet"),
            (self.base_dir / "1xbet" / "1xbet_live.json", "1xbet")
        ]
        
        total_new_teams = 0
        total_new_sports = 0
        
        for file_path, source in sources:
            print(f"\nScanning {source} data...")
            summary = self.cache_manager.auto_update_from_file(file_path, source)
            
            if summary['success']:
                print(f"  ✓ {source}: {summary['matches_processed']} matches, "
                      f"+{len(summary['new_teams'])} new teams, "
                      f"+{len(summary['new_sports'])} new sports")
                total_new_teams += len(summary['new_teams'])
                total_new_sports += len(summary['new_sports'])
            else:
                print(f"  ❌ {source}: {', '.join(summary['errors'])}")
        
        # Add manual sport name mappings for better cross-source matching
        print("\nAdding manual sport name mappings...")
        self.add_manual_sport_mappings()
        
        # Get final stats
        stats = self.cache_manager.get_stats()
        
        print("\n" + "=" * 80)
        print("CACHE BUILD COMPLETE")
        print("=" * 80)
        print(f"   Canonical sports: {stats['total_sports']}")
        print(f"   Canonical teams: {stats['total_teams']}")
        print(f"   Team aliases: {stats['total_aliases']}")
        print(f"   New teams added: {total_new_teams}")
        print(f"   New sports added: {total_new_sports}")
        print(f"\n� Database-ready structure:")
        print(f"   - Sports table: {stats['total_sports']} records")
        print(f"   - Teams table: {stats['total_teams']} records")
        print(f"   - Team-Aliases junction: {stats['total_aliases']} mappings")
        print("\n✅ Cache build complete with incremental updates!")
        print("   Note: Existing data was preserved, only new items were added")
    
    def add_manual_sport_mappings(self):
        """Add manual sport name aliases for better cross-source matching"""
        
        mappings = [
            # Basketball mappings
            ('Basketball', {'NBA', 'NCAAB', 'basketball'}),
            ('NBA', {'Basketball', 'basketball', 'nba'}),
            
            # Ice Hockey mappings
            ('Ice Hockey', {'NHL', 'hockey', 'ice hockey'}),
            ('NHL', {'Ice Hockey', 'hockey', 'nhl'}),
            
            # American Football mappings
            ('American Football', {'NFL', 'NCAAF', 'football', 'american football'}),
            ('NFL', {'American Football', 'football', 'nfl'}),
            ('NCAAF', {'American Football', 'College Football', 'ncaaf'}),
            
            # Soccer/Football mappings
            ('Football', {'Soccer', 'soccer', 'football'}),
            ('Soccer', {'Football', 'football', 'soccer'}),
            
            # Tennis mappings
            ('Tennis', {'tennis'}),
            
            # Table Tennis mappings
            ('Table Tennis', {'table tennis', 'tabletennis', 'ping pong'}),
            
            # Cricket mappings
            ('Cricket', {'cricket'}),
            
            # MMA/UFC mappings
            ('MMA', {'UFC', 'mma', 'ufc', 'mixed martial arts'}),
            ('UFC', {'MMA', 'mma', 'ufc'}),
            
            # Muay Thai mappings
            ('Muay Thai', {'muay thai', 'muaythai', 'thai boxing'}),
        ]
        
        added_count = 0
        for canonical, aliases in mappings:
            if self.cache_manager.add_sport(canonical, aliases):
                added_count += 1
        
        if added_count > 0:
            self.cache_manager.save_cache()
            print(f"  ✓ Added/updated {added_count} sport name mappings")


if __name__ == "__main__":
    builder = TeamCacheBuilder()
    builder.build()
