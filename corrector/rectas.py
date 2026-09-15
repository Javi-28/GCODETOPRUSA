"""Union de rectas colineales: colapsa la polilinea de Cura a un solo G1.

Cura corta cada recta en cientos de G1 diminutos (con ruido de 3 decimales).
Esto los convierte en UNA linea G1 cuando todos los puntos intermedios se
desvian <= 'tolerancia' (mm) de la recta que une el primero con el ultimo y su
proyeccion cae dentro del segmento (para no unir retrocesos).
"""

import logging
import math
import re

from .curvas import _extr_xyz_ef, _fmt
from .patrones import _REG_G1_XY

logger = logging.getLogger(__name__)

TOLERANCIA_RECTA_DEFECTO = 0.05
MIN_PUNTOS_RECTA = 3


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

        # ---- buscar si el run ENTRO es colineal ----
        if len(run) == 0:
            # G1 sin X/Y (solo E o Z): no es un tramo de coordenadas
            salida.append(linea)
            i += 1
            continue
        if not _tramo_colineal(run, tolerancia):
            # No re-escanear sufijos: la cola de una curva es localmente
            # colineal y se colapsaria comiendose el arco de a bocados.
            # El arco lo recupera soldar_arcos despues.
            salida.extend(lineas[i:i + len(run)])
            i += len(run)
            continue

        k = len(run)

        fin = run[k - 1][0]
        partes = ["G1", "X" + _fmt(fin["X"]), "Y" + _fmt(fin["Y"])]
        z0 = run[0][0].get("Z")
        if z0 is not None:
            partes.append("Z" + _fmt(z0))

        valores_e = [p[1] for p in run[:k] if p[1] is not None]
        if valores_e:
            e_tot = sum(valores_e) if modo_e == "REL" else valores_e[-1]
            partes.append("E" + _fmt(e_tot))
        frun = run[k - 1][2]
        if frun is not None:
            partes.append("F" + _fmt(frun, 3))

        logger.debug("Se unen %d segmentos -> G1 %s X=%s Y=%s, %d lineas ahorradas",
                     k - 1, " ".join(partes[1:]), _fmt(fin["X"]), _fmt(fin["Y"]),
                     k - 1)
        salida.append(" ".join(partes))
        unidas += 1
        ahorro += k - 1
        i += k

    logger.debug("Resumen unir rectas: %d rectas unidas, %d lineas ahorradas",
                 unidas, ahorro)
    return salida, {"rectas_unidas": unidas, "lineas_ahorradas_rectas": ahorro}