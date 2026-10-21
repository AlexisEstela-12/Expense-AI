"""Read-only financial queries with explicitly injected dependencies."""

from collections.abc import Callable, Mapping
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Literal
import unicodedata
from dateutil.tz import gettz

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Numeric, func, select
from sqlalchemy.orm import Session


BalanceQuery = Callable[[Session], Mapping[str, Decimal]]


def get_balances(
    session: Session,
    *,
    available_fn: BalanceQuery,
    reserved_savings_fn: BalanceQuery,
    spendable_balance_fn: BalanceQuery,
) -> dict[str, dict[str, str]]:
    """Return PEN and USD balances using the existing financial calculations.

    The caller provides the session and calculation functions. This module
    does not import the application, manage transactions, or close the session.
    Autoflush is temporarily disabled while the injected queries run.
    """
    with session.no_autoflush:
        balances = available_fn(session)
        reserved = reserved_savings_fn(session)
        spendable = spendable_balance_fn(session)

    return {
        name: {currency: format(amounts[currency], '.2f') for currency in ('PEN', 'USD')}
        for name, amounts in (
            ('balances', balances),
            ('reserved', reserved),
            ('spendable', spendable),
        )
    }


class SpendingSummaryParams(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')

    period: Literal['current_month', 'previous_month', 'specific_month']
    month: str | None = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    currency: Literal['PEN', 'USD', 'BOTH']

    @model_validator(mode='after')
    def validate_month(self):
        if self.period == 'specific_month':
            if self.month is None:
                raise ValueError('specific_month requiere month.')
            date.fromisoformat(self.month + '-01')
        elif self.month is not None:
            raise ValueError('month debe ser null para períodos relativos.')
        return self


def lima_today() -> date:
    # dateutil is already used by the backend and includes IANA zone data on
    # Windows, where the standard library may not have a system tz database.
    zone = gettz('America/Lima')
    if zone is None:
        raise RuntimeError('Zona horaria America/Lima no disponible.')
    return datetime.now(zone).date()


def resolve_spending_period(params: SpendingSummaryParams, as_of: date) -> tuple[date, date]:
    """Return inclusive start and exclusive end, never including future dates."""
    current_start = as_of.replace(day=1)
    if params.period == 'current_month':
        start = current_start
    elif params.period == 'previous_month':
        start = (current_start - timedelta(days=1)).replace(day=1)
    else:
        start = date.fromisoformat(params.month + '-01')
    if start > as_of:
        raise ValueError('No se admiten meses futuros.')
    if start == current_start:
        end = as_of + timedelta(days=1)
    else:
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, end


def spending_summary_statement(movement_model, start: date, end: date, currency: str):
    """Portable, parameterized aggregation; no database-specific date functions."""
    currencies = ('PEN', 'USD') if currency == 'BOTH' else (currency,)
    return (
        select(
            movement_model.currency,
            func.sum(movement_model.amount, type_=Numeric(38, 2)).label('spent'),
        )
        .where(
            movement_model.kind == 'expense',
            movement_model.exchange_id.is_(None),
            movement_model.date >= start,
            movement_model.date < end,
            movement_model.currency.in_(currencies),
        )
        .group_by(movement_model.currency)
    )


def get_spending_summary(
    session: Session,
    params: SpendingSummaryParams,
    *,
    movement_model,
    as_of: date | None = None,
) -> dict:
    """Sum gross recorded expenses in SQL, separately by requested currency.

    Reimbursements received are not subtracted. Exchange legs are excluded.
    The caller retains ownership of the session and its transaction.
    """
    as_of = lima_today() if as_of is None else as_of
    start, end = resolve_spending_period(params, as_of)
    currencies = ('PEN', 'USD') if params.currency == 'BOTH' else (params.currency,)
    totals = {currency: Decimal('0.00') for currency in currencies}
    statement = spending_summary_statement(movement_model, start, end, params.currency)
    with session.no_autoflush:
        for currency, amount in session.execute(statement):
            if not isinstance(amount, Decimal):
                raise TypeError('Se esperaba un agregado Decimal.')
            totals[currency] = amount
    return {
        'period': {
            'start_date': start.isoformat(),
            'end_date_exclusive': end.isoformat(),
            'as_of': as_of.isoformat(),
            'timezone': 'America/Lima',
        },
        'currency': params.currency,
        'totals': {currency: format(amount, '.2f') for currency, amount in totals.items()},
        'basis': 'gross_expenses_excluding_exchanges',
    }


class SpendingByCategoryParams(SpendingSummaryParams):
    """Strict filters for a ranking or a single category lookup."""

    category: str | None
    limit: int = Field(strict=True, ge=1, le=20)

    @model_validator(mode='after')
    def validate_category(self):
        if self.category is not None:
            if not self.category.strip():
                raise ValueError('Categoría inválida.')
            normalized = normalize_category(self.category)
            if not normalized or len(normalized) > 80:
                raise ValueError('Categoría inválida.')
            self.category = normalized
        return self


def normalize_category(value: str | None) -> str:
    """Normalize whitespace and casing, without removing accents or punctuation."""
    if value is None:
        return 'Sin categoría'
    normalized = ' '.join(value.split())
    return normalized if normalized else 'Sin categoría'


def _category_key(value: str) -> str:
    return unicodedata.normalize('NFC', normalize_category(value)).casefold()


def _category_search_key(value: str) -> str:
    decomposed = unicodedata.normalize('NFKD', _category_key(value))
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def spending_by_category_statement(movement_model, start: date, end: date, currency: str, dialect_name: str):
    """Aggregate stored categories and currencies, then normalize names in Python."""
    currencies = ('PEN', 'USD') if currency == 'BOTH' else (currency,)
    category_expression = movement_model.category
    return (
        select(
            category_expression.label('category'),
            movement_model.currency,
            func.sum(movement_model.amount, type_=Numeric(38, 2)).label('spent'),
        )
        .where(
            movement_model.kind == 'expense',
            movement_model.exchange_id.is_(None),
            movement_model.date >= start,
            movement_model.date < end,
            movement_model.currency.in_(currencies),
        )
        .group_by(category_expression, movement_model.currency)
    )


def get_spending_by_category(
    session: Session,
    params: SpendingByCategoryParams,
    *,
    movement_model,
    category_model,
    as_of: date | None = None,
) -> dict:
    """Return period expenses grouped by normalized category and kept per currency."""
    as_of = lima_today() if as_of is None else as_of
    start, end = resolve_spending_period(params, as_of)
    currencies = ('PEN', 'USD') if params.currency == 'BOTH' else (params.currency,)
    statement = spending_by_category_statement(
        movement_model, start, end, params.currency, session.bind.dialect.name
    )

    # Known labels include the catalogue and all historical expense movements.
    # Category has no FK/unique constraint on Movement.category, so avoid joins.
    with session.no_autoflush:
        aggregate_rows = session.execute(statement).all()
        historical_names = session.scalars(
            select(movement_model.category).where(movement_model.kind == 'expense').distinct()
        ).all()
        catalogue_names = session.scalars(
            select(category_model.name).where(category_model.kind == 'expense')
        ).all()

    totals: dict[tuple[str, str], Decimal] = {}
    labels: dict[str, set[str]] = {}
    for raw_name, row_currency, amount in aggregate_rows:
        if not isinstance(amount, Decimal):
            raise TypeError('Se esperaba un agregado Decimal.')
        display = normalize_category(raw_name)
        key = _category_key(display)
        labels.setdefault(key, set()).add(display)
        pair = (key, row_currency)
        totals[pair] = totals.get(pair, Decimal('0.00')) + amount
    known_names = [*historical_names, *catalogue_names]
    known_by_key: dict[str, set[str]] = {}
    for name in known_names:
        display = normalize_category(name)
        known_by_key.setdefault(_category_key(display), set()).add(display)

    status = 'ok'
    selected_key = None
    if params.category is not None:
        query = params.category
        exact = {key for key in known_by_key if key == _category_key(query)}
        matches = exact or {
            key for key, names in known_by_key.items()
            if _category_search_key(query) == _category_search_key(next(iter(names)))
        }
        if len(matches) > 1:
            status = 'ambiguous_category'
        elif not matches:
            status = 'category_not_found'
        else:
            selected_key = next(iter(matches))
            if not known_by_key[selected_key]:
                status = 'category_not_found'
            elif not any(key == selected_key for key, _ in totals):
                status = 'category_no_spending'

    period = {
        'start_date': start.isoformat(), 'end_date_exclusive': end.isoformat(),
        'as_of': as_of.isoformat(), 'timezone': 'America/Lima',
    }
    if status in ('category_not_found', 'ambiguous_category'):
        return {
            'period': period, 'currency': params.currency, 'category': params.category,
            'limit': params.limit, 'status': status, 'groups': {},
            'basis': 'gross_expenses_excluding_exchanges',
        }

    groups = {}
    for row_currency in currencies:
        rows = [(key, amount) for (key, currency_key), amount in totals.items()
                if currency_key == row_currency and (selected_key is None or key == selected_key)]
        rows.sort(key=lambda item: (-item[1], _category_key(min(labels[item[0]], key=lambda value: (value.casefold(), value)))))
        has_more = selected_key is None and len(rows) > params.limit
        rows = rows[:params.limit] if selected_key is None else rows
        categories = []
        for key, amount in rows:
            # Deterministic display among case/whitespace-equivalent spellings.
            display = min(labels[key], key=lambda value: (value.casefold(), value))
            categories.append({'category': display, 'amount': format(amount, '.2f')})
        groups[row_currency] = {'categories': categories, 'has_more': has_more}
    return {
        'period': period, 'currency': params.currency, 'category': params.category,
        'limit': params.limit, 'status': status, 'groups': groups,
        'basis': 'gross_expenses_excluding_exchanges',
    }


class BudgetStatusParams(SpendingSummaryParams):
    """Monthly budget lookup, with the same strict period and currency rules."""

    category: str | None

    @model_validator(mode='after')
    def validate_category(self):
        if self.category is not None and (not self.category.strip() or len(self.category) > 80):
            raise ValueError('Categoría inválida.')
        return self


def budget_spent_statement(movement_model, start: date, end: date, currency: str, category: str):
    """Use the same database equality semantics as GET /budgets."""
    return select(func.sum(movement_model.amount, type_=Numeric(38, 2))).where(
        movement_model.kind == 'expense',
        movement_model.exchange_id.is_(None),
        movement_model.date >= start,
        movement_model.date < end,
        movement_model.currency == currency,
        movement_model.category == category,
    )


def get_budget_status(
    session: Session,
    params: BudgetStatusParams,
    *,
    budget_model,
    movement_model,
    as_of: date | None = None,
) -> dict:
    """Read each stored budget independently; calculate exact status with Decimal."""
    as_of = lima_today() if as_of is None else as_of
    start, end = resolve_spending_period(params, as_of)
    currencies = ('PEN', 'USD') if params.currency == 'BOTH' else (params.currency,)
    month = start.strftime('%Y-%m')
    budget_query = select(budget_model).where(
        budget_model.month == month,
        budget_model.currency.in_(currencies),
    ).order_by(budget_model.id)
    if params.category is not None:
        budget_query = budget_query.where(budget_model.category == params.category)

    groups = {currency: [] for currency in currencies}
    spent_cache: dict[tuple[str, str], Decimal] = {}
    with session.no_autoflush:
        budgets = session.scalars(budget_query).all()
        for budget in budgets:
            key = (budget.currency, budget.category)
            if key not in spent_cache:
                spent = session.scalar(budget_spent_statement(
                    movement_model, start, end, budget.currency, budget.category,
                ))
                if spent is not None and not isinstance(spent, Decimal):
                    raise TypeError('Se esperaba un agregado Decimal.')
                spent_cache[key] = spent if spent is not None else Decimal('0.00')
            limit = budget.limit_amount
            if not isinstance(limit, Decimal) or limit <= 0:
                raise ValueError('Límite de presupuesto inválido.')
            spent = spent_cache[key]
            remaining = max(limit - spent, Decimal('0.00'))
            overrun = max(spent - limit, Decimal('0.00'))
            status = 'exceeded' if spent > limit else 'exhausted' if spent == limit else 'within_budget'
            groups[budget.currency].append({
                'id': budget.id, 'category': budget.category,
                'limit': format(limit, '.2f'), 'spent': format(spent, '.2f'),
                'remaining': format(remaining, '.2f'), 'overrun': format(overrun, '.2f'),
                'status': status,
            })
    return {
        'period': {
            'start_date': start.isoformat(), 'end_date_exclusive': end.isoformat(),
            'as_of': as_of.isoformat(), 'timezone': 'America/Lima',
        },
        'currency': params.currency, 'category': params.category,
        'status': 'ok' if budgets else 'no_budget', 'groups': groups,
        'basis': 'gross_expenses_excluding_exchanges',
    }
