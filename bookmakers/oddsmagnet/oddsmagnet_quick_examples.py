#!/usr/bin/env python3
"""
OddsMagnet Quick Reference & Examples
Run this file to see common usage patterns with optimized scrapers
"""

from oddsmagnet_optimized_collector import OddsMagnetOptimizedCollector
from oddsmagnet_optimized_scraper import OddsMagnetOptimizedScraper
import json

def example_1_get_all_matches():
    """Example 1: Get all available matches (fast, no odds, cached)"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Get All Available Matches")
    print("="*80)
    
    collector = OddsMagnetOptimizedCollector(max_workers=8, requests_per_second=4.0)
    
    # Get all matches (takes ~25 seconds)
    all_matches = collector.get_all_matches_summary()
    
    print(f"\n✓ Found {len(all_matches)} total matches")
    
    # Group by league
    by_league = {}
    for match in all_matches:
        league = match['league']
        by_league[league] = by_league.get(league, 0) + 1
    
    print(f"✓ Across {len(by_league)} leagues")
    
    # Show top 5 leagues
    print("\nTop 5 leagues by match count:")
    sorted_leagues = sorted(by_league.items(), key=lambda x: x[1], reverse=True)
    for league, count in sorted_leagues[:5]:
        print(f"  {league}: {count} matches")
    
    return all_matches


def example_2_single_match_all_markets():
    """Example 2: Scrape single match with all markets (optimized)"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Single Match with All Markets (Optimized)")
    print("="*80)
    
    scraper = OddsMagnetOptimizedScraper(max_workers=8, requests_per_second=4.0)
    
    # Pick a match (you can change this)
    match_data = scraper.scrape_match_all_markets(
        match_uri="football/spain-laliga/barcelona-v-atletico-madrid",
        match_name="Barcelona v Atletico Madrid",
        league_name="Spain La Liga",
        match_date="2025-12-21",
        use_concurrent=True  # Use concurrent processing for speed
    )
    
    if match_data:
        print(f"\n✓ Collected {match_data['total_odds_collected']} odds")
        print(f"✓ From {sum(len(m) for m in match_data['markets'].values())} markets")
        
        # Show market breakdown
        print("\nMarket breakdown:")
        for category, markets in match_data['markets'].items():
            print(f"  {category}: {len(markets)} markets")
    
    return match_data


def example_3_league_filtered_markets():
    """Example 3: Scrape league with filtered markets (optimized)"""
    print("\n" + "="*80)
    print("EXAMPLE 3: League with Filtered Markets (Optimized)")
    print("="*80)
    
    collector = OddsMagnetOptimizedCollector(max_workers=8, requests_per_second=4.0)
    
    league_data = collector.collect_by_leagues(
        league_slugs=["england-premier-league"],
        max_matches_per_league=3,  # Only first 3 matches
        market_filter=['popular markets', 'over under betting'],
        max_markets_per_category=3,  # Only first 3 markets per category
        output_file='example_league_filtered.json'
    )
    
    if league_data:
        print(f"\n✓ Processed {league_data['processed_matches']} matches")
        
        total_odds = sum(
            m['total_odds_collected'] 
            for m in league_data['matches']
        )
        print(f"✓ Total odds collected: {total_odds}")
    
    return league_data


def example_4_specific_leagues():
    """Example 4: Collect odds from specific leagues"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Specific Leagues Collection")
    print("="*80)
    
    collector = OddsMagnetCompleteCollector()
    
    # Collect from top 3 leagues only
    data = collector.collect_all_matches_with_odds(
        leagues=['spain-laliga', 'england-premier-league', 'germany-bundesliga'],
        max_matches_per_league=2,  # 2 matches per league for demo
        market_filter=['popular markets'],  # Only main markets
        max_markets_per_category=2,  # Limit markets
        save_interval=5
    )
    
    if data:
        print(f"\n✓ Processed {len(data['leagues'])} leagues")
        
        for league in data['leagues']:
            print(f"\n  {league['league']}:")
            print(f"    Matches processed: {league['matches_processed']}")
            
            total_odds = sum(
                m['total_odds_collected'] 
                for m in league['matches']
            )
            print(f"    Total odds: {total_odds}")
    
    return data


def example_5_find_upcoming_matches():
    """Example 5: Find matches in next 7 days"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Find Upcoming Matches (Next 7 Days)")
    print("="*80)
    
    from datetime import datetime, timedelta
    
    collector = OddsMagnetCompleteCollector()
    all_matches = collector.get_all_matches_summary()
    
    # Get date range
    now = datetime.now()
    week_later = now + timedelta(days=7)
    
    # Filter upcoming matches
    upcoming = [
        m for m in all_matches
        if m['match_date'] and now.isoformat() <= m['match_date'] <= week_later.isoformat()
    ]
    
    print(f"\n✓ Found {len(upcoming)} matches in next 7 days")
    
    # Group by league
    by_league = {}
    for match in upcoming:
        league = match['league']
        if league not in by_league:
            by_league[league] = []
        by_league[league].append(match)
    
    print(f"\nTop leagues with upcoming matches:")
    sorted_leagues = sorted(by_league.items(), key=lambda x: len(x[1]), reverse=True)
    for league, matches in sorted_leagues[:5]:
        print(f"  {league}: {len(matches)} matches")
    
    return upcoming


def example_6_specific_match_uri():
    """Example 6: Scrape using exact match URI (optimized)"""
    print("\n" + "="*80)
    print("EXAMPLE 6: Scrape Specific Match by URI (Optimized)")
    print("="*80)
    
    scraper = OddsMagnetOptimizedScraper(max_workers=8, requests_per_second=4.0)
    
    # You can get URIs from all_matches_summary.json
    # Example: "football/italy-serie-a/juventus-v-ac-milan"
    
    print("\nTo scrape a specific match:")
    print("1. Check all_matches_summary.json for available matches")
    print("2. Copy the 'match_uri' value")
    print("3. Use scrape_match_all_markets() with that URI")
    
    print("\nExample URI format:")
    print("  'football/spain-laliga/real-madrid-v-barcelona'")


def main():
    """Run all examples or choose specific ones"""
    
    print("\n" + "#"*80)
    print("ODDSMAGNET SCRAPER - QUICK REFERENCE EXAMPLES")
    print("#"*80)
    
    print("\nAvailable examples:")
    print("  1. Get all available matches (fast)")
    print("  2. Single match with all markets")
    print("  3. League with filtered markets")
    print("  4. Specific leagues collection")
    print("  5. Find upcoming matches")
    print("  6. Scrape specific match by URI")
    
    choice = input("\nEnter example number (1-6) or 'all' to run all: ").strip()
    
    if choice == '1' or choice == 'all':
        example_1_get_all_matches()
    
    if choice == '2' or choice == 'all':
        example_2_single_match_all_markets()
    
    if choice == '3' or choice == 'all':
        example_3_league_filtered_markets()
    
    if choice == '4' or choice == 'all':
        example_4_specific_leagues()
    
    if choice == '5' or choice == 'all':
        example_5_find_upcoming_matches()
    
    if choice == '6' or choice == 'all':
        example_6_specific_match_uri()
    
    print("\n" + "="*80)
    print("DONE! Check README_ODDSMAGNET.md for full documentation")
    print("="*80)


if __name__ == "__main__":
    main()
