"""Offline regression checks for the extracted movements router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.routers.movements import create_router
from db.base import Base
from db.models import Movement
from schemas.movements import MovementIn
from services.balances import available


class MovementsRouterTest(unittest.TestCase):
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

    def create(self, *, kind='income', currency='PEN', amount='10.00',
               day=20, category='Categoría ficticia', description=''):
        payload = MovementIn.model_validate({
            'date': f'2026-10-{day:02d}', 'kind': kind, 'currency': currency,
            'amount': amount, 'category': category, 'description': description,
        })
        return self.routes[('/movements', 'POST')].endpoint(payload, session=self.session)

    def test_routes_keep_paths_methods_status_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(set(self.routes), {('/movements', 'GET'), ('/movements', 'POST')})
        self.assertIsNone(self.routes[('/movements', 'GET')].status_code)
        self.assertEqual(self.routes[('/movements', 'POST')].status_code, 201)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        operations = app.openapi()['paths']['/movements']
        self.assertEqual(set(operations), {'get', 'post'})
        self.assertEqual(set(operations['get']['responses']), {'200'})
        self.assertEqual(set(operations['post']['responses']), {'201', '422'})

    def test_create_preserves_decimal_currency_category_and_date(self):
        pen = self.create(amount='100.10', category='Sueldo', description='Ingreso ficticio')
        usd = self.create(currency='USD', amount='7.25', day=21, category='Bonos')
        self.assertEqual(set(pen), {'id'})
        self.assertEqual(set(usd), {'id'})
        saved = self.session.get(Movement, pen['id'])
        self.assertEqual(saved.date, date(2026, 10, 20))
        self.assertEqual(saved.kind, 'income')
        self.assertEqual(saved.currency, 'PEN')
        self.assertEqual(saved.amount, Decimal('100.10'))
        self.assertEqual(saved.category, 'Sueldo')
        self.assertEqual(saved.description, 'Ingreso ficticio')
        self.assertEqual(available(self.session), {
            'PEN': Decimal('100.10'), 'USD': Decimal('7.25'),
        })

    def test_get_preserves_descending_date_and_id_and_string_amounts(self):
        older = self.create(day=19, amount='1.10')
        same_day_first = self.create(day=20, amount='2.20')
        same_day_second = self.create(day=20, amount='3.30')
        rows = self.routes[('/movements', 'GET')].endpoint(session=self.session)
        self.assertEqual([row['id'] for row in rows], [
            same_day_second['id'], same_day_first['id'], older['id'],
        ])
        self.assertEqual(rows[0], {
            'id': same_day_second['id'], 'date': '2026-10-20',
            'kind': 'income', 'currency': 'PEN', 'amount': '3.30',
            'category': 'Categoría ficticia', 'description': '',
        })

    def test_expense_checks_spendable_and_other_kinds_keep_balance_rules(self):
        self.create(kind='income', amount='30.00')
        self.create(kind='reimbursement', amount='5.00')
        self.create(kind='expense', amount='12.05')
        self.assertEqual(available(self.session)['PEN'], Decimal('22.95'))
        before = len(self.session.scalars(select(Movement)).all())
        with self.assertRaises(HTTPException) as insufficient:
            self.create(kind='expense', amount='22.96')
        self.assertEqual(insufficient.exception.status_code, 400)
        self.assertEqual(len(self.session.scalars(select(Movement)).all()), before)
        self.assertEqual(available(self.session)['PEN'], Decimal('22.95'))

    def test_existing_schema_validations_remain(self):
        for changes in (
            {'kind': 'transfer'}, {'currency': 'EUR'}, {'amount': '0.00'},
            {'amount': '1.001'}, {'category': ''}, {'date': '2026-02-30'},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                MovementIn.model_validate({
                    'date': '2026-10-20', 'kind': 'income', 'currency': 'PEN',
                    'amount': '10.00', 'category': 'Sueldo', **changes,
                })


if __name__ == '__main__':
    unittest.main()
