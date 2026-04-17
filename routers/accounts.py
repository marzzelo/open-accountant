"""routers/accounts.py — HTTP adapter for account services."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from database import db_dep
from models import AccountIn, AccountOut, AccountUpdate
from services import accounts_service

router = APIRouter()


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    conn=Depends(db_dep),
):
    return accounts_service.list_accounts(conn, from_date, to_date)


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    conn=Depends(db_dep),
):
    return accounts_service.get_account(conn, account_id, from_date, to_date)


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, conn=Depends(db_dep)):
    return accounts_service.create_account(conn, data)


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountUpdate, conn=Depends(db_dep)):
    return accounts_service.update_account(conn, account_id, data)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, conn=Depends(db_dep)):
    accounts_service.delete_account(conn, account_id)
