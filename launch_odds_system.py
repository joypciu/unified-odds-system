#!/usr/bin/env python3
"""
Master Launcher for Complete Odds System
Runs both the unified odds collection system and the web viewer UI
"""

import subprocess
import sys
import time
import signal
import os
import argparse
import psutil
import atexit
from pathlib import Path

# Track processes
processes = []
shutdown_in_progress = False

def kill_process_tree(pid):
    """Kill a process and all its children"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Kill children first
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        
        # Kill parent
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            pass
            
        # Wait for processes to terminate
        gone, alive = psutil.wait_procs(children + [parent], timeout=3)
        
        # Force kill any remaining processes
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
                
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        print(f"   Warning: Error killing process {pid}: {e}")

def cleanup_processes():
    """Cleanup function called on exit"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        return
    
    shutdown_in_progress = True
    
    # Kill all tracked processes and their children
    for proc in processes:
        try:
            if proc.poll() is None:  # Process still running
                kill_process_tree(proc.pid)
        except Exception:
            pass

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        return
    
    print("\n\n🛑 Shutting down all processes...")
    print("   This may take a few seconds...")
    
    cleanup_processes()
    
    print("✅ All processes stopped")
    sys.exit(0)

# Register signal handler and exit handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_processes)

def main():
    parser = argparse.ArgumentParser(description='Launch unified odds collection and viewing system')
    parser.add_argument('--live-only', action='store_true',
                       help='Run ONLY live match scrapers (no pregame data collection)')
    parser.add_argument('--include-live', action='store_true',
                       help='Include live match scrapers (default: pregame + live)')
    parser.add_argument('--pregame-only', action='store_true',
                       help='Run ONLY pregame scrapers (no live data collection)')
    parser.add_argument('--mode', choices=['once', 'continuous', 'realtime'],
                       default='realtime',
                       help='Collection mode (default: realtime)')
    parser.add_argument('--duration', type=int, default=120,
                       help='Duration in seconds for one-time collection (default: 120)')
    parser.add_argument('--no-monitoring', action='store_true',
                       help='Disable automated monitoring system')
    args = parser.parse_args()
    
    # Default behavior: run both pregame and live
    if not args.live_only and not args.pregame_only:
        args.include_live = True
    
    base_dir = Path(__file__).parent
    
    print("=" * 80)
    print("⚡ UNIFIED ODDS COLLECTION & VIEWING SYSTEM")
    print("=" * 80)
    print()
    
    # Start the monitoring system first (unless disabled)
    if not args.no_monitoring:
        print("🔍 Starting Automated Monitoring System...")
        print("   - Module health checks every 5 minutes")
        print("   - Cache auto-update every 30 minutes")
        print("   - Email alerts on failures")
        print()
        
        monitoring_script = base_dir / "monitoring_system.py"
        if monitoring_script.exists():
            try:
                monitoring_process = subprocess.Popen(
                    [sys.executable, str(monitoring_script)],
                    cwd=str(base_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
                processes.append(monitoring_process)
                print("✅ Monitoring system started (PID: {})".format(monitoring_process.pid))
                print("   Check the new console window for monitoring logs")
                print()
                time.sleep(2)
            except Exception as e:
                print(f"⚠️  Could not start monitoring system: {e}")
                print("   Continuing without monitoring...")
                print()
        else:
            print("⚠️  monitoring_system.py not found, skipping monitoring")
            print()
    
    # Start the unified odds collection system
    print("🔄 Starting Unified Odds Collection System...")
    if args.live_only:
        print("   - Mode: LIVE ONLY")
        print("   - Collecting LIVE data from Bet365, FanDuel, and 1xBet")
    elif args.pregame_only:
        print("   - Mode: PREGAME ONLY")
        print("   - Collecting PREGAME data from Bet365, FanDuel, and 1xBet")
    else:
        print("   - Mode: PREGAME + LIVE (ALL MODULES)")
        print("   - Collecting PREGAME data from Bet365, FanDuel, and 1xBet")
        print("   - Collecting LIVE data from all sources")
    print("   - Generating unified_odds.json with real-time updates")
    print()

    unified_script = base_dir / "run_unified_system.py"
    if not unified_script.exists():
        print(f"❌ Error: {unified_script} not found!")
        sys.exit(1)

    try:
        # Build command arguments
        cmd_args = [sys.executable, str(unified_script), "--mode", args.mode]

        if args.mode == 'once':
            cmd_args.extend(["--duration", str(args.duration)])

        if args.live_only:
            cmd_args.append("--live-only")
        elif args.pregame_only:
            # Don't add any flag - default is pregame only in run_unified_system.py
            pass
        else:
            # Run both pregame and live
            cmd_args.append("--include-live")

        print(f"   Running command: {' '.join(cmd_args)}")
        print()

        # Start unified system in background
        # Don't capture stdout/stderr - let it run in its own console window
        unified_process = subprocess.Popen(
            cmd_args,
            cwd=str(base_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )
        processes.append(unified_process)
        print("✅ Unified collection system started (PID: {})".format(unified_process.pid))
        print("   Check the new console window for backend logs")
        print()
        
        # Give it a moment to initialize
        time.sleep(5)
        
    except Exception as e:
        print(f"❌ Error starting unified system: {e}")
        sys.exit(1)
    
    # Start the web viewer
    print("🌐 Starting Web Viewer UI...")
    print("   - Real-time monitoring dashboard")
    print("   - System health monitoring")
    print("   - Email alerts configured")
    print()
    
    viewer_script = base_dir / "live_odds_viewer_clean.py"
    if not viewer_script.exists():
        print(f"❌ Error: {viewer_script} not found!")
        unified_process.terminate()
        sys.exit(1)
    
    try:
        # Start web viewer
        viewer_process = subprocess.Popen(
            [sys.executable, str(viewer_script)],
            cwd=str(base_dir)
        )
        processes.append(viewer_process)
        print("✅ Web viewer started (PID: {})".format(viewer_process.pid))
        print()
        
    except Exception as e:
        print(f"❌ Error starting web viewer: {e}")
        unified_process.terminate()
        sys.exit(1)
    
    print("=" * 80)
    print("🚀 SYSTEM IS NOW RUNNING")
    print("=" * 80)
    print()
    print("📊 Web Dashboard: http://localhost:8000")
    print()
    print("🔍 What's Running:")
    if not args.no_monitoring:
        print("   1. Monitoring System - Health checks & email alerts")
        if args.live_only:
            print("   2. Unified Odds Collector - LIVE ONLY fetching from all sources")
        elif args.pregame_only:
            print("   2. Unified Odds Collector - PREGAME ONLY fetching from all sources")
        else:
            print("   2. Unified Odds Collector - ALL MODULES (LIVE + PREGAME)")
        print("   3. Web Viewer - Real-time dashboard with monitoring")
    else:
        if args.live_only:
            print("   1. Unified Odds Collector - LIVE ONLY fetching from all sources")
        elif args.pregame_only:
            print("   1. Unified Odds Collector - PREGAME ONLY fetching from all sources")
        else:
            print("   1. Unified Odds Collector - ALL MODULES (LIVE + PREGAME)")
        print("   2. Web Viewer - Real-time dashboard")
    print()
    print("💡 Features Available:")
    if not args.no_monitoring:
        print("   • Automated health monitoring (every 5 min)")
        print("   • Cache auto-updates (every 30 min)")
        print("   • Email alerts on failures")
    if args.live_only:
        print("   • Real-time LIVE odds updates (scraped continuously)")
    elif args.pregame_only:
        print("   • Real-time PREGAME odds updates (scraped continuously)")
    else:
        print("   • Real-time PREGAME odds updates (scraped continuously)")
        print("   • Real-time LIVE odds updates (scraped continuously)")
    print("   • Advanced filtering and search")
    print("   • Pagination for large datasets")
    print("   • System health monitoring dashboard")
    print()
    print("🛑 Press Ctrl+C to stop all services")
    print("=" * 80)
    print()
    
    # Monitor processes
    try:
        while True:
            # Check monitoring system if enabled
            if not args.no_monitoring and len(processes) >= 3:
                monitoring_status = processes[0].poll()
                if monitoring_status is not None:
                    print(f"\n⚠️  Monitoring system exited with code {monitoring_status}")
                    print("🔄 Restarting monitoring system...")
                    monitoring_script = base_dir / "monitoring_system.py"
                    monitoring_process = subprocess.Popen(
                        [sys.executable, str(monitoring_script)],
                        cwd=str(base_dir),
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                    )
                    processes[0] = monitoring_process
                    print(f"✅ Monitoring system restarted (PID: {monitoring_process.pid})")
            
            # Check unified system (index depends on whether monitoring is enabled)
            unified_idx = 1 if not args.no_monitoring else 0
            if len(processes) > unified_idx:
                unified_status = processes[unified_idx].poll()
                if unified_status is not None:
                    print(f"\n⚠️  Unified system exited with code {unified_status}")
                    if args.live_only:
                        print(f"🔄 Restarting unified system with --mode {args.mode} --live-only...")
                    elif args.pregame_only:
                        print(f"🔄 Restarting unified system with --mode {args.mode} (pregame only)...")
                    else:
                        print(f"🔄 Restarting unified system with --mode {args.mode} --include-live...")

                    # Build command arguments
                    cmd_args = [sys.executable, str(unified_script), "--mode", args.mode]

                    if args.mode == 'once':
                        cmd_args.extend(["--duration", str(args.duration)])

                    if args.live_only:
                        cmd_args.append("--live-only")
                    elif args.pregame_only:
                        pass  # Default is pregame only
                    else:
                        cmd_args.append("--include-live")

                    unified_process = subprocess.Popen(
                        cmd_args,
                        cwd=str(base_dir),
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                    )
                    processes[unified_idx] = unified_process
                    print(f"✅ Unified system restarted (PID: {unified_process.pid})")
            
            # Check viewer (last process)
            viewer_idx = len(processes) - 1
            if len(processes) > viewer_idx:
                viewer_status = processes[viewer_idx].poll()
                if viewer_status is not None:
                    print(f"\n⚠️  Web viewer exited with code {viewer_status}")
                    print("🔄 Restarting web viewer...")
                    viewer_process = subprocess.Popen(
                        [sys.executable, str(viewer_script)],
                        cwd=str(base_dir)
                    )
                    processes[viewer_idx] = viewer_process
                    print(f"✅ Web viewer restarted (PID: {viewer_process.pid})")
            
            time.sleep(10)  # Check every 10 seconds
            
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
