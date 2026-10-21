"""Offline regression checks for the extracted savings goals router."""

import sys
import unittest
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.routers.savings_goals import create_router
from db.base import Base
from db.models import Movement, SavingsContribution, SavingsGoal
from schemas.savings_goals import SavingsContributionIn, SavingsGoalIn
from services.balances import available, reserved_savings, spendable_balance


class SavingsGoalsRouterTest(unittest.TestCase):
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

    def endpoint(self, method, path):
        return self.routes[(path, method)].endpoint

    def income(self, currency, amount):
        self.session.add(Movement(
            date=date(2026, 10, 1), kind='income', currency=currency,
            amount=Decimal(amount), category='Ingreso ficticio',
        ))
        self.session.commit()

    def goal(self, *, name=' Viaje ', currency='PEN', target='100.00', target_date=None):
        payload = SavingsGoalIn.model_validate({
            'name': name, 'currency': currency, 'target_amount': target,
            'target_date': target_date,
        })
        return self.endpoint('POST', '/savings-goals')(payload, session=self.session)

    def contribute(self, goal_id, amount, contribution_date='2026-10-20'):
        payload = SavingsContributionIn.model_validate({
            'date': contribution_date, 'amount': amount,
        })
        return self.endpoint('POST', '/savings-goals/{goal_id}/contributions')(
            goal_id, payload, session=self.session,
        )

    def test_routes_keep_contract_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(list(self.routes), [
            ('/savings-goals', 'POST'),
            ('/savings-goals', 'GET'),
            ('/savings-goals/{goal_id}/contributions', 'POST'),
            ('/savings-goals/{goal_id}/cancel', 'POST'),
            ('/savings-goals/{goal_id}/use', 'POST'),
        ])
        self.assertEqual(self.routes[('/savings-goals', 'POST')].status_code, 201)
        self.assertEqual(self.routes[('/savings-goals/{goal_id}/contributions', 'POST')].status_code, 201)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        paths = app.openapi()['paths']
        self.assertEqual(set(paths['/savings-goals']), {'get', 'post'})
        self.assertEqual(set(paths['/savings-goals']['post']['responses']), {'201', '422'})
        self.assertEqual(set(paths['/savings-goals/{goal_id}/contributions']['post']['responses']), {'201', '422'})
        self.assertEqual(set(paths['/savings-goals/{goal_id}/cancel']['post']['responses']), {'200', '422'})
        self.assertEqual(set(paths['/savings-goals/{goal_id}/use']['post']['responses']), {'200', '422'})

    def test_create_and_list_keep_names_dates_currency_and_order(self):
        pen = self.goal(target_date='2027-01-31')
        usd = self.goal(name='Equipo', currency='USD', target='250.25')
        self.assertEqual(pen, {
            'id': pen['id'], 'name': 'Viaje', 'currency': 'PEN',
            'target_amount': '100.00', 'target_date': '2027-01-31',
            'active': True, 'saved_amount': '0.00', 'percentage': 0,
        })
        self.assertEqual(usd['currency'], 'USD')
        self.assertEqual(usd['target_amount'], '250.25')
        rows = self.endpoint('GET', '/savings-goals')(session=self.session)
        self.assertEqual([row['id'] for row in rows], [usd['id'], pen['id']])
        self.assertEqual(rows[0]['saved_amount'], '0')
        self.assertEqual(rows[0]['percentage'], 0.0)

    def test_contribution_reserves_decimal_without_changing_total_balance(self):
        self.income('PEN', '100.25')
        self.income('USD', '50.00')
        pen = self.goal(target='80.00')
        usd = self.goal(name='Dólares', currency='USD', target='30.00')
        first = self.contribute(pen['id'], '20.10')
        second = self.contribute(usd['id'], '5.25')
        self.assertEqual((first['amount'], first['saved_amount'], first['percentage']),
                         ('20.10', '20.10', 25.1))
        self.assertEqual(second['currency'], 'USD')
        self.assertEqual(self.session.get(SavingsContribution, first['id']).amount, Decimal('20.10'))
        self.assertEqual(available(self.session), {
            'PEN': Decimal('100.25'), 'USD': Decimal('50.00'),
        })
        self.assertEqual(reserved_savings(self.session), {
            'PEN': Decimal('20.10'), 'USD': Decimal('5.25'),
        })
        self.assertEqual(spendable_balance(self.session), {
            'PEN': Decimal('80.15'), 'USD': Decimal('44.75'),
        })
        rows = self.endpoint('GET', '/savings-goals')(session=self.session)
        self.assertEqual({row['id']: row['saved_amount'] for row in rows},
                         {pen['id']: '20.10', usd['id']: '5.25'})

    def test_contribution_guards_missing_inactive_balance_and_target(self):
        with self.assertRaises(HTTPException) as missing:
            self.contribute(999, '1.00')
        self.assertEqual(missing.exception.status_code, 404)
        goal = self.goal(target='20.00')
        with self.assertRaises(HTTPException) as no_balance:
            self.contribute(goal['id'], '1.00')
        self.assertEqual(no_balance.exception.status_code, 400)
        self.income('PEN', '100.00')
        with self.assertRaises(HTTPException) as above_target:
            self.contribute(goal['id'], '20.01')
        self.assertEqual(above_target.exception.status_code, 400)
        self.assertEqual(self.session.scalars(select(SavingsContribution)).all(), [])
        self.session.get(SavingsGoal, goal['id']).active = 0
        self.session.commit()
        with self.assertRaises(HTTPException) as inactive:
            self.contribute(goal['id'], '1.00')
        self.assertEqual(inactive.exception.status_code, 400)

    def test_cancel_releases_reservation_without_creating_movement(self):
        self.income('PEN', '100.00')
        goal = self.goal()
        self.contribute(goal['id'], '40.00')
        before = len(self.session.scalars(select(Movement)).all())
        result = self.endpoint('POST', '/savings-goals/{goal_id}/cancel')(
            goal['id'], session=self.session,
        )
        self.assertEqual((result['status'], result['released_amount'], result['currency']),
                         ('cancelled', '40.00', 'PEN'))
        self.assertEqual(self.session.get(SavingsGoal, goal['id']).active, 0)
        self.assertEqual(len(self.session.scalars(select(Movement)).all()), before)
        self.assertEqual(available(self.session)['PEN'], Decimal('100.00'))
        self.assertEqual(reserved_savings(self.session)['PEN'], Decimal('0'))
        self.assertEqual(spendable_balance(self.session)['PEN'], Decimal('100.00'))
        self.assertEqual(self.endpoint('GET', '/savings-goals')(session=self.session), [])
        with self.assertRaises(HTTPException) as repeated:
            self.endpoint('POST', '/savings-goals/{goal_id}/cancel')(
                goal['id'], session=self.session,
            )
        self.assertEqual(repeated.exception.status_code, 400)

    def test_use_records_expense_and_preserves_spendable_balance(self):
        self.income('USD', '50.00')
        goal = self.goal(name='Equipo', currency='USD', target='40.00')
        self.contribute(goal['id'], '20.00')
        before = spendable_balance(self.session)['USD']
        result = self.endpoint('POST', '/savings-goals/{goal_id}/use')(
            goal['id'], session=self.session,
        )
        self.assertEqual((result['status'], result['currency'], result['used_amount']),
                         ('completed', 'USD', '20.00'))
        movement = self.session.get(Movement, result['movement_id'])
        self.assertEqual((movement.kind, movement.currency, movement.amount),
                         ('expense', 'USD', Decimal('20.00')))
        self.assertEqual(movement.date, date.today())
        self.assertEqual((movement.category, movement.description),
                         ('Otros gastos', 'Uso de ahorro: Equipo'))
        self.assertEqual(self.session.get(SavingsGoal, goal['id']).active, 0)
        self.assertEqual(available(self.session)['USD'], Decimal('30.00'))
        self.assertEqual(reserved_savings(self.session)['USD'], Decimal('0'))
        self.assertEqual(spendable_balance(self.session)['USD'], before)
        with self.assertRaises(HTTPException) as repeated:
            self.endpoint('POST', '/savings-goals/{goal_id}/use')(
                goal['id'], session=self.session,
            )
        self.assertEqual(repeated.exception.status_code, 400)

    def test_use_without_savings_and_existing_schema_validation(self):
        goal = self.goal()
        with self.assertRaises(HTTPException) as empty:
            self.endpoint('POST', '/savings-goals/{goal_id}/use')(
                goal['id'], session=self.session,
            )
        self.assertEqual(empty.exception.status_code, 400)
        self.assertEqual(self.session.scalars(select(Movement)).all(), [])
        for changes in (
            {'currency': 'EUR'}, {'target_amount': '0.00'},
            {'target_amount': '1.001'}, {'name': ''},
            {'target_date': '2026-02-30'},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SavingsGoalIn.model_validate({
                    'name': 'Viaje', 'currency': 'PEN',
                    'target_amount': '100.00', **changes,
                })
        with self.assertRaises(ValidationError):
            SavingsContributionIn.model_validate({
                'date': '2026-10-20', 'amount': '0.00',
            })


if __name__ == '__main__':
    unittest.main()
