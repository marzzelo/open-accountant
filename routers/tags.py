"""HTTP adapter for tag services."""

from fastapi import APIRouter, HTTPException

from database import get_db
from models import TagIn, TagOut, TagUpdate
from services import tags_service
from services.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter()


@router.get("/tags", response_model=list[TagOut])
def list_tags():
    with get_db() as conn:
        return tags_service.list_tags(conn)


@router.get("/tags/{tag_id}", response_model=TagOut)
def get_tag(tag_id: int):
    with get_db() as conn:
        try:
            return tags_service.get_tag(conn, tag_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(data: TagIn):
    with get_db() as conn:
        try:
            return tags_service.create_tag(conn, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, data: TagUpdate):
    with get_db() as conn:
        try:
            return tags_service.update_tag(conn, tag_id, data)
        except ValidationError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int):
    with get_db() as conn:
        try:
            tags_service.delete_tag(conn, tag_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc