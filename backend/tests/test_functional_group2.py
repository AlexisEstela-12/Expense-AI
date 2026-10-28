"""Group 2: currency exchanges and budgets through isolated HTTP contracts."""
from decimal import Decimal
from datetime import date
from sqlalchemy import select
from api.routers import exchanges, budgets, savings_goals
from db.models import Exchange, Movement
from functional_support import FunctionalCase


class Group2Test(FunctionalCase):
    routers = (exchanges.create_router, budgets.create_router, savings_goals.create_router)

    def exchange(self, currency, out='37.50', incoming='10.00'):
        return {'date': '2026-10-20', 'from_currency': currency,
                'amount_out': out, 'amount_in': incoming}

    def test_both_conversion_directions_link_legs_and_exact_balances(self):
        for currency, out, incoming in [('PEN', '37.50', '10.00'), ('USD', '10.00', '37.50')]:
            with self.subTest(currency=currency):
                before = self.balances()[0]
                result = self.request('POST', '/exchanges', self.exchange(currency, out, incoming), 201)
                dest = 'USD' if currency == 'PEN' else 'PEN'
                before[currency] -= Decimal(out)
                before[dest] += Decimal(incoming)
                self.assertEqual(self.balances()[0], before)
                self.assertEqual(result['balances'], {k: str(v) for k, v in before.items()})
                self.assertEqual(Decimal(result['rate']), Decimal('3.75'))
                with self.sessions() as session:
                    saved = session.get(Exchange, result['id'])
                    self.assertEqual(saved.rate, Decimal('3.750000'))
                    legs = session.scalars(select(Movement).where(Movement.exchange_id == saved.id)).all()
                    self.assertEqual({(m.kind, m.currency, m.amount) for m in legs}, {
                        ('expense', currency, Decimal(out)), ('income', dest, Decimal(incoming))})
                    self.assertEqual(len(legs), 2)

    def test_reserved_money_and_insufficient_currency_reject_atomically(self):
        for currency in ('PEN', 'USD'):
            self.goal(currency)
            self.reject('/exchanges', self.exchange(currency, '60.01'), 400)
            self.reject('/exchanges', self.exchange(currency, '100.01'), 400)
        self.assertEqual(self.balances()[1], {'PEN': Decimal('40'), 'USD': Decimal('40')})

    def test_spendable_boundary_and_fractional_rate(self):
        self.goal()
        result = self.request('POST', '/exchanges', self.exchange('PEN', '60.00', '17.00'), 201)
        self.assertEqual(result['rate'], str(Decimal('60') / Decimal('17')))
        self.assertEqual(self.balances()[2]['PEN'], Decimal('0.00'))
        with self.sessions() as session:
            self.assertEqual(session.get(Exchange, result['id']).rate, Decimal('3.529412'))

    def test_invalid_exchange_payloads_leave_all_tables_unchanged(self):
        for change in [{'date': '2026-02-30'}, {'from_currency': 'EUR'},
                       {'amount_out': '0'}, {'amount_in': '-1'},
                       {'amount_out': '0.001'}, {'amount_in': 'NaN'}]:
            with self.subTest(change=change):
                self.reject('/exchanges', self.exchange('PEN') | change)

    def test_budgets_currencies_months_duplicates_and_no_movements(self):
        before = self.snapshot()['movements']
        ids = []
        for month, currency in [('2026-10', 'PEN'), ('2026-10', 'USD'),
                                ('2026-09', 'PEN'), ('2026-10', 'PEN')]:
            ids.append(self.request('POST', '/budgets', {
                'month': month, 'currency': currency, 'category': 'Ficticio',
                'limit_amount': '10.00'}, 201)['id'])
        self.assertEqual(len(set(ids)), 4)  # Existing contract accepts duplicates.
        self.assertEqual(self.snapshot()['movements'], before)
        with self.sessions() as session:
            for currency, amount, day in [('PEN', '0.10', date(2026, 10, 1)),
                                           ('PEN', '0.20', date(2026, 10, 31)),
                                           ('USD', '1.25', date(2026, 10, 2)),
                                           ('PEN', '2.50', date(2026, 9, 30))]:
                session.add(Movement(date=day, kind='expense', currency=currency,
                                     amount=Decimal(amount), category='Ficticio'))
            session.commit()
        rows = {r['id']: r for r in self.request('GET', '/budgets')}
        self.assertEqual([Decimal(rows[i]['spent']) for i in ids],
                         list(map(Decimal, ['0.30', '1.25', '2.50', '0.30'])))

    def test_invalid_budgets_reject_atomically(self):
        base = {'month': '2026-10', 'currency': 'PEN', 'category': 'Ficticio', 'limit_amount': '10'}
        for change in [{'month': '2026-13'}, {'month': '2026-1'}, {'currency': 'EUR'},
                       {'limit_amount': '0'}, {'limit_amount': '-1'}, {'limit_amount': '1.001'}]:
            with self.subTest(change=change):
                self.reject('/budgets', base | change)
