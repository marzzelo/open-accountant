"""
main.py — Open Accountant · FastAPI entry point.
Run: python main.py
"""

import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import app_config  # must be imported before database
import app_version

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import require_authenticated_user
from routers import types, subtypes, accounts, transactions, reports, tags
from routers import settings as settings_router, about as about_router
from routers import projections as projections_router
from routers import auth as auth_router
from services.errors import (
    ConflictError,
    ExternalServiceError,
    IntegrityError,
    NotFoundError,
    ServiceError,
    ValidationError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load configuration and initialize the active database.
    app_config.load()

    # 2. Bootstrap .env from .env.example if .env doesn't exist yet
    if not app_config.ENV_PATH.exists() and app_config.ENV_EXAMPLE_PATH.exists():
        shutil.copy(app_config.ENV_EXAMPLE_PATH, app_config.ENV_PATH)
        print("[open-accountant] Created .env from .env.example")

    yield


app = FastAPI(
    title="Open Accountant API",
    version=app_version.numeric_version(),
    description="Personal double-entry accounting system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ──────────────────────────────────────────────────
# Routers raise domain errors from services/errors.py; these handlers map them
# to HTTP responses so each endpoint no longer needs boilerplate try/except.
_SERVICE_ERROR_STATUS: dict[type[ServiceError], int] = {
    ValidationError: 400,
    NotFoundError: 404,
    ConflictError: 409,
    IntegrityError: 422,
    ExternalServiceError: 502,
}


@app.exception_handler(ServiceError)
async def _service_error_handler(_request: Request, exc: ServiceError):
    status_code = _SERVICE_ERROR_STATUS.get(type(exc), 500)
    return JSONResponse({"detail": str(exc)}, status_code=status_code)


# ── API routers ────────────────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api", tags=["Auth"])
app.include_router(
    types.router,
    prefix="/api",
    tags=["Types"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    subtypes.router,
    prefix="/api",
    tags=["Subtypes"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    accounts.router,
    prefix="/api",
    tags=["Accounts"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    transactions.router,
    prefix="/api",
    tags=["Transactions"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    tags.router,
    prefix="/api",
    tags=["Tags"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    reports.router,
    prefix="/api",
    tags=["Reports"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(
    settings_router.router,
    prefix="/api",
    tags=["Settings"],
    dependencies=[Depends(require_authenticated_user)],
)
app.include_router(about_router.router, prefix="/api", tags=["About"])
app.include_router(
    projections_router.router,
    prefix="/api",
    tags=["Projections"],
    dependencies=[Depends(require_authenticated_user)],
)

# ── Static frontend ────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    app_config.load()
    uvicorn.run(
        "main:app",
        host=app_config.server_host(),
        port=app_config.server_port(),
        reload=True,
    )
