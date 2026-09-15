"""Lectura y escritura de archivos .gcode en disco."""

import logging
from pathlib import Path

from .contenido import decodificar_contenido
from .constantes import ELIMINAR
from .procesador import construir_correccion

logger = logging.getLogger(__name__)


def corregir_archivo(entrada, salida=None, invertir_e=False, quitar_relleno=False,
                     curvas=False, configurar_extrusion=False,
                     tolerancia_arc=0.1, min_seg_arc=3, unir_rectas=False,
                     tolerancia_recta=0.05, desarmar=False, paso_arc=0.5):
    """Corrige un archivo .gcode en disco (CLI)."""
    entrada = Path(entrada)
    if not entrada.exists():
        raise FileNotFoundError("Archivo no encontrado: %s" % entrada)

    if salida is None:
        salida = entrada.parent / ("%s_corregido%s" % (entrada.stem, entrada.suffix))

    datos = entrada.read_bytes()
    texto = decodificar_contenido(datos)
    logger.info("Leido %s (%d bytes)", entrada, len(datos))
    contenido, reporte = construir_correccion(
        texto, entrada.name, list(ELIMINAR.keys()), invertir_e, quitar_relleno,
        curvas, configurar_extrusion, tolerancia_arc, min_seg_arc,
        unir_rectas=unir_rectas, tolerancia_recta=tolerancia_recta,
        desarmar=desarmar, paso_arc=paso_arc,
    )

    Path(salida).write_text(contenido, encoding="utf-8")
    logger.info("Escrito %s (%d bytes)", salida, len(contenido.encode("utf-8")))
    return entrada, Path(salida), reporte