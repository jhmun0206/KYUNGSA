"""FastAPI 의존성 주입

서비스 인스턴스를 싱글톤으로 관리한다.
.env 없어도 기본값으로 동작 (테스트 환경).
"""

from functools import lru_cache

from app.services.crawler.codef_client import CodefClient
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.enricher import CaseEnricher
from app.services.filter_engine import FilterEngine
from app.services.parser.registry_analyzer import RegistryAnalyzer
from app.services.pipeline import AuctionPipeline
from app.services.registry.codef_provider import CodefRegistryProvider
from app.services.registry.pipeline import RegistryPipeline


@lru_cache()
def get_registry_pipeline() -> RegistryPipeline:
    """싱글톤 RegistryPipeline 인스턴스"""
    codef_client = CodefClient()
    provider = CodefRegistryProvider(codef_client=codef_client)
    analyzer = RegistryAnalyzer()
    return RegistryPipeline(provider=provider, analyzer=analyzer)


@lru_cache()
def get_pipeline() -> AuctionPipeline:
    """싱글톤 AuctionPipeline 인스턴스"""
    crawler = CourtAuctionClient()
    enricher = CaseEnricher()
    filter_engine = FilterEngine()
    registry_pipeline = get_registry_pipeline()
    return AuctionPipeline(
        crawler=crawler,
        enricher=enricher,
        filter_engine=filter_engine,
        registry_pipeline=registry_pipeline,
    )
