import json
from typing import Any, Dict, Optional
from agents.base_agent import BaseAgent
from core.schemas import CompanyAnalysis, CompanyProfile, MultiAgentState

class CompanyAnalystAgent(BaseAgent):
    """Specialized Agent responsible for analyzing the company from company_report_url.
    
    Strictly isolates:
    - company_name
    - description
    - callToActionUrl (for website scoring)
    Discards all other metadata.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="CompanyAnalystAgent",
            role="Corporate & Market Positioning Analyst",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        self.log(state, "Extracting company details and analyzing corporate positioning...")

        raw_report = state.raw_company_report or {}
        company_profile = self._extract_company_profile(raw_report, state)
        state.sanitized_company = company_profile

        self.log(
            state,
            f"Extracted Company: '{company_profile.company_name}', "
            f"Website (callToActionUrl): '{company_profile.website_url}', "
            f"Description length: {len(company_profile.description)} chars."
        )

        # Senior BA analysis of company positioning
        company_analysis = self._analyze_company(company_profile)
        state.company_analysis = company_analysis

        self.log(state, f"Completed Corporate Analysis for {company_profile.company_name}.")
        return state

    def _extract_company_profile(
        self,
        raw_report: Dict[str, Any],
        state: MultiAgentState
    ) -> CompanyProfile:
        """Strictly extracts only company_name, description, and callToActionUrl."""
        company_dict = raw_report.get("company", {})

        # Extract company name
        company_name = (
            company_dict.get("name")
            or raw_report.get("company_name")
            or (state.sanitized_profile.company_name if state.sanitized_profile else "Target Company")
        )

        # Extract description
        description = company_dict.get("description") or raw_report.get("description", "")
        if not description and "description" in company_dict:
            description = str(company_dict["description"])

        # Extract website / callToActionUrl
        website_url = (
            company_dict.get("callToActionUrl")
            or company_dict.get("website")
            or raw_report.get("callToActionUrl")
            or raw_report.get("website")
        )

        return CompanyProfile(
            company_name=company_name,
            description=description.strip(),
            website_url=website_url.strip() if website_url else None
        )

    def _analyze_company(self, profile: CompanyProfile) -> CompanyAnalysis:
        """Performs a Senior BA evaluation of the company using strictly company_name and description."""
        system_prompt = (
            "You are a Senior Business Analyst (Senior BA) specializing in corporate strategy, "
            "business models, and digital transformation services.\n"
            "Analyze the provided company name and description. Evaluate their core value proposition, "
            "market positioning, key offerings, and strategic strengths.\n"
            "Return strictly a JSON object adhering to the specified schema."
        )

        user_content = {
            "company_payload": profile.to_llm_payload(),
            "instructions": (
                "Analyze the company and return a JSON object containing:\n"
                "- 'market_positioning': How this company positions itself against conventional agencies or software houses.\n"
                "- 'core_value_proposition': The primary business value they provide to clients and venture partners.\n"
                "- 'key_offerings': A list of 3-5 core services or product domains they focus on.\n"
                "- 'strategic_strengths': A list of 3-5 organizational and strategic differentiators."
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result = self.llm_client.generate_json(messages=messages, temperature=0.2)

        return CompanyAnalysis(
            company_name=profile.company_name,
            market_positioning=result.get("market_positioning", ""),
            core_value_proposition=result.get("core_value_proposition", ""),
            key_offerings=result.get("key_offerings", []),
            strategic_strengths=result.get("strategic_strengths", [])
        )
