"""Group 3: reimbursement lifecycle, balances and atomic rejections."""
from decimal import Decimal
from sqlalchemy import select
from api.routers import reimbursements, savings_goals
from db.models import Movement
from functional_support import FunctionalCase


class Group3Test(FunctionalCase):
    routers = (reimbursements.create_router, savings_goals.create_router)

    def payload(self, currency='PEN'):
        return {'date': '2026-10-20', 'currency': currency, 'amount': '20.25',
                'category': 'Ficticio', 'description': 'Gasto ficticio'}

    def test_pending_completed_linked_income_and_duplicate_close(self):
        for currency in ('PEN', 'USD'):
            with self.subTest(currency=currency):
                original = self.balances()[0]
                created = self.request('POST', '/reimbursements', self.payload(currency), 201)
                self.assertEqual(created['status'], 'pending')
                self.assertEqual(Decimal(created['amount']), Decimal('20.25'))
                self.assertEqual(self.balances()[0][currency], original[currency] - Decimal('20.25'))
                rows = self.request('GET', '/reimbursements')
                pending = next(r for r in rows if r['id'] == created['id'])
                self.assertIsNone(pending['reimbursement_movement_id'])
                path = f"/reimbursements/{created['id']}/complete"
                closed = self.request('POST', path, {'date': '2026-10-21'})
                self.assertEqual(closed['status'], 'reimbursed')
                self.assertEqual(self.balances()[0], original)
                with self.sessions() as session:
                    expense = session.get(Movement, created['movement_id'])
                    income = session.get(Movement, closed['reimbursement_movement_id'])
                    self.assertEqual((expense.kind, income.kind), ('expense', 'reimbursement'))
                    self.assertEqual((income.currency, income.amount), (currency, Decimal('20.25')))
                    self.assertEqual(income.date.isoformat(), '2026-10-21')
                completed = next(r for r in self.request('GET', '/reimbursements') if r['id'] == created['id'])
                self.assertEqual(completed['status'], 'reimbursed')
                self.assertEqual(completed['reimbursement_movement_id'], closed['reimbursement_movement_id'])
                self.reject(path, {'date': '2026-10-22'}, 400)

    def test_reserved_and_insufficient_balances_reject_without_expense(self):
        for currency in ('PEN', 'USD'):
            self.goal(currency)
            for amount in ('60.01', '100.01'):
                self.reject('/reimbursements', self.payload(currency) | {'amount': amount}, 400)

    def test_invalid_dates_amounts_and_currency_no_partial_rows(self):
        for change in [{'date': '2026-02-30'}, {'amount': '0'}, {'amount': '-1'},
                       {'amount': '0.001'}, {'amount': 'NaN'}, {'currency': 'EUR'}]:
            with self.subTest(change=change):
                self.reject('/reimbursements', self.payload() | change)
        created = self.request('POST', '/reimbursements', self.payload(), 201)
        self.reject(f"/reimbursements/{created['id']}/complete", {'date': 'invalid'})

    def test_missing_reimbursement_returns_404_without_writing(self):
        self.reject('/reimbursements/999/complete', {'date': '2026-10-21'}, 404)
