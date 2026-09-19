import asyncio
import logging
from typing import Dict, Any, List, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import config

logger = logging.getLogger("playwright_crawler")

CONTACT_KEYWORDS = [
    'contact', 'contact-us', 'contactus', 'about', 'about-us', 'aboutus',
    'location', 'locations', 'reach-us', 'find-us', 'office', 'offices',
    'support', 'get-in-touch', 'touch'
]

async def crawl_with_playwright(target_url: str) -> Dict[str, Any]:
    """
    Crawls target URL and discovered contact pages using headless Playwright.
    Returns:
    {
        "success": bool,
        "pages": Dict[str, str], # url -> rendered html
        "error": Optional[str]
    }
    """
    result: Dict[str, Any] = {
        "success": False,
        "pages": {},
        "error": None
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )

            context = await browser.new_context(
                user_agent=config.DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                ignore_https_errors=True
            )

            # Prevent webdriver detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = await context.new_page()

            # Navigate to homepage
            try:
                try:
                    response = await page.goto(
                        target_url,
                        wait_until="load",
                        timeout=22000
                    )
                except Exception:
                    response = await page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=20000
                    )

                # Wait for SPA client-side dynamic hydration (React, Vue, Angular mounting)
                try:
                    await page.wait_for_selector(
                        "#root > *, #app > *, #__next > *, main, footer, header, a[href]",
                        timeout=5000
                    )
                except Exception:
                    pass

                # Allow client-side rendering to settle
                await page.wait_for_timeout(2500)
                
                # Check status code if available
                if response and response.status >= 400:
                    result["error"] = f"HTTP error {response.status}"
                    await browser.close()
                    return result

                html = await page.content()
                actual_url = page.url or target_url
                result["pages"][actual_url] = html
                result["success"] = True

            except Exception as e:
                result["error"] = f"Navigation failed: {str(e)}"
                await browser.close()
                return result

            # Discover contact links in the rendered DOM
            soup = BeautifulSoup(html, 'html.parser')
            base_domain = urlparse(actual_url).netloc.lower()
            discovered_urls: Set[str] = set()

            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                full_url = urljoin(actual_url, href)
                parsed = urlparse(full_url)

                if parsed.netloc.lower() != base_domain:
                    continue

                path_lower = parsed.path.lower()
                text_lower = a.get_text(separator=' ', strip=True).lower()

                if any(kw in path_lower for kw in CONTACT_KEYWORDS) or any(kw in text_lower for kw in CONTACT_KEYWORDS):
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean_url not in result["pages"] and clean_url != actual_url:
                        discovered_urls.add(clean_url)

            # Visit up to MAX_PAGES_PER_DOMAIN contact pages
            for sub_url in list(discovered_urls)[:config.MAX_PAGES_PER_DOMAIN]:
                try:
                    sub_page = await context.new_page()
                    await sub_page.goto(sub_url, wait_until="domcontentloaded", timeout=15000)
                    await sub_page.wait_for_timeout(1000)
                    sub_html = await sub_page.content()
                    result["pages"][sub_url] = sub_html
                    await sub_page.close()
                except Exception as sub_err:
                    logger.debug(f"Failed to crawl subpage {sub_url}: {sub_err}")

            await browser.close()
            return result

    except Exception as exc:
        result["error"] = f"Playwright error: {str(exc)}"
        return result
