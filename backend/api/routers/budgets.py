from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Budget, Movement
    from ...schemas.budgets import BudgetIn
else:
    from db.models import Budget, Movement
    from schemas.budgets import BudgetIn


def create_router(db):
    router = APIRouter()

    @router.get('/budgets')
    def budgets(session:Session=Depends(db)):
        data=[]
        for b in session.scalars(select(Budget)):
            spent=sum((m.amount for m in session.scalars(select(Movement).where(Movement.kind=='expense',Movement.category==b.category,Movement.currency==b.currency,Movement.exchange_id==None)) if m.date.strftime('%Y-%m')==b.month),Decimal('0'))
            pct=spent/b.limit_amount*100
            data.append({'id':b.id,'month':b.month,'category':b.category,'currency':b.currency,'limit':str(b.limit_amount),'spent':str(spent),'percentage':round(float(pct),1),'alert':100 if pct>=100 else 90 if pct>=90 else 75 if pct>=75 else 0})
        return data
    @router.post('/budgets',status_code=201)
    def create_budget(payload:BudgetIn,session:Session=Depends(db)):
        b=Budget(**payload.model_dump());b.currency=payload.currency.value
        session.add(b);session.commit();session.refresh(b)
        return {'id':b.id}

    return router
