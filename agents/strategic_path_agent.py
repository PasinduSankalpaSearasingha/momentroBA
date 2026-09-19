import json
from typing import Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, StrategicPathAnalysis

class StrategicPathAgent(BaseAgent):
    """Specialized Senior BA Agent analyzing the executive's favorite strategic paths,
    operational philosophy, business transformation themes, and growth directions.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="StrategicPathAgent",
            role="Senior BA Strategic Operations & Growth Analyst",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_profile:
            raise ValueError("Sanitized profile must be present before running StrategicPathAgent.")

        self.log(state, "Analyzing strategic paths, growth avenues, and operational philosophy from post texts...")

        profile_payload = state.sanitized_profile.to_llm_payload()
        post_texts = state.sanitized_texts

        system_prompt = (
            "You are a Senior Business Analyst (Senior BA) specializing in organizational strategy, "
            "digital transformation, operational excellence, and enterprise scaling.\n"
            "Your objective is to examine the provided executive profile and LinkedIn post texts "
            "to pinpoint their 'FAVORITE PATHS': the core operational, strategic, and growth paths "
            "they advocate for, invest in, and prioritize.\n\n"
            "STRICT CONSTRAINTS:\n"
            "- Rely ONLY on the provided 7 profile fields and the raw post texts.\n"
            "- Do not hallucinate external details.\n"
            "- Return your findings strictly as a JSON object adhering to the schema below."
        )

        user_content = {
            "profile": profile_payload,
            "post_texts": post_texts,
            "instructions": (
                "Analyze the posts to identify the executive's favorite paths and strategic themes. "
                "Respond with a JSON object containing:\n"
                "- 'favorite_paths': A list of 3-5 specific strategic paths they champion (e.g. operational foundation before AI, franchise simplification in ASEAN/Singapore, Stanford Seed business transformation).\n"
                "- 'core_business_themes': A list of key business concepts they emphasize (e.g. data governance, friction reduction, scalable technology).\n"
                "- 'growth_and_scaling_focus': A detailed synthesis (2-3 paragraphs) of their philosophy on enterprise growth and how technology enables it.\n"
                "- 'technology_and_operational_philosophy': A detailed breakdown of their views on AI, software integration, and data trust.\n"
                "- 'strategic_priorities': A list of 3-5 actionable priorities for this executive."
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result_json = self.llm_client.generate_json(messages=messages, temperature=0.2)

        strategic_analysis = StrategicPathAnalysis(
            favorite_paths=result_json.get("favorite_paths", []),
            core_business_themes=result_json.get("core_business_themes", []),
            growth_and_scaling_focus=result_json.get("growth_and_scaling_focus", ""),
            technology_and_operational_philosophy=result_json.get("technology_and_operational_philosophy", ""),
            strategic_priorities=result_json.get("strategic_priorities", [])
        )

        state.strategic_path_analysis = strategic_analysis
        self.log(state, f"Completed Strategic Path Analysis. {len(strategic_analysis.favorite_paths)} favorite paths identified.")
        return state
