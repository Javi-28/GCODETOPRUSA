#!/usr/bin/env python3
"""
corregir_gcode.py
Transforma G-code generado por Cura (impresoras de plastico) a un formato
compatible con la impresora 3D de cemento.

Este modulo solo reexporta la API del paquete `corrector/` (donde cada
funcionalidad esta en su propio modulo) para mantener compatibilidad con la
CLI, la GUI y scripts antiguos.

Uso CLI:
    python corregir_gcode.py <archivo_entrada> [archivo_salida] [--invertir-e]
                             [--quitar-relleno] [--curvas] [--extrusion]
                             [--tol-arc=NUM]
"""

import sys

from corrector import (
    BARRIDO_MINIMO_DEFECTO,
    ELIMINAR,
    RAZONES,
    RADIO_MAXIMO_DEFECTO,
    RADIO_MINIMO_DEFECTO,
    TODOS_ELIMINAR,
    clasificar_eliminables,
    configurar_log,
    construir_cabecera,
    construir_correccion,
    consumir_bloque_relleno,
    corregir_archivo,
    decodificar_contenido,
    es_linea_movimiento,
    es_tipo_relleno,
    extraer_comando,
    procesar_texto_gcode,
    soldar_arcos,
    main,
)

__all__ = [
    "BARRIDO_MINIMO_DEFECTO",
    "ELIMINAR",
    "RAZONES",
    "RADIO_MAXIMO_DEFECTO",
    "RADIO_MINIMO_DEFECTO",
    "TODOS_ELIMINAR",
    "clasificar_eliminables",
    "configurar_log",
    "construir_cabecera",
    "construir_correccion",
    "consumir_bloque_relleno",
    "corregir_archivo",
    "decodificar_contenido",
    "es_linea_movimiento",
    "es_tipo_relleno",
    "extraer_comando",
    "procesar_texto_gcode",
    "soldar_arcos",
    "main",
]

if __name__ == "__main__":
    sys.exit(main())