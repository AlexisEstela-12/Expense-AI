from datetime import date, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
if __package__:
    from .api.routers.health import router as health_router
    from .api.routers.categories import create_router as create_categories_router
    from .api.routers.budgets import create_router as create_budgets_router
    from .api.routers.reimbursements import create_router as create_reimbursements_router
    from .api.routers.movements import create_router as create_movements_router
    from .api.routers.exchanges import create_router as create_exchanges_router
    from .api.routers.recurring_payments import create_router as create_recurring_payments_router
    from .api.routers.financial_summary import create_router as create_financial_summary_router
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
    from api.routers.health import router as health_router
    from api.routers.categories import create_router as create_categories_router
    from api.routers.budgets import create_router as create_budgets_router
    from api.routers.reimbursements import create_router as create_reimbursements_router
    from api.routers.movements import create_router as create_movements_router
    from api.routers.exchanges import create_router as create_exchanges_router
    from api.routers.recurring_payments import create_router as create_recurring_payments_router
    from api.routers.financial_summary import create_router as create_financial_summary_router
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
Base.metadata.create_all(engine)

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

@app.post('/api/chat/balances', response_model=BalanceChatResponse)
def chat_balances(
    payload: BalanceChatRequest,
    request: Request,
    session: Session = Depends(db)
):
    # Local development only: this is not authentication. Do not publish or
    # expose through a proxy/tunnel; bind Uvicorn to 127.0.0.1.
    if (
        request.client is None
        or request.client.host not in ('127.0.0.1', '::1')
        or any(header in request.headers for header in (
            'forwarded', 'x-forwarded-for', 'x-real-ip'
        ))
        or request.url.hostname not in ('localhost', '127.0.0.1', '::1')
    ):
        raise HTTPException(status_code=403, detail='Chat disponible solo en entorno local.')

    origin = request.headers.get('origin')
    if origin is not None and origin not in (
        'http://localhost:5173', 'http://127.0.0.1:5173',
        'http://127.0.0.1:8000', 'http://localhost:8000'
    ):
        raise HTTPException(status_code=403, detail='Origen no permitido para el chat local.')

    if not is_balance_question(payload.message):
        return BalanceChatResponse(
            answer='Por ahora solo puedo consultar saldos. Pregunta: ¿Cuánto dinero tengo disponible en soles y dólares?',
            financial_data=None,
            explanation_source='unsupported',
        )

    try:
        financial_data = get_balances(
            session,
            available_fn=available,
            reserved_savings_fn=reserved_savings,
            spendable_balance_fn=spendable_balance,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail='No se pudieron consultar los saldos financieros.'
        ) from None

    return explain_balances(financial_data)

@app.post('/api/chat/tool-balances', response_model=ToolBalanceResponse)
def chat_tool_balances(
    payload: ToolBalanceRequest,
    request: Request,
    session: Session = Depends(db)
):
    # Local-only development endpoint; not a substitute for authentication.
    if (
        request.client is None
        or request.client.host not in ('127.0.0.1', '::1')
        or any(header in request.headers for header in (
            'forwarded', 'x-forwarded-for', 'x-real-ip'
        ))
        or request.url.hostname not in ('localhost', '127.0.0.1', '::1')
    ):
        raise HTTPException(status_code=403, detail='Chat disponible solo en entorno local.')
    origin = request.headers.get('origin')
    if origin is not None and origin not in (
        'http://localhost:5173', 'http://127.0.0.1:5173',
        'http://127.0.0.1:8000', 'http://localhost:8000'
    ):
        raise HTTPException(status_code=403, detail='Origen no permitido para el chat local.')

    def execute_balances():
        return get_balances(
            session,
            available_fn=available,
            reserved_savings_fn=reserved_savings,
            spendable_balance_fn=spendable_balance,
        )

    return run_tool_balances(payload.message, execute_balances)

@app.post('/api/chat/tools', response_model=FinancialToolsResponse)
def chat_financial_tools(
    payload: FinancialToolsRequest,
    request: Request,
    session: Session = Depends(db)
):
    # Development on loopback only. Do not publish; this is not authentication.
    if (
        request.client is None
        or request.client.host not in ('127.0.0.1', '::1')
        or any(header in request.headers for header in (
            'forwarded', 'x-forwarded-for', 'x-real-ip'
        ))
        or request.url.hostname not in ('localhost', '127.0.0.1', '::1')
    ):
        raise HTTPException(status_code=403, detail='Chat disponible solo en entorno local.')
    origin = request.headers.get('origin')
    if origin is not None and origin not in (
        'http://localhost:5173', 'http://127.0.0.1:5173',
        'http://127.0.0.1:8000', 'http://localhost:8000'
    ):
        raise HTTPException(status_code=403, detail='Origen no permitido para el chat local.')

    def execute_balances():
        return get_balances(
            session, available_fn=available,
            reserved_savings_fn=reserved_savings,
            spendable_balance_fn=spendable_balance,
        )

    def execute_spending(params, as_of):
        return get_spending_summary(session, params, movement_model=Movement, as_of=as_of)

    def execute_spending_by_category(params, as_of):
        return get_spending_by_category(
            session, params, movement_model=Movement, category_model=Category, as_of=as_of
        )

    def execute_budget_status(params, as_of):
        return get_budget_status(
            session, params, budget_model=Budget, movement_model=Movement, as_of=as_of
        )

    return run_financial_tools(
        payload.message, execute_balances, execute_spending, execute_spending_by_category,
        execute_budget_status,
    )

app.include_router(create_movements_router(db))
app.include_router(create_exchanges_router(db))
app.include_router(create_budgets_router(db))
app.include_router(create_reimbursements_router(db))

app.include_router(create_recurring_payments_router(db))

app.include_router(create_categories_router(db))

app.include_router(create_notifications_router(db))

app.include_router(create_savings_goals_router(db))
