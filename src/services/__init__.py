from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.storage.base import DataRepository

from .analytics import AnalyticsService
from .compliance import ComplianceService
from .image_generation import NanoBananaClient
from .memory import MemoryService
from .scheduling import SchedulingService
from .scoring import ScoringService
from .web_search import WebSearchService


@dataclass
class ServiceContainer:
    repository: DataRepository
    analytics: AnalyticsService
    scoring: ScoringService
    compliance: ComplianceService
    memory: MemoryService
    scheduling: SchedulingService
    image_generation: NanoBananaClient
    web_search: WebSearchService


def build_services(settings: Settings, repository: DataRepository) -> ServiceContainer:
    analytics = AnalyticsService(repository)
    return ServiceContainer(
        repository=repository,
        analytics=analytics,
        scoring=ScoringService(analytics),
        compliance=ComplianceService(repository),
        memory=MemoryService(repository),
        scheduling=SchedulingService(repository),
        image_generation=NanoBananaClient(
            api_key=settings.gemini_api_key or settings.nano_banana_api_key,
            model=settings.nano_banana_model,
            output_dir=settings.generated_images_dir,
        ),
        web_search=WebSearchService(
            provider=settings.web_search_provider,
            api_key=settings.web_search_api_key,
            tavily_base_url=settings.web_search_tavily_base_url,
            serpapi_base_url=settings.web_search_serpapi_base_url,
            default_max_results=settings.web_search_max_results,
        ),
    )
