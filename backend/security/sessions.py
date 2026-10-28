"""Persistent auth operations. Caller supplies a dedicated transaction-free Session."""
from datetime import timedelta
from functools import lru_cache
import hashlib
import hmac
import secrets

from sqlalchemy import select, update, case
from sqlalchemy.exc import IntegrityError

from .config import ABSOLUTE_TIMEOUT, IDLE_TIMEOUT
from .models import AuthUser, AuthSession, AuthLoginLimit
from .primitives import generate_session_token, hash_session_token, hash_password, verify_password, InvalidSecurityInput

LOGIN_WINDOW = timedelta(minutes=15)


class AuthRejected(Exception):
    def __init__(self, status, detail, retry_after=None):
        self.status, self.detail, self.retry_after = status, detail, retry_after
        super().__init__(detail)


@lru_cache(maxsize=1)
def _dummy_hash():
    return hash_password(secrets.token_urlsafe(32))


def csrf_token(token, key):
    return hmac.new(key, b'expense-csrf-v1:' + token.encode('ascii'), hashlib.sha256).hexdigest()


def _reserve_attempt(session, key, limit, now):
    digest = hashlib.sha256(key.encode()).hexdigest()
    table = AuthLoginLimit
    expired = table.window_expires_at <= now
    statement = update(table).where(table.key_hash == digest,
        expired | (table.attempts < limit)).values(
            attempts=case((expired, 1), else_=table.attempts + 1),
            window_started_at=case((expired, now), else_=table.window_started_at),
            window_expires_at=case((expired, now + LOGIN_WINDOW), else_=table.window_expires_at),
            next_allowed_at=None)
    if session.execute(statement).rowcount == 1:
        return
    if session.get(table, digest) is None:
        try:
            with session.begin_nested():
                session.add(table(key_hash=digest, window_started_at=now,
                                  window_expires_at=now+LOGIN_WINDOW, attempts=1))
                session.flush()
            return
        except IntegrityError:
            # Another replica inserted the key. Retry the same atomic claim.
            if session.execute(statement).rowcount == 1:
                return
    row = session.get(table, digest, populate_existing=True)
    wait = max(1, int((row.window_expires_at-now).total_seconds()))
    raise AuthRejected(429, 'Demasiados intentos. Intente mas tarde.', wait)


def login(session, username, password, peer, now):
    # Reserve shared counters before Argon2. These committed audit writes are
    # deliberate even for wrong credentials; denied claims roll back together.
    with session.begin():
        _reserve_attempt(session, 'login-global', 20, now)
        _reserve_attempt(session, 'login-peer:' + peer, 5, now)
        user = session.get(AuthUser, 1)
        encoded = user.password_hash if user is not None else _dummy_hash()
        valid_password = verify_password(password, encoded)
        allowed = (user is not None and user.active and
                   hmac.compare_digest(username.encode('utf-8'), user.username.encode('utf-8')) and
                   valid_password)
        identity = (user.id, user.username) if allowed else None
    if identity is None:
        raise AuthRejected(401, 'Credenciales incorrectas.')
    token = generate_session_token()
    digest = hash_session_token(token)
    with session.begin():
        # Recheck state after the reserved attempt transaction.
        user = session.get(AuthUser, identity[0], populate_existing=True)
        if not user.active or user.password_hash != encoded:
            raise AuthRejected(401, 'Credenciales incorrectas.')
        session.add(AuthSession(token_hash=digest, user_id=user.id, created_at=now,
                    last_seen_at=now, idle_expires_at=now+IDLE_TIMEOUT,
                    expires_at=now+ABSOLUTE_TIMEOUT))
        session.flush()
    return token, identity, now+ABSOLUTE_TIMEOUT


def current_session(session, token, key, supplied_csrf, now, *, logout=False):
    try:
        digest = hash_session_token(token)
    except InvalidSecurityInput:
        raise AuthRejected(401, 'Sesion no valida.') from None
    with session.begin():
        row = session.get(AuthSession, digest)
        if row is None or row.revoked_at is not None or now >= row.expires_at or now >= row.idle_expires_at:
            raise AuthRejected(401, 'Sesion no valida.')
        user = session.get(AuthUser, row.user_id)
        if user is None or not user.active or row.created_at < user.password_changed_at:
            raise AuthRejected(401, 'Sesion no valida.')
        expected_csrf = csrf_token(token, key)
        if logout and (not isinstance(supplied_csrf, str) or len(supplied_csrf) != 64 or
                       not supplied_csrf.isascii() or not hmac.compare_digest(supplied_csrf, expected_csrf)):
            raise AuthRejected(403, 'Solicitud no permitida.')
        values = {'revoked_at': now} if logout else {
            'last_seen_at': now, 'idle_expires_at': min(now+IDLE_TIMEOUT, row.expires_at)}
        result = session.execute(update(AuthSession).where(
            AuthSession.token_hash == digest, AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now, AuthSession.idle_expires_at > now,
            AuthSession.last_seen_at <= now).values(**values))
        if result.rowcount != 1:
            raise AuthRejected(401, 'Sesion no valida.')
        return {'user': {'id': user.id, 'username': user.username},
                'csrf_token': expected_csrf, 'expires_at': row.expires_at.isoformat()+'Z'}
