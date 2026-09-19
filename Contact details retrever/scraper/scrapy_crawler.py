import os
import sys

# Ensure root directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
import argparse
import asyncio
from typing import Dict, Any, List
from urllib.parse import urlparse, urljoin
import scrapy
from scrapy.crawler import CrawlerProcess
from bs4 import BeautifulSoup
import config

CONTACT_KEYWORDS = [
    'contact', 'contact-us', 'contactus', 'about', 'about-us', 'aboutus',
    'location', 'locations', 'reach-us', 'find-us', 'office', 'offices',
    'support', 'get-in-touch', 'touch'
]

class ContactSpider(scrapy.Spider):
    name = "contact_spider"

    def __init__(self, start_url: str, output_file: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_url = start_url
        self.start_urls = [start_url]
        self.output_file = output_file
        parsed = urlparse(start_url)
        self.allowed_domains = [parsed.netloc.split(':')[0]]
        self.results = {
            "success": False,
            "status_code": None,
            "pages": {}, # url -> html
            "error": None
        }

    def parse(self, response):
        self.results["status_code"] = response.status
        if response.status >= 400:
            self.results["error"] = f"HTTP error {response.status}"
            self.save_and_exit()
            return

        html = response.text
        self.results["pages"][response.url] = html
        self.results["success"] = True

        # Extract internal links for contact, about, locations
        soup = BeautifulSoup(html, 'html.parser')
        discovered_urls = set()
        base_domain = urlparse(response.url).netloc.lower()

        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            full_url = urljoin(response.url, href)
            parsed = urlparse(full_url)

            if parsed.netloc.lower() != base_domain:
                continue

            path_lower = parsed.path.lower()
            text_lower = a.get_text(separator=' ', strip=True).lower()

            if any(kw in path_lower for kw in CONTACT_KEYWORDS) or any(kw in text_lower for kw in CONTACT_KEYWORDS):
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean_url not in self.results["pages"] and clean_url != self.start_url:
                    discovered_urls.add(clean_url)

        # Limit to top contact pages
        for next_url in list(discovered_urls)[:config.MAX_PAGES_PER_DOMAIN]:
            yield response.follow(
                next_url,
                callback=self.parse_subpage,
                errback=self.handle_subpage_error
            )

    def parse_subpage(self, response):
        if response.status == 200:
            self.results["pages"][response.url] = response.text

    def handle_error(self, failure):
        self.results["error"] = str(failure.value)
        self.save_and_exit()

    def handle_subpage_error(self, failure):
        # Non-fatal for subpages
        pass

    def closed(self, reason):
        self.save_and_exit()

    def save_and_exit(self):
        try:
            out_dir = os.path.dirname(self.output_file)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False)
        except Exception as e:
            sys.stderr.write(f"Error saving results: {e}\n")


def execute_spider(target_url: str, output_file: str):
    settings = {
        'USER_AGENT': config.DEFAULT_USER_AGENT,
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_TIMEOUT': config.REQUEST_TIMEOUT_SECONDS,
        'RETRY_TIMES': 1,
        'LOG_LEVEL': 'WARNING',
        'HTTPERROR_ALLOW_ALL': True,
        'REQUEST_FINGERPRINTER_IMPLEMENTATION': '2.7',
        'TELNETCONSOLE_ENABLED': False,
    }
    process = CrawlerProcess(settings=settings)
    process.crawl(ContactSpider, start_url=target_url, output_file=output_file)
    process.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrapy Crawler for Contact Details")
    parser.add_argument("url", help="Target URL to crawl")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    args = parser.parse_args()

    execute_spider(args.url, args.out)
