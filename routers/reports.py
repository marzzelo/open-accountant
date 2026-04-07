"""routers/reports.py — HTTP adapter for report services and exports."""

import csv
import io
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from database import get_db
from models import BalanceSheet, StatsData
from services import reports_service
from services.errors import NotFoundError

router = APIRouter()


def _fmt(v: float) -> str:
    return f"$ {v:,.2f}"


def _parse_type_ids(type_ids: Optional[str]) -> Optional[set[int]]:
    if type_ids is None:
        return None

    raw_values = [value.strip() for value in type_ids.split(",") if value.strip()]
    if not raw_values:
        return set()

    try:
        return {int(value) for value in raw_values}
    except ValueError as exc:
        raise HTTPException(400, "Invalid type_ids filter") from exc


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


def _build_balance_pdf_table(balance_sheet: BalanceSheet):
    table_data = [["Tipo", "Subtipo", "Cuenta", "Saldo"]]
    spans: list[tuple[int, int, int, int]] = []
    group_total_rows: list[int] = []
    summary_rows: list[int] = []
    current_row = 1

    for group in balance_sheet.groups:
        group_start_row = current_row

        for subgroup in group.subgroups:
            subgroup_start_row = current_row
            subgroup_rows = subgroup.items or [None]

            for item in subgroup_rows:
                table_data.append(
                    [
                        group.type_name if current_row == group_start_row else "",
                        subgroup.subtype_name if current_row == subgroup_start_row else "",
                        item.account_name if item else "",
                        _fmt(item.balance if item else subgroup.subtotal),
                    ]
                )
                current_row += 1

            subgroup_end_row = current_row - 1
            if subgroup_end_row > subgroup_start_row:
                spans.append((1, subgroup_start_row, 1, subgroup_end_row))

        group_end_row = current_row - 1
        if group_end_row > group_start_row:
            spans.append((0, group_start_row, 0, group_end_row))

        table_data.append([f"TOTAL {group.type_name.upper()}", "", "", _fmt(group.total)])
        spans.append((0, current_row, 2, current_row))
        group_total_rows.append(current_row)
        current_row += 1

    table_data.append(["Resultado neto", "", "", _fmt(balance_sheet.resultado)])
    spans.append((0, current_row, 2, current_row))
    summary_rows.append(current_row)
    current_row += 1

    table_data.append(
        [
            "Ecuación (Activo - Pas - Pat - Res)",
            "",
            "",
            str(round(balance_sheet.equation_check, 2)),
        ]
    )
    spans.append((0, current_row, 2, current_row))
    summary_rows.append(current_row)

    return table_data, spans, group_total_rows, summary_rows


@router.get("/reports/balance", response_model=BalanceSheet)
def get_balance(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    hide_accounts: bool = Query(False),
    show_zero_balance: bool = Query(True),
    type_ids: Optional[str] = Query(None),
    tag_ids: Optional[str] = Query(None),
):
    with get_db() as conn:
        return reports_service.get_balance(
            conn,
            from_date,
            to_date,
            hide_accounts=hide_accounts,
            show_zero_balance=show_zero_balance,
            type_ids=_parse_type_ids(type_ids),
            tag_ids=_parse_tag_ids(tag_ids),
        )


@router.get("/reports/journal")
def get_journal(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    tag_ids: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
):
    with get_db() as conn:
        return reports_service.journal_data(
            conn, from_date, to_date, account_id, limit, _parse_tag_ids(tag_ids)
        )


@router.get("/reports/ledger/{account_id}")
def get_ledger(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    tag_ids: Optional[str] = Query(None),
):
    with get_db() as conn:
        try:
            return reports_service.get_ledger(
                conn, account_id, from_date, to_date, _parse_tag_ids(tag_ids)
            )
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/reports/stats", response_model=StatsData)
def get_stats(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    tag_ids: Optional[str] = Query(None),
):
    with get_db() as conn:
        return reports_service.get_stats(conn, from_date, to_date, _parse_tag_ids(tag_ids))


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
):
    buf = io.StringIO()
    parsed_tag_ids = _parse_tag_ids(tag_ids)

    if report == "journal":
        with get_db() as conn:
            data = reports_service.journal_data(
                conn, from_date, to_date, account_id, tag_ids=parsed_tag_ids
            )
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "date",
                "debit_name",
                "credit_name",
                "amount",
                "original_amount",
                "original_currency",
                "fx_rate",
                "fx_source",
                "description",
                "tags_label",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(data)
        filename = "libro_diario.csv"

    elif report == "balance":
        with get_db() as conn:
            balance_sheet = reports_service.get_balance(
                conn,
                from_date,
                to_date,
                hide_accounts=hide_accounts,
                show_zero_balance=show_zero_balance,
                type_ids=_parse_type_ids(type_ids),
                tag_ids=parsed_tag_ids,
            )
        writer = csv.writer(buf)
        writer.writerow(["Tipo", "Subtipo", "Cuenta", "Saldo"])
        for group in balance_sheet.groups:
            for subgroup in group.subgroups:
                if subgroup.items:
                    for item in subgroup.items:
                        writer.writerow(
                            [
                                group.type_name,
                                subgroup.subtype_name,
                                item.account_name,
                                item.balance,
                            ]
                        )
                else:
                    writer.writerow([group.type_name, subgroup.subtype_name, "", subgroup.subtotal])
            writer.writerow([group.type_name, "TOTAL", "", group.total])
        writer.writerow([])
        writer.writerow(
            ["Resultado (Ingresos - Gastos)", "", "", balance_sheet.resultado]
        )
        filename = "balance_general.csv"

    else:
        if account_id is None:
            raise HTTPException(400, "account_id is required for ledger export")
        with get_db() as conn:
            try:
                data = reports_service.get_ledger(
                    conn, account_id, from_date, to_date, parsed_tag_ids
                )
            except NotFoundError as exc:
                raise HTTPException(404, str(exc)) from exc
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "date",
                "description",
                "counterpart",
                "role",
                "debit",
                "credit",
                "original_amount",
                "original_currency",
                "fx_rate",
                "fx_source",
                "balance",
                "tags_label",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(data["entries"])
        filename = f"libro_mayor_{account_id}.csv"

    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
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
):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"error": "reportlab not installed. Run: pip install reportlab"}, 500
        )

    from_dt, to_dt = reports_service.date_params(from_date, to_date)
    parsed_tag_ids = _parse_tag_ids(tag_ids)
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=16, spaceAfter=12
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )

    period_str = f"Período: {from_dt[:10]} al {to_dt[:10]}"
    elements = []

    if report == "journal":
        with get_db() as conn:
            data = reports_service.journal_data(
                conn, from_date, to_date, account_id, tag_ids=parsed_tag_ids
            )
        elements.append(Paragraph("Libro Diario", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [["Fecha", "Débito", "Crédito", "Monto", "Descripción"]]
        for row in data:
            table_data.append(
                [
                    row["date"][:16],
                    row["debit_name"],
                    row["credit_name"],
                    _fmt(row["amount"]),
                    (row["description"] or "")
                    + (f" [{row['tags_label']}]" if row.get("tags_label") else ""),
                ]
            )

        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1 * cm,
        )
        col_widths = [3.5 * cm, 5 * cm, 5 * cm, 3 * cm, None]
        filename = "libro_diario.pdf"

    elif report == "balance":
        with get_db() as conn:
            balance_sheet = reports_service.get_balance(
                conn,
                from_date,
                to_date,
                hide_accounts=hide_accounts,
                show_zero_balance=show_zero_balance,
                type_ids=_parse_type_ids(type_ids),
                tag_ids=parsed_tag_ids,
            )
        elements.append(Paragraph("Balance General", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data, balance_spans, balance_total_rows, balance_summary_rows = _build_balance_pdf_table(
            balance_sheet
        )

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1 * cm,
        )
        col_widths = [4 * cm, 5 * cm, 5 * cm, 4 * cm]
        filename = "balance_general.pdf"

    else:
        if account_id is None:
            raise HTTPException(400, "account_id is required for ledger export")
        with get_db() as conn:
            try:
                data = reports_service.get_ledger(
                    conn, account_id, from_date, to_date, parsed_tag_ids
                )
            except NotFoundError as exc:
                raise HTTPException(404, str(exc)) from exc
        elements.append(Paragraph(f"Libro Mayor - {data['account_name']}", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [
            ["Fecha", "Descripción", "Contrapartida", "Débito", "Crédito", "Saldo"]
        ]
        for entry in data["entries"]:
            table_data.append(
                [
                    entry["date"][:16],
                    ((entry["description"] or "") + (f" [{entry['tags_label']}]" if entry.get("tags_label") else ""))[:40],
                    entry["counterpart"],
                    _fmt(entry["debit"]) if entry["debit"] else "",
                    _fmt(entry["credit"]) if entry["credit"] else "",
                    _fmt(entry["balance"]),
                ]
            )

        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1 * cm,
        )
        col_widths = [3.5 * cm, 6 * cm, 4 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm]
        filename = f"libro_mayor_{account_id}.pdf"

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f5f5")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    if report == "balance":
        balance_style_commands = []

        for start_col, start_row, end_col, end_row in balance_spans:
            balance_style_commands.extend(
                [
                    ("SPAN", (start_col, start_row), (end_col, end_row)),
                    ("VALIGN", (start_col, start_row), (end_col, end_row), "MIDDLE"),
                ]
            )

        for row in balance_total_rows:
            balance_style_commands.extend(
                [
                    ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#dbeafe")),
                    ("TEXTCOLOR", (0, row), (-1, row), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                    ("LINEABOVE", (0, row), (-1, row), 0.6, colors.HexColor("#93c5fd")),
                ]
            )

        for row in balance_summary_rows:
            balance_style_commands.extend(
                [
                    ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, row), (-1, row), colors.HexColor("#111827")),
                    ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                    ("LINEABOVE", (0, row), (-1, row), 0.6, colors.HexColor("#94a3b8")),
                ]
            )

        table.setStyle(TableStyle(balance_style_commands))

    elements.append(table)
    doc.build(elements)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
