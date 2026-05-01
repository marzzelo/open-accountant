"""routers/recurring_transactions.py — HTTP adapter for recurring transactions."""

from typing import Literal

from fastapi import APIRouter, Depends, Query

from database import db_dep
from models import (
    RecurringTransactionIn,
    RecurringTransactionOut,
    RecurringTransactionPostIn,
    RecurringTransactionPostOut,
    RecurringTransactionUpdate,
)
from services import recurring_transactions_service

router = APIRouter()


@router.get(
    "/recurring-transactions",
    response_model=list[RecurringTransactionOut],
)
def list_recurring_transactions(
    filter: Literal["all", "enabled", "active"] = Query("all"),
    conn=Depends(db_dep),
):
    return recurring_transactions_service.list_recurring_transactions(conn, filter)


@router.get("/recurring-transactions/active-count")
def active_count(conn=Depends(db_dep)):
    return recurring_transactions_service.active_count(conn)


@router.get(
    "/recurring-transactions/find-similar",
    response_model=RecurringTransactionOut | None,
)
def find_similar_recurring_transaction(
    credit_account: int,
    debit_account: int,
    description: str = "",
    conn=Depends(db_dep),
):
    return recurring_transactions_service.find_similar_recurring_transaction(
        conn,
        credit_account=credit_account,
        debit_account=debit_account,
        description=description,
    )


@router.get(
    "/recurring-transactions/{recurring_id}",
    response_model=RecurringTransactionOut,
)
def get_recurring_transaction(recurring_id: int, conn=Depends(db_dep)):
    return recurring_transactions_service.get_recurring_transaction(conn, recurring_id)


@router.post(
    "/recurring-transactions",
    response_model=RecurringTransactionOut,
    status_code=201,
)
def create_recurring_transaction(
    data: RecurringTransactionIn, conn=Depends(db_dep)
):
    return recurring_transactions_service.create_recurring_transaction(conn, data)


@router.put(
    "/recurring-transactions/{recurring_id}",
    response_model=RecurringTransactionOut,
)
def update_recurring_transaction(
    recurring_id: int, data: RecurringTransactionUpdate, conn=Depends(db_dep)
):
    return recurring_transactions_service.update_recurring_transaction(
        conn, recurring_id, data
    )


@router.delete("/recurring-transactions/{recurring_id}", status_code=204)
def delete_recurring_transaction(recurring_id: int, conn=Depends(db_dep)):
    recurring_transactions_service.delete_recurring_transaction(conn, recurring_id)


@router.post(
    "/recurring-transactions/{recurring_id}/mark-done",
    response_model=RecurringTransactionOut,
)
def mark_recurring_transaction_done(recurring_id: int, conn=Depends(db_dep)):
    return recurring_transactions_service.mark_recurring_transaction_done(
        conn, recurring_id
    )


@router.post(
    "/recurring-transactions/{recurring_id}/post",
    response_model=RecurringTransactionPostOut,
)
def post_recurring_transaction(
    recurring_id: int, data: RecurringTransactionPostIn, conn=Depends(db_dep)
):
    return recurring_transactions_service.post_recurring_transaction(
        conn, recurring_id, data
    )
