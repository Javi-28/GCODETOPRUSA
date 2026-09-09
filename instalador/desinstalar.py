#!/usr/bin/env python3
"""
desinstalar.py
Desinstala el Corrector G-Code. Este archivo vive dentro de la carpeta
instalada (%LOCALAPPDATA%\\Programs\\CorrectorGcode), por eso se elimina
a si mismo programando un .bat temporal que limpia todo al salir.

Uso:
    py desinstalar.py
"""

import os
import tempfile
from pathlib import Path

INSTALL_DIR = Path(__file__).resolve().parent
NOMBRE_LAUNCHER = "Iniciar CorrectorGcode.bat"

DESKTOP = Path.home() / "Desktop"
APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
START_MENU_DIR = APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "CorrectorGcode"


def main():
    print("Desinstalando Corrector G-Code...")
    print("  Carpeta: %s" % INSTALL_DIR)

    eliminados = []

    # 1) Acceso directo del Escritorio
    launcher_desktop = DESKTOP / NOMBRE_LAUNCHER
    if launcher_desktop.exists():
        launcher_desktop.unlink()
        eliminados.append("Escritorio: %s" % NOMBRE_LAUNCHER)

    # 2) Accesos del Menu Inicio
    for p in list(START_MENU_DIR.iterdir()) if START_MENU_DIR.exists() else []:
        p.unlink()
        eliminados.append("Menu Inicio: %s" % p.name)
    if START_MENU_DIR.exists():
        try:
            START_MENU_DIR.rmdir()
        except OSError:
            pass

    # 3) Programar limpieza de la carpeta + self del sistema
    bat = Path(tempfile.gettempdir()) / "_limpiar_corrector.bat"
    contenido = (
        "@echo off\r\n"
        "ping 127.0.0.1 -n 3 >nul\r\n"
        'if exist "%s" rmdir /s /q "%s"\r\n'
        'del "%%~f0"\r\n'
    ) % (INSTALL_DIR, INSTALL_DIR)
    bat.write_text(contenido, encoding="ascii")

    os.startfile(bat)

    print("  Se eliminaron:")
    for item in eliminados:
        print("    - %s" % item)
    print()
    print("La carpeta %s se eliminara en unos segundos." % INSTALL_DIR)
    print("Desinstalacion completada.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())