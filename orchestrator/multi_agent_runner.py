import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from agents.base_agent import BaseAgent
from agents.data_cleaner_agent import DataCleanerAgent
from agents.marketing_analyst_agent import MarketingAnalystAgent
from agents.strategic_path_agent import StrategicPathAgent
from agents.company_analyst_agent import CompanyAnalystAgent
from agents.competitor_analyst_agent import CompetitorAnalystAgent
from agents.website_scorer_agent import WebsiteScorerAgent
from agents.contact_retriever_agent import ContactRetrieverAgent
from agents.bi_message_agent import BIMessageCreatorAgent
from agents.senior_ba_synthesizer import SeniorBASynthesizerAgent
from core.schemas import MultiAgentState, SeniorBAExecutiveDossier

logger = logging.getLogger("MultiAgentPipeline")

class MultiAgentPipeline:
    """Scalable orchestrator managing the multi-agent pipeline for Senior BA profiling."""

    def __init__(self, agents: Optional[List[BaseAgent]] = None, llm_client=None):
        if agents is not None:
            self.agents = agents
        else:
            # Default comprehensive Senior BA pipeline with automated BI message creation
            self.agents = [
                DataCleanerAgent(),
                MarketingAnalystAgent(llm_client=llm_client),
                StrategicPathAgent(llm_client=llm_client),
                CompanyAnalystAgent(llm_client=llm_client),
                ContactRetrieverAgent(llm_client=llm_client),
                CompetitorAnalystAgent(llm_client=llm_client),
                WebsiteScorerAgent(llm_client=llm_client),
                BIMessageCreatorAgent(llm_client=llm_client),
                SeniorBASynthesizerAgent(llm_client=llm_client)
            ]

    def add_agent(self, agent: BaseAgent, index: Optional[int] = None) -> None:
        """Adds a new specialized agent to the pipeline for seamless horizontal scalability."""
        if index is None:
            self.agents.append(agent)
        else:
            self.agents.insert(index, agent)
        logger.info(f"Registered new agent '{agent.name}' ({agent.role}) at index {index or len(self.agents)-1}")

    def run(
        self,
        raw_lead: Dict[str, Any],
        raw_posts: Any,
        raw_company_report: Optional[Any] = None
    ) -> MultiAgentState:
        """Executes the pipeline on a single lead, their post activity, and company report."""
        start_time = time.time()
        state = MultiAgentState(
            raw_lead=raw_lead,
            raw_posts=raw_posts,
            raw_company_report=raw_company_report or {}
        )
        state.log("=== Multi-Agent Senior BA Pipeline Initialized ===")

        for idx, agent in enumerate(self.agents, start=1):
            step_start = time.time()
            state.log(f"Step {idx}/{len(self.agents)}: Invoking {agent.name}...")
            try:
                state = agent.process(state)
                elapsed = round(time.time() - step_start, 2)
                state.log(f"Step {idx}: {agent.name} completed successfully in {elapsed}s.")
            except Exception as e:
                state.log(f"Error in {agent.name}: {str(e)}")
                logger.error(f"Pipeline failed at agent {agent.name}: {e}", exc_info=True)
                raise e

        total_elapsed = round(time.time() - start_time, 2)
        state.log(f"=== Multi-Agent Pipeline Completed in {total_elapsed}s ===")
        return state

    def run_batch(
        self,
        items: List[Tuple[Dict[str, Any], Any, Optional[Any]]]
    ) -> List[MultiAgentState]:
        """Runs the pipeline across a batch of leads."""
        results: List[MultiAgentState] = []
        for item in items:
            lead = item[0]
            posts = item[1]
            company = item[2] if len(item) > 2 else {}
            state = self.run(lead, posts, company)
            results.append(state)
        return results
