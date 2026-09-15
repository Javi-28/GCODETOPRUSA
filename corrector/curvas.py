"""Arc welding: fusiona tramos de G1 poligonales de Cura en arcos G2/G3.

La impresora de cemento tiene ARC_SUPPORT activo en Marlin; el archivo de
referencia "hace bien curvas" confirma que G2/G3 (incluidos helicoidales
con Z) funcionan y dan un codigo mas acotado y un giro mas suave.
"""

import logging
import math
import re

from .patrones import _REG_E, _REG_F, _REG_G1_XY, _REG_XYZ, _REG_R

logger = logging.getLogger(__name__)

# Limites para que el arc welding NO sea "demasiado sensible": solo se suelda
# una curva real, no rectas con ruido, esquinas cuadradas ni micro-arcos.
#   radio_minimo : un radio tiny (ej. <0.2 mm) significa esquina/duplicado con
#                  ruido (Cura emite hairpins de R~0.005 cuando casi repite puntos).
#   radio_maximo : un radio gigante (ej. >200 mm) significa tramo casi recto
#                  (cuadrados, paredes planas, escombros de coordenadas).
#   barrido_minimo: giro acumulado minimo del arco (rad). Micro-jogges o
#                  desviaciones de 0.001 mm NO deben convertirse en G2/G3.
RADIO_MAXIMO_DEFECTO = 200.0
RADIO_MINIMO_DEFECTO = 0.2
BARRIDO_MINIMO_DEFECTO = math.radians(15.0)

# Un arco casi-semicircular (barrido ~180°) es AMBIGUO para el firmware:
# el centro reconstruido desde R puede caer del lado contrario y el cabezal
# gira al reves ("tira los motores para atras"). No se sueldan arcos con
# barrido mayor a este limite (180° - 5°).
BARRIDO_MAXIMO_DEFECTO = math.pi - math.radians(5.0)

# F2 - Densidad de curva: un tramo solo es candidato a arco si hay una ventana
# deslizante con 'MIN_SEG_DENSIDAD' movimientos consecutivos recorriendo a lo
# sumo 'DISTANCIA_DENSIDAD_DEFECTO' mm. Las curvas de Cura (resolucion fina)
# generan decenas de pasos en 2 mm; una pared o un poligono ralo no lo hace.
DISTANCIA_DENSIDAD_DEFECTO = 2.0
MIN_SEG_DENSIDAD = 3


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


def _ajuste_arco(puntos, tolerancia, radio_maximo=RADIO_MAXIMO_DEFECTO,
                 barrido_minimo=BARRIDO_MINIMO_DEFECTO,
                 radio_minimo=RADIO_MINIMO_DEFECTO):
    """Si TODOS los puntos caen en un circulo dentro de tolerancia y ademas
    el arco es una curva real (radio acotado y giro suficiente), devuelve
    (cx, cy, r, delta_total). delta_total>0 -> G3 (anti-horario), <0 -> G2.
    Devuelve None si son colineales, casi rectos o ruido (demasiado sensible).
    """
    return _ajuste_arco_det(puntos, tolerancia, radio_maximo,
                            barrido_minimo, radio_minimo)[0]


def _ajuste_arco_det(puntos, tolerancia, radio_maximo, barrido_minimo,
                     radio_minimo=RADIO_MINIMO_DEFECTO):
    """Igual que _ajuste_arco pero devuelve (resultado, razon_rechazo).

    'razon_rechazo' es None si encaja, o una cadena legible explicando por
    que NO se suelda (para los logs DEBUG).
    """
    n = len(puntos)
    if n < 3:
        return None, "menos de 3 puntos"
    c = _circuncentro(puntos[0], puntos[n // 2], puntos[-1])
    if c is None:
        return None, "colineales (recta exacta)"
    cx, cy = c
    r = math.hypot(puntos[0][0] - cx, puntos[0][1] - cy)
    if r > radio_maximo:                       # casi recto: no es una curva
        return None, "radio %.1f > limite %.1f (tramo casi recto)" % (
            r, radio_maximo)
    if r < radio_minimo:                       # micro-arco: esquina con ruido
        return None, "radio %.3f < minimo %.3f (micro-arco por ruido)" % (
            r, radio_minimo)
    for px, py in puntos:
        if abs(math.hypot(px - cx, py - cy) - r) > tolerancia:
            return None, ("punto (%.3f, %.3f) se desvia mas de %.3f mm"
                          % (px, py, tolerancia))
    # Los VERTICES ya estan sobre el circulo; ademas cada segmento recto
    # debe desviarse del arco menos que 'tolerancia' (flecha/sagitta).
    # Sin esto, una esquina cuadrada larga "cabe" en el circulo por sus 3
    # puntos y se sueldaria recortando la esquina varios milimetros.
    for i in range(n - 1):
        x1, y1 = puntos[i]
        x2, y2 = puntos[i + 1]
        dm = math.hypot((x1 + x2) / 2 - cx, (y1 + y2) / 2 - cy)
        sag = r - dm
        if sag > tolerancia:
            return None, ("segmento %d corta la esquina %.3f mm"
                          % (i, sag))
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
    if abs(total) < barrido_minimo:            # recta/retroceso: no es un arco
        return None, ("barrido %.1f grados < minimo %.1f (recta con ruido)"
                      % (math.degrees(abs(total)),
                         math.degrees(barrido_minimo)))
    if abs(total) > BARRIDO_MAXIMO_DEFECTO:
        return None, ("barrido %.1f grados casi-semicirculo (R ambiguo: "
                      "el firmware puede girar al reves)"
                      % math.degrees(abs(total)))
    if abs(total) > 2.0 * math.pi:            # mas de una vuelta: ruido/precision
        return None, ("giro %.0f grados > 360 (puntos repetidos o ruido)"
                      % math.degrees(abs(total)))
    return (cx, cy, r, total), None


def _hay_densidad(puntos, distancia=DISTANCIA_DENSIDAD_DEFECTO,
                  min_seg=MIN_SEG_DENSIDAD):
    """True si existe una ventana deslizante con 'min_seg' movimientos
    consecutivos que recorren a lo sumo 'distancia' mm (F2: probable curva).

    Las curvas reales de Cura son densas (muchos G1 cortos en pocos mm); las
    paredes unidas ya no llegan aqui y un poligono ralo (tramos largos) no
    tiene 3+ movimientos dentro de la ventana.
    """
    if len(puntos) < min_seg + 1:
        return False
    for i in range(len(puntos) - min_seg):
        largo = 0.0
        for j in range(i, i + min_seg):
            x1, y1 = puntos[j]
            x2, y2 = puntos[j + 1]
            largo += math.hypot(x2 - x1, y2 - y1)
            if largo > distancia:
                break
        if largo <= distancia:
            return True
    return False


def soldar_arcos(lineas, tolerancia=0.1, min_seg=3, modo_e_relativo=False,
                 radio_maximo=RADIO_MAXIMO_DEFECTO,
                 barrido_minimo=BARRIDO_MINIMO_DEFECTO,
                 radio_minimo=RADIO_MINIMO_DEFECTO,
                 densidad_distancia=DISTANCIA_DENSIDAD_DEFECTO):
    """Reemplaza tramos de G1 XY consecutivos por un unico G2/G3 R cuando
    encajan en un circulo dentro de 'tolerancia' (mm) Y son curvas reales.

    - Solo toca lineas G1 con X e Y estrictamente consecutivas (como emite
      Cura para cada curva). Cualquier otro comando, comentario o cambio de
      modo corta el tramo.
    - Los tramos que no encajen en un radio quedan como G1 (nunca se tocan).
    - Evita ser "demasiado sensible": un tramo casi recto (radio > 'radio_maximo'
      o giro acumulado < 'barrido_minimo') NO se convierte en arco. Asi los
      cuadrados, paredes planas y rectas con ruido quedan intactas.
    - 'modo_e_relativo' fuerza modo relativo (M83): cuando viene de
      invertir_e todos los E ya son incrementos, aunque el archivo no tenga
      un M83 propio. Si es False se detecta M82/M83 linea a linea.
    - E se emite como suma de incrementos (modo relativo M83) o como valor
      absoluto final (M82), segun el modo vigente.
    Devuelve (nuevas_lineas, {"arcos_soldados": int, "lineas_ahorradas": int}).
    """
    min_puntos = min_seg + 1
    modo_e = "REL" if modo_e_relativo else "ABS"
    if radio_maximo is None:
        radio_maximo = RADIO_MAXIMO_DEFECTO
    if radio_minimo is None:
        radio_minimo = RADIO_MINIMO_DEFECTO
    if barrido_minimo is None:
        barrido_minimo = BARRIDO_MINIMO_DEFECTO
    logger.debug("Soldar arcos: tolerancia=%.3f min_seg=%d modo_e=%s "
                 "radio_minimo=%.3f radio_maximo=%.1f barrido_minimo=%.1f "
                 "grados densidad=%d mov en %.1f mm",
                 tolerancia, min_seg, modo_e, radio_minimo, radio_maximo,
                 math.degrees(barrido_minimo), MIN_SEG_DENSIDAD,
                 densidad_distancia)
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

        # F2: si no hay ventana de 3+ movimientos en <= 'densidad_distancia' mm,
        # es un poligono o pared rala, no una curva.
        pts_run = [(p[0]["X"], p[0]["Y"]) for p in run]
        if not _hay_densidad(pts_run, densidad_distancia):
            p0 = run[0][0]
            pend = run[-1][0]
            logger.debug("Tramo de %d segmentos (%.2f %.2f -> %.2f %.2f) "
                         "NO se suelda: no hay ventana de %d movimientos en "
                         "%.1f mm (poligono ralo)",
                         len(run), p0.get("X", 0), p0.get("Y", 0),
                         pend.get("X", 0), pend.get("Y", 0),
                         MIN_SEG_DENSIDAD, densidad_distancia)
            salida.append(linea)
            i += 1
            continue

        # ---- buscar el prefix mas largo que encaje en un arco ----
        mejor = None
        razon = None
        for k in range(min_puntos, len(run) + 1):
            pts = [(p[0]["X"], p[0]["Y"]) for p in run[:k]]
            aj, razon = _ajuste_arco_det(pts, tolerancia, radio_maximo,
                                         barrido_minimo, radio_minimo)
            if aj is not None:
                mejor = (k, aj)

        if mejor is None:
            p0 = run[0][0]
            pend = run[-1][0]
            logger.debug("Tramo de %d segmentos (%.2f %.2f -> %.2f %.2f) "
                         "NO se suelda: %s",
                         len(run), p0.get("X", 0), p0.get("Y", 0),
                         pend.get("X", 0), pend.get("Y", 0), razon)
            salida.append(linea)
            i += 1
            continue

        consumidos, (cx, cy, r, delta_total) = mejor
        fin = run[consumidos - 1][0]
        frun = run[consumidos - 1][2]

        sentido = "G3" if delta_total > 0 else "G2"
        logger.debug("Se suelda tramo de %d segmentos -> %s R=%.3f "
                     "barrido=%.1f grados, %d lineas ahorradas",
                     consumidos, sentido, r, math.degrees(abs(delta_total)),
                     consumidos - 1)
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

    logger.debug("Resumen arc welding: %d arcos soldados, %d lineas ahorradas",
                 soldados, ahorro)
    return salida, {"arcos_soldados": soldados, "lineas_ahorradas": ahorro}


def desarmar_arcos(lineas, paso=0.5, modo_e_relativo=False):
    """Convierte G2/G3 del plano XY a G1 subdivididos de ~'paso' mm.

    Para firmwares SIN ARC_SUPPORT (los G2/G3 generan error, detienen la
    maquina o la hacen girar en sentido contrario). Convierte CADA arco en
    G1 finos que cualquier controlador entiende, repartiendo E y Z
    (helices) a lo largo de los segmentos.

    - Solo se convierten G2/G3 del plano XY con X, Y y R; cualquier arco
      sin esos parametros se deja igual (pasa tal cual).
    - Con 'modo_e_relativo' True (M83) el E del arco es un incremento unico
      que se reparte en proporcion a la longitud de cada segmento. Con
      False (M82) el E es cota absoluta y se interpola linealmente desde la
      posicion anterior hasta el destino.
    - Se hace seguimiento de posicion (G0/G1), de M82/M83 y de G92 para
      mantener la continuidad.
    Devuelve (nuevas_lineas, {"arcos_desarmados": int, "segmentos": int}).
    """
    salida = []
    desarmados = 0
    segmentos = 0
    pos = {"X": 0.0, "Y": 0.0, "Z": None, "E": None}
    modo_e = "REL" if modo_e_relativo else "ABS"

    for linea in lineas:
        ojos = linea.split(";", 1)[0].strip().lstrip("\ufeff")
        m = re.match(r"^G([0-3])\b", ojos, re.I)
        if m:
            codigo = int(m.group(1))
            if codigo == 2 or codigo == 3:
                xyz, e, f = _extr_xyz_ef(linea)
                mr = _REG_R.search(ojos)
                if (xyz.get("X") is None or xyz.get("Y") is None or mr is None):
                    salida.append(linea)
                    continue
                sx, sy = pos["X"], pos["Y"]
                tx, ty = xyz["X"], xyz["Y"]
                R = abs(float(mr.group(1).replace(" ", "")))
                chord = math.hypot(tx - sx, ty - sy)
                if chord < 1e-9 or chord > 2.0 * R:
                    salida.append(linea)
                    continue
                cw = (codigo == 2)                     # G2 horario, G3 anti
                mx, my = (sx + tx) / 2.0, (sy + ty) / 2.0
                px, py = -(ty - sy) / chord, (tx - sx) / chord
                h = math.sqrt(max(R * R - (chord / 2.0) ** 2, 0.0))
                centros = [(mx + px * h, my + py * h),
                           (mx - px * h, my - py * h)]
                centro, ang0, sweep = None, 0.0, None
                for cx, cy in centros:
                    a0 = math.atan2(sy - cy, sx - cx)
                    a1 = math.atan2(ty - cy, tx - cx)
                    d = (a1 - a0) % (2.0 * math.pi)
                    if cw:
                        s = 2.0 * math.pi - d            # horario: girar al reves
                        if s < 1e-12:
                            s = 2.0 * math.pi
                    else:
                        s = d if d > 1e-12 else 2.0 * math.pi
                    if sweep is None or s < sweep:
                        centro, ang0, sweep = (cx, cy), a0, s
                if centro is None or sweep >= 2.0 * math.pi:
                    salida.append(linea)
                    continue
                signo = -1.0 if cw else 1.0
                nseg = max(int(math.ceil(sweep * R / max(paso, 1e-9))), 1)
                e_ini = None
                if e is not None and modo_e == "ABS":
                    e_ini = pos.get("E")
                    if e_ini is None:
                        e_ini = 0.0
                for i in range(1, nseg + 1):
                    ang = ang0 + signo * sweep * i / nseg
                    px_, py_ = centro[0] + R * math.cos(ang), \
                        centro[1] + R * math.sin(ang)
                    p = ["G1", "X" + _fmt(px_), "Y" + _fmt(py_)]
                    if xyz.get("Z") is not None:
                        z0 = pos.get("Z")
                        if z0 is None:
                            z0 = xyz["Z"]
                        p.append("Z" + _fmt(z0 + (xyz["Z"] - z0) * i / nseg))
                    if e is not None:
                        if modo_e == "REL":
                            por_seg = e / nseg
                            e_seg = e - por_seg * (nseg - 1) if i == nseg \
                                else por_seg
                        else:
                            e_seg = e_ini + (e - e_ini) * i / nseg
                        p.append("E" + _fmt(e_seg))
                    if f is not None and i == 1:
                        p.append("F" + _fmt(f, 3))
                    salida.append(" ".join(p))
                segmentos += nseg
                desarmados += 1
                if modo_e == "ABS" and e is not None:
                    pos["E"] = e
                pos["X"], pos["Y"] = tx, ty
                if xyz.get("Z") is not None:
                    pos["Z"] = xyz["Z"]
                continue
            if codigo in (0, 1):
                xyz, e, _f = _extr_xyz_ef(linea)
                for k in ("X", "Y"):
                    if xyz.get(k) is not None:
                        pos[k] = xyz[k]
                if xyz.get("Z") is not None:
                    pos["Z"] = xyz["Z"]
                if e is not None and modo_e == "ABS":
                    pos["E"] = e
                salida.append(linea)
                continue
        ojos_up = ojos.upper()
        if ojos_up.startswith("M82"):
            modo_e = "ABS"
        elif ojos_up.startswith("M83"):
            modo_e = "REL"
        elif re.match(r"^G92\b", ojos, re.I):
            m = _REG_E.search(ojos)
            if m:
                pos["E"] = float(m.group(1).replace(" ", ""))
        salida.append(linea)

    logger.debug("Desarmar arcos: %d G2/G3 convertidos a %d segmentos G1",
                 desarmados, segmentos)
    return salida, {"arcos_desarmados": desarmados, "segmentos": segmentos}