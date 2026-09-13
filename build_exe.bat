@echo off
rem Bygger en fristaende Windows-version i dist\ och packar den som zip for GitHub Releases.
setlocal
cd /d "%~dp0"

set "VENV=.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "OUT=dist\LLM Overlay"
set "ZIP=dist\LLM-Overlay-windows.zip"

if not exist "%VPY%" (
    echo Ingen virtuell miljo hittad. Kor run.bat forst sa skapas den.
    echo.
    pause
    exit /b 1
)

"%VPY%" -m pip install --upgrade pyinstaller --quiet
if errorlevel 1 goto :failed

echo Bygger. Det har tar nagra minuter ...
"%VPY%" -m PyInstaller --noconfirm --clean LLMOverlay.spec
if errorlevel 1 goto :failed

if not exist "%OUT%\LLM Overlay.exe" goto :failed

echo Packar %ZIP% ...
if exist "%ZIP%" del "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\LLM Overlay' -DestinationPath '%ZIP%'"
if errorlevel 1 goto :failed

echo.
echo Klart.
echo   Mapp: %OUT%
echo   Zip:  %ZIP%
echo.
echo Ladda upp till GitHub Releases med:
echo   gh release create v1.0.0 "%ZIP%" --title "LLM Overlay v1.0.0" --notes "Fristaende Windows-version."
echo.
pause
exit /b 0

:failed
echo.
echo Bygget misslyckades. Se utskriften ovan.
echo.
pause
exit /b 1
