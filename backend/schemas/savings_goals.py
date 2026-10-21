from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class SavingsGoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: Money
    target_amount: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=2
    )
    target_date: date | None = None


class SavingsContributionIn(BaseModel):
    date: date
    amount: Decimal = Field(
        gt=0,
        max_digits=16,
        decimal_places=2
    )
