"""One-shot, read-only diagnosis. Run explicitly with --run; never import main.py."""

import json
import logging
import os
import re
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import Column, Date, Integer, MetaData, Numeric, String, Table, create_engine, func, select, text
from sqlalchemy.exc import DBAPIError

from chat.financial_tools import _aggregate_only
from services.financial_queries import (
    SpendingByCategoryParams,
    get_spending_by_category,
    lima_today,
    resolve_spending_period,
    spending_by_category_statement,
)


metadata = MetaData()
movement_table = Table(
    'movements', metadata,
    Column('date', Date), Column('kind', String(24)),
    Column('currency', String(3)), Column('amount', Numeric(16, 2)),
    Column('category', String(80)), Column('exchange_id', Integer),
)
category_table = Table(
    'categories', metadata, Column('name', String(80)), Column('kind', String(24)),
)
Movement = SimpleNamespace(**{name: movement_table.c[name] for name in (
    'date', 'kind', 'currency', 'amount', 'category', 'exchange_id',
)})
Category = SimpleNamespace(name=category_table.c.name, kind=category_table.c.kind)


def report(stage, status, error=None):
    allowed = {
        'ProgrammingError', 'OperationalError', 'DataError', 'DatabaseError',
        'InterfaceError', 'IntegrityError', 'CompileError', 'InvalidRequestError',
        'ValueError', 'TypeError', 'KeyError', 'AttributeError', 'RuntimeError',
    }
    error_class = type(error).__name__ if error is not None else None
    if error_class not in allowed:
        error_class = 'OtherError' if error is not None else None
    sqlstate = None
    if isinstance(error, DBAPIError):
        args = getattr(error.orig, 'args', ())
        if args and isinstance(args[0], str) and re.fullmatch(r'[A-Z0-9]{5}', args[0]):
            sqlstate = args[0]
    print(json.dumps({
        'stage': stage, 'status': status,
        'exception_class': error_class, 'sqlstate': sqlstate,
    }))


def make_engine():
    # Same driver and connection settings as main.py. Never display these values.
    load_dotenv(Path(__file__).with_name('.env'), override=False)
    connection_string = (
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f"SERVER=tcp:{os.environ['DB_SERVER']},1433;"
        f"DATABASE={os.environ['DB_NAME']};"
        f"UID={os.environ['DB_USER']};"
        f"PWD={os.environ['DB_PASSWORD']};"
        'Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    )
    return create_engine(
        'mssql+pyodbc:///?odbc_connect=' + quote_plus(connection_string),
        echo=False, hide_parameters=True, pool_pre_ping=False,
    )


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class ReplaySession:
    """Run the real Python processing against already fetched aggregates."""

    def __init__(self, engine, aggregates, historical, catalogue):
        self.bind = engine
        self.aggregates = aggregates
        self.names = iter((historical, catalogue))
        self.aggregate_used = False

    @property
    def no_autoflush(self):
        return nullcontext()

    def execute(self, _statement):
        if self.aggregate_used:
            raise RuntimeError('Unexpected query')
        self.aggregate_used = True
        return Rows(self.aggregates)

    def scalars(self, _statement):
        return Rows(next(self.names))


def main():
    if sys.argv[1:] != ['--run']:
        report('invocation', 'error', ValueError())
        return 2
    logging.disable(logging.CRITICAL)
    engine = None
    try:
        params = SpendingByCategoryParams(
            period='current_month', month=None, currency='BOTH', category=None, limit=3,
        )
        as_of = lima_today()
        start, end = resolve_spending_period(params, as_of)
        currencies = ('PEN', 'USD') if params.currency == 'BOTH' else (params.currency,)
        filters = (
            Movement.kind == 'expense',
            Movement.exchange_id.is_(None),
            Movement.date >= start,
            Movement.date < end,
            Movement.currency.in_(currencies),
        )
        spent = func.sum(Movement.amount, type_=Numeric(38, 2))
        minimal_sum = select(spent).where(*filters)
        grouped_currency = (
            select(Movement.currency, spent)
            .where(*filters)
            .group_by(Movement.currency)
        )
        grouped_category = (
            select(Movement.category, spent)
            .where(*filters)
            .group_by(Movement.category)
        )
        grouped_category_currency = (
            select(Movement.category, Movement.currency, spent)
            .where(*filters)
            .group_by(Movement.category, Movement.currency)
        )
        coalesced_category = func.coalesce(Movement.category, '')
        grouped_coalesce_currency = (
            select(coalesced_category, Movement.currency, spent)
            .where(*filters)
            .group_by(coalesced_category, Movement.currency)
        )
        grouped_without_collate = spending_by_category_statement(
            Movement, start, end, params.currency, 'diagnostic_without_collate',
        )
        grouped_with_collate = spending_by_category_statement(
            Movement, start, end, params.currency, 'mssql',
        )
        engine = make_engine()
        with engine.connect() as connection:
            try:
                available = connection.execute(text(
                    "SELECT CASE WHEN EXISTS (SELECT 1 FROM sys.fn_helpcollations() "
                    "WHERE name = 'Latin1_General_100_BIN2') THEN 1 ELSE 0 END"
                )).scalar_one() == 1
                report('collation_check', 'ok' if available else 'error')
                if not available:
                    return 1
            except Exception as error:
                report('collation_check', 'error', error)
                return 1

            try:
                connection.execute(minimal_sum).scalar_one()
                report('minimal_sum', 'ok')
            except Exception as error:
                report('minimal_sum', 'error', error)
                return 1

            progressive_statements = (
                ('group_currency', grouped_currency),
                ('group_category', grouped_category),
                ('group_category_currency', grouped_category_currency),
                ('group_coalesce_currency', grouped_coalesce_currency),
                ('generated_without_collate', grouped_without_collate),
            )
            for stage, statement in progressive_statements:
                try:
                    connection.execute(statement).all()
                    report(stage, 'ok')
                except Exception as error:
                    report(stage, 'error', error)
                    return 1

            try:
                aggregate_rows = connection.execute(grouped_with_collate).all()
                report('generated_with_collate', 'ok')
            except Exception as error:
                report('generated_with_collate', 'error', error)
                return 1

            try:
                historical_rows = connection.execute(
                    select(Movement.category).where(
                        Movement.kind == 'expense', Movement.category.is_not(None),
                    ).distinct()
                ).all()
                report('historical_names', 'ok')
            except Exception as error:
                report('historical_names', 'error', error)
                return 1

            try:
                catalogue_rows = connection.execute(
                    select(Category.name).where(Category.kind == 'expense')
                ).all()
                report('catalogue', 'ok')
            except Exception as error:
                report('catalogue', 'error', error)
                return 1
        try:
            replay = ReplaySession(engine, aggregate_rows,
                                   [row[0] for row in historical_rows],
                                   [row[0] for row in catalogue_rows])
            result = get_spending_by_category(
                replay, params, movement_model=Movement,
                category_model=Category, as_of=as_of,
            )
            report('processing', 'ok')
        except Exception as error:
            report('processing', 'error', error)
            return 1
        try:
            _aggregate_only('get_spending_by_category', result)
            report('financial_data', 'ok')
        except Exception as error:
            report('financial_data', 'error', error)
            return 1
        return 0
    except Exception as error:
        report('connection_or_setup', 'error', error)
        return 1
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(main())
