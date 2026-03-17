"""routers/about.py — HTTP adapter for developer metadata services."""

from fastapi import APIRouter, HTTPException

from services import about_service
from services.errors import IntegrityError

router = APIRouter()


@router.get("/about")
def get_about():
    try:
        return about_service.get_about()
    except IntegrityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/version")
def get_version():
    return about_service.get_version()
