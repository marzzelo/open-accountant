"""HTTP adapter for tag services."""

from fastapi import APIRouter, Depends

from database import db_dep
from models import TagIn, TagOut, TagUpdate
from services import tags_service

router = APIRouter()


@router.get("/tags", response_model=list[TagOut])
def list_tags(conn=Depends(db_dep)):
    return tags_service.list_tags(conn)


@router.get("/tags/{tag_id}", response_model=TagOut)
def get_tag(tag_id: int, conn=Depends(db_dep)):
    return tags_service.get_tag(conn, tag_id)


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(data: TagIn, conn=Depends(db_dep)):
    return tags_service.create_tag(conn, data)


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, data: TagUpdate, conn=Depends(db_dep)):
    return tags_service.update_tag(conn, tag_id, data)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, conn=Depends(db_dep)):
    tags_service.delete_tag(conn, tag_id)
