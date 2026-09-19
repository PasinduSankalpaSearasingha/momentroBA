from typing import Optional
from agents.base_agent import BaseAgent
from core.schemas import MultiAgentState, CompanyContactInfo
from tools.contact_retriever_tool import ContactRetrieverTool

class ContactRetrieverAgent(BaseAgent):
    """Specialized Agent responsible for scraping the company website (extracted from 
    company_report_url or callToActionUrl) using 'Contact details retrever' to discover 
    verified corporate contact details: emails, phone numbers, office/HQ locations, 
    social links, and contact channels.
    """

    def __init__(self, contact_tool: Optional[ContactRetrieverTool] = None, llm_client=None):
        super().__init__(
            name="ContactRetrieverAgent",
            role="Corporate Digital & Physical Footprint / Contact Intelligence Extractor",
            llm_client=llm_client
        )
        self.contact_tool = contact_tool or ContactRetrieverTool()

    def process(self, state: MultiAgentState) -> MultiAgentState:
        if not state.sanitized_company:
            raise ValueError("Sanitized company profile is required before running ContactRetrieverAgent.")

        company = state.sanitized_company
        website_url = company.website_url

        if not website_url:
            self.log(state, "No website URL found for company profile. Skipping contact extraction.")
            return state

        self.log(state, f"Scraping website '{website_url}' using Contact details retriever for '{company.company_name}'...")

        contact_info: CompanyContactInfo = self.contact_tool.extract_contacts(
            website_url=website_url,
            company_name=company.company_name
        )

        state.contact_info = contact_info

        emails_summary = ", ".join(contact_info.emails) if contact_info.emails else "None found"
        phones_summary = ", ".join(contact_info.phone_numbers) if contact_info.phone_numbers else "None found"
        locs_count = len(contact_info.locations)
        socials_count = len(contact_info.social_links)

        self.log(
            state,
            f"Contact Extraction Completed: {len(contact_info.emails)} email(s) [{emails_summary}], "
            f"{len(contact_info.phone_numbers)} phone(s) [{phones_summary}], "
            f"{locs_count} location(s), {socials_count} social profile(s)."
        )

        return state
