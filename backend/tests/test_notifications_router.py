"""Offline regression tests for the notifications router."""

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers import notifications
from db.base import Base
from db.models import Budget, Movement, RecurringPayment, Reimbursement


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 20)


class NotificationsRouterTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        def db():
            yield self.session

        self.db = db
        self.router = notifications.create_router(db)
        self.route = next(route for route in self.router.routes if isinstance(route, APIRoute))

    def get_notifications(self):
        with patch.object(notifications, 'date', FixedDate):
            return self.route.endpoint(session=self.session)

    def test_route_contract_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(self.route.path, '/notifications')
        self.assertEqual(self.route.methods, {'GET'})
        self.assertIsNone(self.route.status_code)
        self.assertIs(self.route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        self.assertIn('/notifications', app.openapi()['paths'])

    def test_empty_result(self):
        self.assertEqual(self.get_notifications(), [])

    def test_recurring_due_date_levels_and_inactive(self):
        for offset, active in [(-1, 1), (0, 1), (3, 1), (7, 1), (8, 1), (0, 0)]:
            self.session.add(RecurringPayment(
                name=f'Pago {offset} {active}', category='Servicios', currency='PEN',
                amount=Decimal('20.00'), frequency='monthly',
                next_payment_date=FixedDate.today() + timedelta(days=offset),
                active=active,
            ))
        self.session.commit()
        result = self.get_notifications()
        self.assertEqual(
            [(item['title'], item['level']) for item in result],
            [('Pago vencido', 'danger'), ('Pago vence hoy', 'danger'),
             ('Pago próximo', 'warning'), ('Próximo pago', 'info')],
        )
        self.assertEqual([item['date'] for item in result],
                         ['2026-10-19', '2026-10-20', '2026-10-23', '2026-10-27'])

    def test_budget_thresholds_and_financial_filters(self):
        for category, currency, amount in [
            ('A', 'PEN', '75.00'), ('B', 'PEN', '90.00'),
            ('C', 'USD', '100.00'), ('D', 'PEN', '74.99'),
        ]:
            self.session.add(Budget(
                month='2026-10', category=category, currency=currency,
                limit_amount=Decimal('100.00'),
            ))
            self.session.add(Movement(
                date=date(2026, 10, 10), kind='expense', currency=currency,
                amount=Decimal(amount), category=category,
            ))
        for kind, currency, category, when in [
            ('income', 'PEN', 'A', date(2026, 10, 10)),
            ('expense', 'USD', 'A', date(2026, 10, 10)),
            ('expense', 'PEN', 'A', date(2026, 9, 10)),
        ]:
            self.session.add(Movement(
                date=when, kind=kind, currency=currency,
                amount=Decimal('1000.00'), category=category,
            ))
        self.session.commit()
        result = self.get_notifications()
        self.assertEqual(
            [(item['title'], item['level']) for item in result],
            [('Presupuesto al 75%', 'info'), ('Presupuesto al 90%', 'warning'),
             ('Presupuesto excedido', 'danger')],
        )
        self.assertTrue(all(item['date'] == '2026-10-01' for item in result))
        self.assertEqual(len(self.session.dirty), 0)

    def test_pending_reimbursements_and_original_order(self):
        movement = Movement(
            date=date(2026, 10, 15), kind='expense', currency='PEN',
            amount=Decimal('12.50'), category='Viáticos',
        )
        self.session.add(movement)
        self.session.flush()
        self.session.add_all([
            Reimbursement(
                date=date(2026, 10, 15), currency='PEN',
                amount=Decimal('12.50'), category='Viáticos',
                status=status, movement_id=movement.id,
            ) for status in ('pending', 'reimbursed')
        ])
        self.session.add(RecurringPayment(
            name='Internet', category='Servicios', currency='PEN',
            amount=Decimal('20.00'), frequency='monthly',
            next_payment_date=date(2026, 10, 20), active=1,
        ))
        self.session.commit()
        result = self.get_notifications()
        self.assertEqual([item['type'] for item in result],
                         ['recurring_payment', 'reimbursement'])
        self.assertEqual(result[1]['date'], '2026-10-15')
        self.assertIn('PEN 12.50', result[1]['message'])
        self.assertIn('5 días', result[1]['message'])


if __name__ == '__main__':
    unittest.main()
