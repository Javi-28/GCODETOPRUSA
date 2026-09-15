# Corrector G-Code — Impresora 3D de Cemento (Proyecto Isaac)

Programa (100% librería estándar de Python: `tkinter`, `re`, `pathlib`) que
convierte el G-code que genera **Cura** (un slicer pensado para filamento)
al formato que necesita la **impresora 3D de cemento** de la marca M3D
(firmware **Marlin 2.1.3** con `ARC_SUPPORT` activo en
`Configuration_adv.h`).

Además de limpiar comandos de temperatura/ventilador/homeo que la máquina no
tiene, este proyecto ataca el problema de **detección de curvas**: Cura nunca
emite arcos reales, solo polilíneas de cientos de `G1` diminutos. El programa
los reconoce y los vuelve a escribir como **arcos `G2/G3` con radio** para que
el giro sea suave y el código sea compacto.

Este documento explica **por qué existen estos problemas** (dos causas
distintas) y **cómo la comunidad resolvió casos idénticos**, como base del
criterio de detección implementado (F1 unir rectas, F2 densidad, F3 círculo).

---

## 1. Por qué tenemos estos problemas

Hay dos razones de fondo, y confundirlas hace que los diagnósticos fallen:

### Causa 1 — El software (el slicer)
- **Cura no sabe dibujar curvas.** Todo arco se representa como una *polilínea*:
  una cadena de movimientos rectos `G1` diminutos que sólo "imitan" la curva.
  El propio equipo de Cura lo confirma: *"no hay IA que decida que esto parece
  un arco; los círculos sólo existen como polígonos de muchos lados"*
  (issue #15577).
- **La resolución del slicing controla el tamaño de esos pasos.** El ajuste
  *Maximum Resolution* fija cuán chiquitos son los `G1`; *Maximum Deviation*
  fija cuánto se le permite a la polilínea desviarse de la forma real. Con
  resolución fina se generan **cientos de segmentos de <1 mm**; con resolución
  gruesa la curva se ve *poligonal* (varios usuarios midieron pasos de ~3–5 mm).
- **Precisión de 3 decimales introduce ruido.** Cura escribe coordenadas con 3
  cifras; al recomponer una recta, errores de 0.001–0.05 mm quedan "escritos"
  en el código y convierten lo que es una línea en una pared *con ruido*.
- **La simplificación de Cura (Visvalingam-Whyatt) ya elimina vértices
  colineales** durante el slicing, pero su criterio es la *desviación*: deja
  pasar micro-desviaciones y vuelve a producir segmentos cortos innecesarios
  en rectas.
- **Consecuencia concreta:** un G-code "de curvas" de Cura puede tener más
  líneas que el modelo real, y la placa procesa comandos diminutos en ráfaga
  (-> *stutter*/tartamudeo o buffer del planificador bajo).

### Causa 2 — La adaptación del mundo FDM al cemento
No imprimimos plástico fundido: **adaptamos una impresora de filamento a un
cabezal de mortero/cemento**, y casi todos los supuestos del slicer dejan de
aplicar:
- **Sin hotend ni termistor** -> `M104/M109/M140/M190` son trampas: esperan un
  sensor inexistente y **traban la máquina** (M109/M190 bloquean hasta alcanzar
  temperatura).
- **Sin cama caliente ni sondeo (mesh)** -> `G28 W`/`G80` requieren endstops y
  sonda que no existen; se eliminan. Igual `M107/M106` (no hay ventilador),
  `M207/M220/M221` (retracción/velocidad/flujo de filamento) y `M84`.
- **Extrusor distinto.** El plástico usa `M82 E` absoluto con valores que
  crecen; el tornillo extrusor de cemento gira al revés o con distinta
  proporción. Por eso el programa tiene la opción *"Invertir giro del
  extrusor (E negativo)"*: fuerza `M83` (relativo) e **invierte el signo de
  cada incremento E**, replicando el archivo manual que ya funciona en la
  máquina.
- **ARC_SUPPORT depende del firmware.** Marlin no acepta `G2/G3` "de fábrica";
  hay que compilarlo con `ARC_SUPPORT` y planificar en el plano correcto
  (`G17`, plano XY). Nuestro firmware ya lo trae activo, y un archivo de
  referencia de la máquina confirma que los arcos `G2/G3 R` (incluso
  helicoidales con Z) funcionan correctamente.

### El síntoma que nos hizo trabajar en esto
Aplicando arc welding "ingenuo" sobre los `G1` de Cura aparecían arcos
**monstruosos**: radios de **2792 mm, 305 mm** sobre paredes casi rectas con
ruido, y a la vez **micro-arcos de 0.005 mm** en esquinas con puntos casi
duplicados. Esto **no es un bug nuestro en particular**: es el mismo problema
que tuvo ArcWelder y que la comunidad resolvió añadiendo *radio máximo*,
*detección de colinealidad* y un detector de errores (ver sección 2).

---

## 2. Cómo lo resolvió la comunidad (investigación)

### 2.1 ArcWelder y el plugin "Arc Welder" para Cura
Referencias:
- https://github.com/FormerLurker/ArcWelderLib
- https://plugins.octoprint.org/plugins/arc_welder
- https://github.com/fieldOfView/Cura-ArcWelderPlugin
- https://hackaday.com/2020/11/03/this-gcode-post-processor-squeezes-lines-into-arcs

ArcWelder "suelda" tramos de `G0/G1` a `G2/G3` para **anti-stutter y
compresión de G-code**. Sus decisiones clave, todas replicables:
- **Construye un arco solo si** (1) el arco puede intersecar todos los
  puntos de intersección entre segmentos consecutivos y (2) la distancia entre
  el segmento y el arco no supera un umbral de error.
- **Resolución por defecto 0.05 mm** (desviación máxima ±0.025): el "play" que
  se le da a la herramienta. Subirla = más compresión pero menos fidelidad;
  los slicers ya hacen este compromiso por defecto.
- **`--max-radius` (radio máximo)**: añadido *como protección* para que rectas
  casi perfectas no se conviertan en arcos gigantes.
- **Detección de colinealidad integrada**: evita convertir rectas en arcos;
  aun así, desviaciones por la precisión de 3 decimales del G-code (0.001 mm)
  pueden generar arcos donde sobra una recta -> por eso el ajuste manual.
- **`--mm-per-arc-segment`**: debe coincidir con el ajuste del firmware (1.0 en
  el 99% de los casos) para la compensación de longitud de arco.
- **Problema real documentado** (issue #93): arcos malos con `I-0 J-0` y
  desvíos gigantes (`J 28697.69`) al soldar una recta casi recta -> la misma
  clase de error que vimos. La solución fue el detector de errores + el radio
  máximo + la detección de colinealidad.

### 2.2 Marlin: cómo ejecuta los arcos G2/G3
Referencias:
- https://marlinfw.org/docs/gcode/G002-G003.html
- https://github.com/MarlinFirmware/Marlin/issues/2519
- https://github.com/bigtreetech/BIQU-B1/issues/26

- Para usar arcos hay que compilar con `ARC_SUPPORT`. Se detecta con `M115`
  (EXTENDED_CAPABILITIES) o enviando un `G2` vacío.
- Existen **dos formatos**: centro `I/J` (offsets desde el punto de inicio) o
  **radio `R`**. No se pueden mezclar. Nosotros emitimos `R`, que es el formato
  del archivo manual de la máquina.
- **Marlin NO dibuja NUNCA curvas reales**: convierte cada `G2/G3` en muchos
  segmentos pequeños según `MM_PER_ARC_SEGMENT` (por defecto **1 mm**). O sea,
  el filtmo vuelve a segmentar el arco; el beneficio real es que la placa puede
  calcularlo sin enviar miles de comandos por el puerto (menos carga y menos
  stutter), y el giro se ve más suave.
- **`G2/G3 bad parameters`** es un error típico (por ejemplo, `R` con `I/J`
  mezclados, radio < mitad de la cuerda, o coordenadas repetidas): el firmware
  simplemente ignora/bota la línea. Por eso nuestros arcos se validan bien
  antes de emitirse.
- Arcos con diámetro menor al segmento predeterminado no son recomendados:
  para micro-arcos de 0.005 mm el firmware no sabría dibujarlos.

### 2.3 Cura: por qué emite tantos segmentos
Referencias:
- https://github.com/Ultimaker/CuraEngine/wiki/Simplify
- https://github.com/Ultimaker/Cura/issues/15577
- https://community.ultimaker.com/topic/26465-help-me-understand-maximum-resolution-setting

- Cura **nunca emite G2/G3**: toda curva sale como polilínea de `G1`.
- La simplificación usa Visvalingam-Whyatt con importancia = desviación del
  vértice respecto a la línea entre sus vecinos: elimina vértices colineales y
  casos degenerados (segmentos de longitud cero), pero **dentro del límite de
  "Maximum Deviation"**; no puede quitar micro-ruido de 3 decimales.
- Resolución fina -> muchos pasos cortos y riesgo de **stutter**; resolución
  gruesa -> curvas con facetas visibles. Cada usuairo elige su punto.
  Nosotros corremos después del slicer justamente para que **la resolución de
  Cura deje de importar tanto**.

### 2.4 Herencia CNC (G02/G03)
- Los arcos circulares vienen del mundo CNC (fresadoras/tornos), no de la
  impresión 3D. El formato `R` es el más simple pero tiene una ambigüedad
  conocida: un radio define **dos** arcos posibles; la mayoría de controles
  toma siempre el menor (<180°). Para arcos ≥180° conviene `I/J` o dividir.
- Caso conocido: controles viejos tenían errores grandes cerca de arcos de
  180°; por eso los post-procesadores validan los arcos que emiten.
- Reflexión de la comunidad: todo CAM "serio" ya genera `G2/G3`; los slicers de
  impresión 3D tardaron años en seguirlos.

---

## 3. Cómo lo resolvemos aquí: detección de curvas en dos etapas

Sobre un *run* (tramo de líneas `G1` con `X` e `Y` consecutivas; cualquier
`G0`, `G92`, `M82/M83` o comentario lo corta) solo hay tres señales útiles:

| Señal | Interpretación |
|---|---|
| Dirección constante entre puntos | Es una **recta** -> "sucesiones innecesarias", unirlas en un solo `G1`. |
| Muchos puntos en poca distancia, girando | **Probable curva** -> probar un círculo. |
| Cualquier otra cosa (zigzag, S, espiral) | No es un círculo -> dejar los `G1` intactos. |

### F1 — Unir rectas (filtro de línea) [opción separada, implementado]
Antes de buscar curvas, colapsar los puntos casi colineales:
- Un tramo es colineal si **cada punto intermedio se desvía ≤ umbral** de la
  recta que une el primero con el último (desvío perpendicular) y su proyección
  cae dentro del segmento (para no unir retrocesos).
- Umbral **configurable** (GUI/CLI), default **0.05 mm**, rango 0.02–0.25.
- Mínimo 3 puntos (2 segmentos) para colapsar; `E` se suma (modo relativo) o se
  toma el último absoluto (modo absoluto); `F` del último; `Z` solo si idéntico
  (no toca helicoides).
- **Beneficio estructural:** al colapsar la recta primero, el detector de
  curvas nunca ve una pared subdividida -> desaparece el caso "R=2792" sin
  esforzar los filtros de radio.

### F2 — Densidad de curva: "3+ movimientos en 2 mm" [criterio acordado, implementado]
Un tramo se considera *candidato a curva* si, en una **ventana deslizante**, se
recorrieron **3 o más movimientos consecutivos dentro de 2 mm** de distancia
recorrida (umbral configurable `--densidad` / GUI *Distancia densidad*). Es un
*pre-filtro*: solo marca "probable curva" para la etapa F3. Las rectas unidas en
F1 ya no llegan aquí; un acabado de 2 movimientos nunca llega.

### F3 — Ajuste de círculo (implementado)
Sobre el candidato curvoo se prueba un círculo con **todos** estos criterios
(independientes, por eso no es "demasiado sensible"):

| Criterio | Valor default | Qué evita |
|---|---|---|
| Desviación de cada vértice al círculo | `tolerancia` = **0.1 mm** (GUI 0.05–0.5; `--tol-arc`) | ruido y tramos de distinta curva |
| **Flecha (sagitta)** de cada segmento vs el arco | ≤ tolerancia | redondear esquinas cuadradas (une 2 rectas) |
| Radio mínimo | **0.2 mm** | micro-arcos de 0.005–0.008 mm por puntos casi duplicados |
| Radio máximo | **200 mm** | tramos casi rectos con ruido (R≈2792 / R≈305) |
| Barrido acumulado (giro) mínimo | **15°** | paredes planas con micro-ruido (2–3°) |
| Giro total | ≤ 360° | puntos repetidos / ruido de precisión |
| No colineales | — | rectas exactas |

Se elige el **prefijo más largo** del run que cumpla todo, y se emite **una**
línea de arco:
- `G3` si el giro acumulado es positivo (anti-horario) / `G2` si es negativo
  (horario), en plano `G17`.
- `X/Y` del último punto, `Z` opcional (arco helicoidal), **`R`** del círculo.
- `E`: **suma de incrementos** si el modo es relativo (`M83`/invertir E) o el
  **último valor absoluto** si `M82`.
- `F` del último segmento del tramo.

**Qué NO se toca nunca:** los tramos de menos de 4 puntos, los no circulares
(se quedan como `G1`), lineas con `G0`, `G92`, cambios de modo, comentarios.

### Resultados medidos (archivo real `PI3MK2_Fijador.gcode`)

| Métrica | Antes del endurecimiento | Hoy |
|---|---|---|
| Arcos emitidos | 38 (incl. R≈2792, R≈305, R≈0.005) | **16** |
| Radios de los arcos | 0.005 … 2792 mm | reales (filtró R≈2792, R≈0.005) |
| Líneas ahorradas | (sin control) | **179** |
| Cuadrados / rectas con ruido | se "redondeaban" | **intactos como G1** |
| Rectas unidas (F1) | — | PI3MK2 no tiene paredes rectas; verificado en la suite de pruebas |

El archivo de referencia "hace bien curvas" (con sus 64 G2/G3) se procesa sin
tocarlos, y "hace bien extrusión" sigue exacto.

---

## 4. Cómo verificar y afinar en la práctica

- **GUI:** la opción *Curvas (G2/G3)* + su *Tolerancia (mm)*; la opción
  separada *Unir rectas* con su umbral.
- **CLI:**
  - `python corregir_gcode.py entrada.gcode --curvas --invertir-e`
  - `python corregir_gcode.py entrada.gcode --curvas --tol-arc=0.05`
  - `python corregir_gcode.py entrada.gcode --unir-rectas --tol-recta=0.05`
- **Logs:** todo se registra en `logs/CorrectorGcode.log` (carpeta junto al
  script o al ejecutable). Nivel **DEBUG** en archivo, INFO en consola. Cada
  tramo de G1 evaluado queda documentado: el que se suelda (con R, barrido y
  líneas ahorradas) y el descartado **con su motivo** (p. ej. "radio 276.7 >
  límite 200.0", "barrido 12.7° < mínimo 15.0", "segmento 0 corta la esquina
  1.585 mm", "micro-arco por ruido").
- **Diagnóstico rápido de un archivo sospechoso:** abrir el `.log`, buscar
  "NO se suelda" y leer la causa; en la GUI el reporte ya muestra las
  categorías eliminadas.

---

## 5. Flujo completo del programa

1. **Leer** el archivo (UTF-8, tolerante a BOM/UTF-16).
2. **Eliminar comandos irrelevantes** por categoría (temperatura, homeo, mesh,
   ventilador, config), con resync `G92 E` tras quitar relleno.
3. **Invertir E** (opcional): `M83` + signo de cada incremento.
4. **Unir rectas** (F1, planeada) -> **Detectar y soldar curvas** (F2+F3).
5. **Inyectar prefijo** (G17 / M200/M220/M221 / M83 según opciones) y **cabecera
   comentada**.
6. **Guardar** `_corregido.gcode` y registrar todo en el log.

---

## 6. Referencias

- ArcWelder: https://github.com/FormerLurker/ArcWelderLib
- Plugin oficial de Cura: https://github.com/fieldOfView/Cura-ArcWelderPlugin
- Cura ArcWelder (Guía/OctoPrint): https://plugins.octoprint.org/plugins/arc_welder
- Hackaday (análisis divulgativo): https://hackaday.com/2020/11/03/this-gcode-post-processor-squeezes-lines-into-arcs
- Issue G2/G3 malos de ArcWelder: https://github.com/FormerLurker/ArcWelderPlugin/issues/93
- G2/G3 en Marlin: https://marlinfw.org/docs/gcode/G002-G003.html
- Marlin "arcos verdaderos" (discusión): https://github.com/MarlinFirmware/Marlin/issues/2519
- CuraEngine Simplify (Visvalingam-Whyatt): https://github.com/Ultimaker/CuraEngine/wiki/Simplify
- "Cura no produce círculos" (issue #15577): https://github.com/Ultimaker/Cura/issues/15577
- Maximum Resolution / Maximum Deviation: https://community.ultimaker.com/topic/26465-help-me-understand-maximum-resolution-setting
- G02/G03 para CNC (teoría): https://www.machiningdoctor.com/gcodes/g2-3-circular