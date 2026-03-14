@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Open Accountant — Windows installer
REM Usage: install.bat
REM ─────────────────────────────────────────────────────────────────────────────
setlocal EnableDelayedExpansion

echo.
echo   Open Accountant -- Windows Installer
echo   =====================================
echo.

REM ── 1. Find Python ──────────────────────────────────────────────────────────
set PYTHON=
for %%P in (python3 python py) do (
    where %%P >nul 2>&1
    if !errorlevel! == 0 (
        for /f "delims=" %%V in ('%%P --version 2^>^&1') do set PYVER=%%V
        echo   Found: !PYVER!
        set PYTHON=%%P
        goto :found_python
    )
)
echo   ERROR: Python 3.10+ not found. Install from https://www.python.org
pause & exit /b 1
:found_python

REM ── 2. Dependencies ─────────────────────────────────────────────────────────
echo   Installing Python dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo   ERROR: pip install failed.
    pause & exit /b 1
)
echo   Dependencies installed.

REM ── 3. Config ───────────────────────────────────────────────────────────────
if not exist config.ini (
    copy config.ini.example config.ini >nul
    echo   config.ini created.
) else (
    echo   config.ini already exists -- skipping.
)

REM ── 4. .env ─────────────────────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo   .env created.
    )
)

REM ── 5. data/ directory ──────────────────────────────────────────────────────
if not exist data mkdir data
echo   data\ directory ready.

REM ── 6. Seed demo database ───────────────────────────────────────────────────
if not exist data\home.db (
    echo   Creating demo database...
    %PYTHON% scripts\seed_demo.py --db data\home.db
    echo   Demo database ready.
) else (
    echo   data\home.db already exists -- skipping seed.
)

echo.
echo   Installation complete!
echo   Run:  python main.py
echo   Open: http://127.0.0.1:5001/
echo.
pause
