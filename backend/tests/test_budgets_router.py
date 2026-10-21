"""Offline regression checks for the extracted budgets router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers.budgets import create_router
from db.base import Base
from db.models import Budget, Movement
from schemas.budgets import BudgetIn


class BudgetsRouterTest(unittest.TestCase):
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
        self.routes = {
            (route.path, next(iter(route.methods))): route
            for route in self.router.routes if isinstance(route, APIRoute)
        }

    def add_budget(self, category, currency, limit, month='2026-10'):
        budget = Budget(
            month=month, category=category, currency=currency,
            limit_amount=Decimal(limit),
        )
        self.session.add(budget)
        self.session.flush()
        return budget.id

    def add_movement(self, kind, category, currency, amount, day=20, exchange_id=None):
        self.session.add(Movement(
            date=date(2026, 10, day), kind=kind, category=category,
            currency=currency, amount=Decimal(amount), exchange_id=exchange_id,
        ))

    def test_routes_keep_contract_and_same_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(set(self.routes), {('/budgets', 'GET'), ('/budgets', 'POST')})
        self.assertIsNone(self.routes[('/budgets', 'GET')].status_code)
        self.assertEqual(self.routes[('/budgets', 'POST')].status_code, 201)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        operations = app.openapi()['paths']['/budgets']
        self.assertEqual(set(operations), {'get', 'post'})
        self.assertEqual(set(operations['get']['responses']), {'200'})
        self.assertEqual(set(operations['post']['responses']), {'201', '422'})

    def test_create_budget_keeps_currency_and_response(self):
        payload = BudgetIn.model_validate({
            'month': '2026-10', 'category': 'Servicios',
            'currency': 'USD', 'limit_amount': '200.00',
        })
        response = self.routes[('/budgets', 'POST')].endpoint(payload, session=self.session)
        self.assertEqual(response, {'id': response['id']})
        saved = self.session.get(Budget, response['id'])
        self.assertEqual(saved.currency, 'USD')
        self.assertEqual(saved.limit_amount, Decimal('200.00'))
        with self.assertRaises(ValidationError):
            BudgetIn.model_validate({
                'month': '2026-13', 'category': 'Servicios',
                'currency': 'USD', 'limit_amount': '200.00',
            })

    def test_spending_filters_month_category_currency_kind_and_exchange(self):
        pen_id = self.add_budget('Servicios', 'PEN', '200.00')
        usd_id = self.add_budget('Servicios', 'USD', '100.00')
        self.add_movement('expense', 'Servicios', 'PEN', '75.25')
        self.add_movement('expense', 'Servicios', 'USD', '25.00')
        self.add_movement('income', 'Servicios', 'PEN', '100.00')
        self.add_movement('reimbursement', 'Servicios', 'PEN', '10.00')
        self.add_movement('expense', 'Otra', 'PEN', '30.00')
        self.add_movement('expense', 'Servicios', 'PEN', '99.00', exchange_id=123)
        self.session.add(Movement(
            date=date(2026, 9, 30), kind='expense', category='Servicios',
            currency='PEN', amount=Decimal('40.00'),
        ))
        self.session.flush()
        rows = {row['id']: row for row in self.routes[('/budgets', 'GET')].endpoint(session=self.session)}
        self.assertEqual(rows[pen_id], {
            'id': pen_id, 'month': '2026-10', 'category': 'Servicios',
            'currency': 'PEN', 'limit': '200.00', 'spent': '75.25',
            'percentage': 37.6, 'alert': 0,
        })
        self.assertEqual(rows[usd_id]['spent'], '25.00')
        self.assertEqual(rows[usd_id]['percentage'], 25.0)

    def test_duplicate_budgets_remain_independent_and_alerts_match(self):
        first = self.add_budget('Servicios', 'PEN', '100.00')
        second = self.add_budget('Servicios', 'PEN', '80.00')
        third = self.add_budget('Transporte', 'USD', '40.00')
        self.add_movement('expense', 'Servicios', 'PEN', '90.00')
        self.session.flush()
        rows = {row['id']: row for row in self.routes[('/budgets', 'GET')].endpoint(session=self.session)}
        self.assertEqual((rows[first]['spent'], rows[first]['percentage'], rows[first]['alert']), ('90.00', 90.0, 90))
        self.assertEqual((rows[second]['spent'], rows[second]['percentage'], rows[second]['alert']), ('90.00', 112.5, 100))
        self.assertEqual((rows[third]['spent'], rows[third]['percentage'], rows[third]['alert']), ('0', 0.0, 0))


if __name__ == '__main__':
    unittest.main()
