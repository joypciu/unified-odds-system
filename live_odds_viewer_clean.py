#!/usr/bin/env python3
"""
Live Odds Viewer - Modern Web UI with FastAPI
Real-time monitoring of unified_odds.json and source files
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import uvicorn

# Import format converters
from odds_format_converters import OpticOddsConverter, EternityFormatConverter, filter_by_bookmaker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events"""
    # Startup
    asyncio.create_task(monitor_files())
    yield
    # Shutdown - cleanup if needed
    pass

app = FastAPI(title="Live Odds Viewer", lifespan=lifespan)

# Base directory
BASE_DIR = Path(__file__).parent

# Email configuration (can be set via environment variables)
EMAIL_CONFIG = {
    'enabled': False,
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'username': '',  # Set via environment or config
    'password': '',  # Set via environment or config
}

class EmailAlert(BaseModel):
    email: EmailStr
    alert: Dict


def format_betlink(*, betlink=None, sportsbook=None, state_info=None):
    """Format betlink for different sportsbooks based on location"""
    assert sportsbook is not None
    if not betlink:
        return None
    if (not "{country}" in betlink) and (not "{state}" in betlink):
        return betlink

    if not state_info or state_info == "default":
        return None

    state_info = state_info.lower().strip()
    if ',' not in state_info:
        return None

    try:
        state, country = state_info.split(",")
        state = state.strip()
        country = country.strip()
    except:
        return None

    sportsbook = sportsbook.lower()
    if sportsbook in ['fanduel', '1xbet', 'bet365'] and country == 'ca':
        betlink = betlink.format(country="ca", state='on')
        betlink = betlink.replace(".com", ".ca")
        return betlink

    betlink = betlink.format(country=country, state=state)
    return betlink

# Files to monitor
FILES = {
    'unified': BASE_DIR / "unified_odds.json",
    'bet365_pregame': BASE_DIR / "bet365" / "bet365_current_pregame.json",
    'bet365_live': BASE_DIR / "bet365" / "bet365_live_current.json",
    'fanduel_pregame': BASE_DIR / "fanduel" / "fanduel_pregame.json",
    'fanduel_live': BASE_DIR / "fanduel" / "fanduel_live.json",
    '1xbet_pregame': BASE_DIR / "1xbet" / "1xbet_pregame.json",
    '1xbet_live': BASE_DIR / "1xbet" / "1xbet_live.json"
}

# Track file modifications
last_modified = {}
active_connections: List[WebSocket] = []


def check_file_status() -> Dict:
    """Check status of all monitored files"""
    status = {}
    for name, filepath in FILES.items():
        if filepath.exists():
            stat = filepath.stat()
            status[name] = {
                'exists': True,
                'size': stat.st_size,
                'modified': stat.st_mtime
            }
        else:
            status[name] = {'exists': False, 'size': 0, 'modified': 0}
    return status


def load_individual_json(filepath: Path) -> Dict:
    """Load a single JSON file safely"""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error loading {filepath.name}: {e}")
        # Try to recover by loading from backup if it exists
        backup_path = filepath.with_suffix('.bak')
        if backup_path.exists():
            try:
                print(f"  Attempting to load backup: {backup_path.name}")
                with open(backup_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
    except Exception as e:
        print(f"Error loading {filepath.name}: {e}")
    return {}


def merge_individual_sources() -> Dict:
    """Merge data from individual source JSON files when unified doesn't exist"""
    print("📦 Loading data from individual source files...")
    
    pregame_matches = []
    live_matches = []
    
    # Load Bet365 Pregame - has nested structure: sports_data.{sport}.games[]
    bet365_pregame = load_individual_json(FILES['bet365_pregame'])
    if bet365_pregame and 'sports_data' in bet365_pregame:
        for sport, sport_data in bet365_pregame['sports_data'].items():
            if 'games' in sport_data:
                for match in sport_data['games']:
                    odds_data = match.get('odds', {})
                    moneyline = odds_data.get('moneyline', [])
                    
                    pregame_matches.append({
                        'match_id': f"bet365_pregame_{match.get('game_id', len(pregame_matches))}",
                        'sport': match.get('sport', sport),
                        'league': match.get('sport', sport),
                        'home_team': match.get('team1', 'Unknown'),
                        'away_team': match.get('team2', 'Unknown'),
                        'match_time': f"{match.get('date', 'TBD')} {match.get('time', '')}",
                        'bet365': {
                            'available': True,
                            'home_odds': moneyline[0] if len(moneyline) > 0 else None,
                            'draw_odds': None,
                            'away_odds': moneyline[1] if len(moneyline) > 1 else None
                        }
                    })
    
    # Load FanDuel Pregame - has structure: data.matches[]
    fanduel_pregame = load_individual_json(FILES['fanduel_pregame'])
    if fanduel_pregame and 'data' in fanduel_pregame and 'matches' in fanduel_pregame['data']:
        for match in fanduel_pregame['data']['matches']:
            odds = match.get('odds', {})
            pregame_matches.append({
                'match_id': f"fanduel_pregame_{match.get('match_id', len(pregame_matches))}",
                'sport': match.get('sport', 'Unknown'),
                'league': match.get('league', 'Unknown'),
                'home_team': match.get('home_team', 'Unknown'),
                'away_team': match.get('away_team', 'Unknown'),
                'match_time': match.get('scheduled_time', 'TBD'),
                'fanduel': {
                    'available': True,
                    'home_odds': odds.get('moneyline_home'),
                    'draw_odds': odds.get('moneyline_draw'),
                    'away_odds': odds.get('moneyline_away')
                }
            })
    
    # Load 1xBet Pregame - has structure: matches[]
    xbet_pregame = load_individual_json(FILES['1xbet_pregame'])
    if xbet_pregame and 'matches' in xbet_pregame:
        for match in xbet_pregame['matches']:
            odds = match.get('odds', {})
            pregame_matches.append({
                'match_id': f"1xbet_pregame_{match.get('match_id', len(pregame_matches))}",
                'sport': match.get('sport', 'Unknown'),
                'league': match.get('league', 'Unknown'),
                'home_team': match.get('home_team', 'Unknown'),
                'away_team': match.get('away_team', 'Unknown'),
                'match_time': match.get('start_time', 'TBD'),
                '1xbet': {
                    'available': True,
                    'home_odds': odds.get('home'),
                    'draw_odds': odds.get('draw'),
                    'away_odds': odds.get('away')
                }
            })
    
    # Load Bet365 Live - has structure: matches[] array (from bet365_live_concurrent_scraper.py)
    bet365_live = load_individual_json(FILES['bet365_live'])
    if bet365_live and 'matches' in bet365_live:
        for match in bet365_live['matches']:
            # bet365 live provides home_team/away_team directly
            home_team = match.get('home_team', '') or match.get('teams', {}).get('home', '')
            away_team = match.get('away_team', '') or match.get('teams', {}).get('away', '')
            
            odds_data = match.get('odds', {})
            
            live_matches.append({
                'match_id': f"bet365_live_{match.get('match_id', len(live_matches))}",
                'sport': match.get('sport', match.get('sport_name', 'Unknown')),
                'league': match.get('sport', match.get('sport_name', 'Unknown')),
                'home_team': home_team,
                'away_team': away_team,
                'match_time': 'LIVE',
                'bet365': {
                    'available': True,
                    'home_odds': odds_data.get('home') or odds_data.get('moneyline', [None])[0],
                    'draw_odds': odds_data.get('draw'),
                    'away_odds': odds_data.get('away') or odds_data.get('moneyline', [None, None])[1]
                }
            })
    
    # Load FanDuel Live - has structure: data.matches[]
    fanduel_live = load_individual_json(FILES['fanduel_live'])
    if fanduel_live and 'data' in fanduel_live and 'matches' in fanduel_live['data']:
        for match in fanduel_live['data']['matches']:
            odds = match.get('odds', {})
            live_matches.append({
                'match_id': f"fanduel_live_{match.get('match_id', len(live_matches))}",
                'sport': match.get('sport', 'Unknown'),
                'league': match.get('league', 'Unknown'),
                'home_team': match.get('home_team', 'Unknown'),
                'away_team': match.get('away_team', 'Unknown'),
                'match_time': 'LIVE',
                'fanduel': {
                    'available': True,
                    'home_odds': odds.get('moneyline_home'),
                    'draw_odds': odds.get('moneyline_draw'),
                    'away_odds': odds.get('moneyline_away')
                }
            })
    
    # Load 1xBet Live - has structure: matches[]
    xbet_live = load_individual_json(FILES['1xbet_live'])
    if xbet_live and 'matches' in xbet_live:
        for match in xbet_live['matches']:
            odds = match.get('odds', {})
            live_matches.append({
                'match_id': f"1xbet_live_{match.get('match_id', len(live_matches))}",
                'sport': match.get('sport', 'Unknown'),
                'league': match.get('league', 'Unknown'),
                'home_team': match.get('home_team', 'Unknown'),
                'away_team': match.get('away_team', 'Unknown'),
                'match_time': 'LIVE',
                '1xbet': {
                    'available': True,
                    'home_odds': odds.get('home'),
                    'draw_odds': odds.get('draw'),
                    'away_odds': odds.get('away')
                }
            })
    
    print(f"✅ Loaded {len(pregame_matches)} pregame matches and {len(live_matches)} live matches from individual sources")
    
    return {
        'pregame_matches': pregame_matches,
        'live_matches': live_matches,
        'metadata': {
            'source': 'individual_files',
            'timestamp': datetime.now().isoformat(),
            'note': 'Data loaded from individual bookmaker files (unified_odds.json not yet available)'
        }
    }


def load_unified_data() -> Dict:
    """Load unified odds data, fallback to individual sources if unified doesn't exist"""
    try:
        unified_file = FILES['unified']
        if unified_file.exists():
            # Try main file first
            try:
                with open(unified_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['metadata'] = data.get('metadata', {})
                    data['metadata']['source'] = 'unified_file'
                    return data
            except json.JSONDecodeError as e:
                print(f"⚠ Unified file corrupted: {e}")
                
                # Try backup file
                backup_file = unified_file.with_suffix('.json.bak')
                if backup_file.exists():
                    print(f"  Attempting to load backup: {backup_file.name}")
                    try:
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            data['metadata'] = data.get('metadata', {})
                            data['metadata']['source'] = 'unified_file_backup'
                            print("  ✓ Loaded from backup successfully")
                            return data
                    except:
                        print("  ✗ Backup also corrupted")
                
                # Fall back to individual sources
                print("  Loading from individual sources instead")
                return merge_individual_sources()
        else:
            # Unified file doesn't exist yet, load from individual sources
            return merge_individual_sources()
    except Exception as e:
        print(f"Error loading unified data: {e}")
        # Try loading from individual sources as fallback
        return merge_individual_sources()


async def monitor_files():
    """Monitor files for changes and broadcast updates"""
    global last_modified
    
    while True:
        try:
            # Check file statuses
            status = check_file_status()
            
            should_reload = False
            data_source = 'unified'
            
            # Check if unified file exists and changed
            unified_file = FILES['unified']
            if unified_file.exists():
                current_mtime = status['unified']['modified']
                
                if 'unified' not in last_modified or current_mtime > last_modified['unified']:
                    last_modified['unified'] = current_mtime
                    should_reload = True
                    data_source = 'unified'
            else:
                # Unified doesn't exist, check individual files
                for name in ['bet365_pregame', 'bet365_live', 'fanduel_pregame', 'fanduel_live', '1xbet_pregame', '1xbet_live']:
                    if status[name]['exists']:
                        current_mtime = status[name]['modified']
                        if name not in last_modified or current_mtime > last_modified[name]:
                            last_modified[name] = current_mtime
                            should_reload = True
                            data_source = 'individual'
            
            # Reload and broadcast if any file changed
            if should_reload:
                data = load_unified_data()
                message = {
                    'type': 'data_update',
                    'data': data,
                    'timestamp': datetime.now().isoformat(),
                    'source': data_source
                }
                
                await broadcast(message)
            
            # Broadcast status update
            status_message = {
                'type': 'status_update',
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            await broadcast(status_message)
            
            await asyncio.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(2)


async def broadcast(message: dict):
    """Broadcast message to all connected clients"""
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)


@app.post("/api/send-email")
async def send_email_alert(alert_data: EmailAlert):
    """Send email alert for monitoring issues"""
    try:
        if not EMAIL_CONFIG['enabled']:
            print(f"📧 Email Alert (Not Configured):")
            print(f"   To: {alert_data.email}")
            print(f"   Title: {alert_data.alert.get('title', 'Alert')}")
            print(f"   Message: {alert_data.alert.get('message', '')}")
            return {"success": True, "message": "Email logged (SMTP not configured)"}

        # Production code for actual email sending:
        # import smtplib
        # from email.mime.text import MIMEText
        # msg = MIMEText(alert_data.alert['message'])
        # msg['Subject'] = f"Odds Viewer Alert: {alert_data.alert['title']}"
        # msg['From'] = EMAIL_CONFIG['username']
        # msg['To'] = alert_data.email
        #
        # with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
        #     server.starttls()
        #     server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
        #     server.send_message(msg)

        return {"success": True, "message": "Alert logged"}
    except Exception as e:
        print(f"Error processing email alert: {e}")
        return {"success": False, "message": str(e)}


@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Serve the main HTML page"""
    html_content = open('odds_viewer_template.html', 'r', encoding='utf-8').read()
    return HTMLResponse(content=html_content)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial data
        data = load_unified_data()
        status = check_file_status()
        
        await websocket.send_json({
            'type': 'data_update',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
        await websocket.send_json({
            'type': 'status_update',
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.get("/api/matches")
async def get_matches():
    """API endpoint to get all matches"""
    data = load_unified_data()
    return data


@app.get("/api/matches/sport/{sport}")
async def get_matches_by_sport(sport: str):
    """API endpoint to get matches for a specific sport"""
    data = load_unified_data()
    all_matches = data.get('pregame_matches', []) + data.get('live_matches', [])

    # Filter matches by sport (case insensitive)
    filtered_matches = [
        match for match in all_matches
        if match.get('sport', '').lower() == sport.lower()
    ]

    return {
        'matches': filtered_matches,
        'sport': sport,
        'count': len(filtered_matches),
        'metadata': data.get('metadata', {})
    }


@app.get("/api/matches/bookmaker/{bookmaker}")
async def get_matches_by_bookmaker(bookmaker: str):
    """API endpoint to get matches available on a specific bookmaker"""
    data = load_unified_data()
    all_matches = data.get('pregame_matches', []) + data.get('live_matches', [])

    # Filter matches that have data for this bookmaker
    filtered_matches = [
        match for match in all_matches
        if bookmaker.lower() in match and match[bookmaker.lower()].get('available', False)
    ]

    return {
        'matches': filtered_matches,
        'bookmaker': bookmaker,
        'count': len(filtered_matches),
        'metadata': data.get('metadata', {})
    }


@app.get("/api/matches/live")
async def get_live_matches():
    """API endpoint to get only live matches"""
    data = load_unified_data()
    live_matches = data.get('live_matches', [])

    return {
        'matches': live_matches,
        'type': 'live',
        'count': len(live_matches),
        'metadata': data.get('metadata', {})
    }


@app.get("/api/matches/pregame")
async def get_pregame_matches():
    """API endpoint to get only pregame matches"""
    data = load_unified_data()
    pregame_matches = data.get('pregame_matches', [])

    return {
        'matches': pregame_matches,
        'type': 'pregame',
        'count': len(pregame_matches),
        'metadata': data.get('metadata', {})
    }


@app.get("/api/betlink")
async def get_formatted_betlink(betlink: str, sportsbook: str, state_info: str):
    """API endpoint to format betlinks for different sportsbooks and locations"""
    formatted_link = format_betlink(betlink=betlink, sportsbook=sportsbook, state_info=state_info)
    return {
        'original_betlink': betlink,
        'sportsbook': sportsbook,
        'state_info': state_info,
        'formatted_betlink': formatted_link
    }


@app.get("/api/status")
async def get_status():
    """API endpoint to get file status"""
    return check_file_status()


@app.get("/api/monitoring")
async def get_monitoring_status():
    """API endpoint to get monitoring system status"""
    try:
        # Try to load monitoring status directly from file
        monitoring_status_file = BASE_DIR / "monitoring_status.json"
        if monitoring_status_file.exists():
            with open(monitoring_status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check if data is recent (within last 10 minutes)
                last_updated = data.get('last_updated')
                if last_updated:
                    from datetime import datetime
                    last_update_time = datetime.fromisoformat(last_updated)
                    time_diff = (datetime.now() - last_update_time).total_seconds()
                    
                    # Mark as inactive if not updated recently
                    if time_diff > 600:  # 10 minutes
                        data['monitoring_active'] = False
                        data['warning'] = f'Last updated {int(time_diff/60)} minutes ago'
                
                return data
        else:
            return {
                'monitoring_active': False,
                'message': 'Monitoring system not started - monitoring_status.json not found',
                'summary': {'healthy': 0, 'warnings': 0, 'errors': 0, 'total': 0},
                'modules': {}
            }
    except Exception as e:
        return {
            'monitoring_active': False,
            'error': str(e),
            'message': 'Error reading monitoring status',
            'summary': {'healthy': 0, 'warnings': 0, 'errors': 0, 'total': 0},
            'modules': {}
        }


# ==================== OpticOdds Format API Endpoints ====================

@app.get("/1xbet")
async def get_1xbet_optic_odds():
    """Get all 1xBet odds in OpticOdds format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, '1xbet')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/1xbet/pregame")
async def get_1xbet_pregame_optic_odds():
    """Get 1xBet pregame odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only pregame matches
    pregame_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': data.get('pregame_matches', []),
        'live_matches': []
    }
    
    filtered_data = filter_by_bookmaker(pregame_only, '1xbet')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/1xbet/live")
async def get_1xbet_live_optic_odds():
    """Get 1xBet live odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only live matches
    live_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': [],
        'live_matches': data.get('live_matches', [])
    }
    
    filtered_data = filter_by_bookmaker(live_only, '1xbet')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/fanduel")
async def get_fanduel_optic_odds():
    """Get all FanDuel odds in OpticOdds format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'fanduel')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/fanduel/pregame")
async def get_fanduel_pregame_optic_odds():
    """Get FanDuel pregame odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only pregame matches
    pregame_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': data.get('pregame_matches', []),
        'live_matches': []
    }
    
    filtered_data = filter_by_bookmaker(pregame_only, 'fanduel')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/fanduel/live")
async def get_fanduel_live_optic_odds():
    """Get FanDuel live odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only live matches
    live_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': [],
        'live_matches': data.get('live_matches', [])
    }
    
    filtered_data = filter_by_bookmaker(live_only, 'fanduel')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/bet365")
async def get_bet365_optic_odds():
    """Get all Bet365 odds in OpticOdds format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'bet365')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/bet365/pregame")
async def get_bet365_pregame_optic_odds():
    """Get Bet365 pregame odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only pregame matches
    pregame_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': data.get('pregame_matches', []),
        'live_matches': []
    }
    
    filtered_data = filter_by_bookmaker(pregame_only, 'bet365')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/bet365/live")
async def get_bet365_live_optic_odds():
    """Get Bet365 live odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only live matches
    live_only = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': [],
        'live_matches': data.get('live_matches', [])
    }
    
    filtered_data = filter_by_bookmaker(live_only, 'bet365')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/bet365/soccer")
async def get_bet365_soccer_optic_odds():
    """Get Bet365 soccer odds in OpticOdds format"""
    data = load_unified_data()
    
    # Filter for only soccer matches
    all_matches = data.get('pregame_matches', []) + data.get('live_matches', [])
    soccer_matches = [m for m in all_matches if m.get('sport', '').lower() in ['soccer', 'football']]
    
    soccer_data = {
        'metadata': data.get('metadata', {}),
        'pregame_matches': [m for m in soccer_matches if m in data.get('pregame_matches', [])],
        'live_matches': [m for m in soccer_matches if m in data.get('live_matches', [])]
    }
    
    filtered_data = filter_by_bookmaker(soccer_data, 'bet365')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


# ==================== Eternity Format API Endpoints ====================

@app.get("/eternity/1xbet")
async def get_1xbet_eternity_format():
    """Get all 1xBet odds in Eternity format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, '1xbet')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


@app.get("/eternity/fanduel")
async def get_fanduel_eternity_format():
    """Get all FanDuel odds in Eternity format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'fanduel')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


@app.get("/eternity/bet365")
async def get_bet365_eternity_format():
    """Get all Bet365 odds in Eternity format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'bet365')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


if __name__ == "__main__":
    print("\n" + "="*80)
    print("⚡ LIVE ODDS VIEWER - Web Interface")
    print("="*80)
    print("\n🌐 Starting server at: http://localhost:8000")
    print("📊 Monitoring files for real-time updates")
    print("\n✨ Open http://localhost:8000 in your browser")
    print("\nPress CTRL+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
