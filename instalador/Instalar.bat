@echo off
title Instalar Corrector G-Code
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py instalar.py
) else (
    python instalar.py
)
echo.
pause