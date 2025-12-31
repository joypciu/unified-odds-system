"""
LLM Agent API Integration
Provides real-time LLM analysis for the odds comparison UI
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, List
import json
from datetime import datetime

# Add agent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from data_analyzer import DataAnalyzer
from llm_agent import LLMAgent

class LLMAgentAPI:
    """
    API wrapper for LLM Agent to integrate with FastAPI backend
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.analyzer = None
        self.llm_agent = None
        self.last_analysis = None
        self.last_analysis_time = None
        self._data_cache = None
        self._data_cache_time = None
        self._cache_ttl = 60  # Cache data for 60 seconds
        self._initialize()
    
    def _initialize(self):
        """Initialize the data analyzer and LLM agent"""
        try:
            # Initialize data analyzer
            self.analyzer = DataAnalyzer(str(self.base_dir))
            print("✅ LLM Agent API: Data analyzer initialized")
            
            # Initialize LLM agent with Google API key
            api_key = os.getenv('GOOGLE_API_KEY', 'AIzaSyCqS5F_fbYzB-ZUHKOdGXrVpmRYaQ9jVbU')
            if api_key:
                try:
                    self.llm_agent = LLMAgent(provider='google', api_key=api_key)
                    print("✅ LLM Agent API: LLM agent initialized with Google AI Studio")
                except Exception as e:
                    print(f"⚠️  LLM Agent API: Could not initialize LLM: {e}")
                    self.llm_agent = None
            else:
                print("⚠️  LLM Agent API: No API key found, LLM features disabled")
                
        except Exception as e:
            print(f"❌ LLM Agent API: Initialization failed: {e}")
            self.analyzer = None
            self.llm_agent = None
    
    def load_data(self) -> Dict:
        """Load and analyze current data"""
        if not self.analyzer:
            return {"error": "Analyzer not initialized"}
        
        try:
            # Load unified and oddsmagnet data
            unified_data = self.analyzer.load_unified_data()
            oddsmagnet_data = self.analyzer.load_oddsmagnet_data()
            
            if not unified_data and not oddsmagnet_data:
                return {"error": "Failed to load data"}
            
            # Calculate match counts
            unified_count = len(unified_data.get('pregame_matches', [])) + len(unified_data.get('live_matches', []))
            oddsmagnet_count = sum(
                data.get('matches_count', len(data.get('matches', []))) 
                for data in oddsmagnet_data.values()
            )
            
            # Generate analysis report
            report = self.analyzer.generate_analysis_report()
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "unified_matches": unified_count,
                "oddsmagnet_matches": oddsmagnet_count,
                "report": report
            }
        except Exception as e:
            return {"error": f"Data loading failed: {str(e)}"}
    
    def get_quick_analysis(self, force_refresh: bool = False) -> Dict:
        """
        Get quick correlation analysis (cached for 5 minutes unless forced)
        
        Args:
            force_refresh: Force new analysis even if cached
            
        Returns:
            Dictionary with analysis results
        """
        # Check cache (5 minutes)
        if not force_refresh and self.last_analysis and self.last_analysis_time:
            time_since_last = (datetime.now() - self.last_analysis_time).total_seconds()
            if time_since_last < 300:  # 5 minutes
                return {
                    "success": True,
                    "cached": True,
                    "cache_age_seconds": int(time_since_last),
                    **self.last_analysis
                }
        
        # Load fresh data
        data_result = self.load_data()
        if "error" in data_result:
            return data_result
        
        report = data_result["report"]
        
        # Calculate correlation rate
        total_checked = report['correlations']['matches_found'] + report['correlations']['matches_not_found']
        correlation_rate = 0.0
        if total_checked > 0:
            correlation_rate = (report['correlations']['matches_found'] / total_checked) * 100
        
        # Prepare quick summary
        analysis = {
            "timestamp": data_result["timestamp"],
            "unified_total": data_result["unified_matches"],
            "oddsmagnet_total": data_result["oddsmagnet_matches"],
            "correlation_rate": round(correlation_rate, 1),
            "matches_found": report['correlations']['matches_found'],
            "matches_not_found": report['correlations']['matches_not_found'],
            "unified_sports": report['summary'].get('unified_sports', []),
            "oddsmagnet_sports": report['summary'].get('oddsmagnet_sports', []),
            "insights": report.get('insights', [])
        }
        
        # Cache the result
        self.last_analysis = analysis
        self.last_analysis_time = datetime.now()
        
        return {
            "success": True,
            "cached": False,
            **analysis
        }
    
    def get_llm_analysis(self, force_refresh: bool = False) -> Dict:
        """
        Get comprehensive LLM-powered analysis
        
        Args:
            force_refresh: Force new LLM analysis
            
        Returns:
            Dictionary with LLM analysis
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available",
                "message": "Please set GOOGLE_API_KEY environment variable"
            }
        
        # Get quick analysis first
        quick_result = self.get_quick_analysis(force_refresh)
        if not quick_result.get("success"):
            return quick_result
        
        # Load full report
        data_result = self.load_data()
        if "error" in data_result:
            return data_result
        
        try:
            # Get LLM analysis
            llm_analysis = self.llm_agent.analyze_data_correlation(data_result["report"])
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "quick_summary": quick_result,
                "llm_analysis": llm_analysis,
                "has_llm": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"LLM analysis failed: {str(e)}",
                "quick_summary": quick_result,
                "has_llm": False
            }
    
    def _get_cached_data(self):
        """Get cached data or load fresh if expired"""
        now = datetime.now()
        
        # Check if cache is valid
        if (self._data_cache is not None and 
            self._data_cache_time is not None and 
            (now - self._data_cache_time).total_seconds() < self._cache_ttl):
            return self._data_cache
        
        # Load fresh data
        unified_data = self.analyzer.load_unified_data() if self.analyzer else None
        oddsmagnet_data = self.analyzer.load_oddsmagnet_data() if self.analyzer else None
        
        self._data_cache = (unified_data, oddsmagnet_data)
        self._data_cache_time = now
        
        return self._data_cache
    
    def ask_llm_question(self, question: str, context: Optional[Dict] = None) -> Dict:
        """
        Ask the LLM a specific question about the data
        
        Args:
            question: User's question
            context: Additional context (optional)
            
        Returns:
            Dictionary with LLM response
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available"
            }
        
        try:
            # Load current data to provide real context
            if context is None:
                context = {}
                
                # Use cached data to speed up responses
                unified_data, oddsmagnet_data = self._get_cached_data()
                
                if unified_data:
                    # Get minimal sample matches for context (reduced from 10/5 to 3/2)
                    pregame_matches = unified_data.get('pregame_matches', [])[:3]
                    live_matches = unified_data.get('live_matches', [])[:2]
                    
                    context['unified'] = {
                        'total_pregame': len(unified_data.get('pregame_matches', [])),
                        'total_live': len(unified_data.get('live_matches', [])),
                        'samples': pregame_matches + live_matches
                    }
                
                if oddsmagnet_data:
                    # Get minimal sample from top sport only for speed
                    top_sport = None
                    max_matches = 0
                    
                    for sport, data in oddsmagnet_data.items():
                        matches = data.get('matches', [])
                        if len(matches) > max_matches:
                            max_matches = len(matches)
                            top_sport = sport
                    
                    if top_sport:
                        context['oddsmagnet'] = {
                            'total_sports': len(oddsmagnet_data),
                            'top_sport': top_sport,
                            'total_matches': max_matches,
                            'samples': oddsmagnet_data[top_sport].get('matches', [])[:3]
                        }
            
            # Add brief instruction to analyze actual data
            enhanced_question = f"""Using the real odds data provided, answer: {question}

Data context:

User Question: {question}

If the data context is insufficient, ask for clarification. Do not make up generic information."""

            response = self.llm_agent.ask_question(enhanced_question, context)
            return {
                "success": True,
                "question": question,
                "answer": response,
                "timestamp": datetime.now().isoformat(),
                "used_real_data": bool(context.get('unified_sample') or context.get('oddsmagnet_sample'))
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Question processing failed: {str(e)}"
            }
    
    def get_match_comparison(self, unified_match_id: str, oddsmagnet_match_id: str) -> Dict:
        """
        Get detailed LLM comparison of two specific matches
        
        Args:
            unified_match_id: Match ID from unified system
            oddsmagnet_match_id: Match ID from oddsmagnet
            
        Returns:
            Dictionary with match comparison
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available"
            }
        
        # TODO: Implement match lookup by ID
        # For now, return placeholder
        return {
            "success": False,
            "error": "Feature under development"
        }
    
    def get_status(self) -> Dict:
        """Get current status of LLM Agent API"""
        return {
            "analyzer_ready": self.analyzer is not None,
            "llm_ready": self.llm_agent is not None,
            "has_cached_analysis": self.last_analysis is not None,
            "cache_age_seconds": int((datetime.now() - self.last_analysis_time).total_seconds()) if self.last_analysis_time else None,
            "llm_provider": "google" if self.llm_agent else None,
            "llm_model": self.llm_agent.model if self.llm_agent else None
        }


# Singleton instance
_llm_agent_api = None

def get_llm_agent_api(base_dir: Path) -> LLMAgentAPI:
    """Get or create singleton LLM Agent API instance"""
    global _llm_agent_api
    if _llm_agent_api is None:
        _llm_agent_api = LLMAgentAPI(base_dir)
    return _llm_agent_api
