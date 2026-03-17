"""routers/subtypes.py — HTTP adapter for subtype services."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from database import get_db
from models import SubtypeIn, SubtypeOut, SubtypeUpdate
from services import subtypes_service
from services.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter()


@router.get("/subtypes", response_model=list[SubtypeOut])
def list_subtypes(type_id: Optional[int] = None):
    with get_db() as conn:
        return subtypes_service.list_subtypes(conn, type_id)


@router.get("/subtypes/{subtype_id}", response_model=SubtypeOut)
def get_subtype(subtype_id: int):
    with get_db() as conn:
        try:
            return subtypes_service.get_subtype(conn, subtype_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/subtypes", response_model=SubtypeOut, status_code=201)
def create_subtype(data: SubtypeIn):
    with get_db() as conn:
        try:
            return subtypes_service.create_subtype(conn, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc


@router.put("/subtypes/{subtype_id}", response_model=SubtypeOut)
def update_subtype(subtype_id: int, data: SubtypeUpdate):
    with get_db() as conn:
        try:
            return subtypes_service.update_subtype(conn, subtype_id, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc


@router.delete("/subtypes/{subtype_id}", status_code=204)
def delete_subtype(subtype_id: int):
    with get_db() as conn:
        try:
            subtypes_service.delete_subtype(conn, subtype_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
