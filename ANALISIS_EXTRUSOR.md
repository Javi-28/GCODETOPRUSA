# Analisis de Hipotesis: Velocidad y Sentido del Extrusor (E)

Fecha: 2026-09-09

## Objetivo

Verificar la hipotesis del usuario sobre por que la impresora de cemento se
traba o no extruye al usar el G-code generado por Cura:

1. "El motor se mueve demasiado lento y dice `no puedo tan lento`."
2. "Estamos usando E positivos cuando necesitamos E negativos."

Para fundamentarlo se descargo el repositorio oficial de configuraciones
Marlin y se compararon los numeros reales de ambos archivos.

---

## Repositorio Marlin de referencia

| Dato | Valor |
|------|-------|
| Repositorio | https://github.com/MarlinFirmware/Configurations |
| Copia local | `Marlin-Configurations/` (branch `master` = `Configurations-import-2.1.x`) |
| Tamano | ~185 MB, 1246 archivos |
| Configuracion usada como referencia | `config/examples/Prusa/MK3/` (Prusa i3, la placa base del proyecto) |

---

## Datos medidos en los archivos

### Archivo manual (el que SI funciona)

```
G90
M83            <- E RELATIVO
G1 Z5
G1 X150 F1500
G1 X50 F400 E-30
G1 X50 Y50 F400
G1 X100 F400 E-10
...
```

- Modo de extrusion: **relativo (M83)**
- Incrementos E: **siempre negativos** (-10, -20, -30 mm)
- Flujo E medido: **-1.33 mm/s** (constante)

### Archivo Cura (el que falla / se traba)

```
M82            <- E ABSOLUTO
G90
M104 S231
M140 S23
M190 S23       <- espera temperatura (traba)
M109 S231      <- espera temperatura (traba)
G28 W          <- homeo sin endstops (traba/colisiona)
G80            <- mesh leveling sin sonda (traba)
...
```

- Modo de extrusion: **absoluto (M82)**
- Incrementos E: **siempre positivos**, creciendo hasta ~13316 mm
- Flujo E medido: **+49.9 mm/s** (mediana; ver tabla)

### Tabla comparativa (flujo del extrusor en mm de E por segundo)

| Archivo | Movs c/E | p50 | minimo | maximo |
|---------|---------:|----:|-------:|-------:|
| Manual (funciona) | 8 | **-1.33** | -1.33 | -1.33 |
| Cura solo limpieza | 106 | **+49.9** | -1859 | +1888 |
| Cura limpieza + E invertido | 106 | **-49.9** | -391.7 | -0.6 |

Los extremos minimo/maximo del Cura son retracciones al inicio de perimetro
(picos), el valor representativo es la mediana (+49.9 en original).

---

## Veredicto por hipotesis

### Hipotesis 1: "el motor no puede ir tan lento" -> REFUTADA

El analisis da el resultado **opuesto**:

- El archivo **manual** (que la maquina ejecuta bien) mueve el extrusor a
  solo **-1.33 mm/s**. Eso es *muy lento* y funciona perfectamente.
- El archivo de **Cura** lo mueve a **+49.9 mm/s**. Es **40 veces mas
  rapido** que el manual.

No hay un piso de velocidad que la maquina rechace en este rango:

- `DEFAULT_MINIMUMFEEDRATE 0.0` (mm/s) en `Configuration_adv.h`
- `DEFAULT_MINTRAVELFEEDRATE 0.0` (mm/s) en `Configuration_adv.h`
- El piso real del planner Marlin (MINIMUM_PLANNER_SPEED) ronda los
  0.05 mm/s, muchisimo mas bajo que 1.33.

Conclusion: la velocidad no es el problema. De hecho, la maquina ya probo
que tolera sin drama velocidades lentas.

### Hipotesis 2: "E positivo vs E negativo" -> CONFIRMADA como causa probable

Los datos muestran la diferencia mas fuerte entre ambos archivos:

| Aspecto | Manual (funciona) | Cura (falla) |
|---------|--------------------|--------------|
| modo E | M83 relativo | M82 absoluto |
| signo E | **negativo** (-1.33) | **positivo** (+49.9) |
| acumulacion | decrece | crece hasta ~13316 mm |

La maquina de cemento **extruye con E negativo**: el tornillo/husillo gira
al reves del estandar FDM (o el cableado del stepper esta invertido). Al
llegar E positivo de Cura, el tornillo va **a reversa**: no empuja cemento,
jala material hacia arriba, y la cabeza no deposita nada (o se traba).

En la configuracion Prusa de referencia:
- `#define INVERT_E0_DIR false` -> el estandar extruye con E positivo.

Por eso el firmware de la maquina inversa NECESITA que el E vaya al reves.

---

## Otras causas ya atendidas

El mismo archivo Cura tenia comandos que **trababan la maquina esperando
sensores que no existen** (ya eliminados por el corrector):

- `M109` / `M190`: espera de temperatura (termostato inexistente)
- `G28` / `G80`: homeo y nivelacion (endstops/sonda inexistentes)

Ademas, la config Marlin trae:

- `#define EXTRUDE_MINTEMP 175` -> bloquea extrusion si el hotend esta
  frio. Solo afecta si la maquina tuviera termistor leyendo <175 C. Como el
  archivo manual extruye bien sin calentar, en esta maquina no aplica
  (probablemente TEMP_SENSOR_0 desactivado o cold extrusion habilitado).

---

## Solucion recomendada (de preferencia a alternativa)

### Opcion A (mejor): invertir el sentido del motor en el firmware

En `Configuration.h` de Marlin cambiar una linea:

```
#define INVERT_E0_DIR true
```

(o invertir las dos fases del conector del motor del extrusor).

Con esto, el E **positivo** de Cura extruye cemento y el G-code de Cura
funciona tal cual, sin tocar nada mas. Es el arreglo definitivo de raiz.

### Opcion B: invertir E por software con el corrector (nueva opcion)

Se agrego la opcion **"Invertir giro del extrusor (E negativo)"** en la
GUI del Corrector G-Code (y el flag `--invertir-e` en CLI).

Que hace:

1. Fuerza modo relativo `M83` (como el archivo manual).
2. Neutraliza cualquier `M82` posterior.
3. Multiplica cada incremento E por **-1**.
4. El resultado queda con flujo E **negativo**, igual que el manual que ya
   funciona.

Uso:

```
py corregir_gcode.py PI3MK2_Fijador.gcode --invertir-e
```

En la GUI: marcar el checkbox **"Invertir giro del extrusor (E negativo)"**
antes de Procesar.

Resultado verificado sobre el archivo real: flujo E mediana de **+49.9 ->
-49.9 mm/s**, con la misma geometria y los mismos tiempos de impresion.

### Nota

No usar la opcion B si ya se aplico la opcion A (se invertiria dos veces,
devolviendo el E a positivo).

---

## Conclusiones

1. La velocidad **no** es la causa: el archivo que funciona es 40 veces mas
   lento que el que falla.
2. El **sentido del E** es la diferencia critica: la maquina extruye con E
   negativo y Cura envia E positivo.
3. Arreglo de raiz: `INVERT_E0_DIR true` en firmware (o swap de fases del
   motor).
4. Alternativa por software: la nueva opcion "Invertir E" del corrector,
   que reproduce el patron probado del archivo manual (M83 + E negativo).
5. Los bloqueos por espera (M109/M190/G28/G80) ya los elimina el corrector
   desde la version anterior.