@echo off
rem Startar LLM Overlay. Skapar virtuell miljo och installerar beroenden vid behov.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV=.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "VPYW=%VENV%\Scripts\pythonw.exe"
set "STAMP=%VENV%\requirements.stamp"

if not exist "%VPY%" (
    echo Skapar virtuell miljo i %VENV% ...
    py -3 -m venv "%VENV%" 2>nul
    if not exist "%VPY%" python -m venv "%VENV%" 2>nul
    if not exist "%VPY%" goto :no_python
)

"%VPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :old_python

rem Installera om beroenden nar requirements.txt har andrats (tidsstampel + storlek).
set "REQ_ID="
for %%F in (requirements.txt) do set "REQ_ID=%%~tF-%%~zF"
set "OLD_ID="
if exist "%STAMP%" set /p OLD_ID=<"%STAMP%"

if not "!REQ_ID!"=="!OLD_ID!" (
    echo Installerar beroenden. Forsta gangen tar det nagra minuter ...
    "%VPY%" -m pip install --upgrade pip --quiet
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :pip_failed
    >"%STAMP%" echo !REQ_ID!
)

echo Startar LLM Overlay ...
start "" "%VPYW%" main.py
exit /b 0

:no_python
echo.
echo Hittade ingen Python-installation.
where winget >nul 2>&1
if errorlevel 1 goto :manual_python
set "INSTALL="
set /p INSTALL="Vill du installera Python 3.12 nu via winget? (J/N) "
if /i not "!INSTALL!"=="J" goto :manual_python
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :manual_python
echo.
echo Python ar installerat. Stang det har fonstret och kor run.bat igen.
echo.
pause
exit /b 0

:manual_python
echo.
echo Installera Python 3.10 eller senare fran https://www.python.org/downloads/
echo och kryssa i "Add python.exe to PATH". Kor sedan run.bat igen.
echo.
pause
exit /b 1

:old_python
echo.
echo Python-versionen i %VENV% ar for gammal. Programmet kraver 3.10 eller senare.
echo Ta bort mappen %VENV% och kor run.bat igen med en nyare Python installerad.
echo.
pause
exit /b 1

:pip_failed
echo.
echo Installationen av beroenden misslyckades. Kontrollera din internetanslutning
echo och kor run.bat igen.
echo.
pause
exit /b 1
