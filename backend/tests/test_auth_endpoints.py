"""Authentication HTTP tests with fictitious users and SQLite memory only."""
import asyncio
import base64
from datetime import datetime, timedelta
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from security.config import load_auth_settings
from security.models import AuthBase, AuthUser, AuthSession, AuthLoginLimit
from security.primitives import hash_password, hash_session_token
from security.router import create_router

PASSWORD = 'Fictitious phase three password'
ORIGIN = 'https://expense.test'
ENV = {'APP_ENV': 'test', 'AUTH_ALLOWED_ORIGINS': ORIGIN,
       'AUTH_CSRF_KEY': base64.urlsafe_b64encode(b'F'*32).decode()}


class AuthEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password(PASSWORD)

    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:',
            connect_args={'check_same_thread': False}, poolclass=StaticPool,
            execution_options={'schema_translate_map': {'dbo': None}})
        self.addCleanup(self.engine.dispose)
        @event.listens_for(self.engine, 'connect')
        def fk(connection, record):
            connection.execute('PRAGMA foreign_keys=ON')
        AuthBase.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.now = datetime(2026, 10, 27)
        self.settings = load_auth_settings(environ=ENV)
        with self.sessions() as session:
            session.add(AuthUser(id=1, username='fictitious', password_hash=self.encoded,
                         created_at=self.now, password_changed_at=self.now, active=True))
            session.commit()
        self.app = self.make_app()

    def make_app(self):
        def db():
            with self.sessions() as session:
                yield session
        app = FastAPI()
        app.include_router(create_router(db, settings_provider=lambda: self.settings,
                                         now_provider=lambda: self.now))
        return app

    def request(self, path, payload=None, *, cookie=None, csrf=None, origin=ORIGIN,
                method='POST', peer='192.0.2.1', app=None, extra_headers=None, raw=None):
        headers = {'content-type': 'application/json'}
        if origin is not None: headers['origin'] = origin
        if cookie: headers['cookie'] = cookie
        if csrf is not None: headers['x-csrf-token'] = csrf
        headers.update(extra_headers or {})
        body = raw if raw is not None else json.dumps(payload).encode()
        async def call():
            messages=[]
            async def receive(): return {'type':'http.request','body':body,'more_body':False}
            async def send(message): messages.append(message)
            await (app or self.app)({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1',
                'method':method,'scheme':'https','path':path,'raw_path':path.encode(),
                'root_path':'','query_string':b'',
                'headers':[(k.encode(),v.encode()) for k,v in headers.items()],
                'client':(peer,50000),'server':('expense.test',443)},receive,send)
            start=next(m for m in messages if m['type']=='http.response.start')
            data=json.loads(b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))
            return start['status'],data,{k.decode():v.decode() for k,v in start['headers']}
        return asyncio.run(call())

    def login(self, **kwargs):
        return self.request('/auth/login', {'username':'fictitious','password':PASSWORD},
                            csrf='login', **kwargs)

    def credentials(self):
        status,data,headers=self.login()
        self.assertEqual(status,200)
        return headers['set-cookie'].split(';')[0],data['csrf_token']

    def snapshot(self):
        with self.engine.connect() as connection:
            return {table.name:list(connection.execute(select(table)))
                    for table in AuthBase.metadata.sorted_tables}

    def test_valid_login_cookie_and_hash_only_storage(self):
        status,data,headers=self.login()
        self.assertEqual(status,200)
        self.assertEqual(data['user'],{'id':1,'username':'fictitious'})
        cookie=headers['set-cookie']
        for value in ('__Host-expense_session=', 'HttpOnly', 'Secure', 'SameSite=lax', 'Path=/', 'Max-Age=43200'):
            self.assertIn(value,cookie)
        self.assertNotIn('Domain=',cookie)
        self.assertEqual(headers['cache-control'],'no-store')
        token=cookie.split(';')[0].split('=',1)[1]
        with self.sessions() as session:
            saved=session.get(AuthSession,hash_session_token(token))
            self.assertIsNotNone(saved)
            self.assertEqual(saved.idle_expires_at,self.now+timedelta(minutes=30))
            self.assertNotIn(token,repr(saved))
        self.assertNotIn(token,json.dumps(data))

    def test_development_cookie_is_separate(self):
        self.settings=load_auth_settings(environ=ENV|{'APP_ENV':'development'})
        headers=self.login()[2]
        self.assertIn('expense_session_dev=',headers['set-cookie'])
        self.assertNotIn('Secure',headers['set-cookie'])

    def test_invalid_credentials_are_generic_and_create_no_session(self):
        results=[]
        for username,password in [('fictitious','Incorrect fictional password'),('unknown',PASSWORD)]:
            status,data,headers=self.request('/auth/login',{'username':username,'password':password},csrf='login')
            self.assertEqual(status,401)
            self.assertNotIn('set-cookie',headers)
            results.append(data)
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.snapshot()['auth_session'],[])
        self.assertEqual(len(self.snapshot()['auth_login_limit']),2)

    def test_origin_and_login_csrf_rejections_do_not_write(self):
        before=self.snapshot()
        for origin,csrf in [(None,'login'),('https://evil.test','login'),(ORIGIN,None),(ORIGIN,'bad')]:
            status,data,_=self.request('/auth/login',{'username':'fictitious','password':PASSWORD},origin=origin,csrf=csrf)
            self.assertEqual(status,403)
            self.assertEqual(self.snapshot(),before)

    def test_session_shared_between_instances_and_logout_revokes(self):
        cookie,csrf=self.credentials()
        other=self.make_app()
        status,data,_=self.request('/auth/session',method='GET',cookie=cookie,origin=None,app=other)
        self.assertEqual(status,200)
        self.assertEqual(data['csrf_token'],csrf)
        status,_,headers=self.request('/auth/logout',cookie=cookie,csrf=csrf,app=other)
        self.assertEqual(status,200)
        self.assertIn('Max-Age=0',headers['set-cookie'])
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],401)
        self.assertIsNotNone(self.snapshot()['auth_session'][0]._mapping['revoked_at'])

    def test_bad_logout_csrf_and_origin_leave_session_unchanged(self):
        cookie,csrf=self.credentials()
        for token,origin in [(None,ORIGIN),('0'*64,ORIGIN),(csrf,None),(csrf,'https://evil.test')]:
            before=self.snapshot()
            self.assertEqual(self.request('/auth/logout',cookie=cookie,csrf=token,origin=origin)[0],403)
            self.assertEqual(self.snapshot(),before)

    def test_csrf_from_another_session_is_rejected(self):
        cookie,_=self.credentials()
        _,other_csrf=self.credentials()
        self.assertEqual(self.request('/auth/logout',cookie=cookie,csrf=other_csrf)[0],403)

    def test_missing_malformed_and_inactive_sessions_are_rejected(self):
        self.assertEqual(self.request('/auth/session',method='GET')[0],401)
        self.assertEqual(self.request('/auth/session',method='GET',cookie='__Host-expense_session=bad')[0],401)
        cookie,_=self.credentials()
        with self.sessions() as session:
            session.get(AuthUser,1).active=False
            session.commit()
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],401)

    def test_idle_and_absolute_expiration_and_sliding_touch(self):
        cookie,_=self.credentials()
        self.now+=timedelta(minutes=29)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],200)
        self.assertEqual(self.snapshot()['auth_session'][0]._mapping['idle_expires_at'],self.now+timedelta(minutes=30))
        self.now+=timedelta(minutes=30)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],401)
        self.now+=timedelta(minutes=1)
        cookie,_=self.credentials()
        self.now+=timedelta(hours=12)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],401)

    def test_login_limit_shared_429_no_partial_claim_and_window_reset(self):
        for _ in range(5):
            self.assertEqual(self.request('/auth/login',{'username':'wrong','password':PASSWORD},csrf='login')[0],401)
        before=self.snapshot()
        status,_,headers=self.login(app=self.make_app())
        self.assertEqual(status,429)
        self.assertEqual(headers['retry-after'],'900')
        self.assertEqual(self.snapshot(),before)
        self.now+=timedelta(minutes=15)
        self.assertEqual(self.login()[0],200)

    def test_activity_cannot_extend_absolute_expiration(self):
        cookie,_=self.credentials()
        with self.sessions() as session:
            row=session.scalars(select(AuthSession)).one()
            row.last_seen_at=self.now+timedelta(hours=11,minutes=50)
            row.idle_expires_at=self.now+timedelta(hours=12,minutes=20)
            session.commit()
        self.now+=timedelta(hours=11,minutes=59)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],200)
        row=self.snapshot()['auth_session'][0]._mapping
        self.assertEqual(row['idle_expires_at'],row['expires_at'])
        self.now+=timedelta(minutes=1)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie)[0],401)

    def test_session_get_rejects_explicit_untrusted_origin_without_touch(self):
        cookie,_=self.credentials()
        before=self.snapshot()
        self.now+=timedelta(minutes=5)
        self.assertEqual(self.request('/auth/session',method='GET',cookie=cookie,
                                      origin='https://evil.test')[0],403)
        self.assertEqual(self.snapshot(),before)

    def test_request_errors_never_echo_submitted_secrets(self):
        for payload in ({'password':PASSWORD}, {'username':PASSWORD,'password':['secret']},
                        {'username':'fictitious','password':'X'*5000}):
            status,data,_=self.request('/auth/login',payload,csrf='login')
            self.assertEqual(status,400)
            self.assertNotIn(PASSWORD,json.dumps(data))
        self.assertEqual(self.request('/auth/login',csrf='login',raw=b'{bad')[0],400)

    def test_missing_configuration_or_schema_is_generic_503(self):
        app=FastAPI()
        def db():
            with self.sessions() as session:
                yield session
        app.include_router(create_router(db,settings_provider=lambda:load_auth_settings(environ={})))
        self.assertEqual(self.login(app=app)[0],503)
        empty=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},
                            poolclass=StaticPool,execution_options={'schema_translate_map':{'dbo':None}})
        try:
            def empty_db():
                with sessionmaker(bind=empty)() as session:
                    yield session
            app=FastAPI()
            app.include_router(create_router(empty_db,settings_provider=lambda:self.settings))
            status,data,headers=self.login(app=app)
            self.assertEqual(status,503)
            self.assertNotIn('set-cookie',headers)
            self.assertNotIn(PASSWORD,json.dumps(data))
        finally:
            empty.dispose()

    def test_global_limit_applies_across_different_peers_and_replicas(self):
        for index in range(20):
            self.assertEqual(self.request('/auth/login',{'username':'wrong','password':PASSWORD},
                             csrf='login',peer=f'192.0.2.{index+1}')[0],401)
        before=self.snapshot()
        self.assertEqual(self.login(peer='192.0.2.250',app=self.make_app())[0],429)
        self.assertEqual(self.snapshot(),before)

    def test_cross_site_and_forwarded_headers_do_not_bypass_limits(self):
        before=self.snapshot()
        self.assertEqual(self.login(extra_headers={'sec-fetch-site':'cross-site'})[0],403)
        self.assertEqual(self.snapshot(),before)
        for index in range(5):
            self.assertEqual(self.login(extra_headers={'x-forwarded-for':f'192.0.2.{index}'})[0],200)
        self.assertEqual(self.login(extra_headers={'x-forwarded-for':'192.0.2.200'})[0],429)

    def test_database_failure_does_not_create_partial_session_or_leak(self):
        def fail(connection,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('INSERT INTO') and 'auth_session' in statement:
                raise OperationalError('fictional statement',None,Exception(PASSWORD))
        event.listen(self.engine,'before_cursor_execute',fail)
        try:
            status,data,headers=self.login()
        finally:
            event.remove(self.engine,'before_cursor_execute',fail)
        self.assertEqual(status,503)
        self.assertNotIn(PASSWORD,json.dumps(data))
        self.assertNotIn('set-cookie',headers)
        self.assertEqual(self.snapshot()['auth_session'],[])

    def test_auth_config_has_no_dotenv_or_secret_repr(self):
        with patch('dotenv.dotenv_values',side_effect=AssertionError('File forbidden')):
            for env in ('development','test','production'):
                settings=load_auth_settings(environ=ENV|{'APP_ENV':env})
                self.assertNotIn(ENV['AUTH_CSRF_KEY'],repr(settings))
            for changes in ({'AUTH_CSRF_KEY':''},{'AUTH_ALLOWED_ORIGINS':'*'},
                            {'AUTH_ALLOWED_ORIGINS':'http://expense.test'}):
                with self.assertRaises(ValueError):
                    load_auth_settings(environ=ENV|changes)

    def test_no_secret_console_output(self):
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(output):
            self.credentials()
        self.assertEqual(output.getvalue(),'')
