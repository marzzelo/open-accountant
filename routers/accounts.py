"""routers/accounts.py — HTTP adapter for account services."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import AccountIn, AccountOut, AccountUpdate
from services import accounts_service
from services.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter()


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    with get_db() as conn:
        return accounts_service.list_accounts(conn, from_date, to_date)


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    with get_db() as conn:
        try:
            return accounts_service.get_account(conn, account_id, from_date, to_date)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn):
    with get_db() as conn:
        try:
            return accounts_service.create_account(conn, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountUpdate):
    with get_db() as conn:
        try:
            return accounts_service.update_account(conn, account_id, data)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int):
    with get_db() as conn:
        try:
            accounts_service.delete_account(conn, account_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
