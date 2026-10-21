"""HTTP checks for movements with fictitious savings, using SQLite memory only."""

import asyncio
import json
import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.routers.movements import create_router
from db.base import Base
from db.models import Movement, SavingsContribution, SavingsGoal
from services.balances import available, reserved_savings, spendable_balance


class MovementsReservedHttpTest(unittest.TestCase):
    def setUp(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.engine = create_engine(
            'sqlite+pysqlite:///:memory:',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
        )
        self.assertEqual(self.engine.url.get_backend_name(), 'sqlite')
        self.assertEqual(self.engine.url.database, ':memory:')
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

        with self.sessions() as session:
            session.add_all([
                Movement(
                    date=date(2026, 10, 1), kind='income', currency='PEN',
                    amount=Decimal('100.00'), category='Ingreso ficticio',
                ),
                Movement(
                    date=date(2026, 10, 1), kind='income', currency='USD',
                    amount=Decimal('80.00'), category='Ingreso ficticio',
                ),
            ])
            goal = SavingsGoal(
                name='Meta ficticia', currency='PEN',
                target_amount=Decimal('50.00'), active=1,
            )
            session.add(goal)
            session.flush()
            session.add(SavingsContribution(
                goal_id=goal.id, date=date(2026, 10, 2),
                amount=Decimal('40.00'),
            ))
            session.commit()

        def db():
            with self.sessions() as session:
                yield session

        app = FastAPI()
        app.include_router(create_router(db))
        self.assertEqual(set(app.openapi()['paths']), {'/movements'})
        self.app = app

    def request(self, method, path, payload=None):
        body = json.dumps(payload).encode('utf-8') if payload is not None else b''

        async def call():
            messages = []

            async def receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}

            async def send(message):
                messages.append(message)

            await self.app({
                'type': 'http', 'asgi': {'version': '3.0'},
                'http_version': '1.1', 'method': method, 'scheme': 'http',
                'path': path, 'raw_path': path.encode('ascii'),
                'query_string': b'', 'root_path': '',
                'headers': [(b'content-type', b'application/json')],
                'client': ('127.0.0.1', 50000), 'server': ('127.0.0.1', 8000),
            }, receive, send)
            status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
            response_body = b''.join(
                m.get('body', b'') for m in messages if m['type'] == 'http.response.body'
            )
            return status, json.loads(response_body)

        return asyncio.run(call())

    def balances_and_count(self):
        with self.sessions() as session:
            return (
                available(session),
                reserved_savings(session),
                spendable_balance(session),
                session.scalar(select(func.count()).select_from(Movement)),
            )

    def expense(self, amount):
        return self.request('POST', '/movements', {
            'date': '2026-10-20', 'kind': 'expense', 'currency': 'PEN',
            'amount': amount, 'category': 'Gasto ficticio',
            'description': 'Prueba aislada',
        })

    def test_reserved_pen_rejects_expense_below_total_without_writing(self):
        before = self.balances_and_count()
        self.assertEqual(before, (
            {'PEN': Decimal('100.00'), 'USD': Decimal('80.00')},
            {'PEN': Decimal('40.00'), 'USD': Decimal('0')},
            {'PEN': Decimal('60.00'), 'USD': Decimal('80.00')},
            2,
        ))
        response = self.expense('70.00')
        self.assertEqual(response[0], 400)
        self.assertEqual(response[1], {
            'detail': 'Saldo disponible insuficiente en PEN. '
                      'Disponible: PEN 60.00. '
                      'Parte de tu saldo puede estar reservada para metas de ahorro.'
        })
        self.assertEqual(self.balances_and_count(), before)
        self.assertEqual(len(self.request('GET', '/movements')[1]), 2)

    def test_allowed_pen_expense_preserves_usd_and_reservation(self):
        response = self.expense('20.25')
        self.assertEqual(response[0], 201)
        movement_id = response[1]['id']
        self.assertEqual(response[1], {'id': movement_id})
        with self.sessions() as session:
            movement = session.get(Movement, movement_id)
            self.assertEqual((movement.kind, movement.currency, movement.amount),
                             ('expense', 'PEN', Decimal('20.25')))
            self.assertEqual((movement.date, movement.category),
                             (date(2026, 10, 20), 'Gasto ficticio'))
        self.assertEqual(self.balances_and_count(), (
            {'PEN': Decimal('79.75'), 'USD': Decimal('80.00')},
            {'PEN': Decimal('40.00'), 'USD': Decimal('0')},
            {'PEN': Decimal('39.75'), 'USD': Decimal('80.00')},
            3,
        ))
        rows = self.request('GET', '/movements')[1]
        self.assertEqual(rows[0]['id'], movement_id)
        self.assertEqual(rows[0]['amount'], '20.25')

    def test_expense_equal_to_spendable_is_allowed(self):
        response = self.expense('60.00')
        self.assertEqual(response[0], 201)
        self.assertEqual(set(response[1]), {'id'})
        self.assertEqual(self.balances_and_count(), (
            {'PEN': Decimal('40.00'), 'USD': Decimal('80.00')},
            {'PEN': Decimal('40.00'), 'USD': Decimal('0')},
            {'PEN': Decimal('0.00'), 'USD': Decimal('80.00')},
            3,
        ))


if __name__ == '__main__':
    unittest.main()
