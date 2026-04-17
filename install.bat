@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Open Accountant — Windows installer
REM Usage: install.bat
REM ─────────────────────────────────────────────────────────────────────────────
setlocal EnableDelayedExpansion

set PYTHON_CMD=
set PYTHON_VER=
set VENV_DIR=.venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

echo.
echo   Open Accountant -- Windows Installer
echo   =====================================
echo.

REM ── 1. Find Python ──────────────────────────────────────────────────────────
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
        for /f "delims=" %%V in ('py -3 --version 2^>^&1') do set "PYTHON_VER=%%V"
    )
)

if not defined PYTHON_CMD (
    for %%C in (python python3) do (
        if not defined PYTHON_CMD (
            where %%C >nul 2>&1
            if !errorlevel! == 0 (
                for /f "delims=" %%P in ('where %%C') do (
                    if not defined PYTHON_CMD (
                        "%%P" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
                        if !errorlevel! == 0 (
                            set "PYTHON_CMD=\"%%~fP\""
                            for /f "delims=" %%V in ('"%%P" --version 2^>^&1') do set "PYTHON_VER=%%V"
                        )
                    )
                )
            )
        )
    )
)

if defined PYTHON_CMD goto :found_python
echo   ERROR: Python 3.10+ not found. Install from https://www.python.org
pause & exit /b 1
:found_python
echo   Found: %PYTHON_VER%

REM ── 2. Virtual environment ──────────────────────────────────────────────────
if not exist "%VENV_PYTHON%" (
    echo   Creating virtual environment in %VENV_DIR%...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   ERROR: failed to create virtual environment.
        pause & exit /b 1
    )
    echo   Virtual environment created.
) else (
    echo   %VENV_DIR% already exists -- reusing.
)

REM ── 3. Dependencies ─────────────────────────────────────────────────────────
echo   Installing Python dependencies in %VENV_DIR%...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo   ERROR: pip upgrade failed inside %VENV_DIR%.
    pause & exit /b 1
)
"%VENV_PYTHON%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo   ERROR: pip install failed inside %VENV_DIR%.
    pause & exit /b 1
)
echo   Dependencies installed.

REM ── 4. .env ─────────────────────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo   .env created. Edit it and set DATABASE_URL before starting.
    )
)

REM ── 5. data/ directory ──────────────────────────────────────────────────────
if not exist data mkdir data
echo   data\ directory ready.

REM ── 6. Initialize PostgreSQL schema and app settings ────────────────────────
if not defined DATABASE_URL (
    echo   WARNING: DATABASE_URL is not set. Edit .env and re-run install.bat
    echo            to initialize the PostgreSQL schema.
) else (
    echo   Initializing PostgreSQL schema and app settings...
    "%VENV_PYTHON%" -c "import app_config; app_config.load()"
    if errorlevel 1 (
        echo   ERROR: failed to initialize PostgreSQL schema.
        pause ^& exit /b 1
    )
    echo   PostgreSQL schema ready.
)

echo.
echo   Installation complete!
echo   Run:  %VENV_PYTHON% main.py
echo   Open: http://127.0.0.1:5001/
echo.
pause
