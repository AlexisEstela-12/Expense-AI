from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class ReimbursementIn(BaseModel):
    date: date
    currency: Money
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    category: str = Field(default='Gastos laborales', min_length=1, max_length=80)
    description: str = Field(default='', max_length=255)


class ReimbursementPaidIn(BaseModel):
    date: date
