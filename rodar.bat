@echo off
rem ==== Roda direto do código (sem gerar .exe) ====
cd /d "%~dp0"
where python >nul 2>nul || (echo Python nao encontrado. Instale o Python 3.11+ em python.org & pause & exit /b 1)
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
start "" .venv\Scripts\pythonw.exe run_lolitos.pyw
