"""Exercise the actual main.py wiring under offline fixtures; no production DB."""
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from sqlalchemy import event, select
from api.routers import chat as chat_router_module

from db.base import Base
from db.models import Movement
from security.models import AuthSession
from security.dependencies import create_authentication_dependency
from security.router import create_router as auth_router
import test_auth_endpoints as auth_fixtures
from test_auth_endpoints import ENV, ORIGIN

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT/'tests/fixtures/openapi_before_startup_fix.json').read_text())
PRIVATE = [(method.upper(), path.replace('{goal_id}','1').replace('{reimbursement_id}','1')
            .replace('{recurring_payment_id}','1'))
           for path, operations in REFERENCE['paths'].items() if path != '/health'
           for method in operations]


class PrivateEndpointsTest(unittest.TestCase):
    setUpClass = classmethod(auth_fixtures.AuthEndpointsTest.setUpClass.__func__)
    request = auth_fixtures.AuthEndpointsTest.request
    login = auth_fixtures.AuthEndpointsTest.login
    credentials = auth_fixtures.AuthEndpointsTest.credentials
    snapshot = auth_fixtures.AuthEndpointsTest.snapshot

    def make_app(self, app_env='test'):
        fake=ModuleType('db.session')
        fake.connection_string='fictional'
        fake.DB_URL='sqlite+pysqlite:///:memory:'
        fake.engine=self.engine
        fake.SessionLocal=self.sessions
        module=ModuleType('_protected_app_test')
        module.__package__=''
        def dependency(db):
            return create_authentication_dependency(db,settings_provider=lambda:self.settings,
                                                     now_provider=lambda:self.now)
        def auth(db):
            return auth_router(db,settings_provider=lambda:self.settings,now_provider=lambda:self.now)
        with patch.dict(sys.modules,{'db.session':fake}), \
             patch.dict('os.environ',ENV|{'APP_ENV':app_env},clear=True), \
             patch('security.dependencies.create_authentication_dependency',side_effect=dependency), \
             patch('security.router.create_router',side_effect=auth):
            exec(compile((ROOT/'main.py').read_text(),str(ROOT/'main.py'),'exec'),module.__dict__)
        return module.app

    def setUp(self):
        auth_fixtures.AuthEndpointsTest.setUp(self)
        Base.metadata.create_all(self.engine)
        with self.sessions() as session:
            for currency in ('PEN','USD'):
                session.add(Movement(date=date(2026,10,1),kind='income',currency=currency,
                                     amount=Decimal('100'),category='Ficticio'))
            session.commit()

    @contextmanager
    def financial_io_forbidden(self):
        def guard(connection,cursor,statement,parameters,context,executemany):
            for table in Base.metadata.tables:
                if re.search(r'\b'+re.escape(table)+r'\b',statement,re.I):
                    raise AssertionError('Financial SQL before authorization')
        event.listen(self.engine,'before_cursor_execute',guard)
        try:
            with patch('llm.openai_provider.OpenAI',side_effect=AssertionError('Provider forbidden')):
                yield
        finally:
            event.remove(self.engine,'before_cursor_execute',guard)

    def test_all_23_operations_reject_anonymous_before_financial_io(self):
        self.assertEqual(len(PRIVATE),23)
        before=self.snapshot()
        with self.financial_io_forbidden():
            for method,path in PRIVATE:
                with self.subTest(method=method,path=path):
                    self.assertEqual(self.request(path,{},method=method)[0],401)
        self.assertEqual(self.snapshot(),before)

    def test_invalid_expired_and_revoked_sessions_reject_all_private_operations(self):
        cookie,_=self.credentials()
        with self.financial_io_forbidden():
            for method,path in PRIVATE:
                self.assertEqual(self.request(path,{},method=method,
                    cookie='__Host-expense_session=invalid')[0],401)
            self.now+=timedelta(minutes=30)
            for method,path in PRIVATE:
                self.assertEqual(self.request(path,{},method=method,cookie=cookie)[0],401)
        self.now-=timedelta(minutes=30)
        with self.sessions() as session:
            session.scalars(select(AuthSession)).one().revoked_at=self.now
            session.commit()
        with self.financial_io_forbidden():
            for method,path in PRIVATE:
                self.assertEqual(self.request(path,{},method=method,cookie=cookie)[0],401)

    def test_all_private_posts_enforce_origin_and_csrf_without_partial_writes(self):
        cookie,csrf=self.credentials()
        before=self.snapshot()
        with self.financial_io_forbidden():
            for method,path in PRIVATE:
                if method!='POST':continue
                for origin,token in [(ORIGIN,None),(ORIGIN,'0'*64),(None,csrf),('https://evil.test',csrf)]:
                    with self.subTest(path=path,origin=origin):
                        self.assertEqual(self.request(path,{},cookie=cookie,csrf=token,origin=origin)[0],403)
        self.assertEqual(self.snapshot(),before)

    def test_forwarded_headers_cannot_authenticate(self):
        with self.financial_io_forbidden():
            for method,path in PRIVATE:
                self.assertEqual(self.request(path,{},method=method,
                    extra_headers={'x-forwarded-for':'127.0.0.1','x-ms-client-principal':'fictional'})[0],401)

    def test_authenticated_summary_and_financial_write(self):
        cookie,csrf=self.credentials()
        self.assertEqual(self.request('/summary',method='GET',cookie=cookie,origin=None)[0],200)
        self.assertEqual(self.request('/movements',{'date':'2026-10-27','kind':'expense',
            'currency':'PEN','amount':'10.25','category':'Ficticio'},cookie=cookie,csrf=csrf)[0],201)

    def test_auth_transaction_does_not_break_reimbursement_transaction(self):
        cookie,csrf=self.credentials()
        status,created,_=self.request('/reimbursements',{'date':'2026-10-27',
            'currency':'PEN','amount':'10.25','category':'Ficticio'},cookie=cookie,csrf=csrf)
        self.assertEqual(status,201,created)
        status,completed,_=self.request(f"/reimbursements/{created['id']}/complete",
            {'date':'2026-10-27'},cookie=cookie,csrf=csrf)
        self.assertEqual(status,200,completed)
        self.assertEqual(completed['status'],'reimbursed')

    def test_all_private_gets_accept_session_without_csrf(self):
        cookie,_=self.credentials()
        for method,path in PRIVATE:
            if method=='GET':
                self.assertEqual(self.request(path,method=method,cookie=cookie,origin=None)[0],200)

    def test_health_public_and_docs_disabled_only_in_production(self):
        self.assertEqual(self.request('/health',method='GET',origin=None)[0],200)
        for env in ('development','test','production'):
            app=self.make_app(env)
            paths={getattr(route,'path',None) for route in app.routes}
            for path in ('/docs','/redoc','/openapi.json'):
                self.assertEqual(path in paths,env!='production')
            self.assertEqual(sum(len(ops) for ops in app.openapi()['paths'].values()),27)
        app=self.make_app('production')
        self.assertEqual(self.request('/openapi.json',method='GET',app=app)[0],404)

    def test_authenticated_chat_reaches_mock_provider_without_loopback(self):
        from chat.financial_tools import FinancialToolsResponse
        from chat.tool_balances import ToolBalanceResponse
        from chat.balances import BalanceChatResponse
        cookie,csrf=self.credentials()
        responses=[('/api/chat/balances','explain_balances',BalanceChatResponse),
                   ('/api/chat/tool-balances','run_tool_balances',ToolBalanceResponse),
                   ('/api/chat/tools','run_financial_tools',FinancialToolsResponse)]
        for path,name,model in responses:
            fields=dict(answer='Ficticio',financial_data=None,explanation_source='unsupported',
                        explanation_reason='unsupported',diagnostic_id='fictional',tool_executed=False)
            if name=='run_financial_tools':fields['tool_name']=None
            result=model(**fields)
            with patch.object(chat_router_module,name,return_value=result) as mocked:
                status,data,_=self.request(path,{'message':'saldo'},cookie=cookie,csrf=csrf,
                    peer='192.0.2.10',extra_headers={'x-forwarded-for':'192.0.2.99'})
            self.assertEqual(status,200,data)
            mocked.assert_called_once()
