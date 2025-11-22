#!/usr/bin/env python3
"""
Unified Odds Collector - Combines Bet365, FanDuel, and 1xBet odds data
Creates a unified database where each match has odds from all bookmakers

TEAM NAME NORMALIZATION STRATEGY:
==================================
This module uses a two-tier approach for team name matching:

1. PRIMARY: Cache-based O(1) lookup (cache_data.json)
   - All team names are normalized to canonical format from cache
   - O(1) hash table lookup via normalized name (lowercase, no special chars)
   - Ensures consistent naming across all three sources
   - Example: "pakistan" -> "Pakistan", "new zealand breakers" -> "New Zealand Breakers"
   - NOW WITH AUTO-UPDATE: New teams are automatically added to cache

2. FALLBACK: Fuzzy string matching
   - Used only when team not found in cache (new teams, typos, etc.)
   - Uses SequenceMatcher for similarity comparison (threshold: 0.6)
   - Prevents system failure when cache doesn't have a team yet
   - Allows gradual cache building as new teams are discovered

WORKFLOW:
1. Load data from all sources (bet365, fanduel, 1xbet)
2. Normalize all team names using cache (normalize_match_teams)
3. Auto-update cache with new teams discovered
4. Match games using canonical names (exact match if in cache)
5. Fallback to fuzzy matching for unknown teams
6. Merge odds from all sources into unified structure

This ensures maximum accuracy for known teams while maintaining
robustness for new/unknown teams that haven't been added to cache yet.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import re
import threading
from pathlib import Path
from dynamic_cache_manager import DynamicCacheManager


class UnifiedOddsCollector:
    """Combines odds data from Bet365 and FanDuel into a unified database"""
    
    def __init__(self):
        # Paths to data sources
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Bet365 sources
        self.bet365_pregame_file = os.path.join(self.base_dir, "bet365", "bet365_current_pregame.json")
        self.bet365_live_file = os.path.join(self.base_dir, "bet365", "bet365_live_current.json")

        # FanDuel sources
        self.fanduel_pregame_file = os.path.join(self.base_dir, "fanduel", "fanduel_pregame.json")
        self.fanduel_live_file = os.path.join(self.base_dir, "fanduel", "fanduel_live.json")

        # 1xBet sources
        self.xbet_pregame_file = os.path.join(self.base_dir, "1xbet", "1xbet_pregame.json")
        self.xbet_live_file = os.path.join(self.base_dir, "1xbet", "1xbet_live.json")
        
        # Cache file (moved to parent directory)
        self.cache_file = os.path.join(self.base_dir, "cache_data.json")
        
        # Output file
        self.unified_output_file = os.path.join(self.base_dir, "unified_odds.json")
        
        # File write lock to prevent concurrent writes
        self.file_lock = threading.Lock()
        
        # Initialize dynamic cache manager for auto-updates
        self.cache_manager = DynamicCacheManager(Path(self.base_dir))
        
        # Load cache for O(1) team name lookups
        self.team_lookup_cache = {}  # normalized_name -> canonical_name
        self.sport_lookup_cache = {}  # normalized_sport -> canonical_sport
        self.load_cache()
        
        # Fallback cache for normalized team names (legacy)
        self.team_name_cache = {}
        
        # Sport name mapping (FanDuel -> Bet365 format, plus 1xBet mappings)
        self.sport_mapping = {
            'basketball': 'NBA',  # FanDuel uses 'basketball' for both NBA and NCAAB
            'football': 'NCAAF',  # Could also be NFL
            'ice-hockey': 'NHL',
            'soccer': 'soccer',
            'tennis': 'Tennis',
            'baseball': 'MLB',
            'mma': 'MMA',
            'cricket': 'cricket',
            # 1xBet sport mappings
            'football': 'soccer',  # 1xBet uses 'Football' for soccer
            'american football': 'NFL',  # 1xBet uses 'American Football' for NFL
            'ice hockey': 'NHL',  # 1xBet uses 'Ice Hockey' for NHL
            'basketball': 'NBA',  # 1xBet uses 'Basketball' for NBA
            'formula 1': 'Formula 1'  # 1xBet uses 'Formula 1'
        }
        
        # Special sport aliases - specific leagues/competitions that map to parent sports
        self.sport_aliases = {
            'UEFA Champions League': 'soccer',
            'EPL': 'soccer',
            'MLS': 'soccer',
            'NBA': 'basketball',
            'NCAAB': 'basketball'
        }
        
        # City abbreviation mappings (Bet365 -> Full name)
        self.city_abbreviations = {
            # NBA
            'atl': 'atlanta', 'bos': 'boston', 'bkn': 'brooklyn', 'cha': 'charlotte',
            'chi': 'chicago', 'cle': 'cleveland', 'dal': 'dallas', 'den': 'denver',
            'det': 'detroit', 'gs': 'golden state', 'gsw': 'golden state', 'hou': 'houston',
            'ind': 'indiana', 'lac': 'la clippers', 'lal': 'la lakers', 'mem': 'memphis',
            'mia': 'miami', 'mil': 'milwaukee', 'min': 'minnesota', 'no': 'new orleans',
            'nop': 'new orleans', 'ny': 'new york', 'nyk': 'new york', 'okc': 'oklahoma',
            'orl': 'orlando', 'phi': 'philadelphia', 'phx': 'phoenix', 'por': 'portland',
            'sac': 'sacramento', 'sa': 'san antonio', 'sas': 'san antonio', 'tor': 'toronto',
            'uta': 'utah', 'uth': 'utah', 'was': 'washington', 'wsh': 'washington',
            # NHL
            'ana': 'anaheim', 'ari': 'arizona', 'buf': 'buffalo', 'cgy': 'calgary',
            'car': 'carolina', 'cbj': 'columbus', 'col': 'colorado', 'edm': 'edmonton',
            'fla': 'florida', 'la': 'los angeles', 'min': 'minnesota', 'mtl': 'montreal',
            'nsh': 'nashville', 'nj': 'new jersey', 'njd': 'new jersey', 'nyi': 'ny islanders',
            'nyr': 'ny rangers', 'ott': 'ottawa', 'pit': 'pittsburgh', 'sea': 'seattle',
            'sj': 'san jose', 'stl': 'st louis', 'tb': 'tampa bay', 'tbl': 'tampa bay',
            'van': 'vancouver', 'vgk': 'vegas', 'wpg': 'winnipeg',
            # NFL
            'ari': 'arizona', 'atl': 'atlanta', 'bal': 'baltimore', 'buf': 'buffalo',
            'car': 'carolina', 'chi': 'chicago', 'cin': 'cincinnati', 'cle': 'cleveland',
            'dal': 'dallas', 'den': 'denver', 'det': 'detroit', 'gb': 'green bay',
            'hou': 'houston', 'ind': 'indianapolis', 'jax': 'jacksonville', 'kc': 'kansas',
            'lac': 'la chargers', 'lar': 'la rams', 'lv': 'las vegas', 'mia': 'miami',
            'min': 'minnesota', 'ne': 'new england', 'no': 'new orleans', 'nyg': 'ny giants',
            'nyj': 'ny jets', 'phi': 'philadelphia', 'pit': 'pittsburgh', 'sea': 'seattle',
            'sf': 'san francisco', 'tb': 'tampa bay', 'ten': 'tennessee', 'wsh': 'washington',
            # MLB
            'bal': 'baltimore', 'bos': 'boston', 'cws': 'chicago white sox', 'chc': 'chicago cubs',
            'cin': 'cincinnati', 'cle': 'cleveland', 'col': 'colorado', 'det': 'detroit',
            'hou': 'houston', 'kc': 'kansas', 'laa': 'la angels', 'lad': 'la dodgers',
            'mia': 'miami', 'mil': 'milwaukee', 'min': 'minnesota', 'nym': 'ny mets',
            'nyy': 'ny yankees', 'oak': 'oakland', 'phi': 'philadelphia', 'pit': 'pittsburgh',
            'sd': 'san diego', 'sea': 'seattle', 'sf': 'san francisco', 'stl': 'st louis',
            'tb': 'tampa bay', 'tex': 'texas', 'tor': 'toronto', 'wsh': 'washington',
        }
    
    def normalize_sport_name(self, sport: str) -> str:
        """
        Normalize sport names for matching between sources
        Uses cache lookup first, then falls back to manual mappings
        """
        if not sport:
            return ''
            
        sport_lower = sport.lower().strip()
        
        # PRIMARY: Try cache lookup first (O(1))
        normalized_sport = sport_lower
        normalized_sport = re.sub(r'[^\w\s]', '', normalized_sport)
        normalized_sport = re.sub(r'\s+', ' ', normalized_sport)
        
        canonical_sport = self.sport_lookup_cache.get(normalized_sport)
        if canonical_sport:
            return canonical_sport.lower()  # Return lowercase for matching

        # Check if it's a specific league/competition with an alias
        if sport in self.sport_aliases:
            return self.sport_aliases[sport]

        # Comprehensive sport normalization mapping
        sport_mappings = {
            # Basketball variations
            'basketball': 'basketball',
            'nba': 'basketball',
            'ncaab': 'basketball',
            'nba2k': 'basketball',
            'euroleague': 'basketball',
            
            # Football variations (American)
            'football': 'football',
            'american football': 'football',
            'nfl': 'football',
            'ncaaf': 'football',
            
            # Soccer variations
            'soccer': 'soccer',
            'ucl': 'soccer',
            'mls': 'soccer',
            'epl': 'soccer',
            
            # Hockey variations
            'hockey': 'hockey',
            'ice hockey': 'hockey',
            'nhl': 'hockey',
            'ice-hockey': 'hockey',
            
            # Tennis
            'tennis': 'tennis',
            
            # Baseball
            'baseball': 'baseball',
            'mlb': 'baseball',
            
            # MMA
            'mma': 'mma',
            'mixed martial arts': 'mma',
            'ufc': 'mma',
            
            # Cricket
            'cricket': 'cricket',
            
            # Golf
            'golf': 'golf',
            'pga': 'golf',
            
            # Motorsport
            'formula 1': 'motorsport',
            'f1': 'motorsport',
            'formula1': 'motorsport',
            
            # Darts
            'darts': 'darts',
            
            # Table tennis
            'table-tennis': 'table-tennis',
            'table tennis': 'table-tennis',
            'tabletennis': 'table-tennis',
        }
        
        normalized = sport_mappings.get(sport_lower, sport_lower)
        return normalized
    
    def get_canonical_sport_name(self, sport: str) -> str:
        """Get the canonical display name for a sport (for UI consistency)"""
        if not sport:
            return ''
        
        # Normalize first
        normalized = self.normalize_sport_name(sport)
        
        # Map to consistent display names
        display_names = {
            'basketball': 'Basketball',
            'football': 'Football',  # American Football
            'soccer': 'Soccer',
            'hockey': 'Hockey',
            'tennis': 'Tennis',
            'baseball': 'Baseball',
            'mma': 'MMA',
            'cricket': 'Cricket',
            'golf': 'Golf',
            'motorsport': 'Motorsport',
            'darts': 'Darts',
            'table-tennis': 'Table Tennis',
        }
        
        return display_names.get(normalized, normalized.title())

    def load_cache(self):
        """Load team name cache for O(1) lookups from hierarchical cache structure"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    # Load from new hierarchical structure
                    lookups = cache_data.get('lookups', {})
                    self.team_lookup_cache = lookups.get('team_alias_to_canonical', {})
                    self.sport_lookup_cache = lookups.get('sport_alias_to_canonical', {})
                    
                    print(f"✓ Loaded cache: {len(self.team_lookup_cache)} team aliases, {len(self.sport_lookup_cache)} sport aliases")
            else:
                print(f"⚠ Cache file not found: {self.cache_file}")
                print(f"  Run build_team_cache.py to create it")
        except Exception as e:
            print(f"⚠ Error loading cache: {e}")
    
    def get_canonical_team_name(self, team_name: str) -> str:
        """
        Get canonical team name using O(1) cache lookup
        First tries cache lookup, then returns original name if not found
        This ensures cache is primary, with fallback to original name
        """
        if not team_name:
            return team_name
        
        # Normalize the input (same normalization as build_team_cache.py)
        normalized = team_name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove special chars
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        
        # O(1) lookup in cache - PRIMARY METHOD
        canonical = self.team_lookup_cache.get(normalized)
        if canonical:
            return canonical
        
        # Fallback: return original if not in cache
        # This allows the fuzzy matching logic to still work for unknown teams
        return team_name
    
    def normalize_match_teams(self, match: Dict) -> Dict:
        """
        Normalize team names in a match to canonical names from cache.
        If team not in cache, keeps original name for fuzzy matching fallback.
        
        This ensures all matches use canonical names where possible,
        improving match accuracy across different sources.
        """
        if 'home_team' in match:
            original_home = match['home_team']
            canonical_home = self.get_canonical_team_name(original_home)
            match['home_team'] = canonical_home
            
            # Store original if different (for debugging)
            if canonical_home != original_home:
                match['home_team_original'] = original_home
        
        if 'away_team' in match:
            original_away = match['away_team']
            canonical_away = self.get_canonical_team_name(original_away)
            match['away_team'] = canonical_away
            
            # Store original if different (for debugging)
            if canonical_away != original_away:
                match['away_team_original'] = original_away
        
        return match
    
    def normalize_team_name(self, team: str) -> str:
        """Normalize team names for better matching with comprehensive abbreviation handling"""
        if team in self.team_name_cache:
            return self.team_name_cache[team]

        # Convert to lowercase and strip whitespace
        normalized = team.lower().strip()

        # First, expand city abbreviations using our comprehensive mapping
        words = normalized.split()
        expanded_words = []
        for word in words:
            # Remove punctuation from word for matching
            clean_word = word.replace('.', '').replace(',', '')
            if clean_word in self.city_abbreviations:
                # Expand abbreviation
                expanded = self.city_abbreviations[clean_word]
                expanded_words.append(expanded)
            else:
                expanded_words.append(word)
        
        normalized = ' '.join(expanded_words)

        # Remove common team suffixes/prefixes to get core name
        # For NBA/NFL/NHL: "warriors", "suns", "lakers", etc.
        # For soccer: "fc", "united", etc.
        common_words = r'\b(royale|fc|club|ac|as|sc|fk|tsg|sv|cf|ud|rc|ssc|efc|afc|bfc|ifk|aik|gif|hb|ob|rb|sg|st|fc|cd|cp|cs|gc|gs|js|ks|ls|ms|ns|ps|rs|ts|vs|ws|ys|saint|germain|eindhoven|munich|prague|frankfurt|madrid|barcelona|manchester|city|united|liverpool|chelsea|arsenal|tottenham|newcastle|brighton|wolves|palace|bournemouth|fulham|nottingham|sheffield|leicester|southampton|everton|west|ham|aston|villa|leeds|burnley|watford|norwich|cardiff|swansea|stoke|hull|middlesbrough|sunderland|bolton|blackburn|birmingham|derby|reading|millwall|brentford|luton|paris|g|stg)\b'
        normalized = re.sub(common_words, '', normalized)

        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', '', normalized)      # Remove all spaces for final comparison

        self.team_name_cache[team] = normalized
        return normalized
    
    def safe_load_json(self, filepath: str, max_retries: int = 3, retry_delay: float = 0.2) -> Optional[Dict]:
        """
        Safely load JSON file with retry logic to handle race conditions
        where file is being written while we try to read it
        """
        for attempt in range(max_retries):
            try:
                if not os.path.exists(filepath):
                    return None
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
                    
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    # File is being written, wait and retry
                    time.sleep(retry_delay)
                    continue
                else:
                    # Final attempt failed - file is corrupted
                    print(f"Error loading {os.path.basename(filepath)}: {e}")
                    print(f"  File appears to be corrupted. Attempting to load backup...")
                    
                    # Try to load from backup if it exists
                    backup_path = filepath.replace('.json', '.bak')
                    if os.path.exists(backup_path):
                        try:
                            with open(backup_path, 'r', encoding='utf-8') as f:
                                print(f"  Successfully loaded backup file")
                                return json.load(f)
                        except:
                            pass
                    
                    print(f"  Could not load {os.path.basename(filepath)}, continuing without this data source")
                    return None
            except Exception as e:
                # Other errors (file not found, permission, etc.)
                print(f"Error loading {os.path.basename(filepath)}: {e}")
                return None
        
        return None
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two team names (0-1 scale)"""
        norm1 = self.normalize_team_name(name1)
        norm2 = self.normalize_team_name(name2)
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def extract_date_time_from_game_id(self, game_id: str) -> Tuple[str, str]:
        """Extract date and time from game_id format and format like Bet365"""
        try:
            # game_id format: team1:team2:YYYYMMDD:HHMM
            from datetime import datetime
            parts = game_id.split(':')
            if len(parts) >= 4:
                date_str = parts[2]  # YYYYMMDD
                time_str = parts[3]  # HHMM
                
                # Parse date and format like "Mon Nov 03"
                dt = datetime.strptime(date_str, '%Y%m%d')
                formatted_date = dt.strftime('%a %b %d')  # "Mon Nov 03"
                
                # Parse time and format like "10:07 PM"
                hour = int(time_str[:2])
                minute = time_str[2:]
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                formatted_time = f"{display_hour}:{minute} {period}"
                
                return formatted_date, formatted_time
        except:
            pass
        return '', ''
    
    def parse_scheduled_time(self, scheduled_time: str) -> Tuple[str, str]:
        """Parse FanDuel's scheduled_time (ISO format) into Bet365-style date and time"""
        try:
            # scheduled_time format: "2025-11-04T20:00:00.000Z"
            from datetime import datetime
            dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            
            # Format like Bet365: "Mon Nov 03"
            date = dt.strftime('%a %b %d')
            
            # Format like Bet365: "10:07 PM"
            time = dt.strftime('%-I:%M %p') if hasattr(dt, 'strftime') else dt.strftime('%I:%M %p')
            # Remove leading zero from hour for consistency with Bet365
            time = time.lstrip('0')
            
            return date, time
        except:
            return '', ''
    
    def matches_are_same(self, match1: Dict, match2: Dict,
                          threshold: float = 0.6) -> bool:
        """
        Determine if two matches are the same based on sport, teams and time
        
        Strategy:
        1. First try O(1) cache lookup for canonical team names (PRIMARY)
        2. If cache lookup succeeds, compare canonical names directly
        3. If team not in cache, fallback to fuzzy string matching (FALLBACK)
        
        This ensures cache normalization is used first, with fuzzy matching
        only for teams not yet in the cache database.
        """

        # First check if sports match (normalized)
        sport1 = self.normalize_sport_name(match1.get('sport', ''))
        sport2 = self.normalize_sport_name(match2.get('sport', ''))

        # Sports must match after normalization
        if sport1 != sport2:
            return False

        # Extract teams
        home1 = match1.get('home_team', '')
        away1 = match1.get('away_team', '')
        home2 = match2.get('home_team', '')
        away2 = match2.get('away_team', '')
        
        # PRIMARY: Try O(1) cache lookup for canonical names
        home1_canonical = self.get_canonical_team_name(home1)
        away1_canonical = self.get_canonical_team_name(away1)
        home2_canonical = self.get_canonical_team_name(home2)
        away2_canonical = self.get_canonical_team_name(away2)
        
        # If both teams were found in cache, use exact canonical comparison
        home1_in_cache = home1_canonical != home1  # Changed from original
        away1_in_cache = away1_canonical != away1
        home2_in_cache = home2_canonical != home2
        away2_in_cache = away2_canonical != away2
        
        # If all teams are in cache, use exact canonical match
        if home1_in_cache and away1_in_cache and home2_in_cache and away2_in_cache:
            # Exact match via cache
            if (home1_canonical == home2_canonical and away1_canonical == away2_canonical):
                return True
            
            # Check reversed (sometimes home/away are flipped)
            if (home1_canonical == away2_canonical and away1_canonical == home2_canonical):
                return True
            
            # Both in cache but don't match - they're different teams
            return False
        
        # FALLBACK: Use fuzzy matching if any team is not in cache
        # This handles new teams that haven't been added to cache yet
        home_similarity = self.calculate_name_similarity(home1, home2)
        away_similarity = self.calculate_name_similarity(away1, away2)

        # Average similarity
        avg_similarity = (home_similarity + away_similarity) / 2

        # Check if similarity is above threshold (lowered from 0.75 to 0.6)
        if avg_similarity >= threshold:
            return True

        # Also check reversed (sometimes home/away are flipped)
        home_similarity_rev = self.calculate_name_similarity(home1, away2)
        away_similarity_rev = self.calculate_name_similarity(away1, home2)
        avg_similarity_rev = (home_similarity_rev + away_similarity_rev) / 2

        return avg_similarity_rev >= threshold
    
    def load_bet365_pregame(self) -> List[Dict]:
        """Load Bet365 pregame data"""
        try:
            data = self.safe_load_json(self.bet365_pregame_file)
            if data is None:
                print(f"Warning: Bet365 pregame file not found: {self.bet365_pregame_file}")
                return []
            
            matches = []
            
            # Bet365 pregame structure has sports_data with games per sport
            if 'sports_data' in data:
                for sport, sport_data in data['sports_data'].items():
                    games = sport_data.get('games', [])
                    for game in games:
                        # Standardize to our unified format
                        match = {
                            'sport': game.get('sport', sport),
                            'home_team': game.get('team1', ''),
                            'away_team': game.get('team2', ''),
                            'date': game.get('date', ''),
                            'time': game.get('time', ''),
                            'game_id': game.get('game_id', ''),
                            'fixture_id': game.get('fixture_id', ''),
                            'source': 'bet365',
                            'is_live': False,
                            'raw_data': game
                        }
                        matches.append(match)
            
            print(f"Loaded {len(matches)} pregame matches from Bet365")
            return matches

        except Exception as e:
            print(f"Error loading Bet365 pregame data: {e}")
            return []
    
    def load_bet365_live(self) -> List[Dict]:
        """Load Bet365 live data"""
        try:
            data = self.safe_load_json(self.bet365_live_file)
            if data is None:
                print(f"Warning: Bet365 live file not found: {self.bet365_live_file}")
                return []
            
            matches = []
            live_matches_data = data.get('matches', [])
            
            for match_data in live_matches_data:
                # Extract teams from match data
                teams = match_data.get('teams', {})
                
                match = {
                    'sport': match_data.get('sport', ''),
                    'home_team': teams.get('home', ''),
                    'away_team': teams.get('away', ''),
                    'date': '',  # Live matches don't have scheduled date
                    'time': '',
                    'game_id': '',  # Will generate if needed
                    'source': 'bet365',
                    'is_live': True,
                    'raw_data': match_data
                }
                matches.append(match)
            
            print(f"Loaded {len(matches)} live matches from Bet365")
            return matches
            
        except Exception as e:
            print(f"Error loading Bet365 live data: {e}")
            return []
    
    def load_fanduel_pregame(self) -> List[Dict]:
        """Load FanDuel pregame data"""
        try:
            data = self.safe_load_json(self.fanduel_pregame_file)
            if data is None:
                print(f"Warning: FanDuel pregame file not found: {self.fanduel_pregame_file}")
                return []
            
            matches = []
            fanduel_matches = data.get('data', {}).get('matches', [])
            
            for match_data in fanduel_matches:
                # Extract date and time from scheduled_time
                scheduled_time = match_data.get('scheduled_time', '')
                date, time = self.parse_scheduled_time(scheduled_time)
                
                # Fallback to game_id if scheduled_time parsing failed
                if not date or not time:
                    game_id = match_data.get('game_id', '')
                    date, time = self.extract_date_time_from_game_id(game_id)
                
                match = {
                    'sport': match_data.get('sport', ''),
                    'home_team': match_data.get('home_team', ''),
                    'away_team': match_data.get('away_team', ''),
                    'date': date,
                    'time': time,
                    'game_id': match_data.get('game_id', ''),
                    'match_id': match_data.get('match_id', ''),
                    'source': 'fanduel',
                    'is_live': match_data.get('status') == 'live',
                    'raw_data': match_data
                }
                matches.append(match)
            
            print(f"Loaded {len(matches)} pregame matches from FanDuel")
            return matches
            
        except Exception as e:
            print(f"Error loading FanDuel pregame data: {e}")
            return []
    
    def load_fanduel_live(self) -> List[Dict]:
        """Load FanDuel live data"""
        try:
            data = self.safe_load_json(self.fanduel_live_file)
            if data is None:
                print(f"Warning: FanDuel live file not found: {self.fanduel_live_file}")
                return []
            
            matches = []
            fanduel_live_matches = data.get('matches', [])
            
            for match_data in fanduel_live_matches:
                match = {
                    'sport': match_data.get('sport', ''),
                    'home_team': match_data.get('home_team', ''),
                    'away_team': match_data.get('away_team', ''),
                    'date': '',
                    'time': '',
                    'game_id': match_data.get('game_id', ''),
                    'event_id': match_data.get('event_id', ''),
                    'source': 'fanduel',
                    'is_live': True,
                    'raw_data': match_data
                }
                matches.append(match)
            
            print(f"Loaded {len(matches)} live matches from FanDuel")
            return matches
            
        except Exception as e:
            print(f"Error loading FanDuel live data: {e}")
            return []
    
    def load_1xbet_pregame(self) -> List[Dict]:
        """Load 1xBet pregame data"""
        try:
            data = self.safe_load_json(self.xbet_pregame_file)
            if data is None:
                print(f"Warning: 1xBet pregame file not found: {self.xbet_pregame_file}")
                return []

            matches = []
            xbet_matches = data.get('data', {}).get('matches', [])

            for match_data in xbet_matches:
                # Extract date and time from scheduled_time
                scheduled_time = match_data.get('scheduled_time', '')
                date, time = self.parse_scheduled_time(scheduled_time)

                # Special handling for 1xBet sport names
                sport_name = match_data.get('sport_name', '')
                
                # 1xBet uses "Football" for soccer, "American Football" for NFL
                if sport_name == 'Football':
                    normalized_sport = 'soccer'
                elif sport_name == 'American Football':
                    normalized_sport = 'football'
                else:
                    normalized_sport = self.normalize_sport_name(sport_name)

                match = {
                    'sport': normalized_sport,  # Use normalized sport name
                    'home_team': match_data.get('team1', ''),
                    'away_team': match_data.get('team2', ''),
                    'date': date,
                    'time': time,
                    'game_id': str(match_data.get('match_id', '')),
                    'match_id': match_data.get('match_id', ''),
                    'source': '1xbet',
                    'is_live': False,
                    'raw_data': match_data
                }
                matches.append(match)

            print(f"Loaded {len(matches)} pregame matches from 1xBet")
            return matches

        except Exception as e:
            print(f"Error loading 1xBet pregame data: {e}")
            return []
    
    def load_1xbet_live(self) -> List[Dict]:
        """Load 1xBet live data"""
        try:
            data = self.safe_load_json(self.xbet_live_file)
            if data is None:
                print(f"Warning: 1xBet live file not found: {self.xbet_live_file}")
                return []

            matches = []
            # Get matches directly from root
            xbet_live_matches = data.get('matches', [])

            for match_data in xbet_live_matches:
                # Special handling for 1xBet sport names
                sport_name = match_data.get('sport_name', '')
                
                # 1xBet uses "Football" for soccer, "American Football" for NFL
                if sport_name == 'Football':
                    normalized_sport = 'soccer'
                elif sport_name == 'American Football':
                    normalized_sport = 'football'
                else:
                    normalized_sport = self.normalize_sport_name(sport_name)

                match = {
                    'sport': normalized_sport,  # Use normalized sport name
                    'home_team': match_data.get('team1', ''),
                    'away_team': match_data.get('team2', ''),
                    'date': '',
                    'time': match_data.get('time', ''),
                    'game_id': str(match_data.get('match_id', '')),
                    'match_id': match_data.get('match_id', ''),
                    'source': '1xbet',
                    'is_live': True,
                    'raw_data': match_data
                }
                matches.append(match)

            print(f"Loaded {len(matches)} live matches from 1xBet")
            return matches

        except Exception as e:
            print(f"Error loading 1xBet live data: {e}")
            return []
    
    def extract_bet365_odds(self, match_data: Dict) -> Dict:
        """Extract odds from Bet365 match data"""
        # For live matches, odds are in 'markets' field
        if 'markets' in match_data:
            markets = match_data.get('markets', {})
            
            extracted = {}
            
            # Moneyline
            if 'moneyline' in markets:
                ml = markets['moneyline']
                extracted['moneyline'] = [
                    ml.get('home', {}).get('odds', ''),
                    ml.get('away', {}).get('odds', '')
                ]
            
            # Spread/Handicap
            if 'handicap' in markets:
                hc = markets['handicap']
                extracted['spread'] = [
                    hc.get('home', {}).get('odds', ''),
                    hc.get('away', {}).get('odds', '')
                ]
            
            # Total
            if 'total' in markets:
                total = markets['total']
                over_line = total.get('over', {}).get('line', '')
                under_line = total.get('under', {}).get('line', '')
                extracted['total'] = [
                    f"{over_line} {total.get('over', {}).get('odds', '')}",
                    f"{under_line} {total.get('under', {}).get('odds', '')}"
                ]
            
            return extracted
        
        # For pregame matches, odds are in 'odds' field
        odds_data = match_data.get('odds', {})
        
        # Bet365 odds structure varies by sport
        extracted = {
            'spread': odds_data.get('spread', []),
            'total': odds_data.get('total', []),
            'moneyline': odds_data.get('moneyline', []),
            'runline': odds_data.get('runline', []),
            'puckline': odds_data.get('puckline', [])
        }
        
        return extracted
    
    def extract_fanduel_odds(self, match_data: Dict) -> Dict:
        """Extract odds from FanDuel match data"""
        # For pregame matches, odds are in 'odds' field
        odds_data = match_data.get('odds', {})
        
        # For live matches, odds are in 'odds_data' field
        if not odds_data and 'odds_data' in match_data:
            odds_data_dict = match_data.get('odds_data', {})
            
            # Extract from FanDuel live structure
            extracted = {}
            
            # Moneyline
            if 'Moneyline' in odds_data_dict:
                moneyline_odds = odds_data_dict['Moneyline'].get('odds', {})
                for selection_id, selection in moneyline_odds.items():
                    if 'Home' in selection.get('name', '') or selection.get('name', '') == match_data.get('home_team', ''):
                        extracted['moneyline_home'] = selection.get('american_odds')
                    elif 'Away' in selection.get('name', '') or selection.get('name', '') == match_data.get('away_team', ''):
                        extracted['moneyline_away'] = selection.get('american_odds')
                    elif 'Draw' in selection.get('name', ''):
                        extracted['moneyline_draw'] = selection.get('american_odds')
            
            # Spread
            if 'Spread' in odds_data_dict:
                spread_odds = odds_data_dict['Spread'].get('odds', {})
                for selection_id, selection in spread_odds.items():
                    if 'Home' in selection.get('name', '') or selection.get('name', '') == match_data.get('home_team', ''):
                        extracted['spread_home_line'] = selection.get('handicap')
                        extracted['spread_home_odds'] = selection.get('american_odds')
                    elif 'Away' in selection.get('name', '') or selection.get('name', '') == match_data.get('away_team', ''):
                        extracted['spread_away_line'] = selection.get('handicap')
                        extracted['spread_away_odds'] = selection.get('american_odds')
            
            # Total
            for key in odds_data_dict:
                if 'Total' in key or 'Over/Under' in key:
                    total_odds = odds_data_dict[key].get('odds', {})
                    for selection_id, selection in total_odds.items():
                        if 'Over' in selection.get('name', ''):
                            extracted['total_line'] = selection.get('handicap')
                            extracted['total_over_odds'] = selection.get('american_odds')
                        elif 'Under' in selection.get('name', ''):
                            if 'total_line' not in extracted:
                                extracted['total_line'] = selection.get('handicap')
                            extracted['total_under_odds'] = selection.get('american_odds')
                    break
            
            return extracted
        
        # Pregame structure - FanDuel has structured odds
        extracted = {
            'moneyline_home': odds_data.get('moneyline_home'),
            'moneyline_away': odds_data.get('moneyline_away'),
            'moneyline_draw': odds_data.get('moneyline_draw'),  # Soccer specific
            'spread_home_line': odds_data.get('spread_home_line'),
            'spread_home_odds': odds_data.get('spread_home_odds'),
            'spread_away_line': odds_data.get('spread_away_line'),
            'spread_away_odds': odds_data.get('spread_away_odds'),
            'total_line': odds_data.get('total_line'),
            'total_over_odds': odds_data.get('total_over_odds'),
            'total_under_odds': odds_data.get('total_under_odds')
        }
        
        return extracted
    
    def extract_1xbet_odds(self, match_data: Dict) -> Dict:
        """Extract odds from 1xBet match data"""
        # 1xBet uses 'odds_data' field in pregame and 'odds' in live
        odds_data = match_data.get('odds_data', {}) or match_data.get('odds', {})
        
        # 1xBet odds structure
        extracted = {
            'moneyline_home': odds_data.get('moneyline_home'),
            'moneyline_draw': odds_data.get('moneyline_draw'),
            'moneyline_away': odds_data.get('moneyline_away'),
            'spread_home': odds_data.get('spread_home'),
            'spread_away': odds_data.get('spread_away'),
            'total_over': odds_data.get('sets_over') or odds_data.get('total_over'),
            'total_under': odds_data.get('sets_under') or odds_data.get('total_under')
        }
        
        return extracted
    
    def merge_pregame_data(self, bet365_matches: List[Dict],
                           fanduel_matches: List[Dict],
                           xbet_matches: List[Dict]) -> List[Dict]:
        """
        DYNAMIC MERGE: Handles any number of bookmakers dynamically
        
        This function uses a dynamic bookmaker registration system that automatically
        handles matching and merging for any number of bookmakers. Adding a new bookmaker
        requires minimal code changes.
        
        Strategy:
        1. Normalize all team names to canonical names from cache (PRIMARY)
        2. Use exact matching for teams in cache
        3. Fallback to fuzzy matching for teams not in cache (FALLBACK)
        4. Dynamically find all pairwise matches between bookmakers
        5. Group related matches across all bookmakers using Union-Find algorithm
        6. Create unified records with odds from all available bookmakers
        
        How to add a new bookmaker:
        1. Create a loader function (e.g., load_draftkings_pregame())
        2. Create an odds extractor (e.g., extract_draftkings_odds())
        3. Add the bookmaker to the 'bookmakers' dict in this function:
           'draftkings': {
               'matches': [self.normalize_match_teams(m) for m in draftkings_matches],
               'extract_odds': self.extract_draftkings_odds,
               'extra_fields': lambda m: {'match_id': m.get('match_id', '')}
           }
        4. That's it! The matching logic will automatically include the new bookmaker.
        
        Args:
            bet365_matches: List of Bet365 match dictionaries
            fanduel_matches: List of FanDuel match dictionaries
            xbet_matches: List of 1xBet match dictionaries
        
        Returns:
            List of unified match dictionaries with odds from all bookmakers
        """
        # STEP 1: Build dynamic bookmaker registry
        bookmakers = {
            'bet365': {
                'matches': [self.normalize_match_teams(m) for m in bet365_matches],
                'extract_odds': self.extract_bet365_odds,
                'extra_fields': lambda m: {'fixture_id': m.get('fixture_id', '')}
            },
            'fanduel': {
                'matches': [self.normalize_match_teams(m) for m in fanduel_matches],
                'extract_odds': self.extract_fanduel_odds,
                'extra_fields': lambda m: {'match_id': m.get('match_id', ''), 'game_id': m.get('game_id', '')}
            },
            '1xbet': {
                'matches': [self.normalize_match_teams(m) for m in xbet_matches],
                'extract_odds': self.extract_1xbet_odds,
                'extra_fields': lambda m: {'match_id': m.get('match_id', ''), 'game_id': m.get('game_id', '')}
            }
        }
        
        # NOTE: To add a new bookmaker, simply add a new entry to the bookmakers dict above
        # Example:
        # 'draftkings': {
        #     'matches': [self.normalize_match_teams(m) for m in draftkings_matches],
        #     'extract_odds': self.extract_draftkings_odds,
        #     'extra_fields': lambda m: {'match_id': m.get('match_id', '')}
        # }
        
        print(f"\n🔄 Normalizing team names to canonical format...")
        
        # Print match counts per bookmaker
        bookmaker_names = list(bookmakers.keys())
        match_counts = {name: len(bookmakers[name]['matches']) for name in bookmaker_names}
        print(f"\nMatching {', '.join([f'{count} {name}' for name, count in match_counts.items()])} matches...")
        
        # STEP 2: Find all pairwise matches dynamically
        print("\n🔍 Finding pairwise matches between all bookmakers...")
        pairwise_matches = {}  # Key: (bookmaker1, bookmaker2), Value: [(idx1, idx2), ...]
        matched_indices = {name: set() for name in bookmaker_names}  # Track matched indices per bookmaker
        
        def find_matches(matches1, matches2, threshold=0.6):
            """Generator to find matching pairs"""
            for i, match1 in enumerate(matches1):
                for j, match2 in enumerate(matches2):
                    if self.matches_are_same(match1, match2, threshold=threshold):
                        yield (i, j)
        
        # Find all unique pairs of bookmakers
        for i, name1 in enumerate(bookmaker_names):
            for name2 in bookmaker_names[i+1:]:
                print(f"  Finding {name1} + {name2} matches...")
                matches1 = bookmakers[name1]['matches']
                matches2 = bookmakers[name2]['matches']
                pairs = list(find_matches(matches1, matches2, 0.6))
                pairwise_matches[(name1, name2)] = pairs
                print(f"    Found {len(pairs)} matches")
        
        # STEP 3: Build match groups (clusters of related matches across bookmakers)
        print("\n🔗 Building match groups across all bookmakers...")
        match_groups = []  # Each group is a dict: {bookmaker_name: match_index}
        
        # Use Union-Find algorithm to group related matches
        from collections import defaultdict
        parent = {}  # (bookmaker, index) -> parent (bookmaker, index)
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Union all matching pairs
        for (name1, name2), pairs in pairwise_matches.items():
            for idx1, idx2 in pairs:
                union((name1, idx1), (name2, idx2))
        
        # Group matches by their root parent
        groups_dict = defaultdict(dict)
        for (bookmaker, idx) in parent.keys():
            root = find((bookmaker, idx))
            groups_dict[root][bookmaker] = idx
        
        # Convert to list and mark indices as matched
        for group in groups_dict.values():
            if len(group) > 0:  # Only include groups with at least one bookmaker
                match_groups.append(group)
                for bookmaker, idx in group.items():
                    matched_indices[bookmaker].add(idx)
        
        print(f"  Found {len(match_groups)} unique match groups")
        
        # Count matches by number of bookmakers
        multi_bookmaker_groups = [g for g in match_groups if len(g) >= 2]
        all_bookmaker_groups = [g for g in match_groups if len(g) == len(bookmaker_names)]
        print(f"  Matches with 2+ bookmakers: {len(multi_bookmaker_groups)}")
        print(f"  Matches with all {len(bookmaker_names)} bookmakers: {len(all_bookmaker_groups)}")
        
        # STEP 4: Create unified match records
        print("\n📦 Creating unified match records...")
        unified_matches = []
        
        for group in match_groups:
            # Use the first available bookmaker as the primary source for match details
            primary_bookmaker = bookmaker_names[0] if bookmaker_names[0] in group else list(group.keys())[0]
            primary_idx = group[primary_bookmaker]
            primary_match = bookmakers[primary_bookmaker]['matches'][primary_idx]
            
            # Get canonical sport name
            canonical_sport = self.get_canonical_sport_name(primary_match['sport'])
            
            # Build unified match with all bookmakers
            unified_match = {
                'sport': canonical_sport,
                'home_team': primary_match['home_team'],
                'away_team': primary_match['away_team'],
                'date': primary_match['date'],
                'time': primary_match['time'],
                'game_id': primary_match['game_id'],
                'is_live': False
            }
            
            # Add odds from each bookmaker (dynamically)
            for bookmaker_name in bookmaker_names:
                if bookmaker_name in group:
                    # Bookmaker has this match
                    idx = group[bookmaker_name]
                    match_data = bookmakers[bookmaker_name]['matches'][idx]
                    odds = bookmakers[bookmaker_name]['extract_odds'](match_data['raw_data'])
                    extra = bookmakers[bookmaker_name]['extra_fields'](match_data)
                    
                    unified_match[bookmaker_name] = {
                        'available': True,
                        'odds': odds,
                        **extra
                    }
                else:
                    # Bookmaker doesn't have this match
                    unified_match[bookmaker_name] = {
                        'available': False,
                        'odds': {}
                    }
            
            unified_matches.append(unified_match)
        
        # Add unmatched singles (matches that appear in only one bookmaker)
        print("\n➕ Adding unmatched singles...")
        for bookmaker_name in bookmaker_names:
            unmatched_count = 0
            for idx, match_data in enumerate(bookmakers[bookmaker_name]['matches']):
                if idx not in matched_indices[bookmaker_name]:
                    # This match wasn't matched with any other bookmaker
                    canonical_sport = self.get_canonical_sport_name(match_data['sport'])
                    
                    unified_match = {
                        'sport': canonical_sport,
                        'home_team': match_data['home_team'],
                        'away_team': match_data['away_team'],
                        'date': match_data['date'],
                        'time': match_data['time'],
                        'game_id': match_data['game_id'],
                        'is_live': False
                    }
                    
                    # Add this bookmaker's odds
                    odds = bookmakers[bookmaker_name]['extract_odds'](match_data['raw_data'])
                    extra = bookmakers[bookmaker_name]['extra_fields'](match_data)
                    unified_match[bookmaker_name] = {
                        'available': True,
                        'odds': odds,
                        **extra
                    }
                    
                    # Mark all other bookmakers as unavailable
                    for other_name in bookmaker_names:
                        if other_name != bookmaker_name:
                            unified_match[other_name] = {
                                'available': False,
                                'odds': {}
                            }
                    
                    unified_matches.append(unified_match)
                    unmatched_count += 1
            
            if unmatched_count > 0:
                print(f"  Added {unmatched_count} unmatched {bookmaker_name} matches")

        print(f"\n✅ Pregame Summary:")
        print(f"   Total unified matches: {len(unified_matches)}")
        print(f"   Matches with all {len(bookmaker_names)} bookmakers: {len(all_bookmaker_groups)}")
        print(f"   Matches with 2+ bookmakers: {len(multi_bookmaker_groups)}")

        return unified_matches
    
    def extract_live_score(self, match_data: Dict, source: str) -> Dict:
        """Extract score information from live match data for UI display"""
        score_info = {
            'home_score': None,
            'away_score': None,
            'period': None,
            'time_remaining': None,
            'status': 'Live'
        }
        
        if source == 'bet365':
            raw = match_data.get('raw_data', {})
            
            # Extract scores
            scores = raw.get('scores', {})
            if scores:
                score_info['home_score'] = scores.get('home', '')
                score_info['away_score'] = scores.get('away', '')
            
            # Extract period/time info
            score_info['period'] = raw.get('period', '')
            score_info['status'] = raw.get('status', 'Live')
            
            # Extract time remaining - check multiple locations
            live_fields = raw.get('live_fields', {})
            time_remaining = live_fields.get('time_remaining', '') or raw.get('time', '')
            score_info['time_remaining'] = time_remaining if time_remaining and time_remaining.lower() != 'live' else ''
            
            # For set-based sports, also include set scores
            sets_scores = raw.get('sets_scores', {})
            if sets_scores:
                score_info['sets'] = {
                    'home': sets_scores.get('home', ''),
                    'away': sets_scores.get('away', ''),
                    'points_home': sets_scores.get('points_home', ''),
                    'points_away': sets_scores.get('points_away', '')
                }
        
        elif source == 'fanduel':
            raw = match_data.get('raw_data', {})
            
            # Extract scores from FanDuel structure
            score = raw.get('score', {})
            if score:
                score_info['home_score'] = score.get('home')
                score_info['away_score'] = score.get('away')
            
            # Extract game state
            game_state = raw.get('game_state', {})
            if game_state:
                score_info['period'] = game_state.get('period', '')
                score_info['time_remaining'] = game_state.get('clock', '')
                score_info['status'] = game_state.get('status', 'Live')
        
        elif source == '1xbet':
            raw = match_data.get('raw_data', {})
            
            # Extract scores from 1xBet structure (uses score1/score2)
            score_info['home_score'] = str(raw.get('score1', '')) if raw.get('score1') is not None else None
            score_info['away_score'] = str(raw.get('score2', '')) if raw.get('score2') is not None else None
            score_info['period'] = raw.get('period', '')
            score_info['time_remaining'] = raw.get('time', '')
            score_info['status'] = 'Live'
            
            # Extract detailed score data (period-by-period and statistics)
            detailed_score = raw.get('detailed_score', {})
            if detailed_score:
                # Extract period-by-period scores
                periods = detailed_score.get('periods', [])
                if periods:
                    score_info['periods'] = periods
                
                # Extract statistics
                statistics = detailed_score.get('statistics', [])
                if statistics:
                    score_info['statistics'] = statistics
        
        return score_info
    
    def merge_live_data(self, bet365_matches: List[Dict], 
                        fanduel_matches: List[Dict],
                        xbet_matches: List[Dict]) -> List[Dict]:
        """
        Merge live matches from all three bookmakers
        
        Strategy:
        1. Normalize all team names to canonical names from cache (PRIMARY)
        2. Use exact matching for teams in cache
        3. Fallback to fuzzy matching for teams not in cache (FALLBACK)
        """
        # STEP 1: Normalize all team names to canonical names from cache
        print(f"\n🔄 Normalizing team names to canonical format...")
        bet365_matches = [self.normalize_match_teams(m) for m in bet365_matches]
        fanduel_matches = [self.normalize_match_teams(m) for m in fanduel_matches]
        xbet_matches = [self.normalize_match_teams(m) for m in xbet_matches]
        
        unified_matches = []
        matched_fanduel_indices = set()
        matched_xbet_indices = set()
        
        print(f"\n Matching {len(bet365_matches)} Bet365, {len(fanduel_matches)} FanDuel, and {len(xbet_matches)} 1xBet live matches...")
        
        # Try to match each Bet365 live match with FanDuel and 1xBet
        for bet365_match in bet365_matches:
            # Use canonical sport name for consistency
            canonical_sport = self.get_canonical_sport_name(bet365_match['sport'])
            
            # Extract score information for easy UI access
            score_info = self.extract_live_score(bet365_match, 'bet365')
            
            # For live matches, use "Live" as date and show time/status
            match_date = 'Live'
            match_time = score_info.get('time_remaining') or score_info.get('period') or 'In Progress'
            
            unified_match = {
                'sport': canonical_sport,  # Use canonical name for UI consistency
                'home_team': bet365_match['home_team'],
                'away_team': bet365_match['away_team'],
                'date': match_date,
                'time': match_time,
                'is_live': True,
                'score': score_info,  # Add score at top level for UI
                'bet365': {
                    'available': True,
                    'live_data': bet365_match['raw_data'],
                    'odds': self.extract_bet365_odds(bet365_match['raw_data'])
                },
                'fanduel': {
                    'available': False,
                    'live_data': {},
                    'odds': {}
                },
                '1xbet': {
                    'available': False,
                    'live_data': {},
                    'odds': {}
                }
            }
            
            # Try to find matching FanDuel match
            best_fanduel_idx = None
            best_fanduel_sim = 0.0
            
            for idx, fanduel_match in enumerate(fanduel_matches):
                if idx in matched_fanduel_indices:
                    continue
                
                if self.matches_are_same(bet365_match, fanduel_match):
                    home_sim = self.calculate_name_similarity(
                        bet365_match['home_team'], 
                        fanduel_match['home_team']
                    )
                    away_sim = self.calculate_name_similarity(
                        bet365_match['away_team'], 
                        fanduel_match['away_team']
                    )
                    avg_sim = (home_sim + away_sim) / 2
                    
                    if avg_sim > best_fanduel_sim:
                        best_fanduel_sim = avg_sim
                        best_fanduel_idx = idx
            
            # Try to find matching 1xBet match
            best_xbet_idx = None
            best_xbet_sim = 0.0
            
            for idx, xbet_match in enumerate(xbet_matches):
                if idx in matched_xbet_indices:
                    continue
                
                if self.matches_are_same(bet365_match, xbet_match):
                    home_sim = self.calculate_name_similarity(
                        bet365_match['home_team'], 
                        xbet_match['home_team']
                    )
                    away_sim = self.calculate_name_similarity(
                        bet365_match['away_team'], 
                        xbet_match['away_team']
                    )
                    avg_sim = (home_sim + away_sim) / 2
                    
                    if avg_sim > best_xbet_sim:
                        best_xbet_sim = avg_sim
                        best_xbet_idx = idx
            
            # Add FanDuel match if found
            if best_fanduel_idx is not None:
                fanduel_match = fanduel_matches[best_fanduel_idx]
                matched_fanduel_indices.add(best_fanduel_idx)
                
                unified_match['fanduel'] = {
                    'available': True,
                    'live_data': fanduel_match['raw_data'],
                    'odds': self.extract_fanduel_odds(fanduel_match['raw_data'])
                }
                
                # Update score info with FanDuel data (if available and more complete)
                fanduel_score_info = self.extract_live_score(fanduel_match, 'fanduel')
                if not score_info['home_score'] and fanduel_score_info['home_score']:
                    score_info = fanduel_score_info
            
            # Add 1xBet match if found
            if best_xbet_idx is not None:
                xbet_match = xbet_matches[best_xbet_idx]
                matched_xbet_indices.add(best_xbet_idx)
                
                unified_match['1xbet'] = {
                    'available': True,
                    'live_data': xbet_match['raw_data'],
                    'odds': self.extract_1xbet_odds(xbet_match['raw_data'])
                }
                
                # Update score info with 1xBet data (if not already set)
                xbet_score_info = self.extract_live_score(xbet_match, '1xbet')
                if not score_info['home_score'] and xbet_score_info['home_score']:
                    score_info = xbet_score_info
            
            unified_matches.append(unified_match)
        
        # Add unmatched FanDuel live matches
        for idx, fanduel_match in enumerate(fanduel_matches):
            if idx not in matched_fanduel_indices:
                canonical_sport = self.get_canonical_sport_name(fanduel_match['sport'])
                score_info = self.extract_live_score(fanduel_match, 'fanduel')
                
                # Use Live as date and extract time from score info
                match_time = score_info.get('time_remaining') or score_info.get('period') or 'In Progress'
                
                unified_match = {
                    'sport': canonical_sport,
                    'home_team': fanduel_match['home_team'],
                    'away_team': fanduel_match['away_team'],
                    'date': 'Live',
                    'time': match_time,
                    'is_live': True,
                    'score': score_info,
                    'bet365': {
                        'available': False,
                        'live_data': {},
                        'odds': {}
                    },
                    'fanduel': {
                        'available': True,
                        'live_data': fanduel_match['raw_data'],
                        'odds': self.extract_fanduel_odds(fanduel_match['raw_data'])
                    },
                    '1xbet': {
                        'available': False,
                        'live_data': {},
                        'odds': {}
                    }
                }
                unified_matches.append(unified_match)
        
        # Add unmatched 1xBet live matches
        for idx, xbet_match in enumerate(xbet_matches):
            if idx not in matched_xbet_indices:
                canonical_sport = self.get_canonical_sport_name(xbet_match['sport'])
                score_info = self.extract_live_score(xbet_match, '1xbet')
                
                # Use Live as date and extract time from score info
                match_time = score_info.get('time_remaining') or score_info.get('period') or 'In Progress'
                
                unified_match = {
                    'sport': canonical_sport,
                    'home_team': xbet_match['home_team'],
                    'away_team': xbet_match['away_team'],
                    'date': 'Live',
                    'time': match_time,
                    'is_live': True,
                    'score': score_info,
                    'bet365': {
                        'available': False,
                        'live_data': {},
                        'odds': {}
                    },
                    'fanduel': {
                        'available': False,
                        'live_data': {},
                        'odds': {}
                    },
                    '1xbet': {
                        'available': True,
                        'live_data': xbet_match['raw_data'],
                        'odds': self.extract_1xbet_odds(xbet_match['raw_data'])
                    }
                }
                unified_matches.append(unified_match)
        
        print(f"\n Live Summary:")
        print(f"   Total unified live matches: {len(unified_matches)}")
        print(f"   Bet365 only: {len(bet365_matches) - len([m for m in unified_matches if m['bet365']['available'] and (m['fanduel']['available'] or m['1xbet']['available'])])}")
        print(f"   FanDuel only: {len(fanduel_matches) - len(matched_fanduel_indices)}")
        print(f"   1xBet only: {len(xbet_matches) - len(matched_xbet_indices)}")
        
        return unified_matches
    
    def collect_and_merge(self):
        """Main collection and merging process with memory optimization"""
        import gc  # Import garbage collector
        
        print("="*80)
        print("UNIFIED ODDS COLLECTOR - Combining Bet365, FanDuel, and 1xBet")
        print("="*80)

        # Load all data
        print("\nLoading data from all sources...")
        bet365_pregame = self.load_bet365_pregame()
        bet365_live = self.load_bet365_live()
        fanduel_pregame = self.load_fanduel_pregame()
        fanduel_live = self.load_fanduel_live()
        xbet_pregame = self.load_1xbet_pregame()
        xbet_live = self.load_1xbet_live()

        # Auto-update cache with new teams discovered
        print("\nAuto-updating cache with newly discovered teams...")
        cache_updates = {
            'bet365_pregame': bet365_pregame,
            'bet365_live': bet365_live,
            'fanduel_pregame': fanduel_pregame,
            'fanduel_live': fanduel_live,
            '1xbet_pregame': xbet_pregame,
            '1xbet_live': xbet_live
        }
        
        total_new_teams = 0
        total_new_sports = 0
        for source_name, matches in cache_updates.items():
            if matches:
                try:
                    for match in matches:
                        sport = match.get('sport', 'Unknown')
                        home_team = match.get('home_team', '')
                        away_team = match.get('away_team', '')
                        
                        if sport and sport != 'Unknown':
                            self.cache_manager.add_sport(sport, source=source_name.split('_')[0])
                        
                        if home_team:
                            was_added = self.cache_manager.add_team(sport, home_team, source=source_name.split('_')[0])
                            if was_added:
                                total_new_teams += 1
                        
                        if away_team:
                            was_added = self.cache_manager.add_team(sport, away_team, source=source_name.split('_')[0])
                            if was_added:
                                total_new_teams += 1
                except Exception as e:
                    print(f"  Warning: Could not process {source_name} for cache update: {e}")
        
        # Save updated cache
        if total_new_teams > 0:
            self.cache_manager.save_cache(replicate_to_subfolders=True)
            print(f"✓ Cache updated: +{total_new_teams} new teams discovered")
            # Reload cache for this session
            self.load_cache()
        else:
            print("✓ No new teams found (cache is up to date)")

        # Merge pregame
        print("\nMerging pregame matches...")
        unified_pregame = self.merge_pregame_data(bet365_pregame, fanduel_pregame, xbet_pregame)
        
        # Track if we have 1xBet data
        has_xbet_pregame = len(xbet_pregame) > 0
        
        # Clear source data to free memory
        del bet365_pregame, fanduel_pregame, xbet_pregame
        gc.collect()

        # Merge live
        print("\nMerging live matches...")
        unified_live = self.merge_live_data(bet365_live, fanduel_live, xbet_live)
        
        # Track if we have 1xBet live data
        has_xbet_live = len(xbet_live) > 0
        
        # Clear source data to free memory
        del bet365_live, fanduel_live, xbet_live
        gc.collect()

        # Determine active sources
        sources = ['bet365', 'fanduel']
        if has_xbet_pregame or has_xbet_live:
            sources.append('1xbet')

        # Create final output
        output = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'sources': sources,
                'total_pregame_matches': len(unified_pregame),
                'total_live_matches': len(unified_live)
            },
            'pregame_matches': unified_pregame,
            'live_matches': unified_live
        }

        # Save to file with streaming to reduce memory usage
        print(f"\n Saving unified data to {self.unified_output_file}...")
        self.stream_json_to_file(output, self.unified_output_file)

        print(f"Unified odds database created successfully!")
        print(f"\n Output file: {self.unified_output_file}")
        print(f"   - Pregame matches: {len(unified_pregame)}")
        print(f"   - Live matches: {len(unified_live)}")
        print("="*80)

    def stream_json_to_file(self, data, filepath):
        """Stream JSON to file with atomic write and locking to prevent corruption"""
        import json
        import tempfile
        import shutil
        import time
        
        # Acquire lock to prevent concurrent writes
        with self.file_lock:
            # Additional file-based lock for cross-process safety
            lock_file = filepath + '.lock'
            max_wait = 10  # Maximum 10 seconds wait for lock
            waited = 0
            
            # Wait for lock file to be released
            while os.path.exists(lock_file) and waited < max_wait:
                time.sleep(0.1)
                waited += 0.1
            
            try:
                # Create lock file
                with open(lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                # Write to temporary file in same directory (for atomic move)
                temp_file = filepath + '.tmp'
                backup_file = filepath + '.bak'
                
                try:
                    # Sanitize data before writing to prevent JSON errors
                    sanitized_data = self._sanitize_data_for_json(data)
                    
                    # Write to temp file with explicit flush
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(sanitized_data, f, indent=2, ensure_ascii=False, allow_nan=False)
                        f.flush()
                        os.fsync(f.fileno())  # Force write to disk
                    
                    # Verify temp file is valid JSON before proceeding
                    try:
                        with open(temp_file, 'r', encoding='utf-8') as f:
                            json.load(f)  # Validate JSON
                    except json.JSONDecodeError as e:
                        raise Exception(f"Generated JSON is invalid: {e}")
                    
                    # Backup existing file if it exists and is valid
                    if os.path.exists(filepath):
                        try:
                            # Verify existing file before backing up
                            with open(filepath, 'r', encoding='utf-8') as f:
                                json.load(f)
                            # File is valid, back it up
                            if os.path.exists(backup_file):
                                os.remove(backup_file)
                            shutil.copy2(filepath, backup_file)
                        except json.JSONDecodeError:
                            # Existing file is corrupted, don't back it up
                            print("⚠ Existing file corrupted, not backing up")
                    
                    # Atomic replace using os.replace (atomic on Windows and Unix)
                    os.replace(temp_file, filepath)
                    
                    print("✓ File saved successfully (atomic write with validation)")
                    
                except Exception as e:
                    print(f"❌ Error saving file: {e}")
                    # Clean up temp file if it exists
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    raise
            finally:
                # Always remove lock file
                try:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                except:
                    pass
    
    def _sanitize_data_for_json(self, obj):
        """Remove circular references and non-serializable objects"""
        import math
        
        if isinstance(obj, dict):
            return {k: self._sanitize_data_for_json(v) for k, v in obj.items() if k != '__visited__'}
        elif isinstance(obj, list):
            return [self._sanitize_data_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._sanitize_data_for_json(item) for item in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, (str, int, bool, type(None))):
            return obj
        else:
            # Try to convert to string for unknown types
            try:
                return str(obj)
            except:
                return None


def main():
    collector = UnifiedOddsCollector()
    collector.collect_and_merge()


if __name__ == "__main__":
    main()
