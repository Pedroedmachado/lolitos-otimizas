@echo off
chcp 65001 >nul
title Chinese Control - gerando o instalador
rem =====================================================================
rem  Gera dist\ChineseControl-2.5.0-Setup.exe com dois cliques.
rem  Instala sozinho (pelo winget) o que faltar: Python 3.12 e Inno Setup 6.
rem =====================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  [1/5] Procurando o Python...
set "PY="
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%ProgramFiles%\Python313\python.exe" "%ProgramFiles%\Python312\python.exe") do (
  if not defined PY if exist %%P set "PY=%%~P"
)
if not defined PY (
  where py >nul 2>nul && for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
)
if not defined PY (
  echo        Python nao encontrado. Instalando o Python 3.12 pelo winget...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not exist "!PY!" (
  echo  ERRO: nao consegui instalar o Python. Instale pelo python.org e rode de novo.
  goto :erro
)
echo        !PY!

echo.
echo  [2/5] Procurando o Inno Setup 6...
set "ISCC="
for %%I in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if not defined ISCC if exist %%I set "ISCC=%%~I"
)
if not defined ISCC (
  echo        Inno Setup nao encontrado. Instalando pelo winget...
  winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
  for %%I in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
    if not defined ISCC if exist %%I set "ISCC=%%~I"
  )
)
if not defined ISCC (
  echo  ERRO: nao consegui instalar o Inno Setup. Baixe em jrsoftware.org/isdl.php e rode de novo.
  goto :erro
)
echo        !ISCC!

echo.
echo  [3/5] Preparando o ambiente (PySide6, psutil, PyInstaller)...
if not exist .venv\Scripts\python.exe (
  "!PY!" -m venv .venv || goto :erro
)
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller pillow --quiet || goto :erro

echo.
echo  [4/5] Gerando o programa (.exe)...
.venv\Scripts\python.exe tools\make_icon.py || goto :erro
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --uac-admin ^
  --name ChineseControl ^
  --icon build\app.ico ^
  --add-data "lolitos\data;lolitos\data" ^
  --distpath dist --workpath build\pyi ^
  run_lolitos.pyw || goto :erro

echo.
echo  [5/5] Montando o instalador...
.venv\Scripts\python.exe tools\get_presentmon.py || echo        (sem PresentMon: o instalador sai sem ele)
"!ISCC!" /Q installer.iss || goto :erro

echo.
echo  =====================================================================
echo   PRONTO:  dist\ChineseControl-2.5.0-Setup.exe
echo  =====================================================================
explorer /select,"%~dp0dist\ChineseControl-2.5.0-Setup.exe"
pause
exit /b 0

:erro
echo.
echo  O processo parou com erro (veja a mensagem acima).
pause
exit /b 1
