"""Security policy with no file reads, secrets or import-time configuration."""
from dataclasses import dataclass, field
import base64
from datetime import timedelta
import os
from typing import Mapping
from urllib.parse import urlsplit

if __package__.startswith('backend.'):
    from ..core.config import APP_ENVIRONMENTS, ConfigurationError
else:
    from core.config import APP_ENVIRONMENTS, ConfigurationError

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=12)


@dataclass(frozen=True)
class SecuritySettings:
    app_env: str
    cookie_name: str
    cookie_secure: bool
    cookie_httponly: bool = True
    cookie_samesite: str = 'lax'
    cookie_path: str = '/'
    cookie_domain: None = None
    idle_timeout: timedelta = IDLE_TIMEOUT
    absolute_timeout: timedelta = ABSOLUTE_TIMEOUT


def load_security_settings(*, app_env: str | None = None,
                           environ: Mapping[str, str] | None = None) -> SecuritySettings:
    # Security policy never requires or loads dotenv, including development.
    process = os.environ if environ is None else environ
    selected = app_env if app_env is not None else process.get('APP_ENV')
    if selected not in APP_ENVIRONMENTS:
        raise ConfigurationError('APP_ENV debe ser development, test o production.')
    development = selected == 'development'
    return SecuritySettings(selected,
                            'expense_session_dev' if development else '__Host-expense_session',
                            not development)


@dataclass(frozen=True)
class AuthSettings:
    cookies: SecuritySettings
    allowed_origins: tuple[str, ...]
    csrf_key: bytes = field(repr=False)


def load_auth_settings(*, environ: Mapping[str, str] | None = None) -> AuthSettings:
    process = os.environ if environ is None else environ
    cookies = load_security_settings(environ=process)
    try:
        origins = tuple(process.get('AUTH_ALLOWED_ORIGINS', '').split(','))
        for origin in origins:
            parsed = urlsplit(origin)
            parsed.port  # Validate a supplied port without retaining its value.
            if ('*' in origin or not parsed.hostname or parsed.username or parsed.password or parsed.query or
                    parsed.fragment or parsed.path or origin != origin.strip() or
                    parsed.scheme not in ('http', 'https') or
                    (cookies.app_env != 'development' and parsed.scheme != 'https')):
                raise ValueError
        encoded = process.get('AUTH_CSRF_KEY', '')
        key = base64.b64decode(encoded, altchars=b'-_', validate=True)
        if len(key) != 32:
            raise ValueError
    except (ValueError, TypeError):
        raise ConfigurationError('Configuracion de autenticacion invalida: AUTH_ALLOWED_ORIGINS, AUTH_CSRF_KEY.') from None
    return AuthSettings(cookies, origins, key)


def documentation_options(*, environ: Mapping[str, str] | None = None):
    settings = load_security_settings(environ=environ)
    if settings.app_env == 'production':
        return {'docs_url': None, 'redoc_url': None, 'openapi_url': None}
    return {}
