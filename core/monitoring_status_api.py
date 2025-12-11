"""
Monitoring Status API - Shared interface for monitoring data
Allows web UI to read real-time monitoring status
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import threading


class MonitoringStatusAPI:
    """Provides thread-safe access to monitoring status for UI"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        # base_dir should be project root, not core/
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.status_file = self.base_dir / "data" / "monitoring_status.json"
        self.lock = threading.Lock()
    
    def update_status(self, status_data: Dict) -> bool:
        """Update monitoring status (called by monitoring_system.py)"""
        with self.lock:
            try:
                status_data['last_updated'] = datetime.now().isoformat()
                with open(self.status_file, 'w', encoding='utf-8') as f:
                    json.dump(status_data, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                print(f"❌ Error writing monitoring status: {e}")
                return False
    
    def get_status(self) -> Dict:
        """Get current monitoring status (called by web UI)"""
        with self.lock:
            try:
                if self.status_file.exists():
                    with open(self.status_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    return {
                        'monitoring_active': False,
                        'message': 'Monitoring system not started',
                        'last_updated': None
                    }
            except Exception as e:
                return {
                    'monitoring_active': False,
                    'error': str(e),
                    'last_updated': None
                }
    
    def get_module_status(self, module_name: str) -> Optional[Dict]:
        """Get status for a specific module"""
        status = self.get_status()
        modules = status.get('modules', {})
        return modules.get(module_name)
    
    def is_monitoring_active(self) -> bool:
        """Check if monitoring system is running"""
        status = self.get_status()
        
        # Check if status was updated recently (within last 10 minutes)
        last_updated = status.get('last_updated')
        if last_updated:
            try:
                last_update_time = datetime.fromisoformat(last_updated)
                time_diff = (datetime.now() - last_update_time).total_seconds()
                return time_diff < 600  # 10 minutes
            except:
                return False
        
        return status.get('monitoring_active', False)


# Convenience functions for direct use
def get_monitoring_status() -> Dict:
    """Get current monitoring status"""
    api = MonitoringStatusAPI()
    return api.get_status()

def is_monitoring_running() -> bool:
    """Check if monitoring is active"""
    api = MonitoringStatusAPI()
    return api.is_monitoring_active()

def update_monitoring_status(status_data: Dict) -> bool:
    """Update monitoring status"""
    api = MonitoringStatusAPI()
    return api.update_status(status_data)
