"""services/exports_service.py — CSV and PDF export generation for reports.

Thin orchestration layer over `reports_service`. Keeps router files focused on
HTTP concerns (query params, headers, status codes) and moves formatting logic
here so it can be unit-tested independently.

PDF generation depends on the optional ``reportlab`` package. Callers must
handle :class:`ExternalServiceError` raised when the package is missing.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Optional

from models import BalanceSheet
from services import reports_service
from services.errors import ExternalServiceError, ValidationError


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return f"$ {value:,.2f}"


def _csv_bytes(write: callable) -> bytes:
    """Run ``write(writer)`` with a CSV writer and return the UTF-8 BOM bytes."""
    buf = io.StringIO()
    write(buf)
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------

_JOURNAL_CSV_FIELDS = [
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
]

_LEDGER_CSV_FIELDS = [
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
]


def export_journal_csv(
    conn,
    from_date: Optional[str],
    to_date: Optional[str],
    account_id: Optional[int],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    data = reports_service.journal_data(
        conn, from_date, to_date, account_id, tag_ids=tag_ids
    )

    def _write(buf: io.StringIO) -> None:
        writer = csv.DictWriter(
            buf, fieldnames=_JOURNAL_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(data)

    return _csv_bytes(_write), "libro_diario.csv"


def export_balance_csv(
    conn,
    from_date: Optional[str],
    to_date: Optional[str],
    *,
    hide_accounts: bool,
    show_zero_balance: bool,
    type_ids: Optional[set[int]],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    balance_sheet = reports_service.get_balance(
        conn,
        from_date,
        to_date,
        hide_accounts=hide_accounts,
        show_zero_balance=show_zero_balance,
        type_ids=type_ids,
        tag_ids=tag_ids,
    )

    def _write(buf: io.StringIO) -> None:
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
                    writer.writerow(
                        [group.type_name, subgroup.subtype_name, "", subgroup.subtotal]
                    )
            writer.writerow([group.type_name, "TOTAL", "", group.total])
        writer.writerow([])
        writer.writerow(
            ["Resultado (Ingresos - Gastos)", "", "", balance_sheet.resultado]
        )

    return _csv_bytes(_write), "balance_general.csv"


def export_ledger_csv(
    conn,
    account_id: Optional[int],
    from_date: Optional[str],
    to_date: Optional[str],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    if account_id is None:
        raise ValidationError("account_id is required for ledger export")
    data = reports_service.get_ledger(conn, account_id, from_date, to_date, tag_ids)

    def _write(buf: io.StringIO) -> None:
        writer = csv.DictWriter(
            buf, fieldnames=_LEDGER_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(data["entries"])

    return _csv_bytes(_write), f"libro_mayor_{account_id}.csv"


# ---------------------------------------------------------------------------
# PDF exports
# ---------------------------------------------------------------------------


def _require_reportlab():
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
    except ImportError as exc:
        raise ExternalServiceError(
            "reportlab not installed. Run: pip install -r requirements-pdf.txt"
        ) from exc
    return {
        "colors": colors,
        "A4": A4,
        "landscape": landscape,
        "ParagraphStyle": ParagraphStyle,
        "getSampleStyleSheet": getSampleStyleSheet,
        "cm": cm,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _build_balance_pdf_table(balance_sheet: BalanceSheet):
    table_data: list[list[Any]] = [["Tipo", "Subtipo", "Cuenta", "Saldo"]]
    spans: list[tuple[int, int, int, int]] = []
    group_total_rows: list[int] = []
    summary_rows: list[int] = []
    current_row = 1

    for group in balance_sheet.groups:
        group_start_row = current_row

        for subgroup in group.subgroups:
            subgroup_start_row = current_row
            subgroup_rows: Iterable = subgroup.items or [None]

            for item in subgroup_rows:
                table_data.append(
                    [
                        group.type_name if current_row == group_start_row else "",
                        (
                            subgroup.subtype_name
                            if current_row == subgroup_start_row
                            else ""
                        ),
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

        table_data.append(
            [f"TOTAL {group.type_name.upper()}", "", "", _fmt(group.total)]
        )
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


def _render_pdf(rl, elements, *, pagesize, margins: tuple[float, float, float, float]):
    buf = io.BytesIO()
    doc = rl["SimpleDocTemplate"](
        buf,
        pagesize=pagesize,
        rightMargin=margins[0],
        leftMargin=margins[1],
        topMargin=margins[2],
        bottomMargin=margins[3],
    )
    doc.build(elements)
    return buf.getvalue()


def _base_table_style(rl):
    colors = rl["colors"]
    return [
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


def _header_elements(rl, title: str, from_dt: str, to_dt: str):
    styles = rl["getSampleStyleSheet"]()
    colors = rl["colors"]
    cm = rl["cm"]
    title_style = rl["ParagraphStyle"](
        "title", parent=styles["Title"], fontSize=16, spaceAfter=12
    )
    sub_style = rl["ParagraphStyle"](
        "sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )
    return [
        rl["Paragraph"](title, title_style),
        rl["Paragraph"](f"Período: {from_dt[:10]} al {to_dt[:10]}", sub_style),
        rl["Spacer"](1, 0.4 * cm),
    ]


def export_journal_pdf(
    conn,
    from_date: Optional[str],
    to_date: Optional[str],
    account_id: Optional[int],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    rl = _require_reportlab()
    from_dt, to_dt = reports_service.date_params(from_date, to_date)
    data = reports_service.journal_data(
        conn, from_date, to_date, account_id, tag_ids=tag_ids
    )

    elements = _header_elements(rl, "Libro Diario", from_dt, to_dt)
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

    cm = rl["cm"]
    col_widths = [3.5 * cm, 5 * cm, 5 * cm, 3 * cm, None]
    table = rl["Table"](table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(rl["TableStyle"](_base_table_style(rl)))
    elements.append(table)

    pdf = _render_pdf(
        rl,
        elements,
        pagesize=rl["landscape"](rl["A4"]),
        margins=(1 * cm, 1 * cm, 1.5 * cm, 1 * cm),
    )
    return pdf, "libro_diario.pdf"


def export_balance_pdf(
    conn,
    from_date: Optional[str],
    to_date: Optional[str],
    *,
    hide_accounts: bool,
    show_zero_balance: bool,
    type_ids: Optional[set[int]],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    rl = _require_reportlab()
    from_dt, to_dt = reports_service.date_params(from_date, to_date)
    balance_sheet = reports_service.get_balance(
        conn,
        from_date,
        to_date,
        hide_accounts=hide_accounts,
        show_zero_balance=show_zero_balance,
        type_ids=type_ids,
        tag_ids=tag_ids,
    )

    elements = _header_elements(rl, "Balance General", from_dt, to_dt)
    table_data, balance_spans, total_rows, summary_rows = _build_balance_pdf_table(
        balance_sheet
    )

    cm = rl["cm"]
    colors = rl["colors"]
    col_widths = [4 * cm, 5 * cm, 5 * cm, 4 * cm]
    table = rl["Table"](table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = list(_base_table_style(rl))

    for sc, sr, ec, er in balance_spans:
        style_cmds.append(("SPAN", (sc, sr), (ec, er)))
        style_cmds.append(("VALIGN", (sc, sr), (ec, er), "MIDDLE"))
    for row in total_rows:
        style_cmds.extend(
            [
                ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, row), (-1, row), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                ("LINEABOVE", (0, row), (-1, row), 0.6, colors.HexColor("#93c5fd")),
            ]
        )
    for row in summary_rows:
        style_cmds.extend(
            [
                ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, row), (-1, row), colors.HexColor("#111827")),
                ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                ("LINEABOVE", (0, row), (-1, row), 0.6, colors.HexColor("#94a3b8")),
            ]
        )

    table.setStyle(rl["TableStyle"](style_cmds))
    elements.append(table)

    pdf = _render_pdf(
        rl,
        elements,
        pagesize=rl["A4"],
        margins=(1.5 * cm, 1.5 * cm, 1.5 * cm, 1 * cm),
    )
    return pdf, "balance_general.pdf"


def export_ledger_pdf(
    conn,
    account_id: Optional[int],
    from_date: Optional[str],
    to_date: Optional[str],
    tag_ids: Optional[list[int]],
) -> tuple[bytes, str]:
    if account_id is None:
        raise ValidationError("account_id is required for ledger export")
    rl = _require_reportlab()
    from_dt, to_dt = reports_service.date_params(from_date, to_date)
    data = reports_service.get_ledger(conn, account_id, from_date, to_date, tag_ids)

    elements = _header_elements(
        rl, f"Libro Mayor - {data['account_name']}", from_dt, to_dt
    )
    table_data = [
        ["Fecha", "Descripción", "Contrapartida", "Débito", "Crédito", "Saldo"]
    ]
    for entry in data["entries"]:
        desc = (entry["description"] or "") + (
            f" [{entry['tags_label']}]" if entry.get("tags_label") else ""
        )
        table_data.append(
            [
                entry["date"][:16],
                desc[:40],
                entry["counterpart"],
                _fmt(entry["debit"]) if entry["debit"] else "",
                _fmt(entry["credit"]) if entry["credit"] else "",
                _fmt(entry["balance"]),
            ]
        )

    cm = rl["cm"]
    col_widths = [3.5 * cm, 6 * cm, 4 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm]
    table = rl["Table"](table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(rl["TableStyle"](_base_table_style(rl)))
    elements.append(table)

    pdf = _render_pdf(
        rl,
        elements,
        pagesize=rl["landscape"](rl["A4"]),
        margins=(1 * cm, 1 * cm, 1.5 * cm, 1 * cm),
    )
    return pdf, f"libro_mayor_{account_id}.pdf"
