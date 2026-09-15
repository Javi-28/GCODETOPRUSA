@echo off
title Corrector G-Code - Impresora de Cemento
cd /d "%~dp0"

REM 1) Si hay un exe compilado a nuestro lado, usar ese (mas rapido, no
REM    depende de Python).
if exist "distribucion\portable\CorrectorGcode.exe" (
    start "" "distribucion\portable\CorrectorGcode.exe"
    exit /b 0
)
if exist "portable\CorrectorGcode.exe" (
    start "" "portable\CorrectorGcode.exe"
    exit /b 0
)

REM 2) Si no, ejecutar corregir_ui.py con Python. Preferir pyw (sin consola).
set "PY_BIN="
where pyw >nul 2>nul
if %errorlevel%==0 set "PY_BIN=pyw"
if not defined PY_BIN (
    where py >nul 2>nul
    if %errorlevel%==0 set "PY_BIN=py"
)
if not defined PY_BIN (
    where python >nul 2>nul
    if %errorlevel%==0 set "PY_BIN=python"
)
if not defined PY_BIN (
    echo [ERROR] No se encontro Python ni el .exe compilado.
    echo         Instala Python 3 y volve a intentar.
    pause
    exit /b 1
)

if not exist "corregir_ui.py" (
    echo [ERROR] No se encontro corregir_ui.py junto a run.bat.
    pause
    exit /b 1
)

start "" %PY_BIN% "corregir_ui.py"
exit /b 0