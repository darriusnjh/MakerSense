from __future__ import annotations

from typing import Any

import requests


class WebSearchService:
    def __init__(
        self,
        provider: str,
        api_key: str,
        tavily_base_url: str,
        serpapi_base_url: str,
        default_max_results: int = 5,
    ):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()
        self.tavily_base_url = tavily_base_url.rstrip("/")
        self.serpapi_base_url = serpapi_base_url.rstrip("/")
        self.default_max_results = max(1, default_max_results)

    def _mock_results(self, query: str) -> dict[str, Any]:
        return {
            "provider": "mock",
            "query": query,
            "status": "mock",
            "results": [
                {
                    "title": "Web search not configured",
                    "url": "https://example.com/mock-web-search",
                    "snippet": (
                        "Set WEB_SEARCH_PROVIDER and WEB_SEARCH_API_KEY to enable "
                        "real web results."
                    ),
                }
            ],
        }

    @staticmethod
    def _limit(max_results: int | None, default: int) -> int:
        if max_results is None:
            return default
        return min(10, max(1, max_results))

    def _search_tavily(self, query: str, max_results: int) -> dict[str, Any]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        }
        response = requests.post(self.tavily_base_url, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        rows = body.get("results", [])
        parsed = [
            {
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "snippet": row.get("content", ""),
                "score": row.get("score"),
            }
            for row in rows
        ]
        return {
            "provider": "tavily",
            "query": query,
            "status": "ok",
            "results": parsed,
        }

    def _search_serpapi(self, query: str, max_results: int) -> dict[str, Any]:
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": max_results,
        }
        response = requests.get(self.serpapi_base_url, params=params, timeout=30)
        response.raise_for_status()
        body = response.json()
        rows = body.get("organic_results", [])
        parsed = [
            {
                "title": row.get("title", ""),
                "url": row.get("link", ""),
                "snippet": row.get("snippet", ""),
                "position": row.get("position"),
            }
            for row in rows[:max_results]
        ]
        return {
            "provider": "serpapi",
            "query": query,
            "status": "ok",
            "results": parsed,
        }

    def search(
        self,
        query: str,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            return {
                "provider": self.provider or "unknown",
                "query": query,
                "status": "error",
                "results": [],
                "error": "Query cannot be empty.",
            }

        limit = self._limit(max_results, self.default_max_results)
        if self.provider == "none" or not self.api_key:
            return self._mock_results(query)

        try:
            if self.provider == "tavily":
                return self._search_tavily(query, limit)
            if self.provider == "serpapi":
                return self._search_serpapi(query, limit)
            return {
                "provider": self.provider,
                "query": query,
                "status": "error",
                "results": [],
                "error": f"Unsupported provider: {self.provider}",
            }
        except Exception as exc:  # pragma: no cover - network path
            return {
                "provider": self.provider,
                "query": query,
                "status": "error",
                "results": [],
                "error": str(exc),
            }

