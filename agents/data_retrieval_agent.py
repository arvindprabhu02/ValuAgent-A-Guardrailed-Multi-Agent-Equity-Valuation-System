"""
Data Retrieval Agent.

Design note: this agent does NOT use an LLM. Fetching financial data for a
given ticker requires no judgment or reasoning -- it's a deterministic
lookup. Wiring an LLM into this step would only add cost, latency, and a
(small but nonzero) hallucination surface for zero benefit. This is a
direct application of ValuAgent's core principle: LLMs are reserved for
tasks that genuinely need language understanding or generation (see the
Memo Writer Agent); everything else is plain, auditable Python.

This agent still meaningfully demonstrates the ADK + MCP integration
required by the rubric: it connects to the ValuAgent MCP server via ADK's
McpToolset over stdio, and invokes the MCP tools programmatically. The
"agent" here is a BaseAgent subclass participating in the ADK orchestration
graph (readable session state in, readable session state out) -- it's just
not an *LLM* agent, because this step doesn't need one.

Verified against: google-adk==2.3.0 (see README for how to re-verify
against whatever version your team is actually running -- this is a newer
ecosystem and APIs can shift between releases).
"""

import json
import sys
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_session_manager import StdioServerParameters
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# Project root, so the MCP server can be launched consistently regardless of
# the working directory this agent itself is launched from.
_PROJECT_ROOT = Path(__file__).parent.parent


class DataRetrievalAgent(BaseAgent):
    """
    Reads `ticker` from session state, calls the ValuAgent MCP server for
    company profile / cash flow / dividends / price history, and writes the
    combined result to session state under `financial_data`.

    On failure, writes `financial_data_error` instead, so downstream agents
    (and the orchestrator) can detect and handle the failure explicitly
    rather than proceeding with missing data.
    """

    name: str = "data_retrieval_agent"
    description: str = (
        "Fetches company profile, cash flow, dividends, and price history "
        "for a given ticker via the ValuAgent MCP server."
    )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        ticker = ctx.session.state.get("ticker")

        if not ticker:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=(
                        "No ticker found in session state. "
                        "Set state['ticker'] before running this agent."
                    ))],
                ),
                actions=EventActions(
                    state_delta={"financial_data_error": "missing_ticker"}
                ),
            )
            return

        toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    # Launched as a module (-m), not a bare script path, so
                    # the MCP server's package-relative imports resolve
                    # correctly. cwd is set explicitly below so this works
                    # regardless of where this agent process itself was
                    # started from.
                    args=["-m", "mcp_server.server"],
                    cwd=str(_PROJECT_ROOT),
                ),
                timeout=30.0,
            )
        )

        def _unwrap_tool_result(result: object, tool_name: str) -> dict:
            """
            IMPORTANT -- this shape was NOT what it initially appeared to be.

            Neither ADK nor FastMCP return the tool function's Python dict
            directly through McpTool.run_async -- both success AND failure
            come back as an MCP CallToolResult-shaped dict:

                Success: {"content": [{"type": "text", "text": "<JSON string
                          of the actual return value>"}], "isError": False}
                Failure: {"content": [{"type": "text", "text": "Error
                          executing tool X: <message>"}], "isError": True}

            This was confirmed by direct inspection (debug_tool_result.py),
            not by reading ADK's source or docs -- an earlier version of
            this function assumed a simpler {"error": ...} shape based on
            ADK source comments, and that assumption was WRONG: it let a
            fully-failed data fetch report as "success" with silently empty
            fields. Every tool result must be unwrapped through this
            function; never access fields on the raw `result` dict.
            """
            if not isinstance(result, dict) or "isError" not in result:
                raise RuntimeError(
                    f"{tool_name} returned an unexpected shape (not a "
                    f"CallToolResult-like dict): {result!r}"
                )

            content = result.get("content", [])
            text = content[0].get("text") if content else None

            if result.get("isError"):
                raise RuntimeError(f"{tool_name} failed: {text or 'Unknown MCP tool error'}")

            if text is None:
                raise RuntimeError(f"{tool_name} succeeded but returned no content text")

            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError) as parse_exc:
                raise RuntimeError(
                    f"{tool_name} succeeded but its content was not valid JSON: {parse_exc}"
                )

        try:
            tools = await toolset.get_tools()
            tools_by_name = {t.name: t for t in tools}

            tool_context = ToolContext(invocation_context=ctx)

            required_tools = [
                "get_company_profile",
                "get_cash_flow_statement",
                "get_dividend_history",
                "get_price_history",
            ]
            missing = [t for t in required_tools if t not in tools_by_name]
            if missing:
                raise RuntimeError(
                    f"MCP server did not expose expected tools: {missing}. "
                    f"Available tools: {list(tools_by_name.keys())}"
                )

            company_profile = _unwrap_tool_result(
                await tools_by_name["get_company_profile"].run_async(
                    args={"ticker": ticker}, tool_context=tool_context
                ),
                "get_company_profile",
            )

            cash_flow = _unwrap_tool_result(
                await tools_by_name["get_cash_flow_statement"].run_async(
                    args={"ticker": ticker, "years": 4}, tool_context=tool_context
                ),
                "get_cash_flow_statement",
            )

            price_history = _unwrap_tool_result(
                await tools_by_name["get_price_history"].run_async(
                    args={"ticker": ticker, "period": "1y"}, tool_context=tool_context
                ),
                "get_price_history",
            )

            # Dividend history is allowed to fail (non-dividend-paying stocks
            # are a normal, expected case, not a system error). Handle it
            # separately so a missing dividend history doesn't block DCF,
            # which doesn't need it.
            dividend_history = None
            dividend_error = None
            try:
                dividend_history = _unwrap_tool_result(
                    await tools_by_name["get_dividend_history"].run_async(
                        args={"ticker": ticker, "years": 5}, tool_context=tool_context
                    ),
                    "get_dividend_history",
                )
            except Exception as div_exc:
                dividend_error = str(div_exc)
                dividend_history = None

            financial_data = {
                "ticker": ticker,
                "company_profile": company_profile,
                "cash_flow": cash_flow,
                "price_history": price_history,
                "dividend_history": dividend_history,
                "dividend_history_error": dividend_error,
            }

            summary_lines = [f"Retrieved financial data for {ticker}."]
            if dividend_error:
                summary_lines.append(
                    f"Note: no dividend history available ({dividend_error}); "
                    f"DDM will not be applicable for this ticker."
                )

            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=" ".join(summary_lines))],
                ),
                actions=EventActions(
                    state_delta={
                        "financial_data": financial_data,
                        "financial_data_error": None,
                    }
                ),
            )

        except Exception as exc:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Data retrieval failed for {ticker}: {exc}")],
                ),
                actions=EventActions(
                    state_delta={"financial_data_error": str(exc)}
                ),
            )
        finally:
            await toolset.close()
