"""
Match Name Cleaner Utility
Cleans up match names by removing unnecessary suffixes like (Women), Women, (Ladies), etc.
"""

import re
from typing import Dict, Any

class MatchNameCleaner:
    """Clean up match names from various sources"""
    
    # Patterns to remove from team names (case-insensitive)
    TEAM_SUFFIXES_TO_REMOVE = [
        r'\s+\(Women\)',        # (Women)
        r'\s+\(Ladies\)',       # (Ladies)
        r'\s+\(W\)',           # (W)
        r'\s+Women$',          # Women at end
        r'\s+Ladies$',         # Ladies at end
        r'\s+W$',              # W at end
        r'\s+\(Female\)',      # (Female)
        r'\s+Female$',         # Female at end
    ]
    
    # Compiled regex patterns for performance
    _compiled_patterns = None
    
    @classmethod
    def _get_compiled_patterns(cls):
        """Get compiled regex patterns (cached)"""
        if cls._compiled_patterns is None:
            cls._compiled_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in cls.TEAM_SUFFIXES_TO_REMOVE
            ]
        return cls._compiled_patterns
    
    @classmethod
    def clean_team_name(cls, team_name: str) -> str:
        """
        Clean a single team name by removing common suffixes
        
        Args:
            team_name: Original team name
            
        Returns:
            Cleaned team name
            
        Example:
            "Barcelona Women" -> "Barcelona"
            "Barcelona (Women)" -> "Barcelona"
            "Barcelona" -> "Barcelona" (unchanged)
        """
        if not team_name or not isinstance(team_name, str):
            return team_name
        
        cleaned = team_name.strip()
        
        # Apply all removal patterns
        for pattern in cls._get_compiled_patterns():
            cleaned = pattern.sub('', cleaned)
        
        return cleaned.strip()
    
    @classmethod
    def clean_match_name(cls, match_name: str) -> str:
        """
        Clean a match name (team1 v team2 format)
        
        Args:
            match_name: Original match name like "Barcelona Women v Osasuna Women"
            
        Returns:
            Cleaned match name like "Barcelona v Osasuna"
            
        Example:
            "Barcelona Women v Osasuna Women" -> "Barcelona v Osasuna"
            "Barcelona (W) v Osasuna (W)" -> "Barcelona v Osasuna"
        """
        if not match_name or not isinstance(match_name, str):
            return match_name
        
        # Common separators between teams
        separators = [' v ', ' vs ', ' - ', ' @ ']
        
        for separator in separators:
            if separator in match_name:
                parts = match_name.split(separator)
                if len(parts) == 2:
                    cleaned_home = cls.clean_team_name(parts[0])
                    cleaned_away = cls.clean_team_name(parts[1])
                    return f"{cleaned_home}{separator}{cleaned_away}"
        
        # If no separator found, clean the whole name
        return cls.clean_team_name(match_name)
    
    @classmethod
    def clean_match_data(cls, match_data: Dict[str, Any], 
                        clean_match_name: bool = True,
                        clean_home_team: bool = True,
                        clean_away_team: bool = True) -> Dict[str, Any]:
        """
        Clean match data dictionary
        
        Args:
            match_data: Dictionary containing match information
            clean_match_name: Whether to clean 'match_name' field
            clean_home_team: Whether to clean 'home_team' field
            clean_away_team: Whether to clean 'away_team' field
            
        Returns:
            Match data with cleaned fields
            
        Example:
            Input: {
                'match_name': 'Barcelona Women v Osasuna Women',
                'home_team': 'Barcelona Women',
                'away_team': 'Osasuna Women'
            }
            Output: {
                'match_name': 'Barcelona v Osasuna',
                'home_team': 'Barcelona',
                'away_team': 'Osasuna'
            }
        """
        if not match_data or not isinstance(match_data, dict):
            return match_data
        
        # Create a copy to avoid modifying original
        cleaned_data = match_data.copy()
        
        if clean_match_name and 'match_name' in cleaned_data:
            cleaned_data['match_name'] = cls.clean_match_name(cleaned_data['match_name'])
        
        if clean_home_team and 'home_team' in cleaned_data:
            cleaned_data['home_team'] = cls.clean_team_name(cleaned_data['home_team'])
        
        if clean_away_team and 'away_team' in cleaned_data:
            cleaned_data['away_team'] = cls.clean_team_name(cleaned_data['away_team'])
        
        return cleaned_data
    
    @classmethod
    def should_keep_women_suffix(cls, league_name: str) -> bool:
        """
        Determine if league name suggests this is explicitly a women's league
        (in which case we should keep the suffix for clarity)
        
        Args:
            league_name: League name to check
            
        Returns:
            True if women's suffix should be kept, False otherwise
        """
        if not league_name:
            return False
        
        league_lower = league_name.lower()
        
        # If league name already indicates women's league, keep the suffix
        women_indicators = [
            'women', 'ladies', 'female', 'feminin',
            'dames', 'frauen', 'féminine', 'kvinnor'
        ]
        
        return any(indicator in league_lower for indicator in women_indicators)


# Convenience functions for quick access
def clean_match_name(match_name: str) -> str:
    """Quick function to clean a match name"""
    return MatchNameCleaner.clean_match_name(match_name)


def clean_team_name(team_name: str) -> str:
    """Quick function to clean a team name"""
    return MatchNameCleaner.clean_team_name(team_name)


def clean_match_data(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """Quick function to clean match data"""
    return MatchNameCleaner.clean_match_data(match_data)


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "Barcelona Women v Osasuna Women",
        "Barcelona (Women) v Osasuna (Women)",
        "Barcelona W v Osasuna W",
        "Barcelona (W) v Osasuna (W)",
        "Barcelona Ladies v Osasuna Ladies",
        "Chelsea FC Women v Arsenal Women",
        "Barcelona v Osasuna",  # Should remain unchanged
    ]
    
    print("Match Name Cleaning Tests:")
    print("=" * 60)
    for test in test_cases:
        cleaned = clean_match_name(test)
        print(f"Original: {test}")
        print(f"Cleaned:  {cleaned}")
        print()
    
    # Test match data
    print("\nMatch Data Cleaning Test:")
    print("=" * 60)
    test_data = {
        'match_name': 'Barcelona Women v Osasuna Women',
        'home_team': 'Barcelona Women',
        'away_team': 'Osasuna Women',
        'league': 'Spain - La Liga',
        'match_date': '2024-12-14'
    }
    
    print("Original:", test_data)
    print("Cleaned: ", clean_match_data(test_data))
