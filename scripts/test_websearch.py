from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_settings
from src.services.web_search import WebSearchService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick web-search smoke test for this project.")
    parser.add_argument("query", help="Search query to run.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Max number of results (defaults to WEB_SEARCH_MAX_RESULTS).",
    )
    parser.add_argument(
        "--provider",
        choices=["tavily", "serpapi", "none"],
        default=None,
        help="Override WEB_SEARCH_PROVIDER for this run.",
    )
    parser.add_argument(
        "--save-json",
        default="",
        help="Optional path to save raw JSON response.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print full JSON response (otherwise summary only).",
    )
    return parser.parse_args()


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("results", [])
    first = rows[0] if rows else {}
    return {
        "provider": result.get("provider"),
        "status": result.get("status"),
        "error": result.get("error"),
        "result_count": len(rows),
        "first_result": {
            "title": first.get("title"),
            "url": first.get("url"),
            "snippet": first.get("snippet"),
        }
        if first
        else {},
    }


def main() -> None:
    args = parse_args()
    settings = get_settings()

    service = WebSearchService(
        provider=args.provider or settings.web_search_provider,
        api_key=settings.web_search_api_key,
        tavily_base_url=settings.web_search_tavily_base_url,
        serpapi_base_url=settings.web_search_serpapi_base_url,
        default_max_results=settings.web_search_max_results,
    )

    result = service.search(query=args.query, max_results=args.max_results)
    output = result if args.full else summarize(result)
    print(json.dumps(output, indent=2, ensure_ascii=True))

    if args.save_json:
        path = Path(args.save_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"Saved raw response to {path}")


if __name__ == "__main__":
    main()
