import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.error

from core.schemas import CompanyContactInfo, LocationInfo

logger = logging.getLogger("ContactRetrieverTool")

class ContactRetrieverTool:
    """Tool that utilizes 'Contact details retrever' to crawl company websites and extract
    verified contact intelligence: emails, phone numbers, physical office/HQ locations,
    social links, and contact pages.
    
    Supports:
    1. Local HTTP API integration (e.g. http://127.0.0.1:8000/api/extract if the retriever server is active)
    2. In-process direct execution via scraper.service / scraper.extractor from 'Contact details retrever'
    3. Resilient built-in fallback extraction to guarantee pipeline stability.
    """

    def __init__(
        self,
        retriever_dir: Optional[str] = None,
        api_url: Optional[str] = None
    ):
        base_dir = Path(__file__).resolve().parent.parent
        self.retriever_dir = Path(retriever_dir) if retriever_dir else (base_dir / "Contact details retrever")
        self.api_url = api_url or os.getenv("CONTACT_RETRIEVER_API_URL", "http://127.0.0.1:8000/api/extract")

        # Ensure Contact details retrever is available on python path for in-process execution
        if self.retriever_dir.exists() and str(self.retriever_dir) not in sys.path:
            sys.path.insert(0, str(self.retriever_dir))

    def extract_contacts(
        self,
        website_url: str,
        company_name: Optional[str] = None,
        force_playwright: bool = False
    ) -> CompanyContactInfo:
        """Main method to extract contact information from a given website URL."""
        normalized_url = website_url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url

        logger.info(f"Extracting contact information for '{company_name or normalized_url}' via website: {normalized_url}")

        # 1. Try local HTTP API if running
        api_result = self._try_api_extract(normalized_url, force_playwright)
        if api_result:
            logger.info("Successfully extracted contact details via local Retriever API.")
            return api_result

        # 2. Try in-process extraction via Contact details retrever modules
        in_process_result = self._try_in_process_extract(normalized_url, force_playwright)
        if in_process_result:
            logger.info("Successfully extracted contact details via in-process Retriever service.")
            return in_process_result

        # 3. Resilient deterministic fallback extraction
        logger.info("Falling back to deterministic web extraction.")
        return self._fallback_deterministic_extract(normalized_url, company_name)

    def _try_api_extract(self, url: str, force_playwright: bool) -> Optional[CompanyContactInfo]:
        """Attempts to call the Contact Details Retriever service API if running."""
        try:
            payload = json.dumps({"url": url, "force_playwright": force_playwright}).encode("utf-8")
            req = urllib.request.Request(
                self.api_url,
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    contact_data = data.get("data", {})
                    return self._map_to_company_contact_info(contact_data, url)
        except Exception as e:
            logger.debug(f"Retriever API call at {self.api_url} not available ({e}).")
        return None

    def _try_in_process_extract(self, url: str, force_playwright: bool) -> Optional[CompanyContactInfo]:
        """Runs the async extraction service from 'Contact details retrever' synchronously."""
        try:
            from scraper.service import extract_contact_and_location
            
            # Execute async coroutine in the appropriate loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # In nested event loops, run in a separate thread/executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, extract_contact_and_location(url, force_playwright))
                    res = future.result(timeout=45)
            else:
                res = loop.run_until_complete(extract_contact_and_location(url, force_playwright))

            if res and res.success and res.data:
                data_dict = res.data.model_dump() if hasattr(res.data, "model_dump") else res.data.dict()
                return self._map_to_company_contact_info(data_dict, url)
        except Exception as e:
            logger.warning(f"In-process extraction failed ({e}). Proceeding to resilient fallback.")
        return None

    def _fallback_deterministic_extract(self, url: str, company_name: Optional[str]) -> CompanyContactInfo:
        """Direct, lightweight crawler that fetches the homepage,
        discovering emails, phone numbers, locations, and socials using bs4 and regex.
        """
        import re
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            BeautifulSoup = None

        html_content = ""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not fetch homepage for {url}: {e}")

        emails = []
        phone_numbers = []
        social_links = {}

        if html_content and BeautifulSoup:
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Extract emails
                email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
                found_emails = set(email_pattern.findall(html_content))
                # Filter out likely image extensions and long garbage
                for e in found_emails:
                    if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']):
                        if len(e) < 50:
                            emails.append(e)

                # Extract phones (basic international format fallback)
                phone_pattern = re.compile(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}')
                for tag in soup.find_all(string=phone_pattern):
                    matches = phone_pattern.findall(tag)
                    for m in matches:
                        clean_m = re.sub(r'[^\d+]', '', m)
                        if len(clean_m) >= 7 and len(clean_m) <= 15:
                            phone_numbers.append(m.strip())
                phone_numbers = list(set(phone_numbers))

                # Extract socials
                for a in soup.find_all('a', href=True):
                    href = a['href'].lower()
                    if 'linkedin.com' in href: social_links['linkedin'] = a['href']
                    elif 'twitter.com' in href or 'x.com' in href: social_links['twitter'] = a['href']
                    elif 'facebook.com' in href: social_links['facebook'] = a['href']
                    elif 'instagram.com' in href: social_links['instagram'] = a['href']

            except Exception as e:
                logger.warning(f"Deterministic extraction error: {e}")

        return CompanyContactInfo(
            company_name=company_name,
            website=url,
            emails=list(set(emails))[:5],
            phone_numbers=list(set(phone_numbers))[:5],
            locations=[],
            social_links=social_links,
            contact_pages_found=[]
        )

    def _map_to_company_contact_info(self, data: Dict[str, Any], url: str) -> CompanyContactInfo:
        """Converts raw dictionary from retriever to CompanyContactInfo model."""
        locations_list: List[LocationInfo] = []
        for loc in data.get("locations", []):
            if isinstance(loc, dict):
                locations_list.append(LocationInfo(
                    label=loc.get("label", "Main Office"),
                    full_address=loc.get("full_address", ""),
                    street=loc.get("street"),
                    city=loc.get("city"),
                    state=loc.get("state"),
                    postal_code=loc.get("postal_code"),
                    country=loc.get("country"),
                    map_url=loc.get("map_url")
                ))
            elif hasattr(loc, "full_address"):
                locations_list.append(LocationInfo(
                    label=getattr(loc, "label", "Main Office"),
                    full_address=getattr(loc, "full_address", ""),
                    street=getattr(loc, "street", None),
                    city=getattr(loc, "city", None),
                    state=getattr(loc, "state", None),
                    postal_code=getattr(loc, "postal_code", None),
                    country=getattr(loc, "country", None),
                    map_url=getattr(loc, "map_url", None)
                ))

        return CompanyContactInfo(
            company_name=data.get("company_name"),
            website=data.get("website") or url,
            emails=data.get("emails", []),
            phone_numbers=data.get("phone_numbers", []),
            locations=locations_list,
            social_links=data.get("social_links", {}),
            contact_pages_found=data.get("contact_pages_found", []),
            operating_hours=data.get("operating_hours"),
            contact_form_urls=data.get("contact_form_urls", []),
            description=data.get("description"),
            identified_contact_topics=data.get("identified_contact_topics", [])
        )
