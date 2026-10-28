"""Import/lifespan regression with a fake db.session and no external I/O.

Run directly for a fresh isolated process; also collected by run_offline_suite.
The OpenAPI fixture was captured from the previous main.py with its single
create_all statement removed in memory, before changing the production file.
"""
import ast
import asyncio
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, event, MetaData, Table
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


@contextmanager
def isolated_app(source):
    """Never import production connection configuration, even for the baseline."""
    engine = create_engine('sqlite+pysqlite:///:memory:')
    fake = ModuleType('db.session')
    fake.connection_string = 'fictional-offline-connection'
    fake.DB_URL = 'sqlite+pysqlite:///:memory:'
    fake.engine = engine
    fake.SessionLocal = sessionmaker(bind=engine)
    module = ModuleType('_isolated_expense_app')
    module.__package__ = ''
    module.__file__ = str(ROOT / 'main.py')
    module.registered_routers = []
    include_router = FastAPI.include_router

    def record_router(app, router, *args, **kwargs):
        module.registered_routers.append(router)
        return include_router(app, router, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError('Startup must not connect or execute SQL/DDL')

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {'db.session': fake}))
            stack.enter_context(patch.object(FastAPI, 'include_router', record_router))
            stack.enter_context(patch.object(Engine, 'connect', side_effect=forbidden))
            for owner, names in ((MetaData, ('create_all', 'drop_all')),
                                 (Table, ('create', 'drop'))):
                for name in names:
                    stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            stack.enter_context(patch('dotenv.load_dotenv', side_effect=forbidden))
            stack.enter_context(patch('openai.OpenAI', side_effect=forbidden))
            event.listen(engine, 'before_cursor_execute', forbidden)
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
            yield module
    finally:
        engine.dispose()


class StartupIsolationTest(unittest.TestCase):
    def test_main_has_no_schema_calls_and_keeps_original_plus_auth_routers(self):
        tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and
                             node.func.attr in {'create_all', 'drop_all'} for node in calls))
        self.assertEqual(sum(isinstance(node.func, ast.Attribute) and
                             node.func.attr == 'include_router' for node in calls), 12)

    def test_import_lifespan_health_and_openapi_without_connections_or_ddl(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        reference = json.loads((ROOT / 'tests/fixtures/openapi_before_startup_fix.json').read_text(encoding='utf-8'))
        with isolated_app(source) as module:
            app = module.app
            self.assertEqual(len(module.registered_routers), 12)
            routes = [r for router in module.registered_routers for r in router.routes
                      if isinstance(r, APIRoute)]
            self.assertEqual(sum(len(r.methods) for r in routes), 27)
            schema = app.openapi()
            self.assertEqual(set(schema['paths']) - set(reference['paths']),
                             {'/auth/login', '/auth/session', '/auth/logout'})
            original = dict(schema)
            original['paths'] = {path: value for path, value in schema['paths'].items()
                                 if not path.startswith('/auth/')}
            self.assertEqual(original, reference)
            for route in routes:
                if route.path != '/health':
                    self.assertIs(route.dependant.dependencies[0].call, module.db)

            async def startup_and_health():
                async with app.router.lifespan_context(app):
                    messages = []

                    async def receive():
                        return {'type': 'http.request', 'body': b'', 'more_body': False}

                    async def send(message):
                        messages.append(message)

                    await app({'type': 'http', 'asgi': {'version': '3.0'},
                               'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
                               'path': '/health', 'raw_path': b'/health', 'query_string': b'',
                               'root_path': '', 'headers': [],
                               'client': ('127.0.0.1', 50000), 'server': ('test.invalid', 80)},
                              receive, send)
                    self.assertEqual(next(m['status'] for m in messages
                                          if m['type'] == 'http.response.start'), 200)
                    self.assertEqual(json.loads(b''.join(m.get('body', b'') for m in messages
                                                        if m['type'] == 'http.response.body')),
                                     {'status': 'ok'})

            asyncio.run(startup_and_health())

    def test_guard_rejects_reintroduced_import_or_lifespan_ddl(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        for addition in ('\nBase.metadata.create_all(engine)\n',
                         '\nfrom contextlib import asynccontextmanager\n'
                         '@asynccontextmanager\nasync def accidental_ddl(app):\n'
                         '    Base.metadata.create_all(engine)\n    yield\n'
                         'app.router.lifespan_context = accidental_ddl\n'):
            with self.subTest(addition=addition), self.assertRaisesRegex(AssertionError, 'must not connect'):
                with isolated_app(source + addition) as module:
                    async def startup():
                        async with module.app.router.lifespan_context(module.app):
                            pass
                    asyncio.run(startup())


if __name__ == '__main__':
    # Install the same file/network guard as the financial suite before any
    # application imports. Only internal asyncio socketpairs are permitted.
    import platform
    from run_offline_suite import audit
    platform.uname()
    sys.addaudithook(audit)
    unittest.main(verbosity=2)
