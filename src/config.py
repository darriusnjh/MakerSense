from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model_orchestrator: str = "gpt-4.1"
    openai_model_research: str = "gpt-4.1-mini"
    openai_model_planner: str = "gpt-4.1"
    openai_model_creative: str = "gpt-4.1"
    openai_model_compliance: str = "gpt-4.1-mini"
    openai_model_review: str = "gpt-4.1-mini"

    nano_banana_api_key: str = ""
    nano_banana_base_url: str = "https://api.nanobanana.ai/v1/images/generate"
    gemini_api_key: str = ""
    nano_banana_model: str = "gemini-2.5-flash-image"
    generated_images_dir: Path = Path("data/generated_images")

    web_search_provider: Literal["tavily", "serpapi", "none"] = "tavily"
    web_search_api_key: str = ""
    web_search_max_results: int = 5
    web_search_tavily_base_url: str = "https://api.tavily.com/search"
    web_search_serpapi_base_url: str = "https://serpapi.com/search.json"

    data_backend: Literal["json", "postgres"] = "json"
    json_data_dir: Path = Path("data")
    database_url: str = ""

    default_brand_id: str = "brand_001"
    default_campaign_id: str = "campaign_001"
    max_creative_revisions: int = 1

    @property
    def model_by_agent(self) -> dict[str, str]:
        return {
            "orchestrator": self.openai_model_orchestrator,
            "research": self.openai_model_research,
            "planner": self.openai_model_planner,
            "creative": self.openai_model_creative,
            "compliance": self.openai_model_compliance,
            "review": self.openai_model_review,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
