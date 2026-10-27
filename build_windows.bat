@echo off
REM Builds HYSalesEngine.exe (and Setup.exe if Inno Setup is installed). Double-click this file on a Windows PC.
REM The screens are already built in backend\ui, so Node.js is NOT needed. To rebuild them, run:  build_windows.bat rebuild
setlocal
cd /d "%~dp0"
echo.
echo === HY Sales Engine: build ===

if exist backend\ui\index.html (
  if /i not "%~1"=="rebuild" (
    echo [1/3] Using the screens that are already built.
    goto pack
  )
)

echo [1/3] Building the screens...
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 18 or newer is needed to rebuild the screens. Install it from nodejs.org.
  goto screensfailed
)
pushd frontend
call npm install --no-audit --no-fund
if errorlevel 1 (
  popd
  echo npm install failed.
  goto screensfailed
)
set NEXT_PUBLIC_API_URL=
call npm run build
if errorlevel 1 (
  popd
  echo The screens failed to build. If the message mentions SWC, delete the frontend\node_modules folder and try again.
  goto screensfailed
)
popd
if exist backend\ui rmdir /s /q backend\ui
xcopy /e /i /y /q frontend\out backend\ui >nul
goto pack

:screensfailed
if exist backend\ui\index.html (
  echo Carrying on with the screens that are already built.
  goto pack
)
pause
exit /b 1

:pack
echo [2/3] Packaging the program...
pushd backend
set "PY="
for %%V in (3.12 3.11 3.13 3.10 3.14) do (
  if not defined PY (
    py -%%V --version >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY set "PY=python"
echo Using: %PY%
if exist .venv-build\Scripts\python.exe (
  .venv-build\Scripts\python.exe -c "import fastapi, lxml, PyInstaller" >nul 2>nul
  if errorlevel 1 rmdir /s /q .venv-build
)
if not exist .venv-build\Scripts\python.exe %PY% -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv-build\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  popd
  echo pip install failed. If the messages mention Visual C++ or Rust, install Python 3.12 from python.org and run this again.
  pause
  exit /b 1
)
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm HYSalesEngine.spec
if errorlevel 1 (
  popd
  echo Packaging failed
  pause
  exit /b 1
)
popd
if exist dist rmdir /s /q dist
mkdir dist
xcopy /e /i /y /q backend\dist\HYSalesEngine dist\HYSalesEngine >nul

echo [3/3] Making the installer, optional...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC (
  "%ISCC%" installer\HYSalesEngine.iss
  echo.
  echo Done. Installer: installer\Output\HYSalesEngine-Setup.exe
) else (
  echo Inno Setup was not found, so no installer was made. That is fine.
  echo Done. Program: dist\HYSalesEngine\HYSalesEngine.exe   copy the whole HYSalesEngine folder anywhere.
)
pause
