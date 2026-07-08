@echo off
REM ============================================================================
REM  Translational Agent Framework -- one-click Web GUI launcher (Windows)
REM
REM  Double-click this file. It starts the local web server and opens the GUI
REM  in your default browser -- no need to type any command in a terminal.
REM
REM  The console window that appears IS the server: keep it open while you use
REM  the GUI, and close it (or press Ctrl+C) when you are finished.
REM ============================================================================
setlocal

REM Run from the repo root (the folder this script lives in), regardless of
REM where it was launched from.
cd /d "%~dp0"

REM Prefer the Windows "py" launcher; fall back to "python" on PATH.
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)

if not defined PY (
    echo.
    echo [!] Python was not found on this machine.
    echo     Install Python 3.10+ from https://www.python.org/downloads/
    echo     ^(tick "Add python.exe to PATH" during setup^), then run this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting the Translational Agent Framework GUI...
echo A browser tab will open automatically at http://127.0.0.1:8000/
echo Keep this window open while you use the GUI; close it to stop the server.
echo.

%PY% server.py --open

REM If the server exits (or fails to start), keep the window open so any error
REM message stays readable instead of the window vanishing.
echo.
echo The server has stopped.
pause
endlocal
