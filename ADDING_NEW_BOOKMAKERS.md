# Adding New Bookmakers - Quick Guide

This guide explains how to add new bookmaker scrapers to the unified odds system for maximum flexibility and scalability.

## 📁 Folder Structure

```
unified-odds-system/
├── bet365/              ← Existing bookmaker
├── fanduel/             ← Existing bookmaker
├── 1xbet/               ← Existing bookmaker
├── oddsmagnet/          ← Existing bookmaker (NEW!)
└── your_new_bookmaker/  ← Add new bookmakers here
```

## 🚀 Quick Steps to Add a New Bookmaker

### Step 1: Create Bookmaker Folder

```bash
mkdir your_new_bookmaker
```

### Step 2: Create Your Scraper

Create your scraper file in the new folder:

```python
# your_new_bookmaker/scraper.py
import json
from datetime import datetime

class YourBookmakerScraper:
    def __init__(self):
        self.output_file = 'your_bookmaker_realtime.json'

    def collect_odds(self):
        """Main collection method"""
        # Your scraping logic here
        data = {
            'timestamp': datetime.now().isoformat(),
            'matches': []  # Your match data
        }

        # Save to JSON
        with open(self.output_file, 'w') as f:
            json.dump(data, f, indent=2)

        return data

def main():
    scraper = YourBookmakerScraper()
    scraper.collect_odds()

if __name__ == "__main__":
    main()
```

### Step 3: Add to Launch System

Edit `launch_odds_system.py` and add your bookmaker after the OddsMagnet section:

```python
# Add after OddsMagnet collector section (around line 240)

# Start Your Bookmaker Collector
print("🎯 Starting Your Bookmaker Collector...")
print("   - Your specific configuration")
print()

your_bookmaker_script = base_dir / "your_new_bookmaker" / "scraper.py"
if your_bookmaker_script.exists():
    try:
        your_bookmaker_process = subprocess.Popen(
            [sys.executable, str(your_bookmaker_script)],
            cwd=str(base_dir / "your_new_bookmaker")
        )
        processes.append(your_bookmaker_process)
        print("✅ Your Bookmaker collector started (PID: {})".format(your_bookmaker_process.pid))
        print()
        time.sleep(2)
    except Exception as e:
        print(f"⚠️  Could not start Your Bookmaker: {e}")
        print("   Continuing without Your Bookmaker...")
        print()
else:
    print("⚠️  Your Bookmaker script not found, skipping")
    print()
```

### Step 4: Add Auto-Restart Support

In the monitoring loop (around line 320), add restart logic:

```python
# Check Your Bookmaker collector (if running)
your_bookmaker_idx = 3 if not args.no_monitoring else 2
if len(processes) > your_bookmaker_idx + 1:
    status = processes[your_bookmaker_idx].poll()
    if status is not None:
        print(f"\n⚠️  Your Bookmaker exited with code {status}")
        print("🔄 Restarting Your Bookmaker...")
        script = base_dir / "your_new_bookmaker" / "scraper.py"
        if script.exists():
            proc = subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(base_dir / "your_new_bookmaker")
            )
            processes[your_bookmaker_idx] = proc
            print(f"✅ Your Bookmaker restarted (PID: {proc.pid})")
```

### Step 5: Add FastAPI Endpoints

Edit `live_odds_viewer_clean.py` to add API endpoints:

```python
@app.get("/your_bookmaker/data")
async def get_your_bookmaker_data():
    """Get Your Bookmaker data"""
    try:
        data_file = BASE_DIR / "your_new_bookmaker" / "your_bookmaker_realtime.json"
        if not data_file.exists():
            return {'error': 'Data not available', 'matches': []}

        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return {
            'source': 'your_bookmaker',
            'timestamp': data.get('timestamp'),
            'total_matches': len(data.get('matches', [])),
            'matches': data.get('matches', [])
        }
    except Exception as e:
        return {'error': str(e), 'matches': []}
```

### Step 6: Update Display Messages

Update the "What's Running" section in `launch_odds_system.py`:

```python
print("   3. OddsMagnet Real-Time Collector - 117+ leagues, 1s updates")
print("   4. Your Bookmaker Collector - Your description here")  # ADD THIS
print("   5. Web Viewer - Real-time dashboard with monitoring")
```

## 📊 Current System Architecture

```
launch_odds_system.py (Master Controller)
├── monitoring_system.py (Health checks)
├── run_unified_system.py (bet365, fanduel, 1xbet)
├── oddsmagnet/oddsmagnet_realtime_collector.py (OddsMagnet)
├── your_new_bookmaker/scraper.py (Your new scraper)
└── live_odds_viewer_clean.py (FastAPI server)
```

## ✅ Deployment

Once you push to GitHub:

1. GitHub Actions auto-deploys to VPS
2. VPS pulls latest code
3. Systemd service restarts
4. `launch_odds_system.py` starts all scrapers including your new one
5. Auto-restart monitors keep everything running

## 🎯 Benefits of This Architecture

- ✅ **Modular**: Each bookmaker in its own folder
- ✅ **Auto-restart**: Crashed scrapers automatically restart
- ✅ **Single service**: One systemd service manages everything
- ✅ **Scalable**: Add unlimited bookmakers without changing core system
- ✅ **Independent**: Each scraper can fail without affecting others
- ✅ **Easy deployment**: Just push to GitHub, auto-deploys to VPS

## 📝 Example: OddsMagnet Integration

See the `oddsmagnet/` folder for a complete working example:

- `oddsmagnet_realtime_collector.py` - Main scraper
- `oddsmagnet_optimized_scraper.py` - Core scraping logic
- `oddsmagnet_optimized_collector.py` - Bulk collection
- `README_ODDSMAGNET.md` - Documentation

API endpoints:

- `http://142.44.160.36:8000/oddsmagnet/football` (all leagues)
- `http://142.44.160.36:8000/oddsmagnet/football/top10` (top 10 only)

## 🔧 Testing Locally

```bash
# Test your scraper alone
cd your_new_bookmaker
python scraper.py

# Test with full system
python launch_odds_system.py --include-live
```

## 📚 Reference Files

- `launch_odds_system.py` - Main launcher (lines 150-240 for new scrapers)
- `live_odds_viewer_clean.py` - FastAPI endpoints (lines 975-1050 for examples)
- `oddsmagnet/oddsmagnet_realtime_collector.py` - Complete scraper example
