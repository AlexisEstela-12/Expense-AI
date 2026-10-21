"""Offline validation and serialization checks for extracted request schemas."""

import sys
import unittest

from pydantic import ValidationError

from schemas.budgets import BudgetIn
from schemas.categories import CategoryIn
from schemas.common import Money
from schemas.exchanges import ExchangeIn
from schemas.movements import MovementIn
from schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
from schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
from schemas.savings_goals import SavingsContributionIn, SavingsGoalIn


class ExtractedSchemaTest(unittest.TestCase):
    def test_importing_schemas_does_not_import_application_or_database_session(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)

    def test_money_values_and_decimal_serialization(self):
        self.assertEqual([item.value for item in Money], ['PEN', 'USD'])
        payload = MovementIn.model_validate({
            'date': '2026-10-20', 'kind': 'expense', 'currency': 'PEN',
            'amount': '12.50', 'category': 'Servicios',
        })
        self.assertEqual(payload.model_dump(mode='json'), {
            'date': '2026-10-20', 'kind': 'expense', 'currency': 'PEN',
            'amount': '12.50', 'category': 'Servicios', 'description': '',
        })
        with self.assertRaises(ValidationError):
            MovementIn.model_validate({
                'date': '2026-10-20', 'kind': 'transfer', 'currency': 'PEN',
                'amount': '12.50', 'category': 'Servicios',
            })
        with self.assertRaises(ValidationError):
            MovementIn.model_validate({
                'date': '2026-10-20', 'kind': 'expense', 'currency': 'EUR',
                'amount': '12.50', 'category': 'Servicios',
            })

    def test_exchange_budget_and_category_constraints(self):
        exchange = ExchangeIn.model_validate({
            'date': '2026-10-20', 'from_currency': 'USD',
            'amount_out': '10.00', 'amount_in': '37.50',
        })
        self.assertEqual(exchange.model_dump(mode='json')['amount_out'], '10.00')
        budget = BudgetIn.model_validate({
            'month': '2026-10', 'category': 'Servicios',
            'currency': 'PEN', 'limit_amount': '200.00',
        })
        self.assertEqual(budget.model_dump(mode='json')['limit_amount'], '200.00')
        for invalid_month in ('2026-00', '2026-13', '2026-1'):
            with self.subTest(month=invalid_month), self.assertRaises(ValidationError):
                BudgetIn.model_validate({
                    'month': invalid_month, 'category': 'Servicios',
                    'currency': 'PEN', 'limit_amount': '200.00',
                })
        with self.assertRaises(ValidationError):
            CategoryIn.model_validate({'name': 'Servicios', 'kind': 'other'})

    def test_reimbursement_and_recurring_defaults_and_dates(self):
        reimbursement = ReimbursementIn.model_validate({
            'date': '2026-10-20', 'currency': 'PEN', 'amount': '20.00',
        })
        self.assertEqual(reimbursement.category, 'Gastos laborales')
        self.assertEqual(reimbursement.description, '')
        self.assertEqual(
            ReimbursementPaidIn.model_validate({'date': '2026-10-20'}).model_dump(mode='json'),
            {'date': '2026-10-20'},
        )
        recurring = RecurringPaymentIn.model_validate({
            'name': 'Internet', 'category': 'Servicios', 'currency': 'USD',
            'amount': '30.00', 'frequency': 'monthly',
            'next_payment_date': '2026-11-01',
        })
        self.assertEqual(recurring.model_dump(mode='json')['amount'], '30.00')
        with self.assertRaises(ValidationError):
            RecurringPaymentIn.model_validate({
                'name': 'Internet', 'category': 'Servicios', 'currency': 'USD',
                'amount': '30.00', 'frequency': 'daily',
                'next_payment_date': '2026-11-01',
            })
        self.assertEqual(
            RecurringPaymentPaidIn.model_validate({'date': '2026-10-20'}).model_dump(mode='json'),
            {'date': '2026-10-20'},
        )

    def test_savings_goal_and_contribution_constraints(self):
        goal = SavingsGoalIn.model_validate({
            'name': 'Viaje', 'currency': 'PEN', 'target_amount': '1000.00',
        })
        self.assertIsNone(goal.target_date)
        self.assertEqual(goal.model_dump(mode='json')['target_amount'], '1000.00')
        contribution = SavingsContributionIn.model_validate({
            'date': '2026-10-20', 'amount': '50.00',
        })
        self.assertEqual(contribution.model_dump(mode='json')['amount'], '50.00')
        with self.assertRaises(ValidationError):
            SavingsContributionIn.model_validate({'date': '2026-10-20', 'amount': '0.00'})


if __name__ == '__main__':
    unittest.main()
