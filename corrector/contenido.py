"""Decodificacion de los bytes de un archivo .gcode a texto."""

from .patrones import _ENCS_PREFERIDAS


def decodificar_contenido(datos_bytes):
    """Decodifica bytes a texto tolerando BOM y latin-1."""
    for enc in _ENCS_PREFERIDAS:
        try:
            return datos_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return datos_bytes.decode("utf-8", errors="replace")