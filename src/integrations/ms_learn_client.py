# Copyright (c) Microsoft. All rights reserved.

"""
Microsoft Learn Client.
Searches learn.microsoft.com for documentation using the public search API.
"""

import logging
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger(__name__)


class MsLearnClient:
    """
    Client for searching Microsoft Learn documentation.

    Uses the public Microsoft Learn search API at
    https://learn.microsoft.com/api/search to find authoritative
    documentation for Microsoft products and technologies.
    """

    SEARCH_URL = "https://learn.microsoft.com/api/search"

    # Default search parameters scoped to English, Microsoft docs
    DEFAULT_PARAMS = {
        "locale": "en-us",
        "facet": "category",
        "$top": 5,
    }

    def __init__(self):
        self._http_timeout = 15  # seconds

    async def search_term(self, term: str) -> Optional[Dict[str, str]]:
        """
        Search for a term on Microsoft Learn and return the best match.

        Args:
            term: The search query (e.g., "Dynamics 365 Sales pipeline").

        Returns:
            Dict with 'title', 'summary', 'url' or None if no results.
        """
        results = await self.search(term, top=1)
        return results[0] if results else None

    async def search(self, query: str, top: int = 5) -> List[Dict[str, str]]:
        """
        Search Microsoft Learn and return up to *top* results.

        Each result dict contains: title, summary, url.

        Args:
            query: Search query string.
            top: Maximum number of results (1-10).

        Returns:
            List of result dicts, may be empty.
        """
        if not query or not query.strip():
            return []

        params = {**self.DEFAULT_PARAMS, "search": query.strip(), "$top": min(top, 10)}

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(self.SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            results_raw = data.get("results", [])
            results = []
            for item in results_raw:
                title = item.get("title", "").strip()
                url = item.get("url", "").strip()
                description = item.get("description", "").strip()

                if not title or not url:
                    continue

                # Ensure URLs are absolute
                if url.startswith("/"):
                    url = f"https://learn.microsoft.com{url}"

                results.append({
                    "title": title,
                    "summary": description,
                    "url": url,
                })

            logger.info(
                "MS Learn search '%s' returned %d result(s)", query, len(results)
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error("MS Learn search HTTP error: %s %s", e.response.status_code, e.response.text[:200])
            return []
        except Exception as e:
            logger.error("MS Learn search failed: %s", e)
            return []

    async def search_multiple_terms(self, terms: List[str], top_per_term: int = 2) -> List[Dict[str, str]]:
        """
        Search for multiple terms and return deduplicated results.

        Useful for enriching a meeting summary with documentation links
        for all products/technologies mentioned.

        Args:
            terms: List of search queries.
            top_per_term: Results to fetch per term.

        Returns:
            Deduplicated list of result dicts.
        """
        seen_urls = set()
        all_results = []

        for term in terms:
            results = await self.search(term, top=top_per_term)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)

        logger.info(
            "MS Learn multi-search: %d terms -> %d unique results",
            len(terms), len(all_results),
        )
        return all_results
