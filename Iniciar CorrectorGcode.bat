@echo off
title Corrector G-Code - Impresora de Cemento
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw corregir_ui.py
) else (
    start "" py corregir_ui.py
)
