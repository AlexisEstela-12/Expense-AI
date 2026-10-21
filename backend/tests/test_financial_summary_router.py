"""Offline regression tests for the financial summary router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers.financial_summary import create_router
from db.base import Base
from db.models import Movement, SavingsContribution, SavingsGoal


class FinancialSummaryRouterTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        def db():
            yield self.session

        self.db = db
        self.router = create_router(db)
        self.route = next(route for route in self.router.routes if isinstance(route, APIRoute))

    def summary(self):
        return self.route.endpoint(session=self.session)

    def movement(self, kind, currency, amount):
        self.session.add(Movement(
            date=date(2026, 10, 20), kind=kind, currency=currency,
            amount=Decimal(amount), category='Categoría ficticia',
        ))

    def goal(self, currency, active, *amounts):
        goal = SavingsGoal(
            name='Meta ficticia', currency=currency,
            target_amount=Decimal('100.00'), active=active,
        )
        self.session.add(goal)
        self.session.flush()
        for amount in amounts:
            self.session.add(SavingsContribution(
                goal_id=goal.id, date=date(2026, 10, 20), amount=Decimal(amount),
            ))

    def test_route_contract_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(self.route.path, '/summary')
        self.assertEqual(self.route.methods, {'GET'})
        self.assertIsNone(self.route.status_code)
        self.assertIs(self.route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        self.assertIn('/summary', app.openapi()['paths'])

    def test_empty_balances_keep_both_currencies_and_response_shape(self):
        expected = {'PEN': '0', 'USD': '0'}
        self.assertEqual(self.summary(), {
            'balances': expected, 'reserved': expected, 'spendable': expected,
        })

    def test_decimal_balances_reservations_and_inactive_goal(self):
        self.movement('income', 'PEN', '100.10')
        self.movement('expense', 'PEN', '20.05')
        self.movement('reimbursement', 'PEN', '5.00')
        self.movement('income', 'USD', '50.55')
        self.movement('expense', 'USD', '10.10')
        self.goal('PEN', 1, '10.01', '5.04')
        self.goal('PEN', 0, '3.00')
        self.goal('USD', 1, '2.25')
        self.session.commit()
        self.assertEqual(self.summary(), {
            'balances': {'PEN': '85.05', 'USD': '40.45'},
            'reserved': {'PEN': '15.05', 'USD': '2.25'},
            'spendable': {'PEN': '70.00', 'USD': '38.20'},
        })
        self.assertFalse(self.session.dirty)

    def test_reserved_amount_without_movements_can_make_spendable_negative(self):
        self.goal('PEN', 1, '0.01')
        self.session.commit()
        self.assertEqual(self.summary(), {
            'balances': {'PEN': '0', 'USD': '0'},
            'reserved': {'PEN': '0.01', 'USD': '0'},
            'spendable': {'PEN': '-0.01', 'USD': '0'},
        })


if __name__ == '__main__':
    unittest.main()
