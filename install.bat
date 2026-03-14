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

REM ── 4. Config ───────────────────────────────────────────────────────────────
if not exist config.ini (
    copy config.ini.example config.ini >nul
    echo   config.ini created.
) else (
    echo   config.ini already exists -- skipping.
)

REM ── 5. .env ─────────────────────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo   .env created.
    )
)

REM ── 6. data/ directory ──────────────────────────────────────────────────────
if not exist data mkdir data
echo   data\ directory ready.

REM ── 7. Seed demo database ───────────────────────────────────────────────────
if not exist data\home.db (
    echo   Creating demo database...
    "%VENV_PYTHON%" scripts\seed_demo.py --db data\home.db
    echo   Demo database ready.
) else (
    echo   data\home.db already exists -- skipping seed.
)

echo.
echo   Installation complete!
echo   Run:  %VENV_PYTHON% main.py
echo   Open: http://127.0.0.1:5001/
echo.
pause
