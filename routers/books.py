"""routers/books.py — HTTP adapter for book management services."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from services import books_service
from services.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter()


@router.get("/books")
def list_books():
    return books_service.list_books()


class CreateBookRequest(BaseModel):
    name: str
    basic_seed: bool = True


@router.post("/books")
def create_book(req: CreateBookRequest):
    try:
        return books_service.create_book(req.name, req.basic_seed)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


class SelectBookRequest(BaseModel):
    name: str


@router.post("/books/select")
def select_book(req: SelectBookRequest):
    try:
        return books_service.select_book(req.name)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


class RenameBookRequest(BaseModel):
    new_name: str


@router.put("/books/{name}/rename")
def rename_book(name: str, req: RenameBookRequest):
    try:
        return books_service.rename_book(name, req.new_name)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/books/{name}")
def delete_book(name: str):
    try:
        return books_service.delete_book(name)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/books/{name}/backup")
def backup_book(name: str):
    try:
        content = books_service.backup_book(name)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={name}.sql"},
    )


@router.post("/books/import")
async def import_book(
    name: str = Form(..., description="Nombre para la contabilidad importada"),
    file: UploadFile = File(..., description="Archivo .sql generado por el respaldo"),
):
    try:
        return books_service.import_book_from_sql(name, await file.read())
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
