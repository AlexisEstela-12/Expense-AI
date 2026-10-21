from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class RecurringPaymentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=80)
    currency: Money
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    frequency: str = Field(pattern='^(weekly|monthly|yearly)$')
    next_payment_date: date


class RecurringPaymentPaidIn(BaseModel):
    date: date
