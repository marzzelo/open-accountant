"""routers/types.py — HTTP adapter for type services."""

from fastapi import APIRouter, Depends

from database import db_dep
from models import TypeOut
from services import types_service

router = APIRouter()


@router.get("/types", response_model=list[TypeOut])
def list_types(conn=Depends(db_dep)):
    return types_service.list_types(conn)


@router.get("/types/{type_id}", response_model=TypeOut)
def get_type(type_id: int, conn=Depends(db_dep)):
    return types_service.get_type(conn, type_id)
