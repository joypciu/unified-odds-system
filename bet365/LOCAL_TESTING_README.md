# Local PC Testing for VPS Scrapers

Test your bet365 sport scrapers on Windows before deploying to VPS.

## Quick Start

### Method 1: PowerShell (Recommended)

```powershell
cd bet365
.\test_scraper.ps1 nba
```

### Method 2: Command Prompt

```cmd
cd bet365
test_scraper.bat nba
```

### Method 3: Direct Python

```powershell
cd bet365
python test_scraper_local.py nba
```

## Available Sports

- `nba` - NBA games with futures
- `nfl` - NFL games with futures
- `nhl` - NHL games with futures
- `ncaab` - NCAA Basketball with futures
- `ncaaf` - NCAA Football with futures
- `soccer` - Soccer multi-region

## What Happens

1. **Chrome Opens**: A visible Chrome window opens automatically
2. **Navigation**: The scraper navigates to bet365 markets
3. **CAPTCHA**: If CAPTCHA appears, solve it manually
4. **Data Collection**: Scraper collects data from multiple markets
5. **Output**: Data saved to timestamped directory (e.g., `nba_data_20251209_123456/`)

## Output Files

Each test creates a directory with:

- `captured_data.json` - Raw network responses
- `parsed_nba_data.json` - Parsed game/prop data
- `nba_optic_odds_format.json` - OpticOdds format
- `nba_eternity_format.json` - Eternity format
- `nba_futures.json` - Futures data
- `summary.json` - Collection statistics

## Validation

✅ **If test succeeds on local PC:**

- VPS version will work with `xvfb-run`
- Deploy with confidence!

❌ **If test fails:**

- Fix issues on local PC first
- Check Chrome version
- Verify bet365 is accessible
- Check for CAPTCHA blocking

## VPS Deployment

After successful local test, deploy to VPS:

```bash
# On VPS
cd bet365
xvfb-run -a python nba__with_future.py
```

## Troubleshooting

### Chrome doesn't open

- Ensure Chrome is installed
- Check PATH environment variable

### CAPTCHA blocks scraper

- Solve CAPTCHA manually in the Chrome window
- Scraper will continue after solving

### No data collected

- Check bet365 is accessible
- Verify markets are available
- Check logs for errors

### Import errors

- Ensure all dependencies installed: `pip install patchright`
- Run from bet365 directory
- Check all required files are present

## File Structure

```
bet365/
├── test_scraper_local.py       # Test runner script
├── test_scraper.bat            # Windows batch file
├── test_scraper.ps1            # PowerShell script
├── chrome_helper.py            # Cross-platform Chrome manager
├── nba__with_future.py         # NBA scraper (VPS version)
├── nfl__with_future.py         # NFL scraper (VPS version)
├── nhl__with_future.py         # NHL scraper (VPS version)
├── ncaab__with_future.py       # NCAAB scraper (VPS version)
├── ncaaf__with_future.py       # NCAAF scraper (VPS version)
└── soccer__multi_region.py     # Soccer scraper (VPS version)
```

## Notes

- ✅ Works on Windows 10/11
- ✅ Chrome must be visible (not headless)
- ✅ Manual CAPTCHA solving supported
- ✅ Same code runs on VPS with xvfb-run
- ⚠️ Requires Chrome/Chromium installed
- ⚠️ Requires patchright: `pip install patchright`
