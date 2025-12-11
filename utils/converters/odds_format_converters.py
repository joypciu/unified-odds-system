"""
Odds Format Converters - Convert unified odds data to OpticOdds and Eternity formats
Supports: 1xBet, FanDuel, Bet365
"""
from typing import Dict, List, Any
from datetime import datetime


class OpticOddsConverter:
    """Convert odds data to OpticOdds API format"""
    
    @staticmethod
    def convert_unified_to_optic(unified_data: Dict) -> Dict:
        """Convert unified_odds.json format to OpticOdds format"""
        games_data = []
        
        # Process pregame matches
        for match in unified_data.get('pregame_matches', []):
            game_obj = OpticOddsConverter._convert_match_to_optic(match, is_live=False)
            if game_obj:
                games_data.append(game_obj)
        
        # Process live matches
        for match in unified_data.get('live_matches', []):
            game_obj = OpticOddsConverter._convert_match_to_optic(match, is_live=True)
            if game_obj:
                games_data.append(game_obj)
        
        return {"data": games_data}
    
    @staticmethod
    def _convert_match_to_optic(match: Dict, is_live: bool = False) -> Dict:
        """Convert a single match to OpticOdds format"""
        # Extract basic match info - handle None values
        match_id = match.get('match_id', '')
        sport = match.get('sport') or 'Unknown'
        league = match.get('league') or 'Unknown'
        home_team = match.get('home_team', '')
        away_team = match.get('away_team', '')
        start_time = match.get('start_time', '')
        
        # Parse start time to ISO format
        try:
            if 'T' in start_time:
                iso_date = start_time
            else:
                dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except:
            iso_date = start_time or datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Build odds array from all available bookmakers
        odds = []
        timestamp = datetime.now().timestamp()
        
        # Process 1xBet odds
        if match.get('1xbet', {}).get('available'):
            xbet_data = match['1xbet']
            # Handle nested odds structure: 1xbet.odds.moneyline_home OR direct: 1xbet.moneyline_home
            xbet_odds = xbet_data.get('odds', xbet_data)
            odds.extend(OpticOddsConverter._convert_bookmaker_odds(
                match_id, '1xBet', xbet_odds, home_team, away_team, timestamp
            ))
        
        # Process FanDuel odds
        if match.get('fanduel', {}).get('available'):
            fd_data = match['fanduel']
            # Handle nested odds structure
            fd_odds = fd_data.get('odds', fd_data)
            odds.extend(OpticOddsConverter._convert_bookmaker_odds(
                match_id, 'FanDuel', fd_odds, home_team, away_team, timestamp
            ))
        
        # Process Bet365 odds
        if match.get('bet365', {}).get('available'):
            b365_data = match['bet365']
            # Handle nested odds structure OR direct fields (home_odds, away_odds)
            b365_odds = b365_data.get('odds', b365_data)
            odds.extend(OpticOddsConverter._convert_bookmaker_odds(
                match_id, 'Bet365', b365_odds, home_team, away_team, timestamp
            ))
        
        # Safely get sport and league IDs
        sport_id = sport.lower().replace(' ', '_')
        league_id = league.lower().replace(' ', '_')
        
        # Build game object
        game_obj = {
            "id": match_id,
            "game_id": f"{sport_id}-{match_id}",
            "start_date": iso_date,
            "home_competitors": [
                {
                    "id": None,
                    "name": home_team,
                    "abbreviation": ''.join([w[0] for w in home_team.split()]).upper() if home_team else "",
                    "logo": None
                }
            ],
            "away_competitors": [
                {
                    "id": None,
                    "name": away_team,
                    "abbreviation": ''.join([w[0] for w in away_team.split()]).upper() if away_team else "",
                    "logo": None
                }
            ],
            "home_team_display": home_team,
            "away_team_display": away_team,
            "status": "live" if is_live else "unplayed",
            "is_live": is_live,
            "sport": {
                "id": sport_id,
                "name": sport
            },
            "league": {
                "id": league_id,
                "name": league
            },
            "tournament": None,
            "odds": odds
        }
        
        return game_obj
    
    @staticmethod
    def _convert_bookmaker_odds(match_id: str, sportsbook: str, odds_data: Dict, 
                                home_team: str, away_team: str, timestamp: float) -> List[Dict]:
        """Convert bookmaker odds to OpticOdds format"""
        odds_list = []
        
        # Helper to convert odds string to integer
        def odds_to_int(odds_str):
            if odds_str is None:
                return None
            try:
                # Remove '+' and convert to int
                return int(str(odds_str).replace('+', ''))
            except:
                return None
        
        # Handle different odds formats:
        # Format 1: home_odds, away_odds, draw_odds (current bet365 format)
        # Format 2: moneyline_home, moneyline_away (unified format)
        
        # Moneyline odds - check both formats
        home_odds = odds_to_int(odds_data.get('home_odds') or odds_data.get('moneyline_home'))
        away_odds = odds_to_int(odds_data.get('away_odds') or odds_data.get('moneyline_away'))
        draw_odds = odds_to_int(odds_data.get('draw_odds') or odds_data.get('draw'))
        
        if home_odds is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:moneyline:home",
                "sportsbook": sportsbook,
                "market": "Moneyline",
                "name": home_team,
                "is_main": True,
                "selection": home_team,
                "normalized_selection": home_team.lower().replace(' ', '_'),
                "market_id": "moneyline",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": home_odds,
                "timestamp": timestamp,
                "grouping_key": "default",
                "points": None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        if away_odds is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:moneyline:away",
                "sportsbook": sportsbook,
                "market": "Moneyline",
                "name": away_team,
                "is_main": True,
                "selection": away_team,
                "normalized_selection": away_team.lower().replace(' ', '_'),
                "market_id": "moneyline",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": away_odds,
                "timestamp": timestamp,
                "grouping_key": "default",
                "points": None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        # Spread odds
        spread_home = odds_to_int(odds_data.get('spread_home'))
        spread_away = odds_to_int(odds_data.get('spread_away'))
        spread_home_line = odds_data.get('spread_home_line')
        spread_away_line = odds_data.get('spread_away_line')
        
        if spread_home is not None and spread_home_line is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:spread:home",
                "sportsbook": sportsbook,
                "market": "Point Spread",
                "name": f"{home_team} {spread_home_line}",
                "is_main": True,
                "selection": home_team,
                "normalized_selection": home_team.lower().replace(' ', '_'),
                "market_id": "spread",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": spread_home,
                "timestamp": timestamp,
                "grouping_key": f"default:{spread_home_line}",
                "points": float(spread_home_line) if isinstance(spread_home_line, (int, float, str)) else None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        if spread_away is not None and spread_away_line is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:spread:away",
                "sportsbook": sportsbook,
                "market": "Point Spread",
                "name": f"{away_team} {spread_away_line}",
                "is_main": True,
                "selection": away_team,
                "normalized_selection": away_team.lower().replace(' ', '_'),
                "market_id": "spread",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": spread_away,
                "timestamp": timestamp,
                "grouping_key": f"default:{spread_away_line}",
                "points": float(spread_away_line) if isinstance(spread_away_line, (int, float, str)) else None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        # Total (Over/Under) odds
        total_over = odds_to_int(odds_data.get('total_over'))
        total_under = odds_to_int(odds_data.get('total_under'))
        total_line = odds_data.get('total_line')
        
        if total_over is not None and total_line is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:total:over",
                "sportsbook": sportsbook,
                "market": "Total Points",
                "name": f"Over {total_line}",
                "is_main": True,
                "selection": "",
                "normalized_selection": "",
                "market_id": "total",
                "selection_line": "over",
                "player_id": None,
                "team_id": None,
                "price": total_over,
                "timestamp": timestamp,
                "grouping_key": f"default:{total_line}",
                "points": float(total_line) if isinstance(total_line, (int, float, str)) else None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        if total_under is not None and total_line is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:total:under",
                "sportsbook": sportsbook,
                "market": "Total Points",
                "name": f"Under {total_line}",
                "is_main": True,
                "selection": "",
                "normalized_selection": "",
                "market_id": "total",
                "selection_line": "under",
                "player_id": None,
                "team_id": None,
                "price": total_under,
                "timestamp": timestamp,
                "grouping_key": f"default:{total_line}",
                "points": float(total_line) if isinstance(total_line, (int, float, str)) else None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        # Draw odds (for sports like Soccer)
        if draw_odds is not None:
            odds_list.append({
                "id": f"{match_id}:{sportsbook.lower()}:moneyline:draw",
                "sportsbook": sportsbook,
                "market": "Moneyline",
                "name": "Draw",
                "is_main": True,
                "selection": "Draw",
                "normalized_selection": "draw",
                "market_id": "moneyline",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": draw_odds,
                "timestamp": timestamp,
                "grouping_key": "default",
                "points": None,
                "betlink": odds_data.get('url', ''),
                "limits": None
            })
        
        return odds_list
    
    @staticmethod
    def convert_future_to_optic_odds(future_data: Dict) -> Dict:
        """
        Convert 1xbet futures/outright event to OpticOdds format
        
        Args:
            future_data: Future event with selections and odds
        """
        # Build odds array from selections
        odds = []
        timestamp = datetime.now().timestamp()
        
        for selection in future_data.get('selections', []):
            odds.append({
                "id": f"1xbet_future_{future_data.get('event_id')}_{selection.get('selection_id')}",
                "sportsbook": "1xBet",
                "market": future_data.get('market_type', 'Winner'),
                "name": selection.get('selection_name', 'Unknown'),
                "is_main": True,
                "selection": selection.get('selection_name', 'Unknown'),
                "normalized_selection": selection.get('selection_name', '').lower().replace(' ', '_'),
                "market_id": "outright_winner",
                "selection_line": None,
                "player_id": None,
                "team_id": None,
                "price": selection.get('coefficient'),
                "american_odds": selection.get('american_odds'),
                "timestamp": timestamp,
                "grouping_key": "default",
                "points": selection.get('param'),
                "betlink": "",
                "limits": None
            })
        
        event_name = future_data.get('event_name', '')
        
        return {
            "id": f"1xbet_future_{future_data.get('event_id')}",
            "game_id": f"1xbet_future_{future_data.get('event_id')}",
            "start_date": future_data.get('start_time_readable', ''),
            "home_competitors": [{
                "id": None,
                "name": event_name,
                "abbreviation": "",
                "logo": None
            }],
            "away_competitors": [],
            "status": "scheduled",
            "event_status": "pregame",
            "sport": {
                "id": future_data.get('sport_id'),
                "name": future_data.get('sport_name', 'Long-term bets')
            },
            "league": {
                "id": future_data.get('league_id'),
                "name": future_data.get('league_name', ''),
                "logo": None
            },
            "is_live": False,
            "odds": odds,
            "metadata": {
                "event_id": future_data.get('event_id'),
                "country": future_data.get('country'),
                "market_type": future_data.get('market_type'),
                "total_selections": future_data.get('total_selections', len(odds)),
                "type": "future"
            }
        }


class EternityFormatConverter:
    """Convert odds data to Eternity API format"""
    
    @staticmethod
    def convert_unified_to_eternity(unified_data: Dict) -> Dict:
        """Convert unified_odds.json format to Eternity format"""
        bets_data = []
        
        # Process pregame matches
        for match in unified_data.get('pregame_matches', []):
            bets = EternityFormatConverter._convert_match_to_eternity(match, is_live=False)
            bets_data.extend(bets)
        
        # Process live matches
        for match in unified_data.get('live_matches', []):
            bets = EternityFormatConverter._convert_match_to_eternity(match, is_live=True)
            bets_data.extend(bets)
        
        return {"data": bets_data}
    
    @staticmethod
    def _convert_match_to_eternity(match: Dict, is_live: bool = False) -> List[Dict]:
        """Convert a single match to Eternity format"""
        bets = []
        
        # Extract basic match info
        sport = match.get('sport', 'Unknown')
        league = match.get('league', 'Unknown')
        home_team = match.get('home_team', '')
        away_team = match.get('away_team', '')
        start_time = match.get('start_time', '')
        
        # Generate team abbreviations
        away_brief = ''.join([w[0] for w in away_team.split()]).upper() if away_team else ''
        home_brief = ''.join([w[0] for w in home_team.split()]).upper() if home_team else ''
        
        # Parse start time to ISO format
        try:
            if 'T' in start_time:
                iso_date = start_time
            else:
                dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except:
            iso_date = start_time or datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Process each bookmaker
        for bookmaker in ['1xbet', 'fanduel', 'bet365']:
            if match.get(bookmaker, {}).get('available'):
                bookmaker_data = match[bookmaker]
                book_name = '1xBet' if bookmaker == '1xbet' else 'FanDuel' if bookmaker == 'fanduel' else 'Bet365'
                
                # Handle nested odds structure: bookmaker.odds.moneyline_home OR direct: bookmaker.moneyline_home
                odds_data = bookmaker_data.get('odds', bookmaker_data)
                betlink = bookmaker_data.get('url', '')
                
                # Moneyline bets
                if odds_data.get('moneyline_home') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": None,
                        "am_odds": odds_data.get('moneyline_home'),
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
                
                if odds_data.get('moneyline_away') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": None,
                        "am_odds": odds_data.get('moneyline_away'),
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
                
                # Spread bets
                if odds_data.get('spread_home') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": odds_data.get('spread_home_line'),
                        "am_odds": odds_data.get('spread_home'),
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
                
                if odds_data.get('spread_away') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": odds_data.get('spread_away_line'),
                        "am_odds": odds_data.get('spread_away'),
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
                
                # Total bets
                if odds_data.get('total_over') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": odds_data.get('total_line'),
                        "am_odds": odds_data.get('total_over'),
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
                
                if odds_data.get('total_under') is not None:
                    bets.append({
                        "league": league,
                        "limit": None,
                        "tournament": None,
                        "start_date": iso_date,
                        "book": book_name,
                        "bet_player": None,
                        "sgp": None,
                        "is_main": True,
                        "away_brief": away_brief,
                        "line": odds_data.get('total_line'),
                        "am_odds": odds_data.get('total_under'),
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
        
        return bets


def filter_by_bookmaker(unified_data: Dict, bookmaker: str) -> Dict:
    """Filter unified odds data to only include specific bookmaker"""
    filtered_data = {
        'metadata': unified_data.get('metadata', {}),
        'pregame_matches': [],
        'live_matches': []
    }
    
    bookmaker_key = bookmaker.lower()
    
    # Filter pregame matches
    for match in unified_data.get('pregame_matches', []):
        if match.get(bookmaker_key, {}).get('available'):
            filtered_match = {
                'match_id': match.get('match_id'),
                'sport': match.get('sport'),
                'league': match.get('league'),
                'home_team': match.get('home_team'),
                'away_team': match.get('away_team'),
                'start_time': match.get('start_time'),
                bookmaker_key: match.get(bookmaker_key)
            }
            filtered_data['pregame_matches'].append(filtered_match)
    
    # Filter live matches
    for match in unified_data.get('live_matches', []):
        if match.get(bookmaker_key, {}).get('available'):
            filtered_match = {
                'match_id': match.get('match_id'),
                'sport': match.get('sport'),
                'league': match.get('league'),
                'home_team': match.get('home_team'),
                'away_team': match.get('away_team'),
                'start_time': match.get('start_time'),
                bookmaker_key: match.get(bookmaker_key)
            }
            filtered_data['live_matches'].append(filtered_match)
    
    return filtered_data
