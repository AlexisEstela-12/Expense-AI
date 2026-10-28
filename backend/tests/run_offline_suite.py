"""Run unittest discovery with fail-closed isolation, including during imports.

Usage (from backend): .venv/Scripts/python tests/run_offline_suite.py [pattern]
Only tests/ is collected: test_azure.py is an external integration probe.
"""
import importlib.abc
import os
import platform
from pathlib import Path
import sys
import unittest


def forbidden(message):
    raise RuntimeError('Offline isolation: ' + message)


class BlockProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'main', 'backend.main', 'db.session', 'backend.db.session', 'pyodbc'}:
            forbidden('production module forbidden: ' + fullname)


def audit(event, args):
    # asyncio on Windows implements its internal wakeup pipe with a local
    # socketpair. Permit only that stdlib call stack, never HTTP clients.
    if event.startswith('socket.'):
        frame = sys._getframe(1)
        while frame:
            if (frame.f_code.co_name == '_fallback_socketpair' and
                    frame.f_globals.get('__name__') == 'socket'):
                return
            frame = frame.f_back
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo',
                 'socket.bind', 'subprocess.Popen', 'os.system'}:
        forbidden(event)
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.fsdecode(args[0]).replace('\\', '/').lower()
        name = path.rsplit('/', 1)[-1]
        if (name == '.env' or name.startswith('.env.') or
                name.endswith(('.db', '.sqlite', '.sqlite3', '.pem', '.key', '.pfx')) or
                (('credential' in name or 'secret' in name) and
                 not name.endswith(('.py', '.pyc', '.pyd'))) or '/.aws/' in path):
            forbidden('sensitive file access forbidden')


if __name__ == '__main__':
    # Windows' standard-library platform lookup runs `ver`; cache it before
    # forbidding child processes in application imports and tests.
    platform.uname()
    sys.meta_path.insert(0, BlockProduction())
    sys.addaudithook(audit)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import sqlalchemy
    from sqlalchemy.engine import make_url
    original_engine = sqlalchemy.create_engine

    def memory_engine(url, *args, **kwargs):
        parsed = make_url(url)
        if parsed.get_backend_name() != 'sqlite' or parsed.database != ':memory:':
            forbidden('only SQLite :memory: engines are allowed')
        return original_engine(url, *args, **kwargs)

    sqlalchemy.create_engine = memory_engine
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).parent), pattern=sys.argv[1] if len(sys.argv) > 1 else 'test_*.py',
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
