"""
NFL Data Collection - Multiple Markets
Collects NFL betting data from bet365 including:
- Game Lines (Spread, Total, Money Line)
- Alternative Spreads and Totals
- Touchdown Scorers
- Player Props (Passing, Receiving, Rushing)
- Team Props
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from patchright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.helpers.chrome_helper import setup_chrome_browser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NFLParser:
    """Parse bet365 NFL data"""

    def __init__(self):
        self.all_games = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
            'touchdown_scorers': [],
            'passing_yards': [],
            'passing_touchdowns': [],
            'receiving_yards': [],
            'rushing_yards': [],
            'team_totals': [],
            'futures': []
        }

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

    def _fractional_to_american(self, fractional: str) -> str:
        """Convert fractional odds to American odds format"""
        try:
            if '/' not in fractional:
                return fractional
            numerator, denominator = map(int, fractional.split('/'))
            if numerator == 0 or denominator == 0:
                return fractional
            decimal = (numerator / denominator) + 1
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

    def parse_game_lines(self, body: str) -> List[Dict]:
        """Parse main game lines (spread, total, moneyline)"""
        games = []
        fixtures = {}
        current_fixture = None
        current_market = None
        spreads = {}
        totals = {}
        moneylines = {}
        
        for line in body.split('|'):
            # Parse game fixture info from PA;ID=PC lines
            if line.startswith('PA;ID=PC') and 'FD=' in line:
                participant = self._parse_participant(line[3:])
                fixture_id = participant.get('FI')
                if fixture_id:
                    fixtures[fixture_id] = {
                        'fixture_id': fixture_id,
                        'matchup': participant.get('FD', participant.get('NA', '')),
                        'date': self._parse_date(participant.get('BC', '')),
                        'betlink': f'https://www.on.bet365.ca/#/AC/B12/C20426855/D19/E{fixture_id}/F19/'
                    }
            
            # Identify market type and current fixture
            if line.startswith('MA;ID=M1441'):
                parts = line.split(';')
                for part in parts:
                    if part.startswith('NA='):
                        market_name = part[3:]
                        if 'Spread' in market_name:
                            current_market = 'spread'
                        break
                    if part.startswith('FI='):
                        current_fixture = part[3:]
                        
            elif line.startswith('MA;ID=M1442'):
                parts = line.split(';')
                for part in parts:
                    if part.startswith('NA='):
                        market_name = part[3:]
                        if 'Total' in market_name:
                            current_market = 'total'
                        break
                    if part.startswith('FI='):
                        current_fixture = part[3:]
                        
            elif line.startswith('MA;ID=M936'):
                parts = line.split(';')
                for part in parts:
                    if part.startswith('NA='):
                        market_name = part[3:]
                        if 'Money' in market_name:
                            current_market = 'moneyline'
                        break
                    if part.startswith('FI='):
                        current_fixture = part[3:]

            # Parse participant data (odds) for Spread market
            if current_market == 'spread' and line.startswith('PA;ID=') and 'HD=' in line:
                participant = self._parse_participant(line[3:])
                fixture_id = participant.get('FI')
                odds = participant.get('OD', '')
                if odds and fixture_id:
                    if fixture_id not in spreads:
                        spreads[fixture_id] = []
                    spreads[fixture_id].append({
                        'handicap': participant.get('HD'),
                        'odds': self._fractional_to_american(odds)
                    })
            
            # Parse participant data (odds) for Total market  
            elif current_market == 'total' and line.startswith('PA;ID=') and 'HD=' in line:
                participant = self._parse_participant(line[3:])
                # Use OI (origin ID) instead of FI for totals
                fixture_id = participant.get('OI', participant.get('FI'))
                line_value = participant.get('HD', '')
                odds = participant.get('OD', '')
                if odds and line_value and fixture_id:
                    if fixture_id not in totals:
                        totals[fixture_id] = []
                    totals[fixture_id].append({
                        'line': line_value,
                        'odds': self._fractional_to_american(odds)
                    })
            
            # Parse participant data (odds) for Moneyline market
            elif current_market == 'moneyline' and line.startswith('PA;ID=') and 'OD=' in line:
                participant = self._parse_participant(line[3:])
                # Use OI (origin ID) instead of FI for moneylines
                fixture_id = participant.get('OI', participant.get('FI'))
                odds = participant.get('OD', '')
                if odds and fixture_id:
                    if fixture_id not in moneylines:
                        moneylines[fixture_id] = []
                    moneylines[fixture_id].append({
                        'odds': self._fractional_to_american(odds)
                    })

        # Combine all data into games
        for fixture_id, fixture_info in fixtures.items():
            game = fixture_info.copy()
            
            # Add spread data if available
            if fixture_id in spreads and len(spreads[fixture_id]) >= 2:
                game['spread'] = {
                    'away': spreads[fixture_id][0],
                    'home': spreads[fixture_id][1]
                }
            
            # Add total data if available
            if fixture_id in totals:
                over_under = [t for t in totals[fixture_id]]
                if len(over_under) >= 2:
                    game['total'] = {
                        'line': over_under[0]['line'].replace('O ', '').replace('U ', ''),
                        'over_odds': over_under[0]['odds'],
                        'under_odds': over_under[1]['odds']
                    }
            
            # Add moneyline data if available
            if fixture_id in moneylines and len(moneylines[fixture_id]) >= 2:
                game['moneyline'] = {
                    'away': moneylines[fixture_id][0]['odds'],
                    'home': moneylines[fixture_id][1]['odds']
                }
            
            games.append(game)
        
        return games

    def parse_response(self, body: str, market_name: str) -> Dict:
        """Parse response based on market type"""
        result = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
            'touchdown_scorers': [],
            'passing_yards': [],
            'passing_touchdowns': [],
            'receiving_yards': [],
            'rushing_yards': [],
            'team_totals': [],
            'futures': []
        }

        # Extract body from JSON if needed
        try:
            json_data = json.loads(body)
            if isinstance(json_data, dict):
                for key, value in json_data.items():
                    if isinstance(value, str) and '|' in value:
                        body = value
                        break
                if '|' not in body:
                    body = json.dumps(json_data)
        except:
            pass

        # Parse based on market type
        if market_name == 'Game Lines':
            result['game_lines'] = self.parse_game_lines(body)
        elif market_name == 'Alternative Spread':
            result['alt_spreads'] = self._parse_alternative_lines(body, 'spread')
        elif market_name == 'Alternative Total':
            result['alt_totals'] = self._parse_alternative_lines(body, 'total')
        elif market_name == 'Touchdown Scorers':
            result['touchdown_scorers'] = self._parse_player_props(body, 'touchdown')
        elif market_name == 'Passing Yards':
            result['passing_yards'] = self._parse_player_props(body, 'passing_yards')
        elif market_name == 'Passing Touchdowns':
            result['passing_touchdowns'] = self._parse_player_props(body, 'passing_tds')
        elif market_name == 'Receiving Yards':
            result['receiving_yards'] = self._parse_player_props(body, 'receiving_yards')
        elif market_name == 'Rushing Yards':
            result['rushing_yards'] = self._parse_player_props(body, 'rushing_yards')
        elif market_name == 'Team Points':
            result['team_totals'] = self._parse_player_props(body, 'team_points')
        elif market_name in ['To Win Super Bowl', 'To Win Conference', 'To Win Division', 'Regular Season Wins', 'To Make Playoffs', 'To Make NFL Playoffs', 'MVP', 'Regular Season Awards']:
            # Generate betlink based on market
            market_codes = {
                'To Win Super Bowl': '113924249',
                'To Win Conference': '114762810',
                'To Win Division': '115506657',
                'Regular Season Wins': '116716430',
                'To Make Playoffs': '117787900',
                'To Make NFL Playoffs': '117788729',
                'MVP': '114655247',
                'Regular Season Awards': '114759348'
            }
            market_code = market_codes.get(market_name, '113924249')
            betlink = f'https://www.on.bet365.ca/#/AC/B12/C21027846/D1/E{market_code}/F2/'
            result['futures'] = self.parse_futures(body, market_name, betlink)

        return result
    
    def _parse_alternative_lines(self, body: str, line_type: str) -> List[Dict]:
        """Parse alternative spread/total lines"""
        lines = []
        current_game = None
        current_team = None
        
        for line in body.split('|'):
            # Get game info
            if 'MG;ID=G' in line and 'FI=' in line:
                parts = line.split(';')
                game_info = {}
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        game_info[key] = value
                
                if 'NA' in game_info and 'BC' in game_info:
                    fixture_id = game_info.get('FI', '')
                    current_game = {
                        'fixture_id': fixture_id,
                        'matchup': game_info.get('NA', ''),
                        'date': self._parse_date(game_info.get('BC', '')),
                        'betlink': f'https://www.on.bet365.ca/#/AC/B12/C20426855/D19/E{fixture_id}/F19/'
                    }
            
            # Get team name
            if 'MA;ID=M' in line and 'NA=' in line:
                parts = line.split(';')
                for part in parts:
                    if part.startswith('NA='):
                        current_team = part[3:]
                        break
            
            # Get participant lines
            if line.startswith('PA;ID=') and current_game and current_team:
                participant = self._parse_participant(line[3:])
                line_value = participant.get('NA', '')
                odds = participant.get('OD', '')
                
                if line_value and odds:
                    lines.append({
                        'fixture_id': current_game['fixture_id'],
                        'matchup': current_game['matchup'],
                        'date': current_game['date'],
                        'betlink': current_game['betlink'],
                        'team': current_team,
                        'line': line_value,
                        'odds': self._fractional_to_american(odds)
                    })
        
        return lines
    
    def _parse_player_props(self, body: str, prop_type: str) -> List[Dict]:
        """Parse player prop markets"""
        props = []
        current_game = None
        current_market = None
        
        for line in body.split('|'):
            # Get game info
            if 'MG;ID=G' in line and 'FI=' in line:
                parts = line.split(';')
                game_info = {}
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        game_info[key] = value
                
                if 'NA' in game_info:
                    fixture_id = game_info.get('FI', '')
                    current_game = {
                        'fixture_id': fixture_id,
                        'matchup': game_info.get('NA', ''),
                        'date': self._parse_date(game_info.get('BC', '')),
                        'betlink': f'https://www.on.bet365.ca/#/AC/B12/C20426855/D19/E{fixture_id}/F19/'
                    }
            
            # Get market name (player name usually)
            if 'MA;NA=' in line:
                parts = line.split(';')
                for part in parts:
                    if part.startswith('NA='):
                        current_market = part[3:]
                        break
            
            # Get participant lines
            if line.startswith('PA;ID=') and current_game:
                participant = self._parse_participant(line[3:])
                line_value = participant.get('NA', '')
                odds = participant.get('OD', '')
                
                if odds:
                    props.append({
                        'fixture_id': current_game.get('fixture_id', ''),
                        'matchup': current_game.get('matchup', ''),
                        'date': current_game.get('date', ''),
                        'betlink': current_game.get('betlink', ''),
                        'player_or_market': current_market or '',
                        'line': line_value,
                        'odds': self._fractional_to_american(odds),
                        'prop_type': prop_type
                    })
        
        return props
    
    def parse_futures(self, body: str, market_name: str, betlink: str) -> List[Dict]:
        """Parse NFL futures markets (Super Bowl winner, Conference, Division, etc.)"""
        futures = []
        
        for line in body.split('|'):
            # Parse participant/selection data
            if line.startswith('PA;'):
                participant = self._parse_participant(line[3:])
                selection = participant.get('NA', '')
                odds = participant.get('OD', '')
                participant_id = participant.get('ID', '')
                
                if odds and selection:
                    futures.append({
                        'market': market_name,
                        'selection': selection,
                        'participant_id': participant_id,
                        'odds': self._fractional_to_american(odds),
                        'odds_raw': odds,
                        'betlink': betlink
                    })
        
        return futures
    
    def add_to_collection(self, parsed: Dict):
        """Add parsed data to collection"""
        for key in self.all_games.keys():
            self.all_games[key].extend(parsed.get(key, []))
    
    def get_summary(self) -> str:
        """Get summary of parsed data"""
        # Count actual betting options from game_lines
        num_games = len(self.all_games['game_lines'])
        
        # Count spreads, totals, moneylines from game_lines
        spreads = sum(1 for g in self.all_games['game_lines'] if g.get('spread'))
        totals = sum(1 for g in self.all_games['game_lines'] if g.get('total'))
        moneylines = sum(1 for g in self.all_games['game_lines'] if g.get('moneyline'))
        
        # Count other markets
        alt_spreads = len(self.all_games['alt_spreads'])
        alt_totals = len(self.all_games['alt_totals'])
        td_props = len(self.all_games['touchdown_scorers'])
        pass_yds = len(self.all_games['passing_yards'])
        pass_tds = len(self.all_games['passing_touchdowns'])
        rec_yds = len(self.all_games['receiving_yards'])
        rush_yds = len(self.all_games['rushing_yards'])
        team_pts = len(self.all_games['team_totals'])
        futures = len(self.all_games['futures'])
        
        summary_parts = [
            f"{num_games} Games",
            f"{spreads} Spreads",
            f"{totals} Totals",
            f"{moneylines} Moneylines"
        ]
        
        # Add other markets if they exist
        if alt_spreads > 0:
            summary_parts.append(f"{alt_spreads} Alt Spreads")
        if alt_totals > 0:
            summary_parts.append(f"{alt_totals} Alt Totals")
        if futures > 0:
            summary_parts.append(f"{futures} Futures")
        if td_props > 0:
            summary_parts.append(f"{td_props} TD Props")
        if pass_yds > 0:
            summary_parts.append(f"{pass_yds} Pass Yds")
        if pass_tds > 0:
            summary_parts.append(f"{pass_tds} Pass TDs")
        if rec_yds > 0:
            summary_parts.append(f"{rec_yds} Rec Yds")
        if rush_yds > 0:
            summary_parts.append(f"{rush_yds} Rush Yds")
        if team_pts > 0:
            summary_parts.append(f"{team_pts} Team Points")
        
        return ", ".join(summary_parts)
    
    def to_optic_odds_format(self) -> Dict:
        """Convert parsed data to Optic Odds API format"""
        from datetime import datetime
        games_data = []
        
        # Process Game Lines data
        for game in self.all_games.get('game_lines', []):
            fixture_id = game.get('fixture_id', '')
            matchup = game.get('matchup', '')
            date = game.get('date', '')
            betlink = game.get('betlink', '')
            
            # Parse team names from matchup
            teams = matchup.split(' @ ') if ' @ ' in matchup else matchup.split(' vs ')
            away_team = teams[0].strip() if len(teams) > 0 else ''
            home_team = teams[1].strip() if len(teams) > 1 else ''
            
            # Convert date to ISO format
            try:
                dt = datetime.strptime(date, '%Y-%m-%d %H:%M')
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except:
                iso_date = date
            
            # Build odds array
            odds = []
            timestamp = datetime.now().timestamp()
            
            # Spread odds
            spread_data = game.get('spread', {})
            if spread_data:
                away_spread = spread_data.get('away', {})
                home_spread = spread_data.get('home', {})
                
                if away_spread:
                    odds.append({
                        "id": f"{fixture_id}:bet365:spread:{away_team.lower().replace(' ', '_')}_{away_spread.get('handicap', '')}",
                        "sportsbook": "Bet365",
                        "market": "Point Spread",
                        "name": f"{away_team} {away_spread.get('handicap', '')}",
                        "is_main": True,
                        "selection": away_team,
                        "normalized_selection": away_team.lower().replace(' ', '_'),
                        "market_id": "spread",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": int(away_spread.get('odds', '0').replace('+', '').replace('-', '-') or 0),
                        "timestamp": timestamp,
                        "grouping_key": f"default:{away_spread.get('handicap', '')}",
                        "points": float(away_spread.get('handicap', '0').replace('+', '').replace('-', '-') or 0),
                        "betlink": betlink,
                        "limits": None
                    })
                
                if home_spread:
                    odds.append({
                        "id": f"{fixture_id}:bet365:spread:{home_team.lower().replace(' ', '_')}_{home_spread.get('handicap', '')}",
                        "sportsbook": "Bet365",
                        "market": "Point Spread",
                        "name": f"{home_team} {home_spread.get('handicap', '')}",
                        "is_main": True,
                        "selection": home_team,
                        "normalized_selection": home_team.lower().replace(' ', '_'),
                        "market_id": "spread",
                        "selection_line": None,
                        "player_id": None,
                        "team_id": None,
                        "price": int(home_spread.get('odds', '0').replace('+', '').replace('-', '-') or 0),
                        "timestamp": timestamp,
                        "grouping_key": f"default:{home_spread.get('handicap', '')}",
                        "points": float(home_spread.get('handicap', '0').replace('+', '').replace('-', '-') or 0),
                        "betlink": betlink,
                        "limits": None
                    })
            
            # Total odds
            total_data = game.get('total', {})
            if total_data:
                line = total_data.get('line', '0')
                over_odds = total_data.get('over_odds', '0')
                under_odds = total_data.get('under_odds', '0')
                
                odds.append({
                    "id": f"{fixture_id}:bet365:total:over_{line}",
                    "sportsbook": "Bet365",
                    "market": "Total Points",
                    "name": f"Over {line}",
                    "is_main": True,
                    "selection": "",
                    "normalized_selection": "",
                    "market_id": "total",
                    "selection_line": "over",
                    "player_id": None,
                    "team_id": None,
                    "price": int(over_odds.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": f"default:{line}",
                    "points": float(line),
                    "betlink": betlink,
                    "limits": None
                })
                
                odds.append({
                    "id": f"{fixture_id}:bet365:total:under_{line}",
                    "sportsbook": "Bet365",
                    "market": "Total Points",
                    "name": f"Under {line}",
                    "is_main": True,
                    "selection": "",
                    "normalized_selection": "",
                    "market_id": "total",
                    "selection_line": "under",
                    "player_id": None,
                    "team_id": None,
                    "price": int(under_odds.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": f"default:{line}",
                    "points": float(line),
                    "betlink": betlink,
                    "limits": None
                })
            
            # Moneyline odds
            moneyline_data = game.get('moneyline', {})
            if moneyline_data:
                away_ml = moneyline_data.get('away', '0')
                home_ml = moneyline_data.get('home', '0')
                
                odds.append({
                    "id": f"{fixture_id}:bet365:moneyline:{away_team.lower().replace(' ', '_')}",
                    "sportsbook": "Bet365",
                    "market": "Moneyline",
                    "name": away_team,
                    "is_main": True,
                    "selection": away_team,
                    "normalized_selection": away_team.lower().replace(' ', '_'),
                    "market_id": "moneyline",
                    "selection_line": None,
                    "player_id": None,
                    "team_id": None,
                    "price": int(away_ml.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": "default",
                    "points": None,
                    "betlink": betlink,
                    "limits": None
                })
                
                odds.append({
                    "id": f"{fixture_id}:bet365:moneyline:{home_team.lower().replace(' ', '_')}",
                    "sportsbook": "Bet365",
                    "market": "Moneyline",
                    "name": home_team,
                    "is_main": True,
                    "selection": home_team,
                    "normalized_selection": home_team.lower().replace(' ', '_'),
                    "market_id": "moneyline",
                    "selection_line": None,
                    "player_id": None,
                    "team_id": None,
                    "price": int(home_ml.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": "default",
                    "points": None,
                    "betlink": betlink,
                    "limits": None
                })
            
            # Build game object
            game_obj = {
                "id": fixture_id,
                "game_id": f"nfl-{fixture_id}",
                "start_date": iso_date,
                "home_competitors": [
                    {
                        "id": None,
                        "name": home_team,
                        "abbreviation": home_team.split()[-1].upper() if home_team else "",
                        "logo": None
                    }
                ],
                "away_competitors": [
                    {
                        "id": None,
                        "name": away_team,
                        "abbreviation": away_team.split()[-1].upper() if away_team else "",
                        "logo": None
                    }
                ],
                "home_team_display": home_team,
                "away_team_display": away_team,
                "status": "unplayed",
                "is_live": False,
                "sport": {
                    "id": "american_football",
                    "name": "American Football"
                },
                "league": {
                    "id": "nfl",
                    "name": "NFL"
                },
                "tournament": None,
                "odds": odds
            }
            
            games_data.append(game_obj)
        
        return {"data": games_data}
    
    def to_eternity_format(self) -> Dict:
        """Convert parsed data to Eternity API format"""
        from datetime import datetime
        bets_data = []
        
        # Process Game Lines data
        for game in self.all_games.get('game_lines', []):
            fixture_id = game.get('fixture_id', '')
            matchup = game.get('matchup', '')
            date = game.get('date', '')
            betlink = game.get('betlink', '')
            
            # Parse team names from matchup
            teams = matchup.split(' @ ') if ' @ ' in matchup else matchup.split(' vs ')
            away_team = teams[0].strip() if len(teams) > 0 else ''
            home_team = teams[1].strip() if len(teams) > 1 else ''
            
            # Generate team abbreviations
            away_brief = ''.join([word[0] for word in away_team.split()]).upper() if away_team else ''
            home_brief = ''.join([word[0] for word in home_team.split()]).upper() if home_team else ''
            
            # Convert date to ISO format
            try:
                dt = datetime.strptime(date, '%Y-%m-%d %H:%M')
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except:
                iso_date = date
            
            # Spread odds
            spread_data = game.get('spread', {})
            if spread_data:
                away_spread = spread_data.get('away', {})
                home_spread = spread_data.get('home', {})
                
                if away_spread:
                    handicap = away_spread.get('handicap', '')
                    odds_value = away_spread.get('odds', '0')
                    bets_data.append({
                        "league": "NFL",
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": "Bet365",
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": float(handicap.replace('+', '').replace('-', '-') or 0),
                        "am_odds": float(odds_value.replace('+', '').replace('-', '-') or 0),
                        "home_short": home_brief,
                        "bet_team": away_team,
                        "home": home_team,
                        "market": "Point Spread",
                        "bet_occurence": None,
                        "internal_betlink": betlink,
                        "away_short": away_brief,
                        "home_brief": home_brief,
                        "away": away_team,
                        "betlink": betlink
                    })
                
                if home_spread:
                    handicap = home_spread.get('handicap', '')
                    odds_value = home_spread.get('odds', '0')
                    bets_data.append({
                        "league": "NFL",
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": "Bet365",
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": float(handicap.replace('+', '').replace('-', '-') or 0),
                        "am_odds": float(odds_value.replace('+', '').replace('-', '-') or 0),
                        "home_short": home_brief,
                        "bet_team": home_team,
                        "home": home_team,
                        "market": "Point Spread",
                        "bet_occurence": None,
                        "internal_betlink": betlink,
                        "away_short": away_brief,
                        "home_brief": home_brief,
                        "away": away_team,
                        "betlink": betlink
                    })
            
            # Total odds
            total_data = game.get('total', {})
            if total_data:
                line = total_data.get('line', '0')
                over_odds = total_data.get('over_odds', '0')
                under_odds = total_data.get('under_odds', '0')
                
                bets_data.append({
                    "league": "NFL",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": float(line),
                    "am_odds": float(over_odds.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": None,
                    "home": home_team,
                    "market": "Total Points",
                    "bet_occurence": "Over",
                    "internal_betlink": betlink,
                    "away_short": away_brief,
                    "home_brief": home_brief,
                    "away": away_team,
                    "betlink": betlink
                })
                
                bets_data.append({
                    "league": "NFL",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": float(line),
                    "am_odds": float(under_odds.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": None,
                    "home": home_team,
                    "market": "Total Points",
                    "bet_occurence": "Under",
                    "internal_betlink": betlink,
                    "away_short": away_brief,
                    "home_brief": home_brief,
                    "away": away_team,
                    "betlink": betlink
                })
            
            # Moneyline odds
            moneyline_data = game.get('moneyline', {})
            if moneyline_data:
                away_ml = moneyline_data.get('away', '0')
                home_ml = moneyline_data.get('home', '0')
                
                bets_data.append({
                    "league": "NFL",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": None,
                    "am_odds": float(away_ml.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": away_team,
                    "home": home_team,
                    "market": "Moneyline",
                    "bet_occurence": None,
                    "internal_betlink": betlink,
                    "away_short": away_brief,
                    "home_brief": home_brief,
                    "away": away_team,
                    "betlink": betlink
                })
                
                bets_data.append({
                    "league": "NFL",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": None,
                    "am_odds": float(home_ml.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": home_team,
                    "home": home_team,
                    "market": "Moneyline",
                    "bet_occurence": None,
                    "internal_betlink": betlink,
                    "away_short": away_brief,
                    "home_brief": home_brief,
                    "away": away_team,
                    "betlink": betlink
                })
        
        return {"data": bets_data}
    
    def save_to_file(self, filepath: str):
        """Save parsed data to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.all_games, f, indent=2, ensure_ascii=False)
    
    def save_optic_odds_format(self, filepath: str):
        """Save data in Optic Odds API format"""
        optic_data = self.to_optic_odds_format()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(optic_data, f, indent=2, ensure_ascii=False)
    
    def save_eternity_format(self, filepath: str):
        """Save data in Eternity API format"""
        eternity_data = self.to_eternity_format()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(eternity_data, f, indent=2, ensure_ascii=False)
    
    def save_futures_separately(self, filepath: str):
        """Save NFL futures data separately"""
        futures_data = {
            "futures": self.all_games.get('futures', []),
            "total_futures": len(self.all_games.get('futures', []))
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(futures_data, f, indent=2, ensure_ascii=False)

async def collect_nfl_data():
    """NFL data collection with multiple markets"""
    import subprocess
    import shutil
    from pathlib import Path
    
    # Initialize parser
    parser = NFLParser()
    
    # Define markets to collect
    markets = [
        {'code': '1441', 'name': 'Game Lines', 'hash': '#/AC/B12/C20426855/D48/E1441/F36/N0/', 'parser': 'game_lines'},
        {'code': '120504', 'name': 'Alternative Spread', 'hash': '#/AC/B12/C20426855/D47/E120504/F47/N0/', 'parser': 'alt_lines'},
        {'code': '120508', 'name': 'Alternative Total', 'hash': '#/AC/B12/C20426855/D47/E120508/F47/N0/', 'parser': 'alt_lines'},
        {'code': '120591', 'name': 'Touchdown Scorers', 'hash': '#/AC/B12/C20426855/D47/E120591/F47/N0/', 'parser': 'player_props'},
        {'code': '121155', 'name': 'Passing Yards', 'hash': '#/AC/B12/C20426855/D47/E121155/F47/N0/', 'parser': 'player_props'},
        {'code': '121156', 'name': 'Passing Touchdowns', 'hash': '#/AC/B12/C20426855/D47/E121156/F47/N0/', 'parser': 'player_props'},
        {'code': '121158', 'name': 'Receiving Yards', 'hash': '#/AC/B12/C20426855/D47/E121158/F47/N0/', 'parser': 'player_props'},
        {'code': '121161', 'name': 'Rushing Yards', 'hash': '#/AC/B12/C20426855/D47/E121161/F47/N0/', 'parser': 'player_props'},
        {'code': '121205', 'name': 'Team Points', 'hash': '#/AC/B12/C20426855/D47/E121205/F47/N0/', 'parser': 'player_props'},
        {'code': '113924249', 'name': 'To Win Super Bowl', 'hash': '#/AC/B12/C21027846/D1/E113924249/F2/', 'parser': 'futures'},
        {'code': '114762810', 'name': 'To Win Conference', 'hash': '#/AC/B12/C21027846/D1/E114762810/F2/', 'parser': 'futures'},
        {'code': '115506657', 'name': 'To Win Division', 'hash': '#/AC/B12/C21027846/D1/E115506657/F2/', 'parser': 'futures'},
        {'code': '116716430', 'name': 'Regular Season Wins', 'hash': '#/AC/B12/C21027846/D1/E116716430/F2/', 'parser': 'futures'},
        {'code': '117787900', 'name': 'To Make Playoffs', 'hash': '#/AC/B12/C21027846/D1/E117787900/F2/', 'parser': 'futures'},
        {'code': '117788729', 'name': 'To Make NFL Playoffs', 'hash': '#/AC/B12/C21027846/D1/E117788729/F2/', 'parser': 'futures'},
        {'code': '114655247', 'name': 'MVP', 'hash': '#/AC/B12/C21027846/D1/E114655247/F2/', 'parser': 'futures'},
        {'code': '114759348', 'name': 'Regular Season Awards', 'hash': '#/AC/B12/C21027846/D1/E114759348/F2/', 'parser': 'futures'},
    ]
    
    async with async_playwright() as playwright:
        # Use chrome_helper to set up browser (works on Windows and Ubuntu)
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome browser")
            return False
        try:
            browser = await playwright.chromium.connect_over_cdp('http://localhost:9222')
            logger.info("✓ Connected to existing Chrome instance on port 9222")
        except Exception as connect_error:
            logger.info("⚠️ No Chrome found on port 9222, starting new instance...")
            temp_dir = Path(f"C:/Users/User/AppData/Local/Temp/chrome_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
            
            chrome_paths = [
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            ]
            
            chrome_exe = None
            for path in chrome_paths:
                if Path(path).exists():
                    chrome_exe = path
                    break
            
            if not chrome_exe:
                logger.error("❌ Chrome executable not found")
                return False
            
            chrome_cmd = [
                chrome_exe,
                "--remote-debugging-port=9222",
                f"--user-data-dir={temp_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-cache",
                "--start-maximized",
                "--disable-popup-blocking",
                "--new-window",
                "https://www.on.bet365.ca"
            ]
            
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                
                chrome_process = subprocess.Popen(
                    chrome_cmd,
                    shell=False,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                )
                chrome_started_by_script = True
                logger.info("✓ Chrome started")
                await asyncio.sleep(7)
                
                browser = await playwright.chromium.connect_over_cdp('http://localhost:9222')
                logger.info("✓ Connected to Chrome instance")
            except Exception as start_error:
                logger.error(f"❌ Failed to start Chrome: {start_error}")
                return False
        
        # Get page
        try:
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
                pages = context.pages
                if pages:
                    page = pages[0]
                else:
                    page = await context.new_page()
            else:
                page = await browser.new_page()
                

            # Apply anti-detection script to page
            await page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock Chrome runtime
                window.chrome = { runtime: {} };
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)

        except Exception as e:
            logger.error(f"❌ Failed to get page: {e}")
            return False

        try:
            logger.info("🏠 Going to bet365 homepage...")
            await page.goto('https://www.on.bet365.ca/', wait_until='domcontentloaded')
            await asyncio.sleep(3)

            logger.info("📜 Random scrolling for 2-3 seconds...")
            viewport = page.viewport_size or {'width': 1920, 'height': 1080}
            interaction_time = random.uniform(2, 3)
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < interaction_time:
                # Random scroll only (no clicking to avoid triggering navigation)
                scroll_amount = random.randint(50, 300)
                await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
                await asyncio.sleep(random.uniform(0.3, 0.6))
                
                # Scroll back up sometimes
                if random.random() > 0.7:
                    scroll_back = random.randint(-150, -50)
                    await page.evaluate(f'window.scrollBy(0, {scroll_back})')
                
                await asyncio.sleep(random.uniform(0.2, 0.4))

            # Wait a bit more before clicking NFL
            logger.info("⏳ Waiting before clicking NFL...")
            await asyncio.sleep(random.uniform(1, 2))

            logger.info("🏈 Clicking on NFL...")
            # Click on NFL element
            nfl_selectors = [
                'span.wn-PillItem_Text:has-text("NFL")',
                '.wn-PillItem:has-text("NFL")',
                '[alt="NFL"]'
            ]

            nfl_clicked = False
            for selector in nfl_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"✓ Clicked NFL with: {selector}")
                        nfl_clicked = True
                        break
                except:
                    continue

            if not nfl_clicked:
                logger.warning("⚠️ Could not click NFL, navigating directly...")
                await page.goto('https://www.on.bet365.ca/#/AC/B12/C20426855/D48/E1441/F36/')

            await asyncio.sleep(2)

            # Collect data from each market
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Collecting {len(markets)} NFL Markets")
            logger.info(f"{'='*60}\n")
            
            all_captured_data = []
            
            for index, market in enumerate(markets, 1):
                logger.info(f"[{index}/{len(markets)}] Collecting: {market['name']}")
                
                captured_data = []
                
                async def capture_response(response):
                    if 'bet365' in response.url and response.status == 200:
                        try:
                            body = await response.text()
                            if len(body) > 100:
                                captured_data.append({
                                    'url': response.url,
                                    'body': body,
                                    'size': len(body),
                                    'market': market['name'],
                                    'timestamp': datetime.now().isoformat()
                                })
                        except:
                            pass
                
                page.on('response', capture_response)
                
                # Regular market navigation (including futures)
                await page.evaluate(f"window.location.hash = '{market['hash']}'")
                await asyncio.sleep(random.uniform(1.5, 2.5))
                
                # Scroll to load data
                try:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(random.uniform(0.3, 0.5))
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(random.uniform(0.3, 0.5))
                except:
                    pass
                
                page.remove_listener('response', capture_response)
                
                # Parse captured data
                for response in captured_data:
                    parsed = parser.parse_response(response['body'], market['name'])
                    parser.add_to_collection(parsed)
                
                all_captured_data.extend(captured_data)
                
                logger.info(f"  ✓ Captured {len(captured_data)} responses, {sum(r['size'] for r in captured_data):,} bytes")
                
                # Random delay between markets
                await asyncio.sleep(random.uniform(0.5, 1.0))

            # Save all data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(f'nfl_data_{timestamp}')
            output_dir.mkdir(exist_ok=True)

            # Save raw captured data
            raw_data_file = output_dir / 'captured_data.json'
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(all_captured_data, f, indent=2, ensure_ascii=False)

            # Save parsed data (original format)
            parsed_data_file = output_dir / 'parsed_nfl_data.json'
            parser.save_to_file(str(parsed_data_file))
            
            # Save data in Optic Odds format
            optic_odds_file = output_dir / 'nfl_optic_odds_format.json'
            parser.save_optic_odds_format(str(optic_odds_file))
            
            # Save data in Eternity format
            eternity_file = output_dir / 'nfl_eternity_format.json'
            parser.save_eternity_format(str(eternity_file))
            
            # Save futures separately
            futures_file = output_dir / 'nfl_futures.json'
            parser.save_futures_separately(str(futures_file))

            # Save summary
            summary = {
                'timestamp': timestamp,
                'total_markets': len(markets),
                'total_responses': len(all_captured_data),
                'total_bytes': sum(r['size'] for r in all_captured_data),
                'summary': parser.get_summary(),
                'markets_collected': [m['name'] for m in markets]
            }
            
            summary_file = output_dir / 'summary.json'
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            logger.info(f"\n{'='*60}")
            logger.info(f"✅ NFL Data Collection Complete")
            logger.info(f"{'='*60}")
            logger.info(f"Total Markets: {len(markets)}")
            logger.info(f"Total Responses: {len(all_captured_data)}")
            logger.info(f"Total Data: {sum(r['size'] for r in all_captured_data):,} bytes")
            logger.info(f"\n📁 Output Directory: {output_dir}/")
            logger.info(f"  - Raw Data: {raw_data_file.name}")
            logger.info(f"  - Parsed Data: {parsed_data_file.name}")
            logger.info(f"  - Optic Odds Format: {optic_odds_file.name}")
            logger.info(f"  - Eternity Format: {eternity_file.name}")
            logger.info(f"  - Futures Data: {futures_file.name}")
            logger.info(f"  - Summary: {summary_file.name}")
            logger.info(f"\n{parser.get_summary()}")

            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False
        finally:
            await browser.close()
            if chrome_manager:
                chrome_manager.cleanup()
                try:
                    chrome_process.terminate()
                except:
                    pass

if __name__ == '__main__':
    asyncio.run(collect_nfl_data())