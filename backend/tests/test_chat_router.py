"""Offline route tests; provider calls are replaced by local mocks."""

import socket
import sys
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers import chat as chat_router
from chat.balances import BalanceChatRequest
from chat.financial_tools import FinancialToolsRequest
from chat.tool_balances import ToolBalanceRequest
from db.base import Base
from db.models import Movement
from services.financial_queries import (
    SpendingSummaryParams, SpendingByCategoryParams, BudgetStatusParams,
)


class ChatRouterTest(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(
            socket.socket, 'connect', side_effect=AssertionError('Network forbidden'),
        )
        self.network.start()
        self.addCleanup(self.network.stop)
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        def db():
            yield self.session

        self.db = db
        self.router = chat_router.create_router(db)
        self.routes = {
            route.path: route for route in self.router.routes if isinstance(route, APIRoute)
        }

    def request(self, *, host='127.0.0.1', origin=None, forwarded=False):
        headers = [(b'host', b'127.0.0.1:8000')]
        if origin:
            headers.append((b'origin', origin.encode()))
        if forwarded:
            headers.append((b'x-forwarded-for', b'127.0.0.1'))
        return Request({
            'type': 'http', 'method': 'POST', 'scheme': 'http',
            'path': '/api/chat/tools', 'root_path': '',
            'server': ('127.0.0.1', 8000), 'client': (host, 50000),
            'headers': headers,
        })

    def call(self, path, message='¿Cuánto dinero tengo disponible en soles y dólares?',
             request=None):
        payload_type = {
            '/api/chat/balances': BalanceChatRequest,
            '/api/chat/tool-balances': ToolBalanceRequest,
            '/api/chat/tools': FinancialToolsRequest,
        }[path]
        return self.routes[path].endpoint(
            payload_type(message=message), request or self.request(),
            session=self.session,
        )

    def test_contracts_and_injected_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(list(self.routes), [
            '/api/chat/balances', '/api/chat/tool-balances', '/api/chat/tools',
        ])
        for route in self.routes.values():
            self.assertEqual(route.methods, {'POST'})
            self.assertIsNone(route.status_code)
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        self.assertEqual(set(app.openapi()['paths']), set(self.routes))

    def test_local_access_guards_apply_to_all_three_routes(self):
        for path in self.routes:
            for request in (
                self.request(host='192.0.2.1'),
                self.request(origin='https://example.invalid'),
                self.request(forwarded=True),
            ):
                with self.subTest(path=path), self.assertRaises(HTTPException) as caught:
                    self.call(path, request=request)
                self.assertEqual(caught.exception.status_code, 403)
        for path in self.routes:
            self.call_accepted_origin(path)

    def call_accepted_origin(self, path):
        with patch.object(chat_router, 'is_balance_question', return_value=False), \
             patch.object(chat_router, 'run_tool_balances', return_value=object()), \
             patch.object(chat_router, 'run_financial_tools', return_value=object()):
            self.call(path, request=self.request(origin='http://localhost:8000'))

    def test_unsupported_balance_question_does_not_query_or_call_provider(self):
        with patch.object(chat_router, 'get_balances', side_effect=AssertionError('Query forbidden')), \
             patch.object(chat_router, 'explain_balances', side_effect=AssertionError('Provider forbidden')):
            result = self.call('/api/chat/balances', message='Cuéntame un chiste')
        self.assertEqual(result.explanation_source, 'unsupported')
        self.assertIsNone(result.financial_data)

    def test_balance_route_uses_exact_query_result_and_keeps_error(self):
        expected = {
            key: {'PEN': '12.34', 'USD': '5.67'}
            for key in ('balances', 'reserved', 'spendable')
        }
        marker = object()
        with patch.object(chat_router, 'get_balances', return_value=expected) as query, \
             patch.object(chat_router, 'explain_balances', return_value=marker) as explain:
            self.assertIs(self.call('/api/chat/balances'), marker)
        self.assertEqual(query.call_count, 1)
        self.assertIs(query.call_args.args[0], self.session)
        explain.assert_called_once_with(expected)
        with patch.object(chat_router, 'get_balances', side_effect=RuntimeError('synthetic')):
            with self.assertRaises(HTTPException) as caught:
                self.call('/api/chat/balances')
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail, 'No se pudieron consultar los saldos financieros.')

    def test_tool_balances_executes_injected_query_once(self):
        self.session.add(Movement(
            date=date(2026, 10, 20), kind='income', currency='PEN',
            amount=Decimal('15.25'), category='Ingreso ficticio',
        ))
        self.session.commit()
        marker = object()
        results = []

        def fake_flow(message, execute_balances):
            results.append(execute_balances())
            return marker

        with patch.object(chat_router, 'run_tool_balances', side_effect=fake_flow) as flow:
            self.assertIs(self.call('/api/chat/tool-balances'), marker)
        self.assertEqual(flow.call_count, 1)
        self.assertEqual(results[0]['balances'], {'PEN': '15.25', 'USD': '0.00'})
        self.assertFalse(self.session.dirty)

    def test_four_read_only_callbacks_are_delegated_without_provider_calls(self):
        self.session.add(Movement(
            date=date(2026, 10, 20), kind='expense', currency='PEN',
            amount=Decimal('4.50'), category='Servicios',
        ))
        self.session.commit()
        marker = object()
        callbacks = []

        def fake_flow(message, *queries):
            callbacks.extend(queries)
            return marker

        with patch.object(chat_router, 'run_financial_tools', side_effect=fake_flow) as flow:
            self.assertIs(self.call('/api/chat/tools'), marker)
        self.assertEqual(flow.call_count, 1)
        self.assertEqual(len(callbacks), 4)
        self.assertEqual(callbacks[0]()['balances']['PEN'], '-4.50')
        as_of = date(2026, 10, 20)
        self.assertIsInstance(callbacks[1](
            SpendingSummaryParams(period='current_month', month=None, currency='PEN'), as_of,
        ), dict)
        self.assertIsInstance(callbacks[2](
            SpendingByCategoryParams(period='current_month', month=None, currency='PEN',
                                     category=None, limit=5), as_of,
        ), dict)
        self.assertIsInstance(callbacks[3](
            BudgetStatusParams(period='current_month', month=None, currency='PEN',
                               category=None), as_of,
        ), dict)
        self.assertFalse(self.session.dirty)


if __name__ == '__main__':
    unittest.main()
