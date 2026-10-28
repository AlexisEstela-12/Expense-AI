"""Deterministic out-of-order requests; SQLite memory and fictitious sessions only."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import timedelta
from threading import Barrier, Event
import unittest

from fastapi import Depends, FastAPI
from sqlalchemy import event, select, update

from security.dependencies import create_authentication_dependency
from security.models import AuthSession
from security.router import create_router
import test_auth_endpoints as fixtures


class SessionConcurrencyTest(unittest.TestCase):
    setUpClass = classmethod(fixtures.AuthEndpointsTest.setUpClass.__func__)
    request = fixtures.AuthEndpointsTest.request
    login = fixtures.AuthEndpointsTest.login
    credentials = fixtures.AuthEndpointsTest.credentials
    snapshot = fixtures.AuthEndpointsTest.snapshot

    def setUp(self):
        fixtures.AuthEndpointsTest.setUp(self)

    def make_app(self):
        self.clock = ContextVar('request_clock', default=self.now)

        def db():
            with self.sessions() as session:
                yield session

        app = FastAPI()
        app.include_router(create_router(db, settings_provider=lambda: self.settings,
                                         now_provider=self.clock.get))
        auth = create_authentication_dependency(db, settings_provider=lambda: self.settings,
                                                now_provider=self.clock.get)

        @app.get('/probe', dependencies=[Depends(auth)])
        @app.post('/probe', dependencies=[Depends(auth)])
        def probe():
            return {'ok': True}

        return app

    def saved_session(self):
        with self.sessions() as session:
            row = session.scalars(select(AuthSession)).one()
            return row.last_seen_at, row.idle_expires_at, row.expires_at, row.revoked_at

    def test_eight_out_of_order_requests_all_succeed_without_activity_regression(self):
        cookie, _ = self.credentials()
        barrier = Barrier(8)
        gates = [Event() for _ in range(8)]
        gates[7].set()
        observed = []

        def request(index):
            self.clock.set(self.now + timedelta(milliseconds=index + 1))
            barrier.wait(timeout=15)
            if not gates[index].wait(15):
                raise AssertionError('Request scheduling timed out')
            try:
                status = self.request('/probe', method='GET', cookie=cookie)[0]
                observed.append(self.saved_session())
                return status
            finally:
                if index:
                    gates[index - 1].set()

        # All request timestamps are captured first. Execute newest first to
        # reproduce SQL writer ordering without concurrent SQLite connection use.
        with ThreadPoolExecutor(8) as pool:
            statuses = list(pool.map(request, range(8)))
        self.assertEqual(statuses, [200] * 8)
        latest = self.now + timedelta(milliseconds=8)
        for activity, idle, absolute, revoked in observed:
            self.assertEqual(activity, latest)
            self.assertEqual(idle, latest + timedelta(minutes=30))
            self.assertEqual(absolute, self.now + timedelta(hours=12))
            self.assertIsNone(revoked)

    def test_out_of_order_activity_preserves_absolute_expiration(self):
        cookie, _ = self.credentials()
        with self.sessions() as session:
            row = session.scalars(select(AuthSession)).one()
            row.last_seen_at = self.now + timedelta(hours=11, minutes=50)
            row.idle_expires_at = row.expires_at
            session.commit()
        for minutes in (59, 58):
            self.clock.set(self.now + timedelta(hours=11, minutes=minutes))
            self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 200)
            activity, idle, absolute, _ = self.saved_session()
            self.assertEqual(activity, self.now + timedelta(hours=11, minutes=59))
            self.assertEqual(idle, absolute)
        self.clock.set(self.now + timedelta(hours=12))
        self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 401)

    def test_atomic_update_preserves_activity_written_after_initial_read(self):
        cookie, _ = self.credentials()
        self.clock.set(self.now + timedelta(seconds=1))
        later = self.now + timedelta(seconds=10)
        injected = []

        def touch(connection, cursor, statement, parameters, context, executemany):
            compiled = context.compiled
            if (not injected and compiled is not None and
                    getattr(compiled.statement, 'is_update', False) and
                    compiled.statement.table.name == 'auth_session'):
                injected.append(True)
                connection.execute(update(AuthSession).values(
                    last_seen_at=later, idle_expires_at=later + timedelta(minutes=30)))

        event.listen(self.engine, 'before_cursor_execute', touch)
        try:
            self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 200)
        finally:
            event.remove(self.engine, 'before_cursor_execute', touch)
        self.assertEqual(injected, [True])
        activity, idle, absolute, revoked = self.saved_session()
        self.assertEqual(activity, later)
        self.assertEqual(idle, later + timedelta(minutes=30))
        self.assertEqual(absolute, self.now + timedelta(hours=12))
        self.assertIsNone(revoked)

    def test_already_revoked_idle_expired_and_absolute_expired_are_rejected(self):
        cookie, _ = self.credentials()
        for state in ('revoked', 'idle', 'absolute'):
            with self.subTest(state=state):
                with self.sessions() as session:
                    row = session.scalars(select(AuthSession)).one()
                    row.revoked_at = self.now if state == 'revoked' else None
                    row.idle_expires_at = self.now if state == 'idle' else self.now + timedelta(minutes=30)
                    row.expires_at = self.now if state == 'absolute' else self.now + timedelta(hours=12)
                    session.commit()
                self.clock.set(self.now + timedelta(seconds=1))
                before = self.snapshot()
                self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 401)
                self.assertEqual(self.snapshot(), before)

    def test_zero_row_update_after_revocation_or_expiration_still_rejects(self):
        cookie, _ = self.credentials()
        self.clock.set(self.now + timedelta(seconds=1))
        for state in ('revoked', 'idle', 'absolute'):
            with self.subTest(state=state):
                injected = []
                affected = []

                def invalidate(connection, cursor, statement, parameters, context, executemany):
                    compiled = context.compiled
                    if (not injected and compiled is not None and
                            getattr(compiled.statement, 'is_update', False) and
                            compiled.statement.table.name == 'auth_session'):
                        injected.append(True)
                        values = {'revoked_at': self.now} if state == 'revoked' else {
                            ('idle_expires_at' if state == 'idle' else 'expires_at'): self.now}
                        # Inject the state change after validation, immediately
                        # before the real guarded UPDATE. Its zero-row result
                        # must reject; the enclosing transaction rolls back.
                        connection.execute(update(AuthSession).values(**values))

                def capture(connection, cursor, statement, parameters, context, executemany):
                    compiled = context.compiled
                    if (compiled is not None and getattr(compiled.statement, 'is_update', False)
                            and compiled.statement.table.name == 'auth_session'):
                        affected.append(cursor.rowcount)

                before = self.snapshot()
                event.listen(self.engine, 'before_cursor_execute', invalidate)
                event.listen(self.engine, 'after_cursor_execute', capture)
                try:
                    self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 401)
                finally:
                    event.remove(self.engine, 'before_cursor_execute', invalidate)
                    event.remove(self.engine, 'after_cursor_execute', capture)
                self.assertEqual(injected, [True])
                self.assertEqual(affected, [1, 0])
                self.assertEqual(self.snapshot(), before)

    def test_logout_with_older_timestamp_still_revokes(self):
        cookie, csrf = self.credentials()
        self.clock.set(self.now + timedelta(seconds=10))
        self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 200)
        self.clock.set(self.now + timedelta(seconds=5))
        self.assertEqual(self.request('/auth/logout', cookie=cookie, csrf=csrf)[0], 200)
        self.clock.set(self.now + timedelta(seconds=11))
        self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 401)

    def test_out_of_order_requests_cannot_bypass_csrf_or_origin(self):
        cookie, csrf = self.credentials()
        self.clock.set(self.now + timedelta(seconds=10))
        self.assertEqual(self.request('/probe', method='GET', cookie=cookie)[0], 200)
        self.clock.set(self.now + timedelta(seconds=5))
        for supplied, origin in ((None, fixtures.ORIGIN), ('invalid', fixtures.ORIGIN),
                                 (csrf, 'https://untrusted.test'), (csrf, None)):
            with self.subTest(csrf_present=supplied is not None, origin=origin):
                before = self.snapshot()
                self.assertEqual(self.request('/probe', cookie=cookie, csrf=supplied,
                                              origin=origin)[0], 403)
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.request('/probe', cookie=cookie, csrf=csrf)[0], 200)
