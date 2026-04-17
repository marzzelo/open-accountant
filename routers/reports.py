"""routers/reports.py — HTTP adapter for report services and exports."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from database import db_dep
from models import BalanceSheet, StatsData
from routers._common import parse_tag_ids, parse_type_ids
from services import exports_service, reports_service

router = APIRouter()


def _parse_type_ids_or_400(raw: Optional[str]) -> Optional[set[int]]:
    try:
        parsed = parse_type_ids(raw)
    except ValueError as exc:
        raise HTTPException(400, "Invalid type_ids filter") from exc
    return None if parsed is None else set(parsed)


def _parse_tag_ids_or_400(raw: Optional[str]) -> Optional[list[int]]:
    try:
        return parse_tag_ids(raw)
    except ValueError as exc:
        raise HTTPException(400, "Invalid tag_ids filter") from exc


# ---------------------------------------------------------------------------
# Report queries
# ---------------------------------------------------------------------------


@router.get("/reports/balance", response_model=BalanceSheet)
def get_balance(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    hide_accounts: bool = Query(False),
    show_zero_balance: bool = Query(True),
    type_ids: Optional[str] = Query(None),
    tag_ids: Optional[str] = Query(None),
    conn=Depends(db_dep),
):
    return reports_service.get_balance(
        conn,
        from_date,
        to_date,
        hide_accounts=hide_accounts,
        show_zero_balance=show_zero_balance,
        type_ids=_parse_type_ids_or_400(type_ids),
        tag_ids=_parse_tag_ids_or_400(tag_ids),
    )


@router.get("/reports/journal")
def get_journal(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    tag_ids: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    conn=Depends(db_dep),
):
    return reports_service.journal_data(
        conn, from_date, to_date, account_id, limit, _parse_tag_ids_or_400(tag_ids)
    )


@router.get("/reports/ledger/{account_id}")
def get_ledger(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    tag_ids: Optional[str] = Query(None),
    conn=Depends(db_dep),
):
    return reports_service.get_ledger(
        conn, account_id, from_date, to_date, _parse_tag_ids_or_400(tag_ids)
    )


@router.get("/reports/stats", response_model=StatsData)
def get_stats(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    tag_ids: Optional[str] = Query(None),
    conn=Depends(db_dep),
):
    return reports_service.get_stats(
        conn, from_date, to_date, _parse_tag_ids_or_400(tag_ids)
    )


# ---------------------------------------------------------------------------
# Exports (CSV / PDF)
# ---------------------------------------------------------------------------


@router.get("/reports/export/csv")
def export_csv(
    report: str = Query("journal", enum=["journal", "balance", "ledger"]),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    hide_accounts: bool = Query(False),
    show_zero_balance: bool = Query(True),
    type_ids: Optional[str] = Query(None),
    tag_ids: Optional[str] = Query(None),
    conn=Depends(db_dep),
):
    parsed_tag_ids = _parse_tag_ids_or_400(tag_ids)

    if report == "journal":
        content, filename = exports_service.export_journal_csv(
            conn, from_date, to_date, account_id, parsed_tag_ids
        )
    elif report == "balance":
        content, filename = exports_service.export_balance_csv(
            conn,
            from_date,
            to_date,
            hide_accounts=hide_accounts,
            show_zero_balance=show_zero_balance,
            type_ids=_parse_type_ids_or_400(type_ids),
            tag_ids=parsed_tag_ids,
        )
    else:
        content, filename = exports_service.export_ledger_csv(
            conn, account_id, from_date, to_date, parsed_tag_ids
        )

    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/export/pdf")
def export_pdf(
    report: str = Query("journal", enum=["journal", "balance", "ledger"]),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    hide_accounts: bool = Query(False),
    show_zero_balance: bool = Query(True),
    type_ids: Optional[str] = Query(None),
    tag_ids: Optional[str] = Query(None),
    conn=Depends(db_dep),
):
    parsed_tag_ids = _parse_tag_ids_or_400(tag_ids)

    if report == "journal":
        content, filename = exports_service.export_journal_pdf(
            conn, from_date, to_date, account_id, parsed_tag_ids
        )
    elif report == "balance":
        content, filename = exports_service.export_balance_pdf(
            conn,
            from_date,
            to_date,
            hide_accounts=hide_accounts,
            show_zero_balance=show_zero_balance,
            type_ids=_parse_type_ids_or_400(type_ids),
            tag_ids=parsed_tag_ids,
        )
    else:
        content, filename = exports_service.export_ledger_pdf(
            conn, account_id, from_date, to_date, parsed_tag_ids
        )

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
