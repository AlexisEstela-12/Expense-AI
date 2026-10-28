from datetime import date, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
if __package__:
    from .security.router import create_router as create_auth_router
    from .api.routers.health import router as health_router
    from .api.routers.categories import create_router as create_categories_router
    from .api.routers.budgets import create_router as create_budgets_router
    from .api.routers.reimbursements import create_router as create_reimbursements_router
    from .api.routers.movements import create_router as create_movements_router
    from .api.routers.exchanges import create_router as create_exchanges_router
    from .api.routers.recurring_payments import create_router as create_recurring_payments_router
    from .api.routers.financial_summary import create_router as create_financial_summary_router
    from .api.routers.chat import create_router as create_chat_router
    from .api.routers.notifications import create_router as create_notifications_router
    from .api.routers.savings_goals import create_router as create_savings_goals_router
    from .schemas.common import Money
    from .db.base import Base
    from .db.models import Movement, Exchange, Budget, Category, Reimbursement, RecurringPayment, SavingsGoal, SavingsContribution
    from .db.session import connection_string, DB_URL, engine, SessionLocal
    from .chat.balances import BalanceChatRequest, BalanceChatResponse, explain_balances, is_balance_question
    from .services.balances import available, reserved_savings, spendable_balance, ensure_spendable_balance, ensure_balance
    from .services.financial_queries import get_balances
    from .chat.tool_balances import ToolBalanceRequest, ToolBalanceResponse, run_tool_balances
    from .chat.financial_tools import FinancialToolsRequest, FinancialToolsResponse, run_financial_tools
    from .services.financial_queries import get_spending_summary, get_spending_by_category, get_budget_status
else:
    from security.router import create_router as create_auth_router
    from api.routers.health import router as health_router
    from api.routers.categories import create_router as create_categories_router
    from api.routers.budgets import create_router as create_budgets_router
    from api.routers.reimbursements import create_router as create_reimbursements_router
    from api.routers.movements import create_router as create_movements_router
    from api.routers.exchanges import create_router as create_exchanges_router
    from api.routers.recurring_payments import create_router as create_recurring_payments_router
    from api.routers.financial_summary import create_router as create_financial_summary_router
    from api.routers.chat import create_router as create_chat_router
    from api.routers.notifications import create_router as create_notifications_router
    from api.routers.savings_goals import create_router as create_savings_goals_router
    from schemas.common import Money
    from db.base import Base
    from db.models import Movement, Exchange, Budget, Category, Reimbursement, RecurringPayment, SavingsGoal, SavingsContribution
    from db.session import connection_string, DB_URL, engine, SessionLocal
    from chat.balances import BalanceChatRequest, BalanceChatResponse, explain_balances, is_balance_question
    from services.balances import available, reserved_savings, spendable_balance, ensure_spendable_balance, ensure_balance
    from services.financial_queries import get_balances
    from chat.tool_balances import ToolBalanceRequest, ToolBalanceResponse, run_tool_balances
    from chat.financial_tools import FinancialToolsRequest, FinancialToolsResponse, run_financial_tools
    from services.financial_queries import get_spending_summary, get_spending_by_category, get_budget_status

app = FastAPI(title='Expense AI API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])
app.include_router(health_router)

def db():
    with SessionLocal() as session: yield session
DEFAULT_CATEGORIES = {
    'income': [
        'Sueldo',
        'Comisiones',
        'Bonos',
        'Ingresos adicionales',
        'Otros ingresos'
    ],
    'expense': [
        'Alimentación',
        'Transporte',
        'Vivienda',
        'Servicios',
        'Compras',
        'Salud',
        'Entretenimiento',
        'Educación',
        'Viajes',
        'Suscripciones',
        'Gastos laborales',
        'Otros gastos'
    ],
    'reimbursement': [
        'Reembolso laboral'
    ]
}
app.include_router(create_financial_summary_router(db))

app.include_router(create_chat_router(db))

app.include_router(create_movements_router(db))
app.include_router(create_exchanges_router(db))
app.include_router(create_budgets_router(db))
app.include_router(create_reimbursements_router(db))

app.include_router(create_recurring_payments_router(db))

app.include_router(create_categories_router(db))

app.include_router(create_notifications_router(db))

app.include_router(create_savings_goals_router(db))
app.include_router(create_auth_router(db))
