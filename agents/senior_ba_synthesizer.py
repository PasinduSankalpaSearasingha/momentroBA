import json
from typing import Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, SeniorBAExecutiveDossier

class SeniorBASynthesizerAgent(BaseAgent):
    """Orchestrating Senior BA Agent that synthesizes the strictly filtered profile fields,
    post texts, marketing orientation, strategic paths, company analysis, competitor intelligence,
    and website AEO/GEO score into a comprehensive executive dossier.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="SeniorBASynthesizerAgent",
            role="Lead Senior Business Analyst & Executive Dossier Synthesizer",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_profile:
            raise ValueError("Sanitized profile is required for synthesis.")

        self.log(state, "Synthesizing comprehensive Senior BA Executive & Corporate Dossier...")

        profile = state.sanitized_profile
        profile_payload = profile.to_llm_payload()
        post_texts = state.sanitized_texts
        marketing_data = state.marketing_analysis.model_dump() if state.marketing_analysis else {}
        strategic_data = state.strategic_path_analysis.model_dump() if state.strategic_path_analysis else {}
        company_data = state.company_analysis.model_dump() if state.company_analysis else {}
        competitor_data = state.competitor_analysis.model_dump() if state.competitor_analysis else {}
        website_score_data = state.website_score.model_dump() if state.website_score else {}

        contact_data = state.contact_info.model_dump() if state.contact_info else {}
        bi_messages_data = state.bi_messages.model_dump() if state.bi_messages else {}

        system_prompt = (
            "You are a seasoned, elite Senior Business Analyst (Senior BA) and Management Consultant.\n"
            "Your task is to produce an exhaustive, highly insightful Executive Description and Corporate Dossier.\n"
            "You have been provided with:\n"
            "1. Lead profile data (strictly: id, full_name, job_title, company_name, sector_tag, country, location).\n"
            "2. LinkedIn post texts.\n"
            "3. Notes on 'Favorite Marketing Side' and 'Favorite Paths'.\n"
            "4. Company Analysis (market positioning, value proposition, key offerings).\n"
            "5. Competitor Intelligence gathered via the search tool.\n"
            "6. Website AEO/GEO readiness evaluation.\n"
            "7. Verified Company Contact and Location details.\n"
            "8. Customized BI outreach message set tailored to Momentro's platform features.\n\n"
            "As a Senior BA, you evaluate leaders and their companies holistically: their strategic posture, "
            "marketing orientation, operational philosophy, market differentiators against competitors, "
            "and organizational value drivers.\n\n"
            "STRICT CONSTRAINTS:\n"
            "- Only refer to details verified in the profile fields, post texts, company details, and competitor findings.\n"
            "- Structure your output strictly as a JSON object adhering to the specified schema.\n"
            "- Ensure the 'full_description' field contains a beautifully formatted, publication-grade report in GitHub-flavored Markdown integrating all dimensions."
        )

        user_content = {
            "profile_data": profile_payload,
            "post_texts": post_texts,
            "marketing_analysis": marketing_data,
            "strategic_path_analysis": strategic_data,
            "company_analysis": company_data,
            "competitor_analysis": competitor_data,
            "website_aeo_geo_score": website_score_data,
            "company_contact_info": contact_data,
            "bi_outreach_messages": bi_messages_data,
            "instructions": (
                "Compose the definitive Senior BA Executive & Corporate Dossier. Return a JSON object with:\n"
                "- 'executive_summary': An executive summary (2-3 paragraphs) summarizing the leader, their role, credentials, and company footprint.\n"
                "- 'leadership_identity': Detailed assessment of their executive leadership style, governance posture, and organizational philosophy.\n"
                "- 'favorite_marketing_side_analysis': Deep-dive analysis of their favorite marketing side, including preferred narrative angles, messaging tactics, and target audiences.\n"
                "- 'favorite_paths_analysis': Deep-dive analysis of their favorite strategic paths (e.g. operational readiness before AI, franchise system simplification, ASEAN expansion, continuous learning).\n"
                "- 'business_transformation_and_tech_stance': Deep-dive analysis of their attitude toward technology and business transformation (e.g. systems integration, AI prerequisites, data protection).\n"
                "- 'senior_ba_engagement_recommendations': A list of 4-6 prioritized, highly actionable engagement recommendations for business development or partnership discussions.\n"
                "- 'full_description': A comprehensive, publication-grade Senior BA report in Markdown, including clear sections, bullet points, executive profile tables, competitor matrix, and operational recommendations.\n"
                "  Ensure full_description contains the following 8 comprehensive sections:\n"
                "    1. Executive Summary & Profile\n"
                "    2. Leadership Identity & Management Style\n"
                "    3. Favorite Marketing Side & Positioning Analysis\n"
                "    4. Favorite Strategic Paths & Operational Philosophy\n"
                "    5. Corporate Model, Offerings & Market Stance\n"
                "    6. Competitive Benchmarking & Differentiators\n"
                "    7. Strategic Senior BA Engagement Recommendations\n"
                "    8. Tailored LinkedIn Outreach & BI Messaging Architecture"
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result_json = self.llm_client.generate_json(messages=messages, temperature=0.2)

        dossier = SeniorBAExecutiveDossier(
            lead_id=profile.id,
            full_name=profile.full_name,
            job_title=profile.job_title,
            company_name=profile.company_name,
            sector_tag=profile.sector_tag,
            country=profile.country,
            location=profile.location,
            executive_summary=result_json.get("executive_summary", ""),
            leadership_identity=result_json.get("leadership_identity", ""),
            favorite_marketing_side_analysis=result_json.get("favorite_marketing_side_analysis", ""),
            favorite_paths_analysis=result_json.get("favorite_paths_analysis", ""),
            business_transformation_and_tech_stance=result_json.get("business_transformation_and_tech_stance", ""),
            company_analysis=state.company_analysis,
            competitor_analysis=state.competitor_analysis,
            website_aeo_geo_score=state.website_score,
            contact_info=state.contact_info,
            senior_ba_engagement_recommendations=result_json.get("senior_ba_engagement_recommendations", []),
            bi_messages=state.bi_messages,
            full_description=result_json.get("full_description", "")
        )

        state.dossier = dossier
        self.log(state, f"Executive & Corporate Dossier completed for {profile.full_name}.")
        return state
