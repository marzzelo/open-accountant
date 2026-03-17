"""Type service functions."""

from models import TypeOut

from services.errors import NotFoundError
from services.helpers import model_from_row, require_row


def list_types(conn) -> list[TypeOut]:
    rows = conn.execute("SELECT id, name FROM types ORDER BY id").fetchall()
    return [model_from_row(TypeOut, row) for row in rows]


def get_type(conn, type_id: int) -> TypeOut:
    row = require_row(
        conn,
        "SELECT id, name FROM types WHERE id = ?",
        (type_id,),
        "Type not found",
        NotFoundError,
    )
    return model_from_row(TypeOut, row)
