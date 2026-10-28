"""Security policy with no file reads, secrets or import-time configuration."""
from dataclasses import dataclass
from datetime import timedelta
import os
from typing import Mapping

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
