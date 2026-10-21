"""Offline checks for the SQLAlchemy mappings extracted from main.py."""

import sys
import unittest

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.dialects import mssql

from db.base import Base
from db.models import (
    Budget, Category, Exchange, Movement, Reimbursement,
    RecurringPayment, SavingsContribution, SavingsGoal,
)


class ModelMetadataTest(unittest.TestCase):
    def test_models_register_without_importing_application_or_session(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        expected = {
            'movements': Movement,
            'exchanges': Exchange,
            'budgets': Budget,
            'categories': Category,
            'reimbursements': Reimbursement,
            'recurring_payments': RecurringPayment,
            'savings_goals': SavingsGoal,
            'savings_contributions': SavingsContribution,
        }
        self.assertEqual(set(Base.metadata.tables), set(expected))
        for table_name, model in expected.items():
            with self.subTest(table=table_name):
                self.assertIs(model.__table__, Base.metadata.tables[table_name])

    def test_columns_and_types_match_original_mapping(self):
        expected = {
            'movements': ['id', 'date', 'kind', 'currency', 'amount', 'category', 'description', 'exchange_id'],
            'exchanges': ['id', 'date', 'from_currency', 'amount_out', 'amount_in', 'rate'],
            'budgets': ['id', 'month', 'category', 'currency', 'limit_amount'],
            'categories': ['id', 'name', 'kind'],
            'reimbursements': ['id', 'date', 'currency', 'amount', 'category', 'description', 'status', 'reimbursed_date', 'movement_id', 'reimbursement_movement_id'],
            'recurring_payments': ['id', 'name', 'category', 'currency', 'amount', 'frequency', 'next_payment_date', 'active'],
            'savings_goals': ['id', 'name', 'currency', 'target_amount', 'target_date', 'active'],
            'savings_contributions': ['id', 'goal_id', 'date', 'amount'],
        }
        for name, columns in expected.items():
            with self.subTest(table=name):
                self.assertEqual(list(Base.metadata.tables[name].columns.keys()), columns)
        self.assertIsInstance(Movement.__table__.c.amount.type, Numeric)
        self.assertEqual((Movement.__table__.c.amount.type.precision, Movement.__table__.c.amount.type.scale), (16, 2))
        self.assertIsInstance(Exchange.__table__.c.rate.type, Numeric)
        self.assertEqual((Exchange.__table__.c.rate.type.precision, Exchange.__table__.c.rate.type.scale), (16, 6))
        self.assertIsInstance(Movement.__table__.c.category.type, String)
        self.assertEqual(Movement.__table__.c.category.type.length, 80)
        self.assertIsInstance(Movement.__table__.c.date.type, Date)
        self.assertIsInstance(Movement.__table__.c.id.type, Integer)
        self.assertEqual(
            {str(fk.target_fullname) for fk in Reimbursement.__table__.foreign_keys},
            {'movements.id'},
        )
        self.assertEqual(
            {str(fk.target_fullname) for fk in Base.metadata.tables['savings_contributions'].foreign_keys},
            {'savings_goals.id'},
        )

    def test_sql_server_ddl_compiles_without_connection(self):
        from sqlalchemy.schema import CreateTable

        for table in Base.metadata.sorted_tables:
            with self.subTest(table=table.name):
                ddl = str(CreateTable(table).compile(dialect=mssql.dialect()))
                self.assertIn('CREATE TABLE', ddl)


if __name__ == '__main__':
    unittest.main()
