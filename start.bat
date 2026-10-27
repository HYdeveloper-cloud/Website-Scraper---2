@echo off
REM Double-click to run HY Sales Engine. The first time it sets itself up (a few minutes, needs internet).
setlocal
cd /d "%~dp0backend"

set "PY="
for %%V in (3.12 3.11 3.13 3.10 3.14) do (
  if not defined PY (
    py -%%V --version >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python was not found. Install Python 3.12 from python.org, tick "Add Python to PATH", then double-click start.bat again.
  pause
  exit /b 1
)
echo Using: %PY%
%PY% --version

if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import uvicorn, fastapi, sqlalchemy, lxml" >nul 2>nul
  if errorlevel 1 (
    echo The earlier setup was incomplete. Starting it again.
    rmdir /s /q .venv
  )
)

if not exist .venv\Scripts\python.exe (
  echo.
  echo Setting up for the first time. This takes a few minutes and needs internet.
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the Python environment.
    pause
    exit /b 1
  )
  .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Installing failed. If the messages above mention Visual C++ or Rust, your Python is too new for some packages.
    echo Install Python 3.12 from python.org and double-click start.bat again.
    rmdir /s /q .venv
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe launcher.py
pause
