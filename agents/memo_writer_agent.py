"""
Memo Writer Agent.

This is the ONLY agent in the pipeline that uses an LLM. Everything
upstream (data retrieval, valuation, sensitivity, critic checks) is
deterministic Python specifically so that by the time execution reaches
here, every number the LLM will ever see has already been computed and
validated. This agent's instruction is written to make that boundary
explicit to the model itself: it is told, directly, not to calculate or
invent any figure, only to narrate the ones it's given.

IMPORTANT -- environment requirement not verifiable in the build sandbox:
this agent requires a real Gemini API key (GOOGLE_API_KEY or
GEMINI_API_KEY in the environment) and network access to Google's API.
Neither was available where this was built, so this agent is
STRUCTURALLY complete and follows the verified ADK LlmAgent API
(confirmed via introspection against google-adk==2.3.0), but has NOT
been run end-to-end against a real model. Run test_memo_writer_agent.py
on a machine with a real API key before trusting this in a demo.

The model name below ("gemini-2.0-flash") is a reasonable default as of
this build's knowledge, but model availability changes -- if the run
fails with a model-not-found error, check https://ai.google.dev for
currently available model names and update MODEL_NAME below, or set the
VALUAGENT_MEMO_MODEL environment variable to override it without editing code.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models import LiteLlm

from agents.memo_prompt import build_memo_prompt


MODEL_NAME = os.environ.get("VALUAGENT_MEMO_MODEL", "groq/llama3-8b-8192")


def _build_instruction(ctx: ReadonlyContext) -> str:
    """
    Builds the memo-writing prompt by reading already-computed results
    directly out of session state.
    """
    return build_memo_prompt(ctx.state)


llm_model = LiteLlm(
    model=MODEL_NAME
)


memo_writer_agent = LlmAgent(
    name="memo_writer_agent",
    description=(
        "Writes an investment memo narrating the already-computed DCF/DDM "
        "valuation, sensitivity analysis, and critic flags. Never calculates "
        "or invents numbers -- only narrates numbers already in session state."
    ),
    model=llm_model,
    instruction=_build_instruction,
    output_key="memo_text",
)
