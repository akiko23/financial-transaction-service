import uuid
from datetime import datetime

from sqlalchemy import UUID, Column, DateTime, DECIMAL, String

from .base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=False)
    entry_date = Column(DateTime, default=datetime.now)
    receipt_date = Column(DateTime, default=datetime.now)
    withdraw = Column(DECIMAL, nullable=False)
    deposit = Column(DECIMAL, nullable=False)
    processing_status = Column(String, default="in_progress") # in_progress, completed
    category = Column(String, nullable=True)
