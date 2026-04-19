"""Projection series CRUD and monthly adjustment helpers."""

from models import ProjectionSeriesIn, ProjectionSeriesUpdate

from services.errors import NotFoundError
from services.helpers import require_row
from services.projections.common import _parse_month, _series_start_month


def _compute_series_adjustments(
    series_list: list[dict], projected_months: list[str]
) -> dict:
    """Aggregate monthly income/expense/investment series adjustments."""
    count = len(projected_months)
    income_adj = [0.0] * count
    expense_adj = [0.0] * count
    investment_adj = [0.0] * count

    for series in series_list:
        if not bool(series.get("enabled", True)):
            continue
        start_ym = _series_start_month(series["start_date"])
        start_year, start_month = _parse_month(start_ym)
        duration_months = max(1, int(series["months"]))
        period_months = max(1, int(series.get("period_months") or 1))
        for index, projected_month in enumerate(projected_months):
            projected_year, projected_month_num = _parse_month(projected_month)
            month_idx = (projected_year - start_year) * 12 + (
                projected_month_num - start_month
            )
            if 0 <= month_idx < duration_months and month_idx % period_months == 0:
                if series["type"] == "income":
                    income_adj[index] += series["monthly_amount"]
                elif series["type"] == "expense":
                    expense_adj[index] += series["monthly_amount"]
                elif series["type"] == "investment":
                    investment_adj[index] += series["monthly_amount"]
                elif series["type"] == "rescue":
                    investment_adj[index] -= series["monthly_amount"]

    savings_adj = [income_adj[index] - expense_adj[index] for index in range(count)]

    assets_adj = []
    cumulative = 0.0
    for index in range(count):
        cumulative += savings_adj[index]
        assets_adj.append(round(cumulative, 4))

    liabilities_adj = []
    cumulative = 0.0
    for index in range(count):
        cumulative += expense_adj[index]
        liabilities_adj.append(round(cumulative, 4))

    return {
        "income": income_adj,
        "expenses": expense_adj,
        "savings": savings_adj,
        "assets": assets_adj,
        "liabilities": liabilities_adj,
        "investments": investment_adj,
    }


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "start_date": row["start_date"],
        "months": row["months"],
        "period_months": row["period_months"],
        "enabled": bool(row["enabled"]),
        "monthly_amount": row["monthly_amount"],
        "created_at": row["created_at"],
    }


def list_series(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM projection_series ORDER BY start_date, name"
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_series(conn, series_id: int) -> dict:
    row = require_row(
        conn,
        "SELECT * FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    return _row_to_dict(row)


def create_series(conn, data: ProjectionSeriesIn) -> dict:
    row = conn.execute(
        """INSERT INTO projection_series (
               name,
               type,
               start_date,
               months,
               period_months,
               enabled,
               monthly_amount
           )
           VALUES (?, ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        (
            data.name,
            data.type,
            data.start_date,
            data.months,
            data.period_months,
            data.enabled,
            data.monthly_amount,
        ),
    )
    series_id = row.fetchone()["id"]
    conn.commit()
    return get_series(conn, series_id)


def update_series(conn, series_id: int, data: ProjectionSeriesUpdate) -> dict:
    row = require_row(
        conn,
        "SELECT * FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return _row_to_dict(row)
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [series_id]
    conn.execute(f"UPDATE projection_series SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return get_series(conn, series_id)


def delete_series(conn, series_id: int) -> None:
    require_row(
        conn,
        "SELECT id FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    conn.execute("DELETE FROM projection_series WHERE id = ?", (series_id,))
    conn.commit()


__all__ = [
    "_compute_series_adjustments",
    "create_series",
    "delete_series",
    "get_series",
    "list_series",
    "update_series",
]
