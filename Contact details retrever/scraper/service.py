import os
import sys
import time
import json
import logging
import tempfile
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import config
from scraper.models import ExtractionResult, ContactDetails, LocationInfo
from scraper.extractor import (
    extract_deterministic_data,
    extract_page_topics_and_sections,
    prepare_context_for_ai,
    clean_email,
    clean_phone
)
from scraper.ai_extractor import enrich_with_openai_two_stage, enrich_with_openai
from scraper.playwright_crawler import crawl_with_playwright

logger = logging.getLogger("extraction_service")

def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url
    return raw_url

def is_spa_or_empty_dom(html: str) -> bool:
    """Detect if the returned HTML is an empty single-page application wrapper."""
    if len(html.strip()) < 500:
        return True
    # Look for empty SPA mounts commonly used in React/Vue/Angular
    indicators = [
        '<div id="root"></div>',
        '<div id="app"></div>',
        '<div id="__next"></div>',
        'enable javascript to run this app',
        'you need to enable javascript',
        'please turn on javascript'
    ]
    html_lower = html.lower()
    return any(ind in html_lower for ind in indicators)

async def run_scrapy_process(target_url: str) -> Dict[str, Any]:
    """Runs the Scrapy crawler in an isolated Python subprocess."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        output_path = tmp_file.name

    try:
        # Use the virtualenv python executable if available
        python_exe = sys.executable

        crawler_script = os.path.join(os.path.dirname(__file__), "scrapy_crawler.py")
        cmd = [
            python_exe,
            crawler_script,
            target_url,
            "--out", output_path
        ]

        env = dict(os.environ)
        env["PYTHONPATH"] = str(config.BASE_DIR)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=config.REQUEST_TIMEOUT_SECONDS * 2 + 5
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "pages": {}, "error": "Scrapy crawl timed out"}

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        else:
            err_msg = stderr.decode(errors="ignore").strip() or "No output from Scrapy"
            return {"success": False, "pages": {}, "error": err_msg}

    except Exception as exc:
        return {"success": False, "pages": {}, "error": str(exc)}
    finally:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

async def extract_contact_and_location(
    url: str,
    force_playwright: bool = False
) -> ExtractionResult:
    """
    Main extraction orchestrator:
    1. Try Scrapy
    2. Fallback to Playwright if needed
    3. Extract deterministic contacts & microdata
    4. Enrich using OpenAI
    """
    start_time = time.time()
    normalized_url = normalize_url(url)
    
    pages: Dict[str, str] = {}
    method_used = "scrapy"
    fallback_occurred = False
    fallback_reason = None
    crawl_error = None

    if not force_playwright:
        logger.info(f"Attempting Scrapy crawl for: {normalized_url}")
        scrapy_res = await run_scrapy_process(normalized_url)
        
        if scrapy_res.get("success") and scrapy_res.get("pages"):
            pages = scrapy_res["pages"]
            # Check if homepage HTML is basically an empty JS shell
            first_page_html = next(iter(pages.values()), "")
            if is_spa_or_empty_dom(first_page_html):
                fallback_occurred = True
                fallback_reason = "Client-side rendered Single Page Application (SPA) detected; dynamic JS hydration required."
                logger.info(f"Scrapy triggered fallback: {fallback_reason}")
            else:
                logger.info(f"Scrapy succeeded with {len(pages)} pages.")
        else:
            fallback_occurred = True
            fallback_reason = scrapy_res.get("error") or "Scrapy failed or was blocked by host."
            logger.info(f"Scrapy failed ({fallback_reason}). Initiating Playwright fallback...")
    else:
        fallback_occurred = True
        fallback_reason = "Playwright explicitly requested by user."

    # Fallback to Playwright if needed
    if fallback_occurred and (force_playwright or not pages or fallback_reason != "Playwright explicitly requested by user"):
        method_used = "playwright"
        logger.info(f"Starting Playwright fallback for: {normalized_url}")
        pw_res = await crawl_with_playwright(normalized_url)
        if pw_res.get("success") and pw_res.get("pages"):
            pages = pw_res["pages"]
            crawl_error = None
        else:
            crawl_error = pw_res.get("error") or "Playwright failed to retrieve page."

    if not pages:
        # Both scrapers failed to fetch anything
        return ExtractionResult(
            success=False,
            url=normalized_url,
            method_used=method_used,
            fallback_occurred=fallback_occurred,
            fallback_reason=fallback_reason,
            ai_enriched=False,
            execution_time_sec=round(time.time() - start_time, 2),
            pages_crawled=[],
            data=ContactDetails(website=normalized_url),
            error=crawl_error or "Failed to retrieve any content from website."
        )

    # Deterministic extraction across all crawled pages
    all_emails = set()
    all_phones = set()
    all_locations: List[LocationInfo] = []
    all_socials: Dict[str, str] = {}
    all_contact_links = set()
    company_name = None

    for page_url, html in pages.items():
        extracted = extract_deterministic_data(html, page_url)
        all_emails.update(extracted.emails)
        all_phones.update(extracted.phone_numbers)
        all_socials.update(extracted.social_links)
        all_contact_links.update(extracted.contact_pages_found)
        if not company_name and extracted.company_name:
            company_name = extracted.company_name

        for loc in extracted.locations:
            if not any(l.full_address.lower() == loc.full_address.lower() for l in all_locations if l.full_address):
                all_locations.append(loc)

    base_details = ContactDetails(
        company_name=company_name,
        website=normalized_url,
        emails=sorted(list(all_emails)),
        phone_numbers=sorted(list(all_phones)),
        locations=all_locations,
        social_links=all_socials,
        contact_pages_found=sorted(list(all_contact_links))
    )

    # AI Enrichment step via OpenAI (Two-Stage Workflow)
    # Stage 1: Discover topics from crawled pages and verify with OpenAI what is the contact option
    # Stage 2: Send strictly the isolated section content under that contact topic to OpenAI
    topics = extract_page_topics_and_sections(pages)
    enriched_details, ai_success, identified_topics = await enrich_with_openai_two_stage(
        topics,
        normalized_url,
        base_details
    )

    total_time = round(time.time() - start_time, 2)
    return ExtractionResult(
        success=True,
        url=normalized_url,
        method_used=method_used,
        fallback_occurred=fallback_occurred,
        fallback_reason=fallback_reason,
        ai_enriched=ai_success,
        execution_time_sec=total_time,
        pages_crawled=list(pages.keys()),
        identified_contact_topics=identified_topics,
        data=enriched_details
    )
