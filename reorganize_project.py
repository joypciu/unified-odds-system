#!/usr/bin/env python3
"""
Project Reorganization Script
Moves files to new organized structure automatically
"""

import os
import shutil
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

print("=" * 80)
print("PROJECT REORGANIZATION SCRIPT")
print("=" * 80)
print()

# File movements mapping
MOVEMENTS = {
    # Bookmakers folder
    'bookmakers': [
        ('bet365', 'bookmakers/bet365'),
        ('fanduel', 'bookmakers/fanduel'),
        ('1xbet', 'bookmakers/1xbet'),
        ('oddsmagnet', 'bookmakers/oddsmagnet'),
    ],
    
    # Core folder
    'core': [
        ('launch_odds_system.py', 'core/launch_odds_system.py'),
        ('run_unified_system.py', 'core/run_unified_system.py'),
        ('live_odds_viewer_clean.py', 'core/live_odds_viewer_clean.py'),
        ('unified_odds_collector.py', 'core/unified_odds_collector.py'),
        ('monitoring_system.py', 'core/monitoring_system.py'),
        ('monitoring_status_api.py', 'core/monitoring_status_api.py'),
        ('run_futures_collection.py', 'core/run_futures_collection.py'),
    ],
    
    # Utils folder
    'utils': [
        # Cache managers
        ('enhanced_cache_manager.py', 'utils/cache_manager/enhanced_cache_manager.py'),
        ('dynamic_cache_manager.py', 'utils/cache_manager/dynamic_cache_manager.py'),
        ('auto_cache_updater.py', 'utils/cache_manager/auto_cache_updater.py'),
        ('cache_auto_update_hook.py', 'utils/cache_manager/cache_auto_update_hook.py'),
        ('cleanup_cache.py', 'utils/cache_manager/cleanup_cache.py'),
        
        # Converters
        ('odds_format_converters.py', 'utils/converters/odds_format_converters.py'),
        
        # Helpers
        ('chrome_helper.py', 'utils/helpers/chrome_helper.py'),
        ('history_manager.py', 'utils/helpers/history_manager.py'),
        
        # Mappers
        ('intelligent_name_mapper.py', 'utils/mappers/intelligent_name_mapper.py'),
        
        # Security
        ('secure_config.py', 'utils/security/secure_config.py'),
        ('encrypt_config.py', 'utils/security/encrypt_config.py'),
    ],
    
    # Config folder
    'config': [
        ('config.json', 'config/config.json'),
        ('config.json.template', 'config/config.json.template'),
        ('.config_key', 'config/.config_key'),
        ('requirements.txt', 'config/requirements.txt'),
    ],
    
    # Deployment folder
    'deployment': [
        ('deploy_unified_odds.sh', 'deployment/deploy_unified_odds.sh'),
        ('deploy_unified_odds_auto.sh', 'deployment/deploy_unified_odds_auto.sh'),
        ('deploy_1xbet_only.ps1', 'deployment/deploy_1xbet_only.ps1'),
        ('unified-odds.service', 'deployment/unified-odds.service'),
        ('run_without_monitoring.sh', 'deployment/run_without_monitoring.sh'),
        ('vps_ssh_key.txt', 'deployment/vps_ssh_key.txt'),
    ],
    
    # Docs folder
    'docs': [
        ('README.md', 'docs/README.md'),
        ('API_ENDPOINTS.md', 'docs/API_ENDPOINTS.md'),
        ('API_REFERENCE.md', 'docs/API_REFERENCE.md'),
        ('ADDING_NEW_BOOKMAKERS.md', 'docs/ADDING_NEW_BOOKMAKERS.md'),
        ('DOCUMENTATION_INDEX.md', 'docs/DOCUMENTATION_INDEX.md'),
        ('EMAIL_SETUP_GUIDE.md', 'docs/EMAIL_SETUP_GUIDE.md'),
        ('GITHUB_ACTIONS_SETUP.md', 'docs/GITHUB_ACTIONS_SETUP.md'),
        ('GITHUB_DEPLOYMENT_GUIDE.md', 'docs/GITHUB_DEPLOYMENT_GUIDE.md'),
        ('SECURITY_CONFIG_GUIDE.md', 'docs/SECURITY_CONFIG_GUIDE.md'),
        ('PROJECT_STRUCTURE.md', 'docs/PROJECT_STRUCTURE.md'),
    ],
    
    # Data folder
    'data': [
        ('unified_odds.json', 'data/unified_odds.json'),
        ('cache_data.json', 'data/cache_data.json'),
        ('monitoring_status.json', 'data/monitoring_status.json'),
        ('odds_viewer_template.html', 'data/odds_viewer_template.html'),
    ],
    
    # Tests folder
    'tests': [
        ('test_enhanced_cache.py', 'tests/test_enhanced_cache.py'),
    ],
}


def create_subdirectories():
    """Create subdirectories in utils folder"""
    subdirs = [
        'utils/cache_manager',
        'utils/converters',
        'utils/helpers',
        'utils/mappers',
        'utils/security',
    ]
    
    for subdir in subdirs:
        path = BASE_DIR / subdir
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created: {subdir}/")


def move_files():
    """Move files to new structure"""
    total_moved = 0
    total_failed = 0
    
    for category, movements in MOVEMENTS.items():
        print(f"\n{'=' * 80}")
        print(f"MOVING {category.upper()} FILES")
        print(f"{'=' * 80}")
        
        for src, dest in movements:
            src_path = BASE_DIR / src
            dest_path = BASE_DIR / dest
            
            if not src_path.exists():
                print(f"  ⏭  {src} (already moved or doesn't exist)")
                continue
            
            try:
                # Create destination directory if needed
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move file or directory
                if src_path.is_dir():
                    shutil.move(str(src_path), str(dest_path))
                    print(f"  ✓ {src}/ → {dest}/")
                else:
                    shutil.move(str(src_path), str(dest_path))
                    print(f"  ✓ {src} → {dest}")
                
                total_moved += 1
                
            except Exception as e:
                print(f"  ✗ Failed to move {src}: {e}")
                total_failed += 1
    
    return total_moved, total_failed


def create_init_files():
    """Create __init__.py files for Python packages"""
    packages = [
        'core',
        'utils',
        'utils/cache_manager',
        'utils/converters',
        'utils/helpers',
        'utils/mappers',
        'utils/security',
        'tests',
    ]
    
    print(f"\n{'=' * 80}")
    print("CREATING __init__.py FILES")
    print(f"{'=' * 80}")
    
    for package in packages:
        init_file = BASE_DIR / package / '__init__.py'
        if not init_file.exists():
            init_file.write_text('"""Package initialization"""\n')
            print(f"  ✓ {package}/__init__.py")


def create_readme_in_main():
    """Create a new README.md in root pointing to docs"""
    readme_content = """# Unified Odds System

A comprehensive multi-bookmaker odds collection and monitoring system with real-time updates.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r config/requirements.txt

# Configure system
cp config/config.json.template config/config.json
# Edit config/config.json with your settings

# Run the system
python core/launch_odds_system.py --include-live
```

## 📊 Supported Bookmakers

- ✅ **1xBet** (Live + Pregame + Futures)
- ✅ **FanDuel** (Live + Pregame)
- ✅ **Bet365** (Live + Pregame)
- ✅ **OddsMagnet** (Real-time, 117+ leagues, 9 bookmakers)

## 🌐 API Endpoints

Access odds data via REST API:

- `http://localhost:8000/` - Web dashboard
- `http://localhost:8000/api/matches` - All matches
- `http://localhost:8000/1xbet/pregame` - 1xBet pregame odds
- `http://localhost:8000/fanduel/live` - FanDuel live odds
- `http://localhost:8000/oddsmagnet/football` - OddsMagnet all leagues
- `http://localhost:8000/oddsmagnet/football/top10` - Top 10 leagues only

## 📁 Project Structure

```
unified-odds-system/
├── bookmakers/      # Bookmaker-specific scrapers
├── core/            # Core system files
├── utils/           # Utility modules
├── config/          # Configuration files
├── deployment/      # Deployment scripts
├── docs/            # Documentation
├── data/            # Runtime data outputs
└── tests/           # Test files
```

See [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md) for detailed structure.

## 📖 Documentation

- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation
- [**Project Structure**](docs/PROJECT_STRUCTURE.md) - Folder organization
- [**Adding Bookmakers**](docs/ADDING_NEW_BOOKMAKERS.md) - Scalability guide
- [**Deployment Guide**](docs/GITHUB_DEPLOYMENT_GUIDE.md) - VPS deployment
- [**Documentation Index**](docs/DOCUMENTATION_INDEX.md) - All docs

## 🔧 Configuration

Edit `config/config.json`:

```json
{
  "enabled_scrapers": {
    "1xbet": true,
    "fanduel": true,
    "bet365": false,
    "oddsmagnet": true
  }
}
```

## 🚀 Deployment

```bash
# Deploy to VPS
bash deployment/deploy_unified_odds_auto.sh
```

System auto-deploys on git push to `main` branch via GitHub Actions.

## 📊 Features

- ✅ Real-time odds collection (1-second updates)
- ✅ Multi-bookmaker support
- ✅ Automated monitoring & health checks
- ✅ REST API with FastAPI
- ✅ Web dashboard UI
- ✅ Email alerts on failures
- ✅ Auto-restart on crashes
- ✅ Modular & scalable architecture

## 🛠 Tech Stack

- **Backend**: Python, FastAPI
- **Scraping**: Selenium, Requests
- **Deployment**: GitHub Actions, Systemd
- **Monitoring**: Custom health monitoring system

## 📝 License

Private project - All rights reserved

---

**For detailed documentation, see [`docs/`](docs/) folder**
"""
    
    readme_path = BASE_DIR / 'README.md'
    readme_path.write_text(readme_content)
    print(f"\n  ✓ Created new README.md in root")


def main():
    """Main reorganization process"""
    print("\n🚀 Starting reorganization...\n")
    
    # Step 1: Create subdirectories
    print(f"{'=' * 80}")
    print("CREATING SUBDIRECTORIES")
    print(f"{'=' * 80}")
    create_subdirectories()
    
    # Step 2: Move files
    moved, failed = move_files()
    
    # Step 3: Create __init__.py files
    create_init_files()
    
    # Step 4: Create new README
    create_readme_in_main()
    
    # Summary
    print(f"\n{'=' * 80}")
    print("REORGANIZATION COMPLETE")
    print(f"{'=' * 80}")
    print(f"\n✓ Files moved: {moved}")
    print(f"✗ Failed moves: {failed}")
    print()
    print("📝 Next steps:")
    print("  1. Review moved files")
    print("  2. Update import statements in Python files")
    print("  3. Test the system: python core/launch_odds_system.py")
    print("  4. Commit changes: git add . && git commit -m 'Reorganize project structure'")
    print("  5. Push to deploy: git push origin main")
    print()
    print(f"📖 See PROJECT_STRUCTURE.md for import path updates")
    print("=" * 80)


if __name__ == "__main__":
    main()
