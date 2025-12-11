# OddsMagnet Scraper - Quick Navigation

## 🎯 Start Here

### New User?

1. **Read**: [`README_ODDSMAGNET.md`](README_ODDSMAGNET.md) - Complete documentation
2. **Run**: `python oddsmagnet_quick_examples.py` - Interactive examples
3. **Explore**: `all_matches_summary.json` - See available matches

### Want to Scrape?

```python
# Quick start
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector

collector = OddsMagnetCompleteCollector()
matches = collector.get_all_matches_summary()  # Get all 807+ matches
```

---

## 📖 Documentation Files

| File                                                             | Description                       | Read When                            |
| ---------------------------------------------------------------- | --------------------------------- | ------------------------------------ |
| **[README_ODDSMAGNET.md](README_ODDSMAGNET.md)**                 | **Complete user guide**           | **Start here - everything you need** |
| [ODDSMAGNET_SOLUTION_SUMMARY.md](ODDSMAGNET_SOLUTION_SUMMARY.md) | Technical architecture & findings | Want to understand how it works      |
| [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)                         | What was cleaned and why          | Migrating from old files             |
| [INDEX.md](INDEX.md)                                             | This file - navigation guide      | Finding your way around              |

---

## 💻 Code Files

### Production Scripts

| File                                     | Purpose                           | Use Case                              |
| ---------------------------------------- | --------------------------------- | ------------------------------------- |
| **`oddsmagnet_complete_collector.py`**   | **All leagues/matches collector** | **Bulk collection, multiple leagues** |
| **`oddsmagnet_multi_market_scraper.py`** | **Single match/league scraper**   | **Specific matches, custom filters**  |
| `deep_oddsmagnet_inspector.py`           | Site structure inspector          | Debugging, analysis                   |
| `oddsmagnet_quick_examples.py`           | Example code runner               | Learning, quick reference             |

### Other Scrapers

- `espn_scraper.py` - ESPN data
- `native_stats_scraper.py` - Native Stats
- `optic_odds_scraper_v2.py` - Optic Odds
- `sportbex_scraper_v2.py` - Sportbex

---

## 📊 Data Files

| File                             | Content              | Size        | Updated       |
| -------------------------------- | -------------------- | ----------- | ------------- |
| `all_leagues.json`               | 117 leagues metadata | Small       | On collection |
| `all_matches_summary.json`       | 807+ matches         | 8,879 lines | On collection |
| `matches_by_league_summary.json` | Organized by league  | Medium      | On collection |
| `oddsmagnet_odds.json`           | Sample odds          | Small       | Manual        |

---

## 🚀 Common Tasks

### Task 1: Get All Available Matches

```python
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector

collector = OddsMagnetCompleteCollector()
matches = collector.get_all_matches_summary()

print(f"Found {len(matches)} matches")
```

**Time**: ~25 seconds  
**Output**: List of all matches with metadata

---

### Task 2: Scrape Single Match (All Markets)

```python
from oddsmagnet_multi_market_scraper import OddsMagnetMultiMarketScraper

scraper = OddsMagnetMultiMarketScraper()

data = scraper.scrape_match_all_markets(
    match_uri="football/spain-laliga/real-madrid-v-barcelona",
    match_name="Real Madrid v Barcelona",
    league_name="Spain La Liga",
    match_date="2025-12-20"
)

print(f"Collected {data['total_odds_collected']} odds")
```

**Time**: ~45 seconds  
**Output**: ~580 odds from 68 markets

---

### Task 3: Scrape League (Filtered)

```python
from oddsmagnet_multi_market_scraper import OddsMagnetMultiMarketScraper

scraper = OddsMagnetMultiMarketScraper()

data = scraper.scrape_league(
    league_slug="england-premier-league",
    league_name="England Premier League",
    max_matches=5,
    market_filter=['popular markets', 'over under betting']
)
```

**Time**: ~4 minutes  
**Output**: 5 matches with filtered markets

---

### Task 4: Scrape Multiple Leagues

```python
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector

collector = OddsMagnetCompleteCollector()

data = collector.collect_all_matches_with_odds(
    leagues=['spain-laliga', 'england-premier-league', 'germany-bundesliga'],
    max_matches_per_league=3,
    market_filter=['popular markets'],
    save_interval=5
)
```

**Time**: ~15 minutes  
**Output**: 9 matches with popular markets

---

### Task 5: Find Upcoming Matches

```python
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector
from datetime import datetime, timedelta

collector = OddsMagnetCompleteCollector()
all_matches = collector.get_all_matches_summary()

now = datetime.now()
week_later = now + timedelta(days=7)

upcoming = [
    m for m in all_matches
    if now.isoformat() <= m['match_date'] <= week_later.isoformat()
]

print(f"{len(upcoming)} matches in next 7 days")
```

**Time**: ~25 seconds  
**Output**: Filtered match list

---

## 🔍 Finding Information

### "How do I...?"

| Question                | Answer                                                 |
| ----------------------- | ------------------------------------------------------ |
| Get started?            | Read `README_ODDSMAGNET.md`                            |
| See examples?           | Run `python oddsmagnet_quick_examples.py`              |
| Understand the API?     | Check `ODDSMAGNET_SOLUTION_SUMMARY.md`                 |
| Find available matches? | Open `all_matches_summary.json`                        |
| Debug issues?           | Use `deep_oddsmagnet_inspector.py`                     |
| Migrate old code?       | See `CLEANUP_SUMMARY.md`                               |
| Configure options?      | See "Configuration" in `README_ODDSMAGNET.md`          |
| Improve performance?    | See "Potential Improvements" in `README_ODDSMAGNET.md` |

---

## 📈 Capabilities

### What Can It Do?

✅ Collect from **ALL 117 football leagues**  
✅ Process **807+ available matches**  
✅ Scrape **ALL 69 betting markets** per match  
✅ Get odds from **9+ bookmakers**  
✅ Filter by league, date, market type  
✅ Save progress during collection  
✅ Handle errors gracefully  
✅ Respect rate limits

### Scale

| Scope         | Matches | Markets | Odds     | Time     |
| ------------- | ------- | ------- | -------- | -------- |
| Single match  | 1       | 68      | ~580     | 45 sec   |
| Single league | 20      | 1,360   | ~11,600  | 8 min    |
| Top 5 leagues | 100     | 6,800   | ~58,000  | 4 hours  |
| All leagues   | 807     | 55,676  | ~445,000 | 36 hours |

---

## 🛠️ Development

### File Dependencies

```
oddsmagnet_complete_collector.py
    └── imports oddsmagnet_multi_market_scraper.py
        └── uses requests, json, datetime, time

deep_oddsmagnet_inspector.py
    └── standalone (requests, beautifulsoup4, json)

oddsmagnet_quick_examples.py
    └── imports both collector and scraper
```

### Adding Features

1. **Modify collection logic**: Edit `oddsmagnet_multi_market_scraper.py`
2. **Add filtering**: Edit `oddsmagnet_complete_collector.py`
3. **Extend analysis**: Edit `deep_oddsmagnet_inspector.py`
4. **Add examples**: Edit `oddsmagnet_quick_examples.py`

---

## 🐛 Troubleshooting

### Common Issues

| Issue              | Solution                      | Details                                  |
| ------------------ | ----------------------------- | ---------------------------------------- |
| 403 Forbidden      | Check session establishment   | `README_ODDSMAGNET.md` → Troubleshooting |
| Timeouts           | Increase timeout values       | `README_ODDSMAGNET.md` → Troubleshooting |
| Empty data         | Check match date/availability | `README_ODDSMAGNET.md` → Troubleshooting |
| Import errors      | Install dependencies          | `pip install requests beautifulsoup4`    |
| Old file not found | Check migration guide         | `CLEANUP_SUMMARY.md`                     |

---

## 📚 Learning Path

### Beginner

1. Run `python oddsmagnet_quick_examples.py`
2. Read "Quick Start" in `README_ODDSMAGNET.md`
3. Modify examples to suit your needs

### Intermediate

1. Read full `README_ODDSMAGNET.md`
2. Understand configuration options
3. Implement custom filtering

### Advanced

1. Read `ODDSMAGNET_SOLUTION_SUMMARY.md`
2. Review "Potential Improvements" section
3. Extend functionality (database, parallel processing, etc.)

---

## 📞 Quick Reference

### Import Statements

```python
from oddsmagnet_complete_collector import OddsMagnetCompleteCollector
from oddsmagnet_multi_market_scraper import OddsMagnetMultiMarketScraper
from deep_oddsmagnet_inspector import OddsMagnetInspector
```

### Market Categories

Popular Markets • Handicap Betting • Over/Under Betting • Both Teams to Score • Winner Sports Betting • Correct Score Betting • 1st Half Markets • 2nd Half Markets • Goals Exact Markets • To Score Odds • Win to Nil • Odd/Even Betting • Double Chance

### League Slugs (Top 10)

`spain-laliga` • `england-premier-league` • `germany-bundesliga` • `italy-serie-a` • `france-ligue-1` • `champions-league` • `europe-uefa-europa-league` • `netherlands-eredivisie` • `portugal-primeira-liga` • `belgium-first-division-a`

---

## ✅ Checklist for New Users

- [ ] Read `README_ODDSMAGNET.md` (at least Quick Start section)
- [ ] Install dependencies: `pip install requests beautifulsoup4`
- [ ] Run examples: `python oddsmagnet_quick_examples.py`
- [ ] Check available matches in `all_matches_summary.json`
- [ ] Try collecting data for 1 match
- [ ] Try collecting data for 1 league
- [ ] Understand configuration options
- [ ] Customize for your use case

---

## 🎓 Additional Resources

### In This Directory

- All Python files have detailed docstrings
- Check `__main__` sections for usage examples
- JSON files show data structure examples

### External

- OddsMagnet website: https://oddsmagnet.com/football/
- Browser DevTools: Inspect network requests
- API responses: Check saved JSON files

---

**Last Updated**: December 11, 2025  
**Total Files**: 18 (after cleanup)  
**Lines of Code**: ~2,500  
**Documentation Pages**: 4
