#!/usr/bin/env python3
"""
Live Odds Viewer - Modern Web UI with FastAPI
Real-time monitoring of unified_odds.json and source files
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, EmailStr
import json
import asyncio
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import uvicorn
import sys
from pathlib import Path as PathlibPath

# Add parent directory to path for imports
sys.path.insert(0, str(PathlibPath(__file__).parent.parent))

# Import format converters
from utils.converters.odds_format_converters import OpticOddsConverter, EternityFormatConverter, filter_by_bookmaker
from utils.helpers.history_manager import HistoryManager
from utils.security.secure_config import SecureConfig

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events"""
    # Startup
    asyncio.create_task(monitor_files())
    yield
    # Shutdown - cleanup if needed
    pass

app = FastAPI(title="Live Odds Viewer", lifespan=lifespan)

# Add GZip compression middleware for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Base directory - should be project root, not core/
BASE_DIR = Path(__file__).parent.parent

# Initialize history manager
history_manager = HistoryManager(str(BASE_DIR))

# Load enabled scrapers from config
def load_enabled_scrapers() -> Dict[str, bool]:
    """Load enabled scrapers from encrypted config.json"""
    try:
        config_file = BASE_DIR / "config" / "config.json"
        if config_file.exists():
            secure_config = SecureConfig(str(config_file))
            config = secure_config.load_config()
            return config.get('enabled_scrapers', {
                '1xbet': True,
                'fanduel': True,
                'bet365': False
            })
    except Exception as e:
        print(f"⚠️  Error loading config, using defaults: {e}")
    return {'1xbet': True, 'fanduel': True, 'bet365': False}

ENABLED_SCRAPERS = load_enabled_scrapers()
print(f"📋 Enabled scrapers: {ENABLED_SCRAPERS}")

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
    'unified': BASE_DIR / "data" / "unified_odds.json",
    'bet365_pregame': BASE_DIR / "bookmakers" / "bet365" / "bet365_current_pregame.json",
    'bet365_live': BASE_DIR / "bookmakers" / "bet365" / "bet365_live_current.json",
    'fanduel_pregame': BASE_DIR / "bookmakers" / "fanduel" / "fanduel_pregame.json",
    'fanduel_live': BASE_DIR / "bookmakers" / "fanduel" / "fanduel_live.json",
    '1xbet_pregame': BASE_DIR / "bookmakers" / "1xbet" / "1xbet_pregame.json",
    '1xbet_live': BASE_DIR / "bookmakers" / "1xbet" / "1xbet_live.json"
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
    """Merge data from individual source JSON files (only from enabled scrapers)"""
    print("📦 Loading data from enabled scrapers...")
    print(f"   Enabled: {', '.join([k for k, v in ENABLED_SCRAPERS.items() if v])}")
    
    pregame_matches = []
    live_matches = []
    
    # Load Bet365 Pregame - only if enabled
    if ENABLED_SCRAPERS.get('bet365', False):
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
    else:
        print("   ⏭️  Skipping bet365 (disabled)")
    
    # Load FanDuel Pregame - only if enabled
    if ENABLED_SCRAPERS.get('fanduel', False):
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
    else:
        print("   ⏭️  Skipping fanduel (disabled)")
    
    # Load 1xBet Pregame - only if enabled
    if ENABLED_SCRAPERS.get('1xbet', False):
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
    else:
        print("   ⏭️  Skipping 1xbet (disabled)")
    
    # Load Bet365 Live - only if enabled
    if ENABLED_SCRAPERS.get('bet365', False):
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
    else:
        print("   ⏭️  Skipping bet365 live (disabled)")
    
    # Load FanDuel Live - only if enabled
    if ENABLED_SCRAPERS.get('fanduel', False):
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
    else:
        print("   ⏭️  Skipping fanduel live (disabled)")
    
    # Load 1xBet Live - only if enabled
    if ENABLED_SCRAPERS.get('1xbet', False):
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
    else:
        print("   ⏭️  Skipping 1xbet live (disabled)")
    
    enabled_list = ', '.join([k for k, v in ENABLED_SCRAPERS.items() if v])
    print(f"✅ Loaded {len(pregame_matches)} pregame and {len(live_matches)} live matches from enabled scrapers: {enabled_list}")
    
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
    
    # Track last history cleanup time
    last_cleanup_time = 0
    cleanup_interval = 300  # Clean every 5 minutes
    
    while True:
        try:
            # Periodic history cleanup
            current_time = time.time()
            if current_time - last_cleanup_time > cleanup_interval:
                try:
                    results = history_manager.clean_all()
                    total_moved = sum(results.values())
                    if total_moved > 0:
                        print(f"🧹 Cleaned {total_moved} old/completed matches")
                except Exception as e:
                    print(f"⚠ History cleanup error: {e}")
                last_cleanup_time = current_time
            
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
    template_path = BASE_DIR / 'html' / 'odds_viewer_template.html'
    html_content = open(template_path, 'r', encoding='utf-8').read()
    return HTMLResponse(content=html_content)


@app.get("/oddsmagnet", response_class=HTMLResponse)
async def get_oddsmagnet_page():
    """Serve the OddsMagnet viewer page"""
    template_path = BASE_DIR / 'html' / 'oddsmagnet_viewer.html'
    if not template_path.exists():
        return HTMLResponse(content="<h1>OddsMagnet viewer not found</h1>", status_code=404)
    html_content = open(template_path, 'r', encoding='utf-8').read()
    return HTMLResponse(content=html_content)


@app.get("/oddsmagnet/top10", response_class=HTMLResponse)
async def get_oddsmagnet_top10_page():
    """Serve the optimized OddsMagnet Top 10 viewer page with progressive loading"""
    template_path = BASE_DIR / 'html' / 'oddsmagnet_top10_optimized.html'
    if not template_path.exists():
        return HTMLResponse(content="<h1>OddsMagnet Top 10 viewer not found</h1>", status_code=404)
    html_content = open(template_path, 'r', encoding='utf-8').read()
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
        monitoring_status_file = BASE_DIR / "data" / "monitoring_status.json"
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


@app.get("/api/history")
async def get_history():
    """Get historical/completed matches from all sources"""
    try:
        history_matches = []
        
        # Load 1xBet history
        xbet_history_file = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_history.json"
        if xbet_history_file.exists():
            with open(xbet_history_file, 'r', encoding='utf-8') as f:
                xbet_data = json.load(f)
                for match in xbet_data.get('pregame', [])[:100]:  # Limit to 100 recent
                    # Parse odds_data if it's a string
                    odds_data = match.get('odds_data', {})
                    if isinstance(odds_data, str):
                        try:
                            odds_data = json.loads(odds_data)
                        except:
                            odds_data = {}
                    
                    history_matches.append({
                        'match_id': f"1xbet_{match.get('match_id')}",
                        'sport': match.get('sport_name', ''),
                        'league': match.get('league_name', ''),
                        'home_team': match.get('team1', ''),
                        'away_team': match.get('team2', ''),
                        'start_time': match.get('start_time'),
                        'removed_at': match.get('removed_at'),
                        'odds': odds_data,
                        'country': match.get('country', ''),
                        'bookmakers': ['1xbet']
                    })
        
        return {'matches': history_matches, 'total': len(history_matches)}
    except Exception as e:
        return {'matches': [], 'total': 0, 'error': str(e)}


@app.get("/api/futures")
async def get_futures():
    """Get futures/long-term betting events with selections"""
    try:
        futures_matches = []
        
        # Load 1xBet futures from the proper scraper output
        xbet_futures_file = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_future.json"
        if xbet_futures_file.exists():
            with open(xbet_futures_file, 'r', encoding='utf-8') as f:
                xbet_data = json.load(f)
                
                # This file has events with selections
                for event in xbet_data.get('data', {}).get('events', []):
                    # Extract selections for display
                    selections = event.get('selections', [])
                    
                    # Format for UI display
                    futures_matches.append({
                        'match_id': f"1xbet_{event.get('event_id')}",
                        'sport': event.get('sport_name', 'Long-term bets'),
                        'league': event.get('league_name', ''),
                        'event_name': event.get('event_name', ''),
                        'home_team': event.get('event_name', ''),  # Event name as title
                        'away_team': '',  # Futures don't have away team
                        'start_time': event.get('start_time'),
                        'country': event.get('country', ''),
                        'market_type': event.get('market_type', 'Winner'),
                        'selections': selections[:10],  # Limit to top 10 for display
                        'total_selections': event.get('total_selections', len(selections)),
                        'bookmakers': ['1xbet']
                    })
        else:
            # Fallback to old format if new file doesn't exist
            xbet_futures_old = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_futures.json"
            if xbet_futures_old.exists():
                with open(xbet_futures_old, 'r', encoding='utf-8') as f:
                    xbet_data = json.load(f)
                    for match in xbet_data.get('data', {}).get('matches', []):
                        odds_data = match.get('odds_data', '{}')
                        if isinstance(odds_data, str):
                            try:
                                odds_data = json.loads(odds_data)
                            except:
                                odds_data = {}
                        
                        futures_matches.append({
                            'match_id': f"1xbet_{match.get('match_id')}",
                            'sport': match.get('sport_name', ''),
                            'league': match.get('league_name', ''),
                            'home_team': match.get('team1', ''),
                            'away_team': match.get('team2', ''),
                            'start_time': match.get('start_time'),
                            'country': match.get('country', ''),
                            'odds': odds_data,
                            'bookmakers': ['1xbet']
                        })
        
        return {'matches': futures_matches, 'total': len(futures_matches)}
    except Exception as e:
        return {'matches': [], 'total': 0, 'error': str(e)}


# ==================== OpticOdds Format API Endpoints (Default) ====================

@app.get("/1xbet")
async def get_1xbet_optic_odds():
    """Get all 1xBet odds in OpticOdds format (default)"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, '1xbet')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/1xbet/pregame")
async def get_1xbet_pregame_optic_odds():
    """Get 1xBet pregame odds in OpticOdds format (default)"""
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
    """Get 1xBet live odds in OpticOdds format (default)"""
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


@app.get("/1xbet/history")
async def get_1xbet_history_optic_odds():
    """Get 1xBet historical/completed matches in OpticOdds format"""
    try:
        history_file = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_history.json"
        if not history_file.exists():
            return {"data": [], "message": "No history data available"}
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        # Convert history to unified format for OpticOdds converter
        unified_format = {
            'metadata': history_data.get('metadata', {}),
            'pregame_matches': [],
            'live_matches': []
        }
        
        # Add pregame history
        for match in history_data.get('pregame', []):
            unified_match = {
                'match_id': match.get('match_id'),
                'sport': match.get('sport_name', '').lower(),
                'league': match.get('league_name', ''),
                'home_team': match.get('team1', ''),
                'away_team': match.get('team2', ''),
                'start_time': match.get('scheduled_time') or match.get('start_time'),
                '1xbet': {
                    'available': True,
                    'odds': match.get('odds_data', {}),
                    'removed_at': match.get('removed_at'),
                    'status': match.get('status', 'expired')
                }
            }
            unified_format['pregame_matches'].append(unified_match)
        
        # Add live history
        for match in history_data.get('live', []):
            unified_match = {
                'match_id': match.get('match_id'),
                'sport': match.get('sport_name', '').lower(),
                'league': match.get('league', ''),
                'home_team': match.get('team1', ''),
                'away_team': match.get('team2', ''),
                'start_time': match.get('start_time'),
                'score': f"{match.get('score1', 0)}-{match.get('score2', 0)}",
                '1xbet': {
                    'available': True,
                    'odds': match.get('odds', {}),
                    'removed_at': match.get('removed_at'),
                    'status': match.get('status', 'completed')
                }
            }
            unified_format['live_matches'].append(unified_match)
        
        optic_format = OpticOddsConverter.convert_unified_to_optic(unified_format)
        optic_format['metadata'] = history_data.get('metadata', {})
        return optic_format
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading history: {str(e)}")


@app.get("/1xbet/future")
async def get_1xbet_future_optic_odds():
    """Get 1xBet future/long-term events in OpticOdds format"""
    try:
        # Primary futures file
        futures_file_path = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_future.json"
        
        # Legacy fallback files
        futures_with_odds_file = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_futures_with_odds.json"
        futures_basic_file = BASE_DIR / "bookmakers" / "1xbet" / "1xbet_futures.json"
        
        futures_file = None
        has_proper_odds = False
        
        if futures_file_path.exists():
            futures_file = futures_file_path
            has_proper_odds = True
        elif futures_with_odds_file.exists():
            futures_file = futures_with_odds_file
            has_proper_odds = True
        elif futures_basic_file.exists():
            futures_file = futures_basic_file
            has_proper_odds = False
        else:
            return {"data": [], "message": "No futures data available. Run run_futures_collection.py to collect futures with odds."}
        
        with open(futures_file, 'r', encoding='utf-8') as f:
            futures_data = json.load(f)
        
        # Convert based on format
        converter = OpticOddsConverter()
        optic_odds_data = []
        
        if has_proper_odds:
            # New format with selections
            items = futures_data.get('data', {}).get('events', [])
            for item in items:
                converted = converter.convert_future_to_optic_odds(item)
                if converted:
                    optic_odds_data.append(converted)
        else:
            # Old format (basic match structure)
            items = futures_data.get('data', {}).get('matches', [])
            for item in items:
                converted = converter.convert_to_optic_odds(item, "1xbet", "futures")
                if converted:
                    optic_odds_data.append(converted)
        
        return {
            "success": True,
            "data": optic_odds_data,
            "count": len(optic_odds_data),
            "bookmaker": "1xbet",
            "type": "futures",
            "has_odds": has_proper_odds,
            "metadata": futures_data.get('metadata', {}),
            "note": "Run run_futures_collection.py to get futures with proper odds" if not has_proper_odds else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading futures: {str(e)}")


@app.get("/fanduel")
async def get_fanduel_optic_odds():
    """Get all FanDuel odds in OpticOdds format (default)"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'fanduel')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/fanduel/pregame")
async def get_fanduel_pregame_optic_odds():
    """Get FanDuel pregame odds in OpticOdds format (default)"""
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
    """Get FanDuel live odds in OpticOdds format (default)"""
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


@app.get("/oddsmagnet/football")
async def get_oddsmagnet_football(
    page: int = 1,
    page_size: int = 50,
    league: str = None,
    search: str = None
):
    """Get all OddsMagnet football matches with pagination and filtering
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 200)
    - league: Filter by league name (partial match, case-insensitive)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 200)  # Max 200 per page
        
        oddsmagnet_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_realtime.json"
        if not oddsmagnet_file.exists():
            return {
                'error': 'OddsMagnet data not available',
                'message': 'Real-time collector not running',
                'matches': []
            }
        
        with open(oddsmagnet_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        all_matches = data.get('matches', [])
        
        # Apply filters
        filtered_matches = all_matches
        if league:
            league_lower = league.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if league_lower in m.get('league', '').lower()
            ]
        
        if search:
            search_lower = search.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if search_lower in m.get('match_name', '').lower()
            ]
        
        # Calculate pagination
        total_filtered = len(filtered_matches)
        total_pages = (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = filtered_matches[start_idx:end_idx]
        
        return {
            'source': 'oddsmagnet',
            'timestamp': data.get('timestamp'),
            'iteration': data.get('iteration'),
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_filtered,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'filters': {
                'league': league,
                'search': search
            },
            'total_matches': len(all_matches),
            'matches': paginated_matches
        }
    except Exception as e:
        return {
            'error': str(e),
            'matches': []
        }


@app.get("/oddsmagnet/football/top10")
async def get_oddsmagnet_top10(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet football matches from top 10 leagues with pagination and filtering
    
    This endpoint uses a dedicated collector that tracks ONLY the top 10 leagues.
    Supports ETag caching for faster subsequent loads.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league from top 10 (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from dedicated top 10 leagues collector
        # Try top10 file first, fall back to realtime file
        oddsmagnet_top10_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_top10.json"
        oddsmagnet_realtime_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_realtime.json"
        
        data_file = None
        if oddsmagnet_top10_file.exists():
            data_file = oddsmagnet_top10_file
        elif oddsmagnet_realtime_file.exists():
            data_file = oddsmagnet_realtime_file
        
        if not data_file:
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Top 10 data not available',
                    'message': 'Top 10 leagues collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_top10_realtime.py',
                    'matches': []
                }
            )
        
        # Check file modification time for ETag
        file_mtime = data_file.stat().st_mtime
        file_size = data_file.stat().st_size
        
        # Generate ETag from file metadata + query params
        etag_base = f"{file_mtime}-{file_size}-{page}-{page_size}-{league}-{search}"
        etag = hashlib.md5(etag_base.encode()).hexdigest()
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(status_code=304)  # Not Modified
        
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Data is already filtered to top 10 leagues by dedicated collector
        all_matches = data.get('matches', [])
        
        # Apply additional filters
        filtered_matches = all_matches
        if league:
            league_lower = league.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if league_lower in m.get('league', '').lower() or 
                   league_lower in m.get('match_uri', '').lower()
            ]
        
        if search:
            search_lower = search.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if search_lower in m.get('match_name', '').lower()
            ]
        
        # Calculate pagination
        total_filtered = len(filtered_matches)
        total_pages = (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = filtered_matches[start_idx:end_idx]
        
        response_data = {
            'source': 'oddsmagnet_top10',
            'timestamp': data.get('timestamp'),
            'iteration': data.get('iteration'),
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_filtered,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'filters': {
                'league': league,
                'search': search
            },
            'total_matches': len(all_matches),
            'leagues_tracked': data.get('leagues_tracked', []),
            'total_leagues': data.get('total_leagues', 10),
            'matches': paginated_matches
        }
        
        # Return response with ETag header
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',  # Force revalidation but allow caching
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/bet365")
async def get_bet365_optic_odds():
    """Get all Bet365 odds in OpticOdds format (default)"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'bet365')
    optic_format = OpticOddsConverter.convert_unified_to_optic(filtered_data)
    return optic_format


@app.get("/bet365/pregame")
async def get_bet365_pregame_optic_odds():
    """Get Bet365 pregame odds in OpticOdds format (homepage scraper data)"""
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
    """Get Bet365 live odds in OpticOdds format (concurrent scraper data)"""
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


# ==================== Eternity Format API Endpoints ====================

@app.get("/1xbet/eternity")
async def get_1xbet_eternity_format():
    """Get all 1xBet odds in EternityLabs format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, '1xbet')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


@app.get("/fanduel/eternity")
async def get_fanduel_eternity_format():
    """Get all FanDuel odds in EternityLabs format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'fanduel')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


@app.get("/bet365/eternity")
async def get_bet365_eternity_format():
    """Get all Bet365 odds in EternityLabs format"""
    data = load_unified_data()
    filtered_data = filter_by_bookmaker(data, 'bet365')
    eternity_format = EternityFormatConverter.convert_unified_to_eternity(filtered_data)
    return eternity_format


# Legacy endpoint for backwards compatibility
@app.get("/eternity/1xbet")
async def get_1xbet_eternity_format_legacy():
    """Legacy: Get all 1xBet odds in Eternity format"""
    return await get_1xbet_eternity_format()


@app.get("/eternity/fanduel")
async def get_fanduel_eternity_format_legacy():
    """Legacy: Get all FanDuel odds in Eternity format"""
    return await get_fanduel_eternity_format()


@app.get("/eternity/bet365")
async def get_bet365_eternity_format_legacy():
    """Legacy: Get all Bet365 odds in Eternity format"""
    return await get_bet365_eternity_format()


# ==================== History API Endpoint ====================

@app.get("/history")
async def get_history():
    """Get all completed/historical matches from all bookmakers"""
    history = history_manager.load_history()
    return history


@app.get("/history/{bookmaker}")
async def get_history_by_bookmaker(bookmaker: str):
    """Get historical matches for a specific bookmaker"""
    bookmaker = bookmaker.lower()
    if bookmaker not in ['1xbet', 'fanduel', 'bet365']:
        raise HTTPException(status_code=404, detail=f"Bookmaker '{bookmaker}' not found")
    
    history = history_manager.load_history()
    return {
        'metadata': history.get('metadata', {}),
        'bookmaker': bookmaker,
        'matches': history['matches'].get(bookmaker, {'pregame': [], 'live': []})
    }


@app.post("/api/clean-history")
async def clean_history_now():
    """Manually trigger history cleanup"""
    try:
        results = history_manager.clean_all()
        total_moved = sum(results.values())
        return {
            'success': True,
            'message': f'Moved {total_moved} matches to history',
            'details': results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("\n" + "="*80)
    print("⚡ LIVE ODDS VIEWER - Web Interface")
    print("="*80)
    print("\n🌐 Starting server at: http://localhost:8000")
    print("📊 Monitoring files for real-time updates")
    print("\n✨ Open http://localhost:8000 in your browser")
    print("\nPress CTRL+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
