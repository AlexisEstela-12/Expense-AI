"""Offline regression checks for the extracted exchanges router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.routers.exchanges import create_router
from db.base import Base
from db.models import Exchange, Movement
from schemas.exchanges import ExchangeIn
from services.balances import available


class ExchangesRouterTest(unittest.TestCase):
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

    def seed_income(self, currency, amount):
        self.session.add(Movement(
            date=date(2026, 10, 1), kind='income', currency=currency,
            amount=Decimal(amount), category='Ingreso ficticio',
        ))
        self.session.commit()

    def exchange(self, origin, amount_out, amount_in):
        payload = ExchangeIn.model_validate({
            'date': '2026-10-20', 'from_currency': origin,
            'amount_out': amount_out, 'amount_in': amount_in,
        })
        return self.route.endpoint(payload, session=self.session)

    def test_route_keeps_contract_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(len([r for r in self.router.routes if isinstance(r, APIRoute)]), 1)
        self.assertEqual((self.route.path, self.route.methods, self.route.status_code),
                         ('/exchanges', {'POST'}, 201))
        self.assertIs(self.route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        operations = app.openapi()['paths']['/exchanges']
        self.assertEqual(set(operations), {'post'})
        self.assertEqual(set(operations['post']['responses']), {'201', '422'})

    def test_usd_to_pen_keeps_rate_linked_movements_and_balances(self):
        self.seed_income('USD', '20.00')
        result = self.exchange('USD', '10.00', '37.50')
        self.assertEqual(result, {
            'id': result['id'], 'rate': '3.75',
            'balances': {'PEN': '37.50', 'USD': '10.00'},
        })
        saved = self.session.get(Exchange, result['id'])
        self.assertEqual(saved.from_currency, 'USD')
        self.assertEqual(saved.date, date(2026, 10, 20))
        self.assertEqual(saved.amount_out, Decimal('10.00'))
        self.assertEqual(saved.amount_in, Decimal('37.50'))
        self.assertEqual(saved.rate, Decimal('3.750000'))
        legs = self.session.scalars(select(Movement).where(Movement.exchange_id == saved.id)).all()
        self.assertEqual(len(legs), 2)
        self.assertEqual({(m.kind, m.currency, m.amount) for m in legs}, {
            ('expense', 'USD', Decimal('10.00')),
            ('income', 'PEN', Decimal('37.50')),
        })
        self.assertTrue(all(m.category == 'Cambio de divisas' for m in legs))
        self.assertEqual(available(self.session), {
            'PEN': Decimal('37.50'), 'USD': Decimal('10.00'),
        })

    def test_pen_to_usd_keeps_inverse_rate_and_balances(self):
        self.seed_income('PEN', '100.00')
        result = self.exchange('PEN', '37.50', '10.00')
        self.assertEqual(result['rate'], '3.75')
        self.assertEqual(result['balances'], {'PEN': '62.50', 'USD': '10.00'})
        saved = self.session.get(Exchange, result['id'])
        self.assertEqual(saved.from_currency, 'PEN')
        self.assertEqual(saved.rate, Decimal('3.750000'))
        legs = self.session.scalars(select(Movement).where(Movement.exchange_id == saved.id)).all()
        self.assertEqual({(m.kind, m.currency, m.amount) for m in legs}, {
            ('expense', 'PEN', Decimal('37.50')),
            ('income', 'USD', Decimal('10.00')),
        })

    def test_insufficient_balance_creates_no_exchange_or_legs(self):
        with self.assertRaises(HTTPException) as rejected:
            self.exchange('USD', '10.00', '37.50')
        self.assertEqual(rejected.exception.status_code, 400)
        self.assertEqual(self.session.scalars(select(Exchange)).all(), [])
        self.assertEqual(self.session.scalars(select(Movement)).all(), [])

    def test_existing_schema_validation_and_decimal_precision(self):
        for changes in (
            {'from_currency': 'EUR'}, {'amount_out': '0.00'},
            {'amount_in': '-1.00'}, {'amount_out': '1.001'},
            {'date': '2026-02-30'},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ExchangeIn.model_validate({
                    'date': '2026-10-20', 'from_currency': 'USD',
                    'amount_out': '10.00', 'amount_in': '37.50', **changes,
                })
        self.seed_income('USD', '20.00')
        result = self.exchange('USD', '9.00', '33.00')
        self.assertEqual(result['rate'], str(Decimal('33.00') / Decimal('9.00')))
        self.assertEqual(self.session.get(Exchange, result['id']).rate, Decimal('3.666667'))


if __name__ == '__main__':
    unittest.main()
