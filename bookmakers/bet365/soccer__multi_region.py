"""
Soccer Data Collection - Multiple Markets and Regions
Collects Soccer betting data from bet365 including:
- Full Time Result
- To Qualify
- Both Teams to Score
- Result/Both Teams to Score
- Double Chance
- Goalscorers
- Players to be Booked

Regions:
- Top Leagues (J99)
- United Kingdom (J1)
"""
import asyncio
import json
import logging
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from patchright.async_api import async_playwright
from chrome_helper import setup_chrome_browser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SoccerParser:
    """Parse bet365 Soccer data"""

    def __init__(self):
        self.all_games = {
            'full_time_result': [],
            'to_qualify': [],
            'both_teams_to_score': [],
            'result_both_teams_to_score': [],
            'double_chance': [],
            'goalscorers': [],
            'players_to_be_booked': []
        }
        self.games_by_region = defaultdict(lambda: defaultdict(list))
        # Track processed fixtures to avoid duplicates across regions
        self.processed_fixtures = set()  # Set of (fixture_id, market, region) tuples
        
        # Region-specific competition patterns (for filtering misplaced games)
        self.region_patterns = {
            'United Kingdom': ['ENG-', 'SCO-', 'WAL-', 'NIR-', 'English', 'Scottish', 'Welsh', 'Northern Ireland'],
            'Top Leagues': []  # Top Leagues can have anything
        }
    
    def _should_skip_game(self, competition: str, region: str) -> bool:
        """Check if a game should be skipped based on competition/region mismatch"""
        # Top Leagues region accepts all competitions
        if region == 'Top Leagues':
            return False
        
        # For United Kingdom region, only include UK competitions
        if region == 'United Kingdom':
            patterns = self.region_patterns.get(region, [])
            if patterns:
                # Check if competition matches any UK pattern
                competition_upper = competition.upper()
                return not any(pattern.upper() in competition_upper for pattern in patterns)
            # If no patterns defined, allow all (fallback)
            return False
        
        return False

    def _parse_participant(self, line: str) -> Dict[str, str]:
        """Parse a PA (participant) line"""
        data = {}
        if line.startswith('PA;'):
            line = line[3:]
        pairs = line.split(';')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                data[key] = value
        return data

    def convert_odds(self, fractional: str) -> str:
        """Convert fractional odds to American format"""
        try:
            if '/' not in fractional:
                return fractional
            num, den = map(int, fractional.split('/'))
            if num == 0 or den == 0:
                return fractional
            decimal = (num / den) + 1
            if decimal >= 2.0:
                american = int((decimal - 1) * 100)
                return f"+{american}"
            else:
                american = int(-100 / (decimal - 1))
                return f"{american}"
        except:
            return fractional

    def _parse_date(self, bc_code: str) -> str:
        """Parse BC (book closes) date code to readable format"""
        if not bc_code or len(bc_code) != 14:
            return ''
        try:
            year = bc_code[0:4]
            month = bc_code[4:6]
            day = bc_code[6:8]
            hour = bc_code[8:10]
            minute = bc_code[10:12]
            return f"{year}-{month}-{day} {hour}:{minute}"
        except:
            return bc_code

    def parse_full_time_result(self, body: str, market_name: str = 'Full Time Result', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Full Time Result (1X2) market from bet365 Soccer response
        
        Soccer Format:
        - MG;ID=40;...;L3=FA Barclaycard;OI=184173120; (competition metadata)
        - PA;ID=PC44416546;NA=Team A;N2=Team B;...;FI=185388454; (game cards)
        - PA;ID=44416546;FI=185388454;OD=11/10;... (Home win odds)
        - PA;ID=44416547;FI=185388454;OD=23/10;... (Draw odds)
        - PA;ID=44416548;FI=185388454;OD=11/5;... (Away win odds)
        """
        games = {}
        competitions = {}  # fixture_id -> competition mapping
        sections = body.split('|')

        # First pass: extract competitions from MG lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if line.startswith('MG;'):
                    data = self._parse_participant(line)
                    competition = data.get('L3', '')
                    fixture_id = data.get('OI', '')  # MG lines use OI instead of FI
                    if competition and fixture_id:
                        competitions[fixture_id] = competition

        # Second pass: parse game cards and odds
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('EV;'):
                    continue

                if line.startswith('PA;') and ';ID=PC' in line:
                    # Game card
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    competition = competitions.get(fixture_id, '')
                    
                    # Skip games that don't belong to this region
                    if self._should_skip_game(competition, region):
                        continue
                    
                    if fixture_id:
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'participant_id': data.get('ID', '').replace('PC', ''),
                            'home_team': data.get('NA', ''),
                            'away_team': data.get('N2', ''),
                            'competition': competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'home_odds': None,
                            'home_odds_fractional': None,
                            'draw_odds': None,
                            'draw_odds_fractional': None,
                            'away_odds': None,
                            'away_odds_fractional': None
                        }
                elif line.startswith('PA;') and 'OD=' in line:
                    # Odds line
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id in games:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        
                        # Determine which odds (home/draw/away) based on participant ID
                        participant_id = data.get('ID', '')
                        
                        # Usually first odds = home, second = draw, third = away
                        if games[fixture_id]['home_odds'] is None:
                            games[fixture_id]['home_odds'] = american_odds
                            games[fixture_id]['home_odds_fractional'] = odds
                        elif games[fixture_id]['draw_odds'] is None:
                            games[fixture_id]['draw_odds'] = american_odds
                            games[fixture_id]['draw_odds_fractional'] = odds
                        elif games[fixture_id]['away_odds'] is None:
                            games[fixture_id]['away_odds'] = american_odds
                            games[fixture_id]['away_odds_fractional'] = odds

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_to_qualify(self, body: str, market_name: str = 'To Qualify', region: str = 'Top Leagues') -> List[Dict]:
        """Parse To Qualify market"""
        games = {}
        competitions = {}  # fixture_id -> competition mapping
        sections = body.split('|')

        # First pass: extract competitions from MG lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if line.startswith('MG;'):
                    data = self._parse_participant(line)
                    competition = data.get('L3', '')
                    fixture_id = data.get('OI', '')
                    if competition and fixture_id:
                        competitions[fixture_id] = competition

        # Second pass: parse game cards and odds
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('EV;'):
                    continue

                if line.startswith('PA;') and ';ID=PC' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    competition = competitions.get(fixture_id, '')
                    
                    # Skip games that don't belong to this region
                    if self._should_skip_game(competition, region):
                        continue
                    
                    if fixture_id:
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'participant_id': data.get('ID', '').replace('PC', ''),
                            'home_team': data.get('NA', ''),
                            'away_team': data.get('N2', ''),
                            'competition': competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'home_to_qualify_odds': None,
                            'away_to_qualify_odds': None
                        }
                elif line.startswith('PA;') and 'OD=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id in games:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        
                        if games[fixture_id]['home_to_qualify_odds'] is None:
                            games[fixture_id]['home_to_qualify_odds'] = american_odds
                            games[fixture_id]['home_to_qualify_odds_fractional'] = odds
                        elif games[fixture_id]['away_to_qualify_odds'] is None:
                            games[fixture_id]['away_to_qualify_odds'] = american_odds
                            games[fixture_id]['away_to_qualify_odds_fractional'] = odds

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_both_teams_to_score(self, body: str, market_name: str = 'Both Teams to Score', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Both Teams to Score (Yes/No) market"""
        games = {}
        competitions = {}  # fixture_id -> competition mapping
        sections = body.split('|')

        # First pass: extract competitions from MG lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if line.startswith('MG;'):
                    data = self._parse_participant(line)
                    competition = data.get('L3', '')
                    fixture_id = data.get('OI', '')
                    if competition and fixture_id:
                        competitions[fixture_id] = competition

        # Second pass: parse game cards and odds
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('EV;'):
                    continue

                if line.startswith('PA;') and ';ID=PC' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    competition = competitions.get(fixture_id, '')
                    
                    # Skip games that don't belong to this region
                    if self._should_skip_game(competition, region):
                        continue
                    
                    if fixture_id:
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'participant_id': data.get('ID', '').replace('PC', ''),
                            'home_team': data.get('NA', ''),
                            'away_team': data.get('N2', ''),
                            'competition': competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'yes_odds': None,
                            'no_odds': None
                        }
                elif line.startswith('PA;') and 'OD=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id in games:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        
                        if games[fixture_id]['yes_odds'] is None:
                            games[fixture_id]['yes_odds'] = american_odds
                            games[fixture_id]['yes_odds_fractional'] = odds
                        elif games[fixture_id]['no_odds'] is None:
                            games[fixture_id]['no_odds'] = american_odds
                            games[fixture_id]['no_odds_fractional'] = odds

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_result_both_teams_to_score(self, body: str, market_name: str = 'Result/Both Teams to Score', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Result/Both Teams to Score combined market"""
        games = {}
        competitions = {}  # fixture_id -> competition mapping
        sections = body.split('|')

        # First pass: extract competitions from MG lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if line.startswith('MG;'):
                    data = self._parse_participant(line)
                    competition = data.get('L3', '')
                    fixture_id = data.get('OI', '')
                    if competition and fixture_id:
                        competitions[fixture_id] = competition

        # Second pass: parse game cards and odds
        # Result/BTTS has 6 outcomes in order: Home/Yes, Home/No, Draw/Yes, Draw/No, Away/Yes, Away/No
        selection_labels = ["Home & Yes", "Home & No", "Draw & Yes", "Draw/No", "Away & Yes", "Away & No"]
        
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('EV;'):
                    continue

                if line.startswith('PA;') and ';ID=PC' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    competition = competitions.get(fixture_id, '')
                    
                    # Skip games that don't belong to this region
                    if self._should_skip_game(competition, region):
                        continue
                    
                    if fixture_id:
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'participant_id': data.get('ID', '').replace('PC', ''),
                            'home_team': data.get('NA', ''),
                            'away_team': data.get('N2', ''),
                            'competition': competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'selections': []
                        }
                elif line.startswith('PA;') and 'OD=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id in games:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        
                        # Use ordered selection based on position (6 selections per game)
                        selection_index = len(games[fixture_id]['selections'])
                        selection_name = selection_labels[selection_index] if selection_index < len(selection_labels) else 'Unknown'
                        
                        games[fixture_id]['selections'].append({
                            'selection': selection_name,
                            'odds': american_odds,
                            'odds_fractional': odds
                        })

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_double_chance(self, body: str, market_name: str = 'Double Chance', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Double Chance market (Home or Draw, Home or Away, Draw or Away)"""
        games = {}
        competitions = {}  # fixture_id -> competition mapping
        sections = body.split('|')

        # First pass: extract competitions from MG lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if line.startswith('MG;'):
                    data = self._parse_participant(line)
                    competition = data.get('L3', '')
                    fixture_id = data.get('OI', '')
                    if competition and fixture_id:
                        competitions[fixture_id] = competition

        # Second pass: parse game cards and odds
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('EV;'):
                    continue

                if line.startswith('PA;') and ';ID=PC' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    competition = competitions.get(fixture_id, '')
                    
                    # Skip games that don't belong to this region
                    if self._should_skip_game(competition, region):
                        continue
                    
                    if fixture_id:
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'participant_id': data.get('ID', '').replace('PC', ''),
                            'home_team': data.get('NA', ''),
                            'away_team': data.get('N2', ''),
                            'competition': competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'home_or_draw_odds': None,
                            'home_or_away_odds': None,
                            'draw_or_away_odds': None
                        }
                elif line.startswith('PA;') and 'OD=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id in games:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        
                        if games[fixture_id]['home_or_draw_odds'] is None:
                            games[fixture_id]['home_or_draw_odds'] = american_odds
                            games[fixture_id]['home_or_draw_odds_fractional'] = odds
                        elif games[fixture_id]['home_or_away_odds'] is None:
                            games[fixture_id]['home_or_away_odds'] = american_odds
                            games[fixture_id]['home_or_away_odds_fractional'] = odds
                        elif games[fixture_id]['draw_or_away_odds'] is None:
                            games[fixture_id]['draw_or_away_odds'] = american_odds
                            games[fixture_id]['draw_or_away_odds_fractional'] = odds

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_goalscorers(self, body: str, market_name: str = 'Goalscorers', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Goalscorers market (Anytime, First, Last goalscorer)"""
        games = {}
        current_fixture = None
        current_competition = ''
        player_names = {}  # Map player IDs to names
        
        sections = body.split('|')

        # First pass: collect player names from PA;ID=P lines
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Collect player names (PA;ID=P<id>;NA=<name>)
                if line.startswith('PA;ID=P') and ';NA=' in line:
                    data = self._parse_participant(line)
                    player_id = data.get('ID', '')
                    if player_id and player_id.startswith('P'):
                        # Remove P prefix to get numeric ID
                        numeric_id = player_id[1:]
                        player_names[numeric_id] = data.get('NA', 'Unknown Player')

        # Second pass: parse games and match player IDs to names
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Track competition from EV lines
                if line.startswith('EV;') and 'L3=' in line:
                    data = self._parse_participant(line)
                    current_competition = data.get('L3', '')
                
                # Parse MG lines for match/fixture context
                elif line.startswith('MG;') and ';FI=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id:
                        current_fixture = fixture_id
                        match_name = data.get('NA', '')
                        # Split "Team A v Team B" format
                        teams = match_name.split(' v ')
                        home_team = teams[0] if len(teams) > 0 else ''
                        away_team = teams[1] if len(teams) > 1 else ''
                        
                        # Skip games that don't belong to this region
                        if self._should_skip_game(current_competition, region):
                            current_fixture = None
                            continue
                        
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'home_team': home_team,
                            'away_team': away_team,
                            'competition': current_competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'goalscorers': []
                        }
                
                # Parse PA lines for player odds (PA;ID=<numeric_id>;OD=)
                elif line.startswith('PA;ID=') and not line.startswith('PA;ID=P') and 'OD=' in line and current_fixture:
                    data = self._parse_participant(line)
                    player_id = data.get('ID', '')
                    if current_fixture in games and player_id:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        # Look up player name from collected names
                        player_name = player_names.get(player_id, None)
                        
                        # Only add if we have a valid player name (filter out entries without names)
                        if player_name:
                            games[current_fixture]['goalscorers'].append({
                                'player': player_name,
                                'odds': american_odds,
                                'odds_fractional': odds
                            })

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_players_to_be_booked(self, body: str, market_name: str = 'Players to be Booked', region: str = 'Top Leagues') -> List[Dict]:
        """Parse Players to be Booked market"""
        games = {}
        current_fixture = None
        current_competition = ''
        
        sections = body.split('|')

        # Note: Players to be Booked market has BOTH NA and OD in same line (unlike goalscorers which separates them)
        # No first pass needed - we extract player names directly from the odds lines

        # Parse games and extract player data directly
        for section in sections:
            lines = section.split('¬')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Track competition from EV lines
                if line.startswith('EV;') and 'L3=' in line:
                    data = self._parse_participant(line)
                    current_competition = data.get('L3', '')
                
                # Parse MG lines for match/fixture context
                elif line.startswith('MG;') and ';FI=' in line:
                    data = self._parse_participant(line)
                    fixture_id = data.get('FI', '')
                    if fixture_id:
                        current_fixture = fixture_id
                        match_name = data.get('NA', '')
                        # Split "Team A v Team B" format
                        teams = match_name.split(' v ')
                        home_team = teams[0] if len(teams) > 0 else ''
                        away_team = teams[1] if len(teams) > 1 else ''
                        
                        # Skip games that don't belong to this region
                        if self._should_skip_game(current_competition, region):
                            current_fixture = None
                            continue
                        
                        games[fixture_id] = {
                            'fixture_id': fixture_id,
                            'home_team': home_team,
                            'away_team': away_team,
                            'competition': current_competition,
                            'start_time': self._parse_date(data.get('BC', '')),
                            'region': region,
                            'market': market_name,
                            'players': []
                        }
                
                # Parse PA lines for player odds (has BOTH NA and OD in same line)
                elif line.startswith('PA;ID=') and not line.startswith('PA;ID=P') and ';OD=' in line and current_fixture:
                    data = self._parse_participant(line)
                    player_id = data.get('ID', '')
                    if current_fixture in games and player_id:
                        odds = data.get('OD', '')
                        american_odds = self.convert_odds(odds)
                        # Extract player name directly from the line (players_to_be_booked has NA in same line as OD)
                        player_name = data.get('NA', '').strip()
                        
                        # Only add if we have a valid player name
                        if player_name:
                            games[current_fixture]['players'].append({
                                'player': player_name,
                                'odds': american_odds,
                                'odds_fractional': odds
                            })

        # Filter out duplicates - only keep fixtures not already processed
        result = []
        for game in games.values():
            fixture_key = (game['fixture_id'], game['market'], region)
            if fixture_key not in self.processed_fixtures:
                self.processed_fixtures.add(fixture_key)
                result.append(game)
                self.games_by_region[region][market_name].append(game)
        
        return result

    def parse_response(self, body: str, market_name: str, market_url: str, region: str, all_captured_data: Optional[List[Dict]] = None) -> List[Dict]:
        """Route to appropriate parser based on market name"""
        # Extract data after H1= marker if in F|CL format
        if body.startswith('F|CL;'):
            if ';H1=' in body:
                parts = body.split(';H1=', 1)
                if len(parts) == 2:
                    body = parts[1]
                    logger.info(f"  Extracted data from F|CL format, new length: {len(body)} bytes")

        if market_name == 'Full Time Result':
            return self.parse_full_time_result(body, market_name, region)
        elif market_name == 'To Qualify':
            return self.parse_to_qualify(body, market_name, region)
        elif market_name == 'Both Teams to Score':
            return self.parse_both_teams_to_score(body, market_name, region)
        elif market_name == 'Result/Both Teams to Score':
            return self.parse_result_both_teams_to_score(body, market_name, region)
        elif market_name == 'Double Chance':
            return self.parse_double_chance(body, market_name, region)
        elif market_name == 'Goalscorers':
            return self.parse_goalscorers(body, market_name, region)
        elif market_name == 'Players to be Booked':
            return self.parse_players_to_be_booked(body, market_name, region)
        return []

    def add_to_collection(self, parsed_data: List[Dict]):
        """Add parsed data to the main collection"""
        if not parsed_data:
            return
        
        market_name = parsed_data[0].get('market', '').lower().replace(' ', '_').replace('/', '_')
        if market_name in self.all_games:
            self.all_games[market_name].extend(parsed_data)

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        summary = {}
        for market, games in self.all_games.items():
            summary[market] = len(games)
        
        # Add region breakdown
        region_summary = {}
        for region, markets in self.games_by_region.items():
            region_summary[region] = {}
            for market, games in markets.items():
                region_summary[region][market] = len(games)
        summary['by_region'] = region_summary
        
        return summary

    def save_to_file(self, filename: str):
        """Save parsed data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.all_games, f, indent=2, ensure_ascii=False)

    def save_by_region(self, filename: str):
        """Save data organized by region"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(dict(self.games_by_region), f, indent=2, ensure_ascii=False)

    def to_optic_odds_format(self) -> Dict:
        """Convert to Optic Odds API format (matching NFL/NBA structure)"""
        from datetime import datetime
        games_data = []
        
        # Group games by fixture_id to consolidate markets
        games_by_fixture = {}
        for market_type, market_games in self.all_games.items():
            for game in market_games:
                fixture_id = game.get('fixture_id', '')
                if fixture_id not in games_by_fixture:
                    games_by_fixture[fixture_id] = {
                        'game_data': game,
                        'markets': {}
                    }
                games_by_fixture[fixture_id]['markets'][market_type] = game
        
        # Build games with odds array
        for fixture_id, fixture_data in games_by_fixture.items():
            game = fixture_data['game_data']
            home_team = game.get('home_team', '')
            away_team = game.get('away_team', '')
            competition = game.get('competition', '')
            start_time = game.get('start_time', '')
            betlink = f"https://www.bet365.com/#/AC/B1/C1/D1002/E{fixture_id}/"
            
            # Convert start time to ISO format
            try:
                if start_time and ' ' in start_time:
                    dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
                    iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    iso_date = start_time
            except:
                iso_date = start_time
            
            # Build odds array
            odds = []
            timestamp = datetime.now().timestamp()
            
            # Process each market type
            markets = fixture_data['markets']
            
            # Full Time Result (1X2 - Home/Draw/Away)
            if 'full_time_result' in markets:
                ftr_game = markets['full_time_result']
                home_odds = ftr_game.get('home_odds', '')
                draw_odds = ftr_game.get('draw_odds', '')
                away_odds = ftr_game.get('away_odds', '')
                
                if home_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:moneyline:home",
                        "sportsbook": "Bet365",
                        "market": "Moneyline",
                        "name": f"{home_team} (Home Win)",
                        "is_main": True,
                        "selection": home_team,
                        "normalized_selection": home_team.lower().replace(' ', '_'),
                        "market_id": "moneyline",
                        "selection_line": "1",  # 1X2 notation
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(home_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if draw_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:moneyline:draw",
                        "sportsbook": "Bet365",
                        "market": "Moneyline",
                        "name": "Draw",
                        "is_main": True,
                        "selection": "Draw",
                        "normalized_selection": "draw",
                        "market_id": "moneyline",
                        "selection_line": "X",  # 1X2 notation
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(draw_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if away_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:moneyline:away",
                        "sportsbook": "Bet365",
                        "market": "Moneyline",
                        "name": f"{away_team} (Away Win)",
                        "is_main": True,
                        "selection": away_team,
                        "normalized_selection": away_team.lower().replace(' ', '_'),
                        "market_id": "moneyline",
                        "selection_line": "2",  # 1X2 notation
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(away_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
            
            # To Qualify
            if 'to_qualify' in markets:
                tq_game = markets['to_qualify']
                home_tq_odds = tq_game.get('home_to_qualify_odds', '')
                away_tq_odds = tq_game.get('away_to_qualify_odds', '')
                
                if home_tq_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:to_qualify:home",
                        "sportsbook": "Bet365",
                        "market": "To Qualify",
                        "name": home_team,
                        "is_main": True,
                        "selection": home_team,
                        "normalized_selection": home_team.lower().replace(' ', '_'),
                        "market_id": "to_qualify",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(home_tq_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if away_tq_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:to_qualify:away",
                        "sportsbook": "Bet365",
                        "market": "To Qualify",
                        "name": away_team,
                        "is_main": True,
                        "selection": away_team,
                        "normalized_selection": away_team.lower().replace(' ', '_'),
                        "market_id": "to_qualify",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(away_tq_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
            
            # Both Teams to Score
            if 'both_teams_to_score' in markets:
                btts_game = markets['both_teams_to_score']
                yes_odds = btts_game.get('yes_odds', '')
                no_odds = btts_game.get('no_odds', '')
                
                if yes_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:btts:yes",
                        "sportsbook": "Bet365",
                        "market": "Both Teams to Score",
                        "name": "Yes",
                        "is_main": True,
                        "selection": "Yes",
                        "normalized_selection": "yes",
                        "market_id": "btts",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(yes_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if no_odds:
                    odds.append({
                        "id": f"{fixture_id}:bet365:btts:no",
                        "sportsbook": "Bet365",
                        "market": "Both Teams to Score",
                        "name": "No",
                        "is_main": True,
                        "selection": "No",
                        "normalized_selection": "no",
                        "market_id": "btts",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(no_odds) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
            
            # Double Chance
            if 'double_chance' in markets:
                dc_game = markets['double_chance']
                
                if dc_game.get('home_or_draw_odds'):
                    odds.append({
                        "id": f"{fixture_id}:bet365:double_chance:1x",
                        "sportsbook": "Bet365",
                        "market": "Double Chance",
                        "name": "Home or Draw (1X)",
                        "is_main": True,
                        "selection": "Home or Draw",
                        "normalized_selection": "home_or_draw",
                        "market_id": "double_chance",
                        "selection_line": "1X",
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(dc_game.get('home_or_draw_odds', '')) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if dc_game.get('home_or_away_odds'):
                    odds.append({
                        "id": f"{fixture_id}:bet365:double_chance:12",
                        "sportsbook": "Bet365",
                        "market": "Double Chance",
                        "name": "Home or Away (12)",
                        "is_main": True,
                        "selection": "Home or Away",
                        "normalized_selection": "home_or_away",
                        "market_id": "double_chance",
                        "selection_line": "12",
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(dc_game.get('home_or_away_odds', '')) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
                
                if dc_game.get('draw_or_away_odds'):
                    odds.append({
                        "id": f"{fixture_id}:bet365:double_chance:x2",
                        "sportsbook": "Bet365",
                        "market": "Double Chance",
                        "name": "Draw or Away (X2)",
                        "is_main": True,
                        "selection": "Draw or Away",
                        "normalized_selection": "draw_or_away",
                        "market_id": "double_chance",
                        "selection_line": "X2",
                        "player_id": None,
                        "team_id": None,
                        "price": self._parse_american_odds(dc_game.get('draw_or_away_odds', '')) or 0,
                        "timestamp": timestamp,
                        "grouping_key": "default",
                        "points": None,
                        "betlink": betlink,
                        "limits": None
                    })
            
            # Goalscorers
            if 'goalscorers' in markets:
                gs_game = markets['goalscorers']
                for scorer in gs_game.get('goalscorers', []):
                    player_name = scorer.get('player', '')
                    player_odds = scorer.get('odds', '')
                    if player_name and player_odds:
                        odds.append({
                            "id": f"{fixture_id}:bet365:goalscorer:{player_name.lower().replace(' ', '_')}",
                            "sportsbook": "Bet365",
                            "market": "Anytime Goalscorer",
                            "name": player_name,
                            "is_main": False,
                            "selection": player_name,
                            "normalized_selection": player_name.lower().replace(' ', '_'),
                            "market_id": "goalscorer",
                            "selection_line": None,
                            "player_id": None,
                            "team_id": None,
                            "price": self._parse_american_odds(player_odds) or 0,
                            "timestamp": timestamp,
                            "grouping_key": "anytime",
                            "points": None,
                            "betlink": betlink,
                            "limits": None
                        })
            
            # Players to be Booked
            if 'players_to_be_booked' in markets:
                pb_game = markets['players_to_be_booked']
                for player in pb_game.get('players', []):
                    player_name = player.get('player', '')
                    player_odds = player.get('odds', '')
                    if player_name and player_odds:
                        odds.append({
                            "id": f"{fixture_id}:bet365:player_booking:{player_name.lower().replace(' ', '_')}",
                            "sportsbook": "Bet365",
                            "market": "Player to be Booked",
                            "name": player_name,
                            "is_main": False,
                            "selection": player_name,
                            "normalized_selection": player_name.lower().replace(' ', '_'),
                            "market_id": "player_booking",
                            "selection_line": None,
                            "player_id": None,
                            "team_id": None,
                            "price": self._parse_american_odds(player_odds) or 0,
                            "timestamp": timestamp,
                            "grouping_key": "default",
                            "points": None,
                            "betlink": betlink,
                            "limits": None
                        })
            
            # Build game object
            game_obj = {
                "id": fixture_id,
                "game_id": f"soccer-{fixture_id}",
                "start_date": iso_date,
                "home_competitors": [
                    {
                        "id": None,
                        "name": home_team,
                        "abbreviation": self._get_team_abbreviation(home_team),
                        "logo": None
                    }
                ],
                "away_competitors": [
                    {
                        "id": None,
                        "name": away_team,
                        "abbreviation": self._get_team_abbreviation(away_team),
                        "logo": None
                    }
                ],
                "home_team_display": home_team,
                "away_team_display": away_team,
                "status": "unplayed",
                "is_live": False,
                "sport": {
                    "id": "soccer",
                    "name": "Soccer"
                },
                "league": {
                    "id": competition.lower().replace(' ', '_'),
                    "name": competition
                },
                "tournament": None,
                "odds": odds
            }
            
            games_data.append(game_obj)
        
        return {"data": games_data}

    def save_optic_odds_format(self, filename: str):
        """Save in Optic Odds format"""
        data = self.to_optic_odds_format()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def to_eternity_format(self) -> List[Dict]:
        """Convert to Eternity format (matching eternity_dev_response.json structure)"""
        eternity_data = []
        
        for market_type, market_games in self.all_games.items():
            for game in market_games:
                # Convert start time from "YYYY-MM-DD HH:MM" to ISO format "YYYY-MM-DDTHH:MM:SSZ"
                start_time = game.get('start_time', '')
                if start_time and ' ' in start_time:
                    start_time = start_time.replace(' ', 'T') + ':00Z'
                
                # Base entry following eternity_dev_response.json structure
                entry = {
                    'home': game.get('home_team', ''),
                    'away': game.get('away_team', ''),
                    'home_short': self._get_team_abbreviation(game.get('home_team', '')),
                    'away_short': self._get_team_abbreviation(game.get('away_team', '')),
                    'home_brief': self._get_team_abbreviation(game.get('home_team', '')),
                    'away_brief': self._get_team_abbreviation(game.get('away_team', '')),
                    'league': game.get('competition', ''),
                    'start_date': start_time,
                    'market': game.get('market', ''),
                    'bet_team': None,
                    'bet_player': None,
                    'bet_occurence': None,
                    'line': None,
                    'am_odds': None,
                    'book': 'Bet365',
                    'betlink': f"https://www.bet365.com/#/AC/B1/C1/D1002/E{game.get('fixture_id', '')}/",
                    'internal_betlink': f"https://www.bet365.com/#/AC/B1/C1/D1002/E{game.get('fixture_id', '')}/",
                    'is_main': True,
                    'sgp': None,
                    'limit': None,
                    'tournament': None
                }

                # Add market-specific data
                if market_type == 'full_time_result':
                    # Set market name to "Moneyline" for common structure
                    entry['market'] = 'Moneyline'
                    
                    # Home win
                    if game.get('home_odds'):
                        home_entry = entry.copy()
                        home_entry['bet_team'] = game.get('home_team', '')
                        home_entry['am_odds'] = self._parse_american_odds(game.get('home_odds', ''))
                        eternity_data.append(home_entry)
                    
                    # Draw
                    if game.get('draw_odds'):
                        draw_entry = entry.copy()
                        draw_entry['bet_occurence'] = 'Draw'
                        draw_entry['am_odds'] = self._parse_american_odds(game.get('draw_odds', ''))
                        eternity_data.append(draw_entry)
                    
                    # Away win
                    if game.get('away_odds'):
                        away_entry = entry.copy()
                        away_entry['bet_team'] = game.get('away_team', '')
                        away_entry['am_odds'] = self._parse_american_odds(game.get('away_odds', ''))
                        eternity_data.append(away_entry)
                
                elif market_type == 'to_qualify':
                    # Home to qualify
                    if game.get('home_to_qualify_odds'):
                        home_entry = entry.copy()
                        home_entry['bet_team'] = game.get('home_team', '')
                        home_entry['am_odds'] = self._parse_american_odds(game.get('home_to_qualify_odds', ''))
                        eternity_data.append(home_entry)
                    
                    # Away to qualify
                    if game.get('away_to_qualify_odds'):
                        away_entry = entry.copy()
                        away_entry['bet_team'] = game.get('away_team', '')
                        away_entry['am_odds'] = self._parse_american_odds(game.get('away_to_qualify_odds', ''))
                        eternity_data.append(away_entry)
                
                elif market_type == 'both_teams_to_score':
                    # Yes
                    if game.get('yes_odds'):
                        yes_entry = entry.copy()
                        yes_entry['bet_occurence'] = 'Yes'
                        yes_entry['am_odds'] = self._parse_american_odds(game.get('yes_odds', ''))
                        eternity_data.append(yes_entry)
                    
                    # No
                    if game.get('no_odds'):
                        no_entry = entry.copy()
                        no_entry['bet_occurence'] = 'No'
                        no_entry['am_odds'] = self._parse_american_odds(game.get('no_odds', ''))
                        eternity_data.append(no_entry)
                
                elif market_type == 'double_chance':
                    # Home or Draw
                    if game.get('home_or_draw_odds'):
                        hd_entry = entry.copy()
                        hd_entry['bet_occurence'] = 'Home or Draw'
                        hd_entry['am_odds'] = self._parse_american_odds(game.get('home_or_draw_odds', ''))
                        eternity_data.append(hd_entry)
                    
                    # Home or Away
                    if game.get('home_or_away_odds'):
                        ha_entry = entry.copy()
                        ha_entry['bet_occurence'] = 'Home or Away'
                        ha_entry['am_odds'] = self._parse_american_odds(game.get('home_or_away_odds', ''))
                        eternity_data.append(ha_entry)
                    
                    # Draw or Away
                    if game.get('draw_or_away_odds'):
                        da_entry = entry.copy()
                        da_entry['bet_occurence'] = 'Draw or Away'
                        da_entry['am_odds'] = self._parse_american_odds(game.get('draw_or_away_odds', ''))
                        eternity_data.append(da_entry)
                
                elif market_type == 'goalscorers':
                    # Each goalscorer gets a separate entry
                    for scorer in game.get('goalscorers', []):
                        scorer_entry = entry.copy()
                        scorer_entry['bet_player'] = scorer.get('player', '')
                        scorer_entry['am_odds'] = self._parse_american_odds(scorer.get('odds', ''))
                        scorer_entry['bet_occurence'] = 'Anytime'  # Could be 'First', 'Last', or 'Anytime'
                        eternity_data.append(scorer_entry)
                
                elif market_type == 'players_to_be_booked':
                    # Each player gets a separate entry
                    for player in game.get('players', []):
                        player_entry = entry.copy()
                        player_entry['bet_player'] = player.get('player', '')
                        player_entry['am_odds'] = self._parse_american_odds(player.get('odds', ''))
                        player_entry['bet_occurence'] = 'To be Booked'
                        eternity_data.append(player_entry)

        return eternity_data
    
    def _get_team_abbreviation(self, team_name: str) -> str:
        """Generate a 3-4 letter abbreviation for a team name"""
        if not team_name:
            return ''
        
        # Remove common suffixes
        team_name = team_name.replace(' FC', '').replace(' United', '').replace(' City', '')
        
        # Split into words
        words = team_name.split()
        
        if len(words) == 1:
            # Single word - take first 3-4 characters
            return words[0][:4].upper()
        elif len(words) == 2:
            # Two words - take first 2 chars of first word + first char of second
            return (words[0][:2] + words[1][:1]).upper()
        else:
            # Three or more words - take first char of each of first 3 words
            return ''.join([w[0] for w in words[:3]]).upper()
    
    def _parse_american_odds(self, odds_str: str) -> float:
        """Parse American odds string to float"""
        if not odds_str:
            return None
        
        try:
            # Remove '+' sign if present
            odds_str = odds_str.replace('+', '')
            return float(odds_str)
        except:
            return None

    def save_eternity_format(self, filename: str):
        """Save in Eternity format"""
        data = self.to_eternity_format()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


async def collect_soccer_data():
    """Main function to collect soccer data from bet365"""
    
    # Define all markets for Top Leagues (J99)
    top_leagues_markets = [
        {
            'name': 'Full Time Result',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G40/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G40/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'To Qualify',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G1094/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G1094/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'Both Teams to Score',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G10150/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G10150/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'Result/Both Teams to Score',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G50404/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G50404/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'Double Chance',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G10114/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G10114/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'Goalscorers',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G45/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G45/J99/Q1/F^2002',
            'region': 'Top Leagues'
        },
        {
            'name': 'Players to be Booked',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G50134/J99/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G50134/J99/Q1/F^2002',
            'region': 'Top Leagues'
        }
    ]

    # Define all markets for United Kingdom (J1)
    uk_markets = [
        {
            'name': 'Full Time Result',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G40/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G40/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'To Qualify',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G1094/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G1094/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'Both Teams to Score',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G10150/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G10150/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'Result/Both Teams to Score',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G50404/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G50404/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'Double Chance',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G10114/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G10114/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'Goalscorers',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G45/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G45/J1/Q1/F^2002',
            'region': 'United Kingdom'
        },
        {
            'name': 'Players to be Booked',
            'url': 'https://www.on.bet365.ca/#/AC/B1/C1/D1002/G50134/J1/Q1/F^2002',
            'hash': '/AC/B1/C1/D1002/G50134/J1/Q1/F^2002',
            'region': 'United Kingdom'
        }
    ]

    # Combine all markets
    all_markets = top_leagues_markets + uk_markets

    async with async_playwright() as playwright:
        # Use chrome_helper to set up browser (works on Windows and Ubuntu)
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome browser")
            return False
        try:
