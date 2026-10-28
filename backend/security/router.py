"""Only local-auth endpoints; existing financial/chat routes are untouched."""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from .config import load_auth_settings
from .sessions import AuthRejected, login, current_session, csrf_token


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_router(db, *, settings_provider=load_auth_settings, now_provider=utc_now):
    router = APIRouter()

    def response(data, status=200, retry=None):
        headers = {'Cache-Control': 'no-store', 'Pragma': 'no-cache'}
        if retry is not None:
            headers['Retry-After'] = str(retry)
        return JSONResponse(data, status_code=status, headers=headers)

    def origin(request, settings, required):
        value = request.headers.get('origin')
        if (value is None and required) or (value is not None and value not in settings.allowed_origins):
            raise AuthRejected(403, 'Solicitud no permitida.')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise AuthRejected(403, 'Solicitud no permitida.')

    def failure(error):
        if isinstance(error, AuthRejected):
            return response({'detail': error.detail}, error.status, error.retry_after)
        return response({'detail': 'Autenticacion no disponible.'}, 503)

    @router.post('/auth/login')
    async def login_endpoint(request: Request, session=Depends(db)):
        try:
            settings = settings_provider()
            origin(request, settings, True)
            # Public marker + JSON + exact Origin protect login against CSRF.
            # Authenticated operations use the secret session-bound token.
            if (request.headers.get('x-csrf-token') != 'login' or
                request.headers.get('content-type', '').split(';')[0].strip() != 'application/json'):
                raise AuthRejected(403, 'Solicitud no permitida.')
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4096:
                    raise AuthRejected(400, 'Solicitud invalida.')
                body.extend(chunk)
            try:
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {'username', 'password'}:
                    raise ValueError
                username, password = payload['username'], payload['password']
                if (not isinstance(username, str) or not 1 <= len(username) <= 128 or
                    not isinstance(password, str) or not 1 <= len(password) <= 1024):
                    raise ValueError
                username.encode('utf-8'); password.encode('utf-8')
            except (ValueError, TypeError, UnicodeError, RecursionError):
                raise AuthRejected(400, 'Solicitud invalida.') from None
            token, identity, expires = await run_in_threadpool(login, session, username, password,
                request.client.host if request.client else 'unknown', now_provider())
            result = response({'user': {'id': identity[0], 'username': identity[1]},
                               'csrf_token': csrf_token(token, settings.csrf_key),
                               'expires_at': expires.isoformat()+'Z'})
            cookies = settings.cookies
            result.set_cookie(cookies.cookie_name, token, max_age=43200, httponly=True,
                              secure=cookies.cookie_secure, samesite=cookies.cookie_samesite,
                              path=cookies.cookie_path)
            return result
        except (AuthRejected, SQLAlchemyError, ValueError) as error:
            return failure(error)

    def session_endpoint(request, session, logout):
        try:
            settings = settings_provider()
            origin(request, settings, logout)
            result = current_session(session, request.cookies.get(settings.cookies.cookie_name),
                       settings.csrf_key, request.headers.get('x-csrf-token'), now_provider(), logout=logout)
            if not logout:
                return response(result)
            result = response({'status': 'ok'})
            result.delete_cookie(settings.cookies.cookie_name, path=settings.cookies.cookie_path,
                                 secure=settings.cookies.cookie_secure, httponly=True,
                                 samesite=settings.cookies.cookie_samesite)
            return result
        except (AuthRejected, SQLAlchemyError, ValueError) as error:
            return failure(error)

    @router.get('/auth/session')
    def get_session(request: Request, session=Depends(db)):
        return session_endpoint(request, session, False)

    @router.post('/auth/logout')
    def logout_endpoint(request: Request, session=Depends(db)):
        return session_endpoint(request, session, True)

    return router
