#!/bin/bash
# VPS Diagnostic Script
# Run this on the VPS to check system status

echo "============================================="
echo "UNIFIED ODDS SYSTEM - VPS DIAGNOSTICS"
echo "============================================="
echo ""

echo "1. Service Status:"
echo "-------------------"
sudo systemctl status unified-odds --no-pager
echo ""

echo "2. Recent Logs (Last 50 lines):"
echo "--------------------------------"
sudo journalctl -u unified-odds -n 50 --no-pager
echo ""

echo "3. Running Processes:"
echo "---------------------"
ps aux | grep python | grep -v grep
echo ""

echo "4. Port 8000 Status:"
echo "--------------------"
sudo lsof -i :8000 || echo "Port 8000 not in use"
echo ""

echo "5. Data Files:"
echo "--------------"
echo "1xBet files:"
ls -lh /home/ubuntu/services/unified-odds/bookmakers/1xbet/*.json 2>/dev/null || echo "  No 1xbet JSON files"
echo ""
echo "Data folder files:"
ls -lh /home/ubuntu/services/unified-odds/data/*.json 2>/dev/null || echo "  No data JSON files"
echo ""
echo "OddsMagnet files:"
ls -lh /home/ubuntu/services/unified-odds/bookmakers/oddsmagnet/*.json 2>/dev/null || echo "  No oddsmagnet JSON files"
echo ""

echo "6. Disk Space:"
echo "--------------"
df -h /home/ubuntu/services/unified-odds
echo ""

echo "7. Python Environment:"
echo "----------------------"
cd /home/ubuntu/services/unified-odds
source venv/bin/activate
python --version
pip list | grep -E "(fastapi|uvicorn|selenium|patchright)" || echo "Missing key packages"
echo ""

echo "8. Chrome/Chromium:"
echo "-------------------"
which google-chrome || which chromium-browser || echo "Chrome/Chromium not found"
google-chrome --version 2>/dev/null || chromium-browser --version 2>/dev/null || echo "Cannot determine Chrome version"
echo ""

echo "9. Config File:"
echo "---------------"
if [ -f "/home/ubuntu/services/unified-odds/config/config.json" ]; then
    echo "Config file exists"
    # Show enabled scrapers (redact sensitive info)
    cat /home/ubuntu/services/unified-odds/config/config.json | grep -A 5 "enabled_scrapers" || echo "Cannot read scrapers config"
else
    echo "Config file NOT found at /home/ubuntu/services/unified-odds/config/config.json"
fi
echo ""

echo "10. Recent File Changes:"
echo "------------------------"
echo "Last modified files in bookmakers/:"
find /home/ubuntu/services/unified-odds/bookmakers -name "*.json" -mmin -60 -ls 2>/dev/null || echo "No recent JSON files in bookmakers/"
echo ""

echo "============================================="
echo "DIAGNOSTICS COMPLETE"
echo "============================================="
