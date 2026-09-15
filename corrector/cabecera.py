"""Cabecera comentada que se antepone al archivo corregido."""


def construir_cabecera(nombre_original, categorias_activas, quedaron_sin_eliminar,
                       quitar_relleno=False, curvas=False, configurar_extrusion=False,
                       unir_rectas=False):
    lineas = []
    lineas.append("; Corregido por Corrector G-Code (impresora de cemento)")
    lineas.append("; Original: %s" % nombre_original)
    if quedaron_sin_eliminar:
        lineas.append("; Aviso: las categorias marcadas incluyen comandos que podrian trabar la maquina.")
    if quitar_relleno:
        lineas.append("; Relleno interior (infill) eliminado: solo se conservan las paredes.")
    if curvas:
        lineas.append("; Curvas activadas: G17 (plano XY) + arcos G2/G3 (arc welding).")
    if unir_rectas:
        lineas.append("; Rectas unidas: lineas colineales de Cura colapsadas a un solo G1.")
    if configurar_extrusion:
        lineas.append("; Extrusion configurada: M200 S0 (sin volumetrico), M221 S100 (flujo 100%).")
    lineas.append(";")
    return "\n".join(lineas)