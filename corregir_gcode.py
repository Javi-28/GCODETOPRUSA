#!/usr/bin/env python3
"""
corregir_gcode.py
Transforma G-code generado por Cura (impresoras de plastico) a un formato
compatible con la impresora 3D de cemento.

Elimina comandos de temperatura, homeo, nivelacion, ventiladores y
configuracion irrelevante. Conserva movimiento (G0-G3), modos de
coordenadas (G90/G91), unidades (G21), extrusion (M82/M83), reset de
extrusor (G92) y comentarios informativos. Opcionalmente puede quitar el
relleno interior (infill) que Cura marca con ";TYPE:FILL"/";TYPE:INFILL",
activar curvas G2/G3 fusionando los tramos G1 poligonales de Cura en
arcos (arc welding, con tolerancia configurable y G17), o configurar
extrusion (M200/M220/M221).

El parser es robusto: tolera mayusculas/minusculas, espacios raros
("G 28", "m 104"), numeros de linea ("N10 G90") y decimales ("G1.5").
La correccion es determinista: opera sobre texto plano linea por linea.

Uso CLI:
    python corregir_gcode.py <archivo_entrada> [archivo_salida]

Tambien existe una GUI (corregir_ui.py) que usa las funciones de aqui.
"""

import math
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

# Marcadores de seccion de Cura para el relleno interior (infill)
_REG_TIPO = re.compile(r";TYPE:\s*([A-Z-]+)\b", re.IGNORECASE)
_REG_MOVIMIENTO = re.compile(r"^(?:N\d+\s*)?(?:G[0-3])\b", re.IGNORECASE)

# Para arc welding (curvas G2/G3): coordenadas, E y feedrate de una linea
_REG_G1_XY = re.compile(r"^\s*(?:N\d+\s*)?G1\b", re.IGNORECASE)
_REG_XYZ = re.compile(r"\b([XYZ])\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_REG_F = re.compile(r"\bF\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)

_ENC_PREFERIDAS = ("utf-8-sig", "latin-1")


def es_tipo_relleno(linea):
    """True si la linea es un marcador ;TYPE: del relleno interior (infill).

    Cura 4.13+ usa ";TYPE:FILL", las versiones anteriores ";TYPE:INFILL".
    """
    m = _REG_TIPO.search(linea)
    if not m:
        return False
    tipo = m.group(1).upper()
    return tipo.startswith("FILL") or tipo.startswith("INFILL")


def es_linea_movimiento(linea):
    """True si la linea es un movimiento G0/G1/G2/G3 (sin comentario)."""
    ojos = linea.split(";", 1)[0].strip()
    return bool(_REG_MOVIMIENTO.match(ojos))


# ---------------------------------------------------------------------------
# Arc welding: fusiona tramos de G1 poligonales (Cura) en arcos G2/G3 con R.
# La impresora de cemento tiene ARC_SUPPORT activo en Marlin; el archivo de
# referencia "hace bien curvas" confirma que G2/G3 (incluidos helicoidales
# con Z) funcionan y dan un codigo mas acotado y un giro mas suave.
# ---------------------------------------------------------------------------

def _fmt(v, dec=6):
    """Formatea un float sin ceros a la derecha (ej. 25.281546, 2400)."""
    s = ("%.*f" % (dec, v)).rstrip("0").rstrip(".")
    return s if s not in ("", "-0", "0") else "0"


def _extr_xyz_ef(linea):
    """Extrae (xyz, e, f) de una linea de movimiento.

    xyz es dict {"X":.., "Y":.., "Z":..} (Z opcional); e y f son float o None.
    """
    cuerpo = linea.split(";", 1)[0].strip().lstrip("\ufeff")
    xyz = {k.upper(): float(v) for k, v in _REG_XYZ.findall(cuerpo)}
    m = _REG_E.search(cuerpo)
    e = float(m.group(1).replace(" ", "")) if m else None
    m = _REG_F.search(cuerpo)
    f = float(m.group(1).replace(" ", "")) if m else None
    return xyz, e, f


def _circuncentro(pt_a, pt_b, pt_c):
    """Centro del circulo por 3 puntos; None si son colineales."""
    (ax, ay), (bx, by), (cx2, cy2) = pt_a, pt_b, pt_c
    d = 2.0 * (ax * (by - cy2) + bx * (cy2 - ay) + cx2 * (ay - by))
    if abs(d) < 1e-9:
        return None
    aa = ax * ax + ay * ay
    bb = bx * bx + by * by
    cc = cx2 * cx2 + cy2 * cy2
    ux = (aa * (by - cy2) + bb * (cy2 - ay) + cc * (ay - by)) / d
    uy = (aa * (cx2 - bx) + bb * (ax - cx2) + cc * (bx - ax)) / d
    return ux, uy


def _ajuste_arco(puntos, tolerancia):
    """Si TODOS los puntos caen en un circulo dentro de tolerancia, devuelve
    (cx, cy, r, delta_total). delta_total>0 -> G3 (anti-horario), <0 -> G2."""
    n = len(puntos)
    if n < 3:
        return None
    c = _circuncentro(puntos[0], puntos[n // 2], puntos[-1])
    if c is None:
        return None
    cx, cy = c
    r = math.hypot(puntos[0][0] - cx, puntos[0][1] - cy)
    for px, py in puntos:
        if abs(math.hypot(px - cx, py - cy) - r) > tolerancia:
            return None
    total = 0.0
    prev = math.atan2(puntos[0][1] - cy, puntos[0][0] - cx)
    for i in range(1, n):
        cur = math.atan2(puntos[i][1] - cy, puntos[i][0] - cx)
        delta = cur - prev
        if delta > math.pi:
            delta -= 2.0 * math.pi
        elif delta < -math.pi:
            delta += 2.0 * math.pi
        total += delta
        prev = cur
    if abs(total) < 1e-6:      # recta o retroceso: no es un arco
        return None
    return cx, cy, r, total


def soldar_arcos(lineas, tolerancia=0.1, min_seg=3, modo_e_relativo=False):
    """Reemplaza tramos de G1 XY consecutivos por un unico G2/G3 R cuando
    encajan en un circulo dentro de 'tolerancia' (mm).

    - Solo toca lineas G1 con X e Y estrictamente consecutivas (como emite
      Cura para cada curva). Cualquier otro comando, comentario o cambio de
      modo corta el tramo.
    - Los tramos que no encajen en un radio quedan como G1 (nunca se tocan).
    - 'modo_e_relativo' fuerza modo relativo (M83): cuando viene de
      invertir_e todos los E ya son incrementos, aunque el archivo no tenga
      un M83 propio. Si es False se detecta M82/M83 linea a linea.
    - E se emite como suma de incrementos (modo relativo M83) o como valor
      absoluto final (M82), segun el modo vigente.
    Devuelve (nuevas_lineas, {"arcos_soldados": int, "lineas_ahorradas": int}).
    """
    min_puntos = min_seg + 1
    modo_e = "REL" if modo_e_relativo else "ABS"
    salida = []
    soldados = 0
    ahorro = 0
    i = 0
    n = len(lineas)

    while i < n:
        linea = lineas[i]
        ojos = linea.split(";", 1)[0].strip().lstrip("\ufeff")

        if re.match(r"^M82\b", ojos, re.I):
            modo_e = "ABS"
            salida.append(linea)
            i += 1
            continue
        if re.match(r"^M83\b", ojos, re.I):
            modo_e = "REL"
            salida.append(linea)
            i += 1
            continue

        if not _REG_G1_XY.match(ojos):
            salida.append(linea)
            i += 1
            continue

        # ---- construir el run de G1 XY consecutivos ----
        run = []
        idx = i
        while idx < n:
            ojos2 = lineas[idx].split(";", 1)[0].strip().lstrip("\ufeff")
            if not _REG_G1_XY.match(ojos2):
                break
            xyz, e, f = _extr_xyz_ef(lineas[idx])
            if xyz.get("X") is None or xyz.get("Y") is None:
                break
            run.append((xyz, e, f))
            idx += 1

        if len(run) < min_puntos:
            salida.append(linea)
            i += 1
            continue

        # ---- buscar el prefix mas largo que encaje en un arco ----
        mejor = None
        for k in range(min_puntos, len(run) + 1):
            pts = [(p[0]["X"], p[0]["Y"]) for p in run[:k]]
            aj = _ajuste_arco(pts, tolerancia)
            if aj is not None:
                mejor = (k, aj)

        if mejor is None:
            salida.append(linea)
            i += 1
            continue

        consumidos, (cx, cy, r, delta_total) = mejor
        fin = run[consumidos - 1][0]
        frun = run[consumidos - 1][2]

        sentido = "G3" if delta_total > 0 else "G2"
        partes = [sentido]
        partes.append("X" + _fmt(fin.get("X")))
        partes.append("Y" + _fmt(fin.get("Y")))
        if fin.get("Z") is not None:
            partes.append("Z" + _fmt(fin["Z"]))
        partes.append("R" + _fmt(r))

        valores_e = [p[1] for p in run[:consumidos] if p[1] is not None]
        if valores_e:
            e_tot = sum(valores_e) if modo_e == "REL" else valores_e[-1]
            partes.append("E" + _fmt(e_tot))
        if frun is not None:
            partes.append("F" + _fmt(frun, 3))

        salida.append(" ".join(partes))
        soldados += 1
        ahorro += consumidos - 1
        i += consumidos

    return salida, {"arcos_soldados": soldados, "lineas_ahorradas": ahorro}


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


def construir_cabecera(nombre_original, categorias_activas, quedaron_sin_eliminar,
                       quitar_relleno=False, curvas=False, configurar_extrusion=False):
    lineas = []
    lineas.append("; Corregido por Corrector G-Code (impresora de cemento)")
    lineas.append("; Original: %s" % nombre_original)
    if quedaron_sin_eliminar:
        lineas.append("; Aviso: las categorias marcadas incluyen comandos que podrian trabar la maquina.")
    if quitar_relleno:
        lineas.append("; Relleno interior (infill) eliminado: solo se conservan las paredes.")
    if curvas:
        lineas.append("; Curvas activadas: G17 (plano XY) + arcos G2/G3 (arc welding).")
    if configurar_extrusion:
        lineas.append("; Extrusion configurada: M200 S0 (sin volumetrico), M221 S100 (flujo 100%).")
    lineas.append(";")
    return "\n".join(lineas)


def procesar_texto_gcode(texto, categorias=None, invertir_e=False, quitar_relleno=False,
                         curvas=False, configurar_extrusion=False,
                         tolerancia_arc=0.1, min_seg_arc=3):
    """Corrige G-code en una cadena de texto.

    categorias: lista con claves de ELIMINAR (por defecto todas).
    invertir_e: si True convierte toda la extrusion a relativa (M83) e
        invierte el signo de cada incremento E. Util para maquinas (como la
        de cemento) que extruyen con E negativo (tornillo/bobina al reves
        del estandar). Replica el patron del archivo manual que funciona.
    quitar_relleno: si True elimina el relleno interior que Cura marca con
        ";TYPE:FILL" o ";TYPE:INFILL", dejando solo las paredes. Al borrar
        el bloque se resincroniza el extrusor con un "G92 E<valor>" para
        que las extrusiones siguientes no se desfazen.
    curvas: si True fusiona los tramos de G1 poligonales de Cura en arcos
        G2/G3 (arc welding) e inyecta G17 al inicio. Los arcos resultan en
        un codigo mas compacto y un giro mas suave en la maquina de cemento.
        'tolerancia_arc' es la desviacion maxima (mm) aceptada entre la
        curva original y el arco (default 0.1). 'min_seg_arc' es la cantidad
        minima de segmentos G1 fusionados por arco (default 3).
    configurar_extrusion: si True inyecta M200 S0 (desactivar volumetrico),
        M220 S100 (velocidad al 100%) y M221 S100 (flujo al 100%) al
        inicio, y NO elimina los comandos M220/M221 del archivo original.

    Devuelve (texto_corregido, reporte) donde reporte es un dict:
    {
        "total_lineas": int,
        "lineas_escritas": int,
        "eliminadas": [{"linea": num, "texto": str, "comando": str, "razon": str}, ...],
        "por_comando": {comando: cantidad, ...},
        "categorias_activas": [str, ...],
        "invirtio_e": bool,
        "relleno_removido": int (lineas de infill quitadas),
        "bloques_relleno": int (bloques ;TYPE:FILL/INFILL quitados),
        "arcos_procesados": int (G2/G3 preexistentes procesados en invertir_e),
        "arcos_soldados": int (tramos G1 fusionados a G2/G3),
        "lineas_ahorradas": int (lineas G1 reemplazadas por los arcos),
    }
    """
    if categorias is None:
        categorias = list(ELIMINAR.keys())

    a_eliminar = set()
    razones = {}
    for cat in categorias:
        for cmd in ELIMINAR.get(cat, []):
            if configurar_extrusion and cmd in ("M220", "M221"):
                continue
            a_eliminar.add(cmd)
            razones[cmd] = RAZONES.get(cmd, "desconocido")

    lineas = texto.splitlines()
    salida = []
    eliminadas = []
    total = len(lineas)
    escritas = 0
    por_comando = {}
    lineas_relleno = 0
    bloques_relleno = 0
    arcos_procesados = 0

    modo_e = "ABS"   # estandar Marlin: M82 absoluto
    ultimo_e = 0.0
    e_invertidos = 0

    i = 0
    while i < total:
        num = i + 1
        linea = lineas[i]
        ojos = linea.split(";", 1)[0].strip()

        # ---- Quitar bloque de relleno interior (infill) ----
        if quitar_relleno and es_tipo_relleno(linea):
            ultimo_e_bloque = None
            j = i + 1
            while j < total and es_linea_movimiento(lineas[j]):
                m = _REG_E.search(lineas[j].split(";", 1)[0].strip())
                if m:
                    ultimo_e_bloque = float(m.group(1).replace(" ", ""))
                j += 1
            quitaste = j - i
            lineas_relleno += quitaste
            if quitaste:
                bloques_relleno += 1
            if ultimo_e_bloque is not None:
                comando_sig = extraer_comando(lineas[j]) if j < total else None
                if comando_sig != "G92":
                    resync = ("G92 E%g ; relleno interior quitado, "
                              "extrusor resincronizado" % ultimo_e_bloque)
                    lineas.insert(j, resync)
                    total += 1
            i = j
            continue

        # ---- Modo invertir_e: trackear modo/posicion del extrusor ----
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
            i += 1
            continue

        if invertir_e and re.match(r"^(?:[GM])\s*\d+", ojos, re.I):
            if re.match(r"^M82\b", ojos, re.I):
                linea = _REG_M82.sub("M83", linea)  # neutraliza arrancadas a absoluto
            elif re.match(r"^M83\b", ojos, re.I):
                pass
            elif re.match(r"^(?:G[0-3])\b", ojos, re.I):
                if re.match(r"^G[23]\b", ojos, re.I):
                    arcos_procesados += 1
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
        i += 1

    # ---- Arc welding (curvas): fusionar tramos G1 poligonales en G2/G3 ----
    arcos_soldados = 0
    lineas_ahorradas = 0
    if curvas:
        salida, info_weld = soldar_arcos(salida, tolerancia_arc, min_seg_arc,
                                         modo_e_relativo=invertir_e)
        arcos_soldados = info_weld["arcos_soldados"]
        lineas_ahorradas = info_weld["lineas_ahorradas"]

    corregido = "\n".join(salida)
    prefijo = []
    if curvas:
        prefijo.append("G17 ; (plano XY activado para curvas G2/G3)")
    if configurar_extrusion:
        prefijo.append("M200 S0 ; (extrusion volumetrica desactivada)")
        prefijo.append("M220 S100 ; (factor de velocidad al 100%)")
        prefijo.append("M221 S100 ; (factor de flujo de extrucion al 100%)")
    if invertir_e:
        prefijo.append("M83 ; (E forzado a relativo e invertido: maquina extruye con E negativo)")
    if prefijo:
        corregido = "\n".join(prefijo) + "\n" + corregido
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
        "relleno_removido": lineas_relleno,
        "bloques_relleno": bloques_relleno,
        "arcos_procesados": arcos_procesados,
        "arcos_soldados": arcos_soldados,
        "lineas_ahorradas": lineas_ahorradas,
    }
    return corregido, reporte


def construir_correccion(texto, nombre_original="<desconocido>", categorias=None,
                         invertir_e=False, quitar_relleno=False, curvas=False,
                         configurar_extrusion=False, tolerancia_arc=0.1,
                         min_seg_arc=3):
    """Devuelve (contenido_final_con_cabecera, reporte)."""
    corregido, reporte = procesar_texto_gcode(
        texto, categorias, invertir_e, quitar_relleno, curvas,
        configurar_extrusion, tolerancia_arc, min_seg_arc,
    )
    cabecera = construir_cabecera(
        nombre_original, reporte["categorias_activas"], False,
        quitar_relleno, curvas, configurar_extrusion,
    )
    contenido = cabecera + "\n" + corregido
    if not texto.endswith(("\n", "\r")):
        contenido = contenido.rstrip("\n") + "\n"
    return contenido, reporte


def corregir_archivo(entrada, salida=None, invertir_e=False, quitar_relleno=False,
                     curvas=False, configurar_extrusion=False,
                     tolerancia_arc=0.1, min_seg_arc=3):
    """Corrige un archivo .gcode en disco (CLI)."""
    entrada = Path(entrada)
    if not entrada.exists():
        raise FileNotFoundError("Archivo no encontrado: %s" % entrada)

    if salida is None:
        salida = entrada.parent / ("%s_corregido%s" % (entrada.stem, entrada.suffix))

    datos = entrada.read_bytes()
    texto = decodificar_contenido(datos)
    contenido, reporte = construir_correccion(
        texto, entrada.name, list(ELIMINAR.keys()), invertir_e, quitar_relleno,
        curvas, configurar_extrusion, tolerancia_arc, min_seg_arc,
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
    if reporte.get("relleno_removido"):
        print("  Relleno quitado:       %d bloques / %d lineas"
              % (reporte["bloques_relleno"], reporte["relleno_removido"]))
    if reporte.get("arcos_procesados"):
        print("  Arcos G2/G3:           %d (curvas en plano XY)" % reporte["arcos_procesados"])
    if reporte.get("arcos_soldados"):
        print("  Arcos soldados:       %d (G1 -> G2/G3, %d lineas ahorradas)"
              % (reporte["arcos_soldados"], reporte["lineas_ahorradas"]))
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
    FLAGS = ("--invertir-e", "--quitar-relleno", "--curvas", "--extrusion")
    if len(sys.argv) < 2:
        print("Uso: python corregir_gcode.py <archivo_entrada> [archivo_salida] [FLAGS]")
        print()
        print("FLAGS:")
        print("  --invertir-e       Extrusion a relativa (M83) con E negativo")
        print("  --quitar-relleno   Borra bloques ;TYPE:FILL/INFILL (infill)")
        print("  --curvas           Fusiona tramos G1 poligonales en arcos G2/G3")
        print("                     (arc welding) e inyecta G17. Opcional:")
        print("                     --tol-arc=NUM desviacion maxima en mm (default 0.1)")
        print("  --extrusion        Inyecta M200 S0/M220 S100/M221 S100 y conserva M220/M221")
        print()
        print("Ejemplos:")
        print("  python corregir_gcode.py PI3MK2_Fijador.gcode --curvas --invertir-e")
        print("  python corregir_gcode.py entrada.gcode --curvas --tol-arc=0.05")
        print("  python corregir_gcode.py entrada.gcode --extrusion --quitar-relleno")
        return 1

    invertir_e = "--invertir-e" in sys.argv
    quitar_relleno = "--quitar-relleno" in sys.argv
    curvas = "--curvas" in sys.argv
    configurar_extrusion = "--extrusion" in sys.argv

    tolerancia_arc = 0.1
    for a in sys.argv:
        if a.startswith("--tol-arc="):
            try:
                tolerancia_arc = float(a.split("=", 1)[1])
            except ValueError:
                pass

    args = [a for a in sys.argv[1:] if a not in FLAGS and not a.startswith("--tol-arc=")]

    entrada, salida, reporte = corregir_archivo(
        args[0], args[1] if len(args) > 1 else None, invertir_e, quitar_relleno,
        curvas, configurar_extrusion, tolerancia_arc,
    )
    _print_reporte(entrada, salida, reporte)
    return 0


if __name__ == "__main__":
    sys.exit(main())