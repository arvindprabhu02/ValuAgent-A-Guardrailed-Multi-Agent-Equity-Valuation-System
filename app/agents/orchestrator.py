"""
StockLens Root Orchestrator.

Combines all 5 pipeline agents into a SequentialAgent.
Pipeline: DataRetrieval -> FundamentalAnalysis -> IndustryComparison -> Critic -> MemoWriter
"""

from google.adk.agents import SequentialAgent
from app.agents.data_retrieval_agent import DataRetrievalAgent
from app.agents.fundamental_analysis_agent import FundamentalAnalysisAgent
from app.agents.industry_comparison_agent import IndustryComparisonAgent
from app.agents.critic_agent import CriticAgent
from app.agents.memo_writer_agent import memo_writer_agent

root_agent = SequentialAgent(
    name="stocklens_orchestrator",
    sub_agents=[
        DataRetrievalAgent(),
        FundamentalAnalysisAgent(),
        IndustryComparisonAgent(),
        CriticAgent(),
        memo_writer_agent,
    ],
)
