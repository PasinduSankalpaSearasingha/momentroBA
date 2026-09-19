import json
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, BIMessageSet

MOMENTRO_PLATFORM_KNOWLEDGE = """
MOMENTRO PLATFORM DEFINITION & ARCHITECTURE:
- Disambiguation: Momentro is strictly an AI-powered Marketing Strategy, Brand Intelligence, and Growth Infrastructure Platform (offered as Marketing Strategy as a Service, or MSaaS). It is distinct from Momento (caching/Redis), Momentum (Salesforce GTM sync), and Memento Database.
- Core Strategic Modules (The Five Pillars):
  1. Audience Analyser & Behavioral Persona Mapping: 360-degree consumer profiles combining psychographics, behavioral data, and digital consumption habits.
  2. Influencer Alignment Engine: Cross-checks engagement patterns, content style, and audience demographics for genuine peer-to-peer creator relevance over vanity follower counts.
  3. Content Soundness Matrix: Evaluates digital channel footprints to identify structural content gaps and aligns media formats across customer journeys.
  4. Search Intent Mapping Engine: Analyzes real-time search query syntax and volume to map buyer journeys and consumer pain points.
  5. Competitor Tracking & Digital Share of Voice: Proprietary Brand Authority Score (BAS - market influence & organic footprint) and Brand Personality Score (BPS - NLP tone & emotional resonance).
- Operational Growth Infrastructure:
  1. Unified Data Foundation: Unifies fragmented CRM (HubSpot/Salesforce), ads, web/GA4, e-commerce, ERP, and finance data into a central knowledge graph.
  2. Automated Workflows: Governed, on-brand background automation for content creation, lead qualification, and reporting.
  3. Agentic AI: Context-aware AI agents executing operational roles across sales, operations, and service.
  4. AI Visibility (SEO / AEO / GEO): Optimizes brand authority and recommendation profiles across generative search and AI answer engines (ChatGPT, Perplexity, Gemini).
- Stack Integrations: Native connectors for Snowflake, Databricks, BigQuery, Salesforce, HubSpot, Shopify, Meta, GA4, LinkedIn, Power BI, Looker Studio.
"""

class BIMessageCreatorAgent(BaseAgent):
    """Specialized Business Intelligence & Automated Outreach Agent.
    Synthesizes executive profile signals, post themes, operational stances,
    company positioning, competitor intelligence, and website AEO/GEO scores
    into hyper-personalized LinkedIn outreach messages aligned with Momentro.
    """

    def __init__(self, llm_client=None):
        super().__init__(
            name="BIMessageCreatorAgent",
            role="Senior BI Outreach & Personalized Messaging Strategist",
            llm_client=llm_client
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_profile:
            raise ValueError("Sanitized profile is required to generate outreach messages.")

        profile = state.sanitized_profile
        self.log(state, f"Crafting automated BI LinkedIn outreach messages for {profile.full_name} ({profile.company_name})...")

        profile_payload = profile.to_llm_payload()
        post_texts = state.sanitized_texts[:5] if state.sanitized_texts else []
        marketing_data = state.marketing_analysis.model_dump() if state.marketing_analysis else {}
        strategic_data = state.strategic_path_analysis.model_dump() if state.strategic_path_analysis else {}
        company_data = state.company_analysis.model_dump() if state.company_analysis else {}
        competitor_data = state.competitor_analysis.model_dump() if state.competitor_analysis else {}
        website_score_data = state.website_score.model_dump() if state.website_score else {}

        system_prompt = (
            "You are an elite Senior Business Intelligence (BI) Messaging Specialist and GTM Strategist for Momentro.\n"
            "Your objective is to craft hyper-personalized, high-converting LinkedIn messages for high-level executives.\n\n"
            f"{MOMENTRO_PLATFORM_KNOWLEDGE}\n\n"
            "MESSAGING PHILOSOPHY & RULES:\n"
            "1. NO GENERIC SALES SPAM. Speak as a peer-to-peer strategic advisor or business analyst.\n"
            "2. Anchor every message in the executive's verified background, exact public quotes, credentials (e.g. FCMA, CGMA), or operational philosophy (e.g. 'operational foundation before AI', 'unifying systems instead of adding more tools').\n"
            "3. Bridge their specific reality to the exact matching Momentro capability (Unified Data Foundation, Content Soundness Matrix, AEO/GEO AI Visibility, BAS/BPS Competitor Tracking, Stack Integrations).\n"
            "4. STRICT CONSTRAINT on 'connection_request_note': MUST BE UNDER 300 CHARACTERS total to comply with LinkedIn limits.\n"
            "5. RECIPIENT TARGETING RULE (CRITICAL):\n"
            "   - ONLY the LinkedIn connection request note ('connection_request_note') must be created using the individual user's personal name (e.g., 'Hi [First Name],').\n"
            "   - ALL OTHER MESSAGES ('primary_inmail', 'alternative_pitch', 'quick_teaser', 'follow_up') are sent to the company channels (company email, contact forms, partnership desk), and MUST be created using the company name (e.g., 'Hi [Company Name] Team,' or 'Dear [Company Name] Team,'). DO NOT use the individual person's name for company-directed messages.\n"
            "6. Return your response as a valid JSON object matching the required schema."
        )

        user_content = {
            "profile": profile_payload,
            "recent_posts": post_texts,
            "marketing_orientation": marketing_data,
            "strategic_paths_and_tech_stance": strategic_data,
            "company_analysis": company_data,
            "competitor_landscape": competitor_data,
            "website_aeo_geo_readiness": website_score_data,
            "instructions": (
                "Generate a customized set of BI outreach messages adhering strictly to this JSON format:\n"
                "{\n"
                '  "connection_request_note": "A personalized LinkedIn connection request note strictly under 300 characters addressing the executive by personal name (e.g., Hi Rajive,)",\n'
                '  "primary_inmail": "Full, high-resonance message addressing the company team by company name (e.g., Hi [Company Name] Team,), tailored to their operational and strategic philosophy",\n'
                '  "alternative_pitch": "Alternative strategic pitch addressing the company team by company name focusing on business model, venture building, and market growth",\n'
                '  "quick_teaser": "Short 2-3 sentence punchy conversation starter addressing the company team by company name",\n'
                '  "follow_up": "Low-friction follow-up message (+3-5 days) addressing the company team by company name sharing a value-add perspective or diagnostic",\n'
                '  "target_resonance_points": ["Point 1: Executive signal -> Momentro feature", "Point 2: ..."],\n'
                '  "personalization_rationale": "Strategic explanation of why these messages resonate with this organization"\n'
                "}"
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        result_json = self.llm_client.generate_json(messages=messages, temperature=0.3)

        def _format_field(val: Any) -> str:
            if isinstance(val, dict):
                subject = val.get("subject", "")
                body = val.get("body") or val.get("content") or val.get("message") or ""
                if subject:
                    return f"Subject: {subject}\n\n{body}"
                return str(body) if body else json.dumps(val, indent=2)
            elif isinstance(val, list):
                return "\n".join(str(item) for item in val)
            return str(val) if val is not None else ""

        # Deterministic Recipient Greeting Enforcers
        import re
        clean_name = re.sub(r'\(.*?\)', '', profile.full_name).strip()
        first_name = clean_name.split()[0] if clean_name else "There"
        for title_prefix in ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof."]:
            if first_name.lower() == title_prefix.lower():
                parts = clean_name.split()
                if len(parts) > 1:
                    first_name = parts[1]
                break

        company_target = profile.company_name.strip() if profile.company_name else "Company"

        def _enforce_personal_greeting(text: str, name: str) -> str:
            """Ensures LinkedIn note strictly addresses the executive by personal name."""
            if not text:
                return f"Hi {name}, I admire your work and would love to connect."
            t = text.strip()
            # If text mistakenly addresses the company or team
            t = re.sub(r'^(Hi|Hello|Dear)\s+[^,\n]+Team\s*,\s*', f'Hi {name}, ', t, flags=re.IGNORECASE)
            # Ensure it starts with personal greeting
            if not re.match(r'^(Hi|Hello|Dear)\s+', t, re.IGNORECASE):
                t = f"Hi {name}, {t}"
            return t

        def _enforce_company_greeting(text: str, comp_name: str, exec_first: str) -> str:
            """Ensures company outreach messages strictly address the company team by company name."""
            if not text:
                return f"Hi {comp_name} Team,\n\nWe would love to connect with your team."
            t = text.strip()
            subject_prefix = ""
            if t.lower().startswith("subject:"):
                parts = t.split("\n\n", 1)
                if len(parts) == 2:
                    subject_prefix = parts[0] + "\n\n"
                    t = parts[1].strip()
                else:
                    lines = t.split("\n", 1)
                    if len(lines) == 2:
                        subject_prefix = lines[0] + "\n\n"
                        t = lines[1].strip()

            # Replace any executive personal greeting with company team greeting
            t = re.sub(
                rf'^(Hi|Hello|Dear)\s+(?:{re.escape(exec_first)}|{re.escape(clean_name)}|there)\s*,\s*',
                f'Hi {comp_name} Team,\n\n',
                t,
                flags=re.IGNORECASE
            )
            # If it does not already start with Hi/Dear [Company] Team
            if not re.match(r'^(Hi|Hello|Dear)\s+.*Team\s*,', t, re.IGNORECASE):
                t = f"Hi {comp_name} Team,\n\n{t}"

            return subject_prefix + t

        raw_note = _format_field(result_json.get("connection_request_note", ""))
        conn_note = _enforce_personal_greeting(raw_note, first_name)
        if len(conn_note) > 298:
            conn_note = conn_note[:295] + "..."

        raw_primary = _format_field(result_json.get("primary_inmail", ""))
        primary_inmail = _enforce_company_greeting(raw_primary, company_target, first_name)

        raw_pitch = _format_field(result_json.get("alternative_pitch", ""))
        alt_pitch = _enforce_company_greeting(raw_pitch, company_target, first_name)

        raw_teaser = _format_field(result_json.get("quick_teaser", ""))
        quick_teaser = _enforce_company_greeting(raw_teaser, company_target, first_name)

        raw_followup = _format_field(result_json.get("follow_up", ""))
        follow_up = _enforce_company_greeting(raw_followup, company_target, first_name)

        target_pts = result_json.get("target_resonance_points", [])
        if isinstance(target_pts, str):
            target_pts = [target_pts]

        bi_messages = BIMessageSet(
            connection_request_note=conn_note,
            primary_inmail=primary_inmail,
            alternative_pitch=alt_pitch,
            quick_teaser=quick_teaser,
            follow_up=follow_up,
            target_resonance_points=target_pts,
            personalization_rationale=result_json.get("personalization_rationale", "")
        )

        state.bi_messages = bi_messages
        self.log(state, f"Generated customized BI messages for {profile.full_name}.")
        return state
