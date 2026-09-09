#!/usr/bin/env python3
"""
corregir_gcode.py
Transforma G-code generado por Cura (impresoras de plastico) a un formato
compatible con la impresora 3D de cemento.

Elimina comandos de temperatura, homeo, nivelacion, ventiladores y
configuracion irrelevante. Conserva movimiento (G0/G1), modos de
coordenadas (G90/G91), unidades (G21), extrusion (M82/M83), reset de
extrusor (G92) y comentarios informativos.

El parser es robusto: tolera mayusculas/minusculas, espacios raros
("G 28", "m 104"), numeros de linea ("N10 G90") y decimales ("G1.5").
La correccion es determinista: opera sobre texto plano linea por linea.

Uso CLI:
    python corregir_gcode.py <archivo_entrada> [archivo_salida]

Tambien existe una GUI (corregir_ui.py) que usa las funciones de aqui.
"""

import re
import sys
from pathlib import Path

# Comandos a eliminar, agrupados por categoria.
# Las claves son las que muestra la GUI en los checkboxes.
ELIMINAR = {
    "Temperatura bloqueante (espera sensor)": ["M109", "M190"],
    "Temperatura simple": ["M104", "M140"],
    "Homing / Nivelacion (requiere sensores)": ["G28", "G29", "G80", "G30"],
    "Ventilador": ["M106", "M107"],
    "Configuracion (flujo/velocidad/retraccion)": ["M220", "M221", "M207", "M208", "M209", "M117"],
    "Apagado de motores M84": ["M84"],
}

RAZONES = {
    "M104": "temperatura (no hay hotend/termistor)",
    "M109": "temperatura BLOQUEANTE (espera sensor inexistente, traba la maquina)",
    "M140": "temperatura (no hay cama caliente/termistor)",
    "M190": "temperatura BLOQUEANTE (espera sensor inexistente, traba la maquina)",
    "G28": "homeo (requiere endstops inexistentes)",
    "G29": "nivelacion (requiere probe/sensor inexistente)",
    "G80": "nivelacion mesh (requiere sonda inexistente)",
    "G30": "sonda (requiere probe inexistente)",
    "M106": "ventilador (la maquina de cemento no tiene fan)",
    "M107": "ventilador (la maquina de cemento no tiene fan)",
    "M220": "configuracion (porcentaje de velocidad, irrelevante)",
    "M221": "configuracion (porcentaje de flujo, irrelevante)",
    "M207": "configuracion (retraccion firmware, irrelevante)",
    "M208": "configuracion (recuperacion firmware, irrelevante)",
    "M209": "configuracion (auto-retraccion, irrelevante)",
    "M117": "configuracion (mensaje LCD, irrelevante)",
    "M84": "configuracion (deshabilitar motores, manejo manual)",
}

TODOS_ELIMINAR = set()
for _cmds in ELIMINAR.values():
    TODOS_ELIMINAR.update(_cmds)

# Numeros de linea opcionales ("N10"): muy tolerante a los formatos reales.
_REG_COMANDO = re.compile(r"^\s*(?:N\d+\s*)?([GM])\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

# Para el modo invertir_e
_REG_E = re.compile(r"\bE\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_REG_M82 = re.compile(r"^M82\b", re.IGNORECASE)

_ENC_PREFERIDAS = ("utf-8-sig", "latin-1")


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


def decodificar_contenido(datos_bytes):
    """Decodifica bytes a texto tolerando BOM y latin-1."""
    for enc in _ENC_PREFERIDAS:
        try:
            return datos_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return datos_bytes.decode("utf-8", errors="replace")


def construir_cabecera(nombre_original, categorias_activas, quedaron_sin_eliminar):
    lineas = []
    lineas.append("; Corregido por Corrector G-Code (impresora de cemento)")
    lineas.append("; Original: %s" % nombre_original)
    if quedaron_sin_eliminar:
        lineas.append("; Aviso: las categorias marcadas incluyen comandos que podrian trabar la maquina.")
    lineas.append(";")
    return "\n".join(lineas)


def procesar_texto_gcode(texto, categorias=None, invertir_e=False):
    """Corrige G-code en una cadena de texto.

    categorias: lista con claves de ELIMINAR (por defecto todas).
    invertir_e: si True convierte toda la extrusion a relativa (M83) e
        invierte el signo de cada incremento E. Util para maquinas (como la
        de cemento) que extruyen con E negativo (tornillo/bobina al reves
        del estandar). Replica el patron del archivo manual que funciona.

    Devuelve (texto_corregido, reporte) donde reporte es un dict:
    {
        "total_lineas": int,
        "lineas_escritas": int,
        "eliminadas": [{"linea": num, "texto": str, "comando": str, "razon": str}, ...],
        "por_comando": {comando: cantidad, ...},
        "categorias_activas": [str, ...],
        "invirtio_e": bool,
    }
    """
    if categorias is None:
        categorias = list(ELIMINAR.keys())

    a_eliminar = set()
    razones = {}
    for cat in categorias:
        for cmd in ELIMINAR.get(cat, []):
            a_eliminar.add(cmd)
            razones[cmd] = RAZONES.get(cmd, "desconocido")

    salida = []
    eliminadas = []
    total = len(texto.splitlines())
    escritas = 0
    por_comando = {}

    modo_e = "ABS"   # estandar Marlin: M82 absoluto
    ultimo_e = 0.0
    e_invertidos = 0

    for num, linea in enumerate(texto.splitlines(), start=1):
        ojos = linea.split(";", 1)[0].strip()

        if invertir_e:
            if re.match(r"^M82\b", ojos, re.I):
                modo_e = "ABS"
            elif re.match(r"^M83\b", ojos, re.I):
                modo_e = "REL"
            elif re.match(r"^G92\b", ojos, re.I):
                m = _REG_E.search(ojos)
                if m:
                    ultimo_e = float(m.group(1).replace(" ", ""))

        comando = extraer_comando(linea)
        if comando in a_eliminar:
            eliminadas.append({
                "linea": num,
                "texto": linea.strip(),
                "comando": comando,
                "razon": razones[comando],
            })
            por_comando[comando] = por_comando.get(comando, 0) + 1
            continue

        if invertir_e and re.match(r"^(?:[GM])\s*\d+", ojos, re.I):
            if re.match(r"^M82\b", ojos, re.I):
                linea = _REG_M82.sub("M83", linea)  # neutraliza arrancadas a absoluto
            elif re.match(r"^M83\b", ojos, re.I):
                pass
            elif re.match(r"^(?:G0|G1)\b", ojos, re.I):
                m = _REG_E.search(ojos)
                if m:
                    valor = float(m.group(1).replace(" ", ""))
                    if modo_e == "ABS":
                        incremento = valor - ultimo_e
                        ultimo_e = valor
                    else:
                        incremento = valor
                    nueva = -incremento
                    def _reemplazar_e(mm):
                        return "E" + ("%g" % nueva)
                    linea = _REG_E.sub(_reemplazar_e, linea, count=1)
                    e_invertidos += 1
            elif re.match(r"^G92\b", ojos, re.I):
                pass
            else:
                m = _REG_E.search(ojos)
                if m:
                    ultimo_e = float(m.group(1).replace(" ", ""))

        salida.append(linea)
        escritas += 1

    corregido = "\n".join(salida)
    if invertir_e:
        forcer = "M83 ; (E forzado a relativo e invertido: maquina extruye con E negativo)\n"
        corregido = forcer + corregido
    if texto.endswith(("\n", "\r")):
        corregido += "\n"

    reporte = {
        "total_lineas": total,
        "lineas_escritas": escritas,
        "eliminadas": eliminadas,
        "por_comando": por_comando,
        "categorias_activas": categorias,
        "invirtio_e": invertir_e,
        "e_invertidos": e_invertidos,
    }
    return corregido, reporte


def construir_correccion(texto, nombre_original="<desconocido>", categorias=None, invertir_e=False):
    """Devuelve (contenido_final_con_cabecera, reporte)."""
    corregido, reporte = procesar_texto_gcode(texto, categorias, invertir_e)
    cabecera = construir_cabecera(nombre_original, reporte["categorias_activas"], False)
    contenido = cabecera + "\n" + corregido
    if not texto.endswith(("\n", "\r")):
        contenido = contenido.rstrip("\n") + "\n"
    return contenido, reporte


def corregir_archivo(entrada, salida=None, invertir_e=False):
    """Corrige un archivo .gcode en disco (CLI)."""
    entrada = Path(entrada)
    if not entrada.exists():
        raise FileNotFoundError("Archivo no encontrado: %s" % entrada)

    if salida is None:
        salida = entrada.parent / ("%s_corregido%s" % (entrada.stem, entrada.suffix))

    datos = entrada.read_bytes()
    texto = decodificar_contenido(datos)
    contenido, reporte = construir_correccion(
        texto, entrada.name, list(ELIMINAR.keys()), invertir_e
    )

    Path(salida).write_text(contenido, encoding="utf-8")
    return entrada, Path(salida), reporte


def _print_reporte(entrada, salida, reporte):
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
    print()


def main():
    if len(sys.argv) < 2:
        print("Uso: python corregir_gcode.py <archivo_entrada> [archivo_salida] [--invertir-e]")
        print()
        print("Ejemplo:")
        print("  python corregir_gcode.py PI3MK2_Fijador.gcode")
        print("  python corregir_gcode.py PI3MK2_Fijador.gcode")
        print("  python corregir_gcode.py entrada.gcode salida_limpia.gcode")
        print("  python corregir_gcode.py entrada.gcode --invertir-e")
        return 1

    invertir_e = "--invertir-e" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--invertir-e"]

    entrada, salida, reporte = corregir_archivo(
        args[0], args[1] if len(args) > 1 else None, invertir_e
    )
    _print_reporte(entrada, salida, reporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())