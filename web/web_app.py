import asyncio
import os
import sys

# This file now lives in web/, but it imports top-level packages
# (agents.orchestrator) that live at the project root one level up.
# Insert the project root into sys.path so those imports resolve whether
# this module is run directly (`python web/web_app.py`), imported as
# `web.web_app` by run_valuagent.py, or loaded by uvicorn/Docker.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="ValuAgent Web Service")

# Allow CORS for ease of access from multiple devices/local setups
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves index.html at root
@app.get("/", response_class=FileResponse)
async def read_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    return index_path

@app.get("/api/value")
async def get_valuation(ticker: str = Query(..., min_length=1, max_length=10)):
    ticker = ticker.strip().upper()
    
    session_service = InMemorySessionService()
    app_name = "valuagent_web"
    user_id = "web_user"

    try:
        session = await session_service.create_session(
            app_name=app_name, user_id=user_id, state={"ticker": ticker}
        )

        # We will use the SequentialAgent containing the memo_writer_agent.
        # It handles missing API key or error cases internally without crashing.
        from agents.orchestrator import root_agent
        
        runner = Runner(agent=root_agent, app_name=app_name, session_service=session_service)

        # Collect event logs/author notes to return to the UI for live progress feedback
        events_log = []

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=f"Value {ticker}")]),
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                text = event.content.parts[0].text
                events_log.append({
                    "author": event.author,
                    "text": text
                })

        final_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session.id
        )
        state = final_session.state

        # Check errors
        if state.get("financial_data_error"):
            return {
                "success": False,
                "error": f"Failed at data retrieval: {state['financial_data_error']}",
                "stage": "data_retrieval"
            }
        if state.get("valuation_result_error"):
            return {
                "success": False,
                "error": f"Failed at valuation: {state['valuation_result_error']}",
                "stage": "valuation"
            }

        company_profile = state.get("financial_data", {}).get("company_profile")
        if company_profile and "name" not in company_profile:
            company_profile = dict(company_profile)
            company_profile["name"] = company_profile.get("long_name")

        response_data = {
            **state,
            "success": True,
            "company_profile": company_profile,
            "events_log": events_log
        }
        return response_data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Internal server error: {str(e)}",
            "stage": "system"
        }

if __name__ == "__main__":
    import uvicorn
    # Default to 8080 for Cloud Run compatibility
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("web.web_app:app", host="127.0.0.1", port=port, reload=True)
