@echo off
title Corrector G-Code - Impresora de Cemento
cd /d "%~dp0"

REM Usa pyw (sin consola) si existe, si no python.
set "PY_PRG=python"
where pyw >nul 2>nul
if %errorlevel%==0 set "PY_PRG=pyw"

set "PY_BIN=python"
where %PY_PRG% >nul 2>nul
if %errorlevel%==0 set "PY_BIN=%PY_PRG%"

where %PY_BIN% >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instala Python 3 y volve a intentar.
    pause
    exit /b 1
)

if not exist "corregir_ui.py" (
    echo [ERROR] No se encontro corregir_ui.py junto a run.bat.
    pause
    exit /b 1
)

start "" %PY_BIN% corregir_ui.py
exit /b 0