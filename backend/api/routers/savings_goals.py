from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...db.models import Movement, SavingsGoal, SavingsContribution
    from ...schemas.savings_goals import SavingsGoalIn, SavingsContributionIn
    from ...services.balances import ensure_spendable_balance
else:
    from db.models import Movement, SavingsGoal, SavingsContribution
    from schemas.savings_goals import SavingsGoalIn, SavingsContributionIn
    from services.balances import ensure_spendable_balance


def create_router(db):
    router = APIRouter()

    @router.post('/savings-goals', status_code=201)
    def create_savings_goal(
        payload: SavingsGoalIn,
        session: Session = Depends(db)
    ):
        goal = SavingsGoal(
            name=payload.name.strip(),
            currency=payload.currency.value,
            target_amount=payload.target_amount,
            target_date=payload.target_date,
            active=1
        )

        session.add(goal)
        session.commit()
        session.refresh(goal)

        return {
            'id': goal.id,
            'name': goal.name,
            'currency': goal.currency,
            'target_amount': str(goal.target_amount),
            'target_date': (
                goal.target_date.isoformat()
                if goal.target_date
                else None
            ),
            'active': bool(goal.active),
            'saved_amount': '0.00',
            'percentage': 0
        }

    @router.get('/savings-goals')
    def get_savings_goals(session: Session = Depends(db)):
        goals = session.scalars(
        select(SavingsGoal)
        .where(SavingsGoal.active == 1)
        .order_by(SavingsGoal.id.desc())
        ).all()

        result = []

        for goal in goals:
            contributions = session.scalars(
                select(SavingsContribution).where(
                    SavingsContribution.goal_id == goal.id
                )
            ).all()

            saved_amount = sum(
                (contribution.amount for contribution in contributions),
                Decimal('0')
            )

            percentage = (
                saved_amount / goal.target_amount * 100
                if goal.target_amount > 0
                else Decimal('0')
            )

            result.append({
                'id': goal.id,
                'name': goal.name,
                'currency': goal.currency,
                'target_amount': str(goal.target_amount),
                'saved_amount': str(saved_amount),
                'percentage': round(float(percentage), 1),
                'target_date': (
                    goal.target_date.isoformat()
                    if goal.target_date
                    else None
                ),
                'active': bool(goal.active)
            })

        return result

    @router.post('/savings-goals/{goal_id}/contributions', status_code=201)
    def create_savings_contribution(
        goal_id: int,
        payload: SavingsContributionIn,
        session: Session = Depends(db)
    ):
        goal = session.get(SavingsGoal, goal_id)

        if not goal:
            raise HTTPException(
                status_code=404,
                detail='Meta de ahorro no encontrada.'
            )

        if not goal.active:
            raise HTTPException(
                status_code=400,
                detail='Esta meta de ahorro está inactiva.'
            )
        ensure_spendable_balance(
            session,
            goal.currency,
            payload.amount
        )

        # Calcular cuánto ya está reservado en esta meta
        contributions = session.scalars(
            select(SavingsContribution).where(
                SavingsContribution.goal_id == goal.id
            )
        ).all()

        saved_amount = sum(
            (contribution.amount for contribution in contributions),
            Decimal('0')
        )

        remaining = goal.target_amount - saved_amount

        if payload.amount > remaining:
            raise HTTPException(
                status_code=400,
                detail=f'El aporte supera el monto pendiente de la meta. Falta ahorrar {goal.currency} {remaining:.2f}.'
            )

        contribution = SavingsContribution(
            goal_id=goal.id,
            date=payload.date,
            amount=payload.amount
        )

        session.add(contribution)
        session.commit()
        session.refresh(contribution)

        new_saved_amount = saved_amount + contribution.amount

        percentage = (
            new_saved_amount / goal.target_amount * 100
            if goal.target_amount > 0
            else Decimal('0')
        )

        return {
            'id': contribution.id,
            'goal_id': goal.id,
            'goal_name': goal.name,
            'date': contribution.date.isoformat(),
            'currency': goal.currency,
            'amount': str(contribution.amount),
            'saved_amount': str(new_saved_amount),
            'target_amount': str(goal.target_amount),
            'percentage': round(float(percentage), 1)
        }


    @router.post('/savings-goals/{goal_id}/cancel')
    def cancel_savings_goal(
        goal_id: int,
        session: Session = Depends(db)
    ):
        goal = session.get(SavingsGoal, goal_id)

        if not goal:
            raise HTTPException(
                status_code=404,
                detail='Meta de ahorro no encontrada.'
            )

        if not goal.active:
            raise HTTPException(
                status_code=400,
                detail='Esta meta de ahorro ya está cerrada.'
            )

        contributions = session.scalars(
            select(SavingsContribution).where(
                SavingsContribution.goal_id == goal.id
            )
        ).all()

        released_amount = sum(
            (contribution.amount for contribution in contributions),
            Decimal('0')
        )

        goal.active = 0

        session.commit()

        return {
            'id': goal.id,
            'name': goal.name,
            'status': 'cancelled',
            'currency': goal.currency,
            'released_amount': str(released_amount),
            'message': 'Meta cancelada. El dinero reservado vuelve a estar disponible.'
        }

    @router.post('/savings-goals/{goal_id}/use')
    def use_savings_goal(
        goal_id: int,
        session: Session = Depends(db)
    ):
        goal = session.get(SavingsGoal, goal_id)

        if not goal:
            raise HTTPException(
                status_code=404,
                detail='Meta de ahorro no encontrada.'
            )

        if not goal.active:
            raise HTTPException(
                status_code=400,
                detail='Esta meta de ahorro ya está cerrada.'
            )

        contributions = session.scalars(
            select(SavingsContribution).where(
                SavingsContribution.goal_id == goal.id
            )
        ).all()

        saved_amount = sum(
            (contribution.amount for contribution in contributions),
            Decimal('0')
        )

        if saved_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail='Esta meta no tiene dinero ahorrado.'
            )

        movement = Movement(
            date=date.today(),
            kind='expense',
            currency=goal.currency,
            amount=saved_amount,
            category='Otros gastos',
            description=f'Uso de ahorro: {goal.name}'
        )

        session.add(movement)

        goal.active = 0

        session.commit()
        session.refresh(movement)

        return {
            'id': goal.id,
            'name': goal.name,
            'status': 'completed',
            'currency': goal.currency,
            'used_amount': str(saved_amount),
            'movement_id': movement.id,
            'message': 'Ahorro utilizado y registrado como gasto.'
        }

    return router
