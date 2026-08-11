@echo off
REM Set up Dwell: Privacy Lab.  Double-click this file, or run:  setup
REM
REM This wrapper exists so nobody has to know whether their computer calls it
REM python, python3 or py.

setlocal

set "DIR=%~dp0"
set "PYTHON="

for %%C in ("py -3" "python" "python3") do (
    if not defined PYTHON (
        %%~C -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON=%%~C"
    )
)

if not defined PYTHON (
    echo.
    echo   ------------------------------------------------------------------
    echo.
    echo   Setup could not finish.
    echo.
    echo     What went wrong:  Python is not installed on this computer, or
    echo                       the version installed is too old.
    echo.
    echo     Why it matters:
    echo       Dwell is written in Python. Without it, nothing here can run.
    echo.
    echo     What to do next:
    echo       1. Go to  https://www.python.org/downloads
    echo       2. Click the yellow "Download Python" button.
    echo       3. IMPORTANT: on the installer's first screen, tick the box
    echo          "Add python.exe to PATH" before clicking Install Now.
    echo       4. Close this window, open a new one, and run  setup  again.
    echo.
    echo   ------------------------------------------------------------------
    echo.
    pause
    exit /b 1
)

%PYTHON% "%DIR%setup.py" %*
if errorlevel 1 pause
endlocal
