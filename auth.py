"""FastAPI auth dependency helpers."""

from fastapi import HTTPException, Request, status

import app_config
from database import get_db
from services import auth_service
from services.errors import NotFoundError, ValidationError


def require_authenticated_user(request: Request) -> dict:
    if not app_config.auth_enabled():
        return {
            "id": None,
            "username": "anonymous",
            "is_admin": True,
            "is_active": True,
        }

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
