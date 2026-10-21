"""Offline regression tests for the extracted balance calculations."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models import Movement, SavingsContribution, SavingsGoal
from services.balances import (
    available, ensure_balance, ensure_spendable_balance,
    reserved_savings, spendable_balance,
)
from services.financial_queries import get_balances


class BalanceServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

    def movement(self, kind, currency, amount):
        self.session.add(Movement(
            date=date(2026, 10, 20), kind=kind, currency=currency,
            amount=Decimal(amount), category='Prueba',
        ))

    def goal(self, currency, active, amounts):
        goal = SavingsGoal(
            name='Meta ficticia', currency=currency,
            target_amount=Decimal('100.00'), active=active,
        )
        self.session.add(goal)
        self.session.flush()
        for amount in amounts:
            self.session.add(SavingsContribution(
                goal_id=goal.id, date=date(2026, 10, 20),
                amount=Decimal(amount),
            ))
        self.session.flush()

    def test_empty_balances_are_decimal_for_both_currencies(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        zero = {'PEN': Decimal('0'), 'USD': Decimal('0')}
        self.assertEqual(available(self.session), zero)
        self.assertEqual(reserved_savings(self.session), zero)
        self.assertEqual(spendable_balance(self.session), zero)

    def test_total_reserved_and_spendable_preserve_decimal_arithmetic(self):
        self.movement('income', 'PEN', '100.10')
        self.movement('expense', 'PEN', '20.05')
        self.movement('reimbursement', 'PEN', '5.00')
        self.movement('income', 'USD', '50.55')
        self.movement('expense', 'USD', '10.10')
        self.goal('PEN', 1, ['10.01', '5.04'])
        self.goal('PEN', 0, ['3.00'])
        self.goal('USD', 1, ['2.25'])
        self.assertEqual(available(self.session), {
            'PEN': Decimal('85.05'), 'USD': Decimal('40.45'),
        })
        self.assertEqual(reserved_savings(self.session), {
            'PEN': Decimal('15.05'), 'USD': Decimal('2.25'),
        })
        self.assertEqual(spendable_balance(self.session), {
            'PEN': Decimal('70.00'), 'USD': Decimal('38.20'),
        })
        self.assertEqual(get_balances(
            self.session, available_fn=available,
            reserved_savings_fn=reserved_savings,
            spendable_balance_fn=spendable_balance,
        ), {
            'balances': {'PEN': '85.05', 'USD': '40.45'},
            'reserved': {'PEN': '15.05', 'USD': '2.25'},
            'spendable': {'PEN': '70.00', 'USD': '38.20'},
        })

    def test_savings_without_movements_reduce_spendable(self):
        self.goal('PEN', 1, ['0.01'])
        self.assertEqual(available(self.session)['PEN'], Decimal('0'))
        self.assertEqual(reserved_savings(self.session)['PEN'], Decimal('0.01'))
        self.assertEqual(spendable_balance(self.session)['PEN'], Decimal('-0.01'))

    def test_balance_guards_keep_existing_status_and_messages(self):
        self.movement('income', 'PEN', '20.00')
        self.goal('PEN', 1, ['5.00'])
        ensure_balance(self.session, 'PEN', Decimal('15.00'))
        ensure_spendable_balance(self.session, 'PEN', Decimal('15.00'))
        with self.assertRaises(HTTPException) as first:
            ensure_balance(self.session, 'PEN', Decimal('15.01'))
        self.assertEqual(first.exception.status_code, 400)
        self.assertEqual(first.exception.detail,
            'Saldo disponible insuficiente en PEN. Disponible: PEN 15.00. '
            'Parte de tu saldo puede estar reservada para metas de ahorro.')
        with self.assertRaises(HTTPException) as second:
            ensure_spendable_balance(self.session, 'PEN', Decimal('15.01'))
        self.assertEqual(second.exception.status_code, 400)
        self.assertEqual(second.exception.detail,
            'Saldo disponible insuficiente en PEN. Disponible: PEN 15.00.')


if __name__ == '__main__':
    unittest.main()
