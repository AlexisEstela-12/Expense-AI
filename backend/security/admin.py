"""Explicit initial-account administration; never run during web startup."""
from datetime import datetime, timezone
import getpass
import re
import warnings

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .models import AuthUser
from .primitives import hash_password, InvalidSecurityInput


class AdministrationError(ValueError):
    """Safe operational message, with no submitted values or SQL details."""


def create_initial_user(session, username, password):
    """Use a dedicated administrative Session; never creates tables."""
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', username):
        raise AdministrationError('Nombre de usuario invalido.')
    try:
        with session.begin():
            if session.scalar(select(AuthUser.id).limit(1)) is not None:
                raise AdministrationError('La cuenta local ya existe.')
            encoded = hash_password(password)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(AuthUser(id=1, username=username, password_hash=encoded,
                                 active=True, created_at=now, password_changed_at=now))
            session.flush()
    except IntegrityError:
        # The singleton constraint also wins races between concurrent commands.
        raise AdministrationError('No se pudo crear la cuenta local; compruebe si ya existe.') from None
    except SQLAlchemyError:
        raise AdministrationError('No se pudo crear la cuenta local; revise la base y la migracion.') from None
    except InvalidSecurityInput:
        raise AdministrationError('Contrasena invalida.') from None


def main(argv=None, *, session_factory=None):
    import argparse
    parser = argparse.ArgumentParser(description='Administracion local de Expense AI')
    parser.add_argument('command', choices=['create-user'])
    parser.parse_args(argv)
    try:
        username = input('Usuario: ')
        # Fail closed if getpass would fall back to visible input.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Contrasena: ')
            confirmation = getpass.getpass('Confirmar contrasena: ')
        if password != confirmation:
            raise AdministrationError('Las contrasenas no coinciden.')
        if session_factory is None:
            # Only an explicit command imports real connection configuration.
            if __package__.startswith('backend.'):
                from ..db.session import SessionLocal
            else:
                from db.session import SessionLocal
            session_factory = SessionLocal
        with session_factory() as session:
            create_initial_user(session, username, password)
    except (AdministrationError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print('No se pudo crear la cuenta. Revise la entrada o el estado de la cuenta local.')
        return 1
    except Exception:
        print('No se pudo crear la cuenta. Revise la configuracion y la migracion.')
        return 1
    print('Cuenta local creada.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
