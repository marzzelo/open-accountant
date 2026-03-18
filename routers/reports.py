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


@router.get("/reports/balance", response_model=BalanceSheet)
def get_balance(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    with get_db() as conn:
        return reports_service.get_balance(conn, from_date, to_date)


@router.get("/reports/journal")
def get_journal(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    limit: int = Query(1000, ge=1, le=10000),
):
    with get_db() as conn:
        return reports_service.journal_data(conn, from_date, to_date, account_id, limit)


@router.get("/reports/ledger/{account_id}")
def get_ledger(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    with get_db() as conn:
        try:
            return reports_service.get_ledger(conn, account_id, from_date, to_date)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/reports/stats", response_model=StatsData)
def get_stats(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    with get_db() as conn:
        return reports_service.get_stats(conn, from_date, to_date)


@router.get("/reports/export/csv")
def export_csv(
    report: str = Query("journal", enum=["journal", "balance", "ledger"]),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
):
    buf = io.StringIO()

    if report == "journal":
        with get_db() as conn:
            data = reports_service.journal_data(conn, from_date, to_date, account_id)
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
            ],
        )
        writer.writeheader()
        writer.writerows(data)
        filename = "libro_diario.csv"

    elif report == "balance":
        with get_db() as conn:
            balance_sheet = reports_service.get_balance(conn, from_date, to_date)
        writer = csv.writer(buf)
        writer.writerow(["Tipo", "Subtipo", "Cuenta", "Saldo"])
        for group in balance_sheet.groups:
            for subgroup in group.subgroups:
                for item in subgroup.items:
                    writer.writerow(
                        [
                            group.type_name,
                            subgroup.subtype_name,
                            item.account_name,
                            item.balance,
                        ]
                    )
            writer.writerow([group.type_name, "TOTAL", "", group.total])
        writer.writerow([])
        writer.writerow(
            ["Resultado (Ingresos - Gastos)", "", "", balance_sheet.resultado]
        )
        filename = "balance_general.csv"

    else:
        with get_db() as conn:
            try:
                data = reports_service.get_ledger(conn, account_id, from_date, to_date)
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
            ],
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
            data = reports_service.journal_data(conn, from_date, to_date, account_id)
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
                    row["description"] or "",
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
            balance_sheet = reports_service.get_balance(conn, from_date, to_date)
        elements.append(Paragraph("Balance General", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [["Tipo", "Subtipo", "Cuenta", "Saldo"]]
        for group in balance_sheet.groups:
            for subgroup in group.subgroups:
                for item in subgroup.items:
                    table_data.append(
                        [
                            group.type_name,
                            subgroup.subtype_name,
                            item.account_name,
                            _fmt(item.balance),
                        ]
                    )
            table_data.append(
                ["", f"TOTAL {group.type_name.upper()}", "", _fmt(group.total)]
            )
        table_data.append(["", "Resultado neto", "", _fmt(balance_sheet.resultado)])
        table_data.append(
            [
                "",
                "Ecuación (Activo - Pas - Pat - Res)",
                "",
                str(round(balance_sheet.equation_check, 2)),
            ]
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
        with get_db() as conn:
            try:
                data = reports_service.get_ledger(conn, account_id, from_date, to_date)
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
                    entry["description"][:40],
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
    elements.append(table)
    doc.build(elements)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
