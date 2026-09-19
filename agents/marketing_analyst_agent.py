import json
from typing import Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, MarketingAnalysis

class MarketingAnalystAgent(BaseAgent):
    """Specialized Senior BA Agent analyzing the executive's favorite marketing side,
    content strategy, brand positioning, and messaging posture from post texts.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="MarketingAnalystAgent",
            role="Senior BA Marketing & Content Strategist",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_profile:
            raise ValueError("Sanitized profile must be present before running MarketingAnalystAgent.")

        self.log(state, "Analyzing marketing posture and favorite marketing side from post texts...")

        profile_payload = state.sanitized_profile.to_llm_payload()
        post_texts = state.sanitized_texts

        system_prompt = (
            "You are a Senior Business Analyst (Senior BA) specializing in executive profiling, "
            "B2B go-to-market analysis, and content marketing strategy.\n"
            "Your objective is to dissect the provided executive profile and their LinkedIn post texts "
            "to extract their 'FAVORITE MARKETING SIDE': their preferred marketing approach, messaging angle, "
            "target audience focus, content pillars, and communication tone.\n\n"
            "STRICT CONSTRAINTS:\n"
            "- Rely ONLY on the provided 7 profile fields and the raw post texts.\n"
            "- Do not hallucinate external details.\n"
            "- Return your findings strictly as a JSON object adhering to the schema below."
        )

        user_content = {
            "profile": profile_payload,
            "post_texts": post_texts,
            "instructions": (
                "Analyze the posts to determine the executive's favorite marketing side. "
                "Respond with a JSON object containing:\n"
                "- 'favorite_marketing_side': A comprehensive synthesis (2-3 paragraphs) detailing their preferred marketing angle "
                "(e.g., educational thought leadership, consultative B2B authority, event-driven marketing, employer brand values).\n"
                "- 'target_audience_focus': Key buyer or partner personas they address.\n"
                "- 'content_pillars': A list of 3-5 core marketing topics they consistently promote.\n"
                "- 'messaging_tone': A description of their tone of voice (e.g. strategic, pragmatic, value-oriented).\n"
                "- 'key_marketing_observations': A list of 3-5 bullet points analyzing their marketing effectiveness and style from a Senior BA perspective."
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result_json = self.llm_client.generate_json(messages=messages, temperature=0.2)

        marketing_analysis = MarketingAnalysis(
            favorite_marketing_side=result_json.get("favorite_marketing_side", ""),
            target_audience_focus=result_json.get("target_audience_focus", ""),
            content_pillars=result_json.get("content_pillars", []),
            messaging_tone=result_json.get("messaging_tone", ""),
            key_marketing_observations=result_json.get("key_marketing_observations", [])
        )

        state.marketing_analysis = marketing_analysis
        self.log(state, f"Completed Marketing Analysis. Tone: '{marketing_analysis.messaging_tone}'. Pillars: {len(marketing_analysis.content_pillars)} identified.")
        return state
