from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

if __package__.startswith('backend.'):
    from ...security.dependencies import create_authentication_dependency
    from ...db.models import Movement, Category, Budget
    from ...chat.balances import BalanceChatRequest, BalanceChatResponse, explain_balances, is_balance_question
    from ...services.balances import available, reserved_savings, spendable_balance
    from ...services.financial_queries import get_balances, get_spending_summary, get_spending_by_category, get_budget_status
    from ...chat.tool_balances import ToolBalanceRequest, ToolBalanceResponse, run_tool_balances
    from ...chat.financial_tools import FinancialToolsRequest, FinancialToolsResponse, run_financial_tools
else:
    from security.dependencies import create_authentication_dependency
    from db.models import Movement, Category, Budget
    from chat.balances import BalanceChatRequest, BalanceChatResponse, explain_balances, is_balance_question
    from services.balances import available, reserved_savings, spendable_balance
    from services.financial_queries import get_balances, get_spending_summary, get_spending_by_category, get_budget_status
    from chat.tool_balances import ToolBalanceRequest, ToolBalanceResponse, run_tool_balances
    from chat.financial_tools import FinancialToolsRequest, FinancialToolsResponse, run_financial_tools


def create_router(db, *, authentication=None):
    # A standalone chat router is also protected; production injects the same
    # central dependency used by all financial routes.
    authentication = authentication or create_authentication_dependency(db)
    router = APIRouter(dependencies=[Depends(authentication)])
    @router.post('/api/chat/balances', response_model=BalanceChatResponse)
    def chat_balances(
        payload: BalanceChatRequest,
        request: Request,
        session: Session = Depends(db)
    ):
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

    @router.post('/api/chat/tool-balances', response_model=ToolBalanceResponse)
    def chat_tool_balances(
        payload: ToolBalanceRequest,
        request: Request,
        session: Session = Depends(db)
    ):
        def execute_balances():
            return get_balances(
                session,
                available_fn=available,
                reserved_savings_fn=reserved_savings,
                spendable_balance_fn=spendable_balance,
            )

        return run_tool_balances(payload.message, execute_balances)

    @router.post('/api/chat/tools', response_model=FinancialToolsResponse)
    def chat_financial_tools(
        payload: FinancialToolsRequest,
        request: Request,
        session: Session = Depends(db)
    ):
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
    return router
