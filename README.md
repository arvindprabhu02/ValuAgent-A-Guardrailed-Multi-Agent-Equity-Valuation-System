# ValuAgent

**A guardrailed, multi-agent equity valuation system built with Google ADK and MCP — where deterministic Python does all the math, and the LLM only narrates it.**

Built for Kaggle's *AI Agents: Intensive Vibe Coding Course with Google* capstone (Agents for Business track).

## Why

Most "AI valuation" tools let an LLM generate the numbers directly — and that's exactly why they can't be trusted. LLMs are excellent narrators and poor calculators: they interpolate plausible-sounding figures instead of computing exact ones. ValuAgent enforces a hard architectural boundary instead: **every WACC, DCF, DDM, and sensitivity number is produced by deterministic, unit-tested Python. The one LLM in the whole pipeline is explicitly forbidden, at the prompt level, from calculating or inventing any number — it only narrates numbers it's handed.**

## Architecture

A single ADK `SequentialAgent` orchestrator chains five stages through shared session state:

```
DataRetrievalAgent → ValuationAgent → SensitivityAgent → CriticAgent → MemoWriterAgent
     (MCP, no LLM)      (WACC/DCF/DDM,      (WACC×g grid,     (rule-based       (Gemini —
                          no LLM)             no LLM)          guardrails,        the ONLY
                                                                no LLM)           LLM stage)
```

Each agent reads what it needs from session state (written by the agent before it) and writes its own output back. On failure, an agent writes an explicit `<stage>_error` key and returns early rather than crashing — the whole pipeline degrades gracefully instead of throwing an unhandled exception partway through.

### Stage breakdown

| Stage | File(s) | LLM? | What it does |
|---|---|---|---|
| **Data Retrieval** | `agents/data_retrieval_agent.py`, `mcp_server/` | No | Fetches company profile, cash flow, dividends, and price history via a custom **MCP server** (FastMCP) wrapping `yfinance`, consumed through ADK's `McpToolset` over stdio |
| **Valuation** | `agents/valuation_agent.py`, `valuation/wacc.py`, `valuation/dcf.py`, `valuation/ddm.py` | No | CAPM-based WACC, FCFF-derived DCF (Gordon Growth terminal value), and single-stage Gordon Growth DDM — every assumption used is written back to state for auditability |
| **Sensitivity** | `agents/sensitivity_agent.py`, `valuation/sensitivity.py` | No | Re-runs the same trusted DCF function across a WACC × terminal-growth grid — one formula reused, not a second implementation that could drift |
| **Critic / Guardrails** | `agents/critic_agent.py` | No | Rule-based checks: DCF-vs-market divergence, DDM's blind spot for buyback-heavy companies, terminal-value concentration, clamped growth rates |
| **Memo Writer** | `agents/memo_writer_agent.py`, `agents/memo_prompt.py` | **Yes (Gemini)** | The only LLM stage — strictly prompt-constrained to narrate the computed numbers, never to calculate them |
| **Web dashboard** | `web/web_app.py`, `web/index.html` | — | FastAPI backend + dark-mode dashboard that runs the full pipeline and visualizes the result |

## Key engineering notes (proof of work)

- **MCP `CallToolResult` unwrapping** — neither ADK nor FastMCP return a tool's raw Python dict through `McpTool.run_async`; both success and failure come back wrapped in a `CallToolResult`-shaped dict distinguished only by an `isError` flag. An earlier assumption of a simpler shape let a failed fetch silently report as "success" — see `_unwrap_tool_result()` in `agents/data_retrieval_agent.py` for the fix.
- **FCFF sign convention** — `yfinance` reports Capital Expenditure as already negative, so FCFF = `OCF + CapEx`, verified against real AAPL figures.
- **Gemini free-tier hardening** — `gemini-2.0-flash` returned a hard `limit: 0` quota error on the free tier; switched default to `gemini-2.5-flash` (overridable via `VALUAGENT_MEMO_MODEL`) and added `HttpRetryOptions` for automatic exponential-backoff retry on `429`/`503`.
- **Sample real output** — `samples/MSFT_valuation_memo.txt` is an actual pipeline run against live MSFT data, included as proof the full chain (MCP fetch → DCF/DDM → sensitivity → critic flags → Gemini narration) executes end-to-end.

## Features

- 🧮 Deterministic, independently testable valuation core (`valuation/`) — no LLM involved
- 🔌 MCP server exposing financial-data tools over stdio
- 🛡️ Rule-based critic/guardrail layer, not an LLM "critic"
- 💬 Gemini-powered memo writer with strict anti-hallucination prompting
- 🖥️ FastAPI backend + dark-mode glassmorphism web dashboard (`web_app.py`, `index.html`) with a live pipeline stepper, heatmapped sensitivity grid, and critic-flag alerts
- 🐳 `Dockerfile` + Google Cloud Run deployment guide (`cloud_run_deploy.md`)
- ✅ Mocked and live test suites, one per pipeline stage

## Project structure

```
valuagent/
├── agents/                    # ADK agents (4 deterministic + 1 LLM)
│   ├── data_retrieval_agent.py
│   ├── valuation_agent.py
│   ├── sensitivity_agent.py
│   ├── critic_agent.py
│   ├── memo_writer_agent.py
│   ├── memo_prompt.py
│   └── orchestrator.py        # SequentialAgent wiring
├── valuation/                 # Pure-Python financial math (unit-testable, no LLM)
│   ├── wacc.py
│   ├── dcf.py
│   ├── ddm.py
│   └── sensitivity.py
├── mcp_server/                 # MCP server wrapping yfinance
│   ├── server.py
│   └── data_fetch.py
├── web/                         # FastAPI backend + dashboard UI
│   ├── web_app.py
│   └── index.html
├── tests/                       # Mocked + live tests, one set per stage
│   ├── conftest.py               # adds project root to sys.path for imports
│   └── test_*.py
├── docs/
│   └── cloud_run_deploy.md      # Cloud Run deployment steps
├── samples/
│   └── MSFT_valuation_memo.txt  # Sample real pipeline output (proof of work)
├── scripts/
│   └── diagnose_gemini.py       # Gemini API key/quota/model diagnostics
├── run_valuagent.py             # CLI entrypoint (ticker or --web)
├── Dockerfile / .dockerignore
├── .env.example
└── requirements.txt
```

## Quickstart

```bash
git clone <this-repo>
cd valuagent
pip install -r requirements.txt

cp .env.example .env
# add your GEMINI_API_KEY / GOOGLE_API_KEY to .env

# CLI valuation for a ticker
python3 run_valuagent.py AAPL

# Web dashboard at http://127.0.0.1:8080
python3 run_valuagent.py --web
```

Runs without an API key too — the four deterministic agents still execute and print raw valuation numbers; only the memo-writing step is skipped, with a clear message explaining why.

## Running the tests

```bash
pytest tests/test_valuation.py tests/test_data_fetch_mocked.py tests/test_data_retrieval_agent_mocked.py \
       tests/test_valuation_agent.py tests/test_sensitivity_agent.py tests/test_critic_agent.py \
       tests/test_memo_writer_instruction.py tests/test_orchestrator_deterministic_stages.py

# or simply, from the project root:
pytest tests/
```

Live-network variants (`tests/test_data_fetch_live.py`, `tests/test_memo_writer_agent_live.py`) require internet access and a real API key and are excluded from the default mocked run.

## Deployment

```bash
docker build -t valuagent .
```

See `docs/cloud_run_deploy.md` for the full `gcloud` command sequence to deploy to Google Cloud Run.

## Tech stack

Google ADK · Gemini 2.5 Flash · Model Context Protocol (MCP / FastMCP) · yfinance · FastAPI · Docker · Google Cloud Run

## Disclaimer

Educational/prototype project built for a hackathon capstone. Macro assumptions (risk-free rate, market risk premium, cost of debt, tax rate) are documented static defaults, not live market data. This is not investment advice.
