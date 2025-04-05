import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Protocol
from uuid import UUID
from io import BytesIO

from transaction_service.models import Transaction
from transaction_service.models.transaction import EditedTransaction
from transaction_service.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    ManyTransactionsResponse,
)
import PyPDF2
import re
from decimal import Decimal


class TransactionGateway(Protocol):
    async def create(self, transaction: TransactionCreate) -> Transaction:
        raise NotImplementedError

    async def create_account_stmt(self, transactions: list) -> None:
        raise NotImplementedError

    async def get(self, transaction_id: UUID) -> Optional[Transaction]:
        raise NotImplementedError

    async def get_all(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> tuple[List[Transaction], int]:
        raise NotImplementedError

    async def get_avg_withdrawal_by_category(self, user_id: UUID, category: str):
        raise NotImplementedError

    async def get_oldest_ts(self, user_id: UUID):
        raise NotImplementedError

    async def save(self, transaction: Transaction):
        raise NotImplementedError

    async def add_edited(self, transaction: EditedTransaction):
        raise NotImplementedError

    async def get_all_edited(self):
        raise NotImplementedError


class TransactionAnalyzer(Protocol):
    def analyze(self, transaction_id: UUID):
        raise NotImplementedError

    def fit_model(self):
        raise NotImplementedError


class TransactionService:
    def __init__(self, repository: TransactionGateway, financial_category_analyzer: TransactionAnalyzer):
        self.repository = repository
        self.financial_category_analyzer = financial_category_analyzer

    async def create_transaction(
        self, transaction: TransactionCreate
    ) -> TransactionResponse:
        new_transaction = await self.repository.create(transaction)
        self.financial_category_analyzer.analyze(new_transaction.id)

        return TransactionResponse.model_validate(new_transaction)

    async def get_transaction(self, transaction_id: UUID) -> Optional[TransactionResponse]:
        transaction = await self.repository.get(transaction_id)
        if not transaction:
            return None
        return TransactionResponse.model_validate(transaction)

    async def process_account_statement(
        self,
        user_id: UUID,
        pdf_file: bytes,
        bank: Optional[str] = 'tbank',
    ) -> ManyTransactionsResponse:
        dict_transactions = self._parse_account_stmt(pdf_file, user_id=user_id, bank=bank)
        await self.repository.create_account_stmt(dict_transactions)

        for ts in dict_transactions:
            self.financial_category_analyzer.analyze(ts['id'])

        return ManyTransactionsResponse(
            total=len(dict_transactions),
            results=[TransactionResponse.model_validate(ts) for ts in dict_transactions],
        )

    async def get_transactions_by_user_id(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        limit: int,
        offset: int,
    ) -> ManyTransactionsResponse:
        transactions, total = await self.repository.get_all(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            skip=offset,
            limit=limit
        )

        return ManyTransactionsResponse(
            total=total,
            results=[TransactionResponse.model_validate(ts) for ts in transactions],
        )

    def _parse_account_stmt(self, pdf_content: bytes, user_id: UUID, bank: str):
        if bank == 'tbank':
            with BytesIO(pdf_content) as pdf_file:  # noqa
                read_pdf = PyPDF2.PdfReader(pdf_file)
                full_text = ""
                for page in read_pdf.pages:
                    full_text += page.extract_text()

            balance_pattern = r'Баланс на (\d{2}\.\d{2}\.\d{2})\s+([\d\s]+\.\d{2})\s*i'

            balances = re.findall(balance_pattern, full_text, re.MULTILINE)
            # Преобразование в список словарей для удобства
            balance_list = []
            for _, amount in balances:
                amount_float = float(amount.replace(' ', ''))
                balance_list.append(amount_float)

            balance_on_start, balance_on_end = map(lambda x: Decimal(x), balance_list)
            print(balance_on_start, balance_on_end)

            # pattern = r'(\d{2}\.\d{2}\.\d{2})*'
            transactions_pattern = r'(\d{2}\.\d{2}\.\d{2})\s*(?:\d{2}:\d{2})?\s+(\d{2}\.\d{2}\.\d{2})\s+([+-]?\s*\d+(?:\s*\d{3})*(?:\.\d+)?\s*i)'

            # Получаем список всех совпадений
            matches = re.findall(transactions_pattern, full_text, re.MULTILINE)

            # matches содержит список кортежей с захваченными группами

            res = []
            sum_wdraw = 0
            sum_dep = 0
            for match in matches:
                print(match, match[0], match[1])
                entry_date = self._date_from_str(match[0])
                receipt_date = self._date_from_str(match[1])

                data = {
                    'id': uuid.uuid4(),
                    'entry_date': entry_date,
                    'receipt_date': receipt_date,
                    'user_id': user_id,
                    'withdraw': Decimal(),
                    'deposit': Decimal(),
                    'processing_status': 'in_progress',
                    'category': None,
                    'expediency': 0,
                    'created_at': datetime.now(),
                }

                processed_amount = match[2].replace(' i', '')
                if "+" in processed_amount:
                    data['deposit'] = Decimal(processed_amount.replace("+ ", "").replace(" ", ""))
                else:
                    data['withdraw'] = Decimal(processed_amount.replace(" ", ""))

                balance_on_start += data['deposit'] - data['withdraw']
                data['balance'] = balance_on_start

                sum_wdraw += data['deposit']
                sum_dep += data['withdraw']
                res.append(data)

            return res

        raise NotImplementedError

    async def update_ts_category(self, transaction_id: UUID, category: str):
        ts = await self.repository.get(transaction_id)
        if ts is None:
            return None

        ts.category = category
        avg = await self.repository.get_avg_withdrawal_by_category(
            user_id=ts.user_id,
            category=ts.category,
        )
        if avg is not None:
            coef = (ts.withdraw - avg) / avg
            if coef > 20:
                coef = 5
            elif coef > 10:
                coef = 3
            elif coef > 5:
                coef = 2
            else:
                coef = 1
            ts.expediency = coef

        await self.repository.save(ts)
        await self.repository.add_edited(transaction=EditedTransaction(
            id=ts.id,
            user_id=ts.user_id,
            entry_date =ts.receipt_date,
            receipt_date = ts.receipt_date,
            withdraw=ts.withdraw,
            deposit=ts.deposit,
            created_at=datetime.now(),
            new_category=category,
            balance=ts.balance,
        ))
        self.financial_category_analyzer.fit_model()
        return TransactionResponse.model_validate(ts)

    @staticmethod
    def _date_from_str(date_str: str):
        date_str = date_str.strip()
        updated_year = '20' + date_str.split('.')[-1]
        date_str = '.'.join(date_str.split('.')[:2]) + '.' + updated_year
        return datetime.strptime(date_str, '%d.%m.%Y')
