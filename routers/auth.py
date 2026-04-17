"""Authentication HTTP endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import app_config
from auth import require_admin_user
from database import db_dep, get_db
from models import (
    LoginIn,
    SessionOut,
    UserCreateIn,
    UserUpdateIn,
    UserOut,
    UserPasswordUpdateIn,
    UserStatusUpdateIn,
)
from services import auth_service
from services.errors import NotFoundError, ValidationError

router = APIRouter()


def _set_session_cookie(response: Response, token: str, remember_me: bool):
    cookie_kwargs = {
        "key": app_config.auth_cookie_name(),
        "value": token,
        "httponly": True,
        "secure": app_config.auth_cookie_secure(),
        "samesite": "lax",
        "path": "/",
    }
    if remember_me:
        cookie_kwargs["max_age"] = (
            app_config.auth_session_days_remember_me() * 24 * 60 * 60
        )
    response.set_cookie(**cookie_kwargs)


def _clear_session_cookie(response: Response):
    response.delete_cookie(
        key=app_config.auth_cookie_name(),
        httponly=True,
        secure=app_config.auth_cookie_secure(),
        samesite="lax",
        path="/",
    )


@router.get("/auth/session", response_model=SessionOut)
def get_session(request: Request):
    if not app_config.auth_enabled():
        return SessionOut(authenticated=True, user=None, remember_me=False)

    with get_db() as conn:
        bootstrap_status = auth_service.auth_bootstrap_status(conn)
        token = request.cookies.get(app_config.auth_cookie_name())
        if not token:
            return SessionOut(authenticated=False, **bootstrap_status)
        try:
            session = auth_service.get_session(conn, token)
        except (NotFoundError, ValidationError):
            return SessionOut(authenticated=False, **bootstrap_status)

    return SessionOut(authenticated=True, **session, **bootstrap_status)


@router.post("/auth/login", response_model=SessionOut)
def login(data: LoginIn, response: Response):
    if not app_config.auth_enabled():
        return SessionOut(authenticated=True, user=None, remember_me=False)

    with get_db() as conn:
        bootstrap_status = auth_service.auth_bootstrap_status(conn)
        if bootstrap_status["requires_setup"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=bootstrap_status["message"],
            )
        try:
            user = auth_service.authenticate_user(conn, data.username, data.password)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
            ) from exc
        session = auth_service.create_session(conn, user["id"], data.remember_me)

    _set_session_cookie(response, session["token"], session["remember_me"])
    return SessionOut(
        authenticated=True,
        user=user,
        expires_at=session["expires_at"],
        remember_me=session["remember_me"],
    )


@router.post("/auth/logout", response_model=SessionOut)
def logout(request: Request, response: Response):
    if app_config.auth_enabled():
        token = request.cookies.get(app_config.auth_cookie_name())
        if token:
            with get_db() as conn:
                auth_service.delete_session(conn, token)
    _clear_session_cookie(response)
    return SessionOut(authenticated=False, remember_me=False)


@router.get("/auth/users", response_model=list[UserOut])
def list_users(
    _current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return auth_service.list_users(conn)


@router.post("/auth/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreateIn,
    _current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return auth_service.create_user(conn, data.username, data.password, data.is_admin)


@router.put("/auth/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdateIn,
    current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return auth_service.update_user(
        conn,
        user_id,
        data.username,
        data.is_admin,
        current_user["id"],
    )


@router.put("/auth/users/{user_id}/password", response_model=UserOut)
def update_user_password(
    user_id: int,
    data: UserPasswordUpdateIn,
    _current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return auth_service.update_user_password(conn, user_id, data.password)


@router.put("/auth/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: int,
    data: UserStatusUpdateIn,
    current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return auth_service.update_user_status(
        conn, user_id, data.is_active, current_user["id"]
    )


@router.delete("/auth/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    auth_service.delete_user(conn, user_id, current_user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
