#!/bin/bash
# Fix Basketball API Timeout Issue
# This script applies the basketball endpoint timeout fix on the VPS

set -e  # Exit on error

echo "=============================================="
echo "Basketball API Timeout Fix - Deployment"
echo "=============================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📂 Project root: $PROJECT_ROOT"
echo ""

# Step 1: Check if aiofiles is installed
echo "1️⃣  Checking Python dependencies..."
if ! python3 -c "import aiofiles" 2>/dev/null; then
    echo "   ⚠️  aiofiles not found, installing..."
    pip3 install aiofiles
    echo "   ✅ aiofiles installed"
else
    echo "   ✅ aiofiles already installed"
fi
echo ""

# Step 2: Check if basketball collector script exists
echo "2️⃣  Verifying basketball collector..."
BASKETBALL_SCRIPT="$PROJECT_ROOT/bookmakers/oddsmagnet/oddsmagnet_basketball_realtime.py"
if [ -f "$BASKETBALL_SCRIPT" ]; then
    echo "   ✅ Basketball collector script found"
else
    echo "   ❌ Basketball collector script not found at: $BASKETBALL_SCRIPT"
    echo "   This is required for basketball data!"
    exit 1
fi
echo ""

# Step 3: Check if live_odds_viewer_clean.py has the fix
echo "3️⃣  Verifying timeout fix in live_odds_viewer_clean.py..."
VIEWER_SCRIPT="$PROJECT_ROOT/core/live_odds_viewer_clean.py"
if grep -q "asyncio.timeout\|asyncio.wait_for" "$VIEWER_SCRIPT"; then
    echo "   ✅ Timeout handling found in viewer"
else
    echo "   ❌ Timeout fix not found - please pull latest changes"
    exit 1
fi
echo ""

# Step 4: Restart services
echo "4️⃣  Restarting services..."

# Check if running under systemd
if systemctl is-active --quiet live-odds-viewer.service 2>/dev/null; then
    echo "   🔄 Restarting live-odds-viewer service..."
    sudo systemctl restart live-odds-viewer.service
    sleep 2
    
    if systemctl is-active --quiet live-odds-viewer.service; then
        echo "   ✅ live-odds-viewer service restarted successfully"
    else
        echo "   ❌ live-odds-viewer service failed to start"
        sudo systemctl status live-odds-viewer.service --no-pager
        exit 1
    fi
else
    echo "   ⚠️  live-odds-viewer service not found"
    echo "   You may need to start it manually or check unified-odds.service"
fi
echo ""

# Step 5: Check if basketball collector is running
echo "5️⃣  Checking basketball collector status..."
if pgrep -f "oddsmagnet_basketball_realtime.py" > /dev/null; then
    echo "   ✅ Basketball collector is running"
    echo "   Process ID: $(pgrep -f 'oddsmagnet_basketball_realtime.py')"
else
    echo "   ⚠️  Basketball collector is NOT running"
    echo "   Starting unified-odds service (which includes basketball collector)..."
    
    if systemctl is-active --quiet unified-odds.service 2>/dev/null; then
        sudo systemctl restart unified-odds.service
        echo "   ✅ Restarted unified-odds service"
    else
        echo "   ⚠️  unified-odds service not found - basketball collector may need manual start"
    fi
fi
echo ""

# Step 6: Wait for services to initialize
echo "6️⃣  Waiting for services to initialize (10 seconds)..."
sleep 10
echo ""

# Step 7: Test the endpoint
echo "7️⃣  Testing basketball API endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/oddsmagnet/api/basketball 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Endpoint responding with 200 OK - basketball data available!"
elif [ "$HTTP_CODE" = "503" ]; then
    echo "   ⚠️  Endpoint responding with 503 - basketball collector not running yet"
    echo "   This is normal on first start. Wait 60 seconds for first data collection."
elif [ "$HTTP_CODE" = "504" ]; then
    echo "   ⚠️  Endpoint responding with 504 - timeout (better than browser timeout!)"
    echo "   File is being generated. Try again in a moment."
elif [ "$HTTP_CODE" = "000" ]; then
    echo "   ❌ Cannot connect to endpoint - is the web viewer running?"
    echo "   Check: sudo systemctl status live-odds-viewer.service"
else
    echo "   ⚠️  Endpoint responding with HTTP $HTTP_CODE"
fi
echo ""

# Step 8: Display useful commands
echo "=============================================="
echo "✅ Fix deployment complete!"
echo "=============================================="
echo ""
echo "📋 Useful commands:"
echo "  • Check web viewer logs:    sudo journalctl -u live-odds-viewer.service -f"
echo "  • Check basketball collector: ps aux | grep basketball_realtime"
echo "  • Test endpoint:            curl http://localhost:8000/oddsmagnet/api/basketball"
echo "  • View basketball data file: cat bookmakers/oddsmagnet/oddsmagnet_basketball.json | jq '.matches | length'"
echo ""
echo "🌐 Test URLs:"
echo "  • http://142.44.160.36:8000/oddsmagnet/api/basketball"
echo "  • http://142.44.160.36:8000/health"
echo ""
