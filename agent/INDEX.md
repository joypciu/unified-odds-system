# Agent Directory Index

## 📁 Directory Structure

```
agent/
├── __init__.py              # Package initialization
├── data_analyzer.py         # Core data loading and correlation analysis
├── llm_agent.py            # LLM integration (OpenAI, Anthropic, Local)
├── main.py                 # Interactive CLI application
├── quick_start.py          # Quick demo script
├── requirements.txt        # Agent-specific dependencies
├── .env.template           # Configuration template
├── README.md              # Comprehensive documentation
└── INDEX.md               # This file
```

## 🎯 Quick Reference

### Run the Agent

```bash
python agent/main.py
```

### Quick Demo

```bash
python agent/quick_start.py
```

### Install Dependencies

```bash
pip install -r agent/requirements.txt
```

## 📄 File Descriptions

### data_analyzer.py

**Purpose:** Core data analysis engine

**Key Classes:**

- `DataAnalyzer` - Loads and correlates unified/oddsmagnet data

**Key Methods:**

- `load_unified_data()` - Load data/unified_odds.json
- `load_oddsmagnet_data()` - Load bookmakers/oddsmagnet/\*.json
- `find_matching_oddsmagnet_match()` - Fuzzy match finder
- `compare_odds()` - Compare odds between systems
- `generate_analysis_report()` - Generate comprehensive report

**Features:**

- Team name normalization
- Fuzzy matching (75% threshold)
- Bookmaker comparison
- Market depth analysis

---

### llm_agent.py

**Purpose:** LLM integration for intelligent analysis

**Key Classes:**

- `LLMAgent` - Wrapper for various LLM providers

**Supported Providers:**

- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Local LLMs (Ollama, LM Studio)

**Key Methods:**

- `analyze_data_correlation()` - Get AI insights on correlation report
- `ask_question()` - Interactive Q&A
- `compare_specific_match()` - Detailed match comparison

**Features:**

- Automatic provider detection
- Fallback to rule-based analysis
- Context-aware responses

---

### main.py

**Purpose:** Interactive CLI application

**Features:**

- Menu-driven interface
- Step-by-step workflow
- Interactive Q&A mode
- Report saving

**Menu Options:**

1. Load Data
2. Generate Analysis Report
3. Get LLM Analysis
4. Interactive Q&A Mode
5. Save Report to File
6. View Sample Comparisons
7. Exit

---

### quick_start.py

**Purpose:** Quick demonstration script

**What it does:**

1. Loads all data sources
2. Generates correlation report
3. Shows summary statistics
4. Attempts LLM analysis (if API keys available)
5. Displays sample comparison

**Usage:**

```bash
python agent/quick_start.py
```

---

## 🚀 Getting Started

### Option 1: Quick Demo (No Configuration)

```bash
python agent/quick_start.py
```

Works immediately, uses basic analysis if no API keys set.

### Option 2: Full Interactive Experience

```bash
# Install dependencies
pip install openai anthropic python-dotenv

# Set API key (choose one)
export OPENAI_API_KEY="your-key-here"
# or
export ANTHROPIC_API_KEY="your-key-here"

# Run agent
python agent/main.py
```

### Option 3: Programmatic Usage

```python
from agent import DataAnalyzer, LLMAgent

# Load and analyze
analyzer = DataAnalyzer()
analyzer.load_unified_data()
analyzer.load_oddsmagnet_data()
report = analyzer.generate_analysis_report()

# Get AI insights
agent = LLMAgent(provider="openai")
insights = agent.analyze_data_correlation(report)
print(insights)
```

## 📊 What the Agent Does

### Data Analysis

- Compares unified odds (Bet365, FanDuel, 1xBet) with OddsMagnet data
- Identifies matching games using intelligent team name normalization
- Calculates correlation rates and identifies gaps

### Correlation Metrics

- **Match Rate:** Percentage of games found in both systems
- **Bookmaker Overlap:** Common bookmakers across systems
- **Market Coverage:** Betting market availability comparison
- **Data Quality:** Team name matching accuracy

### LLM Insights

The AI agent provides:

- Data quality assessment
- Bookmaker coverage analysis
- Market depth comparison
- Synchronization issue identification
- Actionable recommendations

## 🔧 Configuration

### API Keys (.env file)

```env
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
LOCAL_LLM_URL=http://localhost:11434/v1
```

### Analysis Parameters

Edit in `data_analyzer.py`:

- `SAMPLE_SIZE = 10` - Matches to analyze
- `SIMILARITY_THRESHOLD = 0.75` - Matching threshold

## 📈 Example Output

```
SUMMARY:
Unified:     1884 pregame + 162 live matches
OddsMagnet:  150 matches across 5 sports

CORRELATIONS:
Match Rate:  70.0% (7/10)

KEY INSIGHTS:
• Unified covers 5 sports: Football, Basketball, Tennis, Baseball, Hockey
• OddsMagnet covers 5 sports: basketball, tennis, tabletennis, americanfootball
• OddsMagnet has more market types for matched games
```

## 🎓 Use Cases

1. **Data Quality Monitoring** - Regular checks for data consistency
2. **Bookmaker Coverage Analysis** - Identify bookmaker gaps
3. **Market Opportunity Detection** - Find unique markets
4. **Integration Planning** - Get AI recommendations for system integration
5. **Arbitrage Detection** - Compare odds across systems

## 🔍 Troubleshooting

### No data loaded

- Ensure `data/unified_odds.json` exists
- Ensure `bookmakers/oddsmagnet/*.json` files exist
- Run data collection scripts first

### LLM not working

- Check API key is set correctly
- Verify internet connection (cloud LLMs)
- Try fallback mode (option 4)

### Import errors

```bash
pip install -r agent/requirements.txt
```

## 📚 Further Reading

- [README.md](README.md) - Comprehensive documentation
- [../docs/API_REFERENCE.md](../docs/API_REFERENCE.md) - API documentation
- [../docs/PROJECT_STRUCTURE.md](../docs/PROJECT_STRUCTURE.md) - Project overview

## 🤝 Contributing

To extend the agent:

1. Add new analysis methods to `data_analyzer.py`
2. Add new LLM providers to `llm_agent.py`
3. Enhance CLI features in `main.py`
4. Update documentation

## ⚡ Quick Commands

```bash
# Run interactive agent
python agent/main.py

# Quick demo
python agent/quick_start.py

# Test data analyzer only
python agent/data_analyzer.py

# Test LLM agent only
python agent/llm_agent.py
```

---

**Last Updated:** December 31, 2025
