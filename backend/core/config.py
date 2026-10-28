"""SQL configuration loaded explicitly, never as an import side effect."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

DB_VARIABLES = ('DB_SERVER', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')
APP_ENVIRONMENTS = ('development', 'test', 'production')


class ConfigurationError(ValueError):
    """A configuration error containing names only, never supplied values."""


def _odbc_value(value: str) -> str:
    # ODBC braced values preserve delimiters and surrounding spaces. A right
    # brace inside a value is escaped by doubling it (MS-ODBCSTR).
    return '{' + value.replace('}', '}}') + '}'


@dataclass(frozen=True)
class DatabaseSettings:
    app_env: str
    server: str = field(repr=False)
    name: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)

    def odbc_connection_string(self) -> str:
        return (
            'DRIVER={ODBC Driver 18 for SQL Server};'
            f'SERVER={_odbc_value("tcp:" + self.server + ",1433")};'
            f'DATABASE={_odbc_value(self.name)};'
            f'UID={_odbc_value(self.user)};'
            f'PWD={_odbc_value(self.password)};'
            'Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
        )


def load_database_settings(*, app_env: str | None = None,
                           environ: Mapping[str, str] | None = None) -> DatabaseSettings:
    process = dict(os.environ if environ is None else environ)
    selected = app_env if app_env is not None else process.get('APP_ENV')
    if selected is None:
        raise ConfigurationError('Configuracion incompleta: APP_ENV.')
    if selected not in APP_ENVIRONMENTS:
        raise ConfigurationError('APP_ENV debe ser development, test o production.')

    values = {}
    if selected == 'development':
        # Lazy import: importing core.config does not even import dotenv.
        from dotenv import dotenv_values
        try:
            values = dict(dotenv_values(
                Path(__file__).resolve().parents[1] / '.env', interpolate=False,
            ))
        except Exception:
            raise ConfigurationError('No se pudo cargar la configuracion local.') from None
    values.update(process)
    invalid = [name for name in DB_VARIABLES
               if not isinstance(values.get(name), str) or not values[name].strip()]
    if invalid:
        raise ConfigurationError('Configuracion incompleta: ' + ', '.join(invalid) + '.')
    return DatabaseSettings(selected, *(values[name] for name in DB_VARIABLES))
