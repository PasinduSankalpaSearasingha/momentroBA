from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field

class LeadProfile(BaseModel):
    """Strict model containing only the exact 7 profile fields specified by the user."""
    id: Any = Field(..., description="Unique lead identifier")
    full_name: str = Field(..., description="Full name of the person including titles")
    job_title: str = Field(..., description="Current job title / executive role")
    company_name: str = Field(..., description="Company name")
    sector_tag: str = Field(..., description="Industry or sector classification")
    country: str = Field(..., description="Country of residence / operations")
    location: str = Field(..., description="City and country location")

    def to_llm_payload(self) -> Dict[str, Any]:
        """Strictly returns only the 7 allowed profile fields."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "job_title": self.job_title,
            "company_name": self.company_name,
            "sector_tag": self.sector_tag,
            "country": self.country,
            "location": self.location
        }

class PostExtract(BaseModel):
    """Extracted text-only posts content for the lead."""
    lead_id: Optional[Any] = None
    texts: List[str] = Field(default_factory=list, description="Array of post body texts only")

class MarketingAnalysis(BaseModel):
    """Analysis of the executive's favorite marketing side and communications."""
    favorite_marketing_side: Union[str, List[str]] = Field(..., description="Synthesis of their favorite marketing angle/stance")
    target_audience_focus: Union[str, List[str]] = Field(..., description="Who they speak to (e.g. franchisors, enterprise leadership)")
    content_pillars: List[str] = Field(default_factory=list, description="Key recurring content pillars")
    messaging_tone: Union[str, List[str]] = Field(..., description="Brand voice and communication tone")
    key_marketing_observations: List[str] = Field(default_factory=list, description="Senior BA marketing observations")

class StrategicPathAnalysis(BaseModel):
    """Analysis of the executive's favorite strategic paths and operational directions."""
    favorite_paths: List[str] = Field(default_factory=list, description="Core pathways championed (e.g. franchise scaling, Singapore expansion)")
    core_business_themes: List[str] = Field(default_factory=list, description="Strategic business concepts")
    growth_and_scaling_focus: Union[str, List[str]] = Field(..., description="How they view growth vs operational friction")
    technology_and_operational_philosophy: Union[str, List[str]] = Field(..., description="Prerequisites for AI, data governance, systems integration")
    strategic_priorities: List[str] = Field(default_factory=list, description="High-priority business focus areas")

class CompanyProfile(BaseModel):
    """Strict model containing only company_name, description, and callToActionUrl from company_report_url."""
    company_name: str = Field(..., description="Company name")
    description: str = Field(..., description="Company description from company_report_url")
    website_url: Optional[str] = Field(None, description="Extracted callToActionUrl / website for scoring")

    def to_llm_payload(self) -> Dict[str, Any]:
        """Strictly returns only company_name and description."""
        return {
            "company_name": self.company_name,
            "description": self.description
        }

class CompanyAnalysis(BaseModel):
    """Analysis of the company's business model, positioning, and offerings."""
    company_name: str
    market_positioning: Union[str, List[str]] = Field(..., description="How the company positions itself in the market")
    core_value_proposition: Union[str, List[str]] = Field(..., description="Primary value proposition delivered to clients")
    key_offerings: List[str] = Field(default_factory=list, description="Core products and solutions")
    strategic_strengths: List[str] = Field(default_factory=list, description="Key competitive and organizational strengths")

class CompetitorItem(BaseModel):
    """Profile of a single benchmarked competitor."""
    name: str = Field(..., description="Competitor company name")
    website: Optional[str] = Field(None, description="Competitor website if available")
    description: str = Field(..., description="Competitor description and offering")
    key_strengths: List[str] = Field(default_factory=list, description="What the competitor excels at")
    differentiation_vs_target: Union[str, List[str]] = Field(..., description="How the target company differentiates against this competitor")

class CompetitorAnalysis(BaseModel):
    """Senior BA competitive landscape assessment."""
    target_company: str
    landscape_summary: Union[str, List[str]] = Field(..., description="Overview of the competitive landscape")
    top_competitors: List[CompetitorItem] = Field(default_factory=list, description="List of top benchmarked competitors")
    market_opportunities_and_gaps: List[str] = Field(default_factory=list, description="Opportunities where target company has an edge")

class LocationInfo(BaseModel):
    """Structured location and address record discovered for the company."""
    label: str = Field(default="Main Office", description="Office label e.g. HQ, Regional Office, Branch")
    full_address: str = Field(default="", description="Full formatted physical address")
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    map_url: Optional[str] = None

class CompanyContactInfo(BaseModel):
    """Structured contact and location details retrieved from company website via Contact details retriever."""
    company_name: Optional[str] = None
    website: str
    emails: List[str] = Field(default_factory=list, description="Discovered company email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="Discovered telephone/contact numbers")
    locations: List[LocationInfo] = Field(default_factory=list, description="Verified physical office/HQ locations")
    social_links: Dict[str, str] = Field(default_factory=dict, description="Discovered social profile links (LinkedIn, X, etc.)")
    contact_pages_found: List[str] = Field(default_factory=list, description="Internal contact/about pages discovered")
    operating_hours: Optional[str] = None
    contact_form_urls: List[str] = Field(default_factory=list, description="Contact form URLs on site")
    description: Optional[str] = None
    identified_contact_topics: List[str] = Field(default_factory=list, description="Contact channels/topics identified")

class WebsiteAeoGeoScore(BaseModel):
    """Scores and evaluation for Answer Engine Optimization (AEO) and Generative Engine Optimization (GEO)."""
    website_url: str
    aeo_score: float = Field(..., description="Answer Engine Optimization score (0-100)")
    geo_score: float = Field(..., description="Generative Engine Optimization score (0-100)")
    overall_score: float = Field(..., description="Combined AI/LLM readiness score (0-100)")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed scoring breakdown")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations to improve AI visibility")
    status: str = Field(default="evaluated", description="Status of evaluation (e.g. simulated_baseline, live_api)")

class BIMessageSet(BaseModel):
    """Personalized outreach and Business Intelligence message variations tailored to the executive and Momentro platform."""
    connection_request_note: str = Field(..., description="Personalized LinkedIn connection note (STRICT: under 300 characters)")
    primary_inmail: str = Field(..., description="High-resonance LinkedIn direct message / InMail aligned with their operational & strategic philosophy")
    alternative_pitch: str = Field(..., description="Strategic pitch tailored to venture building, scaling portfolio products, or AEO/GEO AI visibility")
    quick_teaser: str = Field(..., description="Punchy, conversational 2-3 sentence C-level message starter")
    follow_up: str = Field(..., description="Value-add follow-up message (+3-5 days) offering zero-friction diagnostic or insight")
    target_resonance_points: List[str] = Field(default_factory=list, description="Key client triggers mapped to Momentro features")
    personalization_rationale: Union[str, List[str]] = Field(..., description="Senior BA strategic explanation of why this messaging structure resonates")

class SeniorBAExecutiveDossier(BaseModel):
    """Comprehensive Senior BA Executive Description and Corporate Dossier."""
    lead_id: Any
    full_name: str
    job_title: str
    company_name: str
    sector_tag: str
    country: str
    location: str
    executive_summary: Union[str, List[str], Dict[str, Any], Any]
    leadership_identity: Union[str, List[str], Dict[str, Any], Any]
    favorite_marketing_side_analysis: Union[str, List[str], Dict[str, Any], Any]
    favorite_paths_analysis: Union[str, List[str], Dict[str, Any], Any]
    business_transformation_and_tech_stance: Union[str, List[str], Dict[str, Any], Any]
    company_analysis: Optional[CompanyAnalysis] = None
    competitor_analysis: Optional[CompetitorAnalysis] = None
    website_aeo_geo_score: Optional[WebsiteAeoGeoScore] = None
    contact_info: Optional[CompanyContactInfo] = None
    senior_ba_engagement_recommendations: List[str]
    bi_messages: Optional[BIMessageSet] = None
    full_description: str

class MultiAgentState(BaseModel):
    """State object passing between agents across the pipeline."""
    raw_lead: Dict[str, Any] = Field(default_factory=dict)
    raw_posts: Any = Field(default_factory=list)
    raw_company_report: Any = Field(default_factory=dict)
    sanitized_profile: Optional[LeadProfile] = None
    sanitized_texts: List[str] = Field(default_factory=list)
    sanitized_company: Optional[CompanyProfile] = None
    marketing_analysis: Optional[MarketingAnalysis] = None
    strategic_path_analysis: Optional[StrategicPathAnalysis] = None
    company_analysis: Optional[CompanyAnalysis] = None
    competitor_analysis: Optional[CompetitorAnalysis] = None
    website_score: Optional[WebsiteAeoGeoScore] = None
    contact_info: Optional[CompanyContactInfo] = None
    bi_messages: Optional[BIMessageSet] = None
    dossier: Optional[SeniorBAExecutiveDossier] = None
    execution_logs: List[str] = Field(default_factory=list)

    def log(self, message: str) -> None:
        self.execution_logs.append(message)

