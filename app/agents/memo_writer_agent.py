"""
Stage 5 Agent — Memo Writer Agent.

Uses LiteLLM to generate a factual research memo synthesized from pre-computed
state keys.
"""

import os
from google.adk.agents import LlmAgent
from google.adk.models import LiteLlm
from app.agents.memo_prompt import build_memo_prompt

MODEL_NAME = os.environ.get("VALUAGENT_MEMO_MODEL", "groq/openai/gpt-oss-120b")


def _build_instruction(ctx) -> str:
    return build_memo_prompt(ctx.session.state)


memo_writer_agent = LlmAgent(
    name="memo_writer_agent",
    model=LiteLlm(model=MODEL_NAME),
    instruction=_build_instruction,
    output_key="memo_text",
)
