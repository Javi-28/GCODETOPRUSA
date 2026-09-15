#!/usr/bin/env python3
"""
generar_icono.py
Genera build/icono.ico (Windows) y build/icono.icns (macOS) con el logo del
Corrector G-Code (impresora de cemento): un cuadrado oscuro redondeado con
tres capas impresas de colores.

No usa dependencias externas: escribe el ICO a mano (bmp 32bpp con alfa) y
el ICNS a mano (un bloque PNG 256x256; macOS genera el resto de medidas).
"""

import struct
import zlib
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


def _px_64():
    """Dibuja el logo en una grilla 64x64 (BGRA)."""
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
    return px


def generar_ico(destino: Path):
    _guardar_ico(destino, _px_64())


def _escalar_vecino(px_64, nuevo=256):
    """Escala la grilla 64x64 a nuevo x nuevo sin suavizar (vecino mas cercano)."""
    factor = nuevo // ANCHO
    px = [[(0, 0, 0, 0) for _ in range(nuevo)] for _ in range(nuevo)]
    for y in range(nuevo):
        fila = px[y]
        for x in range(nuevo):
            b, g, r, a = px_64[y // factor][x // factor]
            if a:
                fila[x] = (r, g, b, a)
    return px


def _png_bytes(px_rgba):
    """Codifica una grilla RGBA como PNG (solo stdlib: zlib + struct)."""
    alto = len(px_rgba)
    ancho = len(px_rgba[0]) if alto else 0

    def chunk(tipo, datos):
        bloque = struct.pack(">I", len(datos)) + tipo + datos
        return bloque + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    raws = bytearray()
    for fila in px_rgba:
        raws.append(0)  # filtro None
        for r, g, b, a in fila:
            raws += bytes((r, g, b, a))
    idat = zlib.compress(bytes(raws), 9)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat)
            + chunk(b"IEND", b""))


def _icns_bytes(png):
    """Arma un fichero ICNS con un solo bloque PNG 'ic08' (256x256)."""
    bloque = struct.pack(">4sI", b"ic08", len(png) + 8) + png
    return b"icns" + struct.pack(">I", len(bloque) + 8) + bloque


def generar_icns(destino: Path):
    """Genera build/icono.icns (macOS) a partir del mismo dibujo del .ico."""
    destino.write_bytes(_icns_bytes(_png_bytes(_escalar_vecino(_px_64()))))


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
    build = Path(__file__).resolve().parent.parent / "build"
    build.mkdir(parents=True, exist_ok=True)
    for destino, fn in (("icono.ico", generar_ico), ("icono.icns", generar_icns)):
        archivo = build / destino
        fn(archivo)
        print("[OK]  %s (%d bytes)" % (archivo, archivo.stat().st_size))