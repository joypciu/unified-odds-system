#!/usr/bin/env python3
"""
Automated Odds Monitoring System
- Monitors all scraper modules for failures
- Auto-updates cache when new teams/sports discovered
- Sends email alerts for issues
- Provides status API for web UI
"""

import json
import os
import sys
import smtplib
import time
import signal
import threading
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

from dynamic_cache_manager import DynamicCacheManager
from monitoring_status_api import update_monitoring_status
from secure_config import SecureConfig


class ConfigManager:
    """Manages configuration with fallback to environment variables"""
    
    def __init__(self, config_file: Path = None):
        self.config_file = config_file or Path("config.json")
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load config from encrypted file or environment variables"""
        # Try loading from encrypted file
        if self.config_file.exists():
            try:
                secure_config = SecureConfig(str(self.config_file))
                config = secure_config.load_config()
                print(f"✓ Loaded encrypted config from {self.config_file}")
                return config
            except Exception as e:
                print(f"⚠ Error loading config file: {e}")
        
        # Fallback to environment variables
        print("⚠ Using environment variables for config")
        return {
            'email': {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'sender_email': os.getenv('SENDER_EMAIL', ''),
                'sender_password': os.getenv('SENDER_PASSWORD', ''),
                'admin_email': os.getenv('ADMIN_EMAIL', ''),
                'alert_cooldown_minutes': int(os.getenv('ALERT_COOLDOWN', '720')),
                'enabled': os.getenv('EMAIL_ENABLED', 'true').lower() == 'true'
            },
            'monitoring': {
                'check_interval_seconds': int(os.getenv('CHECK_INTERVAL', '300')),
                'data_stale_threshold_minutes': int(os.getenv('STALE_THRESHOLD', '60')),
                'failure_threshold': int(os.getenv('FAILURE_THRESHOLD', '3')),
                'modules': [
                    'bet365_pregame', 'bet365_live',
                    'fanduel_pregame', 'fanduel_live',
                    '1xbet_pregame', '1xbet_live'
                ]
            },
            'cache': {
                'auto_update': os.getenv('CACHE_AUTO_UPDATE', 'true').lower() == 'true',
                'update_interval_minutes': int(os.getenv('CACHE_UPDATE_INTERVAL', '30'))
            }
        }
    
    def get(self, key: str, default=None):
        """Get config value by dot notation (e.g., 'email.smtp_server')"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default


class EmailNotifier:
    """Sends email notifications for system alerts"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.last_alert_times = {}  # Track cooldown per alert type
        self.enabled = config.get('email.enabled', True)
        
        if not self.enabled:
            print("⚠ Email notifications are DISABLED in config")
        elif not config.get('email.sender_email') or not config.get('email.admin_email'):
            print("⚠ Email not configured properly, notifications DISABLED")
            self.enabled = False
    
    def send_alert(self, subject: str, body: str, alert_type: str = "general") -> bool:
        """Send email alert with cooldown"""
        if not self.enabled:
            print(f"📧 [DISABLED] {subject}")
            return False
        
        # Check cooldown
        cooldown_minutes = self.config.get('email.alert_cooldown_minutes', 30)
        now = datetime.now()
        
        if alert_type in self.last_alert_times:
            time_since_last = (now - self.last_alert_times[alert_type]).total_seconds() / 60
            if time_since_last < cooldown_minutes:
                print(f"⏸ Alert on cooldown ({alert_type}): {cooldown_minutes - time_since_last:.1f} min remaining")
                return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.get('email.sender_email')
            msg['To'] = self.config.get('email.admin_email')
            msg['Subject'] = f"🚨 Odds System Alert: {subject}"
            
            # Add timestamp
            body_with_time = f"""
{'='*80}
ODDS MONITORING SYSTEM ALERT
{'='*80}
Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
Alert Type: {alert_type}

{body}

{'='*80}
This is an automated message from the Odds Monitoring System.
To stop receiving alerts, set "enabled": false in config.json
{'='*80}
"""
            msg.attach(MIMEText(body_with_time, 'plain'))
            
            # Send email
            server = smtplib.SMTP(
                self.config.get('email.smtp_server'),
                self.config.get('email.smtp_port')
            )
            server.starttls()
            server.login(
                self.config.get('email.sender_email'),
                self.config.get('email.sender_password')
            )
            server.send_message(msg)
            server.quit()
            
            # Update cooldown
            self.last_alert_times[alert_type] = now
            
            print(f"✅ Alert sent: {subject}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False


class ModuleMonitor:
    """Monitors individual scraper modules"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.module_files = {
            'bet365_pregame': base_dir / 'bet365' / 'bet365_current_pregame.json',
            'bet365_live': base_dir / 'bet365' / 'bet365_live_current.json',
            'fanduel_pregame': base_dir / 'fanduel' / 'fanduel_pregame.json',
            'fanduel_live': base_dir / 'fanduel' / 'fanduel_live.json',
            '1xbet_pregame': base_dir / '1xbet' / '1xbet_pregame.json',
            '1xbet_live': base_dir / '1xbet' / '1xbet_live.json'
        }
        self.failure_counts = {module: 0 for module in self.module_files}
        self.last_check_times = {}
    
    def check_module(self, module_name: str, stale_threshold_minutes: int = 60) -> Dict:
        """Check if a module is working properly"""
        result = {
            'module': module_name,
            'status': 'ok',
            'issues': [],
            'warnings': [],
            'data': {}
        }
        
        file_path = self.module_files.get(module_name)
        if not file_path:
            result['status'] = 'error'
            result['issues'].append(f"Unknown module: {module_name}")
            return result
        
        # Check if file exists
        if not file_path.exists():
            result['status'] = 'error'
            result['issues'].append(f"Data file not found: {file_path}")
            self.failure_counts[module_name] += 1
            return result
        
        try:
            # Check file age
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_minutes = (datetime.now() - file_mtime).total_seconds() / 60
            result['data']['file_age_minutes'] = age_minutes
            result['data']['last_updated'] = file_mtime.isoformat()
            
            if age_minutes > stale_threshold_minutes:
                result['status'] = 'warning'
                result['warnings'].append(
                    f"Data is stale ({age_minutes:.1f} minutes old, threshold: {stale_threshold_minutes})"
                )
            
            # Check file content
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Count matches
            matches = []
            if 'matches' in data:
                matches = data['matches']
            elif 'data' in data and isinstance(data['data'], dict) and 'matches' in data['data']:
                matches = data['data']['matches']
            elif 'sports_data' in data:
                for sport_info in data['sports_data'].values():
                    matches.extend(sport_info.get('games', []))
            
            result['data']['match_count'] = len(matches)
            result['data']['file_size_bytes'] = file_path.stat().st_size
            
            if len(matches) == 0:
                result['status'] = 'warning'
                result['warnings'].append("No matches found in data file")
            
            # Reset failure count on success
            if result['status'] == 'ok':
                self.failure_counts[module_name] = 0
            
        except json.JSONDecodeError as e:
            result['status'] = 'error'
            result['issues'].append(f"Invalid JSON: {e}")
            self.failure_counts[module_name] += 1
        except Exception as e:
            result['status'] = 'error'
            result['issues'].append(f"Error reading file: {e}")
            self.failure_counts[module_name] += 1
        
        return result
    
    def check_all_modules(self, stale_threshold: int) -> Dict:
        """Check all monitored modules"""
        results = {}
        for module_name in self.module_files:
            results[module_name] = self.check_module(module_name, stale_threshold)
        return results


class OddsMonitoringSystem:
    """Main monitoring system with auto-cache updates and email alerts"""
    
    def __init__(self, config_file: Path = None):
        self.base_dir = Path(__file__).parent
        self.config = ConfigManager(config_file or self.base_dir / "config.json")
        self.email = EmailNotifier(self.config)
        self.monitor = ModuleMonitor(self.base_dir)
        self.cache_manager = None
        self.unified_corruption_count = 0  # Track unified_odds.json corruption
        
        # Initialize cache manager if auto-update is enabled
        if self.config.get('cache.auto_update', True):
            self.cache_manager = DynamicCacheManager(self.base_dir)
            print("✓ Dynamic cache auto-update ENABLED")
        
        self.running = False
        self.monitor_thread = None
        self.cache_update_thread = None
    
    def check_unified_file_health(self):
        """Check if unified_odds.json is valid and not corrupted"""
        unified_file = self.base_dir / "unified_odds.json"
        
        if not unified_file.exists():
            return  # File doesn't exist yet, not an error
        
        try:
            with open(unified_file, 'r', encoding='utf-8') as f:
                json.load(f)
            
            # Reset corruption count if file is valid
            if self.unified_corruption_count > 0:
                print("✓ unified_odds.json recovered")
                self.unified_corruption_count = 0
                
        except json.JSONDecodeError as e:
            self.unified_corruption_count += 1
            print(f"⚠ unified_odds.json is corrupted: {e}")
            
            # Send alert on first corruption or every 5 times
            if self.unified_corruption_count == 1 or self.unified_corruption_count % 5 == 0:
                alert_body = f"""
[WARNING] Unified Odds File Corruption Detected

File: unified_odds.json
Corruption Count: {self.unified_corruption_count}
Error: {str(e)[:200]}

IMPACT:
  • Web UI falling back to individual source files
  • May cause slower data loading
  • Data consistency may be affected

CAUSE:
  • Multiple processes writing simultaneously
  • Write interrupted (crash/kill)
  • Disk I/O issues

AUTOMATIC RECOVERY:
  • System has atomic write protection
  • Backup file (.bak) available if needed
  • Will auto-recover on next successful merge

ACTION:
  • Check if multiple unifi collectors are running
  • Ensure disk has sufficient space
  • Review system logs for crashes
  • File will auto-recover on next merge
"""
                self.email.send_alert(
                    f"[WARNING] Unified Odds File Corrupted ({self.unified_corruption_count}x)",
                    alert_body,
                    "unified_file_corruption"
                )
    
    def update_cache_from_all_sources(self):
        """Update cache from all data sources"""
        if not self.cache_manager:
            return
        
        print("\n" + "="*80)
        print("AUTO-UPDATING CACHE FROM ALL SOURCES")
        print("="*80)
        
        sources = [
            (self.base_dir / "bet365" / "bet365_current_pregame.json", "bet365"),
            (self.base_dir / "bet365" / "bet365_live_current.json", "bet365"),
            (self.base_dir / "fanduel" / "fanduel_pregame.json", "fanduel"),
            (self.base_dir / "fanduel" / "fanduel_live.json", "fanduel"),
            (self.base_dir / "1xbet" / "1xbet_pregame.json", "1xbet"),
            (self.base_dir / "1xbet" / "1xbet_live.json", "1xbet")
        ]
        
        total_new_teams = 0
        total_new_sports = 0
        errors = []
        
        for file_path, source in sources:
            summary = self.cache_manager.auto_update_from_file(file_path, source)
            if summary['success']:
                total_new_teams += len(summary['new_teams'])
                total_new_sports += len(summary['new_sports'])
            else:
                # Only add errors that aren't already reported as module failures
                for error in summary['errors']:
                    # Skip fanduel errors if modules are already failing
                    if 'fanduel' in error.lower():
                        # Check if fanduel modules are known failures
                        fanduel_failing = any('fanduel' in m.lower() for m in self.monitor.failure_counts.keys() 
                                             if self.monitor.failure_counts[m] > 0)
                        if fanduel_failing:
                            continue  # Skip this error, already reported
                    errors.append(error)
        
        if total_new_teams > 0 or total_new_sports > 0:
            message = f"Cache auto-updated: +{total_new_teams} teams, +{total_new_sports} sports"
            print(f"✓ {message}")
            self.email.send_alert("Cache Updated", message, "cache_update")
        
        if errors:
            error_msg = "Cache update errors:\n" + "\n".join(errors)
            print(f"⚠ {error_msg}")
            # Only send alert if there are unexpected errors
            if len(errors) > 0:
                self.email.send_alert("Cache Update Errors", error_msg, "cache_error")
    
    def monitoring_loop(self):
        """Main monitoring loop"""
        check_interval = self.config.get('monitoring.check_interval_seconds', 300)
        stale_threshold = self.config.get('monitoring.data_stale_threshold_minutes', 60)
        failure_threshold = self.config.get('monitoring.failure_threshold', 3)
        
        while self.running:
            print(f"\n{'='*80}")
            print(f"MONITORING CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")
            
            # Check all modules
            results = self.monitor.check_all_modules(stale_threshold)
            
            # Analyze results
            failed_modules = []
            warning_modules = []
            ok_modules = []
            
            for module_name, result in results.items():
                if result['status'] == 'error':
                    failed_modules.append(module_name)
                    print(f"❌ {module_name}: {', '.join(result['issues'])}")
                elif result['status'] == 'warning':
                    warning_modules.append(module_name)
                    print(f"⚠ {module_name}: {', '.join(result['warnings'])}")
                else:
                    ok_modules.append(module_name)
                    print(f"✓ {module_name}: {result['data'].get('match_count', 0)} matches, "
                          f"age: {result['data'].get('file_age_minutes', 0):.1f} min")
            
            # Send alerts for failures
            for module in failed_modules:
                failure_count = self.monitor.failure_counts[module]
                
                # Send immediate alert on first failure for critical modules
                # Or send after threshold is reached
                should_alert = False
                alert_urgency = "WARNING"
                
                if failure_count == 1:
                    # First failure - send immediate notification
                    should_alert = True
                    alert_urgency = "NOTICE"
                elif failure_count >= failure_threshold:
                    # Repeated failure - critical alert
                    should_alert = True
                    alert_urgency = "CRITICAL"
                
                if should_alert:
                    issues_list = '\n  - '.join(results[module]['issues'])
                    alert_body = f"""
[{alert_urgency}] Module Health Alert

Module: {module}
Status: FAILED
Failure Count: {failure_count} (Threshold: {failure_threshold})
Consecutive Failures: {failure_count}

Issues Detected:
  - {issues_list}

Possible Causes:
  • Module scraper not running or crashed
  • VPN blocking access (especially for FanDuel)
  • Network connectivity issues
  • API endpoint changes or rate limiting
  • Authentication/session expired

ACTION REQUIRED:
1. Check if the scraper process is running
2. Review module logs for detailed errors
3. Verify network connectivity and VPN status
4. Test API endpoints manually
5. Restart the module if needed

System will continue monitoring every {check_interval} seconds.
"""
                    self.email.send_alert(
                        f"[{alert_urgency}] Module Failure: {module}",
                        alert_body,
                        f"module_failure_{module}"
                    )
            
            # Send summary alert if multiple modules are failing
            if len(failed_modules) >= 2:
                summary_body = f"""
[SYSTEM ALERT] Multiple Module Failures Detected

Failed Modules: {len(failed_modules)} / {len(results)}
  ❌ {', '.join(failed_modules)}

Healthy Modules: {len(ok_modules)}
  ✓ {', '.join(ok_modules) if ok_modules else 'None'}

Warnings: {len(warning_modules)}
  ⚠ {', '.join(warning_modules) if warning_modules else 'None'}

Common Issues:
  • VPN may be blocking access (especially FanDuel)
  • Multiple scrapers not running
  • System-wide network issues
  • Insufficient permissions or resources

ACTION: Review individual module alerts for specific issues.

Next check in {check_interval} seconds.
"""
                self.email.send_alert(
                    f"[CRITICAL] {len(failed_modules)} Modules Failing",
                    summary_body,
                    "system_health_critical"
                )
            
            # Check unified_odds.json for corruption
            self.check_unified_file_health()
            
            # Summary
            print(f"\n📊 Summary: ✓ {len(ok_modules)} OK, ⚠ {len(warning_modules)} Warnings, ❌ {len(failed_modules)} Errors")
            
            # Update status API for web UI
            self.update_status_api(results, ok_modules, warning_modules, failed_modules)
            
            # Sleep until next check
            time.sleep(check_interval)
    
    def cache_update_loop(self):
        """Periodic cache update loop"""
        if not self.cache_manager:
            return
        
        update_interval = self.config.get('cache.update_interval_minutes', 30) * 60
        
        while self.running:
            try:
                self.update_cache_from_all_sources()
            except Exception as e:
                print(f"❌ Error in cache update loop: {e}")
                self.email.send_alert(
                    "Cache Update Error",
                    f"Error during automatic cache update:\n{str(e)}",
                    "cache_error"
                )
            
            time.sleep(update_interval)
    
    def update_status_api(self, results: Dict, ok_modules: List, warning_modules: List, failed_modules: List):
        """Update monitoring status for web UI"""
        try:
            status_data = {
                'monitoring_active': True,
                'timestamp': datetime.now().isoformat(),
                'check_interval_seconds': self.config.get('monitoring.check_interval_seconds', 300),
                'email_enabled': self.email.enabled if self.email else False,
                'cache_auto_update': self.cache_manager is not None,
                'summary': {
                    'healthy': len(ok_modules),
                    'warnings': len(warning_modules),
                    'errors': len(failed_modules),
                    'total': len(results)
                },
                'modules': {}
            }
            
            # Add detailed module status
            for module_name, result in results.items():
                status_data['modules'][module_name] = {
                    'status': result['status'],
                    'issues': result.get('issues', []),
                    'warnings': result.get('warnings', []),
                    'match_count': result['data'].get('match_count', 0),
                    'file_age_minutes': result['data'].get('file_age_minutes', 0),
                    'file_exists': result['data'].get('file_exists', False),
                    'failure_count': self.monitor.failure_counts.get(module_name, 0),
                    'last_checked': datetime.now().isoformat()
                }
            
            # Update the status file
            update_monitoring_status(status_data)
            
        except Exception as e:
            print(f"⚠️  Error updating status API: {e}")
    
    def start(self):
        """Start monitoring system"""
        if self.running:
            print("⚠ Monitoring system is already running")
            return
        
        print("\n" + "="*80)
        print("STARTING ODDS MONITORING SYSTEM")
        print("="*80)
        print(f"Email Notifications: {'ENABLED' if self.email.enabled else 'DISABLED'}")
        print(f"Cache Auto-Update: {'ENABLED' if self.cache_manager else 'DISABLED'}")
        print(f"Check Interval: {self.config.get('monitoring.check_interval_seconds')} seconds")
        print(f"Modules Monitored: {len(self.config.get('monitoring.modules', []))}")
        print("="*80 + "\n")
        
        # Send startup notification
        self.email.send_alert(
            "Monitoring System Started",
            f"The odds monitoring system has started successfully.\n\n"
            f"Configuration:\n"
            f"- Email alerts: {'ENABLED' if self.email.enabled else 'DISABLED'}\n"
            f"- Cache auto-update: {'ENABLED' if self.cache_manager else 'DISABLED'}\n"
            f"- Check interval: {self.config.get('monitoring.check_interval_seconds')} seconds\n"
            f"- Modules: {', '.join(self.config.get('monitoring.modules', []))}",
            "system_startup"
        )
        
        self.running = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # Start cache update thread if enabled
        if self.cache_manager:
            self.cache_update_thread = threading.Thread(target=self.cache_update_loop, daemon=True)
            self.cache_update_thread.start()
        
        print("✅ Monitoring system is running (Press Ctrl+C to stop)\n")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping monitoring system...")
            self.stop()
    
    def stop(self):
        """Stop monitoring system"""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if self.cache_update_thread:
            self.cache_update_thread.join(timeout=5)
        
        print("✅ Monitoring system stopped")
        
        # Send shutdown notification
        self.email.send_alert(
            "Monitoring System Stopped",
            "The odds monitoring system has been stopped.",
            "system_shutdown"
        )


if __name__ == "__main__":
    import sys
    
    # Check for config file argument
    config_file = Path("config.json")
    if len(sys.argv) > 1:
        config_file = Path(sys.argv[1])
    
    # Create and start monitoring system
    system = OddsMonitoringSystem(config_file)
    system.start()
