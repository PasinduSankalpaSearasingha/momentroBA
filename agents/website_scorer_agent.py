from typing import Optional
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, WebsiteAeoGeoScore
from tools.aeo_geo_tool import AeoGeoTool

class WebsiteScorerAgent(BaseAgent):
    """Specialized Agent that scores the company website (extracted from callToActionUrl)
    using the AEO/GEO Tool API interface.
    """

    def __init__(self, aeo_geo_tool: Optional[AeoGeoTool] = None, llm_client=None):
        super().__init__(
            name="WebsiteScorerAgent",
            role="AEO & GEO Digital Footprint Evaluator",
            llm_client=llm_client
        )
        self.aeo_geo_tool = aeo_geo_tool or AeoGeoTool()

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_company:
            raise ValueError("Sanitized company profile is required before running WebsiteScorerAgent.")

        company = state.sanitized_company
        website_url = company.website_url

        if not website_url:
            self.log(state, "No callToActionUrl or website found for company. Skipping AEO/GEO score.")
            return state

        self.log(state, f"Evaluating AEO/GEO readiness for website (callToActionUrl): '{website_url}'...")

        score_result: WebsiteAeoGeoScore = self.aeo_geo_tool.score_website(
            website_url=website_url,
            company_name=company.company_name
        )

        state.website_score = score_result

        self.log(
            state,
            f"Website Scoring Completed: Overall={score_result.overall_score}/100, "
            f"AEO={score_result.aeo_score}/100, GEO={score_result.geo_score}/100. "
            f"Status: {score_result.status}"
        )
        return state
