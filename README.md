# ValuAgent - AI Equity Research Platform

ValuAgent is a powerful, autonomous, guardrailed multi-agent system designed for factual equity research. It leverages the Google Agent Development Kit (ADK) to orchestrate a 5-stage pipeline of specialized AI agents, delivering comprehensive, institutional-grade equity analysis straight to a modern Web UI.

## Features

- **5-Stage Multi-Agent Pipeline**: 
  1. *Data Retrieval*: Connects to Yahoo Finance to fetch live historical OHLC data, statements, and key statistics.
  2. *Fundamental Analysis*: Calculates ROCE, ROIC, FCF Yield, and other core profitability/efficiency metrics.
  3. *Industry Comparison*: Benches against peers.
  4. *Risk Critic Guardrails*: Evaluates flags (e.g. debt-to-equity ratio, insider selling, SMA crossovers).
  5. *Memo Writer*: Drafts an executive summary adhering to strict factual guardrails.
- **Facts-Only Policy**: No subjective buy/sell recommendations, DCF models, or target prices. *Here are the facts. You decide.*
- **Live Candlestick Charting**: Real-time interactive 30-day, 1-year, and 5-year historical stock charting using Plotly.js.
- **Progressive Stepping UI**: Sleek Server-Sent Events (SSE) streaming updates the UI instantly as each agent completes its work.
- **Dual-Search Mechanism**: Search easily using ticker symbols (e.g., AAPL) or company names (e.g., Apple).

## Directory Structure

```
valuagent/
-- app/
   -- agents/          # ADK Agent Definitions (Data, Fundamental, Industry, Critic, Memo)
   -- tools/           # Financial API logic (yfinance integration)
   -- web/             # FastAPI backend (web_app.py) and Frontend HTML UI (index.html)
-- tests/               # Pytest suite
-- main.py              # CLI and Web App Entrypoint
-- Dockerfile           # Docker container configuration
-- README.md
-- requirements.txt
```

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/arvindprabhu02/ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System.git
cd ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System

# 2. Create a virtual environment
python -m venv .venv
source .venv/Scripts/activate # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

## Usage

### Run the Web UI
```bash
# Powershell
$env:GROQ_API_KEY="your-api-key"
python main.py --web

# Bash
export GROQ_API_KEY="your-api-key"
python main.py --web
```
Visit http://localhost:8080 in your browser.

### Run via CLI
```bash
python main.py AAPL
```

## Docker

```bash
docker build -t valuagent .
docker run -p 8080:8080 -e GROQ_API_KEY="your-api-key" valuagent
```

## Deployment (Koyeb - Free Tier)

ValuAgent is optimized for deployment on Koyeb, which offers a generous free tier with native Docker support and no credit card required.

### Steps to Deploy:
1. Create a free account at koyeb.com.
2. Click Create Web Service then Docker then Connect your GitHub repository.
3. Set the environment variable GROQ_API_KEY in Koyeb dashboard under Environment Variables.
4. Koyeb auto-detects the Dockerfile, builds the image, and deploys.
5. You will receive a free *.koyeb.app HTTPS URL for your live application!

### Alternative: Google Cloud Run
If you have a GCP billing account linked, Cloud Run provides the most powerful free-tier experience (2 GB RAM, 5-minute timeouts):
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/valuagent
gcloud run deploy valuagent --image gcr.io/YOUR_PROJECT_ID/valuagent --platform managed --region us-central1 --allow-unauthenticated --timeout 300s --memory 1Gi --set-env-vars="GROQ_API_KEY=your_actual_api_key"
```

## Architecture
ValuAgent uses a sequential runner managed by the Google ADK. Each agent strictly passes its output via session state variables. The critic_agent operates as a strict financial guardrail. The LLM is restricted to providing purely factual, backward-looking synthesis.
