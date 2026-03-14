"""
main.py — Open Accountant · FastAPI entry point.
Run: uvicorn main:app --host 0.0.0.0 --port 5001 --reload
"""
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import app_config          # must be imported before database

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import types, subtypes, accounts, transactions, reports
from routers import books, settings as settings_router, about as about_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load configuration (creates config.ini with defaults if missing)
    app_config.load()

    # 2. Bootstrap .env from .env.example if .env doesn't exist yet
    if not app_config.ENV_PATH.exists() and app_config.ENV_EXAMPLE_PATH.exists():
        shutil.copy(app_config.ENV_EXAMPLE_PATH, app_config.ENV_PATH)
        print("[open-accountant] Created .env from .env.example")

    # 3. Initialise current book DB (creates schema + seeds if new)
    init_db()
    yield


app = FastAPI(
    title="Open Accountant API",
    version="2.0.0",
    description="Sistema de contabilidad personal de doble entrada",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ────────────────────────────────────────────────────────────────
app.include_router(types.router,            prefix="/api", tags=["Types"])
app.include_router(subtypes.router,         prefix="/api", tags=["Subtypes"])
app.include_router(accounts.router,         prefix="/api", tags=["Accounts"])
app.include_router(transactions.router,     prefix="/api", tags=["Transactions"])
app.include_router(reports.router,          prefix="/api", tags=["Reports"])
app.include_router(books.router,            prefix="/api", tags=["Books"])
app.include_router(settings_router.router,  prefix="/api", tags=["Settings"])
app.include_router(about_router.router,     prefix="/api", tags=["About"])

# ── Static frontend ────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)
