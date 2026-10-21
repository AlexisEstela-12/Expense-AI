from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class MovementIn(BaseModel):
    date: date
    kind: str = Field(pattern='^(income|expense|reimbursement)$')
    currency: Money
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    category: str = Field(min_length=1,max_length=80)
    description: str = Field(default='',max_length=255)
