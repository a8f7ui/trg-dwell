@echo off
REM Dwell: Privacy Lab.  Run:  dwell        to see what you can do
REM                            dwell start  to start the course server
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
    echo   Python is not installed, or is too old.
    echo   Run  setup  — it explains how to fix this.
    echo.
    pause
    exit /b 1
)
%PYTHON% "%DIR%dwell.py" %*
endlocal
