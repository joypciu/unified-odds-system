#!/usr/bin/env python3
"""
Quick Start Script for Odds Analysis Agent
Run this for a fast demo of the agent's capabilities
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.data_analyzer import DataAnalyzer
from agent.llm_agent import LLMAgent


def quick_demo():
    """Run a quick demonstration of the agent"""
    
    print("\n" + "="*70)
    print("🤖 ODDS ANALYSIS AGENT - QUICK DEMO")
    print("="*70 + "\n")
    
    # Step 1: Initialize analyzer
    print("Step 1: Initializing Data Analyzer...")
    analyzer = DataAnalyzer()
    
    # Step 2: Load data
    print("\nStep 2: Loading data...\n")
    analyzer.load_unified_data()
    analyzer.load_oddsmagnet_data()
    
    # Check if data is available
    if not analyzer.unified_data or not analyzer.oddsmagnet_data:
        print("\n⚠️  No data available. Please ensure:")
        print("   - data/unified_odds.json exists")
        print("   - bookmakers/oddsmagnet/*.json files exist\n")
        return
    
    # Step 3: Generate report
    print("\nStep 3: Generating analysis report...\n")
    report = analyzer.generate_analysis_report()
    
    # Display summary
    print("\n" + "="*70)
    print("📊 ANALYSIS SUMMARY")
    print("="*70)
    
    summary = report['summary']
    print(f"\n📁 Data Sources:")
    print(f"   Unified:     {summary['unified_pregame_matches']} pregame + {summary['unified_live_matches']} live matches")
    print(f"   OddsMagnet:  {summary['oddsmagnet_total_matches']} matches across {len(summary['oddsmagnet_sports'])} sports")
    
    print(f"\n🔍 Correlation Results:")
    corr = report['correlations']
    total = corr['matches_found'] + corr['matches_not_found']
    if total > 0:
        correlation_pct = (corr['matches_found'] / total) * 100
        print(f"   Match Rate:  {correlation_pct:.1f}% ({corr['matches_found']}/{total})")
    else:
        print(f"   No matches analyzed")
    
    print(f"\n💡 Key Insights:")
    for insight in report['insights']:
        print(f"   • {insight}")
    
    # Step 4: LLM Analysis (optional)
    print("\n" + "="*70)
    print("🤖 LLM ANALYSIS")
    print("="*70)
    
    # Check for API keys
    has_google = bool(os.getenv('GOOGLE_API_KEY'))
    has_openai = bool(os.getenv('OPENAI_API_KEY'))
    has_anthropic = bool(os.getenv('ANTHROPIC_API_KEY'))
    
    if not has_google and not has_openai and not has_anthropic:
        print("\n⚠️  No API keys found. Skipping LLM analysis.")
        print("\nTo enable LLM analysis, set one of these environment variables:")
        print("   GOOGLE_API_KEY=your-key-here (RECOMMENDED)")
        print("   OPENAI_API_KEY=your-key-here")
        print("   ANTHROPIC_API_KEY=your-key-here")
        
        # Show fallback analysis
        print("\n" + "-"*70)
        print("Basic Analysis (without LLM):")
        print("-"*70 + "\n")
        
        agent = LLMAgent(provider="google")  # Will fail gracefully
        basic_analysis = agent._fallback_analysis(report)
        print(basic_analysis)
    
    else:
        # Use LLM (prefer Google)
        if has_google:
            provider = "google"
        elif has_openai:
            provider = "openai"
        else:
            provider = "anthropic"
        print(f"\n✅ Found {provider.upper()} API key. Analyzing with LLM...\n")
        
        agent = LLMAgent(provider=provider)
        
        if agent.client:
            print("⏳ Requesting analysis from LLM (this may take 10-30 seconds)...\n")
            analysis = agent.analyze_data_correlation(report)
            print(analysis)
        else:
            print("⚠️  Failed to initialize LLM client. Using basic analysis.\n")
            basic_analysis = agent._fallback_analysis(report)
            print(basic_analysis)
    
    # Step 5: Show sample comparison
    if report['correlations']['examples']:
        print("\n" + "="*70)
        print("📋 SAMPLE MATCH COMPARISON")
        print("="*70 + "\n")
        
        example = report['correlations']['examples'][0]
        
        unified = example['unified_match']
        oddsmagnet = example['oddsmagnet_match']
        
        print(f"Match Found:")
        print(f"  Unified:     {unified['home']} vs {unified['away']} ({unified['sport']})")
        print(f"  OddsMagnet:  {oddsmagnet['home']} vs {oddsmagnet['away']} ({oddsmagnet['sport']})")
        print(f"  Similarity:  {oddsmagnet['similarity']:.1%}")
        
        print(f"\nBookmakers Available:")
        print(f"  Unified:     {', '.join(example.get('unified_bookmakers', ['None']))}")
        print(f"  OddsMagnet:  {', '.join(example.get('oddsmagnet_bookmakers', ['None']))}")
        
        print(f"\nMarket Coverage:")
        print(f"  Unified:     {', '.join(example.get('unified_markets', ['None']))}")
        print(f"  OddsMagnet:  {example.get('oddsmagnet_markets_count', 0)} different market types")
    
    # Conclusion
    print("\n" + "="*70)
    print("✅ DEMO COMPLETE")
    print("="*70)
    print("\nFor full interactive experience, run:")
    print("   python agent/main.py")
    print("\nFor more information, see:")
    print("   agent/README.md\n")


if __name__ == "__main__":
    try:
        quick_demo()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
