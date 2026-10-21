"""Offline regression tests for the extracted reimbursements router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.routers.reimbursements import create_router
from db.base import Base
from db.models import Movement, Reimbursement
from schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
from services.balances import available


class ReimbursementsRouterTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

        def db():
            with Session(self.engine) as session:
                yield session

        self.db = db
        self.router = create_router(db)
        self.routes = {
            (route.path, next(iter(route.methods))): route
            for route in self.router.routes if isinstance(route, APIRoute)
        }

    def endpoint(self, method, path):
        return self.routes[(path, method)].endpoint

    def seed_income(self, currency='PEN', amount='100.00'):
        with Session(self.engine) as session:
            session.add(Movement(
                date=date(2026, 10, 1), kind='income', currency=currency,
                amount=Decimal(amount), category='Ingreso ficticio',
            ))
            session.commit()

    def create(self, currency='PEN', amount='20.00', day=10, description='Gasto ficticio'):
        payload = ReimbursementIn.model_validate({
            'date': f'2026-10-{day:02d}', 'currency': currency,
            'amount': amount, 'description': description,
        })
        with Session(self.engine) as session:
            return self.endpoint('POST', '/reimbursements')(payload, session=session)

    def complete(self, reimbursement_id, day=20):
        payload = ReimbursementPaidIn.model_validate({'date': f'2026-10-{day:02d}'})
        with Session(self.engine) as session:
            return self.endpoint('POST', '/reimbursements/{reimbursement_id}/complete')(
                reimbursement_id, payload, session=session,
            )

    def test_routes_keep_paths_methods_status_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(set(self.routes), {
            ('/reimbursements', 'POST'),
            ('/reimbursements/{reimbursement_id}/complete', 'POST'),
            ('/reimbursements', 'GET'),
        })
        self.assertEqual(self.routes[('/reimbursements', 'POST')].status_code, 201)
        self.assertIsNone(self.routes[('/reimbursements', 'GET')].status_code)
        self.assertIsNone(self.routes[('/reimbursements/{reimbursement_id}/complete', 'POST')].status_code)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        paths = app.openapi()['paths']
        self.assertEqual(set(paths['/reimbursements']), {'get', 'post'})
        self.assertEqual(set(paths['/reimbursements']['post']['responses']), {'201', '422'})
        self.assertEqual(set(paths['/reimbursements/{reimbursement_id}/complete']['post']['responses']), {'200', '422'})

    def test_creation_links_expense_and_reduces_balance(self):
        self.seed_income('PEN', '100.00')
        response = self.create()
        self.assertEqual(response['status'], 'pending')
        self.assertEqual(response['currency'], 'PEN')
        self.assertEqual(response['amount'], '20.00')
        with Session(self.engine) as session:
            reimbursement = session.get(Reimbursement, response['id'])
            movement = session.get(Movement, response['movement_id'])
            self.assertEqual(reimbursement.movement_id, movement.id)
            self.assertEqual(reimbursement.status, 'pending')
            self.assertEqual(movement.kind, 'expense')
            self.assertEqual(movement.amount, Decimal('20.00'))
            self.assertEqual(available(session), {'PEN': Decimal('80.00'), 'USD': Decimal('0')})

    def test_list_order_and_pending_fields(self):
        self.seed_income('PEN', '100.00')
        older = self.create(day=10)
        newer = self.create(day=12)
        with Session(self.engine) as session:
            rows = self.endpoint('GET', '/reimbursements')(session=session)
        self.assertEqual([row['id'] for row in rows], [newer['id'], older['id']])
        self.assertEqual(rows[0]['date'], '2026-10-12')
        self.assertIsNone(rows[0]['reimbursed_date'])
        self.assertIsNone(rows[0]['reimbursement_movement_id'])

    def test_completion_links_one_movement_and_restores_balance(self):
        self.seed_income('PEN', '100.00')
        self.seed_income('USD', '50.00')
        created = self.create(description='Taxi')
        completed = self.complete(created['id'])
        self.assertEqual(completed, {
            'id': created['id'], 'status': 'reimbursed',
            'reimbursed_date': '2026-10-20', 'currency': 'PEN', 'amount': '20.00',
            'reimbursement_movement_id': completed['reimbursement_movement_id'],
        })
        with Session(self.engine) as session:
            reimbursement = session.get(Reimbursement, created['id'])
            income = session.get(Movement, completed['reimbursement_movement_id'])
            self.assertEqual(reimbursement.reimbursement_movement_id, income.id)
            self.assertEqual(income.kind, 'reimbursement')
            self.assertEqual(income.category, 'Reembolso laboral')
            self.assertEqual(income.description, f'Reembolso #{created["id"]}: Taxi')
            self.assertEqual(income.amount, Decimal('20.00'))
            self.assertEqual(available(session), {'PEN': Decimal('100.00'), 'USD': Decimal('50.00')})
            self.assertEqual(len(session.scalars(select(Movement)).all()), 4)

    def test_missing_or_duplicate_completion_does_not_add_movement(self):
        with self.assertRaises(HTTPException) as missing:
            self.complete(999)
        self.assertEqual((missing.exception.status_code, missing.exception.detail),
                         (404, 'Reembolso no encontrado.'))
        self.seed_income()
        created = self.create()
        self.complete(created['id'])
        with self.assertRaises(HTTPException) as repeated:
            self.complete(created['id'])
        self.assertEqual((repeated.exception.status_code, repeated.exception.detail),
                         (400, 'Este reembolso ya no está pendiente.'))
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(Movement)).all()), 3)

    def test_insufficient_balance_creates_nothing(self):
        with self.assertRaises(HTTPException) as insufficient:
            self.create()
        self.assertEqual(insufficient.exception.status_code, 400)
        with Session(self.engine) as session:
            self.assertEqual(session.scalars(select(Reimbursement)).all(), [])
            self.assertEqual(session.scalars(select(Movement)).all(), [])


if __name__ == '__main__':
    unittest.main()
