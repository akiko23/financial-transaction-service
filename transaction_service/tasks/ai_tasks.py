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

cfg = load_config(os.getenv('TRANSACTION_SERVICE_CONFIG_PATH', './configs/app.toml'))
celery_app = Celery('tasks', broker=cfg.rabbitmq.uri)


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

            try:
                result = analyze_text()

                oldest_ts_time = await repo.get_oldest_ts(user_id=transaction.user_id)
                print(oldest_ts_time)
                # if transaction.withdraw and oldest_ts_time < (datetime.now() - timedelta(days=29)):
                print('Fimoz cat: ', result['category'])
                avg = await repo.get_avg_withdrawal_by_category(
                    user_id=transaction.user_id,
                    category=result['category'],
                )
                if avg is not None:
                    coef = (transaction.withdraw - avg) / avg
                    if coef > 20:
                        coef = 5
                    elif coef > 10:
                        coef = 3
                    elif coef > 5:
                        coef = 2
                    else:
                        coef = 1
                else:
                    coef = 0
                await repo.update_analysis(
                    transaction_id,
                    category=result["category"],
                    status="completed",
                    expediency=coef,
                )
            except Exception:
                await repo.update_status(transaction_id, "failed")
                raise  # Повторно выбрасываем исключение для логирования Celery

    return run_async(inner())


@celery_app.task
def process_fit_model():
    print('fitting model..')
    async def inner():
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = TransactionRepository(session=session)

            edited = await repo.get_all_edited()
            if len(edited) > 10:
                # fit_model(edited)
                pass
            await repo.drop_edited()
    return run_async(inner())


# Celery forces doing outer encapsulation
class AIRemoteTransactionAnalyzer:
    def analyze(self, transaction_id: UUID):
        process_transaction_analysis.delay(transaction_id)
        TOTAL_MESSAGES_PRODUCED.inc()

    def fit_model(self):
        process_transaction_analysis.delay()
        TOTAL_MESSAGES_PRODUCED.inc()
