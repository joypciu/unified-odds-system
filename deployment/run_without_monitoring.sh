#!/bin/bash
# Wrapper to run unified system without monitoring thread
# This avoids the threading.Thread UnboundLocalError in Python 3.13

cd /home/ubuntu/services/unified-odds
source venv/bin/activate

# Run with --pregame-only to avoid live scrapers for now
exec python3 core/run_unified_system.py --mode continuous --pregame-only 2>&1
