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
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    
    # Default behavior: run pregame only (as configured in unified system)
    has_pregame = True
    has_live = False
    
    # Override with command line args if provided
    if args.live_only:
        has_pregame = False
        has_live = True
    elif args.pregame_only:
        has_pregame = True
        has_live = False
    elif args.include_live:
        has_pregame = True
        has_live = True
    
    # base_dir should be project root, not core/
    base_dir = Path(__file__).parent.parent
    
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
        
        monitoring_script = base_dir / "core" / "monitoring_system.py"
        if monitoring_script.exists():
            try:
                # For debugging, don't detach the process so we can see output
                monitoring_process = subprocess.Popen(
                    [sys.executable, str(monitoring_script)],
                    cwd=str(base_dir)
                    # Removed creationflags to keep in same console for debugging
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
    
    if args.live_only or (has_live and not has_pregame):
        print("   - Mode: LIVE ONLY")
        print("   - Collecting LIVE data from all sources")
    elif args.pregame_only or (has_pregame and not has_live):
        print("   - Mode: PREGAME ONLY (Default)")
        print("   - Collecting PREGAME data from all sources")
    else:
        print("   - Mode: PREGAME + LIVE (ALL MODULES)")
        print("   - Collecting both PREGAME and LIVE data")
        print("   - Collecting LIVE data from enabled sources")
    print("   - Generating unified_odds.json with real-time updates")
    print()

    unified_script = base_dir / "core" / "run_unified_system.py"
    if not unified_script.exists():
        print(f"❌ Error: {unified_script} not found!")
        sys.exit(1)

    try:
        # Build command arguments
        cmd_args = [sys.executable, str(unified_script), "--mode", args.mode]

        if args.mode == 'once':
            cmd_args.extend(["--duration", str(args.duration)])

        if args.live_only or (has_live and not has_pregame):
            cmd_args.append("--live-only")
        elif args.pregame_only or (has_pregame and not has_live):
            # Don't add any flag - default is pregame only in run_unified_system.py
            pass
        else:
            # Run both pregame and live
            cmd_args.append("--include-live")

        print(f"   Running command: {' '.join(cmd_args)}")
        print()

        # Start unified system (for debugging, don't detach)
        print("Starting unified system (not detached for debugging)...")
        unified_process = subprocess.Popen(
            cmd_args,
            cwd=str(base_dir)
            # Removed creationflags to keep in same console for debugging
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
    
    # Start OddsMagnet Real-Time Collector
    print("⚽ Starting OddsMagnet Real-Time Collector...")
    print("   - Tracking ALL matches from top 10 football leagues")
    print("   - Update interval: 15 seconds")
    print("   - Output: bookmakers/oddsmagnet/oddsmagnet_realtime.json")
    print()
    
    # Top 10 football leagues
    top_10_leagues = [
        'england-premier-league',
        'spain-laliga',
        'italy-serie-a',
        'germany-bundesliga',
        'france-ligue-1',
        'champions-league',  # UEFA Champions League
        'europe-uefa-europa-league',  # UEFA Europa League
        'england-championship',
        'netherlands-eredivisie',
        'portugal-primeira-liga'
    ]
    
    oddsmagnet_script = base_dir / "bookmakers" / "oddsmagnet" / "oddsmagnet_top10_realtime.py"
    if oddsmagnet_script.exists():
        try:
            # Start OddsMagnet TOP 10 collector in background
            oddsmagnet_process = subprocess.Popen(
                [sys.executable, str(oddsmagnet_script)],
                cwd=str(base_dir / "bookmakers" / "oddsmagnet")
            )
            processes.append(oddsmagnet_process)
            print("✅ OddsMagnet TOP 10 collector started (PID: {})".format(oddsmagnet_process.pid))
            print()
            
            # Give it a moment to initialize
            time.sleep(3)
            
        except Exception as e:
            print(f"⚠️  Could not start OddsMagnet collector: {e}")
            print("   Continuing without OddsMagnet...")
            print()
    else:
        print("⚠️  oddsmagnet_top10_realtime.py not found, skipping OddsMagnet")
        print()
    
    # Start the web viewer
    print("🌐 Starting Web Viewer UI...")
    print("   - Real-time monitoring dashboard")
    print("   - System health monitoring")
    print("   - Email alerts configured")
    print()
    
    viewer_script = base_dir / "core" / "live_odds_viewer_clean.py"
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
        if args.live_only or (has_live and not has_pregame):
            print("   2. Unified Odds Collector - LIVE ONLY fetching from enabled sources")
        elif args.pregame_only or (has_pregame and not has_live):
            print("   2. Unified Odds Collector - PREGAME ONLY fetching from enabled sources")
        else:
            print("   2. Unified Odds Collector - ALL MODULES (LIVE + PREGAME)")
        print("   3. OddsMagnet Real-Time Collector - Top 10 leagues, ALL matches, 15s updates")
        print("   4. Web Viewer - Real-time dashboard with monitoring")
    else:
        if args.live_only:
            print("   1. Unified Odds Collector - LIVE ONLY fetching from all sources")
        elif args.pregame_only:
            print("   1. Unified Odds Collector - PREGAME ONLY fetching from all sources")
        else:
            print("   1. Unified Odds Collector - ALL MODULES (LIVE + PREGAME)")
        print("   2. OddsMagnet Real-Time Collector - Top 10 leagues, ALL matches, 15s updates")
        print("   3. Web Viewer - Real-time dashboard")
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
    print("   • OddsMagnet: 117+ leagues, 9 bookmakers, 69 markets per match")
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
                    monitoring_script = base_dir / "core" / "monitoring_system.py"
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
            
            # Check OddsMagnet collector (if running)
            oddsmagnet_idx = 2 if not args.no_monitoring else 1
            if len(processes) > oddsmagnet_idx + 1:  # Has OddsMagnet + viewer
                oddsmagnet_status = processes[oddsmagnet_idx].poll()
                if oddsmagnet_status is not None:
                    print(f"\n⚠️  OddsMagnet collector exited with code {oddsmagnet_status}")
                    print("🔄 Restarting OddsMagnet collector...")
                    oddsmagnet_script = base_dir / "bookmakers" / "oddsmagnet" / "oddsmagnet_top10_realtime.py"
                    if oddsmagnet_script.exists():
                        oddsmagnet_process = subprocess.Popen(
                            [sys.executable, str(oddsmagnet_script)],
                            cwd=str(base_dir / "bookmakers" / "oddsmagnet")
                        )
                        processes[oddsmagnet_idx] = oddsmagnet_process
                        print(f"✅ OddsMagnet collector restarted (PID: {oddsmagnet_process.pid})")
            
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
