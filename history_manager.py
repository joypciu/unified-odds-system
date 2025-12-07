"""
History Manager for Unified Odds System
Manages completed/finished matches across all bookmakers (1xBet, FanDuel, Bet365)
Moves old matches to history.json to keep live data clean
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set
import logging

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages match history across all bookmakers"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.history_file = self.base_dir / "history.json"
        
        # Individual bookmaker files
        self.xbet_pregame = self.base_dir / "1xbet" / "1xbet_pregame.json"
        self.xbet_live = self.base_dir / "1xbet" / "1xbet_live.json"
        self.fanduel_pregame = self.base_dir / "fanduel" / "fanduel_pregame.json"
        self.fanduel_live = self.base_dir / "fanduel" / "fanduel_live.json"
        self.bet365_pregame = self.base_dir / "bet365" / "bet365_current_pregame.json"
        self.bet365_live = self.base_dir / "bet365" / "bet365_live_current.json"
        
        # Time thresholds
        self.pregame_stale_hours = 24  # Move pregame matches older than 24 hours
        self.live_stale_minutes = 30   # Move live matches not updated in 30 minutes
        
        # Track match IDs we've seen
        self.seen_match_ids: Set[str] = set()
        
    def load_history(self) -> Dict:
        """Load existing history"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        return {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'total_matches': 0,
                'last_updated': datetime.now().isoformat()
            },
            'matches': {
                '1xbet': {'pregame': [], 'live': []},
                'fanduel': {'pregame': [], 'live': []},
                'bet365': {'pregame': [], 'live': []}
            }
        }
    
    def save_history(self, history_data: Dict):
        """Save history to file"""
        history_data['metadata']['last_updated'] = datetime.now().isoformat()
        history_data['metadata']['total_matches'] = sum(
            len(history_data['matches'][bookie]['pregame']) + 
            len(history_data['matches'][bookie]['live'])
            for bookie in ['1xbet', 'fanduel', 'bet365']
        )
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved history: {history_data['metadata']['total_matches']} total matches")
    
    def is_match_old_pregame(self, match: Dict) -> bool:
        """Check if pregame match is old (past start time)"""
        try:
            start_time_str = match.get('start_time') or match.get('start_date') or match.get('date')
            if not start_time_str:
                return False
            
            # Parse various time formats
            try:
                if 'T' in start_time_str:
                    if start_time_str.endswith('Z'):
                        start_time = datetime.fromisoformat(start_time_str[:-1])
                    else:
                        start_time = datetime.fromisoformat(start_time_str)
                else:
                    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
            except:
                return False
            
            # Match is old if start time has passed
            now = datetime.now()
            return now > start_time
            
        except Exception as e:
            logger.debug(f"Error checking match age: {e}")
            return False
    
    def is_match_completed_live(self, match: Dict) -> bool:
        """Check if live match is completed or stale"""
        # Check explicit status
        status = match.get('status', '').lower()
        if status in ['completed', 'finished', 'ended', 'final']:
            return True
        
        # Check if match hasn't been updated recently (stale)
        last_updated = match.get('last_updated') or match.get('updated_at') or match.get('timestamp')
        if last_updated:
            try:
                if isinstance(last_updated, (int, float)):
                    # Unix timestamp
                    last_update_time = datetime.fromtimestamp(last_updated)
                else:
                    # ISO string
                    last_update_time = datetime.fromisoformat(str(last_updated).replace('Z', ''))
                
                # Match is stale if not updated in last 30 minutes
                minutes_since_update = (datetime.now() - last_update_time).total_seconds() / 60
                return minutes_since_update > self.live_stale_minutes
                
            except:
                pass
        
        return False
    
    def clean_1xbet_pregame(self) -> int:
        """Clean 1xBet pregame data, move old matches to history"""
        if not self.xbet_pregame.exists():
            return 0
        
        try:
            with open(self.xbet_pregame, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            matches = data.get('matches', [])
            active_matches = []
            old_matches = []
            
            for match in matches:
                if self.is_match_old_pregame(match):
                    match['moved_to_history_at'] = datetime.now().isoformat()
                    match['reason'] = 'past_start_time'
                    old_matches.append(match)
                else:
                    active_matches.append(match)
            
            if old_matches:
                # Update file with only active matches
                data['matches'] = active_matches
                data['metadata'] = data.get('metadata', {})
                data['metadata']['last_cleaned'] = datetime.now().isoformat()
                data['metadata']['total_matches'] = len(active_matches)
                
                with open(self.xbet_pregame, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Add to history
                history = self.load_history()
                history['matches']['1xbet']['pregame'].extend(old_matches)
                self.save_history(history)
                
                logger.info(f"✓ 1xBet pregame: Moved {len(old_matches)} old matches to history")
            
            return len(old_matches)
            
        except Exception as e:
            logger.error(f"Error cleaning 1xBet pregame: {e}")
            return 0
    
    def clean_1xbet_live(self) -> int:
        """Clean 1xBet live data, move completed matches to history"""
        if not self.xbet_live.exists():
            return 0
        
        try:
            with open(self.xbet_live, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            matches = data.get('matches', [])
            active_matches = []
            completed_matches = []
            
            for match in matches:
                if self.is_match_completed_live(match):
                    match['moved_to_history_at'] = datetime.now().isoformat()
                    match['reason'] = 'completed_or_stale'
                    completed_matches.append(match)
                else:
                    active_matches.append(match)
            
            if completed_matches:
                # Update file with only active matches
                data['matches'] = active_matches
                data['metadata'] = data.get('metadata', {})
                data['metadata']['last_cleaned'] = datetime.now().isoformat()
                data['metadata']['total_matches'] = len(active_matches)
                
                with open(self.xbet_live, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Add to history
                history = self.load_history()
                history['matches']['1xbet']['live'].extend(completed_matches)
                self.save_history(history)
                
                logger.info(f"✓ 1xBet live: Moved {len(completed_matches)} completed matches to history")
            
            return len(completed_matches)
            
        except Exception as e:
            logger.error(f"Error cleaning 1xBet live: {e}")
            return 0
    
    def clean_fanduel_pregame(self) -> int:
        """Clean FanDuel pregame data"""
        if not self.fanduel_pregame.exists():
            return 0
        
        try:
            with open(self.fanduel_pregame, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            matches = data.get('data', {}).get('matches', [])
            active_matches = []
            old_matches = []
            
            for match in matches:
                if self.is_match_old_pregame(match):
                    match['moved_to_history_at'] = datetime.now().isoformat()
                    match['reason'] = 'past_start_time'
                    old_matches.append(match)
                else:
                    active_matches.append(match)
            
            if old_matches:
                # Update file
                data['data']['matches'] = active_matches
                data['metadata'] = data.get('metadata', {})
                data['metadata']['last_cleaned'] = datetime.now().isoformat()
                data['metadata']['total_matches'] = len(active_matches)
                
                with open(self.fanduel_pregame, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Add to history
                history = self.load_history()
                history['matches']['fanduel']['pregame'].extend(old_matches)
                self.save_history(history)
                
                logger.info(f"✓ FanDuel pregame: Moved {len(old_matches)} old matches to history")
            
            return len(old_matches)
            
        except Exception as e:
            logger.error(f"Error cleaning FanDuel pregame: {e}")
            return 0
    
    def clean_fanduel_live(self) -> int:
        """Clean FanDuel live data"""
        if not self.fanduel_live.exists():
            return 0
        
        try:
            with open(self.fanduel_live, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            matches = data.get('data', {}).get('matches', [])
            active_matches = []
            completed_matches = []
            
            for match in matches:
                if self.is_match_completed_live(match):
                    match['moved_to_history_at'] = datetime.now().isoformat()
                    match['reason'] = 'completed_or_stale'
                    completed_matches.append(match)
                else:
                    active_matches.append(match)
            
            if completed_matches:
                # Update file
                data['data']['matches'] = active_matches
                data['metadata'] = data.get('metadata', {})
                data['metadata']['last_cleaned'] = datetime.now().isoformat()
                data['metadata']['total_matches'] = len(active_matches)
                
                with open(self.fanduel_live, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Add to history
                history = self.load_history()
                history['matches']['fanduel']['live'].extend(completed_matches)
                self.save_history(history)
                
                logger.info(f"✓ FanDuel live: Moved {len(completed_matches)} completed matches to history")
            
            return len(completed_matches)
            
        except Exception as e:
            logger.error(f"Error cleaning FanDuel live: {e}")
            return 0
    
    def clean_all(self) -> Dict[str, int]:
        """Clean all bookmaker data files"""
        logger.info("="*70)
        logger.info("CLEANING OLD/COMPLETED MATCHES")
        logger.info("="*70)
        
        results = {
            '1xbet_pregame': self.clean_1xbet_pregame(),
            '1xbet_live': self.clean_1xbet_live(),
            'fanduel_pregame': self.clean_fanduel_pregame(),
            'fanduel_live': self.clean_fanduel_live()
        }
        
        total_moved = sum(results.values())
        
        logger.info("="*70)
        logger.info(f"TOTAL MATCHES MOVED TO HISTORY: {total_moved}")
        logger.info("="*70)
        
        return results


if __name__ == "__main__":
    # Test the history manager
    logging.basicConfig(level=logging.INFO)
    
    manager = HistoryManager()
    results = manager.clean_all()
    
    print("\nResults:")
    for source, count in results.items():
        print(f"  {source}: {count} matches moved")
