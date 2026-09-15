"""Inversion de E: fuerza extrusion relativa con E negativo.

La maquina de cemento extruye con E negativo (tornillo/bobina al reves del
estandar), igual que el archivo manual que funciona. Esto replica ese
patron: usa M83 (relativo) y cambia el signo de cada incremento E.
"""

import re

from .patrones import _REG_E, _REG_M82


class InversorE:
    """Mantiene el estado del extrusor y transforma cada linea conservada.

    Uso: instanciar una vez, e invocar 'procesar(linea)' solo sobre las
    lineas que no fueron eliminadas. La misma linea se devuelve modificada
    cuando corresponde.
    """

    def __init__(self):
        self.modo = "ABS"          # estandar Marlin: M82 absoluto
        self.ultimo_e = 0.0
        self.invertidos = 0        # lineas con E reescrito
        self.arcos = 0             # G2/G3 preexistentes procesados

    def procesar(self, linea):
        """Devuelve la linea con la extrusion invertida si corresponde."""
        ojos = linea.split(";", 1)[0].strip()

        if re.match(r"^M82\b", ojos, re.I):
            self.modo = "ABS"
        elif re.match(r"^M83\b", ojos, re.I):
            self.modo = "REL"
        elif re.match(r"^G92\b", ojos, re.I):
            m = _REG_E.search(ojos)
            if m:
                self.ultimo_e = float(m.group(1).replace(" ", ""))

        if not re.match(r"^[GM]\s*\d+", ojos, re.I):
            return linea

        if re.match(r"^M82\b", ojos, re.I):
            return _REG_M82.sub("M83", linea)   # neutraliza arrancadas a absoluto
        if re.match(r"^M83\b", ojos, re.I):
            return linea
        if re.match(r"^(?:G[0-3])\b", ojos, re.I):
            if re.match(r"^G[23]\b", ojos, re.I):
                self.arcos += 1
            m = _REG_E.search(ojos)
            if m:
                valor = float(m.group(1).replace(" ", ""))
                if self.modo == "ABS":
                    incremento = valor - self.ultimo_e
                    self.ultimo_e = valor
                else:
                    incremento = valor
                nueva = -incremento
                linea = _REG_E.sub(lambda _m: "E%g" % nueva, linea, count=1)
                self.invertidos += 1
            return linea
        if re.match(r"^G92\b", ojos, re.I):
            return linea

        # Otros comandos con E (por ejemplo M221 E, M204 E) actualizan la
        # referencia absoluta del extrusor.
        m = _REG_E.search(ojos)
        if m:
            self.ultimo_e = float(m.group(1).replace(" ", ""))
        return linea