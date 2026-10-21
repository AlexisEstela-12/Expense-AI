"""Existing balance calculations shared by API and financial queries."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

if __package__.startswith('backend.'):
    from ..db.models import Movement, SavingsGoal, SavingsContribution
else:
    from db.models import Movement, SavingsGoal, SavingsContribution


def available(session):
    totals={'PEN':Decimal('0'),'USD':Decimal('0')}
    for m in session.scalars(select(Movement)):
        sign = -1 if m.kind=='expense' else 1
        totals[m.currency] += sign * m.amount
    return totals


def reserved_savings(session):
    totals = {
        'PEN': Decimal('0'),
        'USD': Decimal('0')
    }

    goals = session.scalars(
        select(SavingsGoal).where(
            SavingsGoal.active == 1
        )
    ).all()

    for goal in goals:
        contributions = session.scalars(
            select(SavingsContribution).where(
                SavingsContribution.goal_id == goal.id
            )
        ).all()

        totals[goal.currency] += sum(
            (contribution.amount for contribution in contributions),
            Decimal('0')
        )

    return totals


def spendable_balance(session):
    total = available(session)
    reserved = reserved_savings(session)

    return {
        'PEN': total['PEN'] - reserved['PEN'],
        'USD': total['USD'] - reserved['USD']
    }


def ensure_spendable_balance(session, currency, amount):
    spendable = spendable_balance(session)

    if spendable[currency] < amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Saldo disponible insuficiente en {currency}. '
                f'Disponible: {currency} {spendable[currency]:.2f}.'
            )
        )
def ensure_balance(session, currency, amount):
    spendable = spendable_balance(session)

    if spendable[currency] < amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Saldo disponible insuficiente en {currency}. '
                f'Disponible: {currency} {spendable[currency]:.2f}. '
                f'Parte de tu saldo puede estar reservada para metas de ahorro.'
            )
        )
