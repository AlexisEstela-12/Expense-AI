from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...services.balances import available, reserved_savings, spendable_balance
else:
    from services.balances import available, reserved_savings, spendable_balance


def create_router(db):
    router = APIRouter()
    @router.get('/summary')
    def summary(session: Session = Depends(db)):
        totals = available(session)
        reserved = reserved_savings(session)
        spendable = spendable_balance(session)

        return {
            'balances': {
                k: str(v)
                for k, v in totals.items()
            },
            'reserved': {
                k: str(v)
                for k, v in reserved.items()
            },
            'spendable': {
                k: str(v)
                for k, v in spendable.items()
            }
        }
    return router
