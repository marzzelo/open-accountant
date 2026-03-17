"""routers/types.py — HTTP adapter for type services."""

from fastapi import APIRouter, HTTPException

from database import get_db
from models import TypeOut
from services import types_service
from services.errors import NotFoundError

router = APIRouter()


@router.get("/types", response_model=list[TypeOut])
def list_types():
    with get_db() as conn:
        return types_service.list_types(conn)


@router.get("/types/{type_id}", response_model=TypeOut)
def get_type(type_id: int):
    with get_db() as conn:
        try:
            return types_service.get_type(conn, type_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
