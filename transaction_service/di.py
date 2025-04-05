import os
from collections.abc import AsyncGenerator

from dishka import Provider, Scope, make_async_container, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from transaction_service.config import Config, load_config
from transaction_service.repositories.transaction_repository import TransactionRepository
from transaction_service.services.transaction_service import (
    TransactionAnalyzer,
    TransactionService,
    TransactionGateway,
)
from transaction_service.tasks.ai_tasks import AIRemoteTransactionAnalyzer


def config_provider() -> Provider:
    provider = Provider()

    cfg_path = os.getenv('TRANSACTION_ANALYZER_CONFIG_PATH', './configs/app.toml')
    provider.provide(lambda: load_config(cfg_path), scope=Scope.APP, provides=Config)
    return provider


class RedisProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_redis_client(self, cfg: Config) -> Redis:
        return Redis.from_url(cfg.redis.uri)


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_engine(self, cfg: Config) -> AsyncEngine:
        return create_async_engine(cfg.db.uri, echo=True)

    @provide(scope=Scope.APP)
    def get_sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker:
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def get_session(
            self,
            sessionmaker: async_sessionmaker
    ) -> AsyncGenerator[AsyncSession, None, None]:
        async with sessionmaker() as session:
            yield session


class TransactionProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_transaction_gateway(self, session: AsyncSession) -> TransactionGateway:
        return TransactionRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_financial_category_analyzer(self) -> TransactionAnalyzer:
        return AIRemoteTransactionAnalyzer()

    @provide(scope=Scope.REQUEST)
    def get_transaction_service(
            self,
            repository: TransactionGateway,
            transaction_analyzer: TransactionAnalyzer,
    ) -> TransactionService:
        return TransactionService(repository, transaction_analyzer)


def setup_di():
    return make_async_container(
        config_provider(),
        DatabaseProvider(),
        TransactionProvider(),
        RedisProvider()
    )
