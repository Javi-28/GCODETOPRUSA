"""Inspeccion de una linea de gcode (comando, movimiento, seccion)."""

from .patrones import _REG_COMANDO, _REG_MOVIMIENTO, _REG_TIPO


def extraer_comando(linea):
    """Extrae el codigo M/G de una linea sin comentarios y normalizado.

    Acepta: "G90", "g90", "G 90", "N10 M109 S231", "M104; comentario".
    Iguala el comando entero (G80 != G8). Devuelve None si la linea
    no es un comando (comentario, vacio, etc).
    """
    cuerpo = linea.split(";", 1)[0].strip().lstrip("\ufeff")
    if not cuerpo:
        return None
    m = _REG_COMANDO.match(cuerpo)
    if not m:
        return None
    letra = m.group(1).upper()
    numero = m.group(2).split(".")[0]
    return letra + numero


def es_linea_movimiento(linea):
    """True si la linea es un movimiento G0/G1/G2/G3 (sin comentario)."""
    ojos = linea.split(";", 1)[0].strip()
    return bool(_REG_MOVIMIENTO.match(ojos))


def es_tipo_relleno(linea):
    """True si la linea es un marcador ;TYPE: del relleno interior (infill).

    Cura 4.13+ usa ";TYPE:FILL", las versiones anteriores ";TYPE:INFILL".
    """
    m = _REG_TIPO.search(linea)
    if not m:
        return False
    tipo = m.group(1).upper()
    return tipo.startswith("FILL") or tipo.startswith("INFILL")