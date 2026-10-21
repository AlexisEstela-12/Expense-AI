from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Movement
    from ...schemas.movements import MovementIn
    from ...services.balances import ensure_balance
else:
    from db.models import Movement
    from schemas.movements import MovementIn
    from services.balances import ensure_balance


def create_router(db):
    router = APIRouter()

    @router.get('/movements')
    def movements(session:Session=Depends(db)):
        return [{'id':m.id,'date':m.date.isoformat(),'kind':m.kind,'currency':m.currency,'amount':str(m.amount),'category':m.category,'description':m.description} for m in session.scalars(select(Movement).order_by(Movement.date.desc(),Movement.id.desc())).all()]
    @router.post('/movements',status_code=201)
    def create_movement(payload:MovementIn,session:Session=Depends(db)):
        if payload.kind=='expense': ensure_balance(session,payload.currency.value,payload.amount)
        m=Movement(**payload.model_dump())
        m.currency=payload.currency.value
        session.add(m);session.commit();session.refresh(m)
        return {'id':m.id}

    return router
