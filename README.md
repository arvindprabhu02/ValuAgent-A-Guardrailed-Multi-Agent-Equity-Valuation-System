# ValuAgent - AI Equity Research Platform

ValuAgent is a powerful, autonomous, guardrailed multi-agent system designed for factual equity research. It leverages the Google Agent Development Kit (ADK) to orchestrate a 5-stage pipeline of specialized AI agents, delivering comprehensive, institutional-grade equity analysis straight to a modern Web UI.

## Features

- **5-Stage Multi-Agent Pipeline**: 
  1. *Data Retrieval*: Connects to Yahoo Finance to fetch live historical OHLC data, statements, and key statistics.
  2. *Fundamental Analysis*: Calculates ROCE, ROIC, FCF Yield, and other core profitability/efficiency metrics.
  3. *Industry Comparison*: Benches against peers.
  4. *Risk Critic Guardrails*: Evaluates flags (e.g. debt-to-equity ratio, insider selling, SMA crossovers).
  5. *Memo Writer*: Drafts an executive summary adhering to strict factual guardrails.
- **Facts-Only Policy**: No subjective buy/sell recommendations, DCF models, or target prices. "Here are the facts. You decide."
- **Live Candlestick Charting**: Real-time interactive 5-year and 30-day historical stock charting using Plotly.js.
- **Progressive Stepping UI**: Sleek Server-Sent Events (SSE) streaming updates the UI instantly as each agent completes its work.
- **Dual-Search Mechanism**: Search easily using ticker symbols (e.g., AAPL) or company names (e.g., Apple).

## Directory Structure

\\\
valuagent/
+-- app/
¦   +-- agents/          # ADK Agent Definitions (Data, Fundamental, Industry, Critic, Memo)
¦   +-- tools/           # Financial API logic (yfinance integration)
¦   +-- web/             # FastAPI backend (web_app.py) & Frontend HTML UI (index.html)
+-- tests/               # Pytest suite
+-- main.py              # CLI and Web App Entrypoint
+-- README.md            
+-- requirements.txt     
\\\

## Installation

\\\ash
# 1. Clone the repository
git clone https://github.com/your-username/ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System.git
cd ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System

# 2. Create a virtual environment
python -m venv .venv
source .venv/Scripts/activate # Windows
# source .venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt
\\\

## Usage

### Run the Web UI
Set your LLM API Key (e.g., Groq) and launch the FastAPI server:
\\\ash
# Powershell
\="your-api-key"
python main.py --web

# Bash
export GROQ_API_KEY="your-api-key"
python main.py --web
\\\
Visit \http://localhost:8080\ in your browser to access the ValuAgent Research Dashboard.

### Run via CLI
\\\ash
python main.py AAPL
\\\

## Architecture & Guardrails
ValuAgent uses a sequential runner managed by the Google ADK. Each agent strictly passes its output via session state variables. The \critic_agent\ operates as a strict financial guardrail, ensuring qualitative thresholds aren't blindly ignored. The LLM is restricted to providing purely factual, backward-looking synthesis.
