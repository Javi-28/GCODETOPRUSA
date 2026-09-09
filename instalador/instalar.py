#!/usr/bin/env python3
"""
instalar.py
Instalador del Corrector G-Code (impresora de cemento).

Copia la aplicacion a %LOCALAPPDATA%\\Programs\\CorrectorGcode y crea
accesos directos en el Escritorio y en el Menu Inicio. No requiere
instalar dependencias: usa unicamente la libreria estandar de Python.

Uso:
    py instalar.py
"""

import os
import shutil
import sys
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))

INSTALL_DIR = LOCALAPPDATA / "Programs" / "CorrectorGcode"
DESKTOP = Path.home() / "Desktop"
START_MENU_DIR = APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "CorrectorGcode"

NOMBRE_LAUNCHER = "Iniciar CorrectorGcode.bat"
NOMBRE_DESINSTALAR = "Desinstalar CorrectorGcode.bat"

ARCHIVOS_A_COPIAR = [
    "corregir_gcode.py",
    "corregir_ui.py",
    "ANALISIS.md",
]
ARCHIVOS_OPCIONALES = [
    "corregir_gcode.py",
    "corregir_ui.py",
]


def escribir_bat(ruta, contenido):
    ruta.write_bytes(contenido.replace("\n", "\r\n").encode("ascii", errors="ignore"))


def bat_launcher():
    return (
        "@echo off\r\n"
        "title Corrector G-Code - Impresora de Cemento\r\n"
        'cd /d "%~dp0"\r\n'
        "where pyw >nul 2>nul\r\n"
        "if %errorlevel%==0 (\r\n"
        "    start \"\" pyw corregir_ui.py\r\n"
        ") else (\r\n"
        "    start \"\" py corregir_ui.py\r\n"
        ")\r\n"
    )


def bat_desinstalador():
    return (
        "@echo off\r\n"
        "title Desinstalar CorrectorGcode\r\n"
        'cd /d "%~dp0"\r\n'
        "where py >nul 2>nul\r\n"
        "if %errorlevel%==0 (\r\n"
        "    py desinstalar.py\r\n"
        ") else (\r\n"
        "    python desinstalar.py\r\n"
        ")\r\n"
        "pause\r\n"
    )


def instalar():
    print("Carpeta origen:  %s" % PROYECTO)
    print("Destino:         %s" % INSTALL_DIR)
    print()

    # 1) Copiar archivos de la aplicacion
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS_A_COPIAR:
        origen = PROYECTO / nombre
        if origen.exists():
            shutil.copy2(origen, INSTALL_DIR / nombre)
            print("[OK]  %s" % nombre)
        else:
            print("[--]  %s  (no encontrado, se omite)" % nombre)

    # 2) Launcher dentro de la carpeta instalada
    launcher_dir = INSTALL_DIR / NOMBRE_LAUNCHER
    escribir_bat(launcher_dir, bat_launcher())
    print("[OK]  %s" % NOMBRE_LAUNCHER)

    # 3) Copiar desinstalador dentro de la carpeta instalada
    desinstalador_dir = INSTALL_DIR / "desinstalar.py"
    shutil.copy2(PROYECTO / "instalador" / "desinstalar.py", desinstalador_dir)
    escribir_bat(INSTALL_DIR / NOMBRE_DESINSTALAR, bat_desinstalador())
    print("[OK]  %s" % NOMBRE_DESINSTALAR)

    # 4) Acceso directo en el Escritorio
    DESKTOP.mkdir(exist_ok=True)
    escribir_bat(DESKTOP / NOMBRE_LAUNCHER, bat_launcher())
    print("[OK]  Acceso directo en el Escritorio: %s" % NOMBRE_LAUNCHER)

    # 5) Acceso en el Menu Inicio
    START_MENU_DIR.mkdir(parents=True, exist_ok=True)
    escribir_bat(START_MENU_DIR / NOMBRE_LAUNCHER, bat_launcher())
    escribir_bat(START_MENU_DIR / NOMBRE_DESINSTALAR, bat_desinstalador())
    shutil.copy2(PROYECTO / "instalador" / "desinstalar.py",
                 START_MENU_DIR / "desinstalar.py")
    print("[OK]  Acceso en el Menu Inicio")

    print()
    print("=" * 56)
    print("  INSTALACION COMPLETADA")
    print("=" * 56)
    print("  Abri el Corrector desde el Escritorio:")
    print("    %s" % (DESKTOP / NOMBRE_LAUNCHER))
    print()
    print("  Para desinstalar ejecuta:")
    print("    %s" % (START_MENU_DIR / NOMBRE_DESINSTALAR))
    print("=" * 56)

    try:
        import os as _os
        _os.startfile(DESKTOP / NOMBRE_LAUNCHER)
    except Exception:
        pass
    return 0


def main():
    if sys.platform != "win32":
        print("Este instalador esta pensado para Windows.")
        return 1
    return instalar()


if __name__ == "__main__":
    sys.exit(main())