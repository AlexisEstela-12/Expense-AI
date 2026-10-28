"""Central authentication dependency; no network identity or financial queries."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from .config import load_auth_settings
from .router import utc_now
from .sessions import AuthRejected, current_session


def create_authentication_dependency(db, *, settings_provider=load_auth_settings,
                                     now_provider=utc_now):
    def require_authenticated_user(request: Request, session=Depends(db)):
        try:
            settings = settings_provider()
            unsafe = request.method not in ('GET', 'HEAD', 'OPTIONS')

            def validate_request():
                origin = request.headers.get('origin')
                if ((unsafe and origin is None) or
                    (origin is not None and origin not in settings.allowed_origins) or
                    request.headers.get('sec-fetch-site') == 'cross-site'):
                    raise AuthRejected(403, 'Solicitud no permitida.')

            result = current_session(session, request.cookies.get(settings.cookies.cookie_name),
                settings.csrf_key, request.headers.get('x-csrf-token'), now_provider(),
                require_csrf=unsafe, validate_request=validate_request)
            request.state.authenticated_user = result['user']
            return result['user']
        except AuthRejected as error:
            raise HTTPException(error.status, error.detail, headers={'Cache-Control': 'no-store'}) from None
        except (SQLAlchemyError, ValueError):
            raise HTTPException(503, 'Autenticacion no disponible.',
                                headers={'Cache-Control': 'no-store'}) from None
    return require_authenticated_user
