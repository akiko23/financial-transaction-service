from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from transaction_service.models.transaction import Transaction
from transaction_service.schemas.transaction import TransactionCreate


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, transaction: TransactionCreate) -> Transaction:
        db_transaction = Transaction(**transaction.model_dump())
        self.session.add(db_transaction)
        await self.session.commit()
        await self.session.refresh(db_transaction)
        return db_transaction

    async def create_account_stmt(self, transactions: list):
        for ts in transactions:
            self.session.add(Transaction(**ts))
        await self.session.commit()

    async def get(self, transaction_id: UUID) -> Optional[Transaction]:
        result = await self.session.execute(
            select(Transaction).filter(Transaction.id == transaction_id)
        )
        return result.scalars().first()

    async def get_all(
            self,
            user_id: UUID,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            skip: int = 0,
            limit: int = 10,
    ) -> tuple[list[Transaction], int]:
        base_query = select(Transaction).filter(Transaction.user_id == user_id)

        if start_date:
            base_query = base_query.filter(Transaction.receipt_date >= start_date)
        if end_date:
            base_query = base_query.filter(Transaction.receipt_date <= end_date)

        data_query = base_query.order_by(Transaction.receipt_date.desc()).offset(skip).limit(limit)
        data_result = await self.session.execute(data_query)
        transactions = list(data_result.scalars().all())

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()

        return transactions, total

    async def update_status(
        self, transaction_id: UUID, status: str
    ) -> Optional[Transaction]:
        transaction = await self.get(transaction_id)
        if not transaction:
            return None
        transaction.processing_status = status
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    async def update_analysis(
        self,
        transaction_id: UUID,
        category: str,
        confidence: float,
        status: str
    ) -> Optional[Transaction]:
        transaction = await self.get(transaction_id)
        if not transaction:
            return None
        transaction.category = category
        transaction.confidence = confidence
        transaction.processing_status = status
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction
