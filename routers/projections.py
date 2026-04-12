"""routers/projections.py — HTTP adapter for projection services."""

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import ProjectionSeriesIn, ProjectionSeriesOut, ProjectionSeriesUpdate
from services import projections_service
from services.errors import NotFoundError

router = APIRouter()


# ── Series CRUD ───────────────────────────────────────────────────────────────


@router.get("/projections/series", response_model=list[ProjectionSeriesOut])
def list_series():
    with get_db() as conn:
        return projections_service.list_series(conn)


@router.post("/projections/series", response_model=ProjectionSeriesOut, status_code=201)
def create_series(data: ProjectionSeriesIn):
    with get_db() as conn:
        return projections_service.create_series(conn, data)


@router.put("/projections/series/{series_id}", response_model=ProjectionSeriesOut)
def update_series(series_id: int, data: ProjectionSeriesUpdate):
    with get_db() as conn:
        try:
            return projections_service.update_series(conn, series_id, data)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.delete("/projections/series/{series_id}", status_code=204)
def delete_series(series_id: int):
    with get_db() as conn:
        try:
            projections_service.delete_series(conn, series_id)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))


# ── Projection data ───────────────────────────────────────────────────────────


@router.get("/reports/projections")
def get_projections(
    horizon: int = Query(12, ge=1, le=120),
    history_months: int = Query(12, ge=3, le=60),
    investment_lookback_months: int = Query(None, ge=3, le=60),
    investment_stat: str = Query("mean", pattern=r"^(mean|median)$"),
    investment_exclude_outliers: bool = Query(True),
    investment_outlier_k: float = Query(1.5, ge=0.5, le=5.0),
):
    with get_db() as conn:
        return projections_service.get_projections(
            conn,
            horizon,
            history_months,
            investment_lookback_months=investment_lookback_months,
            investment_stat=investment_stat,
            investment_exclude_outliers=investment_exclude_outliers,
            investment_outlier_k=investment_outlier_k,
        )
