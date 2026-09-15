#!/usr/bin/env python3
r"""
compilar.py
Compila el Corrector G-Code en un instalador profesional de Windows.

Pipeline:
  1)  Genera el icono (build/icono.ico)
  2)  PyInstaller  -> build/dist/CorrectorGcode.exe   (un unico .exe, sin
                      Python en la PC de destino, tkinter incluido)
  3)  Inno Setup   -> distribucion/CorrectorGcode-Setup.exe
                      (instalador con accesos, desinstalador en Panel de
                      Control y asistente grafico en espanol)
  4)  ZIP final    -> distribucion/CorrectorGcode-v1.0.0-windows-x64.zip
                      (setup.exe + version portable + instrucciones)

No necesita pip install de dependencias del proyecto (la app solo usa la
libreria estandar). Solo requiere PyInstaller e Inno Setup instalados.

Uso:
    py compilacion\compilar.py
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from generar_icono import generar_ico

PROYECTO = Path(__file__).resolve().parent.parent
COMPILACION = PROYECTO / "compilacion"
BUILD = PROYECTO / "build"
PYDIST = BUILD / "dist"
SPEC = BUILD / "spec"
WORK = BUILD / "work"
DIST = PROYECTO / "distribucion"
ICONO = BUILD / "icono.ico"
ISS = COMPILACION / "CorrectorGcode.iss"

VERSION = "1.0.0"
ENTRADA = PROYECTO / "corregir_ui.py"
NOMBRE_EXE = "CorrectorGcode"
SETUP = "CorrectorGcode-Setup.exe"
ZIP_BASE = "CorrectorGcode-v%s-windows-x64" % VERSION
ZIP_ARCHIVO = ZIP_BASE + ".zip"
README = "LEEME-INSTALACION.txt"
PORTABLE = Path("portable") / "CorrectorGcode.exe"


def hallar_iscc():
    candidatos = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for p in candidatos:
        if p.exists():
            return p
    return None


def ejecutar(descripcion, lista, cwd):
    print()
    print("#" * 60)
    print("#  %s" % descripcion)
    print("#" * 60)
    print("  $ %s\n" % " ".join(str(x) for x in lista))
    resultado = subprocess.run(lista, cwd=str(cwd))
    if resultado.returncode != 0:
        print("\n[ERROR] Falla en: %s" % descripcion)
        sys.exit(resultado.returncode)
    print("[OK]  %s" % descripcion)


def texto_leeme():
    return "\r\n".join([
        "CORRECTOR G-CODE - Impresora de Cemento (v%s)" % VERSION,
        "=" * 64,
        "",
        "LO QUE NECESITA LA OTRA COMPUTADORA",
        "-------------------------------------",
        "Nada. Ni Python, ni pip, ni ninguna otra cosa.",
        "El .exe incluye Python + tkinter + el programa.",
        "Solo Windows 10/11 de 64 bits.",
        "",
        "OPCION A - INSTALACION COMPLETA (recomendada)",
        "---------------------------------------------",
        "1) Doble clic en  CorrectorGcode-Setup.exe",
        "2) Sigo las pantallas en espanol (Instalar).",
        "3) Se crean accesos directos en el Menu Inicio y",
        "   (opcional) en el Escritorio.",
        "4) Uninstalar en el Panel de Control cuando no se use.",
        "",
        "OPCION B - VERSION PORTABLE (sin instalar)",
        "------------------------------------------",
        "1) Copiar la carpeta  portable/  a cualquier lugar",
        "   (pendrive, escritorio, la otra PC...).",
        "2) Doble clic en  CorrectorGcode.exe",
        "No se registra nada en el sistema.",
        "",
        "DOCUMENTACION",
        "-------------",
        "El analisis tecnico se instala dentro de la app en",
        "  Documentacion/ANALISIS.md",
        "",
        "SOLUCION DE PROBLEMAS",
        "---------------------",
        "- Windows SmartScreen: pulsar 'Mas informacion' ->",
        "  'Ejecutar de todas formas' (es lo normal la primera vez).",
        "- Si no se abre la ventana, revisar que el archivo no",
        "  quede bloqueado por el antivirus.",
        "",
    ]).encode("utf-8")


def flujo():
    print("Compilando Corrector G-Code v%s (Windows x64)" % VERSION)
    print("Proyecto: %s" % PROYECTO)

    iscc = hallar_iscc()
    if iscc is None:
        print("[ERROR] Inno Setup no encontrado. Instalalo con:")
        print("        winget install JRSoftware.InnoSetup")
        sys.exit(1)

    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    for d in (PYDIST, SPEC, WORK):
        shutil.rmtree(d, ignore_errors=True)

    # 1) Icono
    generar_ico(ICONO)
    print("[OK]  Icono: %s" % ICONO)

    # 2) PyInstaller
    ejecutar(
        "PyInstaller: compilando el .exe standalone",
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean",
            "--onefile", "--windowed",
            "--name", NOMBRE_EXE,
            "--icon", str(ICONO),
            "--specpath", str(SPEC),
            "--workpath", str(WORK),
            "--distpath", str(PYDIST),
            str(ENTRADA),
        ],
        PROYECTO,
    )

    # 3) Inno Setup
    ejecutar("Inno Setup: generando setup.exe", [str(iscc), str(ISS)], COMPILACION)

    setup_real = DIST / SETUP
    if not setup_real.exists():
        print("[ERROR] No se genero %s" % setup_real)
        sys.exit(1)

    # 4) Copiar portable + LEEME y armar el ZIP
    (DIST / README).write_bytes(texto_leeme())
    (DIST / PORTABLE).parent.mkdir(exist_ok=True)
    shutil.copy2(PYDIST / (NOMBRE_EXE + ".exe"), DIST / PORTABLE)

    with zipfile.ZipFile(DIST / ZIP_ARCHIVO, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in [SETUP, PORTABLE.as_posix(), README]:
            z.write(DIST / rel, ZIP_BASE + "/" + rel)

    print()
    print("=" * 64)
    print("  COMPILACION COMPLETADA")
    print("=" * 64)
    print("  Instalador : %s" % (DIST / SETUP))
    print("  Portable   : %s" % (DIST / PORTABLE))
    print("  ZIP final  : %s" % (DIST / ZIP_ARCHIVO))
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(flujo())