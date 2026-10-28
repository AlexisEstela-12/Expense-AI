"""In-process ASGI requests and disposable SQLite fixtures; no HTTP server."""
import asyncio
import json
import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import Movement
from services.balances import available, reserved_savings, spendable_balance


class FunctionalCase(unittest.TestCase):
    routers = ()

    def setUp(self):
        for name in ('main', 'backend.main', 'db.session', 'backend.db.session'):
            self.assertNotIn(name, sys.modules)
        self.engine = create_engine('sqlite+pysqlite:///:memory:',
                                    connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        self.assertEqual(self.engine.url.database, ':memory:')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

        def db():
            with self.sessions() as session:
                yield session

        self.app = FastAPI()
        for factory in self.routers:
            self.app.include_router(factory(db))
        with self.sessions() as session:
            for currency in ('PEN', 'USD'):
                session.add(Movement(date=date(2026, 10, 1), kind='income',
                                     currency=currency, amount=Decimal('100.00'), category='Ficticio'))
            session.commit()

    def request(self, method, path, payload=None, status=200):
        body = json.dumps(payload).encode() if payload is not None else b''

        async def call():
            messages = []

            async def receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}

            async def send(message):
                messages.append(message)

            await self.app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                            'method': method, 'scheme': 'http', 'path': path,
                            'raw_path': path.encode(), 'query_string': b'', 'root_path': '',
                            'headers': [(b'content-type', b'application/json')],
                            'client': ('127.0.0.1', 50000), 'server': ('test.invalid', 80)}, receive, send)
            code = next(m['status'] for m in messages if m['type'] == 'http.response.start')
            data = json.loads(b''.join(m.get('body', b'') for m in messages
                                       if m['type'] == 'http.response.body'))
            return code, data

        code, data = asyncio.run(call())
        self.assertEqual(code, status, data)
        return data

    def snapshot(self):
        """Compare every persisted column, not only row counts, after rejection."""
        with self.engine.connect() as connection:
            return {table.name: list(connection.execute(select(table).order_by(*table.primary_key)))
                    for table in Base.metadata.sorted_tables}

    def reject(self, path, payload, status=422):
        before = self.snapshot()
        self.request('POST', path, payload, status=status)
        self.assertEqual(self.snapshot(), before)

    def balances(self):
        with self.sessions() as session:
            return available(session), reserved_savings(session), spendable_balance(session)

    def goal(self, currency='PEN', amount='40.00'):
        goal = self.request('POST', '/savings-goals', {
            'name': 'Meta ficticia', 'currency': currency, 'target_amount': '100.00',
        }, status=201)
        self.request('POST', f"/savings-goals/{goal['id']}/contributions", {
            'date': '2026-10-20', 'amount': amount,
        }, status=201)
        return goal['id']
