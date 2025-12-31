#!/usr/bin/env python3
"""
Example: Using the Odds Analysis Agent Programmatically

This script demonstrates how to integrate the agent into your own code.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import DataAnalyzer, LLMAgent
import json


def example_1_basic_analysis():
    """Example 1: Basic data analysis without LLM"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Analysis (No LLM Required)")
    print("="*70 + "\n")
    
    # Initialize analyzer
    analyzer = DataAnalyzer()
    
    # Load data
    print("Loading data...")
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Generate report
    print("Generating report...")
    report = analyzer.generate_analysis_report()
    
    # Access specific data
    print(f"\nTotal pregame matches: {report['summary']['unified_pregame_matches']}")
    print(f"OddsMagnet matches: {report['summary']['oddsmagnet_total_matches']}")
    print(f"Correlation examples found: {len(report['correlations']['examples'])}")
    
    return report


def example_2_with_llm():
    """Example 2: Using LLM for intelligent analysis"""
    print("\n" + "="*70)
    print("EXAMPLE 2: LLM-Powered Analysis")
    print("="*70 + "\n")
    
    # Initialize
    analyzer = DataAnalyzer()
    agent = LLMAgent(provider="openai")  # or "anthropic" or "local"
    
    # Load data
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Generate report
    report = analyzer.generate_analysis_report()
    
    # Get LLM analysis
    if agent.client:
        print("Getting AI insights...\n")
        analysis = agent.analyze_data_correlation(report)
        print(analysis)
    else:
        print("LLM not available, using basic analysis")
        print(agent._fallback_analysis(report))
    
    return report, agent


def example_3_specific_match_lookup():
    """Example 3: Find and compare a specific match"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Specific Match Lookup")
    print("="*70 + "\n")
    
    analyzer = DataAnalyzer()
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Get first pregame match from unified data
    if not analyzer.unified_data or not analyzer.unified_data.get('pregame_matches'):
        print("No pregame matches available")
        return
    
    unified_match = analyzer.unified_data['pregame_matches'][0]
    
    print(f"Looking for: {unified_match.get('home_team')} vs {unified_match.get('away_team')}")
    
    # Try to find it in oddsmagnet
    om_match = analyzer.find_matching_oddsmagnet_match(unified_match)
    
    if om_match:
        print(f"✅ Found in OddsMagnet!")
        print(f"   Similarity: {om_match['similarity']:.1%}")
        print(f"   Sport: {om_match['sport']}")
        
        # Compare odds
        comparison = analyzer.compare_odds(unified_match, om_match)
        print(f"\nComparison:")
        print(json.dumps(comparison, indent=2))
    else:
        print("❌ Not found in OddsMagnet data")


def example_4_ask_questions():
    """Example 4: Interactive Q&A with LLM"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Ask Questions About Your Data")
    print("="*70 + "\n")
    
    # Setup
    analyzer = DataAnalyzer()
    agent = LLMAgent(provider="openai")
    
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    report = analyzer.generate_analysis_report()
    
    if not agent.client:
        print("LLM not available for Q&A")
        return
    
    # Ask some questions
    questions = [
        "What's the main reason for low correlation between the systems?",
        "Which data source has better bookmaker coverage?",
        "Should I prioritize improving team name matching or adding more sports?"
    ]
    
    for question in questions:
        print(f"\nQ: {question}")
        print("A:", end=" ")
        answer = agent.ask_question(question, context=report)
        print(answer)
        print("-" * 70)


def example_5_custom_analysis():
    """Example 5: Custom analysis logic"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Custom Analysis Logic")
    print("="*70 + "\n")
    
    analyzer = DataAnalyzer()
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Custom: Find all basketball matches
    basketball_matches = [
        m for m in analyzer.unified_data.get('pregame_matches', [])
        if m.get('sport', '').lower() == 'basketball'
    ]
    
    print(f"Found {len(basketball_matches)} basketball matches in unified data")
    
    # Custom: Check which have FanDuel odds
    with_fanduel = [
        m for m in basketball_matches
        if m.get('fanduel', {}).get('available', False)
    ]
    
    print(f"{len(with_fanduel)} have FanDuel odds")
    
    # Custom: Try to find them in OddsMagnet
    found_in_om = 0
    for match in basketball_matches[:5]:  # Check first 5
        om_match = analyzer.find_matching_oddsmagnet_match(match, sport='basketball')
        if om_match:
            found_in_om += 1
            print(f"✅ {match['home_team']} vs {match['away_team']} - found in OddsMagnet")
    
    print(f"\nFound {found_in_om}/5 basketball matches in OddsMagnet")


def example_6_save_report():
    """Example 6: Generate and save a report"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Save Analysis Report")
    print("="*70 + "\n")
    
    analyzer = DataAnalyzer()
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Generate comprehensive report
    report = analyzer.generate_analysis_report()
    
    # Save to file
    output_file = Path(__file__).parent / "correlation_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Report saved to: {output_file}")
    print(f"   Total size: {output_file.stat().st_size:,} bytes")
    
    # Also save a summary
    summary_file = Path(__file__).parent / "correlation_summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("ODDS DATA CORRELATION SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Generated: {report['timestamp']}\n\n")
        f.write(f"Unified Matches: {report['summary']['unified_pregame_matches']} pregame + "
                f"{report['summary']['unified_live_matches']} live\n")
        f.write(f"OddsMagnet Matches: {report['summary']['oddsmagnet_total_matches']}\n\n")
        f.write("KEY INSIGHTS:\n")
        for insight in report['insights']:
            f.write(f"  • {insight}\n")
    
    print(f"✅ Summary saved to: {summary_file}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("🎓 ODDS ANALYSIS AGENT - PROGRAMMING EXAMPLES")
    print("="*70)
    
    examples = [
        ("Basic Analysis", example_1_basic_analysis),
        ("LLM Analysis", example_2_with_llm),
        ("Specific Match Lookup", example_3_specific_match_lookup),
        ("Interactive Q&A", example_4_ask_questions),
        ("Custom Analysis", example_5_custom_analysis),
        ("Save Report", example_6_save_report),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print(f"  {len(examples) + 1}. Run all examples")
    print("  0. Exit")
    
    choice = input(f"\nSelect example [0-{len(examples) + 1}]: ").strip()
    
    if choice == "0":
        print("\n👋 Goodbye!\n")
        return
    
    if choice == str(len(examples) + 1):
        # Run all
        for name, func in examples:
            try:
                print(f"\n{'='*70}")
                print(f"Running: {name}")
                print('='*70)
                func()
            except Exception as e:
                print(f"⚠️  Error in {name}: {e}")
        return
    
    # Run specific example
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(examples):
            examples[idx][1]()
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
