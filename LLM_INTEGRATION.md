# LLM Agent Integration - Real-time AI Analysis

## Overview

The LLM Agent has been successfully integrated with the Live Odds Viewer system to provide real-time AI-powered correlation analysis between **Unified Odds** and **OddsMagnet** data.

## Features

### 🎯 Real-time Analysis

- **Quick Analysis**: Fast correlation metrics (cached for 5 minutes)
- **Full LLM Analysis**: Comprehensive AI-powered insights using Google's Gemini 2.5 Flash
- **Interactive Q&A**: Ask specific questions about the data
- **Live Updates**: Always working with the latest data from both systems

### 📊 Analysis Capabilities

1. **Data Quality Assessment**

   - Correlation rate calculation
   - Team name normalization effectiveness
   - Data gap identification

2. **Bookmaker Coverage**

   - Compare availability across systems
   - Identify coverage gaps
   - Suggest integration improvements

3. **Market Depth Comparison**

   - Analyze betting market variety
   - Identify unique markets
   - Recommend expansion opportunities

4. **Synchronization Analysis**

   - Timing discrepancies
   - Update frequency comparison
   - Sport/league-specific correlation

5. **Actionable Recommendations**
   - Data quality improvements
   - Source prioritization
   - Integration strategies

## Architecture

### Backend Components

```
core/
├── llm_agent_api.py          # API wrapper for LLM agent
└── live_odds_viewer_clean.py # FastAPI endpoints

agent/
├── data_analyzer.py          # Data loading and correlation
├── llm_agent.py              # LangChain-powered agent
└── requirements.txt          # Dependencies

html/
└── llm_analysis.html         # AI Analysis dashboard
```

### API Endpoints

#### GET `/api/llm/status`

Get LLM system status

```json
{
  "analyzer_ready": true,
  "llm_ready": true,
  "llm_provider": "google",
  "llm_model": "gemini-2.5-flash",
  "has_cached_analysis": true,
  "cache_age_seconds": 120
}
```

#### GET `/api/llm/quick-analysis?force=false`

Quick correlation analysis (cached for 5 minutes)

```json
{
  "success": true,
  "cached": false,
  "timestamp": "2025-12-31T12:00:00",
  "unified_total": 2046,
  "oddsmagnet_total": 359,
  "correlation_rate": 0.0,
  "matches_found": 0,
  "matches_not_found": 10,
  "insights": [...]
}
```

#### GET `/api/llm/full-analysis?force=false`

Comprehensive LLM-powered analysis

```json
{
  "success": true,
  "timestamp": "2025-12-31T12:00:00",
  "quick_summary": {...},
  "llm_analysis": "Detailed AI analysis...",
  "has_llm": true
}
```

#### POST `/api/llm/ask`

Ask the LLM a question

```json
// Request
{
  "question": "Why is the correlation rate so low?",
  "context": {...} // Optional
}

// Response
{
  "success": true,
  "question": "Why is the correlation rate so low?",
  "answer": "The low correlation rate...",
  "timestamp": "2025-12-31T12:00:00"
}
```

## Usage

### Access the Dashboard

1. **From Unified Odds Viewer**: Click the "🤖 AI Analysis" button in the top controls
2. **From OddsMagnet Viewer**: Click the "🤖 AI Analysis" button in the filters bar
3. **Direct Access**: Navigate to `/llm-analysis`

### Quick Start

1. **View System Status**

   - Automatically loads on page load
   - Shows analyzer and LLM readiness
   - Displays current model and cache status

2. **Run Quick Analysis**

   - Click "⚡ Quick Analysis" button
   - Get instant correlation metrics
   - View key insights and statistics

3. **Get Full LLM Analysis**

   - Click "🎯 Full LLM Analysis" button
   - Wait 10-30 seconds for comprehensive analysis
   - Read detailed AI-generated insights

4. **Ask Questions**
   - Type your question in the input field
   - Click "🚀 Ask" or press Enter
   - Get AI-powered answers

### Example Questions

- "Why is the correlation rate so low?"
- "Which bookmakers should we prioritize?"
- "What are the main differences between the two systems?"
- "How can we improve data synchronization?"
- "Which sports have the best correlation?"

## Configuration

### Environment Variables

```bash
# Required for LLM features
GOOGLE_API_KEY=your_google_api_key_here
```

### Default Configuration

- **LLM Provider**: Google AI Studio
- **Model**: gemini-2.5-flash
- **Cache Duration**: 5 minutes
- **Temperature**: 0.7
- **API Key**: AIzaSyCqS5F_fbYzB-ZUHKOdGXrVpmRYaQ9jVbU (default)

## Performance

### Response Times

- Quick Analysis: < 1 second (cached)
- Quick Analysis: 1-3 seconds (fresh)
- Full LLM Analysis: 10-30 seconds
- Question Answering: 3-10 seconds

### Caching

- Quick analysis cached for 5 minutes
- Force refresh with `force=true` parameter
- Cache age displayed in UI

### Rate Limits

- Google AI Studio free tier: 60 requests/minute
- Gemini 2.5 Flash: Stable, fast, good rate limits
- Automatic fallback to cached data on rate limit

## Integration Details

### Data Flow

1. **Data Loading**

   ```
   unified_odds.json → DataAnalyzer → Correlation Analysis
   oddsmagnet/*.json → DataAnalyzer → Correlation Analysis
   ```

2. **Analysis Pipeline**

   ```
   Raw Data → DataAnalyzer.generate_report() → LLMAgent.analyze() → API Response
   ```

3. **UI Communication**
   ```
   User Action → Fetch API → FastAPI Endpoint → LLM Agent API → Response
   ```

### Error Handling

- **LLM Unavailable**: Falls back to automated analysis
- **API Key Missing**: Displays configuration instructions
- **Rate Limit Exceeded**: Uses cached data or shows retry message
- **Data Loading Failed**: Clear error messages in UI

## Troubleshooting

### LLM Not Ready

**Problem**: LLM status shows "Not Ready"

**Solutions**:

1. Check GOOGLE_API_KEY environment variable is set
2. Verify API key is valid
3. Check internet connectivity
4. Review server logs for initialization errors

### No Analysis Results

**Problem**: Quick analysis returns empty or error

**Solutions**:

1. Ensure data files exist (unified_odds.json, oddsmagnet/\*.json)
2. Check file permissions
3. Verify data format is correct
4. Force refresh with `force=true` parameter

### Slow Response Times

**Problem**: Full analysis takes > 30 seconds

**Solutions**:

1. Check API quota and rate limits
2. Try quick analysis instead (faster, cached)
3. Verify network connectivity
4. Use cached results when possible

## Development

### Adding New Analysis Features

1. **Extend DataAnalyzer** (`agent/data_analyzer.py`)

   ```python
   def new_analysis_method(self):
       # Your analysis logic
       return results
   ```

2. **Update LLM Agent** (`agent/llm_agent.py`)

   ```python
   def analyze_new_feature(self, data):
       # LLM integration
       return analysis
   ```

3. **Add API Endpoint** (`core/llm_agent_api.py`)

   ```python
   def get_new_analysis(self):
       # Wrapper method
       return self.analyzer.new_analysis_method()
   ```

4. **Expose via FastAPI** (`core/live_odds_viewer_clean.py`)
   ```python
   @app.get("/api/llm/new-feature")
   async def get_new_feature():
       return llm_api.get_new_analysis()
   ```

### Testing

```bash
# Test standalone LLM agent
cd agent
python test_llm_standalone.py

# Test full integration
python quick_start.py

# Start FastAPI server
cd core
python live_odds_viewer_clean.py
```

## Future Enhancements

### Planned Features

1. **Real-time WebSocket Updates**

   - Push analysis updates to connected clients
   - Live correlation monitoring

2. **Historical Trend Analysis**

   - Track correlation changes over time
   - Identify patterns and anomalies

3. **Match-Specific Comparisons**

   - Deep dive into individual match discrepancies
   - Side-by-side odds comparison

4. **Automated Recommendations**

   - Periodic analysis reports
   - Email alerts for significant changes

5. **Multi-Model Support**
   - Switch between different LLM providers
   - Model comparison and benchmarking

### Performance Optimizations

1. **Background Processing**

   - Scheduled analysis updates
   - Pre-computed reports

2. **Advanced Caching**

   - Redis integration
   - Longer cache durations for stable data

3. **Batch Processing**
   - Analyze multiple matches simultaneously
   - Parallel data loading

## Resources

- **LangChain Documentation**: https://docs.langchain.com
- **Google AI Studio**: https://ai.google.dev
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Test Results**: [agent/TEST_RESULTS.md](../agent/TEST_RESULTS.md)
- **Agent Setup**: [agent/SETUP_COMPLETE.md](../agent/SETUP_COMPLETE.md)

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review server logs in terminal
3. Check API responses in browser DevTools
4. Verify all dependencies are installed

---

**Last Updated**: December 31, 2025  
**Status**: ✅ Production Ready  
**Version**: 1.0.0
