"""routers/transactions.py — HTTP adapter for transaction services."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from database import db_dep
from models import TransactionIn, TransactionOut, TransactionUpdate
from routers._common import parse_tag_ids
from services import transactions_service

router = APIRouter()


def _parse_tag_ids_or_400(raw: Optional[str]) -> Optional[list[int]]:
    try:
        return parse_tag_ids(raw)
    except ValueError as exc:
        raise HTTPException(400, "Invalid tag_ids filter") from exc


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    tag_ids: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    conn=Depends(db_dep),
):
    return transactions_service.list_transactions(
        conn,
        from_date,
        to_date,
        account_id,
        _parse_tag_ids_or_400(tag_ids),
        limit,
        offset,
    )


@router.get("/transactions/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int, conn=Depends(db_dep)):
    return transactions_service.get_transaction(conn, tx_id)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, conn=Depends(db_dep)):
    return transactions_service.create_transaction(conn, data)


@router.put("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, data: TransactionUpdate, conn=Depends(db_dep)):
    return transactions_service.update_transaction(conn, tx_id, data)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, conn=Depends(db_dep)):
    transactions_service.delete_transaction(conn, tx_id)
