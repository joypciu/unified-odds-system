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
        # Replace punctuation with spaces to avoid merging words
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        # Remove common club suffixes like FC, FK, SC, CF, AC (with or without dots)
        normalized = re.sub(r'\b(?:f\.?c\.?|f\.?k\.?|s\.?c\.?|c\.?f\.?|a\.?c\.?)\b', ' ', normalized)
        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    def strip_common_tokens(self, name: str) -> str:
        """Return a variant with extra tokens removed to improve matching."""
        if not name:
            return ''
        tmp = self.normalize_name(name)
        # Remove words like 'team', 'club', year tokens, and short qualifiers
        tmp = re.sub(r"\b(team|club|u\d{1,2}|\d{4})\b", ' ', tmp)
        tmp = re.sub(r'\s+', ' ', tmp)
        return tmp.strip()
    
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

                    # Ensure normalization_stats exists
                    if 'normalization_stats' not in self.cache_data.get('metadata', {}):
                        self.cache_data['metadata']['normalization_stats'] = {
                            'teams_merged': 0,
                            'duplicates_removed': 0,
                            'aliases_created': 0,
                            'last_cleanup': None
                        }
                    
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

    def cleanup_duplicates(self) -> Dict:
        """
        Intelligent cleanup of duplicates and normalization issues
        Returns summary of cleanup operations
        """
        summary = {
            'duplicates_removed': 0,
            'teams_merged': 0,
            'aliases_cleaned': 0,
            'orphaned_entries': 0
        }

        with self.lock:
            try:
                # Step 1: Find and merge duplicate teams within the same sport
                for sport_name, sport_data in self.cache_data['sports'].items():
                    teams = sport_data['teams']
                    normalized_to_canonical = {}

                    # Group teams by normalized name
                    for team_name, team_data in teams.items():
                        normalized = team_data.get('normalized_name', self.normalize_name(team_name))
                        if normalized not in normalized_to_canonical:
                            normalized_to_canonical[normalized] = team_name
                        else:
                            # Merge this team into the canonical one
                            canonical_name = normalized_to_canonical[normalized]
                            if canonical_name != team_name:
                                # Move aliases and metadata
                                canonical_team = teams[canonical_name]
                                if 'aliases' in team_data:
                                    for alias in team_data['aliases']:
                                        if alias not in canonical_team.get('aliases', []):
                                            canonical_team.setdefault('aliases', []).append(alias)
                                            self.cache_data['lookups']['team_alias_to_canonical'][alias] = canonical_name

                                # Update sources
                                if 'metadata' in team_data and 'sources' in team_data['metadata']:
                                    for source in team_data['metadata']['sources']:
                                        if source not in canonical_team.get('metadata', {}).get('sources', []):
                                            canonical_team.setdefault('metadata', {}).setdefault('sources', []).append(source)

                                # Remove the duplicate team
                                del teams[team_name]
                                summary['teams_merged'] += 1

                # Step 2: Clean up orphaned global team entries
                global_teams = self.cache_data['teams_global']
                existing_team_names = set()
                for sport_data in self.cache_data['sports'].values():
                    existing_team_names.update(sport_data['teams'].keys())

                orphaned_teams = [name for name in global_teams.keys() if name not in existing_team_names]
                for orphaned in orphaned_teams:
                    del global_teams[orphaned]
                    summary['orphaned_entries'] += 1

                # Step 3: Clean up invalid alias mappings
                aliases_to_remove = []
                for alias, canonical in self.cache_data['lookups']['team_alias_to_canonical'].items():
                    if canonical not in existing_team_names:
                        aliases_to_remove.append(alias)

                for alias in aliases_to_remove:
                    del self.cache_data['lookups']['team_alias_to_canonical'][alias]
                    summary['aliases_cleaned'] += 1

                # Update metadata
                self.cache_data['metadata']['normalization_stats']['teams_merged'] = summary['teams_merged']
                self.cache_data['metadata']['normalization_stats']['duplicates_removed'] = summary['duplicates_removed']
                self.cache_data['metadata']['normalization_stats']['aliases_created'] = len(self.cache_data['lookups']['team_alias_to_canonical'])
                self.cache_data['metadata']['normalization_stats']['last_cleanup'] = datetime.now().isoformat()

                if sum(summary.values()) > 0:
                    self.save_cache()

                print(f"[OK] Cache cleanup completed: {summary}")
                return summary

            except Exception as e:
                print(f"[ERROR] Error during cache cleanup: {e}")
                return summary
    
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
            print(f"[ERROR] Error restoring from backup: {e}")
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

            # Also add a stripped variant without common tokens (improves matching like 'qarabag fk' -> 'qarabag')
            stripped_canonical = self.strip_common_tokens(team_canonical)
            if stripped_canonical and stripped_canonical not in team_data['aliases']:
                team_data['aliases'].append(stripped_canonical)
                self.cache_data['lookups']['team_alias_to_canonical'][stripped_canonical] = team_canonical
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

        # Add home team if new - improved normalization logic
        canonical_home = self._find_or_create_canonical_team_name(home, canonical_sport, source)
        if self.add_team(canonical_sport, canonical_home, {home}, source):
            updates['new_teams'].append(canonical_home)
            updates['updated'] = True

        # Add away team if new - improved normalization logic
        canonical_away = self._find_or_create_canonical_team_name(away, canonical_sport, source)
        if self.add_team(canonical_sport, canonical_away, {away}, source):
            updates['new_teams'].append(canonical_away)
            updates['updated'] = True

        return updates

    def _find_or_create_canonical_team_name(self, team_name: str, sport: str, source: str = "") -> str:
        """
        Find existing canonical team name or create new one with intelligent matching
        """
        if not team_name:
            return team_name

        # Step 1: Direct normalized lookup
        normalized = self.normalize_name(team_name)
        canonical = self.cache_data['lookups']['team_alias_to_canonical'].get(normalized)
        if canonical:
            return canonical

        # Step 2: Stripped variant lookup (remove FC/FK/etc)
        stripped = self.strip_common_tokens(team_name)
        if stripped and stripped != normalized:
            canonical = self.cache_data['lookups']['team_alias_to_canonical'].get(stripped)
            if canonical:
                return canonical

        # Step 3: Check if any existing team in this sport has similar normalized names
        sport_teams = self.cache_data['sports'].get(sport, {}).get('teams', {})
        for existing_team_name, team_data in sport_teams.items():
            existing_normalized = team_data.get('normalized_name', '')
            existing_stripped = self.strip_common_tokens(existing_team_name)

            # Check similarity scores
            if self._teams_are_similar(normalized, existing_normalized, stripped, existing_stripped):
                # Found a match! Use existing canonical name
                return existing_team_name

        # Step 4: No match found, use original name as canonical
        return team_name

    def _teams_are_similar(self, norm1: str, norm2: str, stripped1: str, stripped2: str) -> bool:
        """
        Determine if two team names are similar enough to be considered the same team
        """
        if not norm1 or not norm2:
            return False

        # Exact match on normalized names
        if norm1 == norm2:
            return True

        # Exact match on stripped names
        if stripped1 and stripped2 and stripped1 == stripped2:
            return True

        # One is substring of the other (but not too short)
        if len(norm1) > 3 and len(norm2) > 3:
            if norm1 in norm2 or norm2 in norm1:
                return True

        # Check if one normalized name contains the other's stripped version
        if stripped1 and stripped2:
            if (stripped1 in norm2 and len(stripped1) > 3) or (stripped2 in norm1 and len(stripped2) > 3):
                return True

        return False
    
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
            'update_count': self.cache_data['metadata'].get('update_count', 0),
            'normalization_stats': self.cache_data['metadata'].get('normalization_stats', {})
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
            print(f"\n[ERROR] {source}: {', '.join(summary['errors'])}")
    
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
