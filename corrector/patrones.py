"""Regex y encodings compartidos entre los modulos del paquete."""

import re

# Encodings preferidos para decodificar los .gcode (pueden traer BOM UTF-8/16).
_ENCS_PREFERIDAS = ("utf-8-sig", "latin-1")

# Numeros de linea opcionales ("N10"): muy tolerante a los formatos reales.
_REG_COMANDO = re.compile(r"^\s*(?:N\d+\s*)?([GM])\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

# Para el modo invertir_e
_REG_E = re.compile(r"\bE\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_REG_M82 = re.compile(r"^M82\b", re.IGNORECASE)

# Marcadores de seccion de Cura para el relleno interior (infill)
_REG_TIPO = re.compile(r";TYPE:\s*([A-Z-]+)\b", re.IGNORECASE)
_REG_MOVIMIENTO = re.compile(r"^(?:N\d+\s*)?(?:G[0-3])\b", re.IGNORECASE)

# Para arc welding (curvas G2/G3): coordenadas, E y feedrate de una linea
_REG_G1_XY = re.compile(r"^\s*(?:N\d+\s*)?G1\b", re.IGNORECASE)
_REG_XYZ = re.compile(r"\b([XYZ])\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_REG_F = re.compile(r"\bF\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
# Radio de un arco G2/G3 (necesario para desarmar arcos a G1).
_REG_R = re.compile(r"\bR\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def numero(parte):
    """Convierte un grupo capturado a float tolerando espacios raros."""
    return float(parte.replace(" ", ""))