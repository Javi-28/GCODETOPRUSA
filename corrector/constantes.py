"""Categorias de comandos a eliminar y las razones de cada uno."""

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


def clasificar_eliminables(categorias, conservar_extrusion=False):
    """Arma el conjunto de comandos a eliminar a partir de las categorias.

    Devuelve (a_eliminar: set, razones: dict). Con 'conservar_extrusion'
    (opcion "Configurar extrusion") no se eliminan M220/M221 porque se
    reinyectan al inicio con valores seguros.
    """
    a_eliminar = set()
    razones = {}
    for cat in categorias:
        for cmd in ELIMINAR.get(cat, []):
            if conservar_extrusion and cmd in ("M220", "M221"):
                continue
            a_eliminar.add(cmd)
            razones[cmd] = RAZONES.get(cmd, "desconocido")
    return a_eliminar, razones