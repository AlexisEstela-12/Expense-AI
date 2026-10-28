"""Group 5: savings lifecycle, currency reserves and category contracts."""
from decimal import Decimal
from api.routers import savings_goals, categories
from functional_support import FunctionalCase


class Group5Test(FunctionalCase):
    routers = (savings_goals.create_router, categories.create_router)

    def test_goals_pen_usd_contributions_reserve_without_movements(self):
        before = self.snapshot()['movements']
        for currency in ('PEN', 'USD'):
            goal_id = self.goal(currency, '0.10')
            contribution = self.request('POST', f'/savings-goals/{goal_id}/contributions', {
                'date': '2026-10-21', 'amount': '0.20'}, 201)
            self.assertEqual(Decimal(contribution['saved_amount']), Decimal('0.30'))
            self.assertEqual(contribution['currency'], currency)
        self.assertEqual(self.snapshot()['movements'], before)
        total, reserved, spendable = self.balances()
        self.assertEqual(total, {'PEN': Decimal('100'), 'USD': Decimal('100')})
        self.assertEqual(reserved, {'PEN': Decimal('0.30'), 'USD': Decimal('0.30')})
        self.assertEqual(spendable, {'PEN': Decimal('99.70'), 'USD': Decimal('99.70')})
        self.assertEqual(len(self.request('GET', '/savings-goals')), 2)

    def test_cancel_releases_only_own_currency_without_movement(self):
        pen = self.goal('PEN')
        usd = self.goal('USD', '25.00')
        before = self.snapshot()['movements']
        response = self.request('POST', f'/savings-goals/{pen}/cancel')
        self.assertEqual(response['status'], 'cancelled')
        self.assertEqual(Decimal(response['released_amount']), Decimal('40.00'))
        self.assertEqual(self.snapshot()['movements'], before)
        self.assertEqual(self.balances()[2], {'PEN': Decimal('100'), 'USD': Decimal('75')})
        self.assertEqual([r['id'] for r in self.request('GET', '/savings-goals')], [usd])
        self.reject(f'/savings-goals/{pen}/cancel', None, 400)
        self.reject(f'/savings-goals/{pen}/use', None, 400)
        self.reject(f'/savings-goals/{pen}/contributions', {'date': '2026-10-20', 'amount': '1'}, 400)

    def test_use_savings_expense_closes_goal_once_and_preserves_other_reserves(self):
        for currency in ('PEN', 'USD'):
            with self.subTest(currency=currency):
                goal = self.goal(currency, '20.25')
                other = self.goal(currency, '10.00')
                original = self.balances()[0]
                result = self.request('POST', f'/savings-goals/{goal}/use')
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(Decimal(result['used_amount']), Decimal('20.25'))
                original[currency] -= Decimal('20.25')
                self.assertEqual(self.balances()[0], original)
                self.assertEqual(self.balances()[1][currency], Decimal('10.00'))
                row = next(r._mapping for r in self.snapshot()['movements'] if r._mapping['id'] == result['movement_id'])
                self.assertEqual((row['kind'], row['currency'], row['amount']),
                                 ('expense', currency, Decimal('20.25')))
                self.reject(f'/savings-goals/{goal}/use', None, 400)
                self.assertIn(other, [r['id'] for r in self.request('GET', '/savings-goals')])

    def test_insufficient_funds_and_target_overflow_reject_atomically(self):
        for currency in ('PEN', 'USD'):
            goal = self.goal(currency, '40.00')
            second = self.request('POST', '/savings-goals', {
                'name': 'Segunda ficticia', 'currency': currency, 'target_amount': '200'}, 201)['id']
            self.reject(f'/savings-goals/{second}/contributions', {'date': '2026-10-20', 'amount': '60.01'}, 400)
            # Enough spendable funds, but more than the remaining target.
            small = self.request('POST', '/savings-goals', {
                'name': 'Pequena ficticia', 'currency': currency, 'target_amount': '1'}, 201)['id']
            self.reject(f'/savings-goals/{small}/contributions', {'date': '2026-10-20', 'amount': '1.01'}, 400)
            self.request('POST', f'/savings-goals/{goal}/contributions', {
                'date': '2026-10-20', 'amount': '60.00'}, 201)
            self.assertEqual(self.balances()[2][currency], Decimal('0.00'))

    def test_missing_and_empty_goals_reject_without_writing(self):
        for action in ('cancel', 'use'):
            self.reject(f'/savings-goals/999/{action}', None, 404)
        self.reject('/savings-goals/999/contributions', {'date': '2026-10-20', 'amount': '1'}, 404)
        goal = self.request('POST', '/savings-goals', {
            'name': 'Vacia ficticia', 'currency': 'USD', 'target_amount': '10'}, 201)['id']
        self.reject(f'/savings-goals/{goal}/use', None, 400)

    def test_invalid_goal_and_contribution_dates_amounts(self):
        base = {'name': 'Ficticia', 'currency': 'PEN', 'target_amount': '10'}
        for change in [{'currency': 'EUR'}, {'target_date': '2026-02-30'},
                       {'target_amount': '0'}, {'target_amount': '-1'}, {'target_amount': '1.001'}]:
            with self.subTest(change=change):
                self.reject('/savings-goals', base | change)
        goal = self.request('POST', '/savings-goals', base, 201)['id']
        for change in [{'date': '2026-02-30'}, {'amount': '0'}, {'amount': '-1'}, {'amount': '0.001'}]:
            with self.subTest(change=change):
                self.reject(f'/savings-goals/{goal}/contributions', {'date': '2026-10-20', 'amount': '1'} | change)

    def test_categories_trim_duplicate_conflict_and_kind_separation(self):
        before = self.snapshot()['movements']
        expense = self.request('POST', '/categories', {'name': '  Ficticia  ', 'kind': 'expense'}, 201)
        self.assertEqual(expense['name'], 'Ficticia')
        self.reject('/categories', {'name': 'Ficticia', 'kind': 'expense'}, 409)
        income = self.request('POST', '/categories', {'name': 'Ficticia', 'kind': 'income'}, 201)
        self.assertNotEqual(expense['id'], income['id'])
        self.assertEqual(len(self.request('GET', '/categories')), 2)
        self.assertEqual(self.snapshot()['movements'], before)

    def test_invalid_categories_preserve_database(self):
        self.reject('/categories', {'name': '   ', 'kind': 'expense'}, 400)
        self.reject('/categories', {'name': '', 'kind': 'expense'})
        self.reject('/categories', {'name': 'Ficticia', 'kind': 'invalid'})
