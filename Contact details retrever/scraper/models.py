from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class LocationInfo(BaseModel):
    label: str = Field(default="Main Office", description="Label e.g. HQ, Branch, Office")
    full_address: str = Field(default="", description="Full formatted address")
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    map_url: Optional[str] = None

class ContactDetails(BaseModel):
    company_name: Optional[str] = None
    website: str
    emails: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    locations: List[LocationInfo] = Field(default_factory=list)
    social_links: Dict[str, str] = Field(default_factory=dict)
    contact_pages_found: List[str] = Field(default_factory=list)
    operating_hours: Optional[str] = None
    contact_form_urls: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    identified_contact_topics: List[str] = Field(default_factory=list)

class ExtractionResult(BaseModel):
    success: bool
    url: str
    method_used: str = Field(description="scrapy or playwright")
    fallback_occurred: bool = False
    fallback_reason: Optional[str] = None
    ai_enriched: bool = False
    execution_time_sec: float = 0.0
    pages_crawled: List[str] = Field(default_factory=list)
    identified_contact_topics: List[str] = Field(default_factory=list)
    data: ContactDetails
    error: Optional[str] = None
