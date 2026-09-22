import json
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from core.schemas import CompetitorAnalysis, CompetitorItem, MultiAgentState
class CompetitorAnalystAgent(BaseAgent):
    """Specialized Senior BA Agent that analyzes competitors provided in the company report."""

    def __init__(self, llm_client=None):
        super().__init__(
            name="CompetitorAnalystAgent",
            role="Competitive Intelligence & Market Benchmarking Analyst",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_company:
            raise ValueError("Sanitized company profile is required before running CompetitorAnalystAgent.")

        company = state.sanitized_company
        self.log(state, f"Extracting competitors from company report for '{company.company_name}'...")

        # 1. Gather competitor intelligence from raw report
        raw_report = state.raw_company_report or {}
        search_results = raw_report.get("similar_organizations") or raw_report.get("similar_organizations_json") or []
        
        self.log(state, f"Found {len(search_results)} competitor candidate(s) in company report.")

        # 2. Senior BA Competitive Synthesis
        competitor_analysis = self._benchmark_competitors(company, search_results)
        state.competitor_analysis = competitor_analysis

        self.log(
            state,
            f"Competitor Analysis completed. Benchmarked {len(competitor_analysis.top_competitors)} top rivals."
        )
        return state

    def _benchmark_competitors(
        self,
        company,
        search_results: List[Dict[str, Any]]
    ) -> CompetitorAnalysis:
        """Analyzes competitors and benchmarks differentiation."""
        system_prompt = (
            "You are a Senior Business Analyst (Senior BA) specializing in competitive intelligence, "
            "market positioning, and industry benchmarking.\n"
            "Using the provided target company details and competitor search findings, produce an in-depth "
            "competitive benchmarking analysis.\n"
            "Identify 3 to 4 key competitors, their strengths, how the target company differentiates from them, "
            "and market gaps/opportunities.\n"
            "Return strictly a JSON object adhering to the schema."
        )

        user_content = {
            "target_company": {
                "name": company.company_name,
                "description": company.description
            },
            "search_findings": search_results,
            "instructions": (
                "Respond with a JSON object containing:\n"
                "- 'landscape_summary': An executive summary (2 paragraphs) of the competitive arena.\n"
                "- 'top_competitors': A list of competitor objects, each with:\n"
                "    - 'name': Competitor name\n"
                "    - 'website': Competitor website/domain\n"
                "    - 'description': Brief description of what they do\n"
                "    - 'key_strengths': List of their strengths\n"
                "    - 'differentiation_vs_target': How the target company distinguishes itself from this competitor\n"
                "- 'market_opportunities_and_gaps': A list of 3-5 strategic market openings where the target company can win."
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result = self.llm_client.generate_json(messages=messages, temperature=0.2)

        top_comps: List[CompetitorItem] = []
        for c in result.get("top_competitors", []):
            top_comps.append(
                CompetitorItem(
                    name=c.get("name", "Competitor"),
                    website=c.get("website"),
                    description=c.get("description", ""),
                    key_strengths=c.get("key_strengths", []),
                    differentiation_vs_target=c.get("differentiation_vs_target", "")
                )
            )

        return CompetitorAnalysis(
            target_company=company.company_name,
            landscape_summary=result.get("landscape_summary", ""),
            top_competitors=top_comps,
            market_opportunities_and_gaps=result.get("market_opportunities_and_gaps", [])
        )
