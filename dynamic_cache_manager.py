#!/usr/bin/env python3
"""
Dynamic Cache Manager - Auto-updates cache with new teams/sports
Implements incremental updates with merge-only logic (never deletes)
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Optional
import threading


class DynamicCacheManager:
    """Manages cache with dynamic updates - only adds, never deletes"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.cache_file = self.base_dir / "cache_data.json"
        self.cache_backup_dir = self.base_dir / "cache_backups"
        
        # Create backup directory if it doesn't exist
        self.cache_backup_dir.mkdir(exist_ok=True)
        
        # Thread safety for concurrent updates
        self.lock = threading.Lock()
        
        # Cache structure
        self.cache_data = {
            'sports': {},
            'teams_global': {},
            'players': {},
            'lookups': {
                'team_alias_to_canonical': {},
                'sport_alias_to_canonical': {},
                'player_alias_to_canonical': {}
            },
            'metadata': {
                'version': '2.0',
                'structure': 'database_ready',
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_sports': 0,
                'total_teams': 0,
                'total_players': 0,
                'total_aliases': 0,
                'update_count': 0
            }
        }
        
        self.sport_id_counter = 1
        self.team_id_counter = 1
        self.player_id_counter = 1
        
        # Load existing cache
        self.load_cache()
    
    def normalize_name(self, name: str) -> str:
        """Basic normalization for comparison"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def load_cache(self) -> bool:
        """Load existing cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    
                    # Convert lists back to sets for easier manipulation
                    self.cache_data = loaded_data
                    
                    # Ensure metadata has all required fields
                    if 'update_count' not in self.cache_data.get('metadata', {}):
                        if 'metadata' not in self.cache_data:
                            self.cache_data['metadata'] = {}
                        self.cache_data['metadata']['update_count'] = 0
                    
                    # Restore ID counters from existing data
                    if self.cache_data['sports']:
                        max_sport_id = max(s['id'] for s in self.cache_data['sports'].values())
                        self.sport_id_counter = max_sport_id + 1
                    
                    if self.cache_data['teams_global']:
                        max_team_id = max(t['id'] for t in self.cache_data['teams_global'].values())
                        self.team_id_counter = max_team_id + 1

                    print(f"[OK] Loaded existing cache: {self.cache_data['metadata']['total_teams']} teams, "
                          f"{self.cache_data['metadata']['total_sports']} sports")
                    return True
            else:
                print("[WARN] No existing cache found, starting fresh")
                return False
        except Exception as e:
            print(f"[WARN] Error loading cache: {e}, starting fresh")
            return False
    
    def save_cache(self, replicate_to_subfolders: bool = True):
        """Save cache to disk with automatic timestamped backups (thread-safe)"""
        with self.lock:
            try:
                # Update metadata
                self.cache_data['metadata']['last_updated'] = datetime.now().isoformat()
                self.cache_data['metadata']['total_sports'] = len(self.cache_data['sports'])
                self.cache_data['metadata']['total_teams'] = len(self.cache_data['teams_global'])
                self.cache_data['metadata']['total_aliases'] = len(
                    self.cache_data['lookups']['team_alias_to_canonical']
                )
                self.cache_data['metadata']['update_count'] += 1
                
                # Create timestamped backup before saving
                self._create_timestamped_backup()
                
                # Save main cache
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
                
                # Replicate to subfolders if requested
                if replicate_to_subfolders:
                    for subfolder in ['1xbet', 'bet365', 'fanduel']:
                        subfolder_path = self.base_dir / subfolder / "cache_data.json"
                        if subfolder_path.parent.exists():
                            with open(subfolder_path, 'w', encoding='utf-8') as f:
                                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
                
                # Cleanup old backups (keep last 10)
                self._cleanup_old_backups(keep_count=10)
                
                return True
            except Exception as e:
                print(f"[ERROR] Error saving cache: {e}")
                return False
    
    def _create_timestamped_backup(self):
        """Create a timestamped backup of the cache in cache_backups folder"""
        try:
            if self.cache_file.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"cache_data_{timestamp}.json"
                backup_path = self.cache_backup_dir / backup_filename
                
                # Copy current cache to backup
                import shutil
                shutil.copy2(self.cache_file, backup_path)
                
        except Exception as e:
            print(f"[WARN] Could not create backup: {e}")
    
    def _cleanup_old_backups(self, keep_count: int = 10):
        """Keep only the most recent N backups, delete older ones"""
        try:
            # Get all backup files
            backup_files = sorted(
                self.cache_backup_dir.glob("cache_data_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Delete old backups beyond keep_count
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                
        except Exception as e:
            print(f"[WARN] Could not cleanup old backups: {e}")
    
    def restore_from_backup(self, backup_file: Optional[Path] = None) -> bool:
        """
        Restore cache from a backup file
        If backup_file is None, uses the most recent backup
        """
        try:
            if backup_file is None:
                # Get most recent backup
                backup_files = sorted(
                    self.cache_backup_dir.glob("cache_data_*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )
                if not backup_files:
                    print("[ERROR] No backup files found")
                    return False
                backup_file = backup_files[0]
            
            # Load backup
            with open(backup_file, 'r', encoding='utf-8') as f:
                self.cache_data = json.load(f)
            
            # Save as current cache
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] Cache restored from backup: {backup_file.name}")
            return True
            
        except Exception as e:
            print(f"❌ Error restoring from backup: {e}")
            return False
    
    def add_sport(self, canonical_sport: str, aliases: Set[str] = None, source: str = "") -> bool:
        """
        Add or update sport in cache (merge-only, never deletes)
        Returns True if something was added/updated
        """
        if not canonical_sport:
            return False
        
        with self.lock:
            normalized_canonical = self.normalize_name(canonical_sport)
            was_updated = False
            
            # Create sport if doesn't exist
            if canonical_sport not in self.cache_data['sports']:
                self.cache_data['sports'][canonical_sport] = {
                    'id': self.sport_id_counter,
                    'canonical_name': canonical_sport,
                    'normalized_name': normalized_canonical,
                    'aliases': [],
                    'teams': {},
                    'metadata': {
                        'sources': [],
                        'match_count': 0,
                        'created_at': datetime.now().isoformat(),
                        'last_updated': datetime.now().isoformat()
                    }
                }
                self.sport_id_counter += 1
                was_updated = True
            
            sport_data = self.cache_data['sports'][canonical_sport]
            
            # Add source if not already tracked
            if source and source not in sport_data['metadata']['sources']:
                sport_data['metadata']['sources'].append(source)
                was_updated = True
            
            # Add canonical name as alias
            if normalized_canonical not in sport_data['aliases']:
                sport_data['aliases'].append(normalized_canonical)
                self.cache_data['lookups']['sport_alias_to_canonical'][normalized_canonical] = canonical_sport
                was_updated = True
            
            # Add additional aliases
            if aliases:
                for alias in aliases:
                    normalized_alias = self.normalize_name(alias)
                    if normalized_alias and normalized_alias not in sport_data['aliases']:
                        sport_data['aliases'].append(normalized_alias)
                        self.cache_data['lookups']['sport_alias_to_canonical'][normalized_alias] = canonical_sport
                        was_updated = True
            
            if was_updated:
                sport_data['metadata']['last_updated'] = datetime.now().isoformat()
            
            return was_updated
    
    def add_team(self, sport_canonical: str, team_canonical: str, 
                 aliases: Set[str] = None, source: str = "") -> bool:
        """
        Add or update team in cache (merge-only, never deletes)
        Returns True if something was added/updated
        """
        if not sport_canonical or not team_canonical:
            return False
        
        with self.lock:
            # Ensure sport exists
            if sport_canonical not in self.cache_data['sports']:
                self.add_sport(sport_canonical, source=source)
            
            normalized_team = self.normalize_name(team_canonical)
            was_updated = False
            
            # Create team if doesn't exist
            if team_canonical not in self.cache_data['sports'][sport_canonical]['teams']:
                team_id = self.team_id_counter
                self.cache_data['sports'][sport_canonical]['teams'][team_canonical] = {
                    'id': team_id,
                    'canonical_name': team_canonical,
                    'normalized_name': normalized_team,
                    'sport': sport_canonical,
                    'sport_id': self.cache_data['sports'][sport_canonical]['id'],
                    'aliases': [],
                    'metadata': {
                        'sources': [],
                        'match_count': 0,
                        'created_at': datetime.now().isoformat(),
                        'last_updated': datetime.now().isoformat()
                    }
                }
                
                # Add to global teams
                self.cache_data['teams_global'][team_canonical] = {
                    'id': team_id,
                    'sport': sport_canonical,
                    'canonical_name': team_canonical,
                    'normalized_name': normalized_team
                }
                
                self.team_id_counter += 1
                was_updated = True
            
            team_data = self.cache_data['sports'][sport_canonical]['teams'][team_canonical]
            
            # Add source if not already tracked
            if source and source not in team_data['metadata']['sources']:
                team_data['metadata']['sources'].append(source)
                was_updated = True
            
            # Add canonical name as alias
            if normalized_team not in team_data['aliases']:
                team_data['aliases'].append(normalized_team)
                self.cache_data['lookups']['team_alias_to_canonical'][normalized_team] = team_canonical
                was_updated = True
            
            # Add additional aliases
            if aliases:
                for alias in aliases:
                    normalized_alias = self.normalize_name(alias)
                    if normalized_alias and normalized_alias not in team_data['aliases']:
                        team_data['aliases'].append(normalized_alias)
                        self.cache_data['lookups']['team_alias_to_canonical'][normalized_alias] = team_canonical
                        was_updated = True
            
            if was_updated:
                team_data['metadata']['last_updated'] = datetime.now().isoformat()
            
            return was_updated
    
    def process_match_data(self, match: Dict, source: str = "") -> Dict:
        """
        Process match data and auto-update cache with new teams/sports
        Returns dict with: {'updated': bool, 'new_teams': list, 'new_sports': list}
        """
        updates = {
            'updated': False,
            'new_teams': [],
            'new_sports': []
        }
        
        # Extract match info (handle different formats)
        sport = match.get('sport') or match.get('sport_name', '')
        home = match.get('home_team') or match.get('team1', '')
        away = match.get('away_team') or match.get('team2', '')
        
        if not sport or not home or not away:
            return updates
        
        # Check if sport exists in cache
        normalized_sport = self.normalize_name(sport)
        canonical_sport = self.cache_data['lookups']['sport_alias_to_canonical'].get(
            normalized_sport, sport
        )
        
        # Add sport if new
        if self.add_sport(canonical_sport, {sport}, source):
            updates['new_sports'].append(canonical_sport)
            updates['updated'] = True
        
        # Add home team if new
        normalized_home = self.normalize_name(home)
        canonical_home = self.cache_data['lookups']['team_alias_to_canonical'].get(
            normalized_home, home
        )
        
        if self.add_team(canonical_sport, canonical_home, {home}, source):
            updates['new_teams'].append(canonical_home)
            updates['updated'] = True
        
        # Add away team if new
        normalized_away = self.normalize_name(away)
        canonical_away = self.cache_data['lookups']['team_alias_to_canonical'].get(
            normalized_away, away
        )
        
        if self.add_team(canonical_sport, canonical_away, {away}, source):
            updates['new_teams'].append(canonical_away)
            updates['updated'] = True
        
        return updates
    
    def auto_update_from_file(self, file_path: Path, source: str = "") -> Dict:
        """
        Auto-update cache from a JSON data file
        Returns summary of updates
        """
        summary = {
            'success': False,
            'file': str(file_path),
            'source': source,
            'new_teams': [],
            'new_sports': [],
            'matches_processed': 0,
            'errors': []
        }
        
        try:
            if not file_path.exists():
                summary['errors'].append(f"File not found: {file_path}")
                return summary
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract matches from different file formats
            matches = []
            
            # Format 1: Direct matches array
            if 'matches' in data:
                matches = data['matches']
            
            # Format 2: data.matches
            elif 'data' in data and isinstance(data['data'], dict) and 'matches' in data['data']:
                matches = data['data']['matches']
            
            # Format 3: sports_data structure (bet365)
            elif 'sports_data' in data:
                for sport_name, sport_info in data['sports_data'].items():
                    games = sport_info.get('games', [])
                    for game in games:
                        game['sport'] = game.get('sport', sport_name)
                        matches.append(game)
            
            # Process each match
            for match in matches:
                updates = self.process_match_data(match, source)
                if updates['updated']:
                    summary['new_teams'].extend(updates['new_teams'])
                    summary['new_sports'].extend(updates['new_sports'])
                summary['matches_processed'] += 1
            
            # Remove duplicates
            summary['new_teams'] = list(set(summary['new_teams']))
            summary['new_sports'] = list(set(summary['new_sports']))
            
            # Save if updates were made
            if summary['new_teams'] or summary['new_sports']:
                if self.save_cache():
                    summary['success'] = True
                    print(f"✓ Updated cache from {file_path.name}: "
                          f"+{len(summary['new_teams'])} teams, "
                          f"+{len(summary['new_sports'])} sports")
                else:
                    summary['errors'].append("Failed to save cache")
            else:
                summary['success'] = True  # No updates needed is still success
            
            return summary
            
        except Exception as e:
            summary['errors'].append(str(e))
            print(f"❌ Error updating cache from {file_path}: {e}")
            return summary
    
    def get_stats(self) -> Dict:
        """Get current cache statistics"""
        return {
            'total_sports': len(self.cache_data['sports']),
            'total_teams': len(self.cache_data['teams_global']),
            'total_aliases': len(self.cache_data['lookups']['team_alias_to_canonical']),
            'last_updated': self.cache_data['metadata'].get('last_updated'),
            'update_count': self.cache_data['metadata'].get('update_count', 0)
        }


if __name__ == "__main__":
    print("=" * 80)
    print("DYNAMIC CACHE MANAGER - Testing")
    print("=" * 80)
    
    manager = DynamicCacheManager()
    
    # Test auto-update from all source files
    sources = [
        (Path("bet365/bet365_current_pregame.json"), "bet365"),
        (Path("bet365/bet365_live_current.json"), "bet365"),
        (Path("fanduel/fanduel_pregame.json"), "fanduel"),
        (Path("fanduel/fanduel_live.json"), "fanduel"),
        (Path("1xbet/1xbet_pregame.json"), "1xbet"),
        (Path("1xbet/1xbet_live.json"), "1xbet")
    ]
    
    for file_path, source in sources:
        summary = manager.auto_update_from_file(file_path, source)
        if summary['success']:
            print(f"\n✓ {source}: {summary['matches_processed']} matches, "
                  f"+{len(summary['new_teams'])} new teams, "
                  f"+{len(summary['new_sports'])} new sports")
        else:
            print(f"\n❌ {source}: {', '.join(summary['errors'])}")
    
    # Show final stats
    stats = manager.get_stats()
    print("\n" + "=" * 80)
    print("FINAL CACHE STATISTICS")
    print("=" * 80)
    print(f"Total Sports: {stats['total_sports']}")
    print(f"Total Teams: {stats['total_teams']}")
    print(f"Total Aliases: {stats['total_aliases']}")
    print(f"Last Updated: {stats['last_updated']}")
    print(f"Update Count: {stats['update_count']}")
    print("\n✅ Cache is now up-to-date!")
