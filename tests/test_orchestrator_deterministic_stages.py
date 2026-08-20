"""
Integration test for the 4-stage deterministic pipeline (excluding LLM memo writer).
"""

import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from google.adk.agents import SequentialAgent
from app.agents.data_retrieval_agent import DataRetrievalAgent
from app.agents.fundamental_analysis_agent import FundamentalAnalysisAgent
from app.agents.industry_comparison_agent import IndustryComparisonAgent
from app.agents.critic_agent import CriticAgent


def test_deterministic_pipeline():
    async def _test():
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            session_id="test_pipeline_session",
            app_name="agents",
            user_id="test_user",
            state={"ticker": "AAPL"}
        )

        pipeline = SequentialAgent(
            name="deterministic_pipeline",
            sub_agents=[
                DataRetrievalAgent(),
                FundamentalAnalysisAgent(),
                IndustryComparisonAgent(),
                CriticAgent(),
            ],
        )

        runner = Runner(agent=pipeline, session_service=session_service, app_name="agents")
        msg = Content(parts=[Part(text="Run Pipeline")])

        async for _ in runner.run_async(session_id=session.id, user_id="test_user", new_message=msg):
            pass

        final_session = await session_service.get_session(session_id=session.id, app_name="agents", user_id="test_user")
        state = final_session.state

        assert state.get("financial_data_error") is None
        assert "fundamental_analysis" in state
        assert "industry_comparison" in state
        assert "critic_flags" in state

    asyncio.run(_test())
