"""Bounded Argon2id, opaque sessions and expiry checks; no external I/O."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import Argon2Error, InvalidHashError

from .config import ABSOLUTE_TIMEOUT, IDLE_TIMEOUT

ARGON2_MEMORY_KIB = 65536
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 1
MIN_PASSWORD_CHARACTERS = 15
MAX_PASSWORD_BYTES = 1024
SESSION_BYTES = 32
_HASHER = PasswordHasher(memory_cost=ARGON2_MEMORY_KIB, time_cost=ARGON2_TIME_COST,
                         parallelism=ARGON2_PARALLELISM, salt_len=16, hash_len=32, type=Type.ID)
_TOKEN = re.compile(r'[A-Za-z0-9_-]{43}', re.ASCII)
_DIGEST = re.compile(r'[0-9a-f]{64}', re.ASCII)


class InvalidSecurityInput(ValueError):
    """Never includes the supplied password, identifier or hash."""


def _validate_password(password):
    if not isinstance(password, str) or not MIN_PASSWORD_CHARACTERS <= len(password) <= MAX_PASSWORD_BYTES:
        raise InvalidSecurityInput('Contrasena invalida.')
    try:
        encoded = password.encode('utf-8')
    except UnicodeError:
        raise InvalidSecurityInput('Contrasena invalida.') from None
    if len(encoded) > MAX_PASSWORD_BYTES or not password.strip():
        raise InvalidSecurityInput('Contrasena invalida.')


def hash_password(password: str) -> str:
    _validate_password(password)
    try:
        return _HASHER.hash(password)
    except Argon2Error:
        raise InvalidSecurityInput('No se pudo generar el hash.') from None


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        _validate_password(password)
        if not isinstance(encoded_hash, str) or len(encoded_hash) > 512:
            return False
        parameters = extract_parameters(encoded_hash)
        # Do not permit attacker-supplied PHC cost parameters to allocate
        # unbounded memory/CPU. This first version accepts our exact policy.
        if (parameters.type, parameters.version, parameters.memory_cost,
            parameters.time_cost, parameters.parallelism, parameters.salt_len,
            parameters.hash_len) != (Type.ID, 19, ARGON2_MEMORY_KIB, ARGON2_TIME_COST,
                                     ARGON2_PARALLELISM, 16, 32):
            return False
        return _HASHER.verify(encoded_hash, password)
    except (InvalidSecurityInput, Argon2Error, InvalidHashError, ValueError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_BYTES)


def _valid_token(token):
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return False
    raw = base64.urlsafe_b64decode(token + '=')
    return len(raw) == SESSION_BYTES and base64.urlsafe_b64encode(raw).decode().rstrip('=') == token


def hash_session_token(token: str) -> str:
    if not _valid_token(token):
        raise InvalidSecurityInput('Identificador de sesion invalido.')
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    return bool(_valid_token(left) and _valid_token(right) and hmac.compare_digest(left, right))


def hashes_equal(left: str, right: str) -> bool:
    return bool(isinstance(left, str) and isinstance(right, str) and
                _DIGEST.fullmatch(left) and _DIGEST.fullmatch(right) and
                hmac.compare_digest(left, right))


def session_expired(*, created_at: datetime, last_seen_at: datetime, now: datetime) -> bool:
    values = (created_at, last_seen_at, now)
    if any(not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None
           for value in values):
        raise InvalidSecurityInput('Fechas de sesion invalidas.')
    created_at, last_seen_at, now = (value.astimezone(timezone.utc) for value in values)
    if not created_at <= last_seen_at <= now:
        raise InvalidSecurityInput('Fechas de sesion invalidas.')
    return now - created_at >= ABSOLUTE_TIMEOUT or now - last_seen_at >= IDLE_TIMEOUT
