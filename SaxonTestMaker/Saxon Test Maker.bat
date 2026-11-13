@echo off
rem Double-click to start the Saxon Test Maker; it opens in your default browser.
cd /d "%~dp0"
set PYTHONUTF8=1
title Saxon Test Maker

rem Try the py launcher first, then python. Each is verified by actually running it,
rem which also skips the Microsoft Store "python" stub that exists without Python installed.
py -3 -c "import sys" >nul 2>nul
if %errorlevel%==0 (
    py -3 saxon_portal.py
    goto done
)
python -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul
if %errorlevel%==0 (
    python saxon_portal.py
    goto done
)

echo.
echo Python 3 was not found on this computer.
echo.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH"
echo on the first screen of the installer, then double-click this file again.
echo.
start "" https://www.python.org/downloads/

:done
echo.
echo Saxon Test Maker has stopped. You can close this window.
pause >nul
