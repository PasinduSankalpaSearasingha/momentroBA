import re
import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional, Tuple, Any
from scraper.models import LocationInfo, ContactDetails

# Regex patterns
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
)

# Phone regex matching international & local formats (e.g. +1 555-123-4567, +94 11 234 5678, (012) 345-6789)
PHONE_REGEX = re.compile(
    r'(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,5}\b'
)

SOCIAL_DOMAINS = {
    'linkedin': ['linkedin.com'],
    'twitter': ['twitter.com', 'x.com'],
    'facebook': ['facebook.com', 'fb.com'],
    'instagram': ['instagram.com'],
    'youtube': ['youtube.com'],
    'github': ['github.com']
}

CONTACT_KEYWORDS = [
    'contact', 'contact-us', 'contactus', 'about', 'about-us', 'aboutus',
    'location', 'locations', 'reach-us', 'find-us', 'office', 'offices',
    'support', 'get-in-touch', 'touch'
]

# File extensions to ignore for email false-positives
IGNORED_EMAIL_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.woff', '.woff2'}

# Discard common placeholder or vendor emails
DISCARD_EMAILS = {
    'example@example.com', 'youremail@example.com', 'email@example.com',
    'info@domain.com', 'test@test.com', 'sentry@sentry.io'
}

def clean_email(email: str) -> Optional[str]:
    email = email.strip().lower()
    for ext in IGNORED_EMAIL_EXTS:
        if email.endswith(ext):
            return None
    if email in DISCARD_EMAILS:
        return None
    if 'w3.org' in email or 'schema.org' in email or 'domain.com' in email:
        return None
    return email

def clean_phone(phone: str) -> Optional[str]:
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Require at least 7 digits and at most 15 digits (standard E.164)
    digits_only = re.sub(r'\D', '', cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return None
    # Filter out obvious fake/year/sequential numbers like 12345678, 20242025
    if digits_only in ("12345678", "123456789", "1234567890", "0000000000"):
        return None
    return phone.strip()

def deduplicate_phone_numbers(phone_numbers: List[str]) -> List[str]:
    """
    Deduplicates phone numbers by checking if they represent the exact same core digits.
    For example: '+94 112 214 4917' and '+941122144917' have the same digits,
    so only one canonical, cleanly formatted version is preserved.
    """
    seen: Dict[str, str] = {}
    for p in phone_numbers:
        if not p or not isinstance(p, str):
            continue
        p_clean = p.strip()
        digits = re.sub(r'\D', '', p_clean)
        if len(digits) < 7:
            continue

        matched_key = None
        for key in seen:
            if digits == key:
                matched_key = key
                break
            # Match local vs international (e.g. 01122144917 vs 941122144917 or same suffix)
            if digits.lstrip('0') == key.lstrip('0') or digits.endswith(key[-8:]) or key.endswith(digits[-8:]):
                if abs(len(digits) - len(key)) <= 3:
                    matched_key = key
                    break

        if matched_key:
            existing = seen[matched_key]
            # Prefer international '+' prefix and clean spacing
            if ('+' in p_clean and '+' not in existing) or (p_clean.count(' ') > existing.count(' ')):
                seen[matched_key] = p_clean
        else:
            seen[digits] = p_clean

    return sorted(list(seen.values()))

def deduplicate_locations(locations: List[LocationInfo]) -> List[LocationInfo]:
    """
    Deduplicates physical locations that represent the same office/address.
    """
    unique_locations: List[LocationInfo] = []

    for loc in locations:
        addr = (loc.full_address or "").strip()
        if not addr:
            continue
        clean_addr = re.sub(r'[^\w\s]', '', addr.lower())

        duplicate_idx = None
        for i, existing in enumerate(unique_locations):
            ex_addr = re.sub(r'[^\w\s]', '', (existing.full_address or "").strip().lower())
            if clean_addr in ex_addr or ex_addr in clean_addr:
                duplicate_idx = i
                break
            if loc.street and existing.street and loc.street.lower() == existing.street.lower():
                duplicate_idx = i
                break

        if duplicate_idx is not None:
            # Keep the more comprehensive location entry
            if len(addr) > len(unique_locations[duplicate_idx].full_address):
                unique_locations[duplicate_idx] = loc
        else:
            unique_locations.append(loc)

    return unique_locations

def extract_social_links(soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
    social_links: Dict[str, str] = {}
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        
        for network, patterns in SOCIAL_DOMAINS.items():
            if any(pat in domain for pat in patterns):
                # Clean profile link
                if network not in social_links and len(parsed.path) > 1:
                    # Filter out share links
                    if 'share' not in href.lower() and 'intent' not in href.lower():
                        social_links[network] = href
    return social_links

def extract_contact_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Find links on the page that point to contact, about, or location pages."""
    base_domain = urlparse(base_url).netloc.lower()
    contact_urls = set()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        
        # Must be internal or same domain
        if parsed.netloc.lower() != base_domain:
            continue
            
        path_lower = parsed.path.lower()
        link_text = a.get_text(separator=' ', strip=True).lower()
        
        # Check URL path or anchor text for contact keywords
        matches_keyword = any(kw in path_lower for kw in CONTACT_KEYWORDS) or \
                          any(kw in link_text for kw in CONTACT_KEYWORDS)
                          
        if matches_keyword:
            # Clean url by stripping query and fragment
            clean_page_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_page_url != base_url and clean_page_url != base_url.rstrip('/') + '/':
                contact_urls.add(clean_page_url)
                
    return list(contact_urls)

def extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    """Extract schema.org JSON-LD microdata from script tags."""
    json_data = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            content = script.string
            if content:
                parsed = json.loads(content.strip())
                if isinstance(parsed, list):
                    json_data.extend(parsed)
                elif isinstance(parsed, dict):
                    if '@graph' in parsed and isinstance(parsed['@graph'], list):
                        json_data.extend(parsed['@graph'])
                    else:
                        json_data.append(parsed)
        except Exception:
            continue
    return json_data

def extract_from_json_ld(json_items: List[Dict]) -> Tuple[List[str], List[str], List[LocationInfo], Optional[str], Dict[str, str]]:
    """Parse schema.org objects for Organization, LocalBusiness, PostalAddress, ContactPoint."""
    emails = set()
    phones = set()
    locations = []
    socials: Dict[str, str] = {}
    company_name = None

    for item in json_items:
        if not isinstance(item, dict):
            continue
        item_type = item.get('@type', '')
        if isinstance(item_type, list):
            item_type = " ".join(item_type)
            
        is_org_or_biz = any(t in item_type for t in ['Organization', 'LocalBusiness', 'Corporation', 'Store', 'Restaurant', 'ProfessionalService', 'Company'])
        
        if is_org_or_biz and not company_name:
            company_name = item.get('name')

        # Emails
        if 'email' in item and item['email']:
            raw_email = str(item['email']).replace('mailto:', '')
            c_email = clean_email(raw_email)
            if c_email:
                emails.add(c_email)

        # Telephones
        if 'telephone' in item and item['telephone']:
            c_phone = clean_phone(str(item['telephone']))
            if c_phone:
                phones.add(c_phone)

        # ContactPoint support (standard schema.org for customer service, sales, etc.)
        contact_points = item.get('contactPoint', [])
        if isinstance(contact_points, dict):
            contact_points = [contact_points]
        elif not isinstance(contact_points, list):
            contact_points = []

        for cp in contact_points:
            if isinstance(cp, dict):
                cp_phone = cp.get('telephone')
                if cp_phone:
                    c_p = clean_phone(str(cp_phone))
                    if c_p:
                        phones.add(c_p)
                cp_email = cp.get('email')
                if cp_email:
                    c_e = clean_email(str(cp_email).replace('mailto:', ''))
                    if c_e:
                        emails.add(c_e)

        # Social Links from sameAs
        same_as = item.get('sameAs', [])
        if isinstance(same_as, str):
            same_as = [same_as]
        if isinstance(same_as, list):
            for link in same_as:
                if isinstance(link, str):
                    for net, patterns in SOCIAL_DOMAINS.items():
                        if any(pat in link.lower() for pat in patterns):
                            if net not in socials:
                                socials[net] = link

        # Addresses
        address = item.get('address')
        if isinstance(address, dict):
            street = address.get('streetAddress')
            city = address.get('addressLocality')
            state = address.get('addressRegion')
            postal_code = address.get('postalCode')
            country = address.get('addressCountry')
            if isinstance(country, dict):
                country = country.get('name')
                
            parts = [p for p in [street, city, state, postal_code, country] if p]
            full_addr = ", ".join(parts) if parts else ""
            
            if full_addr:
                locations.append(LocationInfo(
                    label=item.get('name', 'Main Office'),
                    full_address=full_addr,
                    street=street,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country=country
                ))
        elif isinstance(address, str) and address.strip():
            locations.append(LocationInfo(
                label=item.get('name', 'Main Office'),
                full_address=address.strip()
            ))

    return list(emails), list(phones), locations, company_name, socials

def extract_deterministic_data(html_content: str, url: str) -> ContactDetails:
    """Fast deterministic extraction from HTML using regex, microdata, and DOM."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Title / Company name heuristic
    company_name = None
    title_tag = soup.find('title')
    if title_tag and title_tag.string:
        raw_title = title_tag.string.strip()
        # Common title format: "Page Title | Company Name" or "Company Name - Home"
        parts = re.split(r'[\-|–|•:]', raw_title)
        if len(parts) > 1:
            company_name = parts[0].strip() if len(parts[0].strip()) < len(parts[-1].strip()) else parts[-1].strip()
        else:
            company_name = raw_title

    # 1. JSON-LD
    json_ld_items = extract_json_ld(soup)
    ld_emails, ld_phones, ld_locations, ld_name, ld_socials = extract_from_json_ld(json_ld_items)
    if ld_name:
        company_name = ld_name

    emails = set(ld_emails)
    phones = set(ld_phones)
    locations = list(ld_locations)

    # 2. mailto: and tel: links
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href.lower().startswith('mailto:'):
            e = clean_email(href[7:].split('?')[0])
            if e:
                emails.add(e)
        elif href.lower().startswith('tel:'):
            p = clean_phone(href[4:].split('?')[0])
            if p:
                phones.add(p)

    # 3. Google Maps links
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if any(m in href.lower() for m in ['google.com/maps', 'maps.google.com', 'goo.gl/maps']):
            # Try to associate with first location or add map link
            if locations:
                if not locations[0].map_url:
                    locations[0].map_url = href
            else:
                locations.append(LocationInfo(
                    label="Map Location",
                    full_address="",
                    map_url=href
                ))

    # 4. Text regex for emails
    body_text = soup.get_text(separator=' ')
    for match in EMAIL_REGEX.findall(body_text):
        e = clean_email(match)
        if e:
            emails.add(e)

    # 5. Extract <address> tags
    for addr_tag in soup.find_all('address'):
        addr_text = addr_tag.get_text(separator=', ', strip=True)
        if addr_text and len(addr_text) > 10:
            if not any(loc.full_address == addr_text for loc in locations):
                locations.append(LocationInfo(
                    label="Office Address",
                    full_address=addr_text
                ))

    # 6. Social links
    social_links = {**ld_socials, **extract_social_links(soup, url)}

    # 7. Contact links discovered
    contact_links = extract_contact_links(soup, url)

    return ContactDetails(
        company_name=company_name,
        website=url,
        emails=sorted(list(emails)),
        phone_numbers=deduplicate_phone_numbers(list(phones)),
        locations=deduplicate_locations(locations),
        social_links=social_links,
        contact_pages_found=contact_links
    )

def extract_page_topics_and_sections(html_pages: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Scans crawled HTML pages for semantic headings (h1-h4), sections, and footers.
    Returns a list of structured topics with their isolated section text:
    [
        {"id": 1, "topic": "Get In Touch", "page_url": "...", "content": "..."},
        ...
    ]
    """
    topics: List[Dict[str, Any]] = []
    seen_topic_titles = set()
    current_id = 1

    for page_url, html in html_pages.items():
        if not html:
            continue
        soup = BeautifulSoup(html, 'html.parser')

        # Remove noisy non-content elements
        for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'canvas']):
            tag.decompose()

        # 1. Extract Headings and their following section content
        heading_tags = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        for h in heading_tags:
            title = h.get_text(separator=' ', strip=True)
            # Filter out empty or meaningless short headers
            if len(title) < 3 or len(title) > 120 or title.isdigit():
                continue

            dedup_key = f"{title.lower()}::{page_url}"
            if dedup_key in seen_topic_titles:
                continue
            seen_topic_titles.add(dedup_key)

            # Collect section text under this heading
            section_parts = [f"### {title}"]
            
            # Check parent container (e.g. section or article or div)
            parent = h.parent
            if parent and parent.name in ['section', 'article', 'div'] and len(parent.get_text(strip=True)) < 2500:
                container_text = parent.get_text(separator=' ', strip=True)
                container_text = re.sub(r'\s+', ' ', container_text)
                section_parts.append(container_text)
            else:
                # Accumulate sibling text until next heading
                sibling_text = []
                for sib in h.next_siblings:
                    if getattr(sib, 'name', None) in ['h1', 'h2', 'h3', 'h4']:
                        break
                    if hasattr(sib, 'get_text'):
                        txt = sib.get_text(separator=' ', strip=True)
                        if txt:
                            sibling_text.append(txt)
                    elif isinstance(sib, str) and sib.strip():
                        sibling_text.append(sib.strip())
                combined_sib = " ".join(sibling_text)
                combined_sib = re.sub(r'\s+', ' ', combined_sib)
                section_parts.append(combined_sib[:2000])

            content = "\n".join(section_parts).strip()
            if len(content) > len(title) + 5:
                topics.append({
                    "id": current_id,
                    "topic": title,
                    "page_url": page_url,
                    "content": content[:2500]
                })
                current_id += 1

        # 2. Extract Footers as explicit topics
        footers = soup.find_all('footer')
        for idx, f in enumerate(footers[:2]):
            f_text = f.get_text(separator=' ', strip=True)
            f_text = re.sub(r'\s+', ' ', f_text)
            if len(f_text) > 20:
                footer_title = f"Page Footer & Corporate Info ({urlparse(page_url).path or '/'})"
                topics.append({
                    "id": current_id,
                    "topic": footer_title,
                    "page_url": page_url,
                    "content": f_text[:2000]
                })
                current_id += 1

        # 3. Extract standalone address / office containers if not caught by headings
        addr_containers = soup.find_all(
            ['div', 'section', 'address'],
            class_=re.compile(r'contact|address|location|reach|office', re.I)
        )
        for c in addr_containers[:3]:
            c_text = c.get_text(separator=' ', strip=True)
            c_text = re.sub(r'\s+', ' ', c_text)
            if 30 < len(c_text) < 2000:
                # Check if already covered
                if not any(c_text[:50].lower() in t["content"].lower() for t in topics):
                    title = f"Contact/Office Block ({urlparse(page_url).path or '/'})"
                    topics.append({
                        "id": current_id,
                        "topic": title,
                        "page_url": page_url,
                        "content": c_text
                    })
                    current_id += 1

    # Fallback: if no topics were generated (e.g. dynamic SPA or custom tags)
    if not topics:
        for page_url, html in html_pages.items():
            if not html:
                continue
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe']):
                tag.decompose()
            body_text = soup.get_text(separator=' ', strip=True)
            body_text = re.sub(r'\s+', ' ', body_text)
            if len(body_text) > 30:
                topics.append({
                    "id": current_id,
                    "topic": f"General Page Content ({urlparse(page_url).path or '/'})",
                    "page_url": page_url,
                    "content": body_text[:3500]
                })
                current_id += 1

    return topics[:40]

def filter_sections_by_ids(topics: List[Dict[str, Any]], selected_ids: List[int]) -> str:
    """
    Extracts the isolated content strictly for the selected topic IDs.
    If no topic matches or selected_ids is empty, falls back to contact/footer topics.
    """
    selected_set = set(selected_ids)
    matched_sections = []
    
    for t in topics:
        if t["id"] in selected_set:
            matched_sections.append(f"=== [Topic: {t['topic']} | Page: {t['page_url']}] ===\n{t['content']}")

    # Fallback if no matching section found
    if not matched_sections:
        contact_pattern = re.compile(r'contact|address|location|reach|office|touch|footer', re.I)
        for t in topics:
            if contact_pattern.search(t["topic"]):
                matched_sections.append(f"=== [Topic: {t['topic']} | Page: {t['page_url']}] ===\n{t['content']}")
                if len(matched_sections) >= 3:
                    break

    # Final fallback if still empty: take the last few topics (usually footer / closing info)
    if not matched_sections and topics:
        matched_sections = [f"=== [Topic: {t['topic']}] ===\n{t['content']}" for t in topics[-2:]]

    return "\n\n".join(matched_sections)[:8000]

def prepare_context_for_ai(html_pages: Dict[str, str], base_url: str) -> str:
    """
    Backward-compatible helper that gathers high-signal snippets across crawled pages.
    """
    topics = extract_page_topics_and_sections(html_pages)
    return filter_sections_by_ids(topics, [t["id"] for t in topics if re.search(r'contact|touch|reach|address|location|footer|office', t["topic"], re.I)])
