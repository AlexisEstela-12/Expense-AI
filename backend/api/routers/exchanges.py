from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Exchange, Movement
    from ...schemas.exchanges import ExchangeIn
    from ...services.balances import available, ensure_balance
else:
    from db.models import Exchange, Movement
    from schemas.exchanges import ExchangeIn
    from services.balances import available, ensure_balance


def create_router(db):
    router = APIRouter()

    @router.post('/exchanges',status_code=201)
    def exchange(payload:ExchangeIn,session:Session=Depends(db)):
        origin=payload.from_currency.value
        dest='PEN' if origin=='USD' else 'USD'
        ensure_balance(session,origin,payload.amount_out)
        rate=(payload.amount_in/payload.amount_out if origin=='USD' else payload.amount_out/payload.amount_in)
        ex=Exchange(date=payload.date,from_currency=origin,amount_out=payload.amount_out,amount_in=payload.amount_in,rate=rate)
        session.add(ex);session.flush()
        session.add_all([
            Movement(date=payload.date,kind='expense',currency=origin,amount=payload.amount_out,category='Cambio de divisas',exchange_id=ex.id),
            Movement(date=payload.date,kind='income',currency=dest,amount=payload.amount_in,category='Cambio de divisas',exchange_id=ex.id)
        ])
        session.commit()
        return {'id':ex.id,'rate':str(rate),'balances':{k:str(v) for k,v in available(session).items()}}

    return router
