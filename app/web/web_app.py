"""
FastAPI REST Service for ValuAgent.
Serves web/index.html and endpoints for ticker valuation runs.
"""

import os
import uuid
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from app.agents.orchestrator import root_agent

app = FastAPI(title="ValuAgent — Equity Research Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
APP_NAME = "valuagent_web"
USER_ID = "web_user"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/value_stream")
async def run_valuation_stream(ticker: str):
    if not ticker or not ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker symbol is required.")

    clean_ticker = ticker.strip().upper()
    unique_session_id = f"session_{clean_ticker}_{uuid.uuid4().hex[:8]}"

    async def event_generator():
        session = await session_service.create_session(
            session_id=unique_session_id,
            app_name=APP_NAME,
            user_id=USER_ID,
            state={"ticker": clean_ticker},
        )

        runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)
        input_content = Content(parts=[Part(text="Run Equity Research")])

        events_log = []
        memo_text = None
        try:
            async for event in runner.run_async(session_id=session.id, user_id=USER_ID, new_message=input_content):
                actions = getattr(event, "actions", None)
                if actions and getattr(actions, "state_delta", None):
                    session.state.update(actions.state_delta)

                author = getattr(event, "author", "system")
                content = getattr(event, "content", None)
                extracted_text = ""
                if content and hasattr(content, "parts") and content.parts:
                    extracted_text = "".join(getattr(p, "text", "") for p in content.parts if getattr(p, "text", None))
                elif getattr(event, "text", None):
                    extracted_text = event.text

                if author == "memo_writer_agent" and extracted_text:
                    memo_text = extracted_text

                events_log.append({"author": author, "text": extracted_text or str(event)})
                
                # Yield progress event
                yield f"data: {json.dumps({'type': 'progress', 'author': author})}\n\n"
        except Exception as e:
            events_log.append({"author": "system", "text": f"Execution error: {str(e)}"})
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            return

        final_session = await session_service.get_session(session_id=session.id, app_name=APP_NAME, user_id=USER_ID)
        state = final_session.state

        if state.get("financial_data_error"):
            yield f"data: {json.dumps({'type': 'error', 'error': state['financial_data_error']})}\n\n"
            return

        fin_data = state.get("financial_data") or {}
        profile = fin_data.get("company_profile") or {}

        if not memo_text:
            memo_text = state.get("memo_text")

        if memo_text:
            memo_text = re.sub(r"<think>.*?</think>", "", memo_text, flags=re.DOTALL)
            heading_match = re.search(r"(###|\*\*1\.|\#\#|\#\s|Executive Summary)", memo_text)
            if heading_match and heading_match.start() > 0:
                memo_text = memo_text[heading_match.start():]
            memo_text = memo_text.strip()

        final_data = {
            "type": "result",
            "success": True,
            "ticker": clean_ticker,
            "company_profile": profile,
            "ohlc_data": fin_data.get("ohlc_data", {}),
            "fundamental_analysis": state.get("fundamental_analysis"),
            "industry_comparison": state.get("industry_comparison"),
            "critic_flags": state.get("critic_flags", []),
            "memo_text": memo_text,
            "events_log": events_log,
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/value")
async def run_valuation(ticker: str):
    if not ticker or not ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker symbol is required.")

    clean_ticker = ticker.strip().upper()
    # Always create a fresh unique session ID for each request
    unique_session_id = f"session_{clean_ticker}_{uuid.uuid4().hex[:8]}"

    session = await session_service.create_session(
        session_id=unique_session_id,
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"ticker": clean_ticker},
    )

    runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)
    input_content = Content(parts=[Part(text="Run Equity Research")])

    events_log = []
    memo_text = None
    try:
        async for event in runner.run_async(session_id=session.id, user_id=USER_ID, new_message=input_content):
            actions = getattr(event, "actions", None)
            if actions and getattr(actions, "state_delta", None):
                session.state.update(actions.state_delta)

            author = getattr(event, "author", "system")
            content = getattr(event, "content", None)
            extracted_text = ""
            if content and hasattr(content, "parts") and content.parts:
                extracted_text = "".join(getattr(p, "text", "") for p in content.parts if getattr(p, "text", None))
            elif getattr(event, "text", None):
                extracted_text = event.text

            if author == "memo_writer_agent" and extracted_text:
                memo_text = extracted_text

            events_log.append({"author": author, "text": extracted_text or str(event)})
    except Exception as e:
        events_log.append({"author": "system", "text": f"Execution error: {str(e)}"})

    final_session = await session_service.get_session(session_id=session.id, app_name=APP_NAME, user_id=USER_ID)
    state = final_session.state

    if state.get("financial_data_error"):
        return {
            "success": False,
            "error": state["financial_data_error"],
            "events_log": events_log,
        }

    fin_data = state.get("financial_data") or {}
    profile = fin_data.get("company_profile") or {}

    if not memo_text:
        memo_text = state.get("memo_text")

    if memo_text:
        # Strip any internal thought tags if present
        import re
        memo_text = re.sub(r"<think>.*?</think>", "", memo_text, flags=re.DOTALL)
        # If output contains preamble like "Let's write...", find the first heading
        heading_match = re.search(r"(###|\*\*1\.|\#\#|\#\s|Executive Summary)", memo_text)
        if heading_match and heading_match.start() > 0:
            memo_text = memo_text[heading_match.start():]
        memo_text = memo_text.strip()

    return {
        "success": True,
        "ticker": clean_ticker,
        "company_profile": profile,
        "ohlc_data": fin_data.get("ohlc_data", {}),
        "fundamental_analysis": state.get("fundamental_analysis"),
        "industry_comparison": state.get("industry_comparison"),
        "critic_flags": state.get("critic_flags", []),
        "memo_text": memo_text,
        "events_log": events_log,
    }
