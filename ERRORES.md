# Errores detectados en la máquina y su diagnóstico

Este documento registra los errores/síntomas que aparecieron al ejecutar en la
impresora de cemento los archivos corregidos, **qué se investigó**, **qué se
descartó con evidencia** y **qué se cambió** para mitigarlos.

> Ver también: `ANALISIS.md` (por qué hay que limpiar el G-code de Cura) y
> `README.md` (detección de curvas F1/F2/F3 e investigación).

---

## 1. Síntoma reportado

Al mandar a imprimir el archivo corregido del logo (`LOGO SVG_corregido.gcode`),
la máquina **"tira los motores full para atrás"** (los motores van a fondo en
sentido inverso). No es un simple comando ignorado: hay movimiento real y
violento en contra.

---

## 2. Qué se descartó (con evidencia del propio repo)

### 2.1 La inversión de E NO es la causa

El archivo nativo que la máquina ya ejecuta bien (`respaldo/PRUEBA IMPRESORA 2.gcode`)
usa exactamente el patrón del corrector:

```gcode
G90
M83
G1 Z5
G1 X150 F1500
G1 X50 F 400 E-30
G1 X100 F400 E-10
...
```

Es decir: `M83` (relativo) + **E negativos**. El corrector hace lo mismo
(convierte absoluto→incremento y cambia el signo, ver `corrector/extrusion.py`),
así que forzar E negativo **no** explica el síntoma. Marlin además no tiene un
comando G-code para invertir el extrusor: eso se hace a nivel firmware
(`INVERT_E0_DIR`), por lo que invertir el signo de E es la vía válida y
coincide con el archivo nativo.

### 2.2 La geometría de los arcos es válida

Se verificaron los 26 arcos `G2/G3` emitidos contra el original: **todos**
cumplen `R > cuerda/2` (barrido máximo ≈ 147°), o sea que no hay
`G2/G3 bad parameters` por radio insuficiente. El fallo, si existe, no viene de
un radio mal calculado.

---

## 3. Causas probables (investigación en foros/fuentes)

### 3.1 Firmware sin `ARC_SUPPORT` (la más probable)

Marlin sólo entiende `G2/G3` si se compiló con `ARC_SUPPORT`
(`Configuration_adv.h`). Si no está:

- Responde `echo:Unknown command` o `Error: G2/G3 bad parameters` y **bota la
  línea**, o en algunos controles **detiene la impresión**.
- Fuentes: <https://marlinfw.org/docs/gcode/G002-G003.html>,
  <https://github.com/MarlinFirmware/Marlin/issues/2519>,
  <https://github.com/FormerLurker/ArcWelderPlugin/issues/93>,
  <https://forum.v1e.com/t/error-g2-g3-bad-parameters/42908>.

En el archivo corregido del logo, el **primer arco aparece en la línea 62**
(apenas 18 líneas después de arrancar), justo al empezar a dibujar. Si el
controlador no soporta arcos, el problema se dispara casi de inmediato.

### 3.2 `G17` inyectado

El corrector inyectaba `G17` (plano XY) al activar curvas. En Marlin sin
`CNC_WORKSPACE_PLANES` eso genera error/rechazo (aunque XY ya es el plano por
defecto). Se dejó de inyectar.

### 3.3 Arcos casi-semicirculares (R ambiguo)

Un `R` define **dos** arcos posibles; cerca de 180° el firmware puede
reconstruir el centro del lado contrario y **girar al revés**. Los
post-procesadores serios validan esto. Ahora se **rechazan** los arcos con
barrido > 175° (`BARRIDO_MAXIMO_DEFECTO`).

### 3.4 Viajes sin homeo

El corrector elimina `G28/G80` (la máquina no tiene endstops ni sonda). Pero
entonces quedan viajes heredados de Cura sin posición conocida:

- inicio `G1 Y-3.0 F1000.0` ("go outside print area"), y
- final `G1 X0 Y210 F2100 ; home X axis and push Y forward`.

Sin homeo, esos movimientos pueden llevar el eje **a fondo contra el tope**.
Conviene revisarlos según los límites reales de la máquina (pendiente).

### 3.5 Escala de E del archivo original (a revisar en la máquina)

En el original (M82 absoluto) la capa 1 arranca en `E770.43` y un tramo de 7 mm
salta a `E924.17`, o sea un incremento real de **~154 mm de E en un solo
movimiento**. El inversor lo replica fiel (E `-153.745`), no es un bug
introducido. Pero si la calibración de E de la máquina está hecha para el
archivo manual (`E-10` por movimiento), el tornillo va a girar **muchísimo más**
en el archivo de Cura. Hay que confirmar que los pasos/mm de E coinciden con la
escala del archivo de Cura, no con la del manual.

---

## 4. Bugs internos encontrados durante la verificación

| Bug | Detalle | Corrección |
|---|---|---|
| `desarmar_arcos` no hacía nada | `_REG_XYZ` no capturaba `R`, así que todo arco se descartaba como "sin R" | se agregó `_REG_R` en `corrector/patrones.py` |
| `G17` siempre se inyectaba con curvas | podía fallar en firmware sin `CNC_WORKSPACE_PLANES` | se removió la inyección |
| No había forma de evitar `G2/G3` | si el firmware no soporta arcos, no había salida | nueva opción **solo-G1** (`desarmar_arcos`) |

---

## 5. Cambios implementados

Commit `e1010fd` (rama `master`):

- **`corrector/curvas.py`**
  - `desarmar_arcos()`: convierte cualquier `G2/G3` en `G1` finos (~0.5 mm),
    repartiendo `E` y `Z` (hélices). Para firmware sin `ARC_SUPPORT`.
  - Guard anti-casi-semicírculo (`BARRIDO_MAXIMO_DEFECTO = 180° - 5°`).
- **`corrector/procesador.py`**: se quita la inyección de `G17`; nueva opción
  `desarmar` / `paso_arc` + campos en el reporte.
- **`corrector/patrones.py`**: `_REG_R`.
- **`corrector/cli.py`**: flags `--solo-g1` y `--paso-arc=NUM`.
- **`corregir_ui.py`**: checkbox *"Convertir curvas a movimientos G1"*.
- **`corrector/cabecera.py`**: textos actualizados (sin `G17`).

### Cómo probarlo

```bash
# Prueba A/B: sin curvas (igual que el manual, todo G1)
py corregir_gcode.py "LOGO SVG.gcode" --invertir-e --unir-rectas

# Curvas suaves pero 100% G1 (firmware sin ARC_SUPPORT)
py corregir_gcode.py "LOGO SVG.gcode" --curvas --solo-g1 --invertir-e --unir-rectas

# Curvas como G2/G3 (firmware CON ARC_SUPPORT)
py corregir_gcode.py "LOGO SVG.gcode" --curvas --invertir-e --unir-rectas
```

En la GUI: marcar/desmarcar **Curvas (G2/G3)** y **Convertir curvas a movimientos G1**.

---

## 6. Verificación realizada

Sobre `LOGO SVG.gcode`:

| Prueba | Resultado |
|---|---|
| Curvas ON (`--curvas`) | 26 arcos `G2/G3`, **sin `G17`** |
| Solo G1 (`--curvas --solo-g1`) | **0** `G2/G3`, 26 arcos → **880 segmentos `G1`** |
| Sin curvas | 0 `G2/G3`, 1266 líneas (todo lineal) |
| Conservación de E | `-34580.6603` (arcos) vs `-34580.6602` (G1) → **exacta** |

---

## 7. Cómo diagnosticar en la máquina (pendiente de confirmar)

1. **Aislar los arcos**: imprimir la variante **sin curvas** (prueba A/B). Si el
   problema desaparece, la causa son los `G2/G3`/firmware.
2. **Confirmar soporte de arcos**: mandar `M115` (mirar `EXTENDED_CAPABILITIES`)
   o enviar un `G2 X1 Y1 R5` de prueba y ver si responde `ok` o
   `Unknown command` / `bad parameters`.
3. **Ver el mensaje exacto** de la consola en el momento del fallo
   (`Unknown command`, `G2/G3 bad parameters`, `KILLED`, etc.).
4. **Contar qué motor** va para atrás (extrusor `E`, mesa `Y`, cabezal `X`, `Z`)
   y **cuándo** (inicio, primer arco ~L62, mitad, o final `X0 Y210`).
