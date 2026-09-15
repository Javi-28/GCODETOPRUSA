"""CLI del Corrector G-Code (main, reporte, logging a consola y archivo)."""

import logging
import sys
from pathlib import Path

from .archivo import corregir_archivo

logger = logging.getLogger(__name__)

FORMATO_LOG = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
NIVEL_LOG = logging.INFO


def configurar_log():
    """Configura logging a consola y a logs/CorrectorGcode.log.

    La carpeta 'logs/' se crea junto al script (en fuente) o junto al
    ejecutable (exe/Mac). Devuelve la ruta del archivo de log, o None si la
    carpeta no es escribible.
    """
    logging.basicConfig(
        level=NIVEL_LOG,
        format=FORMATO_LOG,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).resolve().parent.parent
        carpeta = base / "logs"
        carpeta.mkdir(exist_ok=True)
        ruta = carpeta / "CorrectorGcode.log"
        handler = logging.FileHandler(ruta, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMATO_LOG, "%Y-%m-%d %H:%M:%S"))
        logging.getLogger().addHandler(handler)
        return ruta
    except OSError:
        return None


def _print_reporte(entrada, salida, reporte, ruta_log=None):
    print()
    print("=" * 62)
    print("  CORRECCION DE G-CODE COMPLETADA")
    print("=" * 62)
    print("  Archivo entrada:  %s" % entrada.name)
    print("  Archivo salida:   %s" % salida.name)
    print("=" * 62)
    print("  Lineas totales:       %d" % reporte["total_lineas"])
    print("  Lineas escritas:      %d" % reporte["lineas_escritas"])
    print("  Lineas eliminadas:    %d" % len(reporte["eliminadas"]))
    if reporte.get("relleno_removido"):
        print("  Relleno quitado:       %d bloques / %d lineas"
              % (reporte["bloques_relleno"], reporte["relleno_removido"]))
    if reporte.get("arcos_procesados"):
        print("  Arcos G2/G3:           %d (curvas en plano XY)" % reporte["arcos_procesados"])
    if reporte.get("arcos_soldados"):
        print("  Arcos soldados:       %d (G1 -> G2/G3, %d lineas ahorradas)"
              % (reporte["arcos_soldados"], reporte["lineas_ahorradas"]))
    if reporte.get("invirtio_e"):
        print("  E invertido:          %d lineas (modo relativo M83)" % reporte["e_invertidos"])
    print("=" * 62)

    if reporte["eliminadas"]:
        print()
        print("  COMANDOS ELIMINADOS:")
        print("  %-8s %-6s %s" % ("Linea", "Cmd", "Razon"))
        print("  " + "-" * 56)
        for e in reporte["eliminadas"]:
            texto = e["texto"]
            texto = texto[:36] + "..." if len(texto) > 36 else texto
            print("  %-8d %-6s %s  [%s]" % (e["linea"], e["comando"], e["razon"], texto))
    print()
    print("  ARCHIVO GENERADO: %s" % salida.resolve())
    if ruta_log:
        print("  LOG DETALLADO:   %s" % ruta_log)
    print()


def main():
    FLAGS = ("--invertir-e", "--quitar-relleno", "--curvas", "--extrusion")
    if len(sys.argv) < 2:
        print("Uso: python corregir_gcode.py <archivo_entrada> [archivo_salida] [FLAGS]")
        print()
        print("FLAGS:")
        print("  --invertir-e       Extrusion a relativa (M83) con E negativo")
        print("  --quitar-relleno   Borra bloques ;TYPE:FILL/INFILL (infill)")
        print("  --curvas           Fusiona tramos G1 poligonales en arcos G2/G3")
        print("                     (arc welding) e inyecta G17. Opcional:")
        print("                     --tol-arc=NUM desviacion maxima en mm (default 0.1)")
        print("                     Solo convierte curvas reales: rectas y cuadrados")
        print("                     (radio gigante o giro minimo) quedan como G1.")
        print("  --extrusion        Inyecta M200 S0/M220 S100/M221 S100 y conserva M220/M221")
        print()
        print("Ejemplos:")
        print("  python corregir_gcode.py PI3MK2_Fijador.gcode --curvas --invertir-e")
        print("  python corregir_gcode.py entrada.gcode --curvas --tol-arc=0.05")
        print("  python corregir_gcode.py entrada.gcode --extrusion --quitar-relleno")
        return 1

    ruta_log = configurar_log()
    invertir_e = "--invertir-e" in sys.argv
    quitar_relleno = "--quitar-relleno" in sys.argv
    curvas = "--curvas" in sys.argv
    configurar_extrusion = "--extrusion" in sys.argv

    tolerancia_arc = 0.1
    for a in sys.argv:
        if a.startswith("--tol-arc="):
            try:
                tolerancia_arc = float(a.split("=", 1)[1])
            except ValueError:
                pass

    args = [a for a in sys.argv[1:] if a not in FLAGS and not a.startswith("--tol-arc=")]

    logger.info("CLI: entrada=%s flags(i=%s,relleno=%s,curvas=%s,extrusion=%s)",
                args[0], invertir_e, quitar_relleno, curvas, configurar_extrusion)
    entrada, salida, reporte = corregir_archivo(
        args[0], args[1] if len(args) > 1 else None, invertir_e, quitar_relleno,
        curvas, configurar_extrusion, tolerancia_arc,
    )
    _print_reporte(entrada, salida, reporte, ruta_log)
    return 0