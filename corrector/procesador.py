"""Orquestacion del pipeline de correccion (procesar_texto_gcode)."""

import logging

from . import cabecera as cabecera_mod
from .constantes import ELIMINAR, clasificar_eliminables
from .extrusion import InversorE
from .lineas import es_tipo_relleno, extraer_comando
from .relleno import consumir_bloque_relleno
from .curvas import soldar_arcos, desarmar_arcos
from .rectas import unir_rectas as _unir_rectas

logger = logging.getLogger(__name__)


def procesar_texto_gcode(texto, categorias=None, invertir_e=False, quitar_relleno=False,
                         curvas=False, configurar_extrusion=False,
                         tolerancia_arc=0.1, min_seg_arc=3,
                         radio_maximo_arc=None, barrido_minimo_arc=None,
                         unir_rectas=False, tolerancia_recta=0.05,
                         desarmar=False, paso_arc=0.5):
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
        G2/G3 (arc welding). Solo se convierten curvas reales: los tramos
        casi rectos (cuadrados/rectas con ruido) se descartan si no tienen
        un giro minimo o su radio es gigante. No se sueldan arcos casi
        semicirculares (barrido ~180°: el firmware puede revertir el giro).
        'tolerancia_arc' es la desviacion maxima (mm) aceptada entre la
        curva original y el arco (default 0.1). 'min_seg_arc' es la cantidad
        minima de segmentos G1 fusionados por arco (default 3).
    desarmar: si True convierte TODO G2/G3 (los generados por 'curvas' y los
        preexistentes del archivo) a G1 subdivididos (paso ~0.5 mm). Util
        para firmwares SIN ARC_SUPPORT donde los arcos generan error o hacen
        girar los motores al reves. Compatible con 'curvas' True (soldar y
        luego desarmar = curvas suaves en G1 puro) o solo con invertir_e.
        'paso_arc' es el paso aproximado en mm de los segmentos (default 0.5).
    configurar_extrusion: si True inyecta M200 S0 (desactivar volumetrico),
        M220 S100 (velocidad al 100%) y M221 S100 (flujo al 100%) al
        inicio, y NO elimina los comandos M220/M221 del archivo original.
    unir_rectas: si True colapsa los tramos de G1 XY consecutivos y
        colineales (paredes subdivididas por Cura) a un unico G1, ANTES del
        arc welding. Es independiente de 'curvas': puede usarse solo o junto.
        'tolerancia_recta' es la desviacion perpendicular maxima (mm) de los
        puntos intermedios respecto a la recta que une extremos (default 0.05).

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
        "rectas_unidas": int (tramos G1 colineales colapsados a un solo G1),
        "lineas_ahorradas_rectas": int (lineas G1 reemplazadas por las rectas),
    }
    """
    if categorias is None:
        categorias = list(ELIMINAR.keys())

    a_eliminar, razones = clasificar_eliminables(categorias, configurar_extrusion)
    logger.info("Procesando %d lineas: categorias=%s invertir_e=%s "
                "quitar_relleno=%s curvas=%s extrusion=%s unir_rectas=%s",
                len(texto.splitlines()), len(categorias), invertir_e,
                quitar_relleno, curvas, configurar_extrusion, unir_rectas)

    lineas = texto.splitlines()
    salida = []
    eliminadas = []
    total = len(lineas)
    escritas = 0
    por_comando = {}
    lineas_relleno = 0
    bloques_relleno = 0

    inversor = InversorE() if invertir_e else None

    i = 0
    while i < total:
        num = i + 1
        linea = lineas[i]
        ojos = linea.split(";", 1)[0].strip()

        # ---- Quitar bloque de relleno interior (infill) ----
        if quitar_relleno and es_tipo_relleno(linea):
            j, ultimo_e_bloque = consumir_bloque_relleno(lineas, i, total)
            quitaste = j - i
            lineas_relleno += quitaste
            if quitaste:
                bloques_relleno += 1
            logger.debug("Relleno en linea %d: %d lineas quitadas",
                         num, quitaste)
            if ultimo_e_bloque is not None:
                comando_sig = extraer_comando(lineas[j]) if j < total else None
                if comando_sig != "G92":
                    resync = ("G92 E%g ; relleno interior quitado, "
                              "extrusor resincronizado" % ultimo_e_bloque)
                    lineas.insert(j, resync)
                    total += 1
            i = j
            continue

        # ---- Eliminacion de comandos irrelevantes ----
        comando = extraer_comando(linea)
        if comando in a_eliminar:
            eliminadas.append({
                "linea": num,
                "texto": linea.strip(),
                "comando": comando,
                "razon": razones[comando],
            })
            por_comando[comando] = por_comando.get(comando, 0) + 1
            logger.debug("Linea %d: ELIMINADA %s (%s)", num, comando,
                         razones[comando])
            i += 1
            continue

        # ---- Inversion de E (si corresponde) ----
        if inversor is not None:
            linea = inversor.procesar(linea)

        salida.append(linea)
        escritas += 1
        i += 1

    # ---- Unir rectas (F1): colapsar paredes subdivididas antes de curvas ----
    rectas_unidas = 0
    lineas_ahorradas_rectas = 0
    if unir_rectas:
        salida, info_rectas = _unir_rectas(
            salida, tolerancia_recta, modo_e_relativo=bool(inversor),
        )
        rectas_unidas = info_rectas["rectas_unidas"]
        lineas_ahorradas_rectas = info_rectas["lineas_ahorradas_rectas"]

    # ---- Arc welding (curvas): fusionar tramos G1 poligonales en G2/G3 ----
    arcos_soldados = 0
    lineas_ahorradas = 0
    if curvas:
        salida, info_weld = soldar_arcos(
            salida, tolerancia_arc, min_seg_arc,
            modo_e_relativo=bool(inversor),
            radio_maximo=radio_maximo_arc,
            barrido_minimo=barrido_minimo_arc,
        )
        arcos_soldados = info_weld["arcos_soldados"]
        lineas_ahorradas = info_weld["lineas_ahorradas"]

    # ---- Desarmar arcos: G2/G3 a G1 (firmwares sin ARC_SUPPORT) ----
    arcos_desarmados = 0
    segmentos_g1 = 0
    if desarmar:
        salida, info_des = desarmar_arcos(
            salida, paso_arc, modo_e_relativo=bool(inversor),
        )
        arcos_desarmados = info_des["arcos_desarmados"]
        segmentos_g1 = info_des["segmentos"]

    corregido = "\n".join(salida)
    prefijo = []
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

    e_invertidos = inversor.invertidos if inversor else 0
    arcos_procesados = inversor.arcos if inversor else 0

    logger.info("Resultado: %d eliminadas / relleno %d bloques-%d lineas / "
                "E invertido %d / rectas unidas %d (%d ahorradas) / "
                "arcos soldados %d (%d ahorradas) / desarmados %d (%d G1)",
                len(eliminadas), bloques_relleno, lineas_relleno,
                e_invertidos, rectas_unidas, lineas_ahorradas_rectas,
                arcos_soldados, lineas_ahorradas,
                arcos_desarmados, segmentos_g1)

    reporte = {
        "total_lineas": total,
        "lineas_escritas": len(corregido.splitlines()),
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
        "rectas_unidas": rectas_unidas,
        "lineas_ahorradas_rectas": lineas_ahorradas_rectas,
        "arcos_desarmados": arcos_desarmados,
        "segmentos_g1": segmentos_g1,
    }
    return corregido, reporte


def construir_correccion(texto, nombre_original="<desconocido>", categorias=None,
                         invertir_e=False, quitar_relleno=False, curvas=False,
                         configurar_extrusion=False, tolerancia_arc=0.1,
                         min_seg_arc=3, radio_maximo_arc=None,
                         barrido_minimo_arc=None, unir_rectas=False,
                         tolerancia_recta=0.05, desarmar=False, paso_arc=0.5):
    """Devuelve (contenido_final_con_cabecera, reporte)."""
    corregido, reporte = procesar_texto_gcode(
        texto, categorias, invertir_e, quitar_relleno, curvas,
        configurar_extrusion, tolerancia_arc, min_seg_arc,
        radio_maximo_arc, barrido_minimo_arc, unir_rectas, tolerancia_recta,
        desarmar, paso_arc,
    )
    cabecera = cabecera_mod.construir_cabecera(
        nombre_original, reporte["categorias_activas"], False,
        quitar_relleno, curvas, configurar_extrusion, unir_rectas,
        desarmar=desarmar,
    )
    contenido = cabecera + "\n" + corregido
    reporte["lineas_escritas"] = len(contenido.splitlines())
    if not texto.endswith(("\n", "\r")):
        contenido = contenido.rstrip("\n") + "\n"
    return contenido, reporte