from datetime import datetime
from decimal import Decimal

from pydantic import UUID4, BaseModel, ConfigDict


class TransactionCreate(BaseModel):
    user_id: UUID4
    entry_date: datetime = datetime.now()
    receipt_date: datetime = datetime.now()
    withdraw: Decimal
    balance: Decimal
    deposit: Decimal


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    user_id: UUID4
    entry_date: datetime
    receipt_date: datetime
    withdraw: Decimal
    deposit: Decimal
    processing_status: str
    category: str | None
    balance: Decimal
    created_at: datetime
    expediency: int | None


class ManyTransactionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    results: list[TransactionResponse]
