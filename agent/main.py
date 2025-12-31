#!/usr/bin/env python3
"""
Odds Data Analysis Agent - CLI Interface
Interactive tool for analyzing correlations between unified and oddsmagnet data
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.data_analyzer import DataAnalyzer
from agent.llm_agent import LLMAgent


class OddsAnalysisAgent:
    """Main CLI interface for the odds analysis agent"""
    
    def __init__(self):
        self.analyzer = None
        self.llm_agent = None
        self.current_report = None
        
    def setup(self):
        """Initialize the agent components"""
        print("\n" + "="*70)
        print("🤖 ODDS DATA ANALYSIS AGENT")
        print("="*70)
        print("\nInitializing components...")
        
        # Initialize data analyzer
        self.analyzer = DataAnalyzer()
        print("✅ Data Analyzer initialized")
        
        # Ask user for LLM provider
        print("\n" + "-"*70)
        print("LLM Configuration:")
        print("-"*70)
        print("Available providers:")
        print("  1. Google AI Studio (Gemini) - RECOMMENDED ✨")
        print("  2. OpenAI (requires OPENAI_API_KEY)")
        print("  3. Anthropic (requires ANTHROPIC_API_KEY)")
        print("  4. Local LLM (e.g., Ollama, LM Studio)")
        print("  5. Skip LLM (basic analysis only)")
        
        choice = input("\nSelect provider [1-5] (default: 1): ").strip() or "1"
        
        if choice == "1":
            api_key = input("Enter Google API key (or press Enter to use GOOGLE_API_KEY env var): ").strip()
            model = input("Enter model name (default: gemini-pro): ").strip() or "gemini-pro"
            self.llm_agent = LLMAgent(provider="google", model=model, api_key=api_key or None)
        
        elif choice == "2":
            api_key = input("Enter OpenAI API key (or press Enter to use OPENAI_API_KEY env var): ").strip()
            model = input("Enter model name (default: gpt-3.5-turbo): ").strip() or "gpt-3.5-turbo"
            self.llm_agent = LLMAgent(provider="openai", model=model, api_key=api_key or None)
        
        elif choice == "3":
            api_key = input("Enter Anthropic API key (or press Enter to use ANTHROPIC_API_KEY env var): ").strip()
            model = input("Enter model name (default: claude-3-sonnet-20240229): ").strip() or "claude-3-sonnet-20240229"
            self.llm_agent = LLMAgent(provider="anthropic", model=model, api_key=api_key or None)
        
        elif choice == "4":
            base_url = input("Enter local LLM URL (default: http://localhost:11434/v1): ").strip()
            if base_url:
                import os
                os.environ["LOCAL_LLM_URL"] = base_url
            model = input("Enter model name (default: llama2): ").strip() or "llama2"
            self.llm_agent = LLMAgent(provider="local", model=model)
        
        else:
            print("✅ Skipping LLM - using basic analysis")
            self.llm_agent = None
        
        print("\n✅ Setup complete!\n")
    
    def load_data(self):
        """Load all data sources"""
        print("\n" + "="*70)
        print("📊 LOADING DATA")
        print("="*70 + "\n")
        
        self.analyzer.load_unified_data()
        self.analyzer.load_oddsmagnet_data()
        
        print("\n✅ All data loaded successfully\n")
    
    def generate_report(self):
        """Generate correlation analysis report"""
        print("\n" + "="*70)
        print("📈 GENERATING ANALYSIS REPORT")
        print("="*70 + "\n")
        
        self.current_report = self.analyzer.generate_analysis_report()
        
        # Display summary
        print("\nSUMMARY:")
        print("-" * 70)
        summary = self.current_report['summary']
        print(f"Unified System:  {summary['unified_pregame_matches']} pregame + {summary['unified_live_matches']} live matches")
        print(f"OddsMagnet:      {summary['oddsmagnet_total_matches']} total matches across {len(summary['oddsmagnet_sports'])} sports")
        
        print("\nCORRELATIONS:")
        print("-" * 70)
        corr = self.current_report['correlations']
        print(f"Matches found:     {corr['matches_found']}")
        print(f"Matches not found: {corr['matches_not_found']}")
        
        print("\nKEY INSIGHTS:")
        print("-" * 70)
        for insight in self.current_report['insights']:
            print(f"• {insight}")
        
        print("\n✅ Report generated\n")
    
    def llm_analysis(self):
        """Get LLM-powered analysis of the report"""
        if not self.llm_agent:
            print("\n⚠️  LLM not configured. Using basic analysis.\n")
            analysis = self.llm_agent._fallback_analysis(self.current_report) if self.llm_agent else "LLM analysis not available"
        else:
            print("\n" + "="*70)
            print("🤖 LLM ANALYSIS")
            print("="*70 + "\n")
            print("Analyzing data... (this may take a few seconds)\n")
            
            analysis = self.llm_agent.analyze_data_correlation(self.current_report)
        
        print(analysis)
        print("\n")
    
    def interactive_mode(self):
        """Start interactive Q&A mode"""
        if not self.llm_agent:
            print("\n⚠️  LLM not configured. Interactive mode not available.\n")
            return
        
        print("\n" + "="*70)
        print("💬 INTERACTIVE MODE")
        print("="*70)
        print("\nAsk questions about the data. Type 'exit' to return to menu.\n")
        
        while True:
            question = input("\n❓ Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit', 'back']:
                break
            
            print("\n🤔 Thinking...\n")
            answer = self.llm_agent.ask_question(question, context=self.current_report)
            print(answer)
    
    def save_report(self):
        """Save the analysis report to a file"""
        if not self.current_report:
            print("\n⚠️  No report generated yet.\n")
            return
        
        output_file = Path(__file__).parent / "analysis_report.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_report, f, indent=2)
        
        print(f"\n✅ Report saved to: {output_file}\n")
    
    def show_menu(self):
        """Display main menu"""
        print("\n" + "="*70)
        print("MENU")
        print("="*70)
        print("1. Load Data")
        print("2. Generate Analysis Report")
        print("3. Get LLM Analysis")
        print("4. Interactive Q&A Mode")
        print("5. Save Report to File")
        print("6. View Sample Comparisons")
        print("7. Exit")
        print("="*70)
    
    def view_sample_comparisons(self):
        """View detailed sample comparisons"""
        if not self.current_report or not self.current_report['correlations']['examples']:
            print("\n⚠️  No comparisons available. Generate a report first.\n")
            return
        
        print("\n" + "="*70)
        print("📋 SAMPLE COMPARISONS")
        print("="*70 + "\n")
        
        examples = self.current_report['correlations']['examples']
        
        for i, example in enumerate(examples, 1):
            print(f"\nCOMPARISON {i}:")
            print("-" * 70)
            
            unified = example['unified_match']
            oddsmagnet = example['oddsmagnet_match']
            
            print(f"Unified:     {unified['home']} vs {unified['away']} ({unified['sport']})")
            print(f"OddsMagnet:  {oddsmagnet['home']} vs {oddsmagnet['away']} ({oddsmagnet['sport']})")
            print(f"Similarity:  {oddsmagnet['similarity']:.1%}")
            
            print(f"\nBookmakers:")
            print(f"  Unified:     {', '.join(example.get('unified_bookmakers', []))}")
            print(f"  OddsMagnet:  {', '.join(example.get('oddsmagnet_bookmakers', []))}")
            
            print(f"\nMarkets:")
            print(f"  Unified:     {', '.join(example.get('unified_markets', []))}")
            print(f"  OddsMagnet:  {example.get('oddsmagnet_markets_count', 0)} market types")
            
            if example.get('insights'):
                print(f"\nInsights:")
                for insight in example['insights']:
                    print(f"  • {insight}")
            
            print()
    
    def run(self):
        """Main application loop"""
        self.setup()
        
        while True:
            self.show_menu()
            choice = input("\nSelect option [1-7]: ").strip()
            
            if choice == "1":
                self.load_data()
            
            elif choice == "2":
                if not self.analyzer.unified_data or not self.analyzer.oddsmagnet_data:
                    print("\n⚠️  Please load data first (option 1)\n")
                else:
                    self.generate_report()
            
            elif choice == "3":
                if not self.current_report:
                    print("\n⚠️  Please generate a report first (option 2)\n")
                else:
                    self.llm_analysis()
            
            elif choice == "4":
                if not self.current_report:
                    print("\n⚠️  Please generate a report first (option 2)\n")
                else:
                    self.interactive_mode()
            
            elif choice == "5":
                self.save_report()
            
            elif choice == "6":
                self.view_sample_comparisons()
            
            elif choice == "7":
                print("\n👋 Goodbye!\n")
                break
            
            else:
                print("\n⚠️  Invalid choice. Please select 1-7.\n")


def main():
    """Entry point"""
    agent = OddsAnalysisAgent()
    
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
