#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy 1xBet-only configuration to VPS for testing UI functionality
    
.DESCRIPTION
    This script uploads the modified run_unified_system.py (with Bet365/FanDuel disabled)
    and updated service files to the VPS, then restarts the services.
    
    Testing configuration:
    - Only 1xBet pregame and live scrapers enabled
    - Bet365 and FanDuel temporarily disabled
    - Purpose: Verify UI displays 1xBet data correctly
#>

# VPS connection details
$VPS_HOST = "142.44.160.36"
$VPS_USER = "ubuntu"
$VPS_PATH = "/home/ubuntu/services/unified-odds"
$VPS_KEY = "vps_ssh_key.txt"

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "  DEPLOYING 1xBET-ONLY CONFIGURATION TO VPS" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host ""

# Check if SSH key exists
if (-not (Test-Path $VPS_KEY)) {
    Write-Host "[ERROR] SSH key not found: $VPS_KEY" -ForegroundColor Red
    Write-Host "        Please ensure vps_ssh_key.txt exists in the current directory" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Uploading modified run_unified_system.py..." -ForegroundColor Cyan
scp -i $VPS_KEY run_unified_system.py "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [FAILED] Could not upload run_unified_system.py" -ForegroundColor Red
    exit 1
}
Write-Host "      [OK] run_unified_system.py uploaded" -ForegroundColor Green

Write-Host ""
Write-Host "[2/5] Uploading updated service file..." -ForegroundColor Cyan
scp -i $VPS_KEY unified-odds.service "${VPS_USER}@${VPS_HOST}:/tmp/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [FAILED] Could not upload service file" -ForegroundColor Red
    exit 1
}
Write-Host "      [OK] unified-odds.service uploaded to /tmp/" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] Installing service file..." -ForegroundColor Cyan
ssh -i $VPS_KEY "${VPS_USER}@${VPS_HOST}" @"
    sudo cp /tmp/unified-odds.service /etc/systemd/system/
    sudo systemctl daemon-reload
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [FAILED] Could not install service file" -ForegroundColor Red
    exit 1
}
Write-Host "      [OK] Service file installed and systemd reloaded" -ForegroundColor Green

Write-Host ""
Write-Host "[4/5] Restarting unified-odds service..." -ForegroundColor Cyan
ssh -i $VPS_KEY "${VPS_USER}@${VPS_HOST}" @"
    sudo systemctl restart unified-odds
    sleep 3
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "      [FAILED] Could not restart service" -ForegroundColor Red
    exit 1
}
Write-Host "      [OK] Service restarted" -ForegroundColor Green

Write-Host ""
Write-Host "[5/5] Checking service status..." -ForegroundColor Cyan
Write-Host ""
ssh -i $VPS_KEY "${VPS_USER}@${VPS_HOST}" @"
    echo "Service Status:"
    sudo systemctl status unified-odds --no-pager -l | head -15
    echo ""
    echo "Recent Logs (last 30 lines):"
    sudo journalctl -u unified-odds --since '1 minute ago' --no-pager | tail -30
    echo ""
    echo "Active Processes:"
    ps aux | grep -E 'python.*1xbet' | grep -v grep
"@

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  - Only 1xBet pregame and live scrapers enabled" -ForegroundColor White
Write-Host "  - Bet365 and FanDuel disabled for testing" -ForegroundColor White
Write-Host "  - Service running in pregame + live mode" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Wait 2-3 minutes for 1xBet to collect data" -ForegroundColor White
Write-Host "  2. Check UI at: http://142.44.160.36:8000" -ForegroundColor Cyan
Write-Host "  3. Monitor logs with:" -ForegroundColor White
Write-Host "     ssh -i $VPS_KEY ubuntu@142.44.160.36" -ForegroundColor Gray
Write-Host "     sudo journalctl -u unified-odds -f" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Check data files:" -ForegroundColor White
Write-Host "     cd /home/ubuntu/services/unified-odds/1xbet" -ForegroundColor Gray
Write-Host "     ls -lh 1xbet_pregame.json 1xbet_live.json" -ForegroundColor Gray
Write-Host ""
