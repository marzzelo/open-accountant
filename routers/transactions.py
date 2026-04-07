"""routers/transactions.py — HTTP adapter for transaction services."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import TransactionIn, TransactionOut, TransactionUpdate
from services import transactions_service
from services.errors import NotFoundError, ValidationError

router = APIRouter()


def _parse_tag_ids(tag_ids: Optional[str]) -> Optional[list[int]]:
    if tag_ids is None:
        return None

    raw_values = [value.strip() for value in tag_ids.split(",") if value.strip()]
    if not raw_values:
        return []

    try:
        return [int(value) for value in raw_values]
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
):
    with get_db() as conn:
        return transactions_service.list_transactions(
            conn,
            from_date,
            to_date,
            account_id,
            _parse_tag_ids(tag_ids),
            limit,
            offset,
        )


@router.get("/transactions/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int):
    with get_db() as conn:
        try:
            return transactions_service.get_transaction(conn, tx_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn):
    with get_db() as conn:
        try:
            return transactions_service.create_transaction(conn, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.put("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, data: TransactionUpdate):
    with get_db() as conn:
        try:
            return transactions_service.update_transaction(conn, tx_id, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int):
    with get_db() as conn:
        try:
            transactions_service.delete_transaction(conn, tx_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
