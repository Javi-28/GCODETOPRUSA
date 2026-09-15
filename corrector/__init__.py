"""
corrector
Paquete del Corrector G-Code para la impresora 3D de cemento.

Modulos:
    constantes  - categorias de comandos a eliminar y sus razones.
    patrones    - regex y encodings compartidos entre modulos.
    contenido   - decodificacion de bytes (BOM/utf-8/latin-1).
    lineas      - inspeccion de una linea de gcode.
    cabecera    - cabecera del archivo corregido.
    relleno     - quitar relleno interior (infill).
    extrusion   - inversion de E (relativo/negativo) para la maquina.
    curvas      - arc welding: fusiona tramos G1 en arcos G2/G3.
    procesador  - orquestacion del pipeline (procesar_texto_gcode).
    archivo     - corregir_archivo (lectura/escritura en disco).
    cli         - interfaz de linea de comandos (main, reporte).

Uso desde la GUI (corregir_ui.py) o la CLI (corregir_gcode.py):
    from corrector import construir_correccion, corregir_archivo
"""

from .constantes import ELIMINAR, RAZONES, TODOS_ELIMINAR, clasificar_eliminables
from .contenido import decodificar_contenido
from .lineas import es_linea_movimiento, es_tipo_relleno, extraer_comando
from .cabecera import construir_cabecera
from .relleno import consumir_bloque_relleno
from .extrusion import InversorE
from .curvas import soldar_arcos, RADIO_MAXIMO_DEFECTO, RADIO_MINIMO_DEFECTO, BARRIDO_MINIMO_DEFECTO
from .procesador import construir_correccion, procesar_texto_gcode
from .archivo import corregir_archivo
from .cli import configurar_log, main

__all__ = [
    "ELIMINAR",
    "RAZONES",
    "TODOS_ELIMINAR",
    "clasificar_eliminables",
    "decodificar_contenido",
    "es_linea_movimiento",
    "es_tipo_relleno",
    "extraer_comando",
    "construir_cabecera",
    "consumir_bloque_relleno",
    "InversorE",
    "soldar_arcos",
    "RADIO_MAXIMO_DEFECTO",
    "RADIO_MINIMO_DEFECTO",
    "BARRIDO_MINIMO_DEFECTO",
    "construir_correccion",
    "procesar_texto_gcode",
    "corregir_archivo",
    "configurar_log",
    "main",
]