"""Quitar relleno interior (infill) marcado por Cura con ;TYPE:FILL/INFILL."""

from .lineas import es_linea_movimiento
from .patrones import _REG_E


def consumir_bloque_relleno(lineas, i, total):
    """Consume los movimientos tras un marcador ;TYPE:FILL/INFILL.

    Devuelve (j, ultimo_e):
      - j: primera linea que NO es de movimiento (o 'total' si se acabo).
      - ultimo_e: ultimo valor E absoluto del bloque, o None si no tenia E.
    """
    j = i + 1
    ultimo_e = None
    while j < total and es_linea_movimiento(lineas[j]):
        m = _REG_E.search(lineas[j].split(";", 1)[0].strip())
        if m:
            ultimo_e = float(m.group(1).replace(" ", ""))
        j += 1
    return j, ultimo_e