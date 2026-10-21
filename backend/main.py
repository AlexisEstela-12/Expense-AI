from datetime import date, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta
if __package__:
    from .api.routers.health import router as health_router
    from .schemas.common import Money
    from .schemas.movements import MovementIn
    from .schemas.exchanges import ExchangeIn
    from .schemas.categories import CategoryIn
    from .schemas.budgets import BudgetIn
    from .schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
    from .schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
    from .schemas.savings_goals import SavingsGoalIn, SavingsContributionIn
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
    from schemas.common import Money
    from schemas.movements import MovementIn
    from schemas.exchanges import ExchangeIn
    from schemas.categories import CategoryIn
    from schemas.budgets import BudgetIn
    from schemas.reimbursements import ReimbursementIn, ReimbursementPaidIn
    from schemas.recurring_payments import RecurringPaymentIn, RecurringPaymentPaidIn
    from schemas.savings_goals import SavingsGoalIn, SavingsContributionIn
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
@app.get('/summary')
def summary(session: Session = Depends(db)):
    totals = available(session)
    reserved = reserved_savings(session)
    spendable = spendable_balance(session)

    return {
        'balances': {
            k: str(v)
            for k, v in totals.items()
        },
        'reserved': {
            k: str(v)
            for k, v in reserved.items()
        },
        'spendable': {
            k: str(v)
            for k, v in spendable.items()
        }
    }

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

@app.get('/movements')
def movements(session:Session=Depends(db)):
    return [{'id':m.id,'date':m.date.isoformat(),'kind':m.kind,'currency':m.currency,'amount':str(m.amount),'category':m.category,'description':m.description} for m in session.scalars(select(Movement).order_by(Movement.date.desc(),Movement.id.desc())).all()]
@app.post('/movements',status_code=201)
def create_movement(payload:MovementIn,session:Session=Depends(db)):
    if payload.kind=='expense': ensure_balance(session,payload.currency.value,payload.amount)
    m=Movement(**payload.model_dump())
    m.currency=payload.currency.value
    session.add(m);session.commit();session.refresh(m)
    return {'id':m.id}
@app.post('/exchanges',status_code=201)
def exchange(payload:ExchangeIn,session:Session=Depends(db)):
    origin=payload.from_currency.value
    dest='PEN' if origin=='USD' else 'USD'
    ensure_balance(session,origin,payload.amount_out)
    rate=(payload.amount_in/payload.amount_out if origin=='USD' else payload.amount_out/payload.amount_in)
    ex=Exchange(date=payload.date,from_currency=origin,amount_out=payload.amount_out,amount_in=payload.amount_in,rate=rate)
    session.add(ex);session.flush()
    session.add_all([
        Movement(date=payload.date,kind='expense',currency=origin,amount=payload.amount_out,category='Cambio de divisas',exchange_id=ex.id),
        Movement(date=payload.date,kind='income',currency=dest,amount=payload.amount_in,category='Cambio de divisas',exchange_id=ex.id)
    ])
    session.commit()
    return {'id':ex.id,'rate':str(rate),'balances':{k:str(v) for k,v in available(session).items()}}
@app.get('/budgets')
def budgets(session:Session=Depends(db)):
    data=[]
    for b in session.scalars(select(Budget)):
        spent=sum((m.amount for m in session.scalars(select(Movement).where(Movement.kind=='expense',Movement.category==b.category,Movement.currency==b.currency,Movement.exchange_id==None)) if m.date.strftime('%Y-%m')==b.month),Decimal('0'))
        pct=spent/b.limit_amount*100
        data.append({'id':b.id,'month':b.month,'category':b.category,'currency':b.currency,'limit':str(b.limit_amount),'spent':str(spent),'percentage':round(float(pct),1),'alert':100 if pct>=100 else 90 if pct>=90 else 75 if pct>=75 else 0})
    return data
@app.post('/budgets',status_code=201)
def create_budget(payload:BudgetIn,session:Session=Depends(db)):
    b=Budget(**payload.model_dump());b.currency=payload.currency.value
    session.add(b);session.commit();session.refresh(b)
    return {'id':b.id}
@app.post('/reimbursements', status_code=201)
def create_reimbursement(
    payload: ReimbursementIn,
    session: Session = Depends(db)
):
    currency = payload.currency.value

    # Verificar que tengas saldo suficiente para pagar el gasto
    ensure_balance(session, currency, payload.amount)

    # 1. Registrar el gasto real en movimientos
    movement = Movement(
        date=payload.date,
        kind='expense',
        currency=currency,
        amount=payload.amount,
        category=payload.category,
        description=payload.description
    )

    session.add(movement)
    session.flush()

    # 2. Crear el reembolso pendiente y vincularlo al gasto
    reimbursement = Reimbursement(
        date=payload.date,
        currency=currency,
        amount=payload.amount,
        category=payload.category,
        description=payload.description,
        status='pending',
        movement_id=movement.id
    )

    session.add(reimbursement)
    session.commit()
    session.refresh(reimbursement)

    return {
        'id': reimbursement.id,
        'status': reimbursement.status,
        'movement_id': reimbursement.movement_id,
        'currency': reimbursement.currency,
        'amount': str(reimbursement.amount)
    }

@app.post('/reimbursements/{reimbursement_id}/complete')
def complete_reimbursement(
    reimbursement_id: int,
    payload: ReimbursementPaidIn,
    session: Session = Depends(db)
):
    with session.begin():
        reimbursement = session.get(Reimbursement, reimbursement_id)

        if reimbursement is None:
            raise HTTPException(
                status_code=404,
                detail='Reembolso no encontrado.'
            )

        if reimbursement.status != 'pending':
            raise HTTPException(
                status_code=400,
                detail='Este reembolso ya no está pendiente.'
            )

        # La actualización condicional adquiere el bloqueo de escritura antes
        # de crear el movimiento. Una solicitud concurrente no puede reclamar
        # el mismo pendiente, incluso si ambas leyeron su estado inicial.
        result = session.execute(
            Reimbursement.__table__.update()
            .where(
                Reimbursement.id == reimbursement_id,
                Reimbursement.status == 'pending'
            )
            .values(
                status='reimbursed',
                reimbursed_date=payload.date
            )
        )

        if result.rowcount != 1:
            raise HTTPException(
                status_code=400,
                detail='Este reembolso ya no está pendiente.'
            )

        session.refresh(reimbursement)
        movement = Movement(
            date=payload.date,
            kind='reimbursement',
            currency=reimbursement.currency,
            amount=reimbursement.amount,
            category='Reembolso laboral',
            description=(
                f'Reembolso #{reimbursement.id}: '
                f'{reimbursement.description or "Gasto laboral"}'
            )[:255]
        )
        session.add(movement)
        session.flush()
        reimbursement.reimbursement_movement_id = movement.id

        response = {
            'id': reimbursement.id,
            'status': reimbursement.status,
            'reimbursed_date': reimbursement.reimbursed_date.isoformat(),
            'currency': reimbursement.currency,
            'amount': str(reimbursement.amount),
            'reimbursement_movement_id': movement.id
        }

    return response

@app.get('/reimbursements')
def get_reimbursements(session: Session = Depends(db)):
    items = session.scalars(
        select(Reimbursement).order_by(
            Reimbursement.date.desc(),
            Reimbursement.id.desc()
        )
    ).all()

    return [
        {
            'id': r.id,
            'date': r.date.isoformat(),
            'currency': r.currency,
            'amount': str(r.amount),
            'category': r.category,
            'description': r.description,
            'status': r.status,
            'reimbursed_date': (
                r.reimbursed_date.isoformat()
                if r.reimbursed_date
                else None
            ),
            'movement_id': r.movement_id,
            'reimbursement_movement_id': r.reimbursement_movement_id
        }
        for r in items
    ]

@app.post('/recurring-payments', status_code=201)
def create_recurring_payment(
    payload: RecurringPaymentIn,
    session: Session = Depends(db)
):
    recurring_payment = RecurringPayment(
        name=payload.name,
        category=payload.category,
        currency=payload.currency.value,
        amount=payload.amount,
        frequency=payload.frequency,
        next_payment_date=payload.next_payment_date,
        active=1
    )

    session.add(recurring_payment)
    session.commit()
    session.refresh(recurring_payment)

    return {
        'id': recurring_payment.id,
        'name': recurring_payment.name,
        'category': recurring_payment.category,
        'currency': recurring_payment.currency,
        'amount': str(recurring_payment.amount),
        'frequency': recurring_payment.frequency,
        'next_payment_date': recurring_payment.next_payment_date.isoformat(),
        'active': bool(recurring_payment.active)
    }
    

@app.get('/recurring-payments')
def get_recurring_payments(session: Session = Depends(db)):
    items = session.scalars(
        select(RecurringPayment).order_by(
            RecurringPayment.next_payment_date.asc(),
            RecurringPayment.id.asc()
        )
    ).all()

    return [
        {
            'id': item.id,
            'name': item.name,
            'category': item.category,
            'currency': item.currency,
            'amount': str(item.amount),
            'frequency': item.frequency,
            'next_payment_date': item.next_payment_date.isoformat(),
            'active': bool(item.active)
        }
        for item in items
    ]
    
@app.post('/recurring-payments/{recurring_payment_id}/pay')
def pay_recurring_payment(
    recurring_payment_id: int,
    payload: RecurringPaymentPaidIn,
    session: Session = Depends(db)
):
    recurring_payment = session.get(
        RecurringPayment,
        recurring_payment_id
    )

    if not recurring_payment:
        raise HTTPException(
            status_code=404,
            detail='Pago recurrente no encontrado.'
        )

    if not recurring_payment.active:
        raise HTTPException(
            status_code=400,
            detail='Este pago recurrente está inactivo.'
        )

    # Verificar que exista saldo suficiente
    ensure_balance(
        session,
        recurring_payment.currency,
        recurring_payment.amount
    )

    # Registrar el pago como un gasto real
    movement = Movement(
        date=payload.date,
        kind='expense',
        currency=recurring_payment.currency,
        amount=recurring_payment.amount,
        category=recurring_payment.category,
        description=recurring_payment.name
    )

    session.add(movement)

    # Calcular el siguiente vencimiento
    if recurring_payment.frequency == 'weekly':
        recurring_payment.next_payment_date += relativedelta(weeks=1)
    elif recurring_payment.frequency == 'monthly':
        recurring_payment.next_payment_date += relativedelta(months=1)
    elif recurring_payment.frequency == 'yearly':
        recurring_payment.next_payment_date += relativedelta(years=1)

    session.commit()
    session.refresh(recurring_payment)

    return {
        'id': recurring_payment.id,
        'name': recurring_payment.name,
        'paid_date': payload.date.isoformat(),
        'next_payment_date': recurring_payment.next_payment_date.isoformat(),
        'currency': recurring_payment.currency,
        'amount': str(recurring_payment.amount),
        'balances': {
            k: str(v)
            for k, v in available(session).items()
        }
    }
    
    
@app.get('/categories')
def get_categories(session: Session = Depends(db)):
    items = session.scalars(
        select(Category).order_by(
            Category.kind.asc(),
            Category.name.asc()
        )
    ).all()

    return [
        {
            'id': category.id,
            'name': category.name,
            'kind': category.kind
        }
        for category in items
    ]

@app.post('/categories', status_code=201)
def create_category(payload: CategoryIn, session: Session = Depends(db)):
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail='La categoría no puede estar vacía.'
        )

    existing = session.scalars(
        select(Category).where(
            Category.kind == payload.kind,
            Category.name == name
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail='Esta categoría ya existe.'
        )

    category = Category(
        name=name,
        kind=payload.kind
    )

    session.add(category)
    session.commit()
    session.refresh(category)

    return {
        'id': category.id,
        'name': category.name,
        'kind': category.kind
    }

@app.get('/notifications')
def get_notifications(session: Session = Depends(db)):
    today = date.today()
    notifications = []

    # -----------------------------------
    # 1. PAGOS RECURRENTES
    # -----------------------------------

    recurring_payments = session.scalars(
        select(RecurringPayment).where(
            RecurringPayment.active == 1
        )
    ).all()

    for payment in recurring_payments:
        days = (payment.next_payment_date - today).days

        if days < 0:
            notifications.append({
                'type': 'recurring_payment',
                'level': 'danger',
                'title': 'Pago vencido',
                'message': f'{payment.name} venció el {payment.next_payment_date.isoformat()}.',
                'date': payment.next_payment_date.isoformat()
            })

        elif days == 0:
            notifications.append({
                'type': 'recurring_payment',
                'level': 'danger',
                'title': 'Pago vence hoy',
                'message': f'{payment.name} vence hoy.',
                'date': payment.next_payment_date.isoformat()
            })

        elif days <= 3:
            notifications.append({
                'type': 'recurring_payment',
                'level': 'warning',
                'title': 'Pago próximo',
                'message': f'{payment.name} vence en {days} días.',
                'date': payment.next_payment_date.isoformat()
            })

        elif days <= 7:
            notifications.append({
                'type': 'recurring_payment',
                'level': 'info',
                'title': 'Próximo pago',
                'message': f'{payment.name} vence en {days} días.',
                'date': payment.next_payment_date.isoformat()
            })

    # -----------------------------------
    # 2. PRESUPUESTOS
    # -----------------------------------

    budgets = session.scalars(
        select(Budget)
    ).all()

    for budget in budgets:
        spent = sum(
            (
                movement.amount
                for movement in session.scalars(
                    select(Movement).where(
                        Movement.kind == 'expense',
                        Movement.category == budget.category,
                        Movement.currency == budget.currency,
                        Movement.exchange_id == None
                    )
                )
                if movement.date.strftime('%Y-%m') == budget.month
            ),
            Decimal('0')
        )

        percentage = (
            spent / budget.limit_amount * 100
            if budget.limit_amount > 0
            else Decimal('0')
        )

        level = None
        title = None

        if percentage >= 100:
            level = 'danger'
            title = 'Presupuesto excedido'

        elif percentage >= 90:
            level = 'warning'
            title = 'Presupuesto al 90%'

        elif percentage >= 75:
            level = 'info'
            title = 'Presupuesto al 75%'

        if level:
            notifications.append({
                'type': 'budget',
                'level': level,
                'title': title,
                'message': (
                    f'{budget.category}: has utilizado '
                    f'{percentage:.0f}% de tu presupuesto '
                    f'{budget.month}.'
                ),
                'date': f'{budget.month}-01'
            })

    notifications.sort(key=lambda item: item['date'])
        # -----------------------------------
    # 3. REEMBOLSOS PENDIENTES
    # -----------------------------------

    pending_reimbursements = session.scalars(
        select(Reimbursement).where(
            Reimbursement.status == 'pending'
        )
    ).all()

    for reimbursement in pending_reimbursements:
        days_pending = (today - reimbursement.date).days

        notifications.append({
            'type': 'reimbursement',
            'level': 'info',
            'title': 'Reembolso pendiente',
            'message': (
                f'Tienes {reimbursement.currency} '
                f'{reimbursement.amount:.2f} pendientes de reembolso '
                f'desde hace {days_pending} días.'
            ),
            'date': reimbursement.date.isoformat()
        })
    return notifications

@app.post('/savings-goals', status_code=201)
def create_savings_goal(
    payload: SavingsGoalIn,
    session: Session = Depends(db)
):
    goal = SavingsGoal(
        name=payload.name.strip(),
        currency=payload.currency.value,
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        active=1
    )

    session.add(goal)
    session.commit()
    session.refresh(goal)

    return {
        'id': goal.id,
        'name': goal.name,
        'currency': goal.currency,
        'target_amount': str(goal.target_amount),
        'target_date': (
            goal.target_date.isoformat()
            if goal.target_date
            else None
        ),
        'active': bool(goal.active),
        'saved_amount': '0.00',
        'percentage': 0
    }
    
@app.get('/savings-goals')
def get_savings_goals(session: Session = Depends(db)):
    goals = session.scalars(
    select(SavingsGoal)
    .where(SavingsGoal.active == 1)
    .order_by(SavingsGoal.id.desc())
    ).all()

    result = []

    for goal in goals:
        contributions = session.scalars(
            select(SavingsContribution).where(
                SavingsContribution.goal_id == goal.id
            )
        ).all()

        saved_amount = sum(
            (contribution.amount for contribution in contributions),
            Decimal('0')
        )

        percentage = (
            saved_amount / goal.target_amount * 100
            if goal.target_amount > 0
            else Decimal('0')
        )

        result.append({
            'id': goal.id,
            'name': goal.name,
            'currency': goal.currency,
            'target_amount': str(goal.target_amount),
            'saved_amount': str(saved_amount),
            'percentage': round(float(percentage), 1),
            'target_date': (
                goal.target_date.isoformat()
                if goal.target_date
                else None
            ),
            'active': bool(goal.active)
        })

    return result

@app.post('/savings-goals/{goal_id}/contributions', status_code=201)
def create_savings_contribution(
    goal_id: int,
    payload: SavingsContributionIn,
    session: Session = Depends(db)
):
    goal = session.get(SavingsGoal, goal_id)

    if not goal:
        raise HTTPException(
            status_code=404,
            detail='Meta de ahorro no encontrada.'
        )

    if not goal.active:
        raise HTTPException(
            status_code=400,
            detail='Esta meta de ahorro está inactiva.'
        )
    ensure_spendable_balance(
        session,
        goal.currency,
        payload.amount
    )

    # Calcular cuánto ya está reservado en esta meta
    contributions = session.scalars(
        select(SavingsContribution).where(
            SavingsContribution.goal_id == goal.id
        )
    ).all()

    saved_amount = sum(
        (contribution.amount for contribution in contributions),
        Decimal('0')
    )

    remaining = goal.target_amount - saved_amount

    if payload.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f'El aporte supera el monto pendiente de la meta. Falta ahorrar {goal.currency} {remaining:.2f}.'
        )

    contribution = SavingsContribution(
        goal_id=goal.id,
        date=payload.date,
        amount=payload.amount
    )

    session.add(contribution)
    session.commit()
    session.refresh(contribution)

    new_saved_amount = saved_amount + contribution.amount

    percentage = (
        new_saved_amount / goal.target_amount * 100
        if goal.target_amount > 0
        else Decimal('0')
    )

    return {
        'id': contribution.id,
        'goal_id': goal.id,
        'goal_name': goal.name,
        'date': contribution.date.isoformat(),
        'currency': goal.currency,
        'amount': str(contribution.amount),
        'saved_amount': str(new_saved_amount),
        'target_amount': str(goal.target_amount),
        'percentage': round(float(percentage), 1)
    }
    
    
@app.post('/savings-goals/{goal_id}/cancel')
def cancel_savings_goal(
    goal_id: int,
    session: Session = Depends(db)
):
    goal = session.get(SavingsGoal, goal_id)

    if not goal:
        raise HTTPException(
            status_code=404,
            detail='Meta de ahorro no encontrada.'
        )

    if not goal.active:
        raise HTTPException(
            status_code=400,
            detail='Esta meta de ahorro ya está cerrada.'
        )

    contributions = session.scalars(
        select(SavingsContribution).where(
            SavingsContribution.goal_id == goal.id
        )
    ).all()

    released_amount = sum(
        (contribution.amount for contribution in contributions),
        Decimal('0')
    )

    goal.active = 0

    session.commit()

    return {
        'id': goal.id,
        'name': goal.name,
        'status': 'cancelled',
        'currency': goal.currency,
        'released_amount': str(released_amount),
        'message': 'Meta cancelada. El dinero reservado vuelve a estar disponible.'
    }
    
@app.post('/savings-goals/{goal_id}/use')
def use_savings_goal(
    goal_id: int,
    session: Session = Depends(db)
):
    goal = session.get(SavingsGoal, goal_id)

    if not goal:
        raise HTTPException(
            status_code=404,
            detail='Meta de ahorro no encontrada.'
        )

    if not goal.active:
        raise HTTPException(
            status_code=400,
            detail='Esta meta de ahorro ya está cerrada.'
        )

    contributions = session.scalars(
        select(SavingsContribution).where(
            SavingsContribution.goal_id == goal.id
        )
    ).all()

    saved_amount = sum(
        (contribution.amount for contribution in contributions),
        Decimal('0')
    )

    if saved_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail='Esta meta no tiene dinero ahorrado.'
        )

    movement = Movement(
        date=date.today(),
        kind='expense',
        currency=goal.currency,
        amount=saved_amount,
        category='Otros gastos',
        description=f'Uso de ahorro: {goal.name}'
    )

    session.add(movement)

    goal.active = 0

    session.commit()
    session.refresh(movement)

    return {
        'id': goal.id,
        'name': goal.name,
        'status': 'completed',
        'currency': goal.currency,
        'used_amount': str(saved_amount),
        'movement_id': movement.id,
        'message': 'Ahorro utilizado y registrado como gasto.'
    }
