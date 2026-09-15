"""Union de rectas colineales (F1): colapsa la polilinea de Cura a un solo G1.

Cura corta cada recta en cientos de G1 diminutos (con ruido de 3 decimales).
F1 identifica cuando los puntos consecutivos estan sobre UNA MISMA RECTA (la
union de dos puntos) y los colapsa en un solo G1, ANTES de la deteccion de
curvas (F2/F3).

Criterio de recta (el filtro propio de F1):
  - TODOS los puntos intermedios de la ventana caen sobre la recta que une sus
    extremos con desviacion perpendicular <= 'tolerancia' (mm) y proyeccion
    dentro del segmento (para no unir retrocesos);
  - el giro acumulado de la direccion de movimiento en la ventana es ~0
    (<= MAX_GIRO_COLINEAL). Una curva real gira continuamente y por mas corta
    que sea su ventana NO pasa esta prueba, asi F1 nunca "se come" una curva:
    las curvas quedan intactas para que F3 las convierta en G2/G3.
"""

import logging
import math
import re

from .curvas import _extr_xyz_ef, _fmt
from .patrones import _REG_G1_XY

logger = logging.getLogger(__name__)

TOLERANCIA_RECTA_DEFECTO = 0.05
MIN_PUNTOS_RECTA = 3
# Giro acumulado (rad) permitido en una ventana colineal. Una recta (pared de
# Cura) suma ~0; una curva real de radio 200 gira >0.7 grados por paso de 0.5 mm,
# por lo que cualquier ventana de 3+ puntos supera este limite y no se colapsa.
MAX_GIRO_COLINEAL = math.radians(0.6)
# Longitud minima (mm) que debe recorrer la ventana para considerarse recta.
# Dos puntos casi no giran nunca (aunque esten en una curva); con 2 mm de
# recorrido una curva real ya acumulo mas de MAX_GIRO_COLINEAL y no califica.
MIN_LARGO_RECTA = 2.0


def _desviacion_recta(px, py, x1, y1, x2, y2, tolerancia):
    """True si (px, py) esta sobre la recta (x1,y1)-(x2,y2) con desviacion
    perpendicular <= 'tolerancia' Y su proyeccion cae dentro del segmento.
    """
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return True                      # punto duplicado: no aporta desvio
    t = ((px - x1) * dx + (py - y1) * dy) / l2
    if t < 0.0 or t > 1.0:
        return False                     # retroceso: no una esos dos tramos
    dist = abs(dy * px - dx * py + (x2 * y1 - x1 * y2)) / math.sqrt(l2)
    return dist <= tolerancia


def _tramo_colineal(run, tolerancia):
    """True si TODOS los puntos del run caen sobre la recta que une el primero
    y el ultimo dentro de 'tolerancia' (mm), con proyeccion dentro del
    segmento y Z constante.

    Se exige el tramo COMPLETO (no prefijos de pocos puntos): una curva real
    con resolucion fina de Cura es localmente casi recta en 2-3 pasos, y
    tomar prefijos la "comeria" de a bocados y arruinaria el detection de
    arcos (F2/F3) posterior.
    """
    n = len(run)
    if n < MIN_PUNTOS_RECTA:
        return False
    x1, y1 = run[0][0]["X"], run[0][0]["Y"]
    x2, y2 = run[-1][0]["X"], run[-1][0]["Y"]
    z0 = run[0][0].get("Z")
    for j in range(1, n - 1):
        pj = run[j][0]
        if not _desviacion_recta(pj["X"], pj["Y"], x1, y1, x2, y2, tolerancia):
            return False
        zj = pj.get("Z")
        if z0 is None:
            if zj is not None:
                return False
        elif zj is None or abs(zj - z0) > 1e-9:
            return False
    ultimo_z = run[-1][0].get("Z")
    if z0 is None and ultimo_z is not None:
        return False
    if z0 is not None and (ultimo_z is None or abs(ultimo_z - z0) > 1e-9):
        return False
    return True


def _giro_neto(run, a, b):
    """Giro acumulado (rad) de la direccion de movimiento dentro de la ventana
    [a, b]. Para una recta es ~0; para una curva crece con cada segmento.
    """
    dx1 = run[a + 1][0]["X"] - run[a][0]["X"]
    dy1 = run[a + 1][0]["Y"] - run[a][0]["Y"]
    if dx1 == 0 and dy1 == 0:
        return 0.0
    dx2 = run[b][0]["X"] - run[b - 1][0]["X"]
    dy2 = run[b][0]["Y"] - run[b - 1][0]["Y"]
    if dx2 == 0 and dy2 == 0:
        return 0.0
    return abs(math.atan2(dy2, dx2) - math.atan2(dy1, dx1))


def _ventana_colineal(run, a, b, tolerancia):
    """True si los puntos run[a..b] forman UNA RECTA: desviacion perpendicular
    de todos los puntos intermedios <= 'tolerancia', proyeccion dentro del
    segmento, Z constante y giro neto de la direccion <= MAX_GIRO_COLINEAL.

    La condicion de giro es la que separa "recta" de "curva": una pared de
    Cura suma ~0 grados, mientras que cualquier curva real (aunque sea muy
    suave) gira lo suficiente como para NO pasar esta prueba.
    """
    n = b - a + 1
    if n < MIN_PUNTOS_RECTA:
        return False
    x1, y1 = run[a][0]["X"], run[a][0]["Y"]
    x2, y2 = run[b][0]["X"], run[b][0]["Y"]
    z0 = run[a][0].get("Z")
    for j in range(a + 1, b):
        pj = run[j][0]
        if not _desviacion_recta(pj["X"], pj["Y"], x1, y1, x2, y2, tolerancia):
            return False
        zj = pj.get("Z")
        if z0 is None:
            if zj is not None:
                return False
        elif zj is None or abs(zj - z0) > 1e-9:
            return False
    ultimo_z = run[b][0].get("Z")
    if z0 is None and ultimo_z is not None:
        return False
    if z0 is not None and (ultimo_z is None or abs(ultimo_z - z0) > 1e-9):
        return False
    if _giro_neto(run, a, b) > MAX_GIRO_COLINEAL:
        return False
    largo = 0.0
    for j in range(a, b):
        x1, y1 = run[j][0]["X"], run[j][0]["Y"]
        x2, y2 = run[j + 1][0]["X"], run[j + 1][0]["Y"]
        largo += math.hypot(x2 - x1, y2 - y1)
        if largo > MIN_LARGO_RECTA:
            break
    if largo < MIN_LARGO_RECTA:
        return False                 # ventana demasiado corta: no califica
    return True


def unir_rectas(lineas, tolerancia=TOLERANCIA_RECTA_DEFECTO,
                modo_e_relativo=False):
    """Colapsa tramos de G1 XY consecutivos y colineales a un unico G1.

    - Solo toca lineas G1 con X e Y consecutivas (polilineas de Cura); cualquier
      otro comando, comentario o cambio de modo corta el tramo.
    - Mientras 'soldar_arcos' fusiona curvas, aqui se unEN tramos casi rectos:
      los extremos se mantienen como G1, no como arco.
    - E se emite como suma de incrementos (modo relativo M83) o como ultimo
      valor absoluto (M82); F del ultimo segmento; Z solo si todo el tramo
      comparte la misma Z.
    Devuelve (nuevas_lineas, {"rectas_unidas": n, "lineas_ahorradas_rectas": m}).
    """
    modo_e = "REL" if modo_e_relativo else "ABS"
    logger.debug("Unir rectas: tolerancia=%.3f modo_e=%s",
                 tolerancia, modo_e)
    salida = []
    unidas = 0
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

        if len(run) == 0:
            # G1 sin X/Y (solo E o Z): no es un tramo de coordenadas
            salida.append(linea)
            i += 1
            continue

        # ---- colapsar rectas por ventanas dentro del run ----
        # Se busca, desde el inicio, la ventana mas larga [a..b] que formen
        # UNA RECTA (criterio F1: desviacion + giro ~0). Si existe, se emite un
        # solo G1 X Y (la union de dos puntos); si el siguiente punto ya gira,
        # se corta ahi y la cola queda intacta (no se "come" curvas).
        a = 0
        while a < len(run):
            mejor = a
            b = a + MIN_PUNTOS_RECTA - 1
            while b < len(run):
                if not _ventana_colineal(run, a, b, tolerancia):
                    break
                mejor = b
                b += 1

            if mejor - a + 1 >= MIN_PUNTOS_RECTA:
                fin = run[mejor][0]
                partes = ["G1", "X" + _fmt(fin["X"]), "Y" + _fmt(fin["Y"])]
                z0 = run[a][0].get("Z")
                if z0 is not None:
                    partes.append("Z" + _fmt(z0))

                valores_e = [p[1] for p in run[a:mejor + 1] if p[1] is not None]
                if valores_e:
                    e_tot = sum(valores_e) if modo_e == "REL" else valores_e[-1]
                    partes.append("E" + _fmt(e_tot))
                frun = run[mejor][2]
                if frun is not None:
                    partes.append("F" + _fmt(frun, 3))

                logger.debug("Se unen %d segmentos -> G1 %s, %d lineas ahorradas",
                             mejor - a, " ".join(partes[1:]), mejor - a)
                salida.append(" ".join(partes))
                unidas += 1
                ahorro += mejor - a
                a = mejor + 1
            else:
                # No hay ventana colineal que empiece aqui: avanzar un punto
                # de a la vez para no perder la cola (curva/zigzag) intacta.
                j_real = i + a
                salida.append(lineas[j_real])
                a += 1

        i += len(run)

    logger.debug("Resumen unir rectas: %d rectas unidas, %d lineas ahorradas",
                 unidas, ahorro)
    return salida, {"rectas_unidas": unidas, "lineas_ahorradas_rectas": ahorro}