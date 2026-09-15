#!/usr/bin/env python3
r"""
compilar.py
Compila el Corrector G-Code (impresora de cemento) en todos sus formatos,
seguro segun el sistema donde se ejecute:

  Windows (esta PC):
    1)  Icono            -> build/icono.ico + build/icono.icns
    2)  PyInstaller      -> build/dist/CorrectorGcode.exe (un unico .exe,
                            con Python + tkinter adentro)
    3)  Inno Setup       -> distribucion/CorrectorGcode-Setup.exe
    4)  ZIP final        -> distribucion/CorrectorGcode-v1.0.0-windows-x64.zip
                            (setup.exe + portable + instrucciones)

  macOS (si alguien lo corre en una Mac):
    1)  Icono            -> build/icono.ico + build/icono.icns
    2)  PyInstaller      -> build/dist/CorrectorGcode.app (bundle .app)
    3)  .dmg             -> distribucion/CorrectorGcode-v1.0.0-macos-x64|arm64.dmg
    4)  ZIP final        -> distribucion/CorrectorGcode-v1.0.0-macos-x64|arm64.zip

  Paquete "Programa para Chico-Mac" (siempre):
    distribucion/Programa-para-Chico-Mac-v1.0.0.zip  -> codigo fuente listo
    para ejecutar con Python instalado (la app es 100% stdlib, tkinter viene
    en Python). Incluye:
      - INSTALAR-MAC.command : revisa e instala las dependencias que falten
                               (python3 / tkinter) y abre el programa.
      - INICIAR.command      : arranque directo si ya tiene las dependencias.
      - corregir_gcode.py, corregir_ui.py, corrector/, run.bat, compilacion/, LEEME.

    El receptor descomprime, doble clic a INSTALAR-MAC.command y listo.

No hace falta pip install de dependencias del proyecto (la app solo usa la
libreria estandar). Requiere PyInstaller instalado (y Inno Setup solo en
Windows; en macOS no hace falta nada mas, hdiutil viene con el sistema).

Uso:
    py compilacion\compilar.py          (Windows)
    python3 compilacion/compilar.py     (macOS / Linux)
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from generar_icono import generar_icns, generar_ico

PROYECTO = Path(__file__).resolve().parent.parent
COMPILACION = PROYECTO / "compilacion"
BUILD = PROYECTO / "build"
PYDIST = BUILD / "dist"
SPEC = BUILD / "spec"
WORK = BUILD / "work"
STAGING_DMG = BUILD / "dmg-staging"
DIST = PROYECTO / "distribucion"
ICONO_ICO = BUILD / "icono.ico"
ICONO_ICNS = BUILD / "icono.icns"
ISS = COMPILACION / "CorrectorGcode.iss"

VERSION = "1.0.0"
ENTRADA = PROYECTO / "corregir_ui.py"
NOMBRE = "CorrectorGcode"
README = "LEEME-INSTALACION.txt"

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"

if ES_WINDOWS:
    PLATAFORMA = "windows-x64"
    SETUP = NOMBRE + "-Setup.exe"
    PORTABLE_REL = Path("portable") / (NOMBRE + ".exe")
    APPBUILD = PYDIST / (NOMBRE + ".exe")
elif ES_MAC:
    arc = os.uname().machine                     # x86_64 / arm64
    PLATAFORMA = "macos-" + ("arm64" if arc == "arm64" else "x64")
    SETUP = NOMBRE + ".dmg"
    PORTABLE_REL = Path("portable-mac") / (NOMBRE + ".app")
    APPBUILD = PYDIST / (NOMBRE + ".app")
else:
    PLATAFORMA = sys.platform
    SETUP = ""
    PORTABLE_REL = Path("portable") / (NOMBRE + ".bin")
    APPBUILD = PYDIST / NOMBRE

ZIP_ARTIFACTO = "CorrectorGcode-v%s-%s.zip" % (VERSION, PLATAFORMA)

# Paquete fuente "Programa para Chico-Mac"
CHICO_NOMBRE = "Programa-para-Chico-Mac-v%s" % VERSION
CHICO_ZIP = CHICO_NOMBRE + ".zip"


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


def texto_leeme_windows():
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


def texto_leeme_mac():
    return "\r\n".join([
        "CORRECTOR G-CODE - Impresora de Cemento (v%s) para macOS" % VERSION,
        "=" * 64,
        "",
        "INSTALACION (opcion recomendada)",
        "--------------------------------",
        "1) Abrir  CorrectorGcode.dmg  (doble clic).",
        "2) Arrastrar  CorrectorGcode.app  a  Aplicaciones.",
        "3) La primera vez macOS pide autorizarlo (app sin",
        "   firma de Apple): clic derecho -> Abrir -> Abrir.",
        "4) El .app incluye Python + tkinter + el programa.",
        "",
        "VERSION PORTABLE (sin instalar)",
        "-------------------------------",
        "Usar la carpeta  portable-mac/  con el .app adentro:",
        "  1) Copiar CorrectorGcode.app a cualquier lugar.",
        "  2) Doble clic.",
        "",
        "REQUISITOS",
        "----------",
        "macOS 11 o superior. Esta version se compilo en una Mac con",
        "la misma familia de chip (Apple Silicon o Intel).",
        "",
        "SOLUCION DE PROBLEMAS",
        "---------------------",
        "- 'App no puede abrirse': clic derecho -> Abrir -> Abrir.",
        "- 'La app esta danada': descargar de nuevo el ZIP completo.",
        "",
    ]).encode("utf-8")


def texto_leeme_fuente():
    return "\r\n".join([
        "PROGRAMA PARA CHICO-MAC - Corrector G-Code v%s" % VERSION,
        "PAQUETE FUENTE (funciona con Python instalado)",
        "=" * 64,
        "",
        "QUE ES ESTO",
        "-----------",
        "Es el Corrector G-Code (impresora de cemento) listo para",
        "ejecutar con Python. No necesita instalaciones raras: la",
        "app usa SOLO la libreria estandar (tkinter viene con",
        "Python).",
        "",
        "COMO EJECUTAR EN LA MAC",
        "-----------------------",
        "1) Descomprimir esta carpeta.",
        "2) Doble clic en  INSTALAR-MAC.command",
        "   Ese script VA A INSTALAR LO QUE FALTE (python3 o tkinter",
        "   via Homebrew) y despues abre el programa solo.",
        "   Es la opcion mas recomendable.",
        "",
        "ALTERNATIVA (si ya tiene Python + tkinter):",
        "   Doble clic en  INICIAR.command",
        "   o desde la Terminal:",
        "       chmod +x INICIAR.command",
        "       ./INICIAR.command",
        "   o directamente:",
        "       python3 corregir_ui.py",
        "",
        "PROBLEMA COMUN",
        "--------------",
        "- 'python3 no encontrado' o 'tkinter no instalado':",
        "   usar INSTALAR-MAC.command (instala todo solo).",
        "- Si Homebrew no esta, el script indica como ponerlo.",
        "",
        "COMPILAR NATIVO (opcional, para no depender de Python)",
        "------------------------------------------------------",
        "Si quieren una app autocontenida (.app + .dmg):",
        "   pip3 install pyinstaller",
        "   python3 compilacion/compilar.py",
        "Genera distribucion/CorrectorGcode-*.dmg en la misma Mac.",
        "",
    ]).encode("utf-8")


def script_instalar_mac():
    """INSTALAR-MAC.command: chequea/instala dependencias y arranca."""
    return "\n".join([
        "#!/bin/bash",
        "# Programa para Chico-Mac - Corrector G-Code (impresora de cemento)",
        "# Revisa e instala lo que falte (python3 / tkinter) y abre el programa.",
        "",
        "set -u",
        'cd "$(dirname "$0")"',
        "",
        'echo "== Programa para Chico-Mac: revisando dependencias =="',
        "",
        "PY=python3",
        "# 1) Python",
        'if ! command -v python3 >/dev/null 2>&1; then',
        '    echo "[FALTA] Python3 no esta instalado. Lo instalo con Homebrew..."',
        '    if ! command -v brew >/dev/null 2>&1; then',
        '        echo ""',
        '        echo "Homebrew no esta. Instalalo primero desde la Terminal:"',
        '        echo "   /bin/bash -c \\"\\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\\""',
        '        echo "Despues volve a dar doble clic a este archivo."',
        '        read -r -p "Presiona Enter para cerrar... "',
        "        exit 1",
        "    fi",
        "    brew install python",
        "    PY=python3",
        'fi',
        "",
        "# 2) tkinter (la GUI)",
        'if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then',
        '    echo "[FALTA] tkinter no disponible. Instalo python-tk..."',
        '    if ! command -v brew >/dev/null 2>&1; then',
        '        echo "Hace falta Homebrew para instalar tkinter."',
        '        echo "Y despues:  brew install python-tk"',
        '        read -r -p "Presiona Enter para cerrar... "',
        "        exit 1",
        "    fi",
        "    brew install python-tk",
        'fi',
        "",
        '# 3) listo, abrir el programa',
        'echo "[OK] Dependencias listas. Abriendo el Corrector G-Code..."',
        'exec "$PY" corregir_ui.py',
        "",
    ]).encode("utf-8")


def script_iniciar_mac():
    """INICIAR.command: arranque directo (asume dependencias OK)."""
    return "\n".join([
        "#!/bin/bash",
        "# Programa para Chico-Mac - arranque directo",
        'cd "$(dirname "$0")"',
        'exec python3 corregir_ui.py',
        "",
    ]).encode("utf-8")


def copiar_portable(origen, destino):
    if origen.is_dir():
        shutil.rmtree(destino, ignore_errors=True)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(origen, destino)
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)


def armar_chico_mac():
    """Genera el ZIP fuente 'Programa para Chico-Mac' (funciona con Python)."""
    ruta_zip = DIST / CHICO_ZIP
    compilacion_py = [(f, "compilacion/%s" % f.name)
                      for f in sorted(COMPILACION.iterdir())
                      if f.is_file() and f.suffix.lower() in (".py", ".iss", ".bat", ".md")]

    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("%s/INSTALAR-MAC.command" % CHICO_NOMBRE, script_instalar_mac())
        z.writestr("%s/INICIAR.command" % CHICO_NOMBRE, script_iniciar_mac())
        z.writestr("%s/LEEME-FUENTE.txt" % CHICO_NOMBRE, texto_leeme_fuente())
        for origen, destino in (
            (PROYECTO / "corregir_gcode.py", "corregir_gcode.py"),
            (PROYECTO / "corregir_ui.py", "corregir_ui.py"),
            (PROYECTO / "run.bat", "run.bat"),
        ):
            z.write(origen, "%s/%s" % (CHICO_NOMBRE, destino))
        paquete = PROYECTO / "corrector"
        for f in sorted(paquete.glob("*.py")):
            z.write(f, "%s/corrector/%s" % (CHICO_NOMBRE, f.name))
        for origen, destino in compilacion_py:
            z.write(origen, "%s/%s" % (CHICO_NOMBRE, destino))
    return ruta_zip


def flujo():
    print("Compilando Corrector G-Code v%s [%s]" % (VERSION, PLATAFORMA))
    print("Proyecto: %s" % PROYECTO)

    if ES_WINDOWS:
        iscc = hallar_iscc()
        if iscc is None:
            print("[ERROR] Inno Setup no encontrado. Instalalo con:")
            print("        winget install JRSoftware.InnoSetup")
            sys.exit(1)

    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    for d in (PYDIST, SPEC, WORK):
        shutil.rmtree(d, ignore_errors=True)

    # 1) Iconos (ico para Windows, icns para macOS; inofensivo generar ambos)
    generar_ico(ICONO_ICO)
    generar_icns(ICONO_ICNS)
    print("[OK]  Icono .ico : %s" % ICONO_ICO)
    print("[OK]  Icono .icns: %s" % ICONO_ICNS)

    # 2) PyInstaller (onefile en Windows, onedir/.app en macOS)
    pyi_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--windowed",
        "--name", NOMBRE,
        "--icon", str(ICONO_ICO if ES_WINDOWS else ICONO_ICNS),
        "--specpath", str(SPEC),
        "--workpath", str(WORK),
        "--distpath", str(PYDIST),
    ]
    pyi_args[6:6] = ["--onefile"] if ES_WINDOWS else ["--onedir"]
    pyi_args.append(str(ENTRADA))
    ejecutar("PyInstaller: compilando el binario standalone", pyi_args, PROYECTO)

    if not APPBUILD.exists():
        print("[ERROR] No se genero %s" % APPBUILD)
        sys.exit(1)

    # 3) Instalador nativo + portable + ZIP del sistema
    if ES_WINDOWS:
        ejecutar("Inno Setup: generando setup.exe", [str(iscc), str(ISS)], COMPILACION)
        setup_real = DIST / SETUP
        if not setup_real.exists():
            print("[ERROR] No se genero %s" % setup_real)
            sys.exit(1)
        (DIST / README).write_bytes(texto_leeme_windows())
    elif ES_MAC:
        shutil.rmtree(STAGING_DMG, ignore_errors=True)
        STAGING_DMG.mkdir(parents=True, exist_ok=True)
        shutil.copytree(APPBUILD, STAGING_DMG / (NOMBRE + ".app"))
        ejecutar(
            "hdiutil: generando el .dmg",
            ["hdiutil", "create",
             "-volname", "Corrector G-Code",
             "-srcfolder", str(STAGING_DMG),
             "-ov", "-format", "UDZO",
             str(DIST / SETUP)],
            PROYECTO,
        )
        (DIST / README).write_bytes(texto_leeme_mac())

    copiar_portable(APPBUILD, DIST / PORTABLE_REL)

    with zipfile.ZipFile(DIST / ZIP_ARTIFACTO, "w", zipfile.ZIP_DEFLATED) as z:
        base = ZIP_ARTIFACTO.replace(".zip", "")
        for rel in [Path(SETUP), PORTABLE_REL, Path(README)]:
            if (DIST / rel).exists():
                z.write(DIST / rel, base + "/" + rel.as_posix())

    # 4) Paquete fuente "Programa para Chico-Mac" (siempre)
    chico = armar_chico_mac()

    print()
    print("=" * 64)
    print("  COMPILACION COMPLETADA [%s]" % PLATAFORMA)
    print("=" * 64)
    if ES_WINDOWS:
        print("  Instalador : %s" % (DIST / SETUP))
        print("  Portable   : %s" % (DIST / PORTABLE_REL))
        print("  ZIP final  : %s" % (DIST / ZIP_ARTIFACTO))
    elif ES_MAC:
        print("  .dmg       : %s" % (DIST / SETUP))
        print("  Portable   : %s" % (DIST / PORTABLE_REL))
        print("  ZIP final  : %s" % (DIST / ZIP_ARTIFACTO))
    print("  Chico-Mac  : %s" % chico)
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(flujo())