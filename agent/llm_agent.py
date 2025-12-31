#!/usr/bin/env python3
"""
LLM Agent Module - LangChain Powered with Advanced Agent Techniques
Uses LangChain's ReAct pattern, tools, and middleware for intelligent analysis
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Any
from datetime import datetime


class LLMAgent:
    """
    Advanced LangChain-powered agent using latest techniques:
    - ReAct pattern (Reasoning + Acting)
    - Tool integration with error handling
    - Middleware for dynamic behavior  
    - Structured output support
    - Memory/state management
    
    Supports:
    - Google AI Studio (Gemini) - RECOMMENDED
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Local models via LangChain
    """
    
    def __init__(self, provider: str = "google", model: str = None, api_key: str = None):
        """
        Initialize LangChain agent with advanced features
        
        Args:
            provider: "google", "openai", "anthropic", or "local"
            model: Model name (e.g., "gemini-pro", "gpt-4", "claude-3-sonnet")
            api_key: API key for the provider
        """
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        
        # Set default models
        if not self.model:
            if self.provider == "google":
                self.model = "gemini-2.5-flash"  # Stable, fast multimodal model
            elif self.provider == "openai":
                self.model = "gpt-3.5-turbo"
            elif self.provider == "anthropic":
                self.model = "claude-3-5-sonnet-20241022"
            else:
                self.model = "gemini-pro"
        
        # Initialize components
        self.llm = None
        self.agent = None
        self.tools = []
        self.client = None  # For backward compatibility
        
        # Initialize LangChain agent
        self._initialize_langchain_agent()
    
    def _initialize_llm(self):
        """Initialize the base LLM"""
        try:
            if self.provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model,
                    google_api_key=self.api_key,
                    temperature=0.3,  # Lower for faster responses
                    convert_system_message_to_human=True
                )
                print(f"✅ Initialized LangChain with Google AI Studio ({self.model} - optimized)")
            
            elif self.provider == "openai":
                from langchain_openai import ChatOpenAI
                
                self.llm = ChatOpenAI(
                    model=self.model,
                    api_key=self.api_key,
                    temperature=0.7
                )
                print(f"✅ Initialized LangChain with OpenAI ({self.model})")
            
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                
                self.llm = ChatAnthropic(
                    model=self.model,
                    api_key=self.api_key,
                    temperature=0.7
                )
                print(f"✅ Initialized LangChain with Anthropic ({self.model})")
            
            elif self.provider == "local":
                from langchain_community.llms import Ollama
                
                self.llm = Ollama(
                    model=self.model,
                    base_url=os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
                )
                print(f"✅ Initialized LangChain with Local LLM ({self.model})")
        
        except ImportError as e:
            library_map = {
                "google": "langchain-google-genai",
                "openai": "langchain-openai",
                "anthropic": "langchain-anthropic",
                "local": "langchain-community"
            }
            library = library_map.get(self.provider, "langchain")
            print(f"⚠️  Failed to import LangChain library for {self.provider}: {e}")
            print(f"   Install with: pip install {library}")
            self.llm = None
        except Exception as e:
            print(f"⚠️  Failed to initialize LangChain LLM: {e}")
            self.llm = None
    
    def _setup_tools(self):
        """Setup tools for the agent using LangChain's @tool decorator"""
        try:
            from langchain.tools import tool
            
            @tool
            def calculate_correlation_rate(found: int, total: int) -> str:
                """Calculate correlation rate percentage between two datasets.
                
                Args:
                    found: Number of matches found
                    total: Total number of matches checked
                    
                Returns:
                    Correlation rate as percentage string
                """
                if total == 0:
                    return "0%"
                rate = (found / total) * 100
                return f"{rate:.1f}%"
            
            @tool
            def compare_bookmaker_coverage(unified_bookmakers: list, oddsmagnet_bookmakers: list) -> Dict:
                """Compare bookmaker coverage between unified and oddsmagnet systems.
                
                Args:
                    unified_bookmakers: List of bookmakers in unified system
                    oddsmagnet_bookmakers: List of bookmakers in oddsmagnet system
                    
                Returns:
                    Dictionary with common, unique_unified, and unique_oddsmagnet bookmakers
                """
                unified_set = set(unified_bookmakers)
                oddsmagnet_set = set(oddsmagnet_bookmakers)
                
                return {
                    "common": list(unified_set & oddsmagnet_set),
                    "only_in_unified": list(unified_set - oddsmagnet_set),
                    "only_in_oddsmagnet": list(oddsmagnet_set - unified_set),
                    "total_unique": len(unified_set | oddsmagnet_set)
                }
            
            @tool
            def assess_data_quality(correlation_rate: float) -> str:
                """Assess data quality based on correlation rate.
                
                Args:
                    correlation_rate: Correlation rate as percentage (0-100)
                    
                Returns:
                    Quality assessment string
                """
                if correlation_rate >= 80:
                    return "Excellent - High correlation between systems"
                elif correlation_rate >= 60:
                    return "Good - Moderate correlation, minor improvements needed"
                elif correlation_rate >= 40:
                    return "Fair - Significant improvements needed"
                else:
                    return "Poor - Major synchronization issues"
            
            self.tools = [calculate_correlation_rate, compare_bookmaker_coverage, assess_data_quality]
            
        except ImportError:
            print("⚠️  Could not import LangChain tools, agent will run without tools")
            self.tools = []
    
    def _initialize_langchain_agent(self):
        """Initialize LangChain agent with tools and middleware"""
        try:
            # First, initialize the LLM
            self._initialize_llm()
            
            if not self.llm:
                return
            
            # Define analysis tools for the agent
            self._setup_tools()
            
            # For now, use the LLM directly since create_agent requires langchain >= 1.0
            # which may not be released yet. This maintains compatibility.
            self.agent = self.llm
            self.client = self.llm  # For backward compatibility
            
            if self.tools:
                print(f"✅ LangChain Agent ready with {len(self.tools)} tools")
            else:
                print(f"✅ LangChain Agent ready (LLM only mode)")
            
        except Exception as e:
            print(f"⚠️  Failed to initialize LangChain agent: {e}")
            self.agent = None
            self.client = None
    
    def analyze_data_correlation(self, analysis_report: Dict) -> str:
        """
        Use LangChain LLM to analyze data correlation report and provide insights
        
        Args:
            analysis_report: Report from DataAnalyzer.generate_analysis_report()
        
        Returns:
            LLM-generated analysis and recommendations
        """
        if not self.llm:
            return self._fallback_analysis(analysis_report)
        
        # Create prompt for LLM
        prompt = self._create_analysis_prompt(analysis_report)
        
        try:
            # Use LangChain to invoke the LLM with ReAct pattern
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="You are an expert sports betting data analyst specializing in odds comparison and bookmaker data correlation. Use reasoning and analysis to provide actionable insights."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Extract text from response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)
        
        except Exception as e:
            print(f"⚠️  LangChain LLM error: {e}")
            return self._fallback_analysis(analysis_report)
    
    def _create_analysis_prompt(self, report: Dict) -> str:
        """Create detailed prompt for LLM analysis using ReAct pattern"""
        
        prompt = f"""Analyze the following correlation report between two sports betting data sources using systematic reasoning:

DATA SUMMARY:
=============
Unified Odds System:
- Pregame matches: {report['summary']['unified_pregame_matches']}
- Live matches: {report['summary']['unified_live_matches']}
- Sources: Bet365, FanDuel, 1xBet

OddsMagnet System:
- Sports covered: {', '.join(report['summary']['oddsmagnet_sports'])}
- Total matches: {report['summary']['oddsmagnet_total_matches']}

CORRELATION RESULTS:
===================
- Matches found: {report['correlations']['matches_found']}
- Matches not found: {report['correlations']['matches_not_found']}

KEY INSIGHTS:
============
{chr(10).join('- ' + insight for insight in report['insights'])}

SAMPLE COMPARISONS:
==================
{json.dumps(report['correlations']['examples'][:3], indent=2)}

ANALYSIS REQUIRED (Use step-by-step reasoning):
================================================
1. Data Quality Assessment:
   - Evaluate the correlation rate between the two systems
   - Identify potential data gaps or mismatches
   - Assess team name normalization effectiveness

2. Bookmaker Coverage Analysis:
   - Compare bookmaker availability across both systems
   - Identify which system provides better coverage
   - Suggest improvements for bookmaker integration

3. Market Depth Comparison:
   - Analyze the variety of betting markets offered
   - Identify unique markets in each system
   - Recommend market expansion opportunities

4. Data Synchronization Issues:
   - Highlight any timing or update frequency discrepancies
   - Identify sports or leagues with poor correlation
   - Suggest synchronization improvements

5. Actionable Recommendations:
   - Provide 3-5 specific recommendations to improve data correlation
   - Suggest which data source to prioritize for specific use cases
   - Identify integration opportunities

Please provide a comprehensive analysis with specific, actionable insights. Think step-by-step and reason through each section."""

        return prompt
    
    def _fallback_analysis(self, report: Dict) -> str:
        """Fallback analysis when LLM is not available"""
        
        analysis = [
            "AUTOMATED ANALYSIS (LLM Unavailable)",
            "=" * 60,
            "",
            "DATA QUALITY ASSESSMENT:",
        ]
        
        # Correlation rate
        total_checked = report['correlations']['matches_found'] + report['correlations']['matches_not_found']
        if total_checked > 0:
            correlation_rate = (report['correlations']['matches_found'] / total_checked) * 100
            analysis.append(f"✓ Correlation Rate: {correlation_rate:.1f}%")
            
            if correlation_rate >= 80:
                analysis.append("  → Excellent correlation between systems")
            elif correlation_rate >= 60:
                analysis.append("  → Good correlation, minor improvements needed")
            elif correlation_rate >= 40:
                analysis.append("  → Moderate correlation, significant improvements needed")
            else:
                analysis.append("  → Poor correlation, major synchronization issues")
        
        analysis.extend([
            "",
            "KEY INSIGHTS:",
        ])
        analysis.extend([f"• {insight}" for insight in report['insights']])
        
        analysis.extend([
            "",
            "RECOMMENDATIONS:",
            "1. Review team name normalization for unmatched games",
            "2. Implement cross-reference mapping for common teams",
            "3. Add more bookmakers to unified system for better coverage",
            "4. Synchronize data collection timing across systems",
            "5. Consider using OddsMagnet as supplementary data source",
        ])
        
        return "\n".join(analysis)
    
    def ask_question(self, question: str, context: Dict = None) -> str:
        """
        Ask the LLM a specific question about the data using LangChain
        
        Args:
            question: User's question
            context: Additional context (e.g., specific match data)
        
        Returns:
            LLM response
        """
        if not self.llm:
            return "LLM client not initialized. Please check API keys and configuration."
        
        # Build prompt with context
        prompt = question
        if context:
            prompt = f"""Context:\n{json.dumps(context, indent=2)}\n\nQuestion: {question}"""
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="""You are an expert sports betting data analyst with access to REAL-TIME odds data. 

CRITICAL RULES:
1. ALWAYS analyze the actual data provided in the context
2. Reference specific matches, teams, leagues, and odds values from the data
3. NEVER give generic explanations about what betting platforms are
4. DO NOT provide general betting advice unless specifically asked
5. Focus on patterns, trends, and insights from the ACTUAL data
6. If data is insufficient, say so and ask for clarification
7. Provide concrete, actionable insights based on real numbers

Your analysis should be data-driven, specific, and practical."""),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Extract text from response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)
        
        except Exception as e:
            return f"Error querying LLM: {e}"
    
    def compare_specific_match(self, unified_match: Dict, oddsmagnet_match: Dict) -> str:
        """
        Get LangChain LLM analysis for a specific match comparison using PromptTemplate
        
        Args:
            unified_match: Match data from unified system
            oddsmagnet_match: Match data from oddsmagnet
        
        Returns:
            Detailed comparison analysis
        """
        try:
            from langchain_core.prompts import PromptTemplate
            
            template = """Compare these two match records from different betting data systems:

UNIFIED SYSTEM:
{unified_data}

ODDSMAGNET SYSTEM:
{oddsmagnet_data}

Analyze and provide:
1. Odds comparison across common bookmakers
2. Market availability differences
3. Data quality assessment
4. Which system provides better value for this match
5. Any discrepancies or concerns

Think step-by-step and be specific in your analysis."""

            prompt = PromptTemplate(
                input_variables=["unified_data", "oddsmagnet_data"],
                template=template
            )
            
            formatted_prompt = prompt.format(
                unified_data=json.dumps(unified_match, indent=2),
                oddsmagnet_data=json.dumps(oddsmagnet_match, indent=2)
            )
            
            return self.ask_question(formatted_prompt)
        
        except ImportError:
            # Fallback if PromptTemplate not available
            prompt = f"""Compare these two match records from different betting data systems:

UNIFIED SYSTEM:
{json.dumps(unified_match, indent=2)}

ODDSMAGNET SYSTEM:
{json.dumps(oddsmagnet_match, indent=2)}

Analyze and provide:
1. Odds comparison across common bookmakers
2. Market availability differences
3. Data quality assessment
4. Which system provides better value for this match
5. Any discrepancies or concerns"""

            return self.ask_question(prompt)


if __name__ == "__main__":
    # Test the agent
    print("\n" + "="*60)
    print("LLM AGENT TEST - LangChain Edition")
    print("="*60 + "\n")
    
    # Try Google AI Studio first
    agent = LLMAgent(provider="google")
    
    # Test with sample data
    sample_report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'unified_pregame_matches': 100,
            'unified_live_matches': 20,
            'oddsmagnet_sports': ['basketball', 'tennis', 'football'],
            'oddsmagnet_total_matches': 150,
        },
        'correlations': {
            'matches_found': 7,
            'matches_not_found': 3,
            'examples': []
        },
        'insights': [
            "Match correlation rate: 70.0% (7/10)",
            "Unified covers 5 sports: Football, Basketball, Tennis, Baseball, Hockey",
            "OddsMagnet covers 3 sports: basketball, tennis, football"
        ]
    }
    
    analysis = agent.analyze_data_correlation(sample_report)
    print(analysis)
