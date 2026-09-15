@echo off
title Compilar Corrector G-Code (Instalador profesional)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py compilar.py
) else (
    python compilar.py
)
echo.
pause