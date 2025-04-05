from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, HTTPException, status, Query, UploadFile
from fastapi.responses import Response
from redis.asyncio import Redis

from transaction_service.schemas.transaction import TransactionCreate, TransactionResponse, ManyTransactionsResponse
from transaction_service.services.transaction_service import TransactionService
from transaction_service.utils.cache import cache
from transaction_service.utils.metrics import (
    CREATE_TRANSACTION_METHOD_DURATION,
    GET_ALL_TRANSACTIONS_METHOD_DURATION,
    measure_latency,
)

router = APIRouter(route_class=DishkaRoute)


@router.post("/transactions/", response_model=TransactionResponse)
@measure_latency(CREATE_TRANSACTION_METHOD_DURATION)
async def create_transaction(
        transaction: TransactionCreate,
        service: FromDishka[TransactionService]
):
    new_transaction = await service.create_transaction(transaction)
    return Response(
        status_code=status.HTTP_201_CREATED,
        content=new_transaction.model_dump_json(indent=4)
    )


@router.get("/transactions/", response_model=ManyTransactionsResponse)
@measure_latency(GET_ALL_TRANSACTIONS_METHOD_DURATION)
async def create_transaction(
        user_id: UUID,
        service: FromDishka[TransactionService],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        offset: int = 0,
        limit: int = 10,
):
    user_transactions = await service.get_transactions_by_user_id(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return user_transactions


@router.post("/transactions/load-account-statement/")
async def process_account_statement(
        user_id: Annotated[UUID, Query(...)],
        bank: Annotated[str, Query(...)],
        file: UploadFile,
        service: FromDishka[TransactionService]
):
    content = await file.read()
    res = await service.process_account_statement(user_id=user_id, bank=bank, pdf_file=content)
    return res


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
@cache(ttl=2)
async def get_transaction(
        transaction_id: UUID,
        redis_client: FromDishka[Redis],  # noqa
        service: FromDishka[TransactionService]
):
    transaction = await service.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction_category(
        transaction_id: UUID,
        category: str,
        service: FromDishka[TransactionService]
):
    await service.update_ts_category(transaction_id, category)
