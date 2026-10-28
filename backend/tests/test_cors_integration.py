"""Credentialed CORS against actual app wiring, SQLite and fictitious sessions."""
import unittest

from security.config import cors_options, load_auth_settings
import test_private_endpoints as private_fixtures
from test_auth_endpoints import ENV, ORIGIN, PASSWORD


class CorsIntegrationTest(unittest.TestCase):
    setUpClass = classmethod(private_fixtures.PrivateEndpointsTest.setUpClass.__func__)
    setUp = private_fixtures.PrivateEndpointsTest.setUp
    make_app = private_fixtures.PrivateEndpointsTest.make_app
    request = private_fixtures.PrivateEndpointsTest.request
    login = private_fixtures.PrivateEndpointsTest.login
    credentials = private_fixtures.PrivateEndpointsTest.credentials
    snapshot = private_fixtures.PrivateEndpointsTest.snapshot
    financial_io_forbidden = private_fixtures.PrivateEndpointsTest.financial_io_forbidden

    def test_development_default_matches_frontend_hostname(self):
        options=cors_options(environ={'APP_ENV':'development'})
        self.assertEqual(options['allow_origins'],['http://127.0.0.1:5173'])
        self.assertTrue(options['allow_credentials'])
        self.assertEqual(options['allow_methods'],['GET','POST'])
        self.assertEqual(options['allow_headers'],['Content-Type','X-CSRF-Token'])
        settings=load_auth_settings(environ={k:v for k,v in ENV.items() if k!='AUTH_ALLOWED_ORIGINS'}|
                                    {'APP_ENV':'development'})
        self.assertEqual(list(settings.allowed_origins),options['allow_origins'])

    def test_production_has_no_implicit_local_origins(self):
        self.assertEqual(cors_options(environ={'APP_ENV':'production'})['allow_origins'],[])
        for origin in ('http://127.0.0.1:5173','https://localhost','https://sub.localhost',
                       'https://127.0.0.1','https://[::1]','https://0.0.0.0',
                       'https://169.254.1.1','https://expense.local','*','https://*.example.test'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                cors_options(environ={'APP_ENV':'production','AUTH_ALLOWED_ORIGINS':origin})
        self.assertEqual(cors_options(environ={'APP_ENV':'production','AUTH_ALLOWED_ORIGINS':ORIGIN})
                         ['allow_origins'],[ORIGIN])

    def test_allowed_preflight_credentials_and_csrf_header(self):
        status,_,headers=self.request('/movements',method='OPTIONS',extra_headers={
            'access-control-request-method':'POST',
            'access-control-request-headers':'content-type,x-csrf-token'})
        self.assertEqual(status,200)
        self.assertEqual(headers['access-control-allow-origin'],ORIGIN)
        self.assertEqual(headers['access-control-allow-credentials'],'true')
        self.assertIn('X-CSRF-Token',headers['access-control-allow-headers'])
        self.assertNotIn('set-cookie',headers)

    def test_untrusted_preflight_method_and_headers_are_rejected(self):
        before=self.snapshot()
        for origin,method,header in [('https://evil.test','POST','content-type'),
                                     (ORIGIN,'DELETE','content-type'),(ORIGIN,'POST','authorization')]:
            status,_,headers=self.request('/movements',method='OPTIONS',origin=origin,extra_headers={
                'access-control-request-method':method,'access-control-request-headers':header})
            self.assertEqual(status,400)
            if origin!=ORIGIN:self.assertNotIn('access-control-allow-origin',headers)
        self.assertEqual(self.snapshot(),before)

    def test_login_session_write_and_logout_keep_cors_csrf_and_cookies(self):
        status,data,headers=self.login()
        self.assertEqual(status,200)
        self.assertEqual(headers['access-control-allow-origin'],ORIGIN)
        self.assertEqual(headers['access-control-allow-credentials'],'true')
        self.assertIn('HttpOnly',headers['set-cookie'])
        cookie=headers['set-cookie'].split(';')[0]
        csrf=data['csrf_token']
        status,restored,_=self.request('/auth/session',method='GET',cookie=cookie)
        self.assertEqual(status,200)
        self.assertEqual(restored['csrf_token'],csrf)
        payload={'date':'2026-10-27','kind':'expense','currency':'PEN','amount':'1.00','category':'Ficticio'}
        self.assertEqual(self.request('/movements',payload,cookie=cookie)[0],403)
        self.assertEqual(self.request('/movements',payload,cookie=cookie,csrf=csrf)[0],201)
        self.assertEqual(self.request('/auth/logout',cookie=cookie,csrf=csrf)[0],200)
        self.assertEqual(self.request('/summary',method='GET',cookie=cookie)[0],401)

    def test_cors_does_not_authenticate_or_allow_untrusted_writes(self):
        with self.financial_io_forbidden():
            self.assertEqual(self.request('/summary',method='GET')[0],401)
        cookie,csrf=self.credentials()
        before=self.snapshot()
        with self.financial_io_forbidden():
            status,_,headers=self.request('/movements',{},cookie=cookie,csrf=csrf,origin='https://evil.test')
        self.assertEqual(status,403)
        self.assertNotIn('access-control-allow-origin',headers)
        self.assertEqual(self.snapshot(),before)

    def test_429_is_readable_by_allowed_credentialed_frontend(self):
        for _ in range(5):
            self.assertEqual(self.request('/auth/login',{'username':'wrong','password':PASSWORD},csrf='login')[0],401)
        status,_,headers=self.login()
        self.assertEqual(status,429)
        self.assertEqual(headers['access-control-allow-origin'],ORIGIN)
        self.assertEqual(headers['access-control-allow-credentials'],'true')
