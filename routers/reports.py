"""
routers/reports.py — Balance sheet, journal, ledger, statistics, CSV/PDF export.
"""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, Response

from database import get_db, compute_filtered_balance, DEBIT_NORMAL
from models import (
    BalanceSheet,
    BalanceGroup,
    BalanceSubgroup,
    BalanceLineItem,
    StatsData,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _current_year_range() -> tuple[str, str]:
    y = datetime.now().year
    return f"{y}-01-01 00:00:00", f"{y}-12-31 23:59:59"


def _date_params(from_date: Optional[str], to_date: Optional[str]) -> tuple[str, str]:
    if from_date and to_date:
        return from_date + " 00:00:00", to_date + " 23:59:59"
    return _current_year_range()


def _fmt(v: float) -> str:
    return f"$ {v:,.2f}"


# ── Balance Sheet ─────────────────────────────────────────────────────────────


@router.get("/reports/balance", response_model=BalanceSheet)
def get_balance(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    from_dt, to_dt = _date_params(from_date, to_date)
    filtered = bool(from_date and to_date)

    # Una sola pasada — conn siempre disponible para compute_filtered_balance
    type_map: dict = {}
    with get_db() as conn:
        rows = conn.execute(
            """SELECT a.id, a.name, a.type_id, a.subtype_id,
                      a.initial_balance, a.balance,
                      t.name AS type_name,
                      COALESCE(s.name, 'Sin subtipo') AS subtype_name
               FROM accounts a
               JOIN types t ON a.type_id = t.id
               LEFT JOIN subtypes s ON a.subtype_id = s.id
               ORDER BY a.type_id, s.name, a.name"""
        ).fetchall()

        for r in rows:
            bal = (
                compute_filtered_balance(
                    conn, r["id"], r["type_id"], r["initial_balance"], from_dt, to_dt
                )
                if filtered
                else r["balance"]
            )
            tid = r["type_id"]
            if tid not in type_map:
                type_map[tid] = {"type_name": r["type_name"], "subtypes": {}}
            sname = r["subtype_name"]
            if sname not in type_map[tid]["subtypes"]:
                type_map[tid]["subtypes"][sname] = []
            type_map[tid]["subtypes"][sname].append(
                BalanceLineItem(account_id=r["id"], account_name=r["name"], balance=bal)
            )

    groups = []
    totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}

    for tid in sorted(type_map.keys()):
        tm = type_map[tid]
        subgroups = []
        type_total = 0.0
        for sname, items in tm["subtypes"].items():
            subtotal = sum(i.balance for i in items)
            subgroups.append(
                BalanceSubgroup(subtype_name=sname, items=items, subtotal=subtotal)
            )
            type_total += subtotal
        groups.append(
            BalanceGroup(
                type_name=tm["type_name"],
                type_id=tid,
                subgroups=subgroups,
                total=type_total,
            )
        )
        totals[tid] = type_total

    resultado = totals[3] - totals[4]  # Ingresos - Gastos
    equation = totals[1] - (totals[2] + totals[5] + resultado)

    return BalanceSheet(
        period_from=from_dt[:10],
        period_to=to_dt[:10],
        groups=groups,
        total_activo=totals[1],
        total_pasivo=totals[2],
        total_patrimonio=totals[5],
        total_ingreso=totals[3],
        total_gasto=totals[4],
        resultado=resultado,
        equation_check=round(equation, 4),
    )


# ── Libro Diario (Journal) ────────────────────────────────────────────────────


def _journal_data(from_date, to_date, account_id=None, limit=1000):
    from_dt, to_dt = _date_params(from_date, to_date)
    conditions = ["t.date BETWEEN ? AND ?"]
    params: list = [from_dt, to_dt]
    if account_id:
        conditions.append("(t.debit_account = ? OR t.credit_account = ?)")
        params += [account_id, account_id]
    where = "WHERE " + " AND ".join(conditions)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT t.id, t.date, t.description, t.amount,
                       da.name AS debit_name, ca.name AS credit_name
                FROM transactions t
                JOIN accounts da ON t.debit_account  = da.id
                JOIN accounts ca ON t.credit_account = ca.id
                {where}
                ORDER BY t.date ASC, t.id ASC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
    return [
        {
            "id": r["id"],
            "date": r["date"],
            "debit_name": r["debit_name"],
            "credit_name": r["credit_name"],
            "amount": r["amount"],
            "description": r["description"],
        }
        for r in rows
    ]


@router.get("/reports/journal")
def get_journal(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    limit: int = Query(1000, ge=1, le=10000),
):
    return _journal_data(from_date, to_date, account_id, limit)


# ── Libro Mayor (Ledger) ──────────────────────────────────────────────────────


def _ledger_data(account_id: int, from_date=None, to_date=None):
    return get_ledger(account_id, from_date, to_date)


@router.get("/reports/ledger/{account_id}")
def get_ledger(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    from_dt, to_dt = _date_params(from_date, to_date)

    with get_db() as conn:
        acc = conn.execute(
            "SELECT id, name, type_id, initial_balance FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not acc:
            from fastapi import HTTPException

            raise HTTPException(404, "Account not found")

        rows = conn.execute(
            """SELECT t.id, t.date, t.description, t.amount,
                      t.debit_account, t.credit_account,
                      da.name AS debit_name, ca.name AS credit_name
               FROM transactions t
               JOIN accounts da ON t.debit_account  = da.id
               JOIN accounts ca ON t.credit_account = ca.id
               WHERE (t.debit_account = ? OR t.credit_account = ?)
                 AND t.date BETWEEN ? AND ?
               ORDER BY t.date ASC, t.id ASC""",
            (account_id, account_id, from_dt, to_dt),
        ).fetchall()

    # Build running balance
    from database import balance_delta as bd

    type_id = acc["type_id"]
    running = acc["initial_balance"]
    entries = []

    for r in rows:
        if r["debit_account"] == account_id:
            role, counterpart, delta = (
                "Débito",
                r["credit_name"],
                bd(type_id, "debit", r["amount"]),
            )
        else:
            role, counterpart, delta = (
                "Crédito",
                r["debit_name"],
                bd(type_id, "credit", r["amount"]),
            )
        running += delta
        entries.append(
            {
                "id": r["id"],
                "date": r["date"],
                "description": r["description"] or counterpart,
                "counterpart": counterpart,
                "role": role,
                "debit": r["amount"] if role == "Débito" else None,
                "credit": r["amount"] if role == "Crédito" else None,
                "balance": round(running, 4),
            }
        )

    return {
        "account_id": acc["id"],
        "account_name": acc["name"],
        "period_from": from_dt[:10],
        "period_to": to_dt[:10],
        "opening_balance": acc["initial_balance"],
        "closing_balance": round(running, 4),
        "entries": entries,
    }


# ── Statistics ────────────────────────────────────────────────────────────────


@router.get("/reports/stats", response_model=StatsData)
def get_stats(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    from_dt, to_dt = _date_params(from_date, to_date)

    with get_db() as conn:
        # Monthly cashflow: Ingresos vs Gastos
        # Ingresos → cuenta ACREDITADA (credit_account) de tipo 3
        # Gastos   → cuenta DEBITADA   (debit_account)  de tipo 4
        cashflow_rows = conn.execute(
            """SELECT strftime('%Y-%m', t.date) AS month,
                      SUM(CASE WHEN ac.type_id = 3 THEN t.amount ELSE 0 END) AS ingresos,
                      SUM(CASE WHEN ad.type_id = 4 THEN t.amount ELSE 0 END) AS gastos
               FROM transactions t
               JOIN accounts ac ON t.credit_account = ac.id
               JOIN accounts ad ON t.debit_account  = ad.id
               WHERE t.date BETWEEN ? AND ?
               GROUP BY month ORDER BY month""",
            (from_dt, to_dt),
        ).fetchall()
        monthly_cashflow = [
            {
                "month": r["month"],
                "ingresos": r["ingresos"],
                "gastos": r["gastos"],
                "neto": r["ingresos"] - r["gastos"],
            }
            for r in cashflow_rows
        ]

        # Expenses by subtype
        exp_rows = conn.execute(
            """SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
                      SUM(t.amount) AS amount
               FROM transactions t
               JOIN accounts a  ON t.debit_account = a.id
               LEFT JOIN subtypes s ON a.subtype_id = s.id
               WHERE a.type_id = 4 AND t.date BETWEEN ? AND ?
               GROUP BY subtype ORDER BY amount DESC""",
            (from_dt, to_dt),
        ).fetchall()
        expenses_by_subtype = [
            {"subtype": r["subtype"], "amount": r["amount"]} for r in exp_rows
        ]

        # Income by subtype
        inc_rows = conn.execute(
            """SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
                      SUM(t.amount) AS amount
               FROM transactions t
               JOIN accounts a  ON t.credit_account = a.id
               LEFT JOIN subtypes s ON a.subtype_id = s.id
               WHERE a.type_id = 3 AND t.date BETWEEN ? AND ?
               GROUP BY subtype ORDER BY amount DESC""",
            (from_dt, to_dt),
        ).fetchall()
        income_by_subtype = [
            {"subtype": r["subtype"], "amount": r["amount"]} for r in inc_rows
        ]

        # Asset composition by account balance for the selected period
        activo_accs = conn.execute(
            "SELECT id, name, type_id, initial_balance FROM accounts WHERE type_id = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()

        asset_composition = []
        for acc in activo_accs:
            balance = compute_filtered_balance(
                conn, acc["id"], acc["type_id"], acc["initial_balance"], from_dt, to_dt
            )
            if balance > 0:
                asset_composition.append(
                    {
                        "account": acc["name"],
                        "balance": round(balance, 4),
                    }
                )

        # Top accounts by volume
        top_rows = conn.execute(
            """SELECT a.name AS account,
                      SUM(t.amount) AS volume,
                      COUNT(*) AS tx_count
               FROM transactions t
               JOIN accounts a ON t.debit_account = a.id OR t.credit_account = a.id
               WHERE t.date BETWEEN ? AND ?
               GROUP BY a.id ORDER BY volume DESC LIMIT 10""",
            (from_dt, to_dt),
        ).fetchall()
        top_accounts = [
            {"account": r["account"], "volume": r["volume"], "tx_count": r["tx_count"]}
            for r in top_rows
        ]

        # Balance evolution (Activo accounts, last 12 months)
        months_rows = conn.execute(
            """SELECT DISTINCT strftime('%Y-%m', date) AS month FROM transactions
               WHERE date BETWEEN ? AND ? ORDER BY month""",
            (from_dt, to_dt),
        ).fetchall()
        months = [r["month"] for r in months_rows]

        balance_evolution = []
        for acc in activo_accs:
            for month in months:
                m_from = month + "-01 00:00:00"
                m_to = month + "-31 23:59:59"
                bal = compute_filtered_balance(
                    conn,
                    acc["id"],
                    acc["type_id"],
                    acc["initial_balance"],
                    from_dt,
                    m_to,
                )
                balance_evolution.append(
                    {
                        "month": month,
                        "account_id": acc["id"],
                        "account_name": acc["name"],
                        "balance": bal,
                    }
                )

    return StatsData(
        monthly_cashflow=monthly_cashflow,
        expenses_by_subtype=expenses_by_subtype,
        income_by_subtype=income_by_subtype,
        asset_composition=asset_composition,
        top_accounts=top_accounts,
        balance_evolution=balance_evolution,
    )


# ── CSV Export ────────────────────────────────────────────────────────────────


@router.get("/reports/export/csv")
def export_csv(
    report: str = Query("journal", enum=["journal", "balance", "ledger"]),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
):
    from_dt, to_dt = _date_params(from_date, to_date)
    buf = io.StringIO()

    if report == "journal":
        data = _journal_data(from_date, to_date, account_id)
        w = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "date",
                "debit_name",
                "credit_name",
                "amount",
                "description",
            ],
        )
        w.writeheader()
        w.writerows(data)
        filename = "libro_diario.csv"

    elif report == "balance":
        bs = get_balance(from_date, to_date)
        w = csv.writer(buf)
        w.writerow(["Tipo", "Subtipo", "Cuenta", "Saldo"])
        for g in bs.groups:
            for sg in g.subgroups:
                for item in sg.items:
                    w.writerow(
                        [g.type_name, sg.subtype_name, item.account_name, item.balance]
                    )
            w.writerow([g.type_name, "TOTAL", "", g.total])
        w.writerow([])
        w.writerow(["Resultado (Ingresos - Gastos)", "", "", bs.resultado])
        filename = "balance_general.csv"

    elif report == "ledger":
        data = _ledger_data(account_id, from_date, to_date)
        w = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "date",
                "description",
                "counterpart",
                "role",
                "debit",
                "credit",
                "balance",
            ],
        )
        w.writeheader()
        w.writerows(data["entries"])
        filename = f"libro_mayor_{account_id}.csv"

    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── PDF Export ────────────────────────────────────────────────────────────────


@router.get("/reports/export/pdf")
def export_pdf(
    report: str = Query("journal", enum=["journal", "balance", "ledger"]),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
    except ImportError:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"error": "reportlab not installed. Run: pip install reportlab"}, 500
        )

    from_dt, to_dt = _date_params(from_date, to_date)
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
        data = _journal_data(from_date, to_date, account_id)
        elements.append(Paragraph("Libro Diario", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [["Fecha", "Débito", "Crédito", "Monto", "Descripción"]]
        for r in data:
            table_data.append(
                [
                    r["date"][:16],
                    r["debit_name"],
                    r["credit_name"],
                    _fmt(r["amount"]),
                    r["description"] or "",
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
        bs = get_balance(from_date, to_date)
        elements.append(Paragraph("Balance General", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [["Tipo", "Subtipo", "Cuenta", "Saldo"]]
        for g in bs.groups:
            for sg in g.subgroups:
                for item in sg.items:
                    table_data.append(
                        [
                            g.type_name,
                            sg.subtype_name,
                            item.account_name,
                            _fmt(item.balance),
                        ]
                    )
            table_data.append(["", f"TOTAL {g.type_name.upper()}", "", _fmt(g.total)])
        table_data.append(["", "Resultado neto", "", _fmt(bs.resultado)])
        table_data.append(
            [
                "",
                "Ecuación (Activo - Pas - Pat - Res)",
                "",
                str(round(bs.equation_check, 2)),
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

    elif report == "ledger":
        data = _ledger_data(account_id, from_date, to_date)
        elements.append(Paragraph(f"Libro Mayor - {data['account_name']}", title_style))
        elements.append(Paragraph(period_str, sub_style))
        elements.append(Spacer(1, 0.4 * cm))

        table_data = [
            ["Fecha", "Descripción", "Contrapartida", "Débito", "Crédito", "Saldo"]
        ]
        for e in data["entries"]:
            table_data.append(
                [
                    e["date"][:16],
                    e["description"][:40],
                    e["counterpart"],
                    _fmt(e["debit"]) if e["debit"] else "",
                    _fmt(e["credit"]) if e["credit"] else "",
                    _fmt(e["balance"]),
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

    # Build table
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
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
    elements.append(t)
    doc.build(elements)

    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
