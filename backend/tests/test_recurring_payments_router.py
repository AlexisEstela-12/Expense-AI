"""Offline regression tests for the extracted recurring payments router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.routers.recurring_payments import create_router
from db.base import Base
from db.models import Movement, RecurringPayment
from schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
from services.balances import available


class RecurringPaymentsRouterTest(unittest.TestCase):
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

    def create(self, *, name='Internet', category='Servicios', currency='PEN',
               amount='20.00', frequency='monthly', next_date='2026-10-20'):
        payload = RecurringPaymentIn.model_validate({
            'name': name, 'category': category, 'currency': currency,
            'amount': amount, 'frequency': frequency,
            'next_payment_date': next_date,
        })
        return self.routes[('/recurring-payments', 'POST')].endpoint(payload, session=self.session)

    def pay(self, payment_id, paid_date='2026-10-20'):
        payload = RecurringPaymentPaidIn.model_validate({'date': paid_date})
        return self.routes[('/recurring-payments/{recurring_payment_id}/pay', 'POST')].endpoint(
            payment_id, payload, session=self.session,
        )

    def seed_income(self, currency, amount):
        self.session.add(Movement(
            date=date(2026, 10, 1), kind='income', currency=currency,
            amount=Decimal(amount), category='Ingreso ficticio',
        ))
        self.session.commit()

    def test_routes_keep_contract_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(set(self.routes), {
            ('/recurring-payments', 'POST'),
            ('/recurring-payments', 'GET'),
            ('/recurring-payments/{recurring_payment_id}/pay', 'POST'),
        })
        self.assertEqual(self.routes[('/recurring-payments', 'POST')].status_code, 201)
        self.assertIsNone(self.routes[('/recurring-payments', 'GET')].status_code)
        self.assertIsNone(self.routes[('/recurring-payments/{recurring_payment_id}/pay', 'POST')].status_code)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        paths = app.openapi()['paths']
        self.assertEqual(set(paths['/recurring-payments']), {'get', 'post'})
        self.assertEqual(set(paths['/recurring-payments/{recurring_payment_id}/pay']), {'post'})
        self.assertEqual(set(paths['/recurring-payments']['post']['responses']), {'201', '422'})

    def test_create_and_list_keep_decimal_currency_status_and_order(self):
        later = self.create(name='Internet', next_date='2026-11-20')
        earlier = self.create(name='Seguro', currency='USD', amount='12.35', next_date='2026-10-15')
        self.assertEqual(later['active'], True)
        self.assertEqual(earlier['amount'], '12.35')
        saved = self.session.get(RecurringPayment, earlier['id'])
        self.assertEqual(saved.currency, 'USD')
        self.assertEqual(saved.amount, Decimal('12.35'))
        self.assertEqual(saved.active, 1)
        rows = self.routes[('/recurring-payments', 'GET')].endpoint(session=self.session)
        self.assertEqual([row['id'] for row in rows], [earlier['id'], later['id']])
        self.assertEqual(rows[0]['next_payment_date'], '2026-10-15')
        self.assertEqual(rows[0]['active'], True)

    def test_pay_records_expense_and_updates_weekly_date_and_balances(self):
        self.seed_income('PEN', '100.00')
        self.seed_income('USD', '50.00')
        payment = self.create(frequency='weekly', amount='20.00', next_date='2026-10-20')
        response = self.pay(payment['id'], paid_date='2026-10-21')
        self.assertEqual(response, {
            'id': payment['id'], 'name': 'Internet', 'paid_date': '2026-10-21',
            'next_payment_date': '2026-10-27', 'currency': 'PEN',
            'amount': '20.00', 'balances': {'PEN': '80.00', 'USD': '50.00'},
        })
        saved = self.session.get(RecurringPayment, payment['id'])
        self.assertEqual(saved.next_payment_date, date(2026, 10, 27))
        self.assertEqual(saved.active, 1)
        movement = self.session.scalars(select(Movement).where(Movement.kind == 'expense')).one()
        self.assertEqual((movement.date, movement.currency, movement.amount),
                         (date(2026, 10, 21), 'PEN', Decimal('20.00')))
        self.assertEqual((movement.category, movement.description), ('Servicios', 'Internet'))
        self.assertEqual(available(self.session), {'PEN': Decimal('80.00'), 'USD': Decimal('50.00')})

    def test_monthly_and_yearly_rollovers_and_usd_payment(self):
        self.seed_income('USD', '30.00')
        monthly = self.create(currency='USD', amount='10.00', next_date='2026-01-31')
        yearly = self.create(name='Anual', frequency='yearly', amount='5.00', next_date='2024-02-29')
        result = self.pay(monthly['id'])
        self.assertEqual(result['next_payment_date'], '2026-02-28')
        self.assertEqual(result['balances']['USD'], '20.00')
        self.seed_income('PEN', '10.00')
        result_year = self.pay(yearly['id'])
        self.assertEqual(result_year['next_payment_date'], '2025-02-28')
        self.assertEqual(result_year['balances']['PEN'], '5.00')

    def test_missing_inactive_and_insufficient_payment_create_no_expense(self):
        with self.assertRaises(HTTPException) as missing:
            self.pay(999)
        self.assertEqual((missing.exception.status_code, missing.exception.detail),
                         (404, 'Pago recurrente no encontrado.'))
        inactive = self.create(name='Inactivo')
        self.session.get(RecurringPayment, inactive['id']).active = 0
        self.session.commit()
        with self.assertRaises(HTTPException) as inactive_error:
            self.pay(inactive['id'])
        self.assertEqual((inactive_error.exception.status_code, inactive_error.exception.detail),
                         (400, 'Este pago recurrente está inactivo.'))
        active = self.create(name='Sin saldo')
        with self.assertRaises(HTTPException) as insufficient:
            self.pay(active['id'])
        self.assertEqual(insufficient.exception.status_code, 400)
        self.assertEqual(self.session.scalars(select(Movement)).all(), [])
        self.assertEqual(self.session.get(RecurringPayment, active['id']).next_payment_date,
                         date(2026, 10, 20))

    def test_existing_schema_validations_remain(self):
        base = {
            'name': 'Internet', 'category': 'Servicios', 'currency': 'PEN',
            'amount': '20.00', 'frequency': 'monthly',
            'next_payment_date': '2026-10-20',
        }
        for changes in (
            {'frequency': 'daily'}, {'currency': 'EUR'}, {'amount': '0.00'},
            {'amount': '1.001'}, {'name': ''}, {'category': ''},
            {'next_payment_date': '2026-02-30'},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                RecurringPaymentIn.model_validate({**base, **changes})
        with self.assertRaises(ValidationError):
            RecurringPaymentPaidIn.model_validate({'date': '2026-02-30'})


if __name__ == '__main__':
    unittest.main()
