"""Group 4: recurring payment frequencies, expenses and atomic failures."""
from decimal import Decimal
from api.routers import recurring_payments, savings_goals
from db.models import RecurringPayment
from functional_support import FunctionalCase


class Group4Test(FunctionalCase):
    routers = (recurring_payments.create_router, savings_goals.create_router)

    def payload(self, **changes):
        return {'name': 'Pago ficticio', 'category': 'Ficticio', 'currency': 'PEN',
                'amount': '10.25', 'frequency': 'monthly',
                'next_payment_date': '2026-01-31'} | changes

    def test_weekly_monthly_yearly_dates_and_movements(self):
        for frequency, start, end, currency in [
            ('weekly', '2026-12-28', '2027-01-04', 'PEN'),
            ('monthly', '2026-01-31', '2026-02-28', 'USD'),
            ('yearly', '2024-02-29', '2025-02-28', 'PEN')]:
            with self.subTest(frequency=frequency):
                before = self.snapshot()['movements']
                balances = self.balances()[0]
                item = self.request('POST', '/recurring-payments', self.payload(
                    frequency=frequency, next_payment_date=start, currency=currency), 201)
                self.assertEqual(self.snapshot()['movements'], before)
                paid = self.request('POST', f"/recurring-payments/{item['id']}/pay", {'date': start})
                self.assertEqual(paid['next_payment_date'], end)
                balances[currency] -= Decimal('10.25')
                self.assertEqual(self.balances()[0], balances)
                rows = self.snapshot()['movements']
                self.assertEqual(len(rows), len(before) + 1)
                movement = rows[-1]._mapping
                self.assertEqual((movement['kind'], movement['currency'], movement['amount']),
                                 ('expense', currency, Decimal('10.25')))
                self.assertEqual(movement['date'].isoformat(), start)
                saved = next(r for r in self.request('GET', '/recurring-payments') if r['id'] == item['id'])
                self.assertEqual(saved['next_payment_date'], end)

    def test_reserved_and_insufficient_rejections_keep_due_date_and_rows(self):
        for currency in ('PEN', 'USD'):
            self.goal(currency)
            for amount in ('60.01', '100.01'):
                item = self.request('POST', '/recurring-payments', self.payload(currency=currency, amount=amount), 201)
                self.reject(f"/recurring-payments/{item['id']}/pay", {'date': '2026-10-20'}, 400)

    def test_pay_exact_spendable_preserves_reservation(self):
        self.goal()
        item = self.request('POST', '/recurring-payments', self.payload(amount='60.00'), 201)
        self.request('POST', f"/recurring-payments/{item['id']}/pay", {'date': '2026-10-20'})
        self.assertEqual(self.balances()[2], {'PEN': Decimal('0.00'), 'USD': Decimal('100.00')})
        self.assertEqual(self.balances()[1]['PEN'], Decimal('40.00'))

    def test_invalid_creation_and_payment_dates_leave_no_partial_writes(self):
        for change in [{'frequency': 'daily'}, {'next_payment_date': '2026-02-30'},
                       {'currency': 'EUR'}, {'amount': '0'}, {'amount': '-1'}, {'amount': '0.001'}]:
            with self.subTest(change=change):
                self.reject('/recurring-payments', self.payload(**change))
        item = self.request('POST', '/recurring-payments', self.payload(), 201)
        self.reject(f"/recurring-payments/{item['id']}/pay", {'date': '2026-02-30'})

    def test_missing_and_inactive_payments_reject_atomically(self):
        self.reject('/recurring-payments/999/pay', {'date': '2026-10-20'}, 404)
        item = self.request('POST', '/recurring-payments', self.payload(), 201)
        with self.sessions() as session:
            session.get(RecurringPayment, item['id']).active = 0
            session.commit()
        self.reject(f"/recurring-payments/{item['id']}/pay", {'date': '2026-10-20'}, 400)
