"""Run full scraper for all 5 sports."""
from working_scraper import OddsPortalScraper

scraper = OddsPortalScraper()
scraper.scrape_all()
scraper.save_to_json('matches_odds_data.json')
scraper.save_to_csv('matches_odds_data.csv')

print("\n✓ Full scraping complete!")
print(f"✓ Total matches with odds: {len(scraper.matches_data)}")
