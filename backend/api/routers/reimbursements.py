from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Movement, Reimbursement
    from ...schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
    from ...services.balances import ensure_balance
else:
    from db.models import Movement, Reimbursement
    from schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
    from services.balances import ensure_balance


def create_router(db):
    router = APIRouter()

    @router.post('/reimbursements', status_code=201)
    def create_reimbursement(
        payload: ReimbursementIn,
        session: Session = Depends(db)
    ):
        currency = payload.currency.value

        # Verificar que tengas saldo suficiente para pagar el gasto
        ensure_balance(session, currency, payload.amount)

        # 1. Registrar el gasto real en movimientos
        movement = Movement(
            date=payload.date,
            kind='expense',
            currency=currency,
            amount=payload.amount,
            category=payload.category,
            description=payload.description
        )

        session.add(movement)
        session.flush()

        # 2. Crear el reembolso pendiente y vincularlo al gasto
        reimbursement = Reimbursement(
            date=payload.date,
            currency=currency,
            amount=payload.amount,
            category=payload.category,
            description=payload.description,
            status='pending',
            movement_id=movement.id
        )

        session.add(reimbursement)
        session.commit()
        session.refresh(reimbursement)

        return {
            'id': reimbursement.id,
            'status': reimbursement.status,
            'movement_id': reimbursement.movement_id,
            'currency': reimbursement.currency,
            'amount': str(reimbursement.amount)
        }

    @router.post('/reimbursements/{reimbursement_id}/complete')
    def complete_reimbursement(
        reimbursement_id: int,
        payload: ReimbursementPaidIn,
        session: Session = Depends(db)
    ):
        with session.begin():
            reimbursement = session.get(Reimbursement, reimbursement_id)

            if reimbursement is None:
                raise HTTPException(
                    status_code=404,
                    detail='Reembolso no encontrado.'
                )

            if reimbursement.status != 'pending':
                raise HTTPException(
                    status_code=400,
                    detail='Este reembolso ya no está pendiente.'
                )

            # La actualización condicional adquiere el bloqueo de escritura antes
            # de crear el movimiento. Una solicitud concurrente no puede reclamar
            # el mismo pendiente, incluso si ambas leyeron su estado inicial.
            result = session.execute(
                Reimbursement.__table__.update()
                .where(
                    Reimbursement.id == reimbursement_id,
                    Reimbursement.status == 'pending'
                )
                .values(
                    status='reimbursed',
                    reimbursed_date=payload.date
                )
            )

            if result.rowcount != 1:
                raise HTTPException(
                    status_code=400,
                    detail='Este reembolso ya no está pendiente.'
                )

            session.refresh(reimbursement)
            movement = Movement(
                date=payload.date,
                kind='reimbursement',
                currency=reimbursement.currency,
                amount=reimbursement.amount,
                category='Reembolso laboral',
                description=(
                    f'Reembolso #{reimbursement.id}: '
                    f'{reimbursement.description or "Gasto laboral"}'
                )[:255]
            )
            session.add(movement)
            session.flush()
            reimbursement.reimbursement_movement_id = movement.id

            response = {
                'id': reimbursement.id,
                'status': reimbursement.status,
                'reimbursed_date': reimbursement.reimbursed_date.isoformat(),
                'currency': reimbursement.currency,
                'amount': str(reimbursement.amount),
                'reimbursement_movement_id': movement.id
            }

        return response

    @router.get('/reimbursements')
    def get_reimbursements(session: Session = Depends(db)):
        items = session.scalars(
            select(Reimbursement).order_by(
                Reimbursement.date.desc(),
                Reimbursement.id.desc()
            )
        ).all()

        return [
            {
                'id': r.id,
                'date': r.date.isoformat(),
                'currency': r.currency,
                'amount': str(r.amount),
                'category': r.category,
                'description': r.description,
                'status': r.status,
                'reimbursed_date': (
                    r.reimbursed_date.isoformat()
                    if r.reimbursed_date
                    else None
                ),
                'movement_id': r.movement_id,
                'reimbursement_movement_id': r.reimbursement_movement_id
            }
            for r in items
        ]

    return router
