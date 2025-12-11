#!/usr/bin/env python3
"""
Enhanced Cache Manager - Intelligent caching with O(1) lookups and smart deduplication
Integrates with IntelligentNameMapper for superior name standardization
"""

import json
import os
import re
import sys
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Optional, List, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.mappers.intelligent_name_mapper import IntelligentNameMapper


class EnhancedCacheManager:
    """
    Enhanced cache manager with intelligent name mapping and O(1) lookups
    Features:
    - Automatic deduplication using intelligent name matching
    - O(1) team/league lookups via hash maps
    - Cross-source name standardization (1xbet, fanduel, bet365)
    - Automatic backup and versioning
    - Thread-safe operations
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.cache_file = self.base_dir / "cache_data.json"
        self.mappings_file = self.base_dir / "name_mappings.json"
        self.cache_backup_dir = self.base_dir / "cache_backups"
        
        # Create backup directory
        self.cache_backup_dir.mkdir(exist_ok=True)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Initialize intelligent name mapper
        self.name_mapper = IntelligentNameMapper()
        
        # Enhanced cache structure
        self.cache_data = {
            'version': '3.0',
            'structure': 'enhanced_with_intelligent_mapping',
            'sports': {},  # sport_canonical -> {id, canonical_name, teams: {}}
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_sports': 0,
                'total_teams': 0,
                'total_aliases': 0,
                'dedup_stats': {
                    'duplicates_merged': 0,
                    'aliases_created': 0,
                    'last_cleanup': None
                }
            }
        }
        
        # O(1) lookup indices
        self.team_lookup = {}  # normalized_name -> (sport, canonical_name)
        self.sport_lookup = {}  # normalized_sport -> canonical_sport
        
        # ID counters
        self.sport_id_counter = 1
        self.team_id_counter = 1
        
        # Load existing cache and mappings
        self.load_cache()
        self.load_mappings()
    
    def load_cache(self) -> bool:
        """Load existing cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                
                # Check version and migrate if needed
                version = loaded_data.get('version', '1.0')
                if version != '3.0':
                    print(f"[INFO] Migrating cache from v{version} to v3.0...")
                    self.cache_data = self._migrate_cache(loaded_data)
                else:
                    self.cache_data = loaded_data
                
                # Rebuild ID counters
                self._rebuild_counters()
                
                # Rebuild lookup indices
                self._rebuild_indices()
                
                stats = self.cache_data['metadata']
                print(f"[OK] Loaded cache v{self.cache_data['version']}: "
                      f"{stats['total_sports']} sports, "
                      f"{stats['total_teams']} teams, "
                      f"{stats['total_aliases']} aliases")
                return True
            else:
                print("[INFO] No existing cache found, starting fresh")
                return False
        except Exception as e:
            print(f"[ERROR] Error loading cache: {e}")
            return False
    
    def load_mappings(self) -> bool:
        """Load name mappings for the intelligent mapper"""
        try:
            if self.mappings_file.exists():
                with open(self.mappings_file, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)
                self.name_mapper.import_mappings(mappings)
                print(f"[OK] Loaded name mappings: {len(self.name_mapper.canonical_names)} canonical names")
                return True
            else:
                # Build from existing cache
                print("[INFO] No mappings file found, building from cache...")
                self.name_mapper.build_from_cache_data(self.cache_data)
                self.save_mappings()
                return True
        except Exception as e:
            print(f"[WARN] Error loading mappings: {e}")
            return False
    
    def save_cache(self, create_backup: bool = True) -> bool:
        """Save cache to disk with optional backup"""
        with self.lock:
            try:
                # Update metadata
                self.cache_data['metadata']['last_updated'] = datetime.now().isoformat()
                self.cache_data['metadata']['total_sports'] = len(self.cache_data['sports'])
                
                # Count total teams across all sports
                total_teams = 0
                for sport_data in self.cache_data['sports'].values():
                    total_teams += len(sport_data.get('teams', {}))
                self.cache_data['metadata']['total_teams'] = total_teams
                
                # Count total aliases
                total_aliases = len(self.name_mapper.alias_to_canonical)
                self.cache_data['metadata']['total_aliases'] = total_aliases
                
                # Create backup if requested
                if create_backup:
                    self._create_backup()
                
                # Save main cache
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
                
                # Replicate to subfolders
                for subfolder in ['1xbet', 'bet365', 'fanduel']:
                    subfolder_path = self.base_dir / subfolder / "cache_data.json"
                    if subfolder_path.parent.exists():
                        with open(subfolder_path, 'w', encoding='utf-8') as f:
                            json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
                
                return True
            except Exception as e:
                print(f"[ERROR] Error saving cache: {e}")
                return False
    
    def save_mappings(self) -> bool:
        """Save name mappings to disk"""
        try:
            mappings = self.name_mapper.export_mappings()
            with open(self.mappings_file, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Error saving mappings: {e}")
            return False
    
    def _migrate_cache(self, old_cache: Dict) -> Dict:
        """Migrate old cache format to new enhanced format"""
        new_cache = {
            'version': '3.0',
            'structure': 'enhanced_with_intelligent_mapping',
            'sports': {},
            'metadata': {
                'created_at': old_cache.get('metadata', {}).get('created_at', datetime.now().isoformat()),
                'last_updated': datetime.now().isoformat(),
                'total_sports': 0,
                'total_teams': 0,
                'total_aliases': 0,
                'dedup_stats': {
                    'duplicates_merged': 0,
                    'aliases_created': 0,
                    'last_cleanup': datetime.now().isoformat()
                },
                'migration_info': {
                    'from_version': old_cache.get('version', '1.0'),
                    'migrated_at': datetime.now().isoformat()
                }
            }
        }
        
        # Migrate sports data
        old_sports = old_cache.get('sports', {})
        for sport_name, sport_data in old_sports.items():
            new_cache['sports'][sport_name] = {
                'id': sport_data.get('id', 0),
                'canonical_name': sport_data.get('canonical_name', sport_name),
                'teams': {}
            }
            
            # Migrate teams
            old_teams = sport_data.get('teams', {})
            for team_name, team_data in old_teams.items():
                new_cache['sports'][sport_name]['teams'][team_name] = {
                    'id': team_data.get('id', 0),
                    'canonical_name': team_data.get('canonical_name', team_name),
                    'aliases': team_data.get('aliases', []),
                    'sources': team_data.get('metadata', {}).get('sources', []),
                    'match_count': team_data.get('metadata', {}).get('match_count', 0)
                }
        
        return new_cache
    
    def _rebuild_counters(self):
        """Rebuild ID counters from existing data"""
        max_sport_id = 0
        max_team_id = 0
        
        for sport_data in self.cache_data['sports'].values():
            sport_id = sport_data.get('id', 0)
            if sport_id > max_sport_id:
                max_sport_id = sport_id
            
            for team_data in sport_data.get('teams', {}).values():
                team_id = team_data.get('id', 0)
                if team_id > max_team_id:
                    max_team_id = team_id
        
        self.sport_id_counter = max_sport_id + 1
        self.team_id_counter = max_team_id + 1
    
    def _rebuild_indices(self):
        """Rebuild O(1) lookup indices from cache data"""
        self.team_lookup.clear()
        self.sport_lookup.clear()
        
        for sport_name, sport_data in self.cache_data['sports'].items():
            sport_canonical = sport_data.get('canonical_name', sport_name)
            sport_normalized = self.name_mapper.normalize_string(sport_canonical)
            
            self.sport_lookup[sport_normalized] = sport_canonical
            
            for team_name, team_data in sport_data.get('teams', {}).items():
                team_canonical = team_data.get('canonical_name', team_name)
                team_normalized = self.name_mapper.normalize_string(team_canonical)
                
                # Store (sport, team) tuple for O(1) lookup
                self.team_lookup[team_normalized] = (sport_canonical, team_canonical)
                
                # Also index aliases
                for alias in team_data.get('aliases', []):
                    alias_normalized = self.name_mapper.normalize_string(alias)
                    if alias_normalized:
                        self.team_lookup[alias_normalized] = (sport_canonical, team_canonical)
    
    def _create_backup(self):
        """Create timestamped backup"""
        try:
            if self.cache_file.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = self.cache_backup_dir / f"cache_data_{timestamp}.json"
                
                import shutil
                shutil.copy2(self.cache_file, backup_path)
                
                # Cleanup old backups (keep last 10)
                backups = sorted(self.cache_backup_dir.glob("cache_data_*.json"), 
                               key=lambda p: p.stat().st_mtime, reverse=True)
                for old_backup in backups[10:]:
                    old_backup.unlink()
        except Exception as e:
            print(f"[WARN] Backup failed: {e}")
    
    def get_canonical_team_name(self, team_name: str, sport: Optional[str] = None) -> str:
        """
        Get canonical team name with O(1) lookup
        Uses intelligent name mapper for standardization
        """
        if not team_name:
            return team_name
        
        # Try name mapper first
        canonical = self.name_mapper.get_canonical_name(team_name)
        
        # If mapper doesn't have it, try direct lookup
        if canonical == team_name:  # Name mapper returned original
            normalized = self.name_mapper.normalize_string(team_name)
            if normalized in self.team_lookup:
                _, canonical = self.team_lookup[normalized]
        
        return canonical
    
    def get_canonical_sport_name(self, sport_name: str) -> str:
        """Get canonical sport name with O(1) lookup"""
        if not sport_name:
            return sport_name
        
        normalized = self.name_mapper.normalize_string(sport_name)
        return self.sport_lookup.get(normalized, sport_name)
    
    def add_or_update_team(self, sport: str, team_name: str, source: str = "", 
                          aliases: Optional[List[str]] = None) -> Tuple[str, bool]:
        """
        Add or update team intelligently
        Automatically filters out esports/virtual/simulation teams
        Returns: (canonical_name, was_created)
        """
        with self.lock:
            # Filter out esports/virtual teams
            if self.name_mapper.is_esports_or_virtual(team_name):
                # Return original name but don't add to cache
                return team_name, False
            
            # Get canonical sport name
            sport_canonical = self.get_canonical_sport_name(sport)
            
            # Ensure sport exists
            if sport_canonical not in self.cache_data['sports']:
                self.cache_data['sports'][sport_canonical] = {
                    'id': self.sport_id_counter,
                    'canonical_name': sport_canonical,
                    'teams': {}
                }
                self.sport_id_counter += 1
                sport_normalized = self.name_mapper.normalize_string(sport_canonical)
                self.sport_lookup[sport_normalized] = sport_canonical
            
            # Check if team already exists (using intelligent matching)
            existing_canonical = self.get_canonical_team_name(team_name, sport_canonical)
            
            # Check if this canonical name exists in this sport
            teams = self.cache_data['sports'][sport_canonical]['teams']
            
            if existing_canonical in teams and existing_canonical != team_name:
                # Team exists with different name - add as alias
                team_data = teams[existing_canonical]
                
                # Add new alias
                team_normalized = self.name_mapper.normalize_string(team_name)
                if team_normalized not in team_data['aliases']:
                    team_data['aliases'].append(team_normalized)
                    self.team_lookup[team_normalized] = (sport_canonical, existing_canonical)
                    self.name_mapper.add_canonical_name(existing_canonical, [team_name])
                
                # Add source
                if source and source not in team_data.get('sources', []):
                    team_data.setdefault('sources', []).append(source)
                
                return existing_canonical, False
            
            elif team_name in teams:
                # Exact match exists - just update
                team_data = teams[team_name]
                if source and source not in team_data.get('sources', []):
                    team_data.setdefault('sources', []).append(source)
                
                # Add any new aliases
                if aliases:
                    for alias in aliases:
                        alias_normalized = self.name_mapper.normalize_string(alias)
                        if alias_normalized not in team_data['aliases']:
                            team_data['aliases'].append(alias_normalized)
                            self.team_lookup[alias_normalized] = (sport_canonical, team_name)
                
                return team_name, False
            
            else:
                # New team - create it
                team_id = self.team_id_counter
                self.team_id_counter += 1
                
                # Determine canonical name using name mapper
                team_canonical = self.name_mapper.get_canonical_name(team_name)
                if team_canonical == team_name:
                    # No mapping exists, check if similar team exists
                    existing_teams = list(teams.keys())
                    similar = self.name_mapper.find_best_match(team_name, existing_teams, threshold=0.80)
                    if similar:
                        # Found similar team, use it as canonical and add current as alias
                        team_data = teams[similar]
                        team_normalized = self.name_mapper.normalize_string(team_name)
                        if team_normalized not in team_data['aliases']:
                            team_data['aliases'].append(team_normalized)
                            self.team_lookup[team_normalized] = (sport_canonical, similar)
                            self.name_mapper.add_canonical_name(similar, [team_name])
                        
                        if source and source not in team_data.get('sources', []):
                            team_data.setdefault('sources', []).append(source)
                        
                        return similar, False
                    else:
                        team_canonical = team_name
                
                # Create new team
                team_normalized = self.name_mapper.normalize_string(team_canonical)
                team_aliases = [team_normalized]
                if aliases:
                    team_aliases.extend([self.name_mapper.normalize_string(a) for a in aliases if a])
                
                teams[team_canonical] = {
                    'id': team_id,
                    'canonical_name': team_canonical,
                    'aliases': list(set(team_aliases)),
                    'sources': [source] if source else [],
                    'match_count': 0
                }
                
                # Update indices
                self.team_lookup[team_normalized] = (sport_canonical, team_canonical)
                for alias in team_aliases:
                    if alias:
                        self.team_lookup[alias] = (sport_canonical, team_canonical)
                
                # Update name mapper
                self.name_mapper.add_canonical_name(team_canonical, [team_name] + (aliases or []))
                
                return team_canonical, True
    
    def process_match(self, match: Dict, source: str = "") -> Dict:
        """
        Process a match and standardize team names
        Automatically filters out esports/virtual teams
        Returns: {'home_team': canonical, 'away_team': canonical, 'sport': canonical, ...}
        """
        sport = match.get('sport') or match.get('sport_name', '')
        home = match.get('home_team') or match.get('team1', '')
        away = match.get('away_team') or match.get('team2', '')
        
        if not sport or not home or not away:
            return match
        
        # Skip esports/virtual teams
        if self.name_mapper.is_esports_or_virtual(home) or self.name_mapper.is_esports_or_virtual(away):
            return match
        
        # Standardize names
        sport_canonical = self.get_canonical_sport_name(sport)
        home_canonical, _ = self.add_or_update_team(sport, home, source)
        away_canonical, _ = self.add_or_update_team(sport, away, source)
        
        # Return standardized match
        standardized = match.copy()
        standardized['sport'] = sport_canonical
        standardized['home_team'] = home_canonical
        standardized['away_team'] = away_canonical
        
        # Keep originals for debugging
        if home != home_canonical:
            standardized['home_team_original'] = home
        if away != away_canonical:
            standardized['away_team_original'] = away
        
        return standardized
    
    def auto_update_from_json(self, file_path: Path, source: str = "", quiet: bool = False) -> Dict:
        """Auto-update cache from JSON file with optional quiet mode"""
        summary = {
            'success': False,
            'file': str(file_path),
            'source': source,
            'matches_processed': 0,
            'new_teams': 0,
            'new_sports': 0,
            'esports_filtered': 0,
            'errors': []
        }
        
        try:
            if not file_path.exists():
                summary['errors'].append("File not found")
                return summary
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract matches (handle multiple formats)
            matches = []
            if 'matches' in data:
                matches = data['matches']
            elif 'data' in data and isinstance(data['data'], dict) and 'matches' in data['data']:
                matches = data['data']['matches']
            elif 'sports_data' in data:
                for sport_name, sport_info in data['sports_data'].items():
                    games = sport_info.get('games', [])
                    for game in games:
                        game['sport'] = game.get('sport', sport_name)
                        matches.append(game)
            
            # Process matches
            teams_before = self.cache_data['metadata']['total_teams']
            sports_before = self.cache_data['metadata']['total_sports']
            
            for match in matches:
                # Check for esports before processing
                home = match.get('home_team', match.get('team1', ''))
                away = match.get('away_team', match.get('team2', ''))
                
                if self.name_mapper.is_esports_or_virtual(home) or self.name_mapper.is_esports_or_virtual(away):
                    summary['esports_filtered'] += 1
                    continue
                
                self.process_match(match, source)
                summary['matches_processed'] += 1
            
            # Calculate new items
            teams_after = len([(s, t) for s in self.cache_data['sports'].values() 
                             for t in s.get('teams', {}).keys()])
            sports_after = len(self.cache_data['sports'])
            
            summary['new_teams'] = teams_after - teams_before
            summary['new_sports'] = sports_after - sports_before
            
            # Save if updates made
            if summary['new_teams'] > 0 or summary['new_sports'] > 0:
                self.save_cache()
                self.save_mappings()
                
                if not quiet:
                    print(f"[CACHE] Updated from {file_path.name}: "
                          f"+{summary['new_teams']} teams, "
                          f"+{summary['new_sports']} sports, "
                          f"{summary['esports_filtered']} esports filtered")
            
            summary['success'] = True
            return summary
            
        except Exception as e:
            summary['errors'].append(str(e))
            print(f"[ERROR] Failed to process {file_path}: {e}")
            return summary
    
    def cleanup_and_deduplicate(self) -> Dict:
        """
        Intelligent cleanup and deduplication using name mapper
        Returns summary of operations
        """
        with self.lock:
            summary = {
                'duplicates_merged': 0,
                'aliases_added': 0,
                'teams_before': 0,
                'teams_after': 0
            }
            
            try:
                # Count teams before
                for sport_data in self.cache_data['sports'].values():
                    summary['teams_before'] += len(sport_data.get('teams', {}))
                
                # Rebuild name mapper from current data
                self.name_mapper.build_from_cache_data(self.cache_data)
                
                # For each sport, merge duplicate teams
                for sport_name, sport_data in self.cache_data['sports'].items():
                    teams = sport_data.get('teams', {})
                    team_names = list(teams.keys())
                    
                    # Find duplicates
                    merged = self.name_mapper.merge_duplicates(team_names)
                    
                    # Merge duplicate entries
                    for canonical, aliases in merged.items():
                        if not aliases:
                            continue
                        
                        canonical_data = teams[canonical]
                        
                        for alias in aliases:
                            if alias in teams and alias != canonical:
                                alias_data = teams[alias]
                                
                                # Merge aliases
                                canonical_data['aliases'].extend(alias_data.get('aliases', []))
                                canonical_data['aliases'] = list(set(canonical_data['aliases']))
                                
                                # Merge sources
                                canonical_data['sources'].extend(alias_data.get('sources', []))
                                canonical_data['sources'] = list(set(canonical_data['sources']))
                                
                                # Sum match counts
                                canonical_data['match_count'] += alias_data.get('match_count', 0)
                                
                                # Remove duplicate
                                del teams[alias]
                                summary['duplicates_merged'] += 1
                
                # Count teams after
                for sport_data in self.cache_data['sports'].values():
                    summary['teams_after'] += len(sport_data.get('teams', {}))
                
                # Update metadata
                self.cache_data['metadata']['dedup_stats']['duplicates_merged'] += summary['duplicates_merged']
                self.cache_data['metadata']['dedup_stats']['last_cleanup'] = datetime.now().isoformat()
                
                # Rebuild indices
                self._rebuild_indices()
                
                # Save
                self.save_cache()
                self.save_mappings()
                
                print(f"[OK] Cleanup complete: {summary['duplicates_merged']} duplicates merged, "
                      f"{summary['teams_before']} -> {summary['teams_after']} teams")
                
                return summary
                
            except Exception as e:
                print(f"[ERROR] Cleanup failed: {e}")
                summary['error'] = str(e)
                return summary
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        mapper_stats = self.name_mapper.get_mapping_stats()
        
        return {
            'cache_version': self.cache_data['version'],
            'total_sports': len(self.cache_data['sports']),
            'total_teams': self.cache_data['metadata']['total_teams'],
            'total_aliases': self.cache_data['metadata']['total_aliases'],
            'mapper_canonical_names': mapper_stats['canonical_names'],
            'mapper_total_aliases': mapper_stats['total_aliases'],
            'dedup_stats': self.cache_data['metadata']['dedup_stats'],
            'last_updated': self.cache_data['metadata']['last_updated']
        }


if __name__ == "__main__":
    print("=" * 80)
    print("ENHANCED CACHE MANAGER - Testing")
    print("=" * 80)
    
    manager = EnhancedCacheManager()
    
    # Test standardization
    print("\n" + "=" * 80)
    print("TEAM NAME STANDARDIZATION TEST")
    print("=" * 80)
    
    test_teams = [
        ("Man City", "soccer"),
        ("Manchester City", "soccer"),
        ("Manchester City FC", "soccer"),
        ("Man City (W)", "soccer"),
        ("Lakers", "basketball"),
        ("LA Lakers", "basketball"),
        ("Los Angeles Lakers", "basketball"),
    ]
    
    for team, sport in test_teams:
        canonical, created = manager.add_or_update_team(sport, team, source="test")
        status = "NEW" if created else "EXISTING"
        print(f"{status:10} | {sport:15} | {team:30} -> {canonical}")
    
    # Show stats
    print("\n" + "=" * 80)
    print("CACHE STATISTICS")
    print("=" * 80)
    stats = manager.get_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")
    
    print("\n✅ Enhanced cache manager ready!")
