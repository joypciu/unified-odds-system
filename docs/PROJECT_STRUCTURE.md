# 📁 Project Structure

This document explains the organized folder structure of the Unified Odds System.

## 📂 Root Directory Structure

```
unified-odds-system/
├── bookmakers/              # All bookmaker-specific scrapers (modular)
│   ├── bet365/             # Bet365 scraper & data
│   ├── fanduel/            # FanDuel scraper & data
│   ├── 1xbet/              # 1xBet scraper & data
│   ├── oddsmagnet/         # OddsMagnet scraper & data
│   └── [future bookmakers] # Add new bookmakers here
│
├── core/                   # Core system files (main logic)
│   ├── launch_odds_system.py       # Main launcher
│   ├── run_unified_system.py       # Unified collector
│   ├── live_odds_viewer_clean.py   # FastAPI web server
│   ├── unified_odds_collector.py   # Data aggregator
│   └── monitoring_system.py        # Health monitoring
│
├── utils/                  # Utility modules (helpers)
│   ├── cache_manager/              # Cache management
│   ├── converters/                 # Format converters
│   ├── helpers/                    # Helper functions
│   └── mappers/                    # Data mappers
│
├── config/                 # Configuration files
│   ├── config.json                 # Main config (encrypted)
│   ├── config.json.template        # Config template
│   ├── .config_key                 # Encryption key
│   └── requirements.txt            # Python dependencies
│
├── deployment/             # Deployment scripts & services
│   ├── deploy_unified_odds.sh      # Main deployment
│   ├── deploy_unified_odds_auto.sh # Auto deployment
│   ├── unified-odds.service        # Systemd service
│   └── run_without_monitoring.sh   # Alternative run
│
├── docs/                   # Documentation
│   ├── README.md                      # Main readme
│   ├── API_ENDPOINTS.md               # API documentation
│   ├── API_REFERENCE.md               # API reference
│   ├── ADDING_NEW_BOOKMAKERS.md       # Scalability guide
│   ├── DOCUMENTATION_INDEX.md         # Docs index
│   ├── EMAIL_SETUP_GUIDE.md           # Email config
│   ├── GITHUB_ACTIONS_SETUP.md        # CI/CD setup
│   ├── GITHUB_DEPLOYMENT_GUIDE.md     # Deployment guide
│   └── SECURITY_CONFIG_GUIDE.md       # Security guide
│
├── data/                   # Runtime data & outputs
│   ├── unified_odds.json           # Main output
│   ├── cache_data.json             # Cache data
│   ├── monitoring_status.json      # Status data
│   └── [dynamic files]             # Generated data
│
├── tests/                  # Test files
│   └── test_enhanced_cache.py      # Cache tests
│
├── .github/                # GitHub Actions workflows
│   └── workflows/
│       ├── deploy.yml              # Auto-deployment
│       └── deploy-with-deps.yml    # Deployment with deps
│
├── .gitignore              # Git ignore rules
└── PROJECT_STRUCTURE.md    # This file

```

## 🎯 Organization Principles

### 1. **Bookmakers Folder** (`bookmakers/`)

- **One folder per bookmaker** for complete isolation
- Each bookmaker folder contains:
  - Scraper scripts (live, pregame, futures)
  - Bookmaker-specific config
  - Data outputs (JSON files)
  - Documentation (README, guides)
- **Easy to add new bookmakers** - just create a new folder

### 2. **Core Folder** (`core/`)

- Main system files that run the entire platform
- Launcher, unified collector, web server, monitoring
- **Critical files** - these control the whole system

### 3. **Utils Folder** (`utils/`)

- Reusable utility modules
- Cache management, converters, helpers
- Organized by function (cache, converters, helpers, mappers)
- **Shared across all bookmakers**

### 4. **Config Folder** (`config/`)

- All configuration files in one place
- Encrypted config, templates, encryption keys
- Dependencies (requirements.txt)
- **Security-sensitive files**

### 5. **Deployment Folder** (`deployment/`)

- Deployment scripts for VPS
- Systemd service files
- Alternative run scripts
- **DevOps files**

### 6. **Docs Folder** (`docs/`)

- All documentation in one central location
- API docs, guides, setup instructions
- **Easy to find documentation**

### 7. **Data Folder** (`data/`)

- Runtime data outputs
- Cache files, status files
- Generated JSON outputs
- **Excluded from git** (add to .gitignore)

### 8. **Tests Folder** (`tests/`)

- All test files
- Unit tests, integration tests
- **Separate from production code**

## 🚀 Benefits of This Structure

✅ **Scalability**: Add new bookmakers without touching core system  
✅ **Modularity**: Each component is isolated and independent  
✅ **Clarity**: Clear separation of concerns  
✅ **Maintainability**: Easy to find and update files  
✅ **Flexibility**: Can easily add/remove bookmakers  
✅ **Professional**: Industry-standard structure

## 📝 How to Add a New Bookmaker

1. Create folder: `bookmakers/new_bookmaker/`
2. Add scraper scripts
3. Add 10 lines to `core/launch_odds_system.py`
4. Add FastAPI endpoint in `core/live_odds_viewer_clean.py`
5. Done! System auto-deploys on git push

## 🔧 Import Path Updates

After reorganization, update imports:

### Before:

```python
from unified_odds_collector import UnifiedOddsCollector
from chrome_helper import ChromeHelper
```

### After:

```python
from core.unified_odds_collector import UnifiedOddsCollector
from utils.helpers.chrome_helper import ChromeHelper
```

## 📊 File Migration Map

| Old Location                | New Location                     |
| --------------------------- | -------------------------------- |
| `bet365/`                   | `bookmakers/bet365/`             |
| `fanduel/`                  | `bookmakers/fanduel/`            |
| `1xbet/`                    | `bookmakers/1xbet/`              |
| `oddsmagnet/`               | `bookmakers/oddsmagnet/`         |
| `launch_odds_system.py`     | `core/launch_odds_system.py`     |
| `run_unified_system.py`     | `core/run_unified_system.py`     |
| `live_odds_viewer_clean.py` | `core/live_odds_viewer_clean.py` |
| `unified_odds_collector.py` | `core/unified_odds_collector.py` |
| `monitoring_system.py`      | `core/monitoring_system.py`      |
| `*.md` (docs)               | `docs/*.md`                      |
| `deploy_*.sh`               | `deployment/*.sh`                |
| `*.service`                 | `deployment/*.service`           |
| `config.json*`              | `config/config.json*`            |
| `requirements.txt`          | `config/requirements.txt`        |
| `*.json` (data)             | `data/*.json`                    |

---

**Last Updated**: December 11, 2025  
**Version**: 2.0 (Reorganized Structure)
