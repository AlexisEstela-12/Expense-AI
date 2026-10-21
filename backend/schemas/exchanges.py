from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Money


class ExchangeIn(BaseModel):
    date: date
    from_currency: Money
    amount_out: Decimal = Field(gt=0,max_digits=16,decimal_places=2)
    amount_in: Decimal = Field(gt=0,max_digits=16,decimal_places=2)
