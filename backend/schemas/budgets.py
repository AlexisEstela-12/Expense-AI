from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class BudgetIn(BaseModel):
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    category: str = Field(min_length=1,max_length=80)
    currency: Money
    limit_amount: Decimal = Field(gt=0,max_digits=16,decimal_places=2)
