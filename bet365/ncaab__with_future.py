"""
NCAAB Data Collection - Multiple Markets
Collects NCAAB betting data from bet365 including:
- Game Lines (Spread, Total, Money Line)
- Alternative Spreads and Totals
- Player Props (Points, Rebounds, Assists, Three Made)
- Team Props
- Futures (Outright, Awards, Final Four)
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from patchright.async_api import async_playwright
from chrome_helper import setup_chrome_browser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NCAABParser:
    """Parse bet365 NCAAB data"""

    def __init__(self):
        self.all_games = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
            'points': [],
            'points_ou': [],
            'rebounds': [],
            'assists': [],
            'three_made': [],
            'point_spread': [],
            'game_total': [],
            'first_half': [],
            'first_half_moneyline': [],
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
        """Parse game lines (spreads, totals, moneylines) from bet365 NCAAB response

        NCAAB Format:
        - PA;ID=PC44416546;NA=Cal State Northridge;N2=Idaho;...;FI=185388454; (game cards)
        - MA;ID=M1453;NA=Spread;FI=185388454;... (market header for spreads)
        - PA;ID=44416546;FI=185388454;HD=+2.0;HA=+2.0;OD=10/11;... (spread odds)
        - MA;ID=M1454;NA=Total;FI=185388454;... (market header for totals)
        - PA;ID=44416561;FI=185388454;HD=O 159.5;HA=159.5;OD=10/11;... (total odds)
        - MA;ID=M960;NA=Money Line;FI=185388454;... (market header for moneylines)
        - PA;ID=44416553;FI=185388454;OD=6/5;... (moneyline odds)

        Market-specific IDs:
        - Game Lines: M1453 (spreads), M1454 (totals), M960 (moneylines)
        - 1st Half: M928 (spreads), M929 (totals), M180019 (moneylines)
        """
        # Define market ID mappings
        market_ids = {
            'Game Lines': {'spreads': 'M1453', 'totals': 'M1454', 'moneylines': 'M960'},
            '1st Half': {'spreads': 'M928', 'totals': 'M929', 'moneylines': 'M180019'}
        }

        current_market_ids = market_ids.get(market_name, market_ids['Game Lines'])

        games = {}  # fixture_id -> game data
        sections = body.split('|')

        # First pass: Extract game cards
        for section in sections:
            if section.startswith('PA;ID=PC') and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                fixture_id = parts.get('FI', '')
                if fixture_id and fixture_id not in games:
                    away_team = parts.get('NA', '')
                    home_team = parts.get('N2', '')
                    matchup = f"{away_team} @ {home_team}"
                    bc_code = parts.get('BC', '')
                    date = self._parse_date(bc_code) if bc_code else ''

                    games[fixture_id] = {
                        'fixture_id': fixture_id,
                        'matchup': matchup,
                        'away_team': away_team,
                        'home_team': home_team,
                        'date': date,
                        'betlink': f'https://www.on.bet365.ca/#/AC/B18/C21097732/D48/E{fixture_id}/F10/',
                        'spreads': [],
                        'totals': [],
                        'moneylines': []
                    }

        # Second pass: Process all sections and associate odds with markets
        # We'll track the current market type as we encounter market headers
        current_market_type = None  # Track which market section we're currently in

        for section in sections:
            # Market header: MA;ID=M1453;NA=Spread;FI=185388454;
            if section.startswith('MA;ID=M') and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                market_id = parts.get('ID', '')

                # Set current market type based on market ID
                if market_id == current_market_ids['spreads']:
                    current_market_type = 'spreads'
                elif market_id == current_market_ids['totals']:
                    current_market_type = 'totals'
                elif market_id == current_market_ids['moneylines']:
                    current_market_type = 'moneylines'

            # Odds entry: PA;ID=44416546;FI=185388454;HD=+2.0;HA=+2.0;OD=10/11;
            elif section.startswith('PA;ID=') and not section.startswith('PA;ID=PC') and ';OD=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                # Try multiple field names for fixture ID
                # OI (original ID) often matches game cards better than FI
                fixture_id = parts.get('FI', '')
                oi = parts.get('OI', '')
                
                # Check which ID is in our games dict
                if fixture_id not in games and oi:
                    fixture_id = oi
                    
                hd = parts.get('HD', '')
                odds_raw = parts.get('OD', '')

                # Use current market type and check if fixture exists in games
                if fixture_id and fixture_id in games and current_market_type and odds_raw:
                    market_type = current_market_type
                    game = games[fixture_id]

                    if market_type == 'spreads' and hd:
                        # Spread: HD contains line like "+2.0" or "-5.5"
                        odds_american = self.convert_odds(odds_raw)
                        game['spreads'].append({
                            'line': hd,
                            'odds': odds_american,
                            'odds_raw': odds_raw
                        })

                    elif market_type == 'totals' and hd and (hd.startswith('O ') or hd.startswith('U ')):
                        # Total: HD contains "O 159.5" or "U 145.0"
                        parts_hd = hd.split(' ', 1)
                        if len(parts_hd) == 2:
                            line_type = 'Over' if parts_hd[0] == 'O' else 'Under'
                            line_value = parts_hd[1]
                            odds_american = self.convert_odds(odds_raw)
                            game['totals'].append({
                                'type': line_type,
                                'line': line_value,
                                'odds': odds_american,
                                'odds_raw': odds_raw
                            })

                    elif market_type == 'moneylines':
                        # Moneyline: no HD field
                        odds_american = self.convert_odds(odds_raw)
                        game['moneylines'].append({
                            'odds': odds_american,
                            'odds_raw': odds_raw
                        })

        return list(games.values())

    def _parse_totals(self, body: str) -> List[Dict]:
        """Parse alternative totals from bet365 response

        Format:
        - MA;ID=C170240;NA=Main;FI=185334691;
        - PA;ID=P37647934;SU=0;NA=5.5;
        - MA;ID=C170240;NA=Over;FI=185334691;
        - PA;ID=37647934;OD=5/6;SU=0;
        - MA;ID=C170240;NA=Under;FI=185334691;
        - PA;ID=37647935;OD=1/1;SU=0;
        """
        totals = []
        sections = body.split('|')

        # Track total lines and odds
        total_lines = {}  # line_id -> {line_value, fixture_id, over_odds, under_odds}
        current_market = None  # 'Main', 'Over', 'Under', 'Alternative'
        current_fixture = None

        for section in sections:
            # Market identifier: MA;ID=C170240;NA=Main;FI=185334691;
            if section.startswith('MA;ID=C170240'):
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                market_name = parts.get('NA', '')
                fixture_id = parts.get('FI', '')

                if market_name in ['Main', 'Over', 'Under', 'Alternative']:
                    current_market = market_name.lower()
                    current_fixture = fixture_id

            # Total line value: PA;ID=P37647934;SU=0;NA=5.5;
            elif section.startswith('PA;ID=P') and ';NA=' in section and current_market in ['main', 'alternative']:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                line_id = parts.get('ID', '')
                line_value = parts.get('NA', '')

                if line_id and line_value:
                    try:
                        float(line_value)  # Validate it's a number
                        total_lines[line_id[1:]] = {  # Remove P prefix
                            'line': line_value,
                            'fixture_id': current_fixture,
                            'over_odds': None,
                            'under_odds': None
                        }
                    except ValueError:
                        pass

            # Odds entry: PA;ID=37647934;OD=5/6;SU=0;
            elif section.startswith('PA;ID=') and not section.startswith('PA;ID=P') and ';OD=' in section and current_market in ['over', 'under']:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                participant_id = parts.get('ID', '')
                odds_raw = parts.get('OD', '')

                if odds_raw:
                    # Match to total line
                    for line_id, line_data in total_lines.items():
                        if participant_id.startswith(line_id) or participant_id == line_id:
                            odds_american = self.convert_odds(odds_raw)

                            if current_market == 'over':
                                line_data['over_odds'] = odds_american
                            elif current_market == 'under':
                                line_data['under_odds'] = odds_american
                            break

        # Convert to list
        for line_id, line_data in total_lines.items():
            if line_data['over_odds'] and line_data['under_odds']:
                totals.append({
                    'fixture_id': line_data['fixture_id'],
                    'total_line': line_data['line'],
                    'over_odds': line_data['over_odds'],
                    'under_odds': line_data['under_odds']
                })

        return totals

    def parse_response(self, body: str, market_name: str, market_url: str, all_captured_data: Optional[List[Dict]] = None) -> Dict:
        """Parse response based on market type"""
        result = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
            'points': [],
            'points_ou': [],
            'rebounds': [],
            'assists': [],
            'three_made': [],
            'point_spread': [],
            'game_total': [],
            'first_half': [],
            'first_half_moneyline': [],
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
            result['game_lines'] = self.parse_game_lines(body, market_name, all_captured_data)
        elif market_name == 'Total':
            result['alt_totals'] = self._parse_totals(body)
        elif market_name == 'Points':
            result['points'] = self._parse_player_props(body, 'points')
        elif market_name == 'Points O/U':
            result['points_ou'] = self._parse_player_props(body, 'points_ou')
        elif market_name == 'Rebounds':
            result['rebounds'] = self._parse_player_props(body, 'rebounds')
        elif market_name == 'Assists':
            result['assists'] = self._parse_player_props(body, 'assists')
        elif market_name == 'Three Made':
            result['three_made'] = self._parse_player_props(body, 'three_made')
        elif market_name == 'Point Spread':
            result['point_spread'] = self._parse_totals(body)
        elif market_name == 'Game Total':
            result['game_total'] = self._parse_totals(body)
        elif market_name == '1st Half':
            # 1st Half contains totals and moneylines for the same games
            half_games = self.parse_game_lines(body, market_name, all_captured_data)
            result['first_half'] = half_games
            # Also merge into game_lines for summary counting
            if 'game_lines' not in result:
                result['game_lines'] = []
            # Merge half_games into game_lines
            for half_game in half_games:
                fixture_id = half_game['fixture_id']
                # Find existing game or create new one
                existing_game = None
                for game in result['game_lines']:
                    if game['fixture_id'] == fixture_id:
                        existing_game = game
                        break
                if existing_game:
                    # Merge odds
                    existing_game['totals'].extend(half_game.get('totals', []))
                    existing_game['moneylines'].extend(half_game.get('moneylines', []))
                else:
                    # Add new game
                    result['game_lines'].append(half_game)
        elif market_name == '1st Half Moneyline 3 Way':
            result['first_half_moneyline'] = self._parse_player_props(body, 'first_half_moneyline')
        elif market_name in ['To Win Outright', 'John R Wooden Award', 'To Make Final Four', 'Annual Awards']:
            result['futures'] = self.parse_futures(body, market_name, market_url)

        return result

    def _parse_player_props(self, body: str, prop_type: str) -> List[Dict]:
        """Parse player props from bet365 response

        Format:
        - PA;ID=PC40191258;NA=Jason Robertson;N2=DAL Stars;TD=43;
        - CO;ID=C170601;NA=1;SY=ipg;
        - PA;ID=40191258;FI=185334736;SU=0;OD=10/29;
        - CO;ID=C170601;NA=2;SY=ipg;
        - PA;ID=40191260;FI=185334736;SU=0;OD=33/20;
        """
        props = []
        sections = body.split('|')

        # Map to track players and their lines
        players = {}  # player_id -> {name, team, fixture_id}
        current_player_id = None
        current_line = None

        for section in sections:
            # Player card: PA;ID=PC40191258;NA=Jason Robertson;N2=DAL Stars;
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
                        'lines': {}  # line_value -> odds
                    }
                    current_player_id = player_id

            # Column definition: CO;ID=C170601;NA=1;
            elif section.startswith('CO;ID='):
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                line_value = parts.get('NA', '')
                if line_value and line_value.isdigit():
                    current_line = line_value

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

                if odds_raw and current_line:
                    # Find matching player by checking if participant_id matches player_id
                    for player_id, player_data in players.items():
                        if participant_id.startswith(player_id) or participant_id == player_id:
                            odds_american = self.convert_odds(odds_raw)
                            player_data['lines'][current_line] = {
                                'odds': odds_american,
                                'odds_raw': odds_raw
                            }
                            player_data['fixture_id'] = fixture_id
                            break

        # Convert to list format
        for player_id, player_data in players.items():
            if player_data['lines']:  # Only include players with odds
                lines_list = []
                for line_value, odds_data in sorted(player_data['lines'].items(), key=lambda x: int(x[0])):
                    lines_list.append({
                        'line': line_value,
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
        """Parse NCAAB futures markets"""
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

    def add_to_collection(self, parsed: Dict):
        """Add parsed data to collection"""
        for key, value in parsed.items():
            if key not in self.all_games:
                self.all_games[key] = []
            if isinstance(value, list):
                if key == 'game_lines':
                    # Merge games by fixture_id
                    for new_game in value:
                        fixture_id = new_game.get('fixture_id')
                        existing_game = None
                        for game in self.all_games[key]:
                            if game.get('fixture_id') == fixture_id:
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

        # Count spreads, totals, moneylines from game_lines (now arrays)
        spreads = sum(len(g.get('spreads', [])) for g in self.all_games['game_lines'])
        totals = sum(len(g.get('totals', [])) for g in self.all_games['game_lines'])
        moneylines = sum(len(g.get('moneylines', [])) for g in self.all_games['game_lines'])

        # Count other markets
        points = len(self.all_games['points'])
        points_ou = len(self.all_games['points_ou'])
        rebounds = len(self.all_games['rebounds'])
        assists = len(self.all_games['assists'])
        three_made = len(self.all_games['three_made'])
        point_spread = len(self.all_games['point_spread'])
        game_total = len(self.all_games['game_total'])
        first_half = len(self.all_games['first_half'])
        first_half_moneyline = len(self.all_games['first_half_moneyline'])
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

            # Spread odds - now from spreads array
            spreads = game.get('spreads', [])
            for spread in spreads:
                line = spread.get('line', '')
                odds_val = spread.get('odds', '0')
                # Determine if this is away or home based on line sign
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

            # Total odds - now from totals array
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

            # Moneyline odds - now from moneylines array
            moneylines = game.get('moneylines', [])
            for i, moneyline in enumerate(moneylines):
                odds_val = moneyline.get('odds', '0')
                # First moneyline is away, second is home
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
                "game_id": f"ncaab-{fixture_id}",
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
                    "id": "ncaab",
                    "name": "NCAAB"
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

            # Spread odds - now from spreads array
            spreads = game.get('spreads', [])
            for spread in spreads:
                line = spread.get('line', '')
                odds_value = spread.get('odds', '0')
                # Determine if this is away or home based on line sign
                if line.startswith('-'):
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NCAAB",
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

            # Total odds - now from totals array
            totals = game.get('totals', [])
            for total in totals:
                line = total.get('line', '0')
                odds_value = total.get('odds', '0')
                bet_occurence = total.get('type', 'Over')

                bets_data.append({
                    "league": "NCAAB",
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

            # Moneyline odds - now from moneylines array
            moneylines = game.get('moneylines', [])
            for i, moneyline in enumerate(moneylines):
                odds_value = moneyline.get('odds', '0')
                # First moneyline is away, second is home
                if i == 0:
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NCAAB",
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
        """Save NCAAB futures data separately"""
        futures_data = {
            "futures": self.all_games.get('futures', []),
            "total_futures": len(self.all_games.get('futures', []))
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(futures_data, f, indent=2, ensure_ascii=False)


async def collect_ncaab_data():
    """NCAAB data collection with multiple markets"""
    import subprocess
    import shutil
    from pathlib import Path

    # Initialize parser
    parser = NCAABParser()

    # Define markets to collect - NCAAB market codes
    markets = [
        # Game lines (Main market with spreads, totals, moneylines)
        {'code': '1453', 'name': 'Game Lines', 'hash': '#/AC/B18/C21097732/D48/E1453/F10/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D48/E1453/F10/', 'type': 'main'},

        # Player Props
        {'code': '181446', 'name': 'Points', 'hash': '#/AC/B18/C21097732/D43/E181446/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D43/E181446/F43/N0/', 'type': 'props'},
        {'code': '181378', 'name': 'Points O/U', 'hash': '#/AC/B18/C21097732/D43/E181378/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D43/E181378/F43/N0/', 'type': 'props'},
        {'code': '181448', 'name': 'Rebounds', 'hash': '#/AC/B18/C21097732/D43/E181448/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D43/E181448/F43/N0/', 'type': 'props'},
        {'code': '181447', 'name': 'Assists', 'hash': '#/AC/B18/C21097732/D43/E181447/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D43/E181447/F43/N0/', 'type': 'props'},
        {'code': '181449', 'name': 'Three Made', 'hash': '#/AC/B18/C21097732/D43/E181449/F43/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D43/E181449/F43/N0/', 'type': 'props'},

        # Alternative Lines
        {'code': '181285', 'name': 'Point Spread', 'hash': '#/AC/B18/C21097732/D47/E181285/F47/N0/', 'parser': 'totals',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D47/E181285/F47/N0/', 'type': 'totals'},
        {'code': '181286', 'name': 'Game Total', 'hash': '#/AC/B18/C21097732/D47/E181286/F47/N0/', 'parser': 'totals',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D47/E181286/F47/N0/', 'type': 'totals'},

        # Half Markets
        {'code': '928', 'name': '1st Half', 'hash': '#/AC/B18/C21097732/D48/E928/F40/N0/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D48/E928/F40/N0/', 'type': 'main'},
        {'code': '181183', 'name': '1st Half Moneyline 3 Way', 'hash': '#/AC/B18/C21097732/D706/E181183/F706/N0/', 'parser': 'player_props',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21097732/D706/E181183/F706/N0/', 'type': 'props'},

        # Futures
        {'code': '117039286', 'name': 'To Win Outright', 'hash': '#/AC/B18/C21047711/D1/E117039286/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21047711/D1/E117039286/F2/', 'type': 'futures'},
        {'code': '120106232', 'name': 'John R Wooden Award', 'hash': '#/AC/B18/C21047711/D1/E120106232/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21047711/D1/E120106232/F2/', 'type': 'futures'},
        {'code': '123192180', 'name': 'To Make Final Four', 'hash': '#/AC/B18/C21047711/D1/E123192180/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21047711/D1/E123192180/F2/', 'type': 'futures'},
        {'code': '124916800', 'name': 'Annual Awards', 'hash': '#/AC/B18/C21047711/D1/E124916800/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B18/C21047711/D1/E124916800/F2/', 'type': 'futures'},
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

            # Wait a bit more before clicking NCAAB
            logger.info("⏳ Waiting before clicking NCAAB...")
            await asyncio.sleep(random.uniform(1, 2))

            logger.info("🏀 Clicking on NCAAB...")
            # Click on NCAAB element
            ncaab_selectors = [
                'span.wn-PillItem_Text:has-text("NCAAB")',
                '.wn-PillItem:has-text("NCAAB")',
                '[alt="NCAAB"]'
            ]

            ncaab_clicked = False
            for selector in ncaab_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"✓ Clicked NCAAB with: {selector}")
                        ncaab_clicked = True
                        break
                except:
                    continue

            if not ncaab_clicked:
                logger.warning("⚠️ Could not click NCAAB, navigating directly...")
                await page.goto('https://www.on.bet365.ca/#/AC/B18/C21097732/D48/E1453/F10/')

            await asyncio.sleep(2)

            # Dynamic market discovery
            logger.info("🔍 Discovering available NCAAB markets...")
            available_markets = []

            # Try to find market links on the page
            try:
                market_elements = await page.query_selector_all('.gl-MarketGroup')
                for element in market_elements:
                    try:
                        market_name = await element.inner_text()
                        market_link = await element.query_selector('a')
                        if market_link:
                            href = await market_link.get_attribute('href')
                            if href and '#' in href:
                                hash_part = href.split('#')[1]
                                # Extract market code from hash
                                if '/E' in hash_part:
                                    parts = hash_part.split('/E')
                                    if len(parts) > 1:
                                        market_code = parts[1].split('/')[0]
                                        available_markets.append({
                                            'code': market_code,
                                            'name': market_name.strip(),
                                            'hash': f'#/{hash_part}',
                                            'parser': 'dynamic'  # Will determine parser type based on market name
                                        })
                    except:
                        continue
            except:
                logger.warning("Could not discover markets dynamically, using predefined list")

            # Use predefined markets for NCAAB since dynamic discovery may not find all markets
            # Keep the predefined markets list instead of overriding with dynamic discovery
            pass  # markets list is already defined above

            # Collect data from each market
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Collecting {len(markets)} NCAAB Markets")
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
                                    'market_url': market['url'],
                                    'timestamp': datetime.now().isoformat()
                                })
                        except:
                            pass

                page.on('response', capture_response)

                # Regular market navigation
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

                all_captured_data.extend(captured_data)

                # Random delay between markets
                await asyncio.sleep(random.uniform(0.5, 1.0))

            # Now parse all collected data
            logger.info(f"\n{'='*60}")
            logger.info(f"📋 Parsing Collected Data")
            logger.info(f"{'='*60}\n")

            for response in all_captured_data:
                # Find the market config for this response
                market_config = None
                for m in markets:
                    if response.get('market') == m['name']:
                        market_config = m
                        break

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
            output_dir = Path(f'ncaab_data_{timestamp}')
            output_dir.mkdir(exist_ok=True)

            # Save raw captured data
            raw_data_file = output_dir / 'captured_data.json'
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(all_captured_data, f, indent=2, ensure_ascii=False)

            # Save parsed data (original format)
            parsed_data_file = output_dir / 'parsed_ncaab_data.json'
            parser.save_to_file(str(parsed_data_file))

            # Save data in Optic Odds format
            optic_odds_file = output_dir / 'ncaab_optic_odds_format.json'
            parser.save_optic_odds_format(str(optic_odds_file))

            # Save data in Eternity format
            eternity_file = output_dir / 'ncaab_eternity_format.json'
            parser.save_eternity_format(str(eternity_file))

            # Save futures separately
            futures_file = output_dir / 'ncaab_futures.json'
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
            logger.info(f"✅ NCAAB Data Collection Complete")
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
    asyncio.run(collect_ncaab_data())
                       