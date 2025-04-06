from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, delete

from transaction_service.models.transaction import Transaction, EditedTransaction
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

    async def save(self, transaction: Transaction):
        self.session.add(transaction)
        await self.session.commit()

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

    async def get_all_edited(self):
        stmt = select(EditedTransaction)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def drop_edited(self):
        stmt = delete(EditedTransaction)
        await self.session.execute(stmt)
        await self.session.commit()

    async def add_edited(self, transaction: EditedTransaction):
        self.session.add(transaction)
        await self.session.commit()

    async def get_avg_withdrawal_by_category(self, user_id: UUID, category: str):
        res = await self.session.execute(text(
            """
            select avg(withdraw) from transactions
            where user_id = :user_id and
            category = :cat and 
            entry_date between (now() - interval '1 month') and now()
            """),
            {'user_id': user_id, 'cat': category}
        )
        result = res.fetchone()
        return result[0] if result else None

    async def get_oldest_ts(self, user_id: UUID):
        res = await self.session.execute(text(
            """
            select created_at from transactions where user_id=:user_id order by created_at desc limit 1
            """),
            {'user_id': user_id}
        )
        return res.fetchone()


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
        expediency: int,
        status: str
    ) -> Optional[Transaction]:
        transaction = await self.get(transaction_id)
        if not transaction:
            return None
        transaction.category = category
        transaction.expediency = expediency
        transaction.processing_status = status
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction
