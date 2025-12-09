@echo off
REM Bet365 Scraper Test Runner for Windows
REM Quick way to test scrapers on local PC

echo ================================================
echo Bet365 Scraper Local PC Test Runner
echo ================================================
echo.

if "%1"=="" (
    echo Usage: test_scraper.bat ^<sport^>
    echo.
    echo Available sports:
    echo   - nba
    echo   - nfl
    echo   - nhl
    echo   - ncaab
    echo   - ncaaf
    echo   - soccer
    echo.
    echo Example: test_scraper.bat nba
    echo.
    pause
    exit /b 1
)

echo Testing %1 scraper...
echo.

python test_scraper_local.py %1

echo.
echo ================================================
echo Test Complete
echo ================================================
pause
