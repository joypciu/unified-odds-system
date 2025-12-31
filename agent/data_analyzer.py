#!/usr/bin/env python3
"""
Data Analyzer Module
Loads and compares unified_odds.json and oddsmagnet data for correlation analysis
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher


class DataAnalyzer:
    """Analyzes and correlates unified odds data with oddsmagnet data"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # Auto-detect base directory
            self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = Path(base_dir)
        
        # Data paths
        self.unified_odds_path = self.base_dir / "data" / "unified_odds.json"
        self.oddsmagnet_dir = self.base_dir / "bookmakers" / "oddsmagnet"
        
        # Loaded data
        self.unified_data = None
        self.oddsmagnet_data = {}
        
    def load_unified_data(self) -> Dict:
        """Load unified odds data"""
        try:
            if not self.unified_odds_path.exists():
                print(f"⚠️  Unified odds file not found: {self.unified_odds_path}")
                return {"pregame_matches": [], "live_matches": [], "metadata": {}}
            
            with open(self.unified_odds_path, 'r', encoding='utf-8') as f:
                self.unified_data = json.load(f)
            
            print(f"✅ Loaded unified data: {len(self.unified_data.get('pregame_matches', []))} pregame, "
                  f"{len(self.unified_data.get('live_matches', []))} live matches")
            return self.unified_data
            
        except Exception as e:
            print(f"❌ Error loading unified data: {e}")
            return {"pregame_matches": [], "live_matches": [], "metadata": {}}
    
    def load_oddsmagnet_data(self) -> Dict:
        """Load all oddsmagnet sport-specific JSON files"""
        try:
            if not self.oddsmagnet_dir.exists():
                print(f"⚠️  Oddsmagnet directory not found: {self.oddsmagnet_dir}")
                return {}
            
            # Find all oddsmagnet JSON files
            oddsmagnet_files = list(self.oddsmagnet_dir.glob("oddsmagnet_*.json"))
            
            for file_path in oddsmagnet_files:
                sport_name = file_path.stem.replace("oddsmagnet_", "")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    self.oddsmagnet_data[sport_name] = data
                    match_count = data.get('matches_count', len(data.get('matches', [])))
                    print(f"✅ Loaded oddsmagnet {sport_name}: {match_count} matches")
                    
                except Exception as e:
                    print(f"⚠️  Error loading {file_path.name}: {e}")
            
            return self.oddsmagnet_data
            
        except Exception as e:
            print(f"❌ Error loading oddsmagnet data: {e}")
            return {}
    
    def normalize_team_name(self, name: str) -> str:
        """Normalize team name for comparison"""
        if not name:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = ' '.join(name.lower().strip().split())
        
        # Remove common suffixes
        suffixes_to_remove = [' fc', ' cf', ' afc', ' united', ' city', ' town', ' rovers']
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        return normalized
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings (0-1)"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def find_matching_oddsmagnet_match(self, unified_match: Dict, sport: str = None) -> Optional[Dict]:
        """Find corresponding match in oddsmagnet data"""
        home_team = self.normalize_team_name(unified_match.get('home_team', ''))
        away_team = self.normalize_team_name(unified_match.get('away_team', ''))
        
        if not home_team or not away_team:
            return None
        
        # Search in specific sport or all sports
        sports_to_search = [sport] if sport else self.oddsmagnet_data.keys()
        
        best_match = None
        best_score = 0.0
        
        for sport_key in sports_to_search:
            if sport_key not in self.oddsmagnet_data:
                continue
            
            matches = self.oddsmagnet_data[sport_key].get('matches', [])
            
            for om_match in matches:
                om_home = self.normalize_team_name(om_match.get('home', ''))
                om_away = self.normalize_team_name(om_match.get('away', ''))
                
                # Calculate similarity scores
                home_score = self.calculate_similarity(home_team, om_home)
                away_score = self.calculate_similarity(away_team, om_away)
                total_score = (home_score + away_score) / 2
                
                # Consider it a match if similarity > 0.75
                if total_score > best_score and total_score >= 0.75:
                    best_score = total_score
                    best_match = {
                        'match': om_match,
                        'sport': sport_key,
                        'similarity': total_score
                    }
        
        return best_match
    
    def compare_odds(self, unified_match: Dict, oddsmagnet_match: Dict) -> Dict:
        """Compare odds between unified and oddsmagnet data"""
        comparison = {
            'unified_match': {
                'home': unified_match.get('home_team'),
                'away': unified_match.get('away_team'),
                'sport': unified_match.get('sport'),
            },
            'oddsmagnet_match': {
                'home': oddsmagnet_match['match'].get('home'),
                'away': oddsmagnet_match['match'].get('away'),
                'sport': oddsmagnet_match['sport'],
                'similarity': oddsmagnet_match['similarity']
            },
            'bookmakers_comparison': {},
            'insights': []
        }
        
        # Check which bookmakers are available in unified data
        unified_bookmakers = []
        for bm in ['bet365', 'fanduel', '1xbet']:
            if unified_match.get(bm, {}).get('available', False):
                unified_bookmakers.append(bm)
        
        # Get oddsmagnet bookmakers
        oddsmagnet_bookmakers = set()
        markets = oddsmagnet_match['match'].get('markets', {})
        for market_list in markets.values():
            if isinstance(market_list, list):
                for market in market_list:
                    if isinstance(market, dict) and 'odds' in market:
                        for odd in market['odds']:
                            if 'bookmaker_name' in odd:
                                oddsmagnet_bookmakers.add(odd['bookmaker_name'])
        
        comparison['unified_bookmakers'] = unified_bookmakers
        comparison['oddsmagnet_bookmakers'] = list(oddsmagnet_bookmakers)
        
        # Check for common bookmakers
        common_bookmakers = set([bm.upper()[:2] for bm in unified_bookmakers]) & oddsmagnet_bookmakers
        
        if common_bookmakers:
            comparison['insights'].append(f"Common bookmakers found: {', '.join(common_bookmakers)}")
        else:
            comparison['insights'].append("No common bookmakers found between unified and oddsmagnet data")
        
        # Compare market coverage
        unified_markets = self._extract_unified_markets(unified_match)
        oddsmagnet_markets = list(markets.keys()) if markets else []
        
        comparison['unified_markets'] = unified_markets
        comparison['oddsmagnet_markets'] = oddsmagnet_markets
        comparison['oddsmagnet_markets_count'] = len(oddsmagnet_markets)
        
        if len(oddsmagnet_markets) > len(unified_markets):
            comparison['insights'].append(
                f"OddsMagnet has {len(oddsmagnet_markets) - len(unified_markets)} more market types"
            )
        
        return comparison
    
    def _extract_unified_markets(self, unified_match: Dict) -> List[str]:
        """Extract available market types from unified match"""
        markets = set()
        
        for bm in ['bet365', 'fanduel', '1xbet']:
            if not unified_match.get(bm, {}).get('available', False):
                continue
            
            odds = unified_match[bm].get('odds', {})
            
            if any(k.startswith('moneyline_') for k in odds.keys()):
                markets.add('moneyline')
            if any(k.startswith('spread_') for k in odds.keys()):
                markets.add('spread')
            if any(k.startswith('total_') for k in odds.keys()):
                markets.add('totals')
        
        return list(markets)
    
    def generate_analysis_report(self) -> Dict:
        """Generate comprehensive analysis report"""
        if not self.unified_data or not self.oddsmagnet_data:
            return {"error": "Data not loaded. Call load_unified_data() and load_oddsmagnet_data() first"}
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'unified_pregame_matches': len(self.unified_data.get('pregame_matches', [])),
                'unified_live_matches': len(self.unified_data.get('live_matches', [])),
                'oddsmagnet_sports': list(self.oddsmagnet_data.keys()),
                'oddsmagnet_total_matches': sum(
                    data.get('matches_count', len(data.get('matches', [])))
                    for data in self.oddsmagnet_data.values()
                ),
            },
            'correlations': {
                'matches_found': 0,
                'matches_not_found': 0,
                'examples': []
            },
            'insights': []
        }
        
        # Sample first 10 pregame matches for correlation check
        sample_size = min(10, len(self.unified_data.get('pregame_matches', [])))
        
        for unified_match in self.unified_data.get('pregame_matches', [])[:sample_size]:
            om_match = self.find_matching_oddsmagnet_match(unified_match)
            
            if om_match:
                report['correlations']['matches_found'] += 1
                comparison = self.compare_odds(unified_match, om_match)
                report['correlations']['examples'].append(comparison)
            else:
                report['correlations']['matches_not_found'] += 1
        
        # Generate insights
        if report['correlations']['matches_found'] > 0:
            match_rate = (report['correlations']['matches_found'] / sample_size) * 100
            report['insights'].append(f"Match correlation rate: {match_rate:.1f}% ({report['correlations']['matches_found']}/{sample_size})")
        
        # Sport coverage comparison
        unified_sports = set(m.get('sport', 'Unknown') for m in self.unified_data.get('pregame_matches', []))
        oddsmagnet_sports = set(self.oddsmagnet_data.keys())
        
        report['insights'].append(f"Unified covers {len(unified_sports)} sports: {', '.join(unified_sports)}")
        report['insights'].append(f"OddsMagnet covers {len(oddsmagnet_sports)} sports: {', '.join(oddsmagnet_sports)}")
        
        return report


if __name__ == "__main__":
    # Test the analyzer
    analyzer = DataAnalyzer()
    
    print("\n" + "="*60)
    print("DATA ANALYZER - Loading Data")
    print("="*60 + "\n")
    
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    print("\n" + "="*60)
    print("GENERATING ANALYSIS REPORT")
    print("="*60 + "\n")
    
    report = analyzer.generate_analysis_report()
    
    print(json.dumps(report, indent=2))
