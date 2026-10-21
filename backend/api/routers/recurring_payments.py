from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta

if __package__.startswith('backend.'):
    from ...db.models import Movement, RecurringPayment
    from ...schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
    from ...services.balances import available, ensure_balance
else:
    from db.models import Movement, RecurringPayment
    from schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
    from services.balances import available, ensure_balance


def create_router(db):
    router = APIRouter()

    @router.post('/recurring-payments', status_code=201)
    def create_recurring_payment(
        payload: RecurringPaymentIn,
        session: Session = Depends(db)
    ):
        recurring_payment = RecurringPayment(
            name=payload.name,
            category=payload.category,
            currency=payload.currency.value,
            amount=payload.amount,
            frequency=payload.frequency,
            next_payment_date=payload.next_payment_date,
            active=1
        )

        session.add(recurring_payment)
        session.commit()
        session.refresh(recurring_payment)

        return {
            'id': recurring_payment.id,
            'name': recurring_payment.name,
            'category': recurring_payment.category,
            'currency': recurring_payment.currency,
            'amount': str(recurring_payment.amount),
            'frequency': recurring_payment.frequency,
            'next_payment_date': recurring_payment.next_payment_date.isoformat(),
            'active': bool(recurring_payment.active)
        }

    @router.get('/recurring-payments')
    def get_recurring_payments(session: Session = Depends(db)):
        items = session.scalars(
            select(RecurringPayment).order_by(
                RecurringPayment.next_payment_date.asc(),
                RecurringPayment.id.asc()
            )
        ).all()

        return [
            {
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'currency': item.currency,
                'amount': str(item.amount),
                'frequency': item.frequency,
                'next_payment_date': item.next_payment_date.isoformat(),
                'active': bool(item.active)
            }
            for item in items
        ]

    @router.post('/recurring-payments/{recurring_payment_id}/pay')
    def pay_recurring_payment(
        recurring_payment_id: int,
        payload: RecurringPaymentPaidIn,
        session: Session = Depends(db)
    ):
        recurring_payment = session.get(
            RecurringPayment,
            recurring_payment_id
        )

        if not recurring_payment:
            raise HTTPException(
                status_code=404,
                detail='Pago recurrente no encontrado.'
            )

        if not recurring_payment.active:
            raise HTTPException(
                status_code=400,
                detail='Este pago recurrente está inactivo.'
            )

        # Verificar que exista saldo suficiente
        ensure_balance(
            session,
            recurring_payment.currency,
            recurring_payment.amount
        )

        # Registrar el pago como un gasto real
        movement = Movement(
            date=payload.date,
            kind='expense',
            currency=recurring_payment.currency,
            amount=recurring_payment.amount,
            category=recurring_payment.category,
            description=recurring_payment.name
        )

        session.add(movement)

        # Calcular el siguiente vencimiento
        if recurring_payment.frequency == 'weekly':
            recurring_payment.next_payment_date += relativedelta(weeks=1)
        elif recurring_payment.frequency == 'monthly':
            recurring_payment.next_payment_date += relativedelta(months=1)
        elif recurring_payment.frequency == 'yearly':
            recurring_payment.next_payment_date += relativedelta(years=1)

        session.commit()
        session.refresh(recurring_payment)

        return {
            'id': recurring_payment.id,
            'name': recurring_payment.name,
            'paid_date': payload.date.isoformat(),
            'next_payment_date': recurring_payment.next_payment_date.isoformat(),
            'currency': recurring_payment.currency,
            'amount': str(recurring_payment.amount),
            'balances': {
                k: str(v)
                for k, v in available(session).items()
            }
        }

    return router
