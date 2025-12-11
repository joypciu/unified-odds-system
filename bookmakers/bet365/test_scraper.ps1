# Bet365 Scraper Test Runner for Windows (PowerShell)
# Quick way to test scrapers on local PC

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('nba', 'nfl', 'nhl', 'ncaab', 'ncaaf', 'soccer')]
    [string]$Sport
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Bet365 Scraper Local PC Test Runner" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

if (-not $Sport) {
    Write-Host "Usage: .\test_scraper.ps1 <sport>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available sports:" -ForegroundColor Green
    Write-Host "  - nba" -ForegroundColor White
    Write-Host "  - nfl" -ForegroundColor White
    Write-Host "  - nhl" -ForegroundColor White
    Write-Host "  - ncaab" -ForegroundColor White
    Write-Host "  - ncaaf" -ForegroundColor White
    Write-Host "  - soccer" -ForegroundColor White
    Write-Host ""
    Write-Host "Example: .\test_scraper.ps1 nba" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "Testing $Sport scraper..." -ForegroundColor Green
Write-Host ""

python test_scraper_local.py $Sport

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
