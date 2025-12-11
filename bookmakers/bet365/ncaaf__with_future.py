"""
NCAAF Data Collection - Multiple Markets
Collects NCAAF (College Football) betting data from bet365 including:
- Game Lines (Spread, Total, Money Line)
- Alternative Spreads and Totals
- Futures
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

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.helpers.chrome_helper import setup_chrome_browser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NCAAFParser:
    """Parse bet365 NCAAF data"""

    def __init__(self):
        self.all_games = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
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
        """Parse game lines (spreads, totals, moneylines) from bet365 NCAAF response

        NCAAF Format (similar to NCAAB but with football-specific structure):
        - PA;ID=PC44416546;NA=Team A;N2=Team B;...;FI=185388454; (game cards)
        - MA;ID=M1441;NA=Spread;FI=185388454;... (market header for spreads)
        - PA;ID=44416546;FI=185388454;HD=+2.0;HA=+2.0;OD=10/11;... (spread odds)
        - MA;ID=M1442;NA=Total;FI=185388454;... (market header for totals)
        - PA;ID=44416561;FI=185388454;HD=O 159.5;HA=159.5;OD=10/11;... (total odds)
        - MA;ID=M960;NA=Money Line;FI=185388454;... (market header for moneylines)
        - PA;ID=44416553;FI=185388454;OD=6/5;... (moneyline odds)

        Market-specific IDs for NCAAF:
        - Game Lines: M1441 (spreads), M1442 (totals), M960 (moneylines)
        """
        # Define market ID mappings for NCAAF
        market_ids = {
            'Game Lines': {'spreads': 'M1441', 'totals': 'M1442', 'moneylines': 'M960'}
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
                        'betlink': f'https://www.on.bet365.ca/#/AC/B12/C20437885/D48/E{fixture_id}/F36/',
                        'spreads': [],
                        'totals': [],
                        'moneylines': []
                    }

        # Second pass: Process all sections and associate odds with markets
        current_market_type = None  # Track which market section we're currently in

        for section in sections:
            # Market header: MA;ID=M1441;NA=Spread;FI=185388454;
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

    def _parse_alternative_lines(self, body: str, line_type: str) -> List[Dict]:
        """Parse alternative spreads or totals from bet365 response

        NCAAF Format (different structure):
        - MG;ID=G120504;FI=185258727;SY=fd;NA=Notre Dame @ Stanford; (game group with fixture)
        - MA;ID=M120504;NA=Notre Dame;FI=185258727; (market for away team)
        - PA;ID=28143400;SU=0;NA=-52.5;OD=71/10; (spread line with odds)
        - MA;ID=M120504;NA=Stanford;FI=185258727; (market for home team)
        - PA;ID=28143398;SU=0;NA=+52.5;OD=5/84; (spread line with odds)
        """
        lines = []
        sections = body.split('|')

        # Track games and their teams
        games = {}  # fixture_id -> {away_team, home_team, away_lines: {}, home_lines: {}}
        current_fixture = None
        current_team = None
        current_team_type = None  # 'away' or 'home'

        for section in sections:
            # Game group: MG;ID=G120504;FI=185258727;SY=fd;NA=Notre Dame @ Stanford;
            if section.startswith('MG;ID=G') and ';FI=' in section and ';NA=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                fixture_id = parts.get('FI', '')
                matchup = parts.get('NA', '')

                if fixture_id and matchup and '@' in matchup:
                    teams = matchup.split(' @ ')
                    if len(teams) == 2:
                        away_team = teams[0].strip()
                        home_team = teams[1].strip()
                        games[fixture_id] = {
                            'away_team': away_team,
                            'home_team': home_team,
                            'away_lines': {},  # line_value -> odds
                            'home_lines': {}   # line_value -> odds
                        }
                        current_fixture = fixture_id

            # Market identifier: MA;ID=M120504;NA=Notre Dame;FI=185258727;
            elif section.startswith('MA;ID=M120504') and ';NA=' in section and ';FI=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                team_name = parts.get('NA', '')
                fixture_id = parts.get('FI', '')

                if fixture_id in games:
                    current_fixture = fixture_id
                    current_team = team_name
                    # Determine if this is away or home team
                    if team_name == games[fixture_id]['away_team']:
                        current_team_type = 'away'
                    elif team_name == games[fixture_id]['home_team']:
                        current_team_type = 'home'

            # Line with odds: PA;ID=28143400;SU=0;NA=-52.5;OD=71/10;
            elif section.startswith('PA;ID=') and ';OD=' in section and ';NA=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                line_value = parts.get('NA', '')
                odds_raw = parts.get('OD', '')

                if current_fixture and current_team_type and line_value and odds_raw:
                    try:
                        # Validate it's a number (with + or -)
                        float(line_value.replace('+', '').replace('-', ''))
                        odds_american = self.convert_odds(odds_raw)
                        
                        if current_team_type == 'away':
                            games[current_fixture]['away_lines'][line_value] = odds_american
                        elif current_team_type == 'home':
                            games[current_fixture]['home_lines'][line_value] = odds_american
                    except ValueError:
                        pass

        # Convert to list - match away and home lines
        for fixture_id, game_data in games.items():
            away_lines = game_data['away_lines']
            home_lines = game_data['home_lines']

            # Match corresponding lines (e.g., -52.5 with +52.5)
            for away_line, away_odds in away_lines.items():
                # Find corresponding home line
                try:
                    away_val = float(away_line.replace('+', '').replace('-', ''))
                    # Home line should be opposite sign
                    if away_line.startswith('-'):
                        home_line = f"+{abs(away_val)}"
                    else:
                        home_line = f"-{abs(away_val)}"
                    
                    # Check if home line exists
                    if home_line in home_lines:
                        home_odds = home_lines[home_line]
                        
                        if line_type == 'spread':
                            lines.append({
                                'fixture_id': fixture_id,
                                'matchup': f"{game_data['away_team']} @ {game_data['home_team']}",
                                'away_team': game_data['away_team'],
                                'home_team': game_data['home_team'],
                                'spread_line': away_line,
                                'away_odds': away_odds,
                                'home_odds': home_odds
                            })
                        else:  # total (if structure is similar)
                            lines.append({
                                'fixture_id': fixture_id,
                                'matchup': f"{game_data['away_team']} @ {game_data['home_team']}",
                                'total_line': away_line,
                                'over_odds': away_odds,
                                'under_odds': home_odds
                            })
                except:
                    pass

        return lines

    def parse_response(self, body: str, market_name: str, market_url: str, all_captured_data: Optional[List[Dict]] = None) -> Dict:
        """Parse response based on market type"""
        result = {
            'game_lines': [],
            'alt_spreads': [],
            'alt_totals': [],
            'futures': []
        }

        # Handle F|CL; format - extract the data portion
        if body.startswith('F|CL;'):
            # Format: F|CL;ID=12;IT=#AC#B12#C20437885#D48#E1441#F36#;OR=0;EX=7,#AC#...;H1=<actual_data>
            # The actual data comes after H1= or similar markers
            parts = body.split('H1=', 1)
            if len(parts) > 1:
                body = parts[1]  # Use data after H1=
                logger.info(f"  Extracted data from F|CL format, new length: {len(body)} bytes")
            else:
                # Try other possible markers
                for marker in ['H2=', 'H3=', 'D1=', 'D2=']:
                    if marker in body:
                        parts = body.split(marker, 1)
                        if len(parts) > 1:
                            body = parts[1]
                            logger.info(f"  Extracted data from F|CL format using {marker}, new length: {len(body)} bytes")
                            break

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
        elif market_name == 'Alternative Spread':
            result['alt_spreads'] = self._parse_alternative_lines(body, 'spread')
        elif market_name == 'Alternative Total':
            result['alt_totals'] = self._parse_alternative_lines(body, 'total')
        elif 'future' in market_name.lower() or 'outright' in market_name.lower() or 'championship' in market_name.lower() or 'heisman' in market_name.lower() or 'trophy' in market_name.lower():
            result['futures'] = self.parse_futures(body, market_name, market_url)

        return result

    def parse_futures(self, body: str, market_name: str, betlink: str) -> List[Dict]:
        """Parse NCAAF futures markets"""
        futures = []
        sections = body.split('|')

        for section in sections:
            # Parse participant/selection data: PA;ID=2047598288;NA=Ohio State;OD=33/20;SU=0;
            if section.startswith('PA;') and ';OD=' in section and ';NA=' in section:
                parts = {}
                for item in section.split(';'):
                    if '=' in item:
                        key, val = item.split('=', 1)
                        parts[key] = val

                selection = parts.get('NA', '')
                odds = parts.get('OD', '')
                participant_id = parts.get('ID', '')

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
        alt_spreads = len(self.all_games['alt_spreads'])
        alt_totals = len(self.all_games['alt_totals'])
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

        return ", ".join(summary_parts)

    def to_optic_odds_format(self) -> Dict:
        """Convert parsed data to Optic Odds API format"""
        from datetime import datetime
        games_data = []

        # Process Alternative Spreads if no game lines
        if not self.all_games.get('game_lines', []) and self.all_games.get('alt_spreads', []):
            # Group alt spreads by fixture_id
            spreads_by_fixture = {}
            for spread in self.all_games.get('alt_spreads', []):
                fixture_id = spread.get('fixture_id', '')
                if fixture_id not in spreads_by_fixture:
                    spreads_by_fixture[fixture_id] = {
                        'fixture_id': fixture_id,
                        'matchup': spread.get('matchup', ''),
                        'away_team': spread.get('away_team', ''),
                        'home_team': spread.get('home_team', ''),
                        'spreads': []
                    }
                spreads_by_fixture[fixture_id]['spreads'].append(spread)
            
            # Convert to game objects
            for fixture_id, game_data in spreads_by_fixture.items():
                game_obj = self._create_game_object_from_alt_spreads(game_data)
                if game_obj:
                    games_data.append(game_obj)

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
                "game_id": f"ncaaf-{fixture_id}",
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
                    "id": "football",
                    "name": "Football"
                },
                "league": {
                    "id": "ncaaf",
                    "name": "NCAAF"
                },
                "tournament": None,
                "odds": odds
            }

            games_data.append(game_obj)

        return {"data": games_data}

    def _create_game_object_from_alt_spreads(self, game_data: Dict) -> Dict:
        """Create a game object from alternative spreads data"""
        from datetime import datetime
        
        fixture_id = game_data.get('fixture_id', '')
        matchup = game_data.get('matchup', '')
        away_team = game_data.get('away_team', '')
        home_team = game_data.get('home_team', '')
        
        # Build odds array from alternative spreads
        odds = []
        timestamp = datetime.now().timestamp()
        betlink = f'https://www.on.bet365.ca/#/AC/B12/C20437885/D48/E{fixture_id}/F36/'
        
        for spread_data in game_data.get('spreads', []):
            spread_line = spread_data.get('spread_line', '')
            away_odds = spread_data.get('away_odds', '0')
            home_odds = spread_data.get('home_odds', '0')
            
            # Away team spread
            odds.append({
                "id": f"{fixture_id}:bet365:spread:away_{spread_line}",
                "sportsbook": "Bet365",
                "market": "Point Spread",
                "name": f"{away_team} {spread_line}",
                "is_main": True,
                "selection": away_team,
                "normalized_selection": away_team.lower().replace(' ', '_'),
                "market_id": "spread",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": int(away_odds.replace('+', '').replace('-', '-') or 0) if away_odds else 0,
                "timestamp": timestamp,
                "grouping_key": f"default:{spread_line}",
                "points": float(spread_line.replace('+', '').replace('-', '-') or 0),
                "betlink": betlink,
                "limits": None
            })
            
            # Home team spread (opposite)
            try:
                home_line = f"+{abs(float(spread_line))}" if spread_line.startswith('-') else f"-{abs(float(spread_line))}"
            except:
                home_line = spread_line
                
            odds.append({
                "id": f"{fixture_id}:bet365:spread:home_{home_line}",
                "sportsbook": "Bet365",
                "market": "Point Spread",
                "name": f"{home_team} {home_line}",
                "is_main": True,
                "selection": home_team,
                "normalized_selection": home_team.lower().replace(' ', '_'),
                "market_id": "spread",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": int(home_odds.replace('+', '').replace('-', '-') or 0) if home_odds else 0,
                "timestamp": timestamp,
                "grouping_key": f"default:{home_line}",
                "points": float(home_line.replace('+', '').replace('-', '-') or 0) if home_line else 0,
                "betlink": betlink,
                "limits": None
            })
        
        # Build game object
        game_obj = {
            "id": fixture_id,
            "game_id": f"ncaaf-{fixture_id}",
            "start_date": "",
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
                "id": "football",
                "name": "Football"
            },
            "league": {
                "id": "ncaaf",
                "name": "NCAAF"
            },
            "tournament": None,
            "odds": odds
        }
        
        return game_obj

    def to_eternity_format(self) -> Dict:
        """Convert parsed data to Eternity API format"""
        from datetime import datetime
        bets_data = []

        # Process Alternative Spreads if no game lines
        if not self.all_games.get('game_lines', []) and self.all_games.get('alt_spreads', []):
            for spread in self.all_games.get('alt_spreads', []):
                fixture_id = spread.get('fixture_id', '')
                matchup = spread.get('matchup', '')
                away_team = spread.get('away_team', '')
                home_team = spread.get('home_team', '')
                spread_line = spread.get('spread_line', '')
                away_odds = spread.get('away_odds', '0')
                home_odds = spread.get('home_odds', '0')
                
                # Generate team abbreviations
                away_brief = ''.join([word[0] for word in away_team.split()]).upper() if away_team else ''
                home_brief = ''.join([word[0] for word in home_team.split()]).upper() if home_team else ''
                
                betlink = f'https://www.on.bet365.ca/#/AC/B12/C20437885/D48/E{fixture_id}/F36/'
                
                # Away team spread
                bets_data.append({
                    "league": "NCAAF",
                    "limit": None,
                    "tournament": None,
                    "start_date": "",
                    "book": "Bet365",
                    "bet_player": None,
                    "sgp": None,
                    "is_main": True,
                    "away_brief": away_brief,
                    "line": float(spread_line.replace('+', '').replace('-', '-') or 0),
                    "am_odds": float(away_odds.replace('+', '').replace('-', '-') or 0) if away_odds else 0,
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
                # Determine if this is away or home based on line sign
                if line.startswith('-'):
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NCAAF",
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
                    "league": "NCAAF",
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
                # First moneyline is away, second is home
                if i == 0:
                    bet_team = away_team
                else:
                    bet_team = home_team

                bets_data.append({
                    "league": "NCAAF",
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
        """Save NCAAF futures data separately"""
        futures_data = {
            "futures": self.all_games.get('futures', []),
            "total_futures": len(self.all_games.get('futures', []))
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(futures_data, f, indent=2, ensure_ascii=False)


async def collect_ncaaf_data():
    """NCAAF data collection with multiple markets"""
    import subprocess
    import shutil
    from pathlib import Path

    # Initialize parser
    parser = NCAAFParser()

    # Define markets to collect - NCAAF market codes from provided URLs
    markets = [
        # Game lines (Main market with spreads, totals, moneylines)
        {'code': '1441', 'name': 'Game Lines', 'hash': '#/AC/B12/C20437885/D48/E1441/F36/', 'parser': 'game_lines',
         'url': 'https://www.on.bet365.ca/#/AC/B12/C20437885/D48/E1441/F36/', 'type': 'main'},

        # Alternative Lines
        {'code': '120504', 'name': 'Alternative Spread', 'hash': '#/AC/B12/C20437885/D47/E120504/F47/N0/', 'parser': 'alternative',
         'url': 'https://www.on.bet365.ca/#/AC/B12/C20437885/D47/E120504/F47/N0/', 'type': 'alternative'},
        {'code': '120508', 'name': 'Alternative Total', 'hash': '#/AC/B12/C20437885/D47/E120508/F47/N0/', 'parser': 'alternative',
         'url': 'https://www.on.bet365.ca/#/AC/B12/C20437885/D47/E120508/F47/N0/', 'type': 'alternative'},

        # Futures
        {'code': '113608685', 'name': 'To Win Outright', 'hash': '#/AC/B12/C21020451/D1/E113608685/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B12/C21020451/D1/E113608685/F2/', 'type': 'futures'},
        {'code': '114004040', 'name': 'Heisman Trophy Winner', 'hash': '#/AC/B12/C21020451/D1/E114004040/F2/', 'parser': 'futures',
         'url': 'https://www.on.bet365.ca/#/AC/B12/C21020451/D1/E114004040/F2/', 'type': 'futures'},
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
                # Random scroll only
                scroll_amount = random.randint(50, 300)
                await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
                await asyncio.sleep(random.uniform(0.3, 0.6))

                # Scroll back up sometimes
                if random.random() > 0.7:
                    scroll_back = random.randint(-150, -50)
                    await page.evaluate(f'window.scrollBy(0, {scroll_back})')

                await asyncio.sleep(random.uniform(0.2, 0.4))

            # Wait a bit more before clicking NCAAF
            logger.info("⏳ Waiting before clicking NCAAF...")
            await asyncio.sleep(random.uniform(1, 2))

            logger.info("🏈 Clicking on NCAAF...")
            # Click on NCAAF element
            ncaaf_selectors = [
                'span.wn-PillItem_Text:has-text("NCAAF")',
                '.wn-PillItem:has-text("NCAAF")',
                '[alt="NCAAF"]'
            ]

            ncaaf_clicked = False
            for selector in ncaaf_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"✓ Clicked NCAAF with: {selector}")
                        ncaaf_clicked = True
                        break
                except:
                    continue

            if not ncaaf_clicked:
                logger.warning("⚠️ Could not click NCAAF, navigating directly...")
                await page.goto('https://www.on.bet365.ca/#/AC/B12/C20437885/D48/E1441/F36/')

            await asyncio.sleep(3)  # Wait longer for initial load

            # Collect data from each market
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Collecting {len(markets)} NCAAF Markets")
            logger.info(f"{'='*60}\n")

            all_captured_data = []

            for index, market in enumerate(markets, 1):
                logger.info(f"[{index}/{len(markets)}] Collecting: {market['name']}")

                captured_data = []

                async def capture_response(response):
                    try:
                        # Capture ALL bet365 responses without filtering
                        if 'bet365' in response.url:
                            try:
                                body = await response.text()
                            except:
                                body = ""
                            
                            # Log first 150 chars of body to see format
                            body_preview = body[:150].replace('\n', ' ').replace('\r', ' ') if body else ""
                            
                            # Special logging for Game Lines endpoint
                            if market['name'] == 'Game Lines':
                                if 'matchmarketscontentapi/markets' in response.url and ('E1441' in response.url or 'D48' in response.url):
                                    logger.info(f"  🎯 GAME LINES ENDPOINT FOUND!")
                                    logger.info(f"     URL: {response.url}")
                                    logger.info(f"     Status: {response.status}")
                                    logger.info(f"     Body preview: {body_preview}...")
                                    logger.info(f"     Size: {len(body)} bytes")
                                else:
                                    # Log ALL responses during Game Lines collection
                                    logger.info(f"  Response: {response.url[:100]}...")
                                    logger.info(f"     Status: {response.status}, Size: {len(body)} bytes")
                            else:
                                # For other markets, only log if it's a markets/outrights/splash API
                                if any(api in response.url for api in ['markets', 'outrights', 'splash']):
                                    logger.info(f"  Captured: {response.url[:80]}...")
                                    logger.info(f"    Body preview: {body_preview}...")
                                    logger.info(f"    Size: {len(body)} bytes")
                            
                            # Save ALL responses with body content
                            if len(body) > 10:
                                captured_data.append({
                                    'url': response.url,
                                    'body': body,
                                    'size': len(body),
                                    'market': market['name'],
                                    'market_url': market['url'],
                                    'timestamp': datetime.now().isoformat()
                                })
                    except Exception as e:
                        logger.warning(f"  Error capturing response: {e}")
                        pass

                # Start listening BEFORE navigation
                page.on('response', capture_response)

                # Special handling for Game Lines - use page.goto() to force API call
                if market['name'] == 'Game Lines':
                    try:
                        logger.info(f"  Loading Game Lines with full page navigation...")
                        logger.info(f"  Target URL: {market['url']}")
                        logger.info(f"  Looking for API: matchmarketscontentapi/markets?...E1441...")
                        
                        # Navigate to the URL first
                        await page.goto(market['url'], wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(1.0)
                        
                        # Now RELOAD the page to trigger the API call (like manual reload)
                        logger.info(f"  Reloading page to trigger Game Lines API...")
                        await page.reload(wait_until='domcontentloaded', timeout=30000)
                        
                        # Wait longer to allow API calls to complete
                        await asyncio.sleep(3.0)
                        
                        logger.info(f"  Page reloaded, waiting for API responses...")
                        await asyncio.sleep(2.0)
                        
                    except Exception as e:
                        logger.warning(f"    Error with page navigation/reload for Game Lines: {e}")
                        # Fallback to hash navigation
                        await page.evaluate(f"window.location.hash = '{market['hash']}'")
                        await asyncio.sleep(random.uniform(2.0, 3.0))
                else:
                    # Navigate to market using hash (same as NCAAB/NFL approach)
                    await page.evaluate(f"window.location.hash = '{market['hash']}'")
                    await asyncio.sleep(random.uniform(1.5, 2.5))

                # Scroll to load data - EXTRA scrolling for Game Lines (like NCAAB/NFL)
                try:
                    if market['name'] == 'Game Lines':
                        # Enhanced scrolling for Game Lines similar to NCAAB/NFL
                        logger.info(f"  Performing enhanced scrolling for Game Lines...")
                        # Scroll down
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(random.uniform(0.5, 0.7))
                        # Scroll back up
                        await page.evaluate('window.scrollTo(0, 0)')
                        await asyncio.sleep(random.uniform(0.5, 0.7))
                        # Scroll to middle
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                        await asyncio.sleep(random.uniform(0.4, 0.6))
                        # Scroll down again
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(random.uniform(0.4, 0.6))
                        # Final scroll to top
                        await page.evaluate('window.scrollTo(0, 0)')
                        await asyncio.sleep(random.uniform(0.3, 0.5))
                    elif market['name'] in ['Alternative Spread', 'Alternative Total']:
                        # Regular scrolling for alternative markets
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(random.uniform(0.3, 0.5))
                        await page.evaluate('window.scrollTo(0, 0)')
                        await asyncio.sleep(random.uniform(0.3, 0.5))
                    else:
                        # Minimal scrolling for futures
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(random.uniform(0.2, 0.4))
                        await page.evaluate('window.scrollTo(0, 0)')
                        await asyncio.sleep(random.uniform(0.2, 0.4))
                except Exception as e:
                    logger.warning(f"  Scroll error: {e}")
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
            output_dir = Path(f'ncaaf_data_{timestamp}')
            output_dir.mkdir(exist_ok=True)

            # Save raw captured data
            raw_data_file = output_dir / 'captured_data.json'
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(all_captured_data, f, indent=2, ensure_ascii=False)

            # Save parsed data (original format)
            parsed_data_file = output_dir / 'parsed_ncaaf_data.json'
            parser.save_to_file(str(parsed_data_file))

            # Save data in Optic Odds format
            optic_odds_file = output_dir / 'ncaaf_optic_odds_format.json'
            parser.save_optic_odds_format(str(optic_odds_file))

            # Save data in Eternity format
            eternity_file = output_dir / 'ncaaf_eternity_format.json'
            parser.save_eternity_format(str(eternity_file))

            # Save futures separately
            futures_file = output_dir / 'ncaaf_futures.json'
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
            logger.info(f"✅ NCAAF Data Collection Complete")
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
    asyncio.run(collect_ncaaf_data())
