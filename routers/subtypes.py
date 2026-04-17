"""routers/subtypes.py — HTTP adapter for subtype services."""

from typing import Optional

from fastapi import APIRouter, Depends

from database import db_dep
from models import SubtypeIn, SubtypeOut, SubtypeUpdate
from services import subtypes_service

router = APIRouter()


@router.get("/subtypes", response_model=list[SubtypeOut])
def list_subtypes(type_id: Optional[int] = None, conn=Depends(db_dep)):
    return subtypes_service.list_subtypes(conn, type_id)


@router.get("/subtypes/{subtype_id}", response_model=SubtypeOut)
def get_subtype(subtype_id: int, conn=Depends(db_dep)):
    return subtypes_service.get_subtype(conn, subtype_id)


@router.post("/subtypes", response_model=SubtypeOut, status_code=201)
def create_subtype(data: SubtypeIn, conn=Depends(db_dep)):
    return subtypes_service.create_subtype(conn, data)


@router.put("/subtypes/{subtype_id}", response_model=SubtypeOut)
def update_subtype(subtype_id: int, data: SubtypeUpdate, conn=Depends(db_dep)):
    return subtypes_service.update_subtype(conn, subtype_id, data)


@router.delete("/subtypes/{subtype_id}", status_code=204)
def delete_subtype(subtype_id: int, conn=Depends(db_dep)):
    subtypes_service.delete_subtype(conn, subtype_id)
