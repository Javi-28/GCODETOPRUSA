# Analisis de G-Code para Impresora 3D de Cemento

## Contexto

Este proyecto consiste en una **impresora 3D modificada para imprimir cemento**. El software generador de G-code (Cura) produce instrucciones pensadas para impresoras de plastico con firmware Marlin, las cuales incluyen comandos de temperatura, homeo, nivelacion de cama y control de ventiladores. La maquina de cemento **no tiene** sensores de temperatura, endstops, ni ventilador de enfriamiento, por lo que muchos de estos comandos pueden **trabar la maquina** esperando sensores que nunca responden.

El archivo `PRUEBA IMPRESORA 2.gcode` es el formato **nativo** que la maquina ejecuta correctamente. El archivo `PI3MK2_Fijador.gcode` es el generado por Cura y contiene las instrucciones problemáticas.

---

## Archivos del Proyecto

| Archivo | Descripcion |
|---------|-------------|
| `PRUEBA IMPRESORA 2.gcode` | G-code nativo de la maquina de cemento (formato correcto) |
| `PI3MK2_Fijador.gcode` | G-code generado por Cura 5.0.0 para impresora Prusa MK2 (formato con problemas) |
| `corregir_gcode.py` | Script Python que transforma G-code de Cura a formato compatible con la maquina de cemento |

---

## Instrucciones del G-code Nativo (Maquina de Cemento)

El archivo `PRUEBA IMPRESORA 2.gcode` solo usa estas instrucciones:

```
G90          Posicionamiento absoluto
M83          Extrusion relativa (E es incremento, no posicion absoluta)
G1           Movimiento lineal con parametros X Y Z E F
```

Esto es todo lo que la maquina necesita: **movimiento + extrusion**. Sin temperatura, sin sensores, sin ventiladores.

---

## Instrucciones del G-code Generado por Cura

El archivo `PI3MK2_Fijador.gcode` contiene las siguientes categorias de comandos:

### Comandos de Modo / Configuracion (SEGUROS - conservar)

| Comando | Funcion | Evaluacion |
|---------|---------|------------|
| `G90` | Posicionamiento absoluto | SEGURO - conservar |
| `G91` | Posicionamiento relativo | SEGURO - conservar |
| `G21` | Unidades en milimetros | SEGURO - conservar |
| `M82` | Extrusion absoluta | SEGURO - conservar |
| `M83` | Extrusion relativa | SEGURO - conservar |
| `G92 E0` | Reset de posicion de extrusor | SEGURO - conservar |
| `;` (comentarios) | Metadata e informacion | SEGURO - conservar |

### Comandos de Movimiento (SEGUROS - conservar)

| Comando | Funcion | Evaluacion |
|---------|---------|------------|
| `G0` | Rapido sin extrusion (travel) | SEGURO - conservar |
| `G1` con E | Movimiento lineal con extrusion | SEGURO - conservar (esencial) |
| `G1` sin E | Movimiento lineal sin extrusion | SEGURO - conservar |

### Comandos de Temperatura (PELIGROSOS - eliminar)

| Comando | Funcion | Por que eliminar |
|---------|---------|-----------------|
| `M104 S231` | Fija temperatura del hotend (sin espera) | La maquina no tiene hotend ni termistor. Puede causar errores o ser ignorado silenciosamente. |
| `M109 S231` | **Espera** a que el hotend alcance temp | **BLOQUEANTE.** La maquina se queda esperando un sensor que nunca responde. |
| `M140 S23` | Fija temperatura de la cama (sin espera) | La maquina no tiene cama caliente ni termistor. |
| `M190 S23` | **Espera** a que la cama alcance temp | **BLOQUEANTE.** La maquina se queda esperando un sensor que nunca responde. |

### Comandos de Homeo y Nivelacion (PELIGROSOS - eliminar)

| Comando | Funcion | Por que eliminar |
|---------|---------|-----------------|
| `G28 W` | Homeo de todos los ejes | Requiere endstops (interruptores fisicos). Sin ellos la maquina no sabe donde esta y puede colisionar contra los limites mecanicos. |
| `G80` | Nivelacion de cama por mesh (Prusa) | Requiere sonda de nivelacion (BLTouch, etc.). La maquina de cemento no tiene sonda. |
| `G29` | Auto bed leveling generico | Requiere probe/sensor de nivelacion inexistente. |

### Comandos de Ventilador (INNECESARIOS - eliminar)

| Comando | Funcion | Por que eliminar |
|---------|---------|-----------------|
| `M106 S255` | Encender ventilador al 100% | La maquina de cemento no tiene ventilador de enfriamiento de plastico. |
| `M107` | Apagar ventilador | Innecesario. No hay fan. |

### Comandos de Configuracion Adicional (INNECESARIOS - eliminar)

| Comando | Funcion | Por que eliminar |
|---------|---------|-----------------|
| `M221 S100` | Porcentaje de flujo | Configuracion de plastico, no aplica al cemento. |
| `M220 S100` | Porcentaje de velocidad de impresion | Redundante con los feedrates en cada movimiento. |
| `M207 S0.0` | Configuracion de retraccion firmware | La retraccion de plastico no aplica al cemento. |
| `M117` | Mensaje en pantalla LCD | Inofensivo pero innecesario. |
| `M104 S0` | Apagar hotend al final | La maquina no tiene hotend. |
| `M140 S0` | Apagar cama al final | La maquina no tiene cama caliente. |
| `M84` | Deshabilitar motores | Puede ser util al final, pero la maquina lo maneja de forma distinta. |

---

## Clasificacion Final: Que Conservar vs Eliminar

### CONSERVAR (Movimiento + Configuracion base)

```
G90, G91, G21, M82, M83, G0, G1, G92
```

### ELIMINAR (Trazar/Travar maquina)

```
M104, M109, M140, M190    <- Temperatura (traba la maquina)
G28, G29, G80, G30        <- Homeo/Nivelacion (requiere sensores)
M106, M107                 <- Ventilador (no existe)
M220, M221                 <- Ajustes de flujo/velocidad (irrelevante)
M207, M208, M209           <- Retraccion firmware (irrelevante)
M117                       <- Mensaje LCD (irrelevante)
M84                        <- Deshabilitar motores (manejo manual)
```

---

## Referencia: Descripcion de Cada Comando Eliminado

### M104 - Fija Temperatura Hotend (sin espera)
- **Fuente:** https://marlinfw.org/docs/gcode/M104.html
- Establece la temperatura objetivo del hotend y continua inmediatamente sin esperar.
- En la maquina de cemento, no hay hotend ni termistor, asi que este comando puede causar errores silenciosos.

### M109 - Espera Temperatura Hotend (BLOQUEANTE)
- **Fuente:** https://marlinfw.org/docs/gcode/M109.html
- Establece la temperatura del hotend y **pausa** la ejecucion hasta que el sensor reporte que se alcanzo.
- **Es el principal causante de que la maquina se trabe.** Sin termistor, la temperatura nunca sera reportada y la maquina queda en loop infinito.

### M140 - Fija Temperatura Cama (sin espera)
- **Fuente:** https://marlinfw.org/docs/gcode/M140.html
- Establece la temperatura objetivo de la cama caliente y continua sin esperar.
- Sin resistencia de cama ni termistor, irrelevante.

### M190 - Espera Temperatura Cama (BLOQUEANTE)
- **Fuente:** https://marlinfw.org/docs/gcode/M190.html
- Establece la temperatura de la cama y **pausa** hasta que el sensor confirme.
- **Otro comando que traba la maquina.** Mismo problema que M109 pero para la cama.

### G28 - Auto Home
- **Fuente:** https://all3dp.com/2/g28-g-code-homing
- Mueve todos los ejes hacia sus endstops para establecer la posicion cero.
- Requiere interruptores de fin de carrera (endstops) que la maquina de cemento no tiene.
- Sin endstops, la maquina no puede determinar su posicion inicial de forma segura.

### G80 - Mesh Bed Leveling (Prusa)
- **Fuente:** https://marlinfw.org/docs/gcode/G029.html
- Nivelacion de cama mediante sonda que mide multiples puntos de la superficie.
- Requiere BLTouch, sensor inductivo, o sonda similar.
- La maquina de cemento no tiene este hardware.

### G29 - Auto Bed Leveling
- **Fuente:** https://marlinfw.org/docs/gcode/G029.html
- Varias modalidades de nivelacion automatica de cama (3-punto, bilinear, etc).
- Todas requieren algun tipo de probe/sensor.

### M106 / M107 - Control de Ventilador
- **Fuente:** https://marlinfw.org/docs/gcode/M106.html
- M106 enciende el ventilador de enfriamiento de pieza (0-255).
- M107 apaga el ventilador.
- En impresion de cemento no hay ventilador de enfriamiento.

### M220 - Velocidad de Impresion (%)
- **Fuente:** https://marlinfw.org/docs/gcode/M220.html
- Ajusta el porcentaje global de velocidad. Redundante con los valores F en cada G1.

### M221 - Flujo de Extrusion (%)
- **Fuente:** https://marlinfw.org/docs/gcode/M221.html
- Ajusta el porcentaje de flujo de extrusion. Configuracion de plastico.

### M207 - Retraccion Firmware
- **Fuente:** https://marlinfw.org/docs/gcode/M207.html
- Configura parametros de retraccion (longitud, velocidad). La retraccion de plastico no aplica al cemento.

### M117 - Mensaje en Pantalla
- Muestra texto en la pantalla LCD de la impresora. Inofensivo pero irrelevante.

---

## Flujo del Script `corregir_gcode.py`

```
Archivo .gcode de Cura
        |
        v
  [Parsing linea por linea]
        |
        v
  [Verificar si la linea es comando conocido]
        |
        +-- Comando en lista de eliminacion? --> Registrar en log --> Saltar (no escribir)
        |
        +-- Comando seguro? --> Escribir al archivo de salida
        |
        +-- Comentario (;)? --> Escribir al archivo de salida
        |
        +-- Linea vacia? --> Escribir al archivo de salida
        |
        v
  Archivo {nombre}_corregido.gcode
        |
        v
  [Imprimir reporte de cambios]
```

---

## Ejemplo de Transformacion

### Entrada (Cura - original):
```gcode
M82
G21
G90
M104 S231 ; set extruder temp
M140 S23 ; set bed temp
M190 S23 ; wait for bed temp       <-- TRABA
M109 S231 ; wait for extruder temp <-- TRABA
G28 W ; home all                    <-- REQUIERE ENDSTOPS
G80 ; mesh bed leveling             <-- REQUIERE SONDAS
G92 E0
G1 Y-3.0 F1000.0
G1 X60.0 E9.0 F1000.0
...
```

### Salida (corregido):
```gcode
M82
G21
G90
G92 E0
G1 Y-3.0 F1000.0
G1 X60.0 E9.0 F1000.0
...
```

---

## Notas Adicionales

1. **Extrusion vs Posicion:** La maquina de cemento funciona con M83 (extrusion relativa) como se ve en el archivo nativo. El script podria forzar M83 al inicio para consistencia.

2. **Intro Lines:** Las lineas de intro (`G1 X60.0 E9.0`) que Cura genera al inicio son para purgar el hotend de plastico. En cemento podrian no ser necesarias pero no causan dano (solo extruyen en vacio o sobre la base).

3. **Comentarios de Cura:** Las lineas que empiezan con `;` son comentarios. Incluyen metadata como `;TYPE:WALL-OUTER`, `;MESH:`, `;LAYER:`. Son informativos y no afectan la ejecucion.

4. **Velocidades y Feedrates:** Los valores `F` en los comandos G1 son importantes y se conservan. La velocidad de impresion del cemento debe ser calibrada segun la viscosidad del material.

5. **Spiralize (Vase Mode):** El archivo de Cura tiene `magic_spiralize = True` en la configuracion, lo que significa impresion en modo vaso (pared unica continua). Esto si es relevante para cemento y se conserva en los movimientos G1.

---

## Interfaz Grafica y Aplicacion

La aplicacion tiene una interfaz grafica (tkinter, sin dependencias) y un
pipeline de compilacion que genera un instalador profesional de Windows
(PyInstaller + Inno Setup), de modo que la PC de destino no necesita tener
Python instalado.

### Archivos de la aplicacion

| Archivo | Descripcion |
|---------|-------------|
| `corregir_gcode.py` | Logica de correccion (reutilizada por CLI, GUI y compilacion) |
| `corregir_ui.py` | Interfaz grafica (cargar, procesar, previsualizar y guardar) |
| `run.bat` | Abre la GUI desde el codigo sin instalar nada (modo portable) |
| `compilacion/` | Pipeline de compilacion (PyInstaller + Inno Setup + ZIP) |
| `compilacion/compilar.py` | Compila el `.exe`, el `setup.exe` y arma el ZIP en `distribucion/` |
| `compilacion/CorrectorGcode.iss` | Script de Inno Setup (instalador profesional) |
| `compilacion/generar_icono.py` | Genera el icono de la aplicacion |
| `distribucion/` | Artefactos finales: `CorrectorGcode-Setup.exe`, `portable/` y `.zip` (generados) |

### Modo portable (sin instalar)

```
run.bat
```

o desde una consola:

```
py corregir_ui.py
```

### Uso de la GUI

1. Clic **"Cargar archivo..."** y seleccionar el `.gcode` generado por Cura.
2. Elegir con los checkboxes que categorias de comandos quitar
   (todas marcadas por defecto).
3. Clic **"Procesar"**: se muestra el reporte de lo eliminado y la vista
   previa corregida.
4. Clic **"Guardar corregido..."** para descargar el archivo
   `{nombre}_corregido.gcode`.

### Robustez del parser

El script identifica el comando de cada linea aun si el formato cambia:

- Mayusculas/minusculas: `g28` es lo mismo que `G28`
- Espacios raros: `M 104`, `G 90`
- Numeros de linea: `N10 M109 S231`
- Comentarios en la linea: `M104 ; set extruder temp`
- BOM (encabezado UTF-8): `\ufeffG90`
- Decimales: `G1.5` se normaliza a `G1`
- Codificaciones: lee UTF-8 (con o sin BOM) y latin-1

La correccion es determinista: misma entrada, misma salida, siempre.
