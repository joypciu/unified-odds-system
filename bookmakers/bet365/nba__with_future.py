"""
NBA Data Collection - Multiple Markets
Collects NBA betting data from bet365 including:
- Game Lines (Spread, Total, Money Line)
- Player Props (Points, Rebounds, Assists, Three Made, Points O/U, Points Low)
- Alternative Lines (Point Spread, Game Total)
- Half Markets (1st Half, 1st Quarter)
- Futures (To Win Outright, Conference, Division, etc.)
"""
import asyncio
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from patchright.async_api import async_playwright
from utils.helpers.chrome_helper import setup_chrome_browser, dismiss_bet365_popups, verify_bet365_loaded

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NBAParser:
    """Parse bet365 NBA data"""

    def __init__(self):
        self.all_games = {
            'game_lines': [],
            'points': [],
            'points_ou': [],
            'points_low': [],
            'rebounds': [],
            'assists': [],
            'three_made': [],
            'point_spread': [],
            'game_total': [],
            'first_half': [],
            'first_half_moneyline': [],
            'first_quarter': [],
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

    def parse_game_lines(self, body: str, market_name: str = 'Game Lines', all_captured_data: Optional[List[Dict]] = None) -> List[Dict]:
        """Parse game lines (spreads, totals, moneylines) from bet365 NBA response

        NBA Format (similar to NCAAB/NFL):
        - PA;ID=PC... game cards with fixture IDs
        - MA;ID=M1453;NA=Spread;FI=... (spread market header)
        - PA;ID=...;FI=...;HD=+5.5;OD=10/11; (spread odds with handicap in HD)
        - MA;ID=M1454;NA=Total;FI=... (total market header)
        - PA;ID=...;FI=...;HD=O 215.5;OD=10/11; (total odds with Over/Under in HD)
        - MA;ID=M936;NA=Money Line;FI=... (moneyline market header)
        - PA;ID=...;FI=...;OD=6/5; (moneyline odds, no HD field)
        
        Alternative format with MA;ID=C for alternative lines:
        - MA;ID=C181286;NA=Over;FI=... (Over market)
        - PA;ID=P...;NA=224.5; (line definitions)
        - PA;ID=...;OD=5/13; (odds entries)
        """
        # Define market ID mappings (similar to NCAAB/NFL)
        market_ids = {
            'Game Lines': {'spreads': 'M1453', 'totals': 'M1454', 'moneylines': 'M936'},
            '1st Half': {'spreads': 'M928', 'totals': 'M929', 'moneylines': 'M180019'},
            '1st Quarter': {'spreads': 'M941', 'totals': 'M942', 'moneylines': 'M180020'}
        }
        
        current_market_ids = market_ids.get(market_name, market_ids['Game Lines'])
        
        games = {}  # fixture_id -> game data
        sections = body.split('|')

        games = {}  # fixture_id -> game data
        sections = body.split('|')

        # First pass: Extract game cards (PA;ID=PC format) AND game headers (MG;ID=M format)
        for section in sections:
            # Game card format: PA;ID=PC...;NA=Team;N2=Team;FI=...;OI=...;BC=...;FD=Full Display;
            if section.startswith('PA;ID=PC') and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                # Use OI (original ID) as fixture_id - this matches spread/total/moneyline PA entries
                fixture_id = parts.get('OI', '') or parts.get('FI', '')
                if fixture_id and fixture_id not in games:
                    # Use FD (full display) if available, otherwise construct from NA/N2
                    matchup = parts.get('FD', '')
                    if not matchup:
                        away_team = parts.get('NA', '')
                        home_team = parts.get('N2', '')
                        matchup = f"{away_team} @ {home_team}"
                    else:
                        # Parse teams from FD
                        if ' @ ' in matchup:
                            teams = matchup.split(' @ ')
                            away_team = teams[0].strip()
                            home_team = teams[1].strip() if len(teams) > 1 else ''
                        else:
                            away_team = parts.get('NA', '')
                            home_team = parts.get('N2', '')
                    
                    bc_code = parts.get('BC', '')
                    date = self._parse_date(bc_code) if bc_code else ''

                    games[fixture_id] = {
                        'fixture_id': fixture_id,
                        'matchup': matchup,
                        'away_team': away_team,
                        'home_team': home_team,
                        'date': date,
                        'betlink': f'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E{fixture_id}/F10/',
                        'spreads': [],
                        'totals': [],
                        'moneylines': []
                    }
            
            # Game header format: MG;ID=M...;FI=...;NA=Team @ Team;BC=...;
            elif (section.startswith('MG;ID=G') or section.startswith('MG;ID=M')) and ';FI=' in section and ';NA=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                fixture_id = parts.get('FI', '')
                game_name = parts.get('NA', '')
                bc_code = parts.get('BC', '')
                
                if fixture_id and fixture_id not in games and game_name and game_name != 'Total' and game_name != '':
                    # Parse teams from matchup
                    if ' @ ' in game_name:
                        teams = game_name.split(' @ ')
                        away_team = teams[0].strip()
                        home_team = teams[1].strip() if len(teams) > 1 else ''
                    else:
                        away_team = game_name
                        home_team = ''

                    date = self._parse_date(bc_code) if bc_code else ''

                    games[fixture_id] = {
                        'fixture_id': fixture_id,
                        'matchup': game_name,
                        'away_team': away_team,
                        'home_team': home_team,
                        'date': date,
                        'betlink': f'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E{fixture_id}/F10/',
                        'spreads': [],
                        'totals': [],
                        'moneylines': []
                    }

        # Second pass: Build line value dictionary from PA;ID=P... entries (for alternative lines)
        line_values = {}  # Map PA ID (without P prefix) to line value
        for section in sections:
            # Line definition: PA;ID=P53917229;NA=224.5;
            if section.startswith('PA;ID=P') and ';NA=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val
                
                pa_id_with_p = parts.get('ID', '')
                line_value = parts.get('NA', '')
                
                # Remove P prefix to get the base ID
                if pa_id_with_p.startswith('P'):
                    pa_id = pa_id_with_p[1:]  # Remove 'P' prefix
                    line_values[pa_id] = line_value

        # Third pass: Process markets and odds using market type tracking (like NCAAB/NFL)
        current_market_type = None  # Track which market section we're currently in
        current_fixture_id = None
        current_bet_type = None  # For alternative lines: 'Over' or 'Under'

        for section in sections:
            # Market header with standard market IDs: MA;ID=M1453;NA=Spread;FI=...;
            if section.startswith('MA;ID=M') and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                market_id = parts.get('ID', '')
                current_fixture_id = parts.get('FI', '')

                # Set current market type based on market ID
                if market_id == current_market_ids['spreads']:
                    current_market_type = 'spreads'
                    current_bet_type = None
                elif market_id == current_market_ids['totals']:
                    current_market_type = 'totals'
                    current_bet_type = None
                elif market_id == current_market_ids['moneylines']:
                    current_market_type = 'moneylines'
                    current_bet_type = None
                else:
                    # Keep current market type for other market IDs within same fixture
                    pass
            
            # Alternative lines market header: MA;ID=C181286;NA=Over (or Under);FI=...;
            elif section.startswith('MA;ID=C') and ';NA=' in section and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val
                
                bet_name = parts.get('NA', '')
                current_fixture_id = parts.get('FI', '')
                
                # Set bet type if this is an Over/Under market
                if bet_name in ['Over', 'Under']:
                    current_market_type = 'totals'
                    current_bet_type = bet_name

            # Odds entry: PA;ID=...;OD=...; (not starting with PC or P)
            elif section.startswith('PA;ID=') and ';OD=' in section and not section.startswith('PA;ID=PC') and not section.startswith('PA;ID=P'):
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                pa_id = parts.get('ID', '')
                odds_raw = parts.get('OD', '')
                fixture_id = parts.get('FI', '') or parts.get('OI', '') or current_fixture_id
                suspended = parts.get('SU', '0')
                hd = parts.get('HD', '')  # Handicap field: "+5.5", "O 215.5", "U 215.5"
                na = parts.get('NA', '')  # Name field: sometimes has spread values

                # Skip suspended odds
                if suspended == '1' or not odds_raw:
                    continue

                # Get line value from PA;ID=P mapping if available
                line_value_from_map = line_values.get(pa_id, '')

                if fixture_id and fixture_id in games and current_market_type:
                    game = games[fixture_id]
                    odds_american = self.convert_odds(odds_raw)

                    if current_market_type == 'spreads':
                        # Spread: HD contains line like "+2.0" or "-5.5", or NA field
                        spread_line = hd or na
                        if spread_line and (spread_line.startswith('+') or spread_line.startswith('-')):
                            game['spreads'].append({
                                'line': spread_line,
                                'odds': odds_american,
                                'odds_raw': odds_raw
                            })

                    elif current_market_type == 'totals':
                        # Total: HD contains "O 159.5" or "U 145.0"
                        if hd and (hd.startswith('O ') or hd.startswith('U ')):
                            parts_hd = hd.split(' ', 1)
                            if len(parts_hd) == 2:
                                line_type = 'Over' if parts_hd[0] == 'O' else 'Under'
                                line_value = parts_hd[1]
                                game['totals'].append({
                                    'type': line_type,
                                    'line': line_value,
                                    'odds': odds_american,
                                    'odds_raw': odds_raw
                                })
                        # Alternative lines format with current_bet_type set
                        elif current_bet_type in ['Over', 'Under'] and line_value_from_map:
                            game['totals'].append({
                                'type': current_bet_type,
                                'line': line_value_from_map,
                                'odds': odds_american,
                                'odds_raw': odds_raw
                            })

                    elif current_market_type == 'moneylines':
                        # Moneyline: no HD field, just odds
                        game['moneylines'].append({
                            'odds': odds_american,
                            'odds_raw': odds_raw
                        })

        return list(games.values())

    def _parse_player_props(self, body: str, prop_type: str) -> List[Dict]:
        """Parse player props from bet365 response

        Format:
        - PA;ID=PC40191258;NA=LeBron James;N2=LAL Lakers;TD=43;
        - CO;ID=C170601;NA=25;SY=ipg;
        - PA;ID=40191258;FI=185334736;SU=0;OD=10/29;
        - CO;ID=C170601;NA=26;SY=ipg;
        - PA;ID=40191260;FI=185334736;SU=0;OD=33/20;
        """
        props = []
        sections = body.split('|')

        # Map to track players and their lines
        players = {}  # player_id -> {name, team, fixture_id, lines: {line_value: odds}}
        current_line = None
        current_column_index = 0
        column_lines = []  # Track all line values in order

        for section in sections:
            # Player card: PA;ID=PC40191258;NA=LeBron James;N2=LAL Lakers;
            if section.startswith('PA;ID=PC'):
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                player_id_full = parts.get('ID', '')
                if player_id_full.startswith('PC'):
                    # Remove PC prefix to get base player ID
                    player_id = player_id_full[2:]
                    players[player_id] = {
                        'player_name': parts.get('NA', ''),
                        'team_name': parts.get('N2', ''),
                        'lines': {},  # line_value -> odds
                        'fixture_id': '',
                        'odds_by_column': {}  # column_index -> odds
                    }

            # Column definition: CO;ID=C170601;NA=25;
            elif section.startswith('CO;ID='):
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                line_value = parts.get('NA', '')
                if line_value:
                    current_line = line_value
                    if current_line not in column_lines:
                        column_lines.append(current_line)
                    current_column_index = column_lines.index(current_line)

            # Odds entry: PA;ID=40191258;FI=185334736;SU=0;OD=10/29;
            elif section.startswith('PA;ID=') and not section.startswith('PA;ID=PC') and ';OD=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                odds_raw = parts.get('OD', '')
                participant_id = parts.get('ID', '')
                fixture_id = parts.get('FI', '')
                suspended = parts.get('SU', '0')

                # Skip suspended odds
                if suspended == '1' or not odds_raw:
                    continue

                if odds_raw and current_line:
                    # Find matching player by checking if participant_id contains player_id
                    for player_id, player_data in players.items():
                        if participant_id == player_id or participant_id.startswith(player_id):
                            odds_american = self.convert_odds(odds_raw)
                            
                            # Store by column index first
                            player_data['odds_by_column'][current_column_index] = {
                                'line': current_line,
                                'odds': odds_american,
                                'odds_raw': odds_raw
                            }
                            
                            if not player_data['fixture_id']:
                                player_data['fixture_id'] = fixture_id
                            break

        # Convert to list format
        for player_id, player_data in players.items():
            if player_data['odds_by_column']:  # Only include players with odds
                lines_list = []
                
                # Sort by column index to maintain order
                for col_idx in sorted(player_data['odds_by_column'].keys()):
                    odds_data = player_data['odds_by_column'][col_idx]
                    lines_list.append({
                        'line': odds_data['line'],
                        'odds': odds_data['odds'],
                        'odds_raw': odds_data['odds_raw']
                    })

                props.append({
                    'fixture_id': player_data.get('fixture_id', ''),
                    'player_name': player_data['player_name'],
                    'team_name': player_data['team_name'],
                    'prop_type': prop_type,
                    'lines': lines_list
                })

        return props

    def parse_futures(self, body: str, market_name: str, betlink: str) -> List[Dict]:
        """Parse NBA futures markets"""
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
                        'odds': self.convert_odds(odds),
                        'odds_raw': odds,
                        'betlink': betlink
                    })

        return futures

    def parse_response(self, body: str, market_name: str, market_url: str, all_captured_data: Optional[List[Dict]] = None) -> Dict:
        """Parse response based on market type"""
        result = {
            'game_lines': [],
            'points': [],
            'points_ou': [],
            'points_low': [],
            'rebounds': [],
            'assists': [],
            'three_made': [],
            'point_spread': [],
            'game_total': [],
            'first_half': [],
            'first_half_moneyline': [],
            'first_quarter': [],
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
        if market_name == 'Game Lines' or market_name == 'NBA Main Lines':
            result['game_lines'] = self.parse_game_lines(body, 'Game Lines', all_captured_data)
        elif market_name == 'Points':
            result['points'] = self._parse_player_props(body, 'points')
        elif market_name == 'Points O/U':
            result['points_ou'] = self._parse_player_props(body, 'points_ou')
        elif market_name == 'Points Low':
            result['points_low'] = self._parse_player_props(body, 'points_low')
        elif market_name == 'Rebounds':
            result['rebounds'] = self._parse_player_props(body, 'rebounds')
        elif market_name == 'Assists':
            result['assists'] = self._parse_player_props(body, 'assists')
        elif market_name == 'Three Made':
            result['three_made'] = self._parse_player_props(body, 'three_made')
        elif market_name == 'Point Spread':
            result['game_lines'] = self.parse_game_lines(body, market_name, all_captured_data)
        elif market_name == 'Game Total':
            result['game_lines'] = self.parse_game_lines(body, market_name, all_captured_data)
        elif market_name == '1st Half':
            result['first_half'] = self.parse_game_lines(body, market_name, all_captured_data)
        elif market_name == '1st Half Moneyline 3 Way':
            result['first_half_moneyline'] = self._parse_player_props(body, 'first_half_moneyline')
        elif market_name == '1st Quarter':
            result['first_quarter'] = self.parse_game_lines(body, market_name, all_captured_data)
        elif market_name in ['To Win Outright', 'To Win Conference', 'To Win Division',
                            'Division of NBA Champions League Winner', 'State of NBA Champions League Winner',
                            'Regular Season Wins']:
            result['futures'] = self.parse_futures(body, market_name, market_url)

        return result

    def add_to_collection(self, parsed: Dict):
        """Add parsed data to collection"""
        for key, value in parsed.items():
            if key not in self.all_games:
                self.all_games[key] = []
            if isinstance(value, list):
                if key == 'game_lines':
                    # Merge games by matchup name (bet365 uses different fixture IDs for same game in different markets)
                    for new_game in value:
                        matchup = new_game.get('matchup', '').strip()
                        existing_game = None
                        for game in self.all_games[key]:
                            if game.get('matchup', '').strip() == matchup and matchup:
                                existing_game = game
                                break
                        if existing_game:
                            # Merge odds
                            existing_game['spreads'].extend(new_game.get('spreads', []))
                            existing_game['totals'].extend(new_game.get('totals', []))
                            existing_game['moneylines'].extend(new_game.get('moneylines', []))
                        else:
                            self.all_games[key].append(new_game)
                else:
                    self.all_games[key].extend(value)
            else:
                self.all_games[key].append(value)

    def get_summary(self) -> str:
        """Get summary of parsed data"""
        # Count actual betting options from game_lines
        num_games = len(self.all_games['game_lines'])

        # Count spreads, totals, moneylines from game_lines
        spreads = sum(len(g.get('spreads', [])) for g in self.all_games['game_lines'])
        totals = sum(len(g.get('totals', [])) for g in self.all_games['game_lines'])
        moneylines = sum(len(g.get('moneylines', [])) for g in self.all_games['game_lines'])

        # Count other markets
        points = len(self.all_games['points'])
        points_ou = len(self.all_games['points_ou'])
        points_low = len(self.all_games['points_low'])
        rebounds = len(self.all_games['rebounds'])
        assists = len(self.all_games['assists'])
        three_made = len(self.all_games['three_made'])
        point_spread = len(self.all_games['point_spread'])
        game_total = len(self.all_games['game_total'])
        first_half = len(self.all_games['first_half'])
        first_half_moneyline = len(self.all_games['first_half_moneyline'])
        first_quarter = len(self.all_games['first_quarter'])
        futures = len(self.all_games['futures'])

        summary_parts = [
            f"{num_games} Games",
            f"{spreads} Spreads",
            f"{totals} Totals",
            f"{moneylines} Moneylines"
        ]

        # Add other markets if they exist
        if points > 0:
            summary_parts.append(f"{points} Points")
        if points_ou > 0:
            summary_parts.append(f"{points_ou} Points O/U")
        if points_low > 0:
            summary_parts.append(f"{points_low} Points Low")
        if rebounds > 0:
            summary_parts.append(f"{rebounds} Rebounds")
        if assists > 0:
            summary_parts.append(f"{assists} Assists")
        if three_made > 0:
            summary_parts.append(f"{three_made} Three Made")
        if point_spread > 0:
            summary_parts.append(f"{point_spread} Point Spread")
        if game_total > 0:
            summary_parts.append(f"{game_total} Game Total")
        if first_half > 0:
            summary_parts.append(f"{first_half} 1st Half")
        if first_half_moneyline > 0:
            summary_parts.append(f"{first_half_moneyline} 1st Half Moneyline")
        if first_quarter > 0:
            summary_parts.append(f"{first_quarter} 1st Quarter")
        if futures > 0:
            summary_parts.append(f"{futures} Futures")

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
            spreads = game.get('spreads', [])
            for spread in spreads:
                line = spread.get('line', '')
                odds_val = spread.get('odds', '0')
                if line.startswith('-'):
                    team = away_team
                    selection = away_team
                    normalized_selection = away_team.lower().replace(' ', '_')
                else:
                    team = home_team
                    selection = home_team
                    normalized_selection = home_team.lower().replace(' ', '_')

                odds.append({
                    "id": f"{fixture_id}:bet365:spread:{normalized_selection}_{line}",
                    "sportsbook": "Bet365",
                    "market": "Point Spread",
                    "name": f"{team} {line}",
                    "is_main": True,
                    "selection": selection,
                    "normalized_selection": normalized_selection,
                    "market_id": "spread",
                    "selection_line": None,
                    "player_id": None,
                    "team_id": None,
                    "price": int(odds_val.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": f"default:{line}",
                    "points": float(line.replace('+', '').replace('-', '-') or 0),
                    "betlink": betlink,
                    "limits": None
                })

            # Total odds
            totals = game.get('totals', [])
            for total in totals:
                line = total.get('line', '0')
                odds_val = total.get('odds', '0')
                type_str = total.get('type', 'Over').lower()

                odds.append({
                    "id": f"{fixture_id}:bet365:total:{type_str}_{line}",
                    "sportsbook": "Bet365",
                    "market": "Total Points",
                    "name": f"{total.get('type', 'Over')} {line}",
                    "is_main": True,
                    "selection": "",
                    "normalized_selection": "",
                    "market_id": "total",
                    "selection_line": type_str,
                    "player_id": None,
                    "team_id": None,
                    "price": int(odds_val.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": f"default:{line}",
                    "points": float(line),
                    "betlink": betlink,
                    "limits": None
                })

            # Moneyline odds
            moneylines = game.get('moneylines', [])
            for i, moneyline in enumerate(moneylines):
                odds_val = moneyline.get('odds', '0')
                if i == 0:
                    team = away_team
                    selection = away_team
                    normalized_selection = away_team.lower().replace(' ', '_')
                else:
                    team = home_team
                    selection = home_team
                    normalized_selection = home_team.lower().replace(' ', '_')

                odds.append({
                    "id": f"{fixture_id}:bet365:moneyline:{normalized_selection}",
                    "sportsbook": "Bet365",
                    "market": "Moneyline",
                    "name": team,
                    "is_main": True,
                    "selection": selection,
                    "normalized_selection": normalized_selection,
                    "market_id": "moneyline",
                    "selection_line": None,
                    "player_id": None,
                    "team_id": None,
                    "price": int(odds_val.replace('+', '').replace('-', '-') or 0),
                    "timestamp": timestamp,
                    "grouping_key": "default",
                    "points": None,
                    "betlink": betlink,
                    "limits": None
                })

            # Build game object
            game_obj = {
                "id": fixture_id,
                "game_id": f"nba-{fixture_id}",
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
                    "id": "basketball",
                    "name": "Basketball"
                },
                "league": {
                    "id": "nba",
                    "name": "NBA"
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
            spreads = game.get('spreads', [])
            for spread in spreads:
                line = spread.get('line', '')
                odds_value = spread.get('odds', '0')
                if line.startswith('-'):
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NBA",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": float(line.replace('+', '').replace('-', '-') or 0),
                    "am_odds": float(odds_value.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": bet_team,
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
            totals = game.get('totals', [])
            for total in totals:
                line = total.get('line', '0')
                odds_value = total.get('odds', '0')
                bet_occurence = total.get('type', 'Over')

                bets_data.append({
                    "league": "NBA",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": float(line),
                    "am_odds": float(odds_value.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": None,
                    "home": home_team,
                    "market": "Total Points",
                    "bet_occurence": bet_occurence,
                    "internal_betlink": betlink,
                    "away_short": away_brief,
                    "home_brief": home_brief,
                    "away": away_team,
                    "betlink": betlink
                })

            # Moneyline odds
            moneylines = game.get('moneylines', [])
            for i, moneyline in enumerate(moneylines):
                odds_value = moneyline.get('odds', '0')
                if i == 0:
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NBA",
                    "limit": None,
                    "tournament": None,
                    "start_date": iso_date,
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": None,
                    "am_odds": float(odds_value.replace('+', '').replace('-', '-') or 0),
                    "home_short": home_brief,
                    "bet_team": bet_team,
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
        """Save NBA futures data separately"""
        futures_data = {
            "futures": self.all_games.get('futures', []),
            "total_futures": len(self.all_games.get('futures', []))
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(futures_data, f, indent=2, ensure_ascii=False)


async def collect_nba_data():
    """NBA data collection with multiple markets"""
    from pathlib import Path

    # Initialize parser
    parser = NBAParser()

    # Define markets to collect - NBA market codes
    markets = [
        # Game lines (Main market with spreads, totals, moneylines)
        {'code': '1453', 'name': 'Game Lines', 'hash': '#/AC/B18/C20604387/D48/E1453/F10/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/', 'type': 'main'},

        # Player Props
        {'code': '181446', 'name': 'Points', 'hash': '#/AC/B18/C20604387/D43/E181446/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181446/F43/N0/', 'type': 'props'},
        {'code': '181378', 'name': 'Points O/U', 'hash': '#/AC/B18/C20604387/D43/E181378/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181378/F43/N0/', 'type': 'props'},
        {'code': '181448', 'name': 'Rebounds', 'hash': '#/AC/B18/C20604387/D43/E181448/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181448/F43/N0/', 'type': 'props'},
        {'code': '181447', 'name': 'Assists', 'hash': '#/AC/B18/C20604387/D43/E181447/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181447/F43/N0/', 'type': 'props'},
        {'code': '181449', 'name': 'Three Made', 'hash': '#/AC/B18/C20604387/D43/E181449/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181449/F43/N0/', 'type': 'props'},
        {'code': '181444', 'name': 'Points Low', 'hash': '#/AC/B18/C20604387/D43/E181444/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D43/E181444/F43/N0/', 'type': 'props'},

        # Alternative Lines
        {'code': '181285', 'name': 'Point Spread', 'hash': '#/AC/B18/C20604387/D47/E181285/F47/N0/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D47/E181285/F47/N0/', 'type': 'main'},
        {'code': '181286', 'name': 'Game Total', 'hash': '#/AC/B18/C20604387/D47/E181286/F47/N0/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D47/E181286/F47/N0/', 'type': 'main'},

        # Half/Quarter Markets
        {'code': '928', 'name': '1st Half', 'hash': '#/AC/B18/C20604387/D48/E928/F40/N0/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E928/F40/N0/', 'type': 'main'},
        {'code': '181183', 'name': '1st Half Moneyline 3 Way', 'hash': '#/AC/B18/C20604387/D706/E181183/F706/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D706/E181183/F706/N0/', 'type': 'props'},
        {'code': '941', 'name': '1st Quarter', 'hash': '#/AC/B18/C20604387/D48/E941/F30/N0/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E941/F30/N0/', 'type': 'main'},

        # Futures
        {'code': '118540602', 'name': 'To Win Outright', 'hash': '#/AC/B18/C21057140/D1/E118540602/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21057140/D1/E118540602/F2/', 'type': 'futures'},
        {'code': '119977155', 'name': 'To Win Conference', 'hash': '#/AC/B18/C21057140/D1/E119977155/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21057140/D1/E119977155/F2/', 'type': 'futures'},
        {'code': '120192062', 'name': 'To Win Division', 'hash': '#/AC/B18/C21057140/D1/E120192062/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21057140/D1/E120192062/F2/', 'type': 'futures'},
        {'code': '120192243', 'name': 'Division of NBA Champions League Winner', 'hash': '#/AC/B18/C21057140/D1/E120192243/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21057140/D1/E120192243/F2/', 'type': 'futures'},
        {'code': '120192244', 'name': 'State of NBA Champions League Winner', 'hash': '#/AC/B18/C21057140/D1/E120192244/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D1/E120192244/F2/', 'type': 'futures'},
        {'code': '120758795', 'name': 'Regular Season Wins', 'hash': '#/AC/B18/C21057140/D1/E120758795/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21057140/D1/E120758795/F2/', 'type': 'futures'},
    ]

    async with async_playwright() as playwright:
        # Use chrome_helper to set up browser (works on Windows and Ubuntu)
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome browser")
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

            # Handle sign-in modal/popup using helper function
            await dismiss_bet365_popups(page, logger)
            
            # Verify page loaded properly
            if not await verify_bet365_loaded(page, logger):
                logger.warning("⚠️ Page appears blank, waiting longer...")
                await asyncio.sleep(5)
                if not await verify_bet365_loaded(page, logger):
                    logger.error("❌ Page still blank after additional wait")

            logger.info("📜 Random scrolling for 2-3 seconds...")
            viewport = page.viewport_size or {'width': 1920, 'height': 1080}
            interaction_time = random.uniform(2, 3)
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < interaction_time:
                scroll_amount = random.randint(50, 300)
                await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
                await asyncio.sleep(random.uniform(0.3, 0.6))

                if random.random() > 0.7:
                    scroll_back = random.randint(-150, -50)
                    await page.evaluate(f'window.scrollBy(0, {scroll_back})')

                await asyncio.sleep(random.uniform(0.2, 0.4))

            logger.info("⏳ Waiting before clicking NBA...")
            await asyncio.sleep(random.uniform(1, 2))

            logger.info("🏀 Clicking on NBA...")
            
            # Prepare to capture initial NBA page load (contains main spreads/moneylines)
            initial_captured_data = []
            
            async def capture_initial_response(response):
                if 'bet365' in response.url and response.status == 200:
                    try:
                        body = await response.text()
                        if len(body) > 100:
                            initial_captured_data.append({
                                'url': response.url,
                                'body': body,
                                'size': len(body),
                                'market': 'NBA Main Lines',
                                'market_url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/',
                                'timestamp': datetime.now().isoformat()
                            })
                    except:
                        pass
            
            page.on('response', capture_initial_response)
            
            nba_selectors = [
                'span.wn-PillItem_Text:has-text("NBA")',
                '.wn-PillItem:has-text("NBA")',
                '[alt="NBA"]'
            ]

            nba_clicked = False
            for selector in nba_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"✓ Clicked NBA with: {selector}")
                        nba_clicked = True
                        break
                except:
                    continue

            if not nba_clicked:
                logger.warning("⚠️ Could not click NBA, navigating directly...")
                await page.goto('https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/', wait_until='networkidle')
            
            # Wait for NBA page to load properly
            logger.info("⏳ Waiting for NBA page content to load...")
            await asyncio.sleep(5)
            
            # Verify NBA page loaded - check for content
            if not await verify_bet365_loaded(page, logger):
                logger.warning("⚠️ NBA page appears dark/blank, trying reload...")
                await page.goto('https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/', wait_until='networkidle')
                await asyncio.sleep(5)
                
                # Check again
                if not await verify_bet365_loaded(page, logger):
                    logger.error("❌ NBA page still not loading - may need manual intervention")
                else:
                    logger.info("✓ NBA page loaded after reload")
            
            # Verify page loaded - check for common NBA elements
            try:
                await page.wait_for_selector('.gl-MarketGroup, .ovm-Fixture, .sl-MarketCouponFixtureLinkJumpLink', timeout=10000)
                logger.info("✓ NBA market elements detected")
            except:
                logger.warning("⚠️ No NBA market elements found - page may be empty")
                
            # Additional wait for API responses
            await asyncio.sleep(2)
            
            page.remove_listener('response', capture_initial_response)
            
            logger.info(f"✓ Captured {len(initial_captured_data)} responses from NBA main page")

            # Collect data from each market
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Collecting {len(markets)} NBA Markets")
            logger.info(f"{'='*60}\n")

            all_captured_data = initial_captured_data.copy()  # Start with initial data

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
                                    'market_url': market['url'],
                                    'timestamp': datetime.now().isoformat()
                                })
                        except:
                            pass

                page.on('response', capture_response)

                # Navigate to market using hash
                await page.evaluate(f"window.location.hash = '{market['hash']}'")
                
                # Wait for content to load
                await asyncio.sleep(random.uniform(3.0, 4.0))  # Increased wait for page load
                
                # Verify content loaded
                try:
                    await page.wait_for_selector('.gl-MarketGroup, .ovm-Fixture, .sl-MarketCouponFixtureLinkJumpLink, .cm-MarketGroupButton', timeout=5000)
                except:
                    logger.debug(f"Market {market['name']} may not have visible content")

                try:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(random.uniform(0.5, 0.8))
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(random.uniform(0.5, 0.8))
                except:
                    pass

                # Wait for network to settle
                await asyncio.sleep(random.uniform(1.5, 2.0))

                page.remove_listener('response', capture_response)

                all_captured_data.extend(captured_data)
                await asyncio.sleep(random.uniform(0.5, 1.0))

            # Parse all collected data
            logger.info(f"\n{'='*60}")
            logger.info(f"📋 Parsing Collected Data")
            logger.info(f"{'='*60}\n")

            for response in all_captured_data:
                market_config = None
                for m in markets:
                    if response.get('market') == m['name']:
                        market_config = m
                        break

                # Handle NBA Main Lines from initial page capture (not in markets config)
                if not market_config and response.get('market') == 'NBA Main Lines':
                    market_config = {'name': 'NBA Main Lines', 'url': 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/'}

                if market_config:
                    market_url = response.get('market_url', market_config['url'])
                    parsed = parser.parse_response(response['body'], response['market'], market_url, all_captured_data)
                    parser.add_to_collection(parsed)

            # Log parsing summary
            for m in markets:
                market_responses = [r for r in all_captured_data if r.get('market') == m['name']]
                if market_responses:
                    logger.info(f"  ✓ {m['name']}: {len(market_responses)} responses, {sum(r['size'] for r in market_responses):,} bytes")

            # Save all data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(f'nba_data_{timestamp}')
            output_dir.mkdir(exist_ok=True)

            # Save raw captured data
            raw_data_file = output_dir / 'captured_data.json'
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(all_captured_data, f, indent=2, ensure_ascii=False)

            # Save parsed data
            parsed_data_file = output_dir / 'parsed_nba_data.json'
            parser.save_to_file(str(parsed_data_file))

            # Save data in Optic Odds format
            optic_odds_file = output_dir / 'nba_optic_odds_format.json'
            parser.save_optic_odds_format(str(optic_odds_file))

            # Save data in Eternity format
            eternity_file = output_dir / 'nba_eternity_format.json'
            parser.save_eternity_format(str(eternity_file))

            # Save futures separately
            futures_file = output_dir / 'nba_futures.json'
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
            logger.info(f"✅ NBA Data Collection Complete")
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
            import traceback
            traceback.print_exc()
            return False
        finally:
            await browser.close()
            if chrome_manager:
                chrome_manager.cleanup()


if __name__ == '__main__':
    asyncio.run(collect_nba_data())
