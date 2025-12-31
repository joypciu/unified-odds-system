# 🤖 Odds Data Analysis Agent

An intelligent LLM-powered agent that analyzes correlations between your unified odds data and OddsMagnet data, providing actionable insights and recommendations.

## Features

✨ **Data Correlation Analysis**

- Automatically compares unified_odds.json with oddsmagnet data
- Identifies matching and missing games across systems
- Team name normalization with fuzzy matching

🤖 **LLM-Powered Insights**

- Supports OpenAI (GPT-3.5, GPT-4)
- Supports Anthropic (Claude)
- Works with local LLMs (Ollama, LM Studio)
- Fallback to rule-based analysis without LLM

📊 **Comprehensive Reports**

- Match correlation rates
- Bookmaker coverage comparison
- Market depth analysis
- Data quality assessment
- Actionable recommendations

💬 **Interactive Q&A**

- Ask questions about your data
- Get instant analysis
- Context-aware responses

## Installation

### 1. Install Required Dependencies

```bash
# For OpenAI support
pip install openai

# For Anthropic support
pip install anthropic

# Both are optional - agent works without LLM
```

### 2. Configure API Keys (Optional)

```bash
# Copy the template
cp agent/.env.template agent/.env

# Edit .env and add your API key
# OPENAI_API_KEY=sk-your-key-here
# or
# ANTHROPIC_API_KEY=your-key-here
```

Or set environment variables:

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-your-key-here"

# Linux/Mac
export OPENAI_API_KEY="sk-your-key-here"
```

## Usage

### Quick Start

```bash
# Run the agent
python agent/main.py
```

### Step-by-Step Workflow

1. **Setup** - Choose your LLM provider (or skip for basic analysis)
2. **Load Data** - Loads unified_odds.json and oddsmagnet data files
3. **Generate Report** - Creates correlation analysis report
4. **Get LLM Analysis** - Receive AI-powered insights and recommendations
5. **Interactive Mode** - Ask questions about your data
6. **Save Report** - Export analysis to JSON file

### Example Session

```
🤖 ODDS DATA ANALYSIS AGENT
=====================================

LLM Configuration:
  1. OpenAI (requires OPENAI_API_KEY)
  2. Anthropic (requires ANTHROPIC_API_KEY)
  3. Local LLM (e.g., Ollama)
  4. Skip LLM (basic analysis only)

Select provider [1-4]: 1
✅ Initialized OpenAI client with model: gpt-3.5-turbo

MENU
=====================================
1. Load Data
2. Generate Analysis Report
3. Get LLM Analysis
4. Interactive Q&A Mode
5. Save Report to File
6. View Sample Comparisons
7. Exit
=====================================

Select option [1-7]: 1

📊 LOADING DATA
✅ Loaded unified data: 1884 pregame, 162 live matches
✅ Loaded oddsmagnet basketball: 3 matches
✅ Loaded oddsmagnet tennis: 45 matches
✅ All data loaded successfully
```

## Module Overview

### 1. data_analyzer.py

Core data loading and correlation engine:

```python
from agent.data_analyzer import DataAnalyzer

analyzer = DataAnalyzer()
analyzer.load_unified_data()
analyzer.load_oddsmagnet_data()

# Generate comprehensive report
report = analyzer.generate_analysis_report()
```

**Key Features:**

- Team name normalization
- Fuzzy matching (75% similarity threshold)
- Bookmaker comparison
- Market depth analysis

### 2. llm_agent.py

LLM integration for intelligent analysis:

```python
from agent.llm_agent import LLMAgent

# Initialize with OpenAI
agent = LLMAgent(provider="openai", model="gpt-3.5-turbo")

# Analyze correlation report
analysis = agent.analyze_data_correlation(report)

# Ask specific questions
answer = agent.ask_question("Which bookmaker has better coverage?", context=report)
```

**Supported Providers:**

- **OpenAI**: gpt-3.5-turbo, gpt-4, gpt-4-turbo
- **Anthropic**: claude-3-sonnet, claude-3-opus
- **Local**: Any OpenAI-compatible endpoint (Ollama, LM Studio)

### 3. main.py

Interactive CLI application with menu-driven interface.

## Configuration

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo  # Optional

# Anthropic
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-sonnet-20240229  # Optional

# Local LLM
LOCAL_LLM_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=llama2
```

### Analysis Settings

Edit in code or use as parameters:

```python
# In data_analyzer.py
SAMPLE_SIZE = 10  # Number of matches to analyze
SIMILARITY_THRESHOLD = 0.75  # Match correlation threshold (0.0-1.0)
```

## Example Output

### Analysis Report Summary

```
SUMMARY:
--------------------------------------------------------------
Unified System:  1884 pregame + 162 live matches
OddsMagnet:      150 total matches across 5 sports

CORRELATIONS:
--------------------------------------------------------------
Matches found:     7
Matches not found: 3

KEY INSIGHTS:
--------------------------------------------------------------
• Match correlation rate: 70.0% (7/10)
• Unified covers 5 sports: Football, Basketball, Tennis, Baseball, Hockey
• OddsMagnet covers 5 sports: basketball, tennis, tabletennis, americanfootball, all_sports
• OddsMagnet has more market types for matched games
```

### LLM Analysis Example

```
DATA QUALITY ASSESSMENT:
========================
The 70% correlation rate indicates good overlap between systems, though
improvement is possible. The main issues are:

1. Team Name Variations: Some teams use different naming conventions
   (e.g., "Man City" vs "Manchester City")

2. Sport Coverage Gaps: Unified has Baseball/Hockey not in OddsMagnet,
   while OddsMagnet has Table Tennis not in Unified

BOOKMAKER COVERAGE:
===================
- Unified focuses on 3 major bookmakers: Bet365, FanDuel, 1xBet
- OddsMagnet aggregates 9+ bookmakers with broader market depth
- Common bookmakers found in both systems for matched games

RECOMMENDATIONS:
================
1. Implement cross-reference mapping for common teams
2. Add OddsMagnet markets to Unified for market depth
3. Use OddsMagnet as supplementary data source for odds comparison
4. Synchronize data collection timing for better correlation
5. Consider expanding Unified bookmaker coverage
```

## Use Cases

### 1. Data Quality Monitoring

```bash
# Regular automated checks
python agent/main.py --auto-analyze --save-report
```

### 2. Bookmaker Coverage Analysis

```python
from agent import DataAnalyzer, LLMAgent

analyzer = DataAnalyzer()
analyzer.load_unified_data()
analyzer.load_oddsmagnet_data()

report = analyzer.generate_analysis_report()

# Check bookmaker overlap
for example in report['correlations']['examples']:
    print(f"Unified: {example['unified_bookmakers']}")
    print(f"OddsMagnet: {example['oddsmagnet_bookmakers']}")
```

### 3. Market Opportunity Identification

Use LLM to identify which markets are available in OddsMagnet but missing from your unified system.

### 4. Data Integration Planning

Get AI recommendations on how to integrate the two systems effectively.

## Advanced Usage

### Custom Analysis

```python
from agent.data_analyzer import DataAnalyzer

analyzer = DataAnalyzer()
analyzer.load_unified_data()
analyzer.load_oddsmagnet_data()

# Find specific match
unified_match = analyzer.unified_data['pregame_matches'][0]
om_match = analyzer.find_matching_oddsmagnet_match(unified_match)

if om_match:
    comparison = analyzer.compare_odds(unified_match, om_match)
    print(json.dumps(comparison, indent=2))
```

### Using Local LLMs

```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull llama2

# In agent configuration, select option 3 (Local LLM)
# URL: http://localhost:11434/v1
# Model: llama2
```

### Programmatic Usage

```python
from agent import DataAnalyzer, LLMAgent

# Initialize
analyzer = DataAnalyzer()
agent = LLMAgent(provider="openai")

# Load and analyze
analyzer.load_unified_data()
analyzer.load_oddsmagnet_data()
report = analyzer.generate_analysis_report()

# Get insights
insights = agent.analyze_data_correlation(report)
print(insights)

# Ask custom questions
answer = agent.ask_question(
    "What's the best source for NBA games?",
    context=report
)
print(answer)
```

## Output Files

### analysis_report.json

Saved when you select "Save Report to File":

```json
{
  "timestamp": "2025-12-31T10:30:00",
  "summary": {
    "unified_pregame_matches": 1884,
    "unified_live_matches": 162,
    "oddsmagnet_sports": ["basketball", "tennis", "football"],
    "oddsmagnet_total_matches": 150
  },
  "correlations": {
    "matches_found": 7,
    "matches_not_found": 3,
    "examples": [...]
  },
  "insights": [...]
}
```

## Troubleshooting

### "LLM client not initialized"

- Check API key is set correctly
- Verify internet connection (for cloud LLMs)
- For local LLMs, ensure server is running
- Try fallback mode (option 4 during setup)

### "No matches found in correlation"

- Data files may be empty or outdated
- Team name formats might be incompatible
- Try adjusting SIMILARITY_THRESHOLD

### Import Errors

```bash
# Install missing dependencies
pip install openai anthropic
```

## Future Enhancements

- [ ] Automated scheduled analysis
- [ ] Email/Slack notifications for data issues
- [ ] Web dashboard for visualization
- [ ] Historical correlation tracking
- [ ] Multi-language support
- [ ] Custom similarity algorithms
- [ ] Odds arbitrage detection

## Contributing

Feel free to extend the agent with:

- Custom analysis methods
- Additional LLM providers
- New correlation algorithms
- Visualization tools

## License

Part of the Unified Odds System project.

---

**Need Help?** Run with `--help` or check the examples above.
