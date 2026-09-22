import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("LeadLoader")

class LeadLoader:
    """Helper class to load lead profiles, post reports, and company reports from files or endpoints."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.cache_dir = self.base_dir / "data" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_sample_data(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Loads sample lead, sample posts report, and sample company report."""
        lead_path = self.base_dir / "data" / "sample_lead.json"
        posts_path = self.base_dir / "data" / "sample_posts_report.json"
        company_path = self.base_dir / "data" / "sample_company_report.json"

        lead_data = {}
        if lead_path.exists():
            with open(lead_path, "r", encoding="utf-8") as f:
                lead_data = json.load(f)

        posts_data = {}
        if posts_path.exists():
            with open(posts_path, "r", encoding="utf-8") as f:
                posts_data = json.load(f)

        company_data = {}
        if company_path.exists():
            with open(company_path, "r", encoding="utf-8") as f:
                company_data = json.load(f)

        return lead_data, posts_data, company_data

    def load_from_scraped_profiles_file(
        self,
        file_path: Optional[Path] = None,
        index: int = 0
    ) -> Dict[str, Any]:
        """Loads a lead from scraped_profiles (2).json, supporting both legacy and new schema."""
        path = file_path or (self.base_dir / "scraped_profiles (2).json")
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Check for "leads" array in new schema
            if "leads" in data and isinstance(data["leads"], list):
                if len(data["leads"]) > index:
                    return data["leads"][index]
                raise IndexError(f"Lead index {index} out of range in 'leads' list.")
            return data
        elif isinstance(data, list):
            if len(data) > index:
                return data[index]
            raise IndexError(f"Index {index} out of range in profiles array.")

        raise ValueError(f"Unrecognized format in {path}")

    def fetch_url_json(self, url: str, cache_filename: Optional[str] = None) -> Dict[str, Any]:
        """Downloads JSON from an HTTP/S3 URL, with local caching and multi-tiered fallback for resilience."""
        if not url or not url.startswith("http"):
            return {}

        cache_file = self.cache_dir / (cache_filename or "cached_report.json") if cache_filename else None

        try:
            logger.info(f"Fetching report from URL: {url[:80]}...")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
                parsed = json.loads(content)
                if cache_file:
                    cache_file.write_text(content, encoding="utf-8")
                return parsed
        except Exception as e:
            logger.warning(f"Failed to fetch {url[:60]}: {e}. Checking local cache...")
            # Fallback 1: cache_file
            if cache_file and cache_file.exists():
                logger.info(f"Loaded fallback from cache: {cache_file}")
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)

            # Fallback 2: check URL path filename
            url_clean = url.split("?")[0]
            url_basename = Path(url_clean).name
            if url_basename:
                for candidate_dir in [self.cache_dir, self.base_dir / "data", self.base_dir / "frontend" / "data"]:
                    cand = candidate_dir / url_basename
                    if cand.exists():
                        logger.info(f"Loaded fallback from candidate file: {cand}")
                        with open(cand, "r", encoding="utf-8") as f:
                            return json.load(f)

            # Fallback 3: smart search by lead_id prefix in cache_dir
            # Extract lead_id from cache_filename (e.g. "3_posts.json" -> "3")
            lead_prefix = None
            if cache_filename:
                parts = cache_filename.split("_", 1)
                if parts[0].isdigit():
                    lead_prefix = parts[0]

            is_posts_request   = "posts"   in (url + (cache_filename or "")).lower()
            is_company_request = "company" in (url + (cache_filename or "")).lower()

            if lead_prefix and is_posts_request:
                # Try lead-id specific posts files
                for suffix in ["_posts_report.json", "_posts.json"]:
                    cand = self.cache_dir / f"{lead_prefix}{suffix}"
                    if cand.exists():
                        # Quick sanity check: make sure it actually has posts content
                        try:
                            with open(cand, "r", encoding="utf-8") as fc:
                                trial = json.load(fc)
                            if isinstance(trial, dict) and ("posts" in trial or "company_posts" in trial):
                                logger.info(f"Loaded posts fallback from {cand}")
                                return trial
                        except Exception:
                            pass

            if lead_prefix and is_company_request:
                # Try lead-id specific company files
                for suffix in ["_company_report.json", "_company.json"]:
                    cand = self.cache_dir / f"{lead_prefix}{suffix}"
                    if cand.exists():
                        try:
                            with open(cand, "r", encoding="utf-8") as fc:
                                trial = json.load(fc)
                            if isinstance(trial, dict) and "company" in trial:
                                logger.info(f"Loaded company fallback from {cand}")
                                return trial
                        except Exception:
                            pass

            # Last resort: generic fallback to lead 1 files
            if is_posts_request:
                for cand in [
                    self.cache_dir / "1_posts_report.json",
                    self.cache_dir / "1_posts.json",
                    self.base_dir / "frontend" / "data" / "posts_report.json"
                ]:
                    if cand.exists():
                        logger.info(f"Loaded generic posts fallback from {cand}")
                        with open(cand, "r", encoding="utf-8") as f:
                            return json.load(f)
            elif is_company_request:
                for cand in [
                    self.cache_dir / "1_company_report.json",
                    self.cache_dir / "1_company.json",
                    self.base_dir / "frontend" / "data" / "company_report.json"
                ]:
                    if cand.exists():
                        logger.info(f"Loaded generic company fallback from {cand}")
                        with open(cand, "r", encoding="utf-8") as f:
                            return json.load(f)

            return {}

    def load_lead_with_reports(
        self,
        index: int = 0
    ) -> Tuple[Dict[str, Any], Any, Dict[str, Any]]:
        """Loads lead at index from scraped_profiles (2).json along with posts and company reports."""
        lead = self.load_from_scraped_profiles_file(index=index)

        posts_url = lead.get("posts_report_url")
        company_url = lead.get("company_report_url")

        lead_id = lead.get("id", index + 1)

        # 1. Posts report
        posts_data = {}
        if posts_url:
            posts_data = self.fetch_url_json(posts_url, cache_filename=f"{lead_id}_posts_report.json")
        if not posts_data:
            posts_data = {"posts": []}

        # 2. Company report
        company_data = {}
        if company_url:
            company_data = self.fetch_url_json(company_url, cache_filename=f"{lead_id}_company_report.json")
        if not company_data:
            company_data = {
                "company": {
                    "name": lead.get("company_name", ""),
                    "description": "",
                    "callToActionUrl": ""
                }
            }

        return lead, posts_data, company_data

    def fetch_from_export_api(
        self,
        endpoint_url: str = "http://52.91.158.106:8000/api/leads/export",
        lead_ids: Optional[List[int]] = None,
        timeout: int = 15
    ) -> Dict[str, Any]:
        """Calls live export endpoint to fetch leads by ID."""
        if lead_ids is None:
            lead_ids = [2]

        payload = json.dumps({"lead_ids": lead_ids}).encode("utf-8")
        req = urllib.request.Request(
            endpoint_url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Export endpoint {endpoint_url} unavailable ({e}).")
            raise e

    def load_export_leads_with_reports(
        self,
        endpoint_url: str = "http://52.91.158.106:8000/api/leads/export",
        lead_ids: Optional[List[int]] = None,
        timeout: int = 20
    ) -> List[Tuple[Dict[str, Any], Any, Dict[str, Any]]]:
        """Fetches leads from the export endpoint and downloads their posts and company reports."""
        raw_res = self.fetch_from_export_api(endpoint_url=endpoint_url, lead_ids=lead_ids, timeout=timeout)
        leads_list = []
        if isinstance(raw_res, dict):
            leads_list = raw_res.get("leads", [])
        elif isinstance(raw_res, list):
            leads_list = raw_res

        results = []
        for lead in leads_list:
            lead_id = lead.get("id")
            posts_url = lead.get("posts_report_url")
            company_url = lead.get("company_report_url")

            posts_data = {}
            if posts_url:
                posts_data = self.fetch_url_json(posts_url, cache_filename=f"{lead_id}_posts_report.json")
            if not posts_data:
                posts_data = {"posts": []}

            company_data = {}
            if company_url:
                company_data = self.fetch_url_json(company_url, cache_filename=f"{lead_id}_company_report.json")
            if not company_data:
                company_data = {
                    "company": {
                        "name": lead.get("company_name", ""),
                        "description": "",
                        "callToActionUrl": ""
                    }
                }

            results.append((lead, posts_data, company_data))

        return results

    def parse_incoming_payload(
        self,
        payload: Any
    ) -> Tuple[Dict[str, Any], Any, Dict[str, Any]]:
        """Parses any incoming JSON payload (scraped webhook with S3 URLs, list of leads, nested lead, or direct object)."""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        lead = {}
        posts = []
        company = {}

        if isinstance(payload, list) and len(payload) > 0:
            first_item = payload[0]
            if isinstance(first_item, dict):
                lead = first_item
                posts = lead.get("posts", [])
                company = lead.get("company_report", {})
        elif isinstance(payload, dict):
            if "leads" in payload and isinstance(payload["leads"], list) and len(payload["leads"]) > 0:
                lead = payload["leads"][0]
            elif "lead" in payload and isinstance(payload["lead"], dict):
                lead = payload["lead"]
                posts = payload.get("posts", [])
                company = payload.get("company_report", {})
            elif "full_name" in payload or "company_name" in payload:
                lead = payload
                posts = payload.get("posts", [])
                company = payload.get("company_report", {})

        # If posts not directly supplied, try posts_report_url
        if not posts and isinstance(lead, dict) and lead.get("posts_report_url"):
            posts = self.fetch_url_json(lead.get("posts_report_url"), cache_filename=f"{lead.get('id', 'temp')}_posts.json")
        if not posts:
            posts = []

        # If company not directly supplied, try company_report_url
        if not company and isinstance(lead, dict) and lead.get("company_report_url"):
            company = self.fetch_url_json(lead.get("company_report_url"), cache_filename=f"{lead.get('id', 'temp')}_company.json")
        if not company:
            company = {
                "company": {
                    "name": lead.get("company_name", ""),
                    "description": "",
                    "callToActionUrl": ""
                }
            }

        return lead, posts, company

    def parse_all_leads_from_payload(
        self,
        payload: Any
    ) -> List[Tuple[Dict[str, Any], Any, Dict[str, Any]]]:
        """Parses all leads from an incoming JSON payload when an endpoint sends multiple leads."""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        raw_leads_list = []
        if isinstance(payload, list):
            raw_leads_list = payload
        elif isinstance(payload, dict):
            if "leads" in payload and isinstance(payload["leads"], list):
                raw_leads_list = payload["leads"]
            elif "lead" in payload and isinstance(payload["lead"], dict):
                raw_leads_list = [payload["lead"]]
            elif "full_name" in payload or "company_name" in payload:
                raw_leads_list = [payload]

        if not raw_leads_list:
            # Fallback to single lead parsing
            l, p, c = self.parse_incoming_payload(payload)
            return [(l, p, c)] if l else []

        results = []
        for item in raw_leads_list:
            if not isinstance(item, dict):
                continue

            # Support both 'posts' and 'company_posts' keys for inline payloads
            item_posts = (
                item.get("company_posts")
                or item.get("posts")
                or []
            )
            if not item_posts and item.get("posts_report_url"):
                item_posts = self.fetch_url_json(
                    item.get("posts_report_url"),
                    cache_filename=f"{item.get('id', 'temp')}_posts.json"
                )
            if not item_posts:
                item_posts = []

            # Support 'company' (inline), 'company_report', and company_report_url
            item_company = (
                item.get("company_report")
                or ({"company": item["company"]} if item.get("company") and isinstance(item["company"], dict) else None)
                or {}
            )
            if not item_company and item.get("company_report_url"):
                item_company = self.fetch_url_json(
                    item.get("company_report_url"),
                    cache_filename=f"{item.get('id', 'temp')}_company.json"
                )
            if not item_company:
                item_company = {
                    "company": {
                        "name": item.get("company_name", ""),
                        "description": "",
                        "callToActionUrl": ""
                    }
                }

            results.append((item, item_posts, item_company))

        return results
