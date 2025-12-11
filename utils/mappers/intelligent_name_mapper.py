#!/usr/bin/env python3
"""
Intelligent Name Mapper - Advanced team/league name standardization system
Handles variations like "Manchester City", "Man City", "Manchester" across sources
Provides O(1) lookup after building the mapping index
"""

import re
import json
from typing import Dict, Set, Optional, List, Tuple
from difflib import SequenceMatcher
from collections import defaultdict


class IntelligentNameMapper:
    """
    Intelligent name mapping system that handles:
    1. Common abbreviations (Man City -> Manchester City)
    2. Special characters and formatting differences
    3. Suffixes/Prefixes (FC, United, etc.)
    4. City names vs full team names
    5. Cross-source variations (1xbet, FanDuel, Bet365)
    """
    
    def __init__(self):
        # O(1) lookup maps
        self.normalized_to_canonical = {}  # normalized string -> canonical name
        self.alias_to_canonical = {}  # any variation -> canonical name
        
        # Canonical name registry
        self.canonical_names = set()  # All approved canonical names
        
        # Common team name patterns and their standardized versions
        self.team_name_patterns = {
            # Soccer teams - common abbreviations
            'man city': 'Manchester City',
            'man united': 'Manchester United',
            'man utd': 'Manchester United',
            'liverpool': 'Liverpool',
            'chelsea': 'Chelsea',
            'arsenal': 'Arsenal',
            'tottenham': 'Tottenham Hotspur',
            'spurs': 'Tottenham Hotspur',
            'newcastle': 'Newcastle United',
            'west ham': 'West Ham United',
            'aston villa': 'Aston Villa',
            'brighton': 'Brighton & Hove Albion',
            'crystal palace': 'Crystal Palace',
            'leicester': 'Leicester City',
            'wolves': 'Wolverhampton Wanderers',
            'nottm forest': 'Nottingham Forest',
            'brentford': 'Brentford',
            'fulham': 'Fulham',
            'bournemouth': 'AFC Bournemouth',
            'everton': 'Everton',
            'southampton': 'Southampton',
            'leeds': 'Leeds United',
            
            # Basketball - NBA team abbreviations
            'lakers': 'Los Angeles Lakers',
            'clippers': 'Los Angeles Clippers',
            'warriors': 'Golden State Warriors',
            'celtics': 'Boston Celtics',
            'nets': 'Brooklyn Nets',
            'knicks': 'New York Knicks',
            'heat': 'Miami Heat',
            'bulls': 'Chicago Bulls',
            'mavericks': 'Dallas Mavericks',
            'rockets': 'Houston Rockets',
            'spurs': 'San Antonio Spurs',
            'suns': 'Phoenix Suns',
            'bucks': 'Milwaukee Bucks',
            '76ers': 'Philadelphia 76ers',
            'sixers': 'Philadelphia 76ers',
            'raptors': 'Toronto Raptors',
            'nuggets': 'Denver Nuggets',
            'jazz': 'Utah Jazz',
            'blazers': 'Portland Trail Blazers',
            'thunder': 'Oklahoma City Thunder',
            'kings': 'Sacramento Kings',
            'pelicans': 'New Orleans Pelicans',
            'grizzlies': 'Memphis Grizzlies',
            'timberwolves': 'Minnesota Timberwolves',
            'pacers': 'Indiana Pacers',
            'pistons': 'Detroit Pistons',
            'cavaliers': 'Cleveland Cavaliers',
            'hornets': 'Charlotte Hornets',
            'magic': 'Orlando Magic',
            'wizards': 'Washington Wizards',
            'hawks': 'Atlanta Hawks',
        }
        
        # Common suffixes/prefixes to remove for normalization
        self.removable_tokens = {
            # Club types
            'fc', 'fk', 'sc', 'ac', 'as', 'cf', 'cd', 'cp', 'rc', 'ud',
            'afc', 'bfc', 'cfc', 'dfc', 'efc',
            
            # Common words
            'club', 'team', 'football', 'basketball', 'hockey',
            
            # Age groups
            'u21', 'u23', 'u19', 'u17', 'u18', 'u20',
            
            # Gender markers
            'women', 'ladies', 'mens', 'men',
            'w', 'm',
            
            # Numbers (often year or version)
            '2', '3', '4', '5'
        }
        
        # Esports/Virtual/Simulation markers to EXCLUDE from cache
        self.esports_markers = {
            'esports', 'e-sports', 'virtual', 'threat', 'royale', 'simulation',
            'sim', 'cyber', 'e-soccer', 'esoccer', 'e-basketball', 'e-football',
            'fifa', 'nba2k', 'madden', 'ebasketball', 'efootball', 'ecricket',
            'simulated', 'cyberleague', 'cybersport', 'gaming', 'e-league',
            'eleague', 'digitalm', 'eafc', 'pes', 'pro evolution',
            '2k', 'league of legends', 'dota', 'csgo', 'valorant',
            'overwatch', 'rocket league', 'fortnite'
        }
        
        # City/state abbreviations
        self.location_expansions = {
            # US States/Cities - NBA
            'la': 'los angeles',
            'ny': 'new york',
            'gs': 'golden state',
            'sa': 'san antonio',
            'okc': 'oklahoma city',
            'no': 'new orleans',
            'nop': 'new orleans',
            
            # UK Cities - Soccer
            'man': 'manchester',
            'liv': 'liverpool',
            'tot': 'tottenham',
            'che': 'chelsea',
            'ars': 'arsenal',
            'lei': 'leicester',
            'new': 'newcastle',
            
            # Other
            'sf': 'san francisco',
            'phi': 'philadelphia',
            'phx': 'phoenix',
            'por': 'portland',
            'den': 'denver',
            'dal': 'dallas',
            'hou': 'houston',
            'mia': 'miami',
            'chi': 'chicago',
            'bos': 'boston',
            'atl': 'atlanta',
            'det': 'detroit',
            'cle': 'cleveland',
            'ind': 'indiana',
            'mem': 'memphis',
            'min': 'minnesota',
            'mil': 'milwaukee',
            'orl': 'orlando',
            'sac': 'sacramento',
            'tor': 'toronto',
            'was': 'washington',
            'cha': 'charlotte',
        }
        
    def is_esports_or_virtual(self, name: str) -> bool:
        """
        Detect if a team/match is esports, virtual, or simulated
        Returns True if it should be excluded from real sports cache
        """
        if not name:
            return False
        
        name_lower = name.lower()
        
        # Check for esports markers in the name
        for marker in self.esports_markers:
            if marker in name_lower:
                return True
        
        # Check for parenthetical markers like (THREAT), (Royale), (Virtual)
        import re
        parenthetical = re.findall(r'\(([^)]+)\)', name)
        for content in parenthetical:
            content_lower = content.lower()
            for marker in self.esports_markers:
                if marker in content_lower:
                    return True
        
        return False
    
    def normalize_string(self, name: str) -> str:
        """
        Deep normalization for matching purposes
        Returns a clean, standardized string for comparison
        """
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove parenthetical content (e.g., "(W)", "(THREAT)", "(U21)")
        normalized = re.sub(r'\([^)]*\)', '', normalized)
        
        # Replace special characters with spaces
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Expand common abbreviations
        words = normalized.split()
        expanded_words = []
        for word in words:
            clean_word = word.strip()
            if clean_word in self.location_expansions:
                expanded_words.append(self.location_expansions[clean_word])
            else:
                expanded_words.append(clean_word)
        normalized = ' '.join(expanded_words)
        
        # Remove removable tokens
        words = normalized.split()
        filtered_words = [w for w in words if w not in self.removable_tokens and len(w) > 1]
        normalized = ' '.join(filtered_words)
        
        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def extract_core_name(self, name: str) -> str:
        """
        Extract the core identifying part of a team name
        Example: "Manchester City FC (W)" -> "manchester city"
        """
        normalized = self.normalize_string(name)
        
        # Additional aggressive cleaning for core extraction
        # Keep only the most essential words (usually first 1-3 words)
        words = normalized.split()
        
        # If it's a known pattern, use that
        if normalized in self.team_name_patterns:
            return self.team_name_patterns[normalized]
        
        # Otherwise return first 2-3 significant words
        if len(words) <= 2:
            return normalized
        elif len(words) == 3:
            # Check if last word is common suffix
            if words[-1] in {'united', 'city', 'town', 'athletic', 'rovers'}:
                return normalized
            else:
                return ' '.join(words[:2])
        else:
            return ' '.join(words[:2])
    
    def similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)"""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def add_canonical_name(self, canonical_name: str, aliases: Optional[List[str]] = None):
        """
        Register a canonical name and its aliases
        All variations will map to this canonical name with O(1) lookup
        """
        if not canonical_name:
            return
        
        # Add to canonical registry
        self.canonical_names.add(canonical_name)
        
        # Normalize the canonical name itself
        normalized = self.normalize_string(canonical_name)
        if normalized:
            self.normalized_to_canonical[normalized] = canonical_name
            self.alias_to_canonical[normalized] = canonical_name
        
        # Add exact match (case-insensitive)
        self.alias_to_canonical[canonical_name.lower()] = canonical_name
        
        # Add all aliases
        if aliases:
            for alias in aliases:
                if alias:
                    alias_lower = alias.lower()
                    alias_normalized = self.normalize_string(alias)
                    
                    self.alias_to_canonical[alias_lower] = canonical_name
                    if alias_normalized:
                        self.alias_to_canonical[alias_normalized] = canonical_name
                        self.normalized_to_canonical[alias_normalized] = canonical_name
    
    def get_canonical_name(self, name: str) -> str:
        """
        Get canonical name for any variation - O(1) lookup
        Returns the original name if no mapping exists
        """
        if not name:
            return name
        
        # Try exact match first (case-insensitive)
        name_lower = name.lower()
        if name_lower in self.alias_to_canonical:
            return self.alias_to_canonical[name_lower]
        
        # Try normalized match
        normalized = self.normalize_string(name)
        if normalized in self.normalized_to_canonical:
            return self.normalized_to_canonical[normalized]
        
        # Try with known patterns
        if normalized in self.team_name_patterns:
            pattern_canonical = self.team_name_patterns[normalized]
            if pattern_canonical in self.canonical_names:
                return pattern_canonical
        
        # Return original if not found (allows fallback matching)
        return name
    
    def find_best_match(self, name: str, candidates: List[str], 
                       threshold: float = 0.75) -> Optional[str]:
        """
        Find best matching canonical name from candidates using fuzzy matching
        Returns None if no good match found
        """
        if not name or not candidates:
            return None
        
        normalized_input = self.normalize_string(name)
        if not normalized_input:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            normalized_candidate = self.normalize_string(candidate)
            if not normalized_candidate:
                continue
            
            # Calculate similarity
            score = self.similarity_score(normalized_input, normalized_candidate)
            
            # Bonus for substring matches
            if normalized_input in normalized_candidate or normalized_candidate in normalized_input:
                score += 0.1
            
            # Bonus for core name match
            core_input = self.extract_core_name(name)
            core_candidate = self.extract_core_name(candidate)
            if core_input == core_candidate and len(core_input) > 3:
                score += 0.2
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        # Only return match if it exceeds threshold
        if best_score >= threshold:
            return best_match
        
        return None
    
    def merge_duplicates(self, names: List[str]) -> Dict[str, List[str]]:
        """
        Group similar names together and identify which should be canonical
        Returns dict: {canonical_name: [list of aliases]}
        """
        if not names:
            return {}
        
        # Group by normalized form
        normalized_groups = defaultdict(list)
        for name in names:
            normalized = self.normalize_string(name)
            if normalized:
                normalized_groups[normalized].append(name)
        
        # For each group, pick the best canonical name
        canonical_mapping = {}
        for normalized, group in normalized_groups.items():
            if len(group) == 1:
                # Only one variant, it's canonical
                canonical_mapping[group[0]] = []
            else:
                # Multiple variants - pick best as canonical
                # Prefer: longer names, no parentheses, proper capitalization
                scored = []
                for name in group:
                    score = 0
                    score += len(name)  # Longer is usually better
                    if '(' not in name:
                        score += 20  # No parentheses is better
                    if name[0].isupper():
                        score += 10  # Proper capitalization
                    if not any(c.isdigit() for c in name):
                        score += 5  # No numbers is cleaner
                    scored.append((score, name))
                
                scored.sort(reverse=True)
                canonical = scored[0][1]
                aliases = [name for _, name in scored[1:]]
                canonical_mapping[canonical] = aliases
        
        return canonical_mapping
    
    def build_from_cache_data(self, cache_data: Dict):
        """
        Build intelligent mappings from existing cache data
        Analyzes all teams and creates optimal canonical mappings
        """
        print("[INFO] Building intelligent name mappings from cache...")
        
        sports_data = cache_data.get('sports', {})
        merge_count = 0
        
        for sport_name, sport_info in sports_data.items():
            teams = sport_info.get('teams', {})
            team_names = list(teams.keys())
            
            if not team_names:
                continue
            
            # Group similar teams
            merged = self.merge_duplicates(team_names)
            
            # Register canonical names and aliases
            for canonical, aliases in merged.items():
                # Collect all known aliases from cache too
                team_data = teams.get(canonical, {})
                cache_aliases = team_data.get('aliases', [])
                
                all_aliases = set(aliases)
                all_aliases.update(cache_aliases)
                
                # Add the canonical name
                self.add_canonical_name(canonical, list(all_aliases))
                
                if aliases:
                    merge_count += len(aliases)
        
        print(f"[OK] Mapped {len(self.canonical_names)} canonical names with {len(self.alias_to_canonical)} total aliases")
        print(f"[OK] Identified {merge_count} duplicate variations to merge")
    
    def get_mapping_stats(self) -> Dict:
        """Return statistics about the current mappings"""
        return {
            'canonical_names': len(self.canonical_names),
            'total_aliases': len(self.alias_to_canonical),
            'normalized_mappings': len(self.normalized_to_canonical),
            'avg_aliases_per_canonical': len(self.alias_to_canonical) / max(len(self.canonical_names), 1)
        }
    
    def export_mappings(self) -> Dict:
        """Export all mappings for persistence"""
        return {
            'canonical_names': list(self.canonical_names),
            'alias_to_canonical': self.alias_to_canonical,
            'normalized_to_canonical': self.normalized_to_canonical
        }
    
    def import_mappings(self, data: Dict):
        """Import mappings from exported data"""
        self.canonical_names = set(data.get('canonical_names', []))
        self.alias_to_canonical = data.get('alias_to_canonical', {})
        self.normalized_to_canonical = data.get('normalized_to_canonical', {})


if __name__ == "__main__":
    # Test the mapper
    print("=" * 80)
    print("INTELLIGENT NAME MAPPER - Testing")
    print("=" * 80)
    
    mapper = IntelligentNameMapper()
    
    # Test cases
    test_cases = [
        ("Manchester City", ["Man City", "Manchester City FC", "Man City (W)", "Manchester City (THREAT)"]),
        ("Manchester United", ["Man United", "Man Utd", "Manchester United FC"]),
        ("Los Angeles Lakers", ["Lakers", "LA Lakers", "L.A. Lakers"]),
        ("Golden State Warriors", ["Warriors", "GS Warriors", "GSW"]),
        ("Liverpool", ["Liverpool FC", "Liverpool (W)", "LFC"]),
    ]
    
    for canonical, aliases in test_cases:
        print(f"\nCanonical: {canonical}")
        mapper.add_canonical_name(canonical, aliases)
        
        print("  Testing lookups:")
        for alias in aliases:
            result = mapper.get_canonical_name(alias)
            status = "✓" if result == canonical else "✗"
            print(f"    {status} '{alias}' -> '{result}'")
    
    # Test normalization
    print("\n" + "=" * 80)
    print("NORMALIZATION TESTS")
    print("=" * 80)
    
    norm_tests = [
        "Manchester City (W)",
        "Man City FC",
        "Liverpool F.C.",
        "LA Lakers",
        "Golden State Warriors (esports)",
    ]
    
    for test in norm_tests:
        normalized = mapper.normalize_string(test)
        core = mapper.extract_core_name(test)
        print(f"{test:40} -> norm: '{normalized:25}' core: '{core}'")
    
    print("\n✅ Mapper tests complete!")
