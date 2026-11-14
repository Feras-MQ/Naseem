@echo off
setlocal
set "NASEEM_PY=%~dp0.venv\Scripts\python.exe"
if exist "%NASEEM_PY%" (
    "%NASEEM_PY%" "%~dp0scripts\setup_usb.py" %*
    goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0scripts\setup_usb.py" %*
    goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0scripts\setup_usb.py" %*
    goto finished
)
echo Python was not found. Install Python 3.10 or newer, then try again.
set "NASEEM_EXIT=2"
goto done
:finished
set "NASEEM_EXIT=%errorlevel%"
:done
if "%~1"=="" pause
exit /b %NASEEM_EXIT%
