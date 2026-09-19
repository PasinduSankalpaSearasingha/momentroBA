import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from core.llm_client import LLMClient

logger = logging.getLogger("CompetitorSearchTool")

class CompetitorSearchTool:
    """Search tool specifically built for discovering and researching industry competitors."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def search_competitors(
        self,
        company_name: str,
        description: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Executes a search for companies with similar offerings and positioning."""
        query = f"{company_name} competitors venture product builder software engineering digital products"
        logger.info(f"Searching for competitors with query: '{query}'")

        # 1. Attempt web search via lightweight search engine
        results = self._web_search(query, max_results=max_results)

        # 2. If web search returns few or blocked results, augment with grounded search synthesis
        if len(results) < 3:
            logger.info("Web search returned limited results. Augmenting with LLM-grounded market intelligence.")
            results = self._llm_market_search(company_name, description)

        return results

    def _web_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Lightweight zero-dependency web search using public search endpoints."""
        results: List[Dict[str, Any]] = []
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            req = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Simple regex parser for result snippets and titles
            pattern = re.compile(
                r'<a class="result__url" href="([^"]+)">.*?<a class="result__snippet[^"]*"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            matches = pattern.findall(html)
            for link, snippet in matches[:max_results]:
                clean_snippet = re.sub(r"<.*?>", "", snippet).strip()
                clean_link = link.strip()
                if "duckduckgo.com" not in clean_link:
                    results.append({
                        "source": "web_search",
                        "url": clean_link,
                        "snippet": clean_snippet
                    })
        except Exception as e:
            logger.warning(f"Web search attempt encountered an error: {e}. Switching to LLM intelligence.")

        return results

    def _llm_market_search(self, company_name: str, description: str) -> List[Dict[str, Any]]:
        """Grounded market intelligence search using the LLM's vast knowledge base of tech companies."""
        system_prompt = (
            "You are a Market Intelligence Search Tool specialized in competitive discovery in technology, "
            "venture building, digital transformation, and software engineering.\n"
            "Given a target company and its core description, search and identify 3 to 5 real-world companies "
            "that operate as direct or secondary competitors in the same domain.\n"
            "Return strictly a JSON object with a 'competitors' array."
        )

        user_content = {
            "target_company": company_name,
            "target_description": description,
            "instruction": (
                "Identify 3 to 5 established direct or indirect competitor companies. "
                "For each, provide 'name', 'website' (or domain), 'description', 'key_strengths', "
                "and 'how_they_compete'."
            )
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content)}
        ]

        try:
            response = self.llm_client.generate_json(messages=messages, temperature=0.2)
            items = response.get("competitors", [])
            return [
                {
                    "source": "market_intelligence_search",
                    "name": item.get("name"),
                    "url": item.get("website", ""),
                    "snippet": item.get("description", ""),
                    "key_strengths": item.get("key_strengths", []),
                    "how_they_compete": item.get("how_they_compete", "")
                }
                for item in items
            ]
        except Exception as e:
            logger.error(f"Failed to generate LLM market search: {e}")
            return []
