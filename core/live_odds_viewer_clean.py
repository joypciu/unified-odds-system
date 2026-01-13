#!/usr/bin/env python3
"""
Live Odds Viewer - Modern Web UI with FastAPI
Real-time monitoring of unified_odds.json and source files
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, EmailStr
import json
import asyncio
import time
import hashlib
import gzip
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import uvicorn
import sys
from pathlib import Path as PathlibPath
import aiofiles

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
    asyncio.create_task(push_oddsmagnet_updates())
    yield
    # Shutdown - cleanup if needed
    pass

app = FastAPI(title="Live Odds Viewer", lifespan=lifespan)

# Add GZip compression middleware for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Base directory - should be project root, not core/
BASE_DIR = Path(__file__).parent.parent

# In-memory cache for OddsMagnet data to avoid slow disk reads
# Changed to per-sport caching for real-time updates
oddsmagnet_cache = {
    'football': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'basketball': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'tennis': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'cricket': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'americanfootball': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'baseball': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'tabletennis': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'boxing': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
    'volleyball': {'data': None, 'timestamp': None, 'file_mtime': None, 'cache_key': None},
}

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
            
            await asyncio.sleep(5)  # Check every 5 seconds (optimized)
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(5)


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
    """Serve the OddsMagnet multi-sport viewer page"""
    template_path = BASE_DIR / 'html' / 'oddsmagnet_viewer.html'
    if not template_path.exists():
        return HTMLResponse(content="<h1>OddsMagnet viewer not found</h1>", status_code=404)
    html_content = open(template_path, 'r', encoding='utf-8').read()
    return HTMLResponse(content=html_content)


@app.get("/oddsmagnet/top10", response_class=HTMLResponse)
async def get_oddsmagnet_top10_redirect():
    """Redirect /oddsmagnet/top10 to /oddsmagnet for backward compatibility"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/oddsmagnet", status_code=301)


@app.get("/llm-analysis", response_class=HTMLResponse)
async def get_llm_analysis_page(response: Response):
    """Serve the modern LLM analysis chat interface"""
    template_path = BASE_DIR / 'html' / 'llm_analysis_v2.html'
    if not template_path.exists():
        return HTMLResponse(content="<h1>LLM Analysis page not found</h1>", status_code=404)
    html_content = open(template_path, 'r', encoding='utf-8').read()
    
    # Add cache-busting headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return HTMLResponse(content=html_content, headers=response.headers)


@app.get("/modern", response_class=HTMLResponse)
async def get_modern_viewer():
    """Serve the modern redesigned odds viewer"""
    template_path = BASE_DIR / 'html' / 'modern_odds_viewer.html'
    if not template_path.exists():
        return HTMLResponse(content="<h1>Modern viewer not found</h1>", status_code=404)
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


# Oddsmagnet WebSocket connections by sport
oddsmagnet_connections: Dict[str, List[WebSocket]] = {
    'football': [],
    'basketball': [],
    'cricket': [],
    'americanfootball': [],
    'baseball': [],
    'tabletennis': [],
    'tennis': [],
    'boxing': [],
    'volleyball': []
}


@app.websocket("/ws/oddsmagnet")
async def oddsmagnet_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time oddsmagnet updates"""
    await websocket.accept()
    current_sport = 'football'  # Default sport
    
    try:
        # Add to connections
        oddsmagnet_connections[current_sport].append(websocket)
        print(f"🟢 WebSocket connected for {current_sport} (total: {len(oddsmagnet_connections[current_sport])})")
        
        # Send initial data based on default sport
        data_file = BASE_DIR / "bookmakers" / "oddsmagnet" / f"oddsmagnet_{current_sport}_top10.json"
        if data_file.exists():
            async with aiofiles.open(data_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                await websocket.send_json({
                    'sport': current_sport,
                    'matches': data.get('matches', []),
                    'timestamp': data.get('timestamp'),
                    'etag': hashlib.md5(content.encode()).hexdigest()
                })
        
        # Listen for messages (sport subscription changes)
        while True:
            message = await websocket.receive_json()
            
            if message.get('action') == 'subscribe':
                new_sport = message.get('sport', 'football')
                
                # Remove from old sport connections
                if websocket in oddsmagnet_connections[current_sport]:
                    oddsmagnet_connections[current_sport].remove(websocket)
                
                # Add to new sport connections
                current_sport = new_sport
                if current_sport not in oddsmagnet_connections:
                    oddsmagnet_connections[current_sport] = []
                oddsmagnet_connections[current_sport].append(websocket)
                
                print(f"🔄 Client switched to {current_sport}")
                
                # Send data for new sport
                data_file = BASE_DIR / "bookmakers" / "oddsmagnet" / f"oddsmagnet_{current_sport}_top10.json"
                if data_file.exists():
                    async with aiofiles.open(data_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
                        await websocket.send_json({
                            'sport': current_sport,
                            'matches': data.get('matches', []),
                            'timestamp': data.get('timestamp'),
                            'etag': hashlib.md5(content.encode()).hexdigest()
                        })
            
    except WebSocketDisconnect:
        if websocket in oddsmagnet_connections[current_sport]:
            oddsmagnet_connections[current_sport].remove(websocket)
        print(f"🔴 WebSocket disconnected from {current_sport}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        if websocket in oddsmagnet_connections.get(current_sport, []):
            oddsmagnet_connections[current_sport].remove(websocket)


# Background task to push updates to WebSocket clients
async def push_oddsmagnet_updates():
    """Monitor oddsmagnet files and push updates to connected clients - OPTIMIZED with reduced polling"""
    last_mtimes = {}
    
    print("🔄 WebSocket monitor started - checking for data updates every 5s (optimized)")
    
    # Map sports to their data files
    sport_files = {
        'football': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_top10.json",
        'basketball': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_basketball.json",
        'cricket': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_cricket.json",
        'americanfootball': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_american_football.json",
        'baseball': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_baseball.json",
        'tabletennis': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_table_tennis.json",
        'tennis': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_tennis.json",
        'boxing': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_boxing.json",
        'volleyball': BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_volleyball.json"
    }
    
    while True:
        try:
            # Check each sport that has active connections
            for sport in ['football', 'basketball', 'cricket', 'americanfootball', 'baseball', 'tabletennis', 'tennis', 'boxing', 'volleyball']:
                if not oddsmagnet_connections[sport]:
                    continue  # Skip sports with no active connections - OPTIMIZATION
                
                data_file = sport_files.get(sport)
                if not data_file or not data_file.exists():
                    continue  # Skip if file doesn't exist
                
                # OPTIMIZATION: Try compressed file first (70% smaller, faster I/O)
                compressed_file = Path(str(data_file) + '.gz')
                use_compressed = compressed_file.exists()
                check_file = compressed_file if use_compressed else data_file
                
                # Get file modification time
                current_mtime = check_file.stat().st_mtime
                cache_key = f"{sport}:{current_mtime}"
                
                # Check if file changed (using mtime for efficiency)
                if last_mtimes.get(sport) != current_mtime:
                    # File changed - read and push update
                    if use_compressed:
                        # Read compressed file (faster I/O)
                        async with aiofiles.open(compressed_file, 'rb') as f:
                            compressed_content = await f.read()
                            content = gzip.decompress(compressed_content).decode('utf-8')
                            data = json.loads(content)
                    else:
                        # Fall back to uncompressed
                        async with aiofiles.open(data_file, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            data = json.loads(content)
                    
                    last_mtimes[sport] = current_mtime
                    
                    # Push to all connected clients for this sport
                    message = {
                        'sport': sport,
                        'matches': data.get('matches', []),
                        'timestamp': data.get('timestamp'),
                        'iteration': data.get('iteration'),
                        'etag': hashlib.md5(content.encode() if isinstance(content, str) else content).hexdigest()
                    }
                    
                    print(f"📡 PUSHING {sport.upper()} UPDATE: {len(data.get('matches', []))} matches to {len(oddsmagnet_connections[sport])} clients")
                    
                    disconnected = []
                    for ws in oddsmagnet_connections[sport]:
                        try:
                            await ws.send_json(message)
                        except Exception as send_err:
                            print(f"⚠️ Failed to send to client: {send_err}")
                            disconnected.append(ws)
                    
                    # Clean up disconnected clients
                    for ws in disconnected:
                        oddsmagnet_connections[sport].remove(ws)
                    
                    if disconnected:
                        print(f"🧹 Cleaned {len(disconnected)} disconnected clients from {sport}")
                    
                    # Invalidate cache for this sport so API serves fresh data immediately
                    if sport in oddsmagnet_cache:
                        oddsmagnet_cache[sport]['data'] = None
                        oddsmagnet_cache[sport]['file_mtime'] = None
                        print(f"🔄 Invalidated cache for {sport}")
            
            # OPTIMIZATION: Reduced from 2s to 5s - less CPU usage, still responsive
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"❌ Error in push_oddsmagnet_updates: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)


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


# ==================== LLM AGENT API ENDPOINTS ====================

@app.get("/api/llm/status")
async def get_llm_status():
    """Get LLM Agent API status"""
    try:
        from core.llm_agent_api import get_llm_agent_api
        llm_api = get_llm_agent_api(BASE_DIR)
        return llm_api.get_status()
    except Exception as e:
        return {
            "analyzer_ready": False,
            "llm_ready": False,
            "error": str(e)
        }


@app.get("/api/llm/data-status")
async def get_llm_data_status():
    """Get data availability status for LLM queries"""
    try:
        from core.llm_agent_api import get_llm_agent_api
        llm_api = get_llm_agent_api(BASE_DIR)
        return llm_api.get_data_status()
    except Exception as e:
        return {
            "data_available": False,
            "error": str(e),
            "unified_count": 0,
            "oddsmagnet_count": 0,
            "total_matches": 0
        }


@app.get("/api/llm/quick-analysis")
async def get_llm_quick_analysis(force: bool = False):
    """Get quick correlation analysis (cached for 5 minutes)"""
    try:
        from core.llm_agent_api import get_llm_agent_api
        llm_api = get_llm_agent_api(BASE_DIR)
        return llm_api.get_quick_analysis(force_refresh=force)
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/llm/full-analysis")
async def get_llm_full_analysis(force: bool = False):
    """Get comprehensive LLM-powered analysis"""
    try:
        from core.llm_agent_api import get_llm_agent_api
        llm_api = get_llm_agent_api(BASE_DIR)
        return llm_api.get_llm_analysis(force_refresh=force)
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/llm/ask")
async def ask_llm_question(request: Request):
    """Ask the LLM a specific question about the data"""
    try:
        from core.llm_agent_api import get_llm_agent_api
        
        llm_api = get_llm_agent_api(BASE_DIR)
        
        body = await request.json()
        question = body.get('question')
        context = body.get('context')
        
        if not question:
            return {
                "success": False,
                "error": "Question is required"
            }
        
        # Get LLM response
        result = llm_api.ask_llm_question(question, context)
        
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ==================== END LLM AGENT API ENDPOINTS ====================


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


@app.get("/oddsmagnet/api/football")
@app.get("/oddsmagnet/football")  # Keep for backward compatibility
async def get_oddsmagnet_football(
    page: int = 1,
    page_size: int = 50,
    league: str = None,
    search: str = None
):
    """Get all OddsMagnet football matches with pagination and filtering
    
    Accessible via:
    - /oddsmagnet/api/football (recommended)
    - /oddsmagnet/football (legacy)
    
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


@app.get("/oddsmagnet/api/football/top10")
@app.get("/oddsmagnet/football/top10")  # Keep for backward compatibility
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
    
    Accessible via:
    - /oddsmagnet/api/football/top10 (recommended)
    - /oddsmagnet/football/top10 (legacy)
    
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
                    'message': 'OddsMagnet collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': []
                }
            )
        
        # Check file modification time for cache invalidation
        current_mtime = data_file.stat().st_mtime
        cache_key = str(data_file)
        
        # Use per-sport cache for real-time updates
        sport_cache = oddsmagnet_cache.get('football', {})
        
        # Use cache if file hasn't changed
        if (sport_cache.get('data') is not None and 
            sport_cache.get('file_mtime') == current_mtime and
            cache_key == sport_cache.get('cache_key')):
            
            data = sport_cache['data']
            print(f"⚡ Using cached football data (mtime: {current_mtime})")
        else:
            # Read data asynchronously for better performance
            try:
                async with aiofiles.open(data_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                
                # Update per-sport cache
                sport_cache['data'] = data
                sport_cache['file_mtime'] = current_mtime
                sport_cache['cache_key'] = cache_key
                sport_cache['timestamp'] = time.time()
                oddsmagnet_cache['football'] = sport_cache
                
                print(f"📁 Loaded fresh football data from {data_file.name} (mtime: {current_mtime})")
                
            except Exception as read_error:
                print(f"❌ Error reading {data_file}: {read_error}")
                return JSONResponse(
                    status_code=500,
                    content={
                        'error': 'Failed to read data file',
                        'message': str(read_error),
                        'matches': []
                    }
                )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        # This ensures ETag changes when data actually changes
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'  # Wrap in quotes per HTTP spec
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            # Return 304 with proper cache control headers
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',  # Require revalidation
                }
            )
        
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
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',  # Force revalidation with server
                'X-Data-Timestamp': data_timestamp,  # For debugging
                'X-Data-Iteration': str(data_iteration),  # For debugging
            }
        )
        
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


@app.get("/oddsmagnet/api/basketball")
@app.get("/oddsmagnet/basketball")  # Keep for backward compatibility
async def get_oddsmagnet_basketball(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet basketball matches with pagination and filtering
    
    This endpoint provides real-time basketball odds from all leagues.
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/basketball (recommended)
    - /oddsmagnet/basketball (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from basketball realtime collector
        basketball_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_basketball.json"
        
        if not basketball_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Basketball data not available',
                    'message': 'Basketball collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_basketball',
                    'sport': 'basketball'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            # Python 3.11+ has asyncio.timeout, for older versions use wait_for
            try:
                # Try Python 3.11+ syntax
                async with asyncio.timeout(5.0):  # 5 second timeout
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                # Fallback for Python < 3.11
                async def read_file():
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            # File read timed out - likely file is being written or is very large
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Basketball data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_basketball',
                    'sport': 'basketball'
                },
                status_code=504
            )
        except json.JSONDecodeError as e:
            # Corrupted JSON - likely file is being written
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Basketball data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_basketball',
                    'sport': 'basketball'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'  # Wrap in quotes per HTTP spec
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            # Return 304 with proper cache control headers
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',  # Require revalidation
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_basketball',
            'sport': 'basketball',
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
            'total_leagues': data.get('total_leagues', 0),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',  # Force revalidation with server
                'X-Data-Timestamp': data_timestamp,  # For debugging
                'X-Data-Iteration': str(data_iteration),  # For debugging
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


# Basketball NBA and NCAA endpoints (consolidated to avoid duplicates)
@app.get("/oddsmagnet/api/basketball/nba")
@app.get("/oddsmagnet/basketball/nba")  # Keep for backward compatibility
async def get_oddsmagnet_basketball_nba(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    search: str = None
):
    """Get NBA basketball matches only
    
    Filters basketball data to show only NBA matches.
    Supports ETag caching for faster subsequent loads.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from basketball realtime collector
        basketball_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_basketball.json"
        
        if not basketball_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Basketball data not available',
                    'message': 'Basketball collector not running',
                    'matches': [],
                    'timestamp': datetime.now().isoformat()
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={'error': 'Request timeout', 'message': 'Basketball data is being updated.', 'matches': []},
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={'error': 'Data temporarily unavailable', 'message': 'Basketball data is being updated.', 'matches': []},
                status_code=503
            )
        
        # Generate ETag
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-nba-{page}-{page_size}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check cache
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={'ETag': etag, 'Cache-Control': 'no-cache'}
            )
        
        # Filter for NBA only
        all_matches = data.get('matches', [])
        nba_matches = [
            m for m in all_matches 
            if m.get('league_slug', '') == 'usa-nba'
        ]
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            nba_matches = [
                m for m in nba_matches 
                if search_lower in m.get('match_name', '').lower()
            ]
        
        # Pagination
        total_matches = len(nba_matches)
        total_pages = (total_matches + page_size - 1) // page_size if total_matches > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = nba_matches[start_idx:end_idx]
        
        response_data = {
            'source': 'oddsmagnet_basketball',
            'sport': 'basketball',
            'league': 'NBA',
            'timestamp': data_timestamp,
            'iteration': data_iteration,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_matches,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'total_matches': total_matches,
            'matches': paginated_matches
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(content={'error': str(e), 'matches': []})


@app.get("/oddsmagnet/api/basketball/ncaa")
@app.get("/oddsmagnet/basketball/ncaa")  # Keep for backward compatibility
async def get_oddsmagnet_basketball_ncaa(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    search: str = None
):
    """Get NCAA basketball matches only
    
    Filters basketball data to show only NCAA matches.
    Supports ETag caching for faster subsequent loads.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from basketball realtime collector
        basketball_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_basketball.json"
        
        if not basketball_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Basketball data not available',
                    'message': 'Basketball collector not running',
                    'matches': [],
                    'timestamp': datetime.now().isoformat()
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={'error': 'Request timeout', 'message': 'Basketball data is being updated.', 'matches': []},
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={'error': 'Data temporarily unavailable', 'message': 'Basketball data is being updated.', 'matches': []},
                status_code=503
            )
        
        # Generate ETag
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-ncaa-{page}-{page_size}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check cache
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={'ETag': etag, 'Cache-Control': 'no-cache'}
            )
        
        # Filter for NCAA only
        all_matches = data.get('matches', [])
        ncaa_matches = [
            m for m in all_matches 
            if m.get('league_slug', '') == 'usa-ncaa'
        ]
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            ncaa_matches = [
                m for m in ncaa_matches 
                if search_lower in m.get('match_name', '').lower()
            ]
        
        # Pagination
        total_matches = len(ncaa_matches)
        total_pages = (total_matches + page_size - 1) // page_size if total_matches > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = ncaa_matches[start_idx:end_idx]
        
        response_data = {
            'source': 'oddsmagnet_basketball',
            'sport': 'basketball',
            'league': 'NCAA',
            'timestamp': data_timestamp,
            'iteration': data_iteration,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_matches,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'total_matches': total_matches,
            'matches': paginated_matches
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(content={'error': str(e), 'matches': []})


@app.get("/oddsmagnet/api/nba-ncaa")
@app.get("/oddsmagnet/nba-ncaa")  # Keep for backward compatibility
async def get_oddsmagnet_nba_ncaa(
    request: Request,
    page: int = 1,
    page_size: int = 999
):
    """Get OddsMagnet NBA and NCAA basketball matches with pagination
    
    This endpoint provides real-time basketball odds from NBA and NCAA only.
    Optimized for UI display with ETag caching.
    
    Accessible via:
    - /oddsmagnet/api/nba-ncaa (recommended)
    - /oddsmagnet/nba-ncaa (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from NBA/NCAA realtime collector
        nba_ncaa_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_nba_ncaa.json"
        
        if not nba_ncaa_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet NBA/NCAA data not available',
                    'message': 'NBA/NCAA collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': []
                }
            )
        
        # Read data first to generate content-based ETag
        with open(nba_ncaa_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
        all_matches = data.get('matches', [])
        
        # Calculate pagination
        total_matches = len(all_matches)
        total_pages = (total_matches + page_size - 1) // page_size if total_matches > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = all_matches[start_idx:end_idx]
        
        response_data = {
            'source': 'oddsmagnet_nba_ncaa',
            'sport': 'basketball',
            'scope': 'nba_ncaa_only',
            'timestamp': data.get('timestamp'),
            'iteration': data.get('iteration'),
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_matches,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'total_matches': total_matches,
            'leagues_tracked': data.get('leagues_tracked', []),
            'total_leagues': data.get('total_leagues', 0),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


# American Football endpoints
@app.get("/oddsmagnet/api/americanfootball")
@app.get("/oddsmagnet/americanfootball")  # Keep for backward compatibility
async def get_oddsmagnet_americanfootball(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet American Football matches with pagination and filtering
    
    This endpoint provides real-time American Football odds from all leagues (NFL, NCAA).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/americanfootball (recommended)
    - /oddsmagnet/americanfootball (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from American Football realtime collector
        af_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_american_football.json"
        
        if not af_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet American Football data not available',
                    'message': 'American Football collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_americanfootball',
                    'sport': 'american-football'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(af_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(af_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'American Football data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_americanfootball',
                    'sport': 'american-football'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'American Football data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_americanfootball',
                    'sport': 'american-football'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_americanfootball',
            'sport': 'american-football',
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
            'total_leagues': data.get('total_leagues', 0),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/cricket")
@app.get("/oddsmagnet/cricket")  # Keep for backward compatibility
async def get_oddsmagnet_cricket(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Cricket matches with pagination and filtering
    
    This endpoint provides real-time Cricket odds from all leagues (IPL, Ashes, T20, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/cricket (recommended)
    - /oddsmagnet/cricket (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Cricket realtime collector
        cricket_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_cricket.json"
        
        if not cricket_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Cricket data not available',
                    'message': 'Cricket collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_cricket',
                    'sport': 'cricket'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(cricket_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(cricket_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Cricket data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_cricket',
                    'sport': 'cricket'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Cricket data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_cricket',
                    'sport': 'cricket'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_cricket',
            'sport': 'cricket',
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
            'total_leagues': data.get('total_leagues', 0),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/baseball")
@app.get("/oddsmagnet/baseball")  # Keep for backward compatibility
async def get_oddsmagnet_baseball(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Baseball matches with pagination and filtering
    
    This endpoint provides real-time Baseball odds from all leagues (MLB, NPB, KBO, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/baseball (recommended)
    - /oddsmagnet/baseball (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Baseball realtime collector
        baseball_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_baseball.json"
        
        if not baseball_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Baseball data not available',
                    'message': 'Baseball collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_baseball',
                    'sport': 'baseball'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(baseball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(baseball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Baseball data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_baseball',
                    'sport': 'baseball'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Baseball data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_baseball',
                    'sport': 'baseball'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_baseball',
            'sport': 'baseball',
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
            'league_breakdown': data.get('league_breakdown', {}),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/tabletennis")
@app.get("/oddsmagnet/tabletennis")  # Keep for backward compatibility
async def get_oddsmagnet_tabletennis(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Table Tennis matches with pagination and filtering
    
    This endpoint provides real-time Table Tennis odds from all leagues (Setka Cup, Czech Pro League, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/tabletennis (recommended)
    - /oddsmagnet/tabletennis (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Table Tennis realtime collector
        tabletennis_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_table_tennis.json"
        
        if not tabletennis_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Table Tennis data not available',
                    'message': 'Table Tennis collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tabletennis',
                    'sport': 'table-tennis'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(tabletennis_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(tabletennis_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Table Tennis data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tabletennis',
                    'sport': 'table-tennis'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Table Tennis data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tabletennis',
                    'sport': 'table-tennis'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_tabletennis',
            'sport': 'table-tennis',
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
            'league_breakdown': data.get('league_breakdown', {}),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/tennis")
@app.get("/oddsmagnet/tennis")  # Keep for backward compatibility
async def get_oddsmagnet_tennis(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Tennis matches with pagination and filtering
    
    This endpoint provides real-time Tennis odds from all tournaments (Grand Slams, ATP, WTA, ITF, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/tennis (recommended)
    - /oddsmagnet/tennis (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific tournament (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Tennis realtime collector
        tennis_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_tennis.json"
        
        if not tennis_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Tennis data not available',
                    'message': 'Tennis collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tennis',
                    'sport': 'tennis'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(tennis_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(tennis_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Tennis data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tennis',
                    'sport': 'tennis'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Tennis data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_tennis',
                    'sport': 'tennis'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_tennis',
            'sport': 'tennis',
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
            'tournament_breakdown': data.get('tournament_breakdown', {}),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/boxing")
@app.get("/oddsmagnet/boxing")  # Keep for backward compatibility
async def get_oddsmagnet_boxing(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Boxing matches with pagination and filtering
    
    This endpoint provides real-time Boxing odds from all events (Boxing, MMA, UFC, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/boxing (recommended)
    - /oddsmagnet/boxing (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific event (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Boxing realtime collector
        boxing_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_boxing.json"
        
        if not boxing_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Boxing data not available',
                    'message': 'Boxing collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_boxing',
                    'sport': 'boxing'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(boxing_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(boxing_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Boxing data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_boxing',
                    'sport': 'boxing'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Boxing data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_boxing',
                    'sport': 'boxing'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_boxing',
            'sport': 'boxing',
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
            'event_breakdown': data.get('event_breakdown', {}),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
            }
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                'error': str(e),
                'matches': []
            }
        )


@app.get("/oddsmagnet/api/volleyball")
@app.get("/oddsmagnet/volleyball")  # Keep for backward compatibility
async def get_oddsmagnet_volleyball(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    league: str = None,
    search: str = None
):
    """Get OddsMagnet Volleyball matches with pagination and filtering
    
    This endpoint provides real-time Volleyball odds from all leagues (Spain, Poland, Russia, Brazil, etc.).
    Supports ETag caching for faster subsequent loads.
    
    Accessible via:
    - /oddsmagnet/api/volleyball (recommended)
    - /oddsmagnet/volleyball (legacy)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - league: Filter by specific league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read from Volleyball realtime collector
        volleyball_file = BASE_DIR / "bookmakers" / "oddsmagnet" / "oddsmagnet_volleyball.json"
        
        if not volleyball_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddsMagnet Volleyball data not available',
                    'message': 'Volleyball collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_realtime_parallel.py --mode local',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_volleyball',
                    'sport': 'volleyball'
                },
                status_code=503
            )
        
        # Read data with timeout (5 seconds max)
        try:
            try:
                async with asyncio.timeout(5.0):
                    async with aiofiles.open(volleyball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
            except AttributeError:
                async def read_file():
                    async with aiofiles.open(volleyball_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        return json.loads(content)
                data = await asyncio.wait_for(read_file(), timeout=5.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                content={
                    'error': 'Request timeout',
                    'message': 'Volleyball data file is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_volleyball',
                    'sport': 'volleyball'
                },
                status_code=504
            )
        except json.JSONDecodeError:
            return JSONResponse(
                content={
                    'error': 'Data temporarily unavailable',
                    'message': 'Volleyball data is being updated. Please try again in a moment.',
                    'matches': [],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'oddsmagnet_volleyball',
                    'sport': 'volleyball'
                },
                status_code=503
            )
        
        # Generate ETag from actual data content (timestamp + iteration + query params)
        data_timestamp = data.get('timestamp', '')
        data_iteration = data.get('iteration', 0)
        etag_base = f"{data_timestamp}-{data_iteration}-{page}-{page_size}-{league}-{search}"
        etag = f'"{hashlib.md5(etag_base.encode()).hexdigest()}"'
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    'ETag': etag,
                    'Cache-Control': 'no-cache',
                }
            )
        
        # Data is from real-time collector
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
            'source': 'oddsmagnet_volleyball',
            'sport': 'volleyball',
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
            'league_breakdown': data.get('league_breakdown', {}),
            'matches': paginated_matches
        }
        
        # Return with proper cache control headers and ETag
        return JSONResponse(
            content=response_data,
            headers={
                'ETag': etag,
                'Cache-Control': 'no-cache',
                'X-Data-Timestamp': data_timestamp,
                'X-Data-Iteration': str(data_iteration),
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


# ==================== OddPortal API Endpoint ====================

@app.get("/oddsmagnet/api/oddportal")
@app.get("/oddportal/api/matches")
async def get_oddportal_data(
    request: Request,
    page: int = 1,
    page_size: int = 999,
    sport: str = None,
    league: str = None,
    search: str = None
):
    """Get OddPortal odds data with pagination and filtering
    
    Accessible via:
    - /oddsmagnet/api/oddportal (displays in oddsmagnet viewer)
    - /oddportal/api/matches (standalone access)
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 999 [all], max: 999)
    - sport: Filter by sport (e.g., 'basketball', 'football')
    - league: Filter by league (partial match)
    - search: Search in match name (partial match, case-insensitive)
    """
    try:
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), 999)
        
        # Read OddPortal unified data
        oddportal_file = BASE_DIR / "bookmakers" / "oddportal" / "oddportal_unified.json"
        
        if not oddportal_file.exists():
            return JSONResponse(
                content={
                    'error': 'OddPortal data not available',
                    'message': 'OddPortal collector not running. Start with: python bookmakers/oddportal/oddportal_collector.py --continuous',
                    'matches': [],
                    'sport': sport or 'all',
                    'timestamp': datetime.now().isoformat(),
                    'matches_count': 0,
                    'total_pages': 0,
                    'current_page': page
                }
            )
        
        # Check ETag for caching
        file_stat = oddportal_file.stat()
        file_mtime = file_stat.st_mtime
        file_size = file_stat.st_size
        etag_base = f"{file_mtime}-{file_size}"
        etag = hashlib.md5(etag_base.encode()).hexdigest()
        
        # Check if client has cached version
        if_none_match = request.headers.get('if-none-match')
        if if_none_match == etag:
            return Response(status_code=304)
        
        # Load data
        try:
            async with aiofiles.open(oddportal_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"❌ JSON decode error in OddPortal file: {je}")
            return JSONResponse(
                status_code=500,
                content={
                    'error': 'Invalid JSON in OddPortal data file',
                    'message': f'JSON parse error: {str(je)}',
                    'matches': []
                }
            )
        except Exception as file_error:
            print(f"❌ Error reading OddPortal file: {file_error}")
            return JSONResponse(
                status_code=500,
                content={
                    'error': 'Failed to read OddPortal data file',
                    'message': str(file_error),
                    'matches': []
                }
            )
        
        matches = data.get('matches', [])
        
        # Apply filters
        filtered_matches = matches
        
        # Filter by sport if specified
        if sport:
            sport_lower = sport.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if m.get('sport', '').lower() == sport_lower
            ]
        
        # Filter by league if specified
        if league:
            league_lower = league.lower()
            filtered_matches = [
                m for m in filtered_matches 
                if league_lower in m.get('league', '').lower()
            ]
        
        # Search filter
        if search:
            search_lower = search.lower()
            filtered_matches = [
                m for m in filtered_matches
                if search_lower in m.get('name', '').lower() or
                   search_lower in m.get('home_team', '').lower() or
                   search_lower in m.get('away_team', '').lower()
            ]
        
        # Calculate pagination
        total_matches = len(filtered_matches)
        total_pages = (total_matches + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = filtered_matches[start_idx:end_idx]
        
        response_data = {
            'sport': data.get('sport', 'multi'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'source': 'oddportal',
            'matches_count': len(paginated_matches),
            'total_matches': total_matches,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size,
            'matches': paginated_matches
        }
        
        return JSONResponse(
            content=response_data,
            headers={'ETag': etag, 'Cache-Control': 'public, max-age=30'}
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Error loading OddPortal data: {e}")
        print(f"Stack trace:\n{error_details}")
        return JSONResponse(
            status_code=500,
            content={
                'error': 'Failed to load OddPortal data',
                'message': str(e),
                'details': error_details if app.debug else None,
                'matches': []
            }
        )


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
