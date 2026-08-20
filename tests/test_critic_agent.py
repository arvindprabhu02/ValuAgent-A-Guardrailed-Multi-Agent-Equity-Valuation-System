"""
Unit tests for CriticAgent under the Facts-Only architecture.
"""

import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from app.agents.critic_agent import CriticAgent


def test_critic_agent_flags():
    async def _test():
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            session_id="test_critic_session",
            app_name="agents",
            user_id="test_user",
            state={
                "ticker": "TESTCO",
                "fundamental_analysis": {
                    "balance_sheet": {
                        "current_ratio": 0.8,
                        "debt_to_equity": 2.5,
                        "interest_coverage": 2.0,
                    },
                    "profitability": {
                        "net_margin": 3.0,
                        "revenue_growth_yoy": 5.0,
                    },
                    "cash_flow": {
                        "free_cash_flow": -100.0,
                        "fcf_conversion": 0.4,
                    },
                    "per_share": {
                        "eps_growth_yoy": 30.0,
                    },
                    "governance": {
                        "recent_insider_activity": "NET SELLING",
                    },
                    "dividend": {
                        "payout_ratio": 90.0,
                    },
                }
            }
        )

        agent = CriticAgent()
        runner = Runner(agent=agent, session_service=session_service, app_name="agents")
        msg = Content(parts=[Part(text="Run Critic")])

        async for _ in runner.run_async(session_id=session.id, user_id="test_user", new_message=msg):
            pass

        final_session = await session_service.get_session(session_id=session.id, app_name="agents", user_id="test_user")
        flags = final_session.state.get("critic_flags", [])

        assert len(flags) >= 8
        checks_triggered = [f["check"] for f in flags]
        assert "Liquidity Risk" in checks_triggered
        assert "High Leverage" in checks_triggered

    asyncio.run(_test())
