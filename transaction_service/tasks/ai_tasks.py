import asyncio
import os
from collections.abc import AsyncGenerator
from uuid import UUID

from celery import Celery
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from transaction_service.config import load_config
from transaction_service.repositories.transaction_repository import TransactionRepository
from transaction_service.services.ai_service import analyze_text
from transaction_service.utils.metrics import TOTAL_MESSAGES_PRODUCED

cfg = load_config(os.getenv('AEZAKMI_TEST_CONFIG_PATH', './configs/app.toml'))
celery_app = Celery('tasks', broker=cfg.redis.uri)


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    def get_engine(self) -> AsyncEngine:
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


container = make_async_container(DatabaseProvider())

def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)



@celery_app.task
def process_transaction_analysis(transaction_id: UUID):
    async def inner():
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = TransactionRepository(session=session)
            transaction = await repo.get(transaction_id)
            if not transaction:
                return

            await repo.update_status(transaction_id, "processing")

            try:
                result = await analyze_text(transaction)
                await repo.update_analysis(
                    transaction_id,
                    category=result["category"],
                    confidence=result["confidence"],
                    status="completed"
                )
            except Exception:
                await repo.update_status(transaction_id, "failed")
                raise  # Повторно выбрасываем исключение для логирования Celery

    return run_async(inner())


# Celery forces doing outer encapsulation
class AIRemoteTransactionAnalyzer:
    def analyze(self, transaction_id: UUID):
        process_transaction_analysis.delay(transaction_id)
        TOTAL_MESSAGES_PRODUCED.inc()
