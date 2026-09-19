import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from openai import AsyncOpenAI
import config
from scraper.models import ContactDetails, LocationInfo

logger = logging.getLogger("ai_extractor")

TOPIC_VERIFIER_SYSTEM_PROMPT = """You are an intelligent web structure analyzer.
Analyze the provided list of topic/section headings from a website.
Identify which topic ID(s) directly represent contact information, office locations, headquarters, branch addresses, customer service, or get-in-touch options.

Respond with ONLY a valid JSON object matching this schema:
{
  "contact_topic_ids": [list of integer IDs],
  "reasoning": "Brief explanation of why these topics were chosen"
}
Rules:
1. Include topics representing contact us, locations, offices, reach us, footers with corporate address, or customer support.
2. Exclude purely marketing, services, blogs, pricing, or terms of service unless they explicitly indicate contact details.
3. If no topic clearly represents contact info, return an empty list for "contact_topic_ids".
4. Output strictly valid JSON with no markdown formatting or backticks.
"""

CONTACT_EXTRACTOR_SYSTEM_PROMPT = """You are an intelligent data extraction specialist.
Analyze the provided text excerpt, which is STRICTLY from the verified contact and location sections of a website.
Extract verified company contact details and location information.

DEDUPLICATION AND CANONICALIZATION RULES (CRITICAL):
1. DEDUPLICATE PHONE NUMBERS: Never output the same phone number multiple times under different formats.
   For example, if you see '+94 112 214 4917' and '+941122144917', or '011 221 44917' and '+94 11 221 44917', recognize that they are the EXACT SAME phone number. Return ONLY ONE single, standardized international phone number (e.g. '+94 11 221 44917').
2. DEDUPLICATE EMAILS: Return each unique email address only once in lowercase. Discard duplicate aliases or identical inboxes.
3. DEDUPLICATE LOCATIONS: If multiple address strings refer to the same physical office / branch (e.g. '651 Kotte Rd, Kotte' vs '651 Kotte Road, Sri Jayawardenepura Kotte, Sri Lanka'), merge them into ONE canonical location entry with the most complete address and postal details.
4. Only extract real, plausible contact info belonging to the company/website. Discard placeholder or template data.
5. If no physical address is found, return an empty list for "locations".
6. Output strictly valid JSON matching the schema with no markdown backticks or commentary.

Respond with ONLY a valid JSON object matching this exact schema:
{
  "company_name": "string or null",
  "description": "Short 1-2 sentence summary of the business or null",
  "emails": ["list of unique lowercase email strings"],
  "phone_numbers": ["list of unique, deduplicated phone numbers formatted with international country code"],
  "locations": [
    {
      "label": "e.g. Headquarters, London Office, Branch",
      "full_address": "Complete formatted street address",
      "street": "Street address or null",
      "city": "City or null",
      "state": "State/Province/Region or null",
      "postal_code": "Postal or ZIP code or null",
      "country": "Country name or null",
      "map_url": "Google maps or navigation link if present in text, else null"
    }
  ],
  "operating_hours": "e.g. Mon-Fri 9:00 AM - 6:00 PM or null"
}
"""

async def verify_contact_topics_with_openai(
    topics: List[Dict[str, Any]],
    base_url: str
) -> Tuple[List[int], List[str]]:
    """
    STAGE 1: Sends ONLY topic titles/headings to OpenAI.
    OpenAI verifies and returns the topic IDs representing contact information.
    """
    api_key = config.OPENAI_API_KEY
    if not api_key or not topics:
        return [], []

    # Prepare lightweight payload containing ONLY IDs and topic titles
    topics_payload = [
        {"id": t["id"], "topic": t["topic"]}
        for t in topics
    ]

    try:
        client = AsyncOpenAI(api_key=api_key)
        user_prompt = f"Website: {base_url}\nExtracted Topics/Headings:\n{json.dumps(topics_payload, indent=2)}"

        logger.info(f"Stage 1: Sending {len(topics_payload)} topics to OpenAI to verify contact options...")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": TOPIC_VERIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500,
            timeout=15.0
        )

        content = response.choices[0].message.content
        if not content:
            return [], []

        parsed = json.loads(content)
        selected_ids = parsed.get("contact_topic_ids", [])
        if not isinstance(selected_ids, list):
            selected_ids = []

        # Convert to int IDs
        valid_ids = [int(i) for i in selected_ids if str(i).isdigit()]
        matched_titles = [t["topic"] for t in topics if t["id"] in valid_ids]
        logger.info(f"Stage 1 Complete: OpenAI verified contact topics: {matched_titles} (IDs: {valid_ids})")
        return valid_ids, matched_titles

    except Exception as exc:
        logger.warning(f"Stage 1 topic verification failed: {exc}. Proceeding with fallback.")
        return [], []

async def extract_details_from_contact_section(
    section_text: str,
    base_url: str,
    initial_data: ContactDetails
) -> Tuple[ContactDetails, bool]:
    """
    STAGE 2: Sends ONLY the isolated contact section content to OpenAI.
    Extracts structured company contacts and locations.
    """
    api_key = config.OPENAI_API_KEY
    if not api_key:
        return initial_data, False

    try:
        client = AsyncOpenAI(api_key=api_key)
        user_prompt = f"""Website: {base_url}
Deterministic Pre-extracted Data:
- Emails: {initial_data.emails}
- Phones: {initial_data.phone_numbers}
- Locations: {[loc.full_address for loc in initial_data.locations]}

Target Contact Section Content:
{section_text}

CRITICAL DEDUPLICATION REQUIREMENT:
Carefully inspect all numbers, emails, and locations. Check if the same phone number or location is repeated again and again in different formats (for example, '+94 112 214 4917' vs '+941122144917', or local vs international format).
Combine and return ONLY ONE canonical, clean version for each unique contact line. Do NOT return duplicates.
"""

        logger.info(f"Stage 2: Sending targeted contact section ({len(section_text)} chars) to OpenAI...")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CONTACT_EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1500,
            timeout=20.0
        )

        content = response.choices[0].message.content
        if not content:
            return initial_data, False

        parsed = json.loads(content)
        from scraper.extractor import deduplicate_phone_numbers, deduplicate_locations

        # Merge results
        company_name = parsed.get("company_name") or initial_data.company_name
        description = parsed.get("description") or initial_data.description
        operating_hours = parsed.get("operating_hours") or initial_data.operating_hours

        # Deduplicate emails
        raw_emails = list(initial_data.emails)
        for e in parsed.get("emails", []):
            if isinstance(e, str) and "@" in e:
                raw_emails.append(e.strip().lower())
        unique_emails = sorted(list({e for e in raw_emails if e}))

        # Deduplicate phones: check OpenAI returned phones first, then verify with deduplicate_phone_numbers
        parsed_phones = [
            p.strip() for p in parsed.get("phone_numbers", [])
            if isinstance(p, str) and len(p.strip()) > 5
        ]
        # Combine with initial data and deduplicate any overlapping / repeated numbers
        raw_phones = parsed_phones + list(initial_data.phone_numbers)
        unique_phones = deduplicate_phone_numbers(raw_phones)

        # Extra OpenAI verification if multiple phone numbers remain
        if len(unique_phones) > 1:
            unique_phones = await verify_phone_deduplication_with_openai(client, unique_phones, base_url)

        # Merge and deduplicate locations
        final_locations: List[LocationInfo] = list(initial_data.locations)
        for loc_dict in parsed.get("locations", []):
            if not isinstance(loc_dict, dict):
                continue
            full_addr = (loc_dict.get("full_address") or "").strip()
            if full_addr:
                final_locations.append(LocationInfo(
                    label=loc_dict.get("label") or "Office",
                    full_address=full_addr,
                    street=loc_dict.get("street"),
                    city=loc_dict.get("city"),
                    state=loc_dict.get("state"),
                    postal_code=loc_dict.get("postal_code"),
                    country=loc_dict.get("country"),
                    map_url=loc_dict.get("map_url")
                ))

        unique_locations = deduplicate_locations(final_locations)

        enriched = ContactDetails(
            company_name=company_name,
            website=base_url,
            emails=unique_emails,
            phone_numbers=unique_phones,
            locations=unique_locations,
            social_links=initial_data.social_links,
            contact_pages_found=initial_data.contact_pages_found,
            operating_hours=operating_hours,
            contact_form_urls=initial_data.contact_form_urls,
            description=description,
            identified_contact_topics=initial_data.identified_contact_topics
        )

        return enriched, True

    except Exception as exc:
        logger.warning(f"Stage 2 contact extraction failed: {exc}. Using deterministic results.")
        return initial_data, False

async def verify_phone_deduplication_with_openai(
    client: AsyncOpenAI,
    phone_numbers: List[str],
    base_url: str
) -> List[str]:
    """
    Asks OpenAI to check if any extracted phone numbers are duplicate representations
    of the same phone line (e.g. with different spacing, dashes, or local vs international format).
    """
    try:
        prompt = f"""Website: {base_url}
List of extracted phone numbers:
{json.dumps(phone_numbers)}

Check if any of these phone numbers represent the same phone line repeated under different formats (e.g., '+94 112 214 4917' vs '+941122144917').
Return ONLY a JSON object:
{{
  "unique_phone_numbers": ["deduplicated list of unique phone numbers"]
}}"""
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a phone number deduplication specialist. Return strictly JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=300,
            timeout=10.0
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        openai_phones = data.get("unique_phone_numbers")
        if isinstance(openai_phones, list) and openai_phones:
            from scraper.extractor import deduplicate_phone_numbers
            return deduplicate_phone_numbers(openai_phones)
    except Exception as exc:
        logger.debug(f"OpenAI phone deduplication check skipped: {exc}")
    
    from scraper.extractor import deduplicate_phone_numbers
    return deduplicate_phone_numbers(phone_numbers)

async def enrich_with_openai_two_stage(
    topics: List[Dict[str, Any]],
    base_url: str,
    initial_data: ContactDetails
) -> Tuple[ContactDetails, bool, List[str]]:
    """
    Two-stage AI enrichment:
    1. First sends topics only to OpenAI to verify what is the contact information option.
    2. Then sends strictly the section under that contact information topic.
    """
    from scraper.extractor import filter_sections_by_ids

    # Stage 1: Send only topics to OpenAI
    selected_ids, identified_topics = await verify_contact_topics_with_openai(topics, base_url)

    # Stage 2: Isolate only the section text under the verified topic(s)
    contact_section_text = filter_sections_by_ids(topics, selected_ids)
    initial_data.identified_contact_topics = identified_topics

    # Stage 3: Send only that section to OpenAI
    enriched, success = await extract_details_from_contact_section(
        contact_section_text,
        base_url,
        initial_data
    )
    enriched.identified_contact_topics = identified_topics
    return enriched, success, identified_topics

async def enrich_with_openai(
    text_context: str,
    base_url: str,
    initial_data: ContactDetails
) -> Tuple[ContactDetails, bool]:
    """Backward-compatible single-pass wrapper."""
    return await extract_details_from_contact_section(text_context, base_url, initial_data)

