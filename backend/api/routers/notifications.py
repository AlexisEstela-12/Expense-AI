from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Budget, Movement, Reimbursement, RecurringPayment
else:
    from db.models import Budget, Movement, Reimbursement, RecurringPayment


def create_router(db):
    router = APIRouter()
    @router.get('/notifications')
    def get_notifications(session: Session = Depends(db)):
        today = date.today()
        notifications = []

        # -----------------------------------
        # 1. PAGOS RECURRENTES
        # -----------------------------------

        recurring_payments = session.scalars(
            select(RecurringPayment).where(
                RecurringPayment.active == 1
            )
        ).all()

        for payment in recurring_payments:
            days = (payment.next_payment_date - today).days

            if days < 0:
                notifications.append({
                    'type': 'recurring_payment',
                    'level': 'danger',
                    'title': 'Pago vencido',
                    'message': f'{payment.name} venció el {payment.next_payment_date.isoformat()}.',
                    'date': payment.next_payment_date.isoformat()
                })

            elif days == 0:
                notifications.append({
                    'type': 'recurring_payment',
                    'level': 'danger',
                    'title': 'Pago vence hoy',
                    'message': f'{payment.name} vence hoy.',
                    'date': payment.next_payment_date.isoformat()
                })

            elif days <= 3:
                notifications.append({
                    'type': 'recurring_payment',
                    'level': 'warning',
                    'title': 'Pago próximo',
                    'message': f'{payment.name} vence en {days} días.',
                    'date': payment.next_payment_date.isoformat()
                })

            elif days <= 7:
                notifications.append({
                    'type': 'recurring_payment',
                    'level': 'info',
                    'title': 'Próximo pago',
                    'message': f'{payment.name} vence en {days} días.',
                    'date': payment.next_payment_date.isoformat()
                })

        # -----------------------------------
        # 2. PRESUPUESTOS
        # -----------------------------------

        budgets = session.scalars(
            select(Budget)
        ).all()

        for budget in budgets:
            spent = sum(
                (
                    movement.amount
                    for movement in session.scalars(
                        select(Movement).where(
                            Movement.kind == 'expense',
                            Movement.category == budget.category,
                            Movement.currency == budget.currency,
                            Movement.exchange_id == None
                        )
                    )
                    if movement.date.strftime('%Y-%m') == budget.month
                ),
                Decimal('0')
            )

            percentage = (
                spent / budget.limit_amount * 100
                if budget.limit_amount > 0
                else Decimal('0')
            )

            level = None
            title = None

            if percentage >= 100:
                level = 'danger'
                title = 'Presupuesto excedido'

            elif percentage >= 90:
                level = 'warning'
                title = 'Presupuesto al 90%'

            elif percentage >= 75:
                level = 'info'
                title = 'Presupuesto al 75%'

            if level:
                notifications.append({
                    'type': 'budget',
                    'level': level,
                    'title': title,
                    'message': (
                        f'{budget.category}: has utilizado '
                        f'{percentage:.0f}% de tu presupuesto '
                        f'{budget.month}.'
                    ),
                    'date': f'{budget.month}-01'
                })

        notifications.sort(key=lambda item: item['date'])
            # -----------------------------------
        # 3. REEMBOLSOS PENDIENTES
        # -----------------------------------

        pending_reimbursements = session.scalars(
            select(Reimbursement).where(
                Reimbursement.status == 'pending'
            )
        ).all()

        for reimbursement in pending_reimbursements:
            days_pending = (today - reimbursement.date).days

            notifications.append({
                'type': 'reimbursement',
                'level': 'info',
                'title': 'Reembolso pendiente',
                'message': (
                    f'Tienes {reimbursement.currency} '
                    f'{reimbursement.amount:.2f} pendientes de reembolso '
                    f'desde hace {days_pending} días.'
                ),
                'date': reimbursement.date.isoformat()
            })
        return notifications
    return router
