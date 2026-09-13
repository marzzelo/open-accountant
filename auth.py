"""FastAPI auth dependency helpers."""

import hmac

from fastapi import HTTPException, Request, status

import app_config
from database import get_db
from services import auth_service
from services.errors import NotFoundError, ValidationError


def _api_key_user(request: Request) -> dict | None:
    """Resolve the user behind an ``X-API-Key`` header, if one is present.

    Returns ``None`` when the header is absent or no key is configured, so the
    caller falls back to cookie authentication. Raises 401/403 when the header
    is present but unusable.
    """
    provided = request.headers.get(app_config.API_KEY_HEADER)
    if not provided:
        return None

    expected = app_config.api_key()
    if not expected or not hmac.compare_digest(provided.strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    username = app_config.api_key_username()
    with get_db() as conn:
        try:
            user = auth_service.get_user_by_username(conn, username)
        except NotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"API key user '{username}' does not exist",
            ) from exc

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="API key user is disabled"
        )

    request.state.current_user = user
    return user


def require_authenticated_user(request: Request) -> dict:
    if not app_config.auth_enabled():
        return {
            "id": None,
            "username": "anonymous",
            "is_admin": True,
            "is_active": True,
        }

    api_key_user = _api_key_user(request)
    if api_key_user is not None:
        return api_key_user

    token = request.cookies.get(app_config.auth_cookie_name())
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    with get_db() as conn:
        bootstrap_status = auth_service.auth_bootstrap_status(conn)
        if bootstrap_status["requires_setup"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=bootstrap_status["message"],
            )
        try:
            session = auth_service.get_session(conn, token)
        except (NotFoundError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
            ) from exc

    request.state.current_user = session["user"]
    return session["user"]


def require_admin_user(request: Request) -> dict:
    user = getattr(request.state, "current_user", None)
    if user is None:
        user = require_authenticated_user(request)
    if not bool(user.get("is_admin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
