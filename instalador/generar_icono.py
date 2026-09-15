#!/usr/bin/env python3
"""
generar_icono.py
Genera build/icono.ico con el logo del Corrector G-Code (impresora de
cemento): un cuadrado oscuro redondeado con tres capas impresas de colores.

No usa dependencias externas: escribe el ICO a mano (bmp 32bpp con alfa).
"""

import struct
from pathlib import Path

ANCHO = 64
ALTO = 64

COLOR_FONDO = (30, 30, 46)        # #1e1e2e (BGRA: 46,30,30)
COLOR_BORDE = (59, 59, 82)        # #3b3b52
COLOR_BASE = (64, 64, 84)         # bandeja
COLOR_CAPA_A = (79, 156, 249)     # #4f9cf9
COLOR_CAPA_B = (123, 216, 143)    # #7bd88f
COLOR_CAPA_C = (255, 184, 108)    # #ffb86c


def _dentro_redondeado(x, y, radio, margen=0.0):
    """True si (x,y) cae dentro de un rectangulo redondeado que ocupa toda
    la imagen, con radio dado en los bordes."""
    r = radio
    izquierda, superior = margen, margen
    derecha = ANCHO - 1 - margen
    inferior = ALTO - 1 - margen
    cx = min(max(x, izquierda + r), derecha - r)
    cy = min(max(y, superior + r), inferior - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _pintar_barra(x, y, margen_izq, margen_der, sup, inf, color, radio):
    """False si el pixel no esta en la barra."""
    if not (margen_izq <= x <= ANCHO - 1 - margen_der and sup <= y <= inf):
        return None
    cx = min(max(x, margen_izq + radio), ANCHO - 1 - margen_der - radio)
    cy = min(max(y, sup + radio), inf - radio)
    if (x - cx) ** 2 + (y - cy) ** 2 <= radio * radio:
        return color
    return None


def generar_ico(destino: Path):
    px = [[(0, 0, 0, 0) for _ in range(ANCHO)] for _ in range(ALTO)]

    for y in range(ALTO):
        for x in range(ANCHO):
            color = None
            # marco exterior redondeado
            if _dentro_redondeado(x, y, 14):
                color = COLOR_FONDO
            # borde interno mas claro (2 px)
            if color is not None and 6 <= x <= ANCHO - 7 and (
                y in (7, ALTO - 8) or x in (7, ANCHO - 8)
            ):
                color = COLOR_BORDE

            # bandeja de impresion (base)
            barra = _pintar_barra(x, y, 10, 8, 50, 58, COLOR_BASE, 4)
            if barra:
                color = barra

            # tres capas impresas (escalera decreciente)
            capas = [
                (14, 12, 40, 48, COLOR_CAPA_A),
                (18, 16, 30, 38, COLOR_CAPA_B),
                (22, 20, 20, 28, COLOR_CAPA_C),
            ]
            for miz, mde, sup, inf, col in capas:
                capa = _pintar_barra(x, y, miz, mde, sup, inf, col, 3)
                if capa:
                    color = capa

            if color is None:
                continue
            b, g, r = color
            px[y][x] = (b, g, r, 255)

    _guardar_ico(destino, px)


def _guardar_ico(destino: Path, px):
    filas = ALTO // 2  # la mitad superior queda vacia arriba (bottom-up)

    xor = bytearray()
    # BMP se guarda de abajo hacia arriba
    for y in range(ALTO - 1, -1, -1):
        for x in range(ANCHO):
            b, g, r, a = px[y][x]
            xor += bytes((b, g, r, a))

    ancho_and = ((ANCHO + 31) // 32) * 4
    and_mask = bytes(ancho_and * ALTO)

    # BITMAPINFOHEADER
    head = struct.pack(
        "<IiiHHIIiiII",
        40, ANCHO, ALTO * 2, 1, 32, 0, len(xor), 0, 0, 0, 0,
    )
    datos_img = head + bytes(xor) + and_mask
    bytes_en_recurso = len(datos_img)

    # ICONDIR + ICONDIRENTRY
    entrada = struct.pack(
        "<BBBBHHII",
        ANCHO if ANCHO < 256 else 0,
        ALTO if ALTO < 256 else 0,
        0, 0, 1, 32, bytes_en_recurso, 22,
    )
    ico = struct.pack("<HHH", 0, 1, 1) + entrada + datos_img

    destino.write_bytes(ico)


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent.parent / "build" / "icono.ico"
    destino.parent.mkdir(parents=True, exist_ok=True)
    generar_ico(destino)
    print("[OK]  %s (%d bytes)" % (destino, destino.stat().st_size))