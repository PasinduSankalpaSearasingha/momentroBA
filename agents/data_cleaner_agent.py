from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from core.schemas import LeadProfile, MultiAgentState

class DataCleanerAgent(BaseAgent):
    """Specialized Agent responsible for data isolation and sanitization.
    
    Ensures that ONLY the 7 mandated profile fields and raw post text strings
    are extracted and passed down the pipeline, strictly discarding all
    extraneous metadata (URNs, media URLs, reaction stats, follower counts).
    """

    def __init__(self):
        super().__init__(
            name="DataCleanerAgent",
            role="Data Extraction & Isolation Specialist"
        )

    def process(self, state: MultiAgentState) -> MultiAgentState:
        self.log(state, "Starting data isolation and extraction process...")

        # 1. Extract strictly the 7 profile fields
        raw_lead = state.raw_lead
        profile = self._extract_lead_profile(raw_lead)
        state.sanitized_profile = profile
        self.log(
            state,
            f"Extracted Profile: id={profile.id}, name='{profile.full_name}', "
            f"title='{profile.job_title}', company='{profile.company_name}', "
            f"sector='{profile.sector_tag}', country='{profile.country}', location='{profile.location}'"
        )

        # 2. Extract strictly the 'text' parameter from posts
        raw_posts = state.raw_posts
        extracted_texts = self._extract_post_texts(raw_posts)
        state.sanitized_texts = extracted_texts
        self.log(state, f"Extracted {len(extracted_texts)} clean post text(s). All non-text metadata stripped.")

        return state

    def _extract_lead_profile(self, raw: Dict[str, Any]) -> LeadProfile:
        """Extracts the 7 fields from either direct format or scraped profile structure."""
        # Direct format check
        if "full_name" in raw or "job_title" in raw:
            return LeadProfile(
                id=raw.get("id", 1),
                full_name=raw.get("full_name") or raw.get("name") or "Unknown Executive",
                job_title=raw.get("job_title") or "Executive",
                company_name=raw.get("company_name") or "Enterprise",
                sector_tag=raw.get("sector_tag") or "General Business",
                country=raw.get("country") or "Global",
                location=raw.get("location") or raw.get("country") or "Unknown"
            )

        # Scraped profile structure (like in scraped_profiles (2).json)
        profile_data = raw.get("profile_data", {})
        first = profile_data.get("firstName", "")
        last = profile_data.get("lastName", "")
        derived_name = f"{first} {last}".strip() or raw.get("matched_name") or "Unknown"

        current_positions = profile_data.get("currentPosition") or []
        first_pos = current_positions[0] if current_positions else {}
        derived_title = first_pos.get("position") or profile_data.get("headline") or "Executive"
        derived_company = first_pos.get("companyName") or raw.get("matched_company") or "Enterprise"

        loc_data = profile_data.get("location", {})
        country_name = loc_data.get("parsed", {}).get("country") or loc_data.get("linkedinText") or "Sri Lanka"
        full_location = first_pos.get("location") or loc_data.get("linkedinText") or country_name

        return LeadProfile(
            id=raw.get("id", 1),
            full_name=derived_name,
            job_title=derived_title,
            company_name=derived_company,
            sector_tag=raw.get("sector_tag", "Technology & Manufacturing"),
            country=country_name,
            location=full_location
        )

    def _extract_post_texts(self, raw_posts_input: Any) -> List[str]:
        """Extracts post text from various LinkedIn scraper formats.

        Supported formats:
        - {'posts': [...]}  with 'text', 'post_text', or 'content' per post
        - {'company_posts': [...]}  same per-post fields
        - direct list of post dicts
        """
        posts_list: List[Dict[str, Any]] = []

        if isinstance(raw_posts_input, dict):
            # Personal posts key
            if "posts" in raw_posts_input and isinstance(raw_posts_input["posts"], list):
                posts_list = raw_posts_input["posts"]
            # Company posts key (company report format)
            if "company_posts" in raw_posts_input and isinstance(raw_posts_input["company_posts"], list):
                posts_list += raw_posts_input["company_posts"]
            # Single post dict
            if not posts_list and ("text" in raw_posts_input or "content" in raw_posts_input or "post_text" in raw_posts_input):
                posts_list = [raw_posts_input]
        elif isinstance(raw_posts_input, list):
            posts_list = raw_posts_input

        clean_texts: List[str] = []
        seen = set()

        for post in posts_list:
            if not isinstance(post, dict):
                continue
            # Try all known text field names in priority order
            text = (
                post.get("text")
                or post.get("post_text")
                or post.get("content")
            )
            if text and isinstance(text, str):
                cleaned = text.strip()
                if cleaned and cleaned not in seen:
                    clean_texts.append(cleaned)
                    seen.add(cleaned)

        return clean_texts
