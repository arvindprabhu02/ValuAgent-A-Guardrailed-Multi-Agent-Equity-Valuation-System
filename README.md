# StockLens - AI Equity Research Platform

StockLens is a powerful, autonomous, guardrailed multi-agent system designed for factual equity research. It leverages the Google Agent Development Kit (ADK) to orchestrate a 5-stage pipeline of specialized AI agents, delivering comprehensive, institutional-grade equity analysis straight to a modern Web UI.

## Features

- **5-Stage Multi-Agent Pipeline**:
  1. *Data Retrieval*: Connects to Yahoo Finance to fetch live historical OHLC data, financial statements, and key statistics.
  2. *Fundamental Analysis*: Calculates ROCE, ROIC, FCF Yield, P/E, and other core profitability and efficiency metrics.
  3. *Industry Comparison*: Benchmarks the company against sector peers.
  4. *Risk Critic Guardrails*: Evaluates financial health flags (e.g. debt-to-equity ratio, insider selling, SMA crossovers).
  5. *Memo Writer*: Drafts an executive research summary adhering to strict factual guardrails.
- **Facts-Only Policy**: No subjective buy/sell recommendations, DCF models, or target prices. *Here are the facts. You decide.*
- **Live Candlestick Charting**: Interactive 30-day, 1-year, and 5-year historical stock charting powered by Plotly.js.
- **Real-Time Progress**: Server-Sent Events (SSE) streaming updates the UI live as each agent completes its work.
- **Smart Search**: Search using ticker symbols (e.g. AAPL) or company names (e.g. Apple Inc.).

## Directory Structure

```
stocklens/
|-- app/
|   |-- agents/        # ADK Agent Definitions (Data, Fundamental, Industry, Critic, Memo)
|   |-- tools/         # Financial data layer (yfinance integration)
|   |-- web/           # FastAPI backend (web_app.py) and Frontend UI (index.html)
|-- tests/             # Pytest suite
|-- main.py            # CLI and Web App entrypoint
|-- Dockerfile         # Docker container configuration
|-- requirements.txt
```

## Installation

```bash
git clone https://github.com/arvindprabhu02/ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System.git
cd ValuAgent-A-Guardrailed-Multi-Agent-Equity-Valuation-System
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## Usage

### Web UI
```bash
$env:GROQ_API_KEY="your-api-key"    # Powershell
python main.py --web
```
Visit http://localhost:8080 in your browser.

### CLI
```bash
python main.py AAPL
```

## Docker

```bash
docker build -t stocklens .
docker run -p 8080:8080 -e GROQ_API_KEY="your-api-key" stocklens
```

## Deployment (Render - Free Tier)

StockLens is optimized for deployment on Render.com, which offers a free tier with native Docker support and no credit card required.

### Steps:
1. Sign up at render.com with your GitHub account (free, no credit card).
2. Click **New +** then **Web Service**.
3. Connect your GitHub repository and select this project.
4. Set Runtime to **Docker** (auto-detected from Dockerfile).
5. Choose the **Free** instance type.
6. Add environment variable: Key = `GROQ_API_KEY`, Value = your API key.
7. Click **Create Web Service**. Render builds and deploys in ~5 minutes.
8. You receive a live URL like `https://stocklens.onrender.com`.

> Note: On the free tier, the app sleeps after 15 minutes of inactivity. The first visit after sleep takes ~30-60 seconds to wake up. This is normal for all free hosting platforms.

### Alternative: Google Cloud Run
If you have a GCP billing account, Cloud Run provides the best free-tier experience (2 GB RAM, 5-min timeouts):
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stocklens
gcloud run deploy stocklens --image gcr.io/YOUR_PROJECT_ID/stocklens --platform managed --region us-central1 --allow-unauthenticated --timeout 300s --memory 1Gi --set-env-vars="GROQ_API_KEY=your_key"
```

## Architecture
StockLens uses a sequential runner managed by the Google ADK. Each agent passes its output via session state variables. The critic_agent operates as a strict financial guardrail. The LLM is restricted to providing purely factual, backward-looking synthesis.
