"""
ValuAgent Orchestrator.

Wires the five agents into a single sequential pipeline:

    DataRetrievalAgent -> ValuationAgent -> SensitivityAgent -> CriticAgent -> MemoWriterAgent

Each agent reads what it needs from session state (written by the agent
before it) and writes its own output back to session state. This is a
deliberately simple orchestration topology (linear, not parallel/branching)
because each stage genuinely depends on the previous stage's output --
there's no benefit to parallelizing steps that must run in order, and a
straight SequentialAgent is easier to audit than a fancier graph would be.

Each individual agent already handles its own upstream-missing-data case
gracefully (writing an `..._error` key and returning early rather than
crashing), so if e.g. DataRetrievalAgent fails, ValuationAgent will run,
see `financial_data_error` is set, and also fail gracefully rather than
throwing an unhandled exception -- the whole pipeline degrades cleanly
instead of crashing partway through.
Note on a deprecation warning you may see: google-adk==2.3.0 emits
"SequentialAgent is deprecated, use Workflow instead." SequentialAgent
still works correctly (confirmed by the tests in this project) and is
used here because its API was directly verified during this build,
whereas Workflow's API was not. If your team wants to remove this
warning, investigate google.adk.Workflow as a direct swap-in, but
verify its constructor/behavior yourselves before switching -- don't
assume it's a drop-in replacement without checking.
"""

from google.adk.agents import SequentialAgent

from agents.data_retrieval_agent import DataRetrievalAgent
from agents.valuation_agent import ValuationAgent
from agents.sensitivity_agent import SensitivityAgent
from agents.critic_agent import CriticAgent
from agents.memo_writer_agent import memo_writer_agent


root_agent = SequentialAgent(
    name="valuagent_orchestrator",
    description=(
        "Full ValuAgent pipeline: fetches financial data for a ticker, runs "
        "DCF/DDM valuation, builds a sensitivity grid, runs guardrail checks, "
        "and writes an investment memo."
    ),
    sub_agents=[
        DataRetrievalAgent(),
        ValuationAgent(),
        SensitivityAgent(),
        CriticAgent(),
        memo_writer_agent,
    ],
)
