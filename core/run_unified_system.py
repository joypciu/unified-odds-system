#!/usr/bin/env python3
"""
Unified Odds System - Master Runner
Runs scrapers and automatically merges data into unified database
Supports real-time monitoring with instant updates

TESTING MODE: Currently configured to run ONLY 1xBet (pregame + live) 
to verify UI functionality and data collection on VPS.
Bet365 and FanDuel are temporarily disabled.
"""

import subprocess
import time
import os
import sys
import json
import threading
import traceback
import signal
import atexit
from datetime import datetime
from pathlib import Path
import argparse
import psutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.unified_odds_collector import UnifiedOddsCollector
from utils.security.secure_config import SecureConfig

# Import cache auto-update hook for automatic background updates
try:
    from cache_auto_update_hook import on_data_saved
    CACHE_AUTO_UPDATE_AVAILABLE = True
except ImportError:
    CACHE_AUTO_UPDATE_AVAILABLE = False
    print("⚠ Cache auto-update hook not available")

# Import monitoring system for integration
try:
    from monitoring_system import OddsMonitoringSystem
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    print("⚠ Monitoring system not available - health monitoring disabled")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Define dummy classes to avoid NameError
    class Observer:
        pass
    class FileSystemEventHandler:
        pass


class RealtimeUnifiedCollector:
    """Monitors source files and updates unified odds in real-time"""
    
    def __init__(self):
        self.collector = UnifiedOddsCollector()
        # base_dir should be project root, not core/
        self.base_dir = Path(__file__).parent.parent

        # Files to monitor
        self.bet365_pregame = self.base_dir / "bookmakers" / "bet365" / "bet365_current_pregame.json"
        self.bet365_live = self.base_dir / "bookmakers" / "bet365" / "bet365_live_current.json"
        self.fanduel_pregame = self.base_dir / "bookmakers" / "fanduel" / "fanduel_pregame.json"
        self.fanduel_live = self.base_dir / "bookmakers" / "fanduel" / "fanduel_live.json"
        self.xbet_pregame = self.base_dir / "bookmakers" / "1xbet" / "1xbet_pregame.json"
        self.xbet_live = self.base_dir / "bookmakers" / "1xbet" / "1xbet_live.json"

        self.output_file = self.base_dir / "data" / "unified_odds.json"
        
        # Track last modification times
        self.last_modified = {}
        self.update_lock = threading.Lock()
        self.last_update_time = 0
        self.min_update_interval = 0.5  # Minimum 0.5 seconds between updates
        
        # Statistics
        self.update_count = 0
        self.start_time = datetime.now()
        
    def get_file_mtime(self, filepath):
        """Get file modification time, return 0 if file doesn't exist"""
        try:
            return os.path.getmtime(filepath)
        except:
            return 0
    
    def has_file_changed(self, filepath):
        """Check if file has been modified since last check"""
        current_mtime = self.get_file_mtime(filepath)
        last_mtime = self.last_modified.get(str(filepath), 0)
        
        if current_mtime > last_mtime:
            self.last_modified[str(filepath)] = current_mtime
            return True
        return False
    
    def update_unified_odds(self, source_file=None):
        """Update unified odds database and trigger cache auto-update"""
        with self.update_lock:
            # Rate limiting - don't update too frequently
            current_time = time.time()
            if current_time - self.last_update_time < self.min_update_interval:
                return
            
            self.last_update_time = current_time
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            try:
                if source_file:
                    print(f"[{timestamp}] 🔄 Change detected: {Path(source_file).name}")
                    
                    # Trigger cache auto-update in background
                    if CACHE_AUTO_UPDATE_AVAILABLE:
                        # Determine source name from file path
                        file_path = Path(source_file)
                        if '1xbet' in str(file_path):
                            source_name = '1xbet'
                        elif 'bet365' in str(file_path):
                            source_name = 'bet365'
                        elif 'fanduel' in str(file_path):
                            source_name = 'fanduel'
                        else:
                            source_name = 'unknown'
                        
                        # Trigger background cache update
                        on_data_saved(source_name, str(source_file))
                
                # Load all data
                bet365_pregame = self.collector.load_bet365_pregame()
                bet365_live = self.collector.load_bet365_live()
                fanduel_pregame = self.collector.load_fanduel_pregame()
                fanduel_live = self.collector.load_fanduel_live()
                xbet_pregame = self.collector.load_1xbet_pregame()
                xbet_live = self.collector.load_1xbet_live()

                # Merge data
                pregame_matches = self.collector.merge_pregame_data(bet365_pregame, fanduel_pregame, xbet_pregame)
                live_matches = self.collector.merge_live_data(bet365_live, fanduel_live, xbet_live)
                
                # Create output
                output = {
                    'metadata': {
                        'generated_at': datetime.now().isoformat(),
                        'sources': ['bet365', 'fanduel', '1xbet'],
                        'total_pregame_matches': len(pregame_matches),
                        'total_live_matches': len(live_matches)
                    },
                    'pregame_matches': pregame_matches,
                    'live_matches': live_matches
                }
                
                # Save to file
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                
                self.update_count += 1
                
                # Count matches with both bookmakers
                pregame_both = sum(1 for m in pregame_matches 
                                  if m.get('bet365', {}).get('available') and 
                                     m.get('fanduel', {}).get('available'))
                
                live_both = sum(1 for m in live_matches 
                               if m.get('bet365', {}).get('available') and 
                                  m.get('fanduel', {}).get('available'))
                
                print(f"[{timestamp}] ✅ Update #{self.update_count}: "
                      f"Pregame: {len(pregame_matches)} ({pregame_both} matched) | "
                      f"Live: {len(live_matches)} ({live_both} matched)")
                
            except Exception as e:
                print(f"[{timestamp}] ❌ Error updating unified odds: {e}")
    
    def initial_update(self):
        """Perform initial update on startup"""
        print("=" * 80)
        print("REAL-TIME UNIFIED ODDS COLLECTOR")
        print("=" * 80)
        print()
        print(" Monitoring files:")
        print(f"   • {self.bet365_pregame.name}")
        print(f"   • {self.bet365_live.name}")
        print(f"   • {self.fanduel_pregame.name}")
        print(f"   • {self.fanduel_live.name}")
        print(f"   • {self.xbet_pregame.name}")
        print(f"   • {self.xbet_live.name}")
        print()
        print(f" Output: {self.output_file.name}")
        print()
        print(" Performing initial update...")
        print()
        
        self.update_unified_odds()
        
        print()
        print(" Watching for changes... (Press Ctrl+C to stop)")
        print("=" * 80)
        print()
    
    def print_statistics(self):
        """Print final statistics"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print()
        print("=" * 80)
        print(" SESSION STATISTICS")
        print("=" * 80)
        print(f"⏱  Duration: {elapsed:.1f} seconds")
        print(f" Total updates: {self.update_count}")
        if elapsed > 0:
            print(f" Update rate: {self.update_count / elapsed:.2f} updates/sec")
        print("=" * 80)


class OddsFileEventHandler(FileSystemEventHandler):
    """Handler for file system events"""
    
    def __init__(self, collector):
        self.collector = collector
        self.monitored_files = {
            str(collector.bet365_pregame),
            str(collector.bet365_live),
            str(collector.fanduel_pregame),
            str(collector.fanduel_live),
            str(collector.xbet_pregame),
            str(collector.xbet_live)
        }
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path in self.monitored_files:
            self.collector.update_unified_odds(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory and event.src_path in self.monitored_files:
            self.collector.update_unified_odds(event.src_path)


class AlertSystem:
    """Monitoring and alert system for scraper modules"""

    def __init__(self):
        # Email configuration - read from config.json
        self._load_email_config()

        # Alert tracking
        self.alert_history = []
        self.last_alert_time = {}
        self.alert_cooldown = 43200  # 12 hours between similar alerts

        # Memory monitoring
        self.memory_stats = {}
        self.memory_check_interval = 60  # Check memory every 60 seconds
        self.memory_threshold_mb = 400  # Alert if any process exceeds 400MB (reduced from 500MB)

    def _load_email_config(self):
        """Load email configuration from config.json"""
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                email_config = config.get('email', {})

                self.smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
                self.smtp_port = int(email_config.get('smtp_port', 587))
                self.sender_email = email_config.get('sender_email', 'usmanjoycse@gmail.com')
                self.sender_password = email_config.get('sender_password', 'your-app-password-here')
                self.admin_emails = [email_config.get('admin_email', 'usmanjoycse@gmail.com')]

                print(f"✓ Email configuration loaded from config.json")
                print(f"  SMTP: {self.smtp_server}:{self.smtp_port}")
                print(f"  From: {self.sender_email}")
                print(f"  To: {', '.join(self.admin_emails)}")
            else:
                print("⚠ config.json not found, using default email settings")
                self._set_default_email_config()
        except Exception as e:
            print(f"⚠ Error loading email config: {e}, using defaults")
            self._set_default_email_config()

    def _set_default_email_config(self):
        """Set default email configuration"""
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.sender_email = 'usmanjoycse@gmail.com'
        self.sender_password = 'your-app-password-here'
        self.admin_emails = ['usmanjoycse@gmail.com']


    def send_alert(self, module_name: str, error_type: str, message: str, details: str = ""):
        """Send alert to admin about scraper issues"""
        try:
            # Check cooldown to avoid spam
            alert_key = f"{module_name}_{error_type}"
            current_time = time.time()

            if alert_key in self.last_alert_time:
                if current_time - self.last_alert_time[alert_key] < self.alert_cooldown:
                    return  # Skip alert due to cooldown

            self.last_alert_time[alert_key] = current_time

            # Create alert message (remove emoji for Windows compatibility)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subject = f"UNIFIED ODDS SYSTEM ALERT - {module_name.upper()} {error_type.upper()}"

            body = f"""
UNIFIED ODDS SYSTEM MONITORING ALERT
=====================================

Timestamp: {timestamp}
Module: {module_name}
Error Type: {error_type}
Message: {message}

Details:
{details}

System Status:
- Base Directory: {os.path.dirname(os.path.abspath(__file__))}
- Python Version: {sys.version}

Please check the system logs and restart if necessary.
"""

            # Send email if configured
            if self.sender_email and self.sender_password and self.admin_emails:
                self._send_email_alert(subject, body)

            # Log alert
            alert_entry = {
                'timestamp': timestamp,
                'module': module_name,
                'error_type': error_type,
                'message': message,
                'details': details
            }
            self.alert_history.append(alert_entry)

            # Keep only last 100 alerts
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]

            print(f"ALERT SENT: {module_name} - {error_type}: {message}")

        except Exception as e:
            print(f"Failed to send alert: {e}")

    def _send_email_alert(self, subject: str, body: str):
        """Send email alert"""
        try:
            # Check if we have credentials
            if not self.sender_email or not self.sender_password or self.sender_password == 'your-app-password-here':
                print(f"Email not configured - logging alert instead: {subject}")
                print("To enable email alerts, set SENDER_PASSWORD environment variable")
                return

            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.admin_emails)
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            print(f"Attempting to send email to: {self.admin_emails}")
            print(f"From: {self.sender_email}")
            print(f"SMTP: {self.smtp_server}:{self.smtp_port}")

            # Add timeout to prevent hanging (especially with VPN issues)
            # Try port 465 (SSL) if port 587 (TLS) fails with VPN
            timeout = 30
            
            try:
                if self.smtp_port == 465:
                    # Use SMTP_SSL for port 465
                    print(f"Connecting to SMTP server with SSL (timeout: {timeout}s)...")
                    server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=timeout)
                    print("Connected with SSL! Logging in...")
                else:
                    # Use SMTP with STARTTLS for port 587
                    print(f"Connecting to SMTP server (timeout: {timeout}s)...")
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=timeout)
                    print("Connected! Starting TLS...")
                    server.starttls()
                    print("TLS started! Logging in...")
                
                server.login(self.sender_email, self.sender_password)
                print("Logged in! Sending email...")
                text = msg.as_string()
                server.sendmail(self.sender_email, self.admin_emails, text)
                server.quit()
                print("✓ Email sent successfully!")
                
            except (TimeoutError, OSError) as e:
                # Try fallback to port 465 if 587 failed
                if self.smtp_port == 587:
                    print(f"\n⚠ Port 587 failed: {e}")
                    print("Trying fallback to port 465 (SSL)...")
                    try:
                        server = smtplib.SMTP_SSL(self.smtp_server, 465, timeout=timeout)
                        server.login(self.sender_email, self.sender_password)
                        text = msg.as_string()
                        server.sendmail(self.sender_email, self.admin_emails, text)
                        server.quit()
                        print("✓ Email sent successfully via port 465!")
                        print("💡 TIP: Update config.json to use port 465 permanently")
                    except Exception as fallback_error:
                        raise Exception(f"Both ports failed - 587: {e}, 465: {fallback_error}")
                else:
                    raise

        except TimeoutError as e:
            print(f"❌ Email connection timeout: {e}")
            print("TROUBLESHOOTING:")
            print("  1. Your VPN (NordVPN) may be blocking SMTP ports")
            print("  2. Try disconnecting VPN temporarily and test again")
            print("  3. Check your firewall settings")
            print("\nAlert logged but email not sent")
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error: {e}")
            print("For Gmail, you need an App Password, not your regular password")
            print("Visit: https://support.google.com/accounts/answer/185833")
        except Exception as e:
            print(f"❌ Email alert failed: {e}")
            print("Alert logged but email not sent - check SMTP configuration")

    def monitor_process(self, process_info: dict):
        """Monitor a scraper process and alert if it fails"""
        try:
            proc = process_info['process']
            name = process_info['name']

            # Check if process is still running
            if proc.poll() is not None:
                # Process has terminated
                return_code = proc.returncode
                if return_code != 0:
                    # Process failed
                    # COMMENTED OUT: Reduced email notifications
                    # self.send_alert(
                    #     module_name=name,
                    #     error_type="PROCESS_CRASH",
                    #     message=f"Scraper process crashed with code {return_code}",
                    #     details=f"Process: {name}\nReturn Code: {return_code}\nPID: {proc.pid}"
                    # )
                    pass
                return False

            return True

        except Exception as e:
            # COMMENTED OUT: Reduced email notifications
            # self.send_alert(
            #     module_name=process_info.get('name', 'unknown'),
            #     error_type="MONITOR_ERROR",
            #     message=f"Process monitoring failed: {e}"
            # )
            return False

    def check_data_files(self):
        """Check if data files are being updated"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            files_to_check = [
                ('bet365', 'bet365_current_pregame.json'),
                ('fanduel', 'fanduel_pregame.json'),
                ('1xbet', '1xbet_pregame.json'),
                ('unified', 'unified_odds.json')
            ]

            current_time = time.time()
            stale_threshold = 600  # 10 minutes

            for module, filename in files_to_check:
                filepath = os.path.join(base_dir, module, filename)
                if os.path.exists(filepath):
                    mtime = os.path.getmtime(filepath)
                    age = current_time - mtime

                    if age > stale_threshold:
                        # COMMENTED OUT: Reduced email notifications
                        # self.send_alert(
                        #     module_name=module,
                        #     error_type="STALE_DATA",
                        #     message=f"Data file not updated for {age/60:.1f} minutes",
                        #     details=f"File: {filename}\nLast Modified: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}"
                        # )
                        pass
                else:
                    # COMMENTED OUT: Reduced email notifications
                    # self.send_alert(
                    #     module_name=module,
                    #     error_type="MISSING_FILE",
                    #     message=f"Data file not found: {filename}",
                    #     details=f"Expected path: {filepath}"
                    # )
                    pass

        except Exception as e:
            # COMMENTED OUT: Reduced email notifications
            # self.send_alert(
            #     module_name="monitoring",
            #     error_type="FILE_CHECK_ERROR",
            #     message=f"Data file check failed: {e}"
            # )
            pass

    def check_memory_usage(self, processes_list):
        """Check memory usage of all scraper processes"""
        try:
            for proc_info in list(self.memory_stats.keys()):
                # Find the process in current processes list
                current_proc = None
                for p in processes_list:
                    if p.get('name') == proc_info:
                        current_proc = p
                        break

                if current_proc and current_proc['process'].poll() is None:
                    # Process is still running, check memory
                    try:
                        proc = psutil.Process(current_proc['process'].pid)
                        memory_mb = proc.memory_info().rss / 1024 / 1024  # Convert to MB

                        # Store memory stats
                        if proc_info not in self.memory_stats:
                            self.memory_stats[proc_info] = []

                        self.memory_stats[proc_info].append({
                            'timestamp': time.time(),
                            'memory_mb': memory_mb
                        })

                        # Keep only last 10 readings
                        if len(self.memory_stats[proc_info]) > 10:
                            self.memory_stats[proc_info] = self.memory_stats[proc_info][-10:]

                        # Check threshold
                        if memory_mb > self.memory_threshold_mb:
                            # COMMENTED OUT: Reduced email notifications
                            # self.send_alert(
                            #     module_name=proc_info,
                            #     error_type="HIGH_MEMORY",
                            #     message=f"Process memory usage: {memory_mb:.1f} MB (threshold: {self.memory_threshold_mb} MB)",
                            #     details=f"Process: {proc_info}\nPID: {proc.pid}\nMemory: {memory_mb:.1f} MB\nCPU: {proc.cpu_percent():.1f}%"
                            # )
                            pass

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process might have died or we can't access it
                        pass

        except Exception as e:
            # COMMENTED OUT: Reduced email notifications
            # self.send_alert(
            #     module_name="memory_monitor",
            #     error_type="MEMORY_CHECK_ERROR",
            #     message=f"Memory monitoring failed: {e}"
            # )
            pass

    def get_memory_report(self):
        """Generate memory usage report"""
        report = "Memory Usage Report:\n"
        report += "=" * 50 + "\n"

        for proc_name, readings in self.memory_stats.items():
            if readings:
                latest = readings[-1]
                avg_memory = sum(r['memory_mb'] for r in readings) / len(readings)
                max_memory = max(r['memory_mb'] for r in readings)

                report += f"{proc_name}:\n"
                report += f"  Current: {latest['memory_mb']:.1f} MB\n"
                report += f"  Average: {avg_memory:.1f} MB\n"
                report += f"  Peak: {max_memory:.1f} MB\n"
                report += "\n"

        return report


class UnifiedSystemRunner:
    """Manages running scrapers and unified collector"""

    def __init__(self, include_live=False, live_only=False):
        # Base dir is project root (parent of core/)
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.bet365_dir = os.path.join(self.base_dir, "bookmakers", "bet365")
        self.fanduel_dir = os.path.join(self.base_dir, "bookmakers", "fanduel")
        self.xbet_dir = os.path.join(self.base_dir, "bookmakers", "1xbet")

        # Load configuration to check which scrapers are enabled
        self.config = self._load_config()
        self.enabled_scrapers = self.config.get('enabled_scrapers', {
            '1xbet': True,
            'fanduel': True,
            'bet365': False
        })

        # Process tracking
        self.processes = []
        self.merge_interval = 30  # seconds
        self.include_live = include_live  # Whether to include live scrapers
        self.live_only = live_only  # Whether to run ONLY live scrapers
        self.chrome_processes = []  # Track Chrome processes we started
        self.shutdown_flag = False

        # Alert system
        self.alert_system = AlertSystem()

        # Monitoring system integration
        self.monitoring_system = None
        if MONITORING_AVAILABLE:
            try:
                self.monitoring_system = OddsMonitoringSystem()
                print("✓ Monitoring system integrated")
            except Exception as e:
                print(f"⚠ Failed to initialize monitoring system: {e}")
        else:
            print("⚠ Monitoring system not available")
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup)
    
    def _load_config(self):
        """Load encrypted configuration from config.json"""
        try:
            config_file = os.path.join(self.base_dir, 'config.json')
            if os.path.exists(config_file):
                secure_config = SecureConfig(config_file)
                config = secure_config.load_config()
                print(f"✓ Encrypted configuration loaded from config.json")
                enabled = config.get('enabled_scrapers', {})
                print(f"  Enabled scrapers: 1xBet={enabled.get('1xbet', False)}, FanDuel={enabled.get('fanduel', False)}, Bet365={enabled.get('bet365', False)}")
                return config
            else:
                print("⚠ config.json not found, using defaults (1xBet and FanDuel enabled)")
                return {'enabled_scrapers': {'1xbet': True, 'fanduel': True, 'bet365': False}}
        except Exception as e:
            print(f"⚠ Error loading config: {e}, using defaults")
            return {'enabled_scrapers': {'1xbet': True, 'fanduel': True, 'bet365': False}}
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C and termination signals gracefully"""
        if not self.shutdown_flag:
            self.shutdown_flag = True
            print("\n\n🛑 Shutdown signal received (Ctrl+C)...")
            print("   Stopping all modules gracefully...")
            self.stop_all_scrapers()
            sys.exit(0)
    
    def _cleanup(self):
        """Cleanup function called on exit"""
        if not self.shutdown_flag:
            self.stop_all_scrapers()

    def _start_monitoring_background(self):
        """Start monitoring system in background thread"""
        if self.monitoring_system:
            try:
                self.monitoring_system.start()
            except Exception as e:
                print(f"❌ Failed to start monitoring system: {e}")

    def _monitor_processes_health(self):
        """Monitor health of all scraper processes"""
        memory_check_counter = 0

        while True:
            try:
                # Check each process
                for proc_info in self.processes[:]:  # Copy list to avoid modification issues
                    if not self.alert_system.monitor_process(proc_info):
                        # Process is dead, remove from list
                        self.processes.remove(proc_info)

                # Periodic memory check
                memory_check_counter += 1
                if memory_check_counter >= self.alert_system.memory_check_interval // 10:  # Every memory_check_interval seconds
                    self.alert_system.check_memory_usage(self.processes)
                    memory_check_counter = 0

                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                # COMMENTED OUT: Reduced email notifications
                # self.alert_system.send_alert(
                #     module_name="process_monitor",
                #     error_type="MONITOR_FAILED",
                #     message=f"Process health monitoring failed: {e}"
                # )
                time.sleep(30)  # Wait longer on error
    
    def log(self, message):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Remove emojis for Windows compatibility
        message = message.replace("🚀", "[START]").replace("✅", "[OK]").replace("❌", "[ERROR]").replace("⏱️", "[TIME]").replace("📊", "[STATS]").replace("⚠️", "[WARN]").replace("⏭️", "[SKIP]").replace("⏳", "[WAIT]").replace("📡", "[API]").replace("💾", "[SAVE]").replace("📋", "[HISTORY]").replace("🔄", "[UPDATE]").replace("➕", "[ADD]").replace("⚠️", "[WARN]").replace("⏹", "[STOP]").replace("🔄", "[CHANGE]")
        print(f"[{timestamp}] {message}")
    
    def start_scraper(self, script_name, working_dir, name, args=None):
        """Start a scraper in background with memory optimization"""
        try:
            # Check if working directory exists
            if not os.path.exists(working_dir):
                self.log(f"⚠️  Skipping {name} - directory not found: {working_dir}")
                return False

            self.log(f"🚀 Starting {name}...")
            self.log(f"   Script: {script_name}")
            self.log(f"   Working dir: {working_dir}")
            self.log(f"   Args: {args}")

            # Build command with memory optimization
            cmd = [sys.executable, script_name]
            if args:
                cmd.extend(args)

            self.log(f"   Command: {' '.join(cmd)}")
            
            # Clean environment for subprocess - avoid Chrome flag conflicts
            env = os.environ.copy()
            # Remove any conflicting environment variables
            env.pop('CHROMIUM_FLAGS', None)
            env.pop('CHROME_MEMORY_PRESSURE_THRESHOLD', None)
            # Chrome flags are now handled directly in fanduel_master_collector.py

            # Start process (for debugging, don't detach and capture output)
            self.log(f"Starting process (not detached for debugging)...")
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                env=env
                # Removed detached flags and output redirection for debugging
            )

            self.processes.append({
                'name': name,
                'process': process,
                'script': script_name,
                'start_time': time.time()
            })

            # Initialize memory tracking for this process
            self.alert_system.memory_stats[name] = []

            # Track Chrome processes started by this scraper
            self.track_chrome_processes(process.pid)

            self.log(f" {name} started (PID: {process.pid})")
            self.log(f"   -> Check the console window for {name}")
            return True

        except Exception as e:
            self.log(f" Failed to start {name}: {e}")
            # Send alert for startup failure
            # COMMENTED OUT: Reduced email notifications
            # self.alert_system.send_alert(
            #     module_name=name,
            #     error_type="STARTUP_FAILED",
            #     message=f"Failed to start scraper: {e}",
            #     details=f"Script: {script_name}\nWorking Dir: {working_dir}\nArgs: {args}"
            # )
            return False
    
    def check_json_files(self):
        """Check if required JSON files exist - 1xBet only for testing"""
        files = {
            # 'Bet365 Pregame': os.path.join(self.bet365_dir, 'bet365_current_pregame.json'),
            # 'FanDuel Pregame': os.path.join(self.fanduel_dir, 'fanduel_pregame.json'),
            '1xBet Pregame': os.path.join(self.xbet_dir, '1xbet_pregame.json')
        }

        # Add live files if enabled
        if self.include_live:
            # files['Bet365 Live'] = os.path.join(self.bet365_dir, 'bet365_live_current.json')
            # files['FanDuel Live'] = os.path.join(self.fanduel_dir, 'live.json')
            files['1xBet Live'] = os.path.join(self.xbet_dir, '1xbet_live.json')

        existing = {}
        for name, path in files.items():
            exists = os.path.exists(path)
            existing[name] = exists
            if exists:
                # Check file size
                size = os.path.getsize(path)
                self.log(f" {name}: Found ({size:,} bytes)")
            else:
                self.log(f"  {name}: Not found")

        return all(existing.values())

    def track_chrome_processes(self, parent_pid):
        """Track Chrome processes spawned by a scraper process"""
        try:
            parent = psutil.Process(parent_pid)
            # Wait a moment for Chrome to start
            time.sleep(2)

            # Find Chrome processes that are children of our scrapers
            for child in parent.children(recursive=True):
                if child.name().lower() in ['chrome.exe', 'chromium.exe', 'google chrome.exe']:
                    self.chrome_processes.append(child.pid)
                    self.log(f" Tracking Chrome process (PID: {child.pid}) from {parent_pid}")
        except Exception as e:
            self.log(f" Could not track Chrome processes: {e}")

    def cleanup_chrome_instances(self):
        """Clean up isolated Chrome instances but preserve user's Chrome"""
        if not self.chrome_processes:
            return

        self.log(" Cleaning up isolated Chrome instances...")

        try:
            # Get all Chrome processes currently running
            all_chrome = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in ['chrome.exe', 'chromium.exe', 'google chrome.exe']:
                        all_chrome.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Identify user's Chrome (has user data directory, not headless/temp)
            user_chrome_pids = []
            scraper_chrome_pids = []

            for proc in all_chrome:
                try:
                    cmdline = proc.info.get('cmdline', [])
                    cmdline_str = ' '.join(cmdline) if cmdline else ''

                    # Check if this is a scraper Chrome (headless or temp directory)
                    is_scraper_chrome = (
                        '--headless' in cmdline_str or
                        '--no-sandbox' in cmdline_str or
                        '--disable-dev-shm-usage' in cmdline_str or
                        any(pid in self.chrome_processes for pid in [proc.pid] + [c.pid for c in proc.children()])
                    )

                    if is_scraper_chrome:
                        scraper_chrome_pids.append(proc.pid)
                    else:
                        user_chrome_pids.append(proc.pid)

                except Exception:
                    continue

            # Close only scraper Chrome instances
            closed_count = 0
            for pid in scraper_chrome_pids:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=3)
                    closed_count += 1
                    self.log(f" Closed scraper Chrome (PID: {pid})")
                except Exception:
                    try:
                        proc = psutil.Process(pid)
                        proc.kill()
                        closed_count += 1
                        self.log(f" Force killed scraper Chrome (PID: {pid})")
                    except:
                        pass

            self.log(f"Cleaned up {closed_count} scraper Chrome instances")
            if user_chrome_pids:
                self.log(f" Preserved {len(user_chrome_pids)} user Chrome instances")

        except Exception as e:
            self.log(f" Chrome cleanup error: {e}")

    def run_unified_collector(self):
        """Run the unified odds collector"""
        try:
            self.log(" Running unified collector...")

            # Import and run collector
            from unified_odds_collector import UnifiedOddsCollector

            collector = UnifiedOddsCollector()
            collector.collect_and_merge()

            self.log(" Unified database updated")
            return True

        except Exception as e:
            self.log(f" Collector failed: {e}")
            # Send alert for collector failure
            # COMMENTED OUT: Reduced email notifications
            # self.alert_system.send_alert(
            #     module_name="unified_collector",
            #     error_type="COLLECTOR_FAILED",
            #     message=f"Unified odds collector failed: {e}",
            #     details=f"Error: {e}\nTraceback: {traceback.format_exc()}"
            # )
            return False
    
    def stop_all_scrapers(self):
        """Stop all running scrapers and clean up Chrome instances"""
        self.log("\n Stopping all scrapers...")

        failed_stops = []

        for proc_info in self.processes:
            try:
                proc = proc_info['process']
                name = proc_info['name']

                # Check if process is still running before stopping
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        self.log(f" Stopped {name}")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
                        self.log(f"  Force killed {name}")
                else:
                    # Process already stopped
                    return_code = proc.returncode
                    if return_code != 0:
                        failed_stops.append(proc_info)
                        # COMMENTED OUT: Reduced email notifications
                        # self.alert_system.send_alert(
                        #     module_name=name,
                        #     error_type="UNEXPECTED_STOP",
                        #     message=f"Scraper stopped unexpectedly with code {return_code}",
                        #     details=f"Process: {name}\nReturn Code: {return_code}\nRuntime: {time.time() - proc_info.get('start_time', time.time()):.1f}s"
                        # )
                    else:
                        self.log(f" {name} already stopped (normal)")

            except Exception as e:
                failed_stops.append(proc_info)
                # COMMENTED OUT: Reduced email notifications
                # self.alert_system.send_alert(
                #     module_name=proc_info.get('name', 'unknown'),
                #     error_type="STOP_FAILED",
                #     message=f"Failed to stop scraper: {e}",
                #     details=f"Process: {proc_info.get('name', 'unknown')}\nError: {e}"
                # )

        # Clean up isolated Chrome instances (but not user's Chrome)
        self.cleanup_chrome_instances()

        # Report any failed stops
        if failed_stops:
            self.log(f"⚠️  {len(failed_stops)} scrapers failed to stop properly")
    
    def _incremental_merge_worker(self):
        """Background worker for incremental merging"""
        while True:
            try:
                # Check if source files have been updated
                if self.check_json_files():
                    self.log("🔄 Incremental merge triggered by new data...")
                    self.run_unified_collector()
                    self.log("✅ Incremental merge completed")
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                self.log(f"Incremental merge error: {e}")
                time.sleep(5)

    def run_one_time_collection(self, duration=120):
        """Run scrapers once, collect data, then merge"""
        print("="*80)
        print("UNIFIED ODDS SYSTEM - ONE-TIME COLLECTION")
        if self.live_only:
            print("Mode: LIVE ONLY")
        elif self.include_live:
            print("Mode: PREGAME + LIVE")
        else:
            print("Mode: PREGAME ONLY")
        print("="*80)

        # Start monitoring system if available
        if self.monitoring_system:
            print("Starting monitoring system...")
            monitoring_thread = threading.Thread(target=self._start_monitoring_background, daemon=True)
            monitoring_thread.start()
            time.sleep(2)  # Give monitoring system time to start

        # Calculate collection time (in minutes for FanDuel)
        collection_minutes = max(1, duration // 60)

        # Start scrapers
        self.log("\n Starting data collection...")

        # Only start pregame scrapers if not live_only mode
        bet365_pregame_started = True
        fanduel_pregame_started = True
        xbet_pregame_started = True
        
        if not self.live_only:
            # Bet365 Pregame - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_pregame_started = self.start_scraper(
                    'bet365_pregame_monitor.py',
                    self.bet365_dir,
                    'Bet365 Pregame',
                    args=['--headless']
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Pregame - DISABLED in config.json")

            # FanDuel Pregame - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_pregame_started = self.start_scraper(
                    'fanduel_master_collector.py',
                    self.fanduel_dir,
                    'FanDuel Pregame (Homepage-First)',
                    args=[str(collection_minutes)]
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Pregame - DISABLED in config.json")

            # 1xBet Pregame - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_pregame_started = self.start_scraper(
                    '1xbet_pregame.py',
                    self.xbet_dir,
                    '1xBet Pregame'
                )
            else:
                self.log("⏭️ 1xBet Pregame - DISABLED in config.json")

        # Start live scrapers if enabled or if live_only mode
        bet365_live_started = True
        fanduel_live_started = True
        xbet_live_started = True

        if self.include_live or self.live_only:
            time.sleep(2)

            # Bet365 Live - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_live_started = self.start_scraper(
                    'bet365_live_concurrent_scraper.py',
                    self.bet365_dir,
                    'Bet365 Live'
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Live - DISABLED in config.json")

            # FanDuel Live - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_live_started = self.start_scraper(
                    'fanduel_live_monitor.py',
                    self.fanduel_dir,
                    'FanDuel Live'
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Live - DISABLED in config.json")

            # 1xBet Live - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_live_started = self.start_scraper(
                    '1xbet_live.py',
                    self.xbet_dir,
                    '1xBet Live'
                    # Removed --single flag to allow continuous collection
                )
            else:
                self.log("⏭️ 1xBet Live - DISABLED in config.json")

        # Start 1xBet Futures scraper - runs once to collect long-term bets
        xbet_futures_started = True
        if self.enabled_scrapers.get('1xbet', False):
            self.log("\n📊 Starting 1xBet Futures/Outrights scraper...")
            time.sleep(2)
            xbet_futures_started = self.start_scraper(
                '1xbet_futures_scraper.py',
                self.xbet_dir,
                '1xBet Futures/Outrights'
            )
        else:
            self.log("⏭️ 1xBet Futures - DISABLED in config.json")

        if not (fanduel_pregame_started and xbet_pregame_started and
                bet365_live_started and fanduel_live_started and xbet_live_started):
            self.log("\n Failed to start all scrapers!")
            self.stop_all_scrapers()
            return

        # Give extra time for browser setup
        self.log("\n Waiting for Bet365 browser to initialize (30 seconds)...")
        time.sleep(30)

        # FanDuel needs more time to open all its sport tabs
        self.log("\n⏳ Waiting for FanDuel to open all sport tabs (45 seconds)...")
        self.log("   (FanDuel opens multiple tabs for different sports)")
        time.sleep(45)

        # Now collect data for the remaining time - scrapers save data immediately when found
        elapsed = 75  # 30 + 45 seconds
        remaining_duration = max(15, duration - elapsed)  # At least 15 seconds for data collection
        self.log(f"\n Collecting data for {remaining_duration} seconds...")
        self.log("   (Scrapers save data immediately when found - no need to wait for full cycle)")
        self.log("   (Check the separate windows - you should see browser activity)")

        # Start incremental merging in background
        import threading
        merge_thread = threading.Thread(target=self._incremental_merge_worker, daemon=True)
        merge_thread.start()

        # Start process monitoring
        monitor_thread = threading.Thread(target=self._monitor_processes_health, daemon=True)
        monitor_thread.start()

        # Force initial memory check
        self.alert_system.check_memory_usage(self.processes)

        for i in range(remaining_duration):
            remaining = remaining_duration - i
            if remaining % 30 == 0:
                self.log(f"   {remaining} seconds remaining...")
                # Periodic health check
                self.alert_system.check_data_files()

                # Show memory report every 30 seconds
                if self.alert_system.memory_stats:
                    memory_report = self.alert_system.get_memory_report()
                    self.log("[STATS] Memory Report:")
                    for line in memory_report.split('\n'):
                        if line.strip():
                            self.log(f"   {line}")
                else:
                    self.log("[STATS] No memory data available yet")

            time.sleep(1)

        # Stop scrapers
        self.stop_all_scrapers()

        # Final merge
        self.log("\n Performing final merge...")
        if self.run_unified_collector():
            self.log("\n" + "="*80)
            self.log(" SUCCESS! unified_odds.json has been created")
            self.log("="*80)
            self.log("\n You can now use unified_odds.json in your UI")
            self.log("   Run: python example_ui_integration.py to see results")
        else:
            self.log("\n Merge failed. Check error messages above.")
    
    def run_continuous_mode(self):
        """Run scrapers continuously and merge data incrementally"""
        print("="*80)
        print("UNIFIED ODDS SYSTEM - CONTINUOUS MODE")
        if self.live_only:
            print("Mode: LIVE ONLY")
        elif self.include_live:
            print("Mode: PREGAME + LIVE")
        else:
            print("Mode: PREGAME ONLY")
        print("="*80)
        print(f"\nWill merge data incrementally as it becomes available")
        print("Press Ctrl+C to stop\n")

        # Start monitoring system if available
        if self.monitoring_system:
            print("Starting monitoring system...")
            monitoring_thread = threading.Thread(target=self._start_monitoring_background, daemon=True)
            monitoring_thread.start()
            time.sleep(2)  # Give monitoring system time to start

        # Start scrapers
        self.log(" Starting continuous data collection...")

        # Only start pregame scrapers if not live_only mode
        bet365_pregame_started = True
        fanduel_pregame_started = True
        xbet_pregame_started = True
        
        if not self.live_only:
            # Bet365 Pregame - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_pregame_started = self.start_scraper(
                    'bet365_pregame_monitor.py',
                    self.bet365_dir,
                    'Bet365 Pregame',
                    args=['--headless']
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Pregame - DISABLED in config.json")

            # FanDuel Pregame - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_pregame_started = self.start_scraper(
                    'fanduel_master_collector.py',
                    self.fanduel_dir,
                    'FanDuel Pregame (Homepage-First)',
                    args=['0']  # 0 = continuous mode
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Pregame - DISABLED in config.json")

            # 1xBet Pregame - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_pregame_started = self.start_scraper(
                    '1xbet_pregame.py',
                    self.xbet_dir,
                    '1xBet Pregame',
                    args=['--monitor']  # Add --monitor flag for continuous collection
                )
            else:
                self.log("⏭️ 1xBet Pregame - DISABLED in config.json")

        # Start live scrapers if enabled or if live_only mode
        bet365_live_started = True
        fanduel_live_started = True
        xbet_live_started = True

        if self.include_live or self.live_only:
            time.sleep(2)

            # Bet365 Live - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_live_started = self.start_scraper(
                    'bet365_live_concurrent_scraper.py',
                    self.bet365_dir,
                    'Bet365 Live'
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Live - DISABLED in config.json")

            # FanDuel Live - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_live_started = self.start_scraper(
                    'fanduel_live_monitor.py',
                    self.fanduel_dir,
                    'FanDuel Live'
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Live - DISABLED in config.json")

            # 1xBet Live - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_live_started = self.start_scraper(
                    '1xbet_live.py',
                    self.xbet_dir,
                    '1xBet Live'
                )
            else:
                self.log("⏭️ 1xBet Live - DISABLED in config.json")

        # Simplified check - only verify 1xBet started successfully
        if not (xbet_pregame_started or xbet_live_started):
            self.log("\n Failed to start 1xBet scrapers!")
            self.stop_all_scrapers()
            return

        # Wait for 1xBet initialization (reduced time for single scraper)
        self.log("\n Waiting for 1xBet browser to initialize (30 seconds)...")
        time.sleep(30)

        self.log(" Collecting initial 1xBet data (30 seconds)...")
        time.sleep(30)

        # Start incremental merging in background
        import threading
        merge_thread = threading.Thread(target=self._incremental_merge_worker, daemon=True)
        merge_thread.start()

        # Start monitoring thread for process health
        monitoring_thread = threading.Thread(target=self._monitor_processes_health, daemon=True)
        monitoring_thread.start()

        # Continuous monitoring loop
        merge_count = 0
        try:
            while True:
                merge_count += 1

                self.log(f"\n Monitoring cycle #{merge_count}")

                # Check data exists and log status
                if self.check_json_files():
                    self.log("  [OK] All data sources active")
                else:
                    self.log("  [WARN] Some data sources not yet available")

                # Periodic data file health check
                if merge_count % 10 == 0:  # Every 10 cycles (5 minutes)
                    self.alert_system.check_data_files()

                    # Log memory report
                    if self.alert_system.memory_stats:
                        memory_report = self.alert_system.get_memory_report()
                        self.log("[STATS] Memory Report:")
                        for line in memory_report.split('\n'):
                            if line.strip():
                                self.log(f"   {line}")
                    else:
                        self.log("[STATS] No memory data available yet")

                # More frequent memory logging (every cycle)
                if merge_count % 2 == 0:  # Every 2 cycles (1 minute)
                    self.alert_system.check_memory_usage(self.processes)
                    if self.alert_system.memory_stats:
                        # Quick memory summary
                        total_memory = 0
                        process_count = 0
                        for proc_name, readings in self.alert_system.memory_stats.items():
                            if readings:
                                total_memory += readings[-1]['memory_mb']
                                process_count += 1
                        if process_count > 0:
                            avg_memory = total_memory / process_count
                            self.log(f"[STATS] Memory: {total_memory:.1f} MB total, {avg_memory:.1f} MB avg per process")

                self.log(f" Next status check in {self.merge_interval} seconds...")
                time.sleep(self.merge_interval)

        except KeyboardInterrupt:
            self.log("\n\n  Stopping continuous mode...")
            self.stop_all_scrapers()

            # Final merge
            self.log("\n Running final merge...")
            self.run_unified_collector()

            self.log("\n" + "="*80)
            self.log(" Continuous mode stopped")
            self.log("="*80)
            self.log(" Final unified_odds.json is ready to use")
    
    def run_realtime_mode(self):
        """Run in real-time mode with instant updates on file changes"""
        print("="*80)
        print("UNIFIED ODDS SYSTEM - REAL-TIME MODE")
        if self.live_only:
            print("Mode: LIVE ONLY - Real-time file monitoring")
        else:
            print("Mode: Real-time file monitoring with instant updates")
        print("="*80)
        print()

        # Start monitoring system if available
        if self.monitoring_system:
            print("Starting monitoring system...")
            monitoring_thread = threading.Thread(target=self._start_monitoring_background, daemon=True)
            monitoring_thread.start()
            time.sleep(2)  # Give monitoring system time to start

        # Start scrapers
        self.log(" Starting scrapers in background...")
        print()

        # Only start pregame scrapers if not live_only mode
        bet365_pregame_started = True
        fanduel_pregame_started = True
        xbet_pregame_started = True
        
        if not self.live_only:
            # Bet365 Pregame - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_pregame_started = self.start_scraper(
                    'bet365_pregame_monitor.py',
                    self.bet365_dir,
                    'Bet365 Pregame'
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Pregame - DISABLED in config.json")

            # FanDuel Pregame - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_pregame_started = self.start_scraper(
                    'fanduel_master_collector.py',
                    self.fanduel_dir,
                    'FanDuel Pregame (Homepage-First)',
                    args=['0']  # 0 = infinite monitoring
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Pregame - DISABLED in config.json")

            # 1xBet Pregame - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_pregame_started = self.start_scraper(
                    '1xbet_pregame.py',
                    self.xbet_dir,
                    '1xBet Pregame',
                    args=['--monitor']  # Add --monitor flag for continuous collection
                )
                time.sleep(2)
            else:
                self.log("⏭️ 1xBet Pregame - DISABLED in config.json")

        # Start live scrapers if requested or if live_only mode
        bet365_live_started = True
        fanduel_live_started = True
        xbet_live_started = True

        if self.include_live or self.live_only:
            # Bet365 Live - only if enabled in config
            if self.enabled_scrapers.get('bet365', False):
                bet365_live_started = self.start_scraper(
                    'bet365_live_concurrent_scraper.py',
                    self.bet365_dir,
                    'Bet365 Live'
                )
                time.sleep(2)
            else:
                self.log("⏭️ Bet365 Live - DISABLED in config.json")

            # FanDuel Live - only if enabled in config
            if self.enabled_scrapers.get('fanduel', False):
                fanduel_live_started = self.start_scraper(
                    'fanduel_live_monitor.py',
                    self.fanduel_dir,
                    'FanDuel Live',
                    args=['0']  # 0 = infinite monitoring
                )
                time.sleep(2)
            else:
                self.log("⏭️ FanDuel Live - DISABLED in config.json")

            # 1xBet Live - only if enabled in config
            if self.enabled_scrapers.get('1xbet', False):
                xbet_live_started = self.start_scraper(
                    '1xbet_live.py',
                    self.xbet_dir,
                    '1xBet Live'
                )
            else:
                self.log("⏭️ 1xBet Live - DISABLED in config.json")

        # Check if at least one scraper started successfully
        any_scraper_started = (
            (self.enabled_scrapers.get('bet365', False) and (bet365_pregame_started or bet365_live_started)) or
            (self.enabled_scrapers.get('fanduel', False) and (fanduel_pregame_started or fanduel_live_started)) or
            (self.enabled_scrapers.get('1xbet', False) and (xbet_pregame_started or xbet_live_started))
        )
        
        if not any_scraper_started:
            self.log(" Failed to start any enabled scrapers")
            self.stop_all_scrapers()
            return
        
        self.log("")
        self.log(" Waiting 30 seconds for scrapers to initialize...")
        time.sleep(30)
        
        self.log("")
        self.log(" Starting real-time unified odds monitoring...")
        self.log("   Updates will happen instantly when any source file changes")
        self.log("")
        self.log("="*80)
        print()
        
        # Start real-time collector (using classes from this file)
        if not WATCHDOG_AVAILABLE:
            self.log(" watchdog not installed")
            self.log("   Install with: pip install watchdog")
            self.stop_all_scrapers()
            return
        
        try:
            collector = RealtimeUnifiedCollector()
            collector.initial_update()
            
            event_handler = OddsFileEventHandler(collector)
            observer = Observer()
            
            observer.schedule(event_handler, str(collector.base_dir / "bookmakers" / "bet365"), recursive=False)
            observer.schedule(event_handler, str(collector.base_dir / "bookmakers" / "fanduel"), recursive=False)
            observer.schedule(event_handler, str(collector.base_dir / "bookmakers" / "1xbet"), recursive=False)
            
            observer.start()
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.log("\n\n⏹  Stopping real-time mode...")
                observer.stop()
                collector.print_statistics()
                self.stop_all_scrapers()
                
                self.log("\n" + "="*80)
                self.log(" Real-time mode stopped")
                self.log("="*80)
            
            observer.join()
            
        except Exception as e:
            self.log(f" Error in real-time mode: {e}")
            self.stop_all_scrapers()


def main():
    parser = argparse.ArgumentParser(description='Unified Odds System Runner')
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous', 'realtime'],
        default='once',
        help='Run mode: once (collect then merge), continuous (periodic merges), or realtime (instant updates)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=120,
        help='Duration in seconds for one-time collection (default: 120)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Merge interval in seconds for continuous mode (default: 30)'
    )
    parser.add_argument(
        '--include-live',
        action='store_true',
        help='Include live match scrapers (default: pregame only)'
    )
    parser.add_argument(
        '--live-only',
        action='store_true',
        help='Run ONLY live match scrapers (no pregame data collection)'
    )
    parser.add_argument(
        '--alert-test',
        action='store_true',
        help='Send a test alert to verify email configuration'
    )

    args = parser.parse_args()

    # If --live-only is set, include_live should also be True
    include_live = args.include_live or args.live_only
    
    runner = UnifiedSystemRunner(include_live=include_live, live_only=args.live_only)
    runner.merge_interval = args.interval

    # Test alert system if requested
    if args.alert_test:
        print("Testing alert system...")
        # COMMENTED OUT: Reduced email notifications
        # runner.alert_system.send_alert(
        #     module_name="system_test",
        #     error_type="TEST_ALERT",
        #     message="This is a test alert to verify email configuration",
        #     details="Alert system test initiated by --alert-test flag"
        # )
        print("Test alert feature disabled. Email notifications are minimized.")
        return

    if args.mode == 'once':
        runner.run_one_time_collection(duration=args.duration)
    elif args.mode == 'continuous':
        runner.run_continuous_mode()
    else:  # realtime
        runner.run_realtime_mode()


if __name__ == "__main__":
    main()
