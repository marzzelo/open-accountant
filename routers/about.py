"""routers/about.py — HTTP adapter for developer metadata services."""

from fastapi import APIRouter

from services import about_service

router = APIRouter()


@router.get("/about")
def get_about():
    return about_service.get_about()


@router.get("/version")
def get_version():
    return about_service.get_version()
