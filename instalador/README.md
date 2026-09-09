# Instalador - Corrector G-Code para Impresora de Cemento

## Que hace el instalador

Instala la aplicacion "Corrector G-Code" en tu sistema sin necesidad de
dependencias externas (usa solo la libreria estandar de Python).

## Como instalar

1. Doble clic en **Instalar.bat** (o `py instalar.py`).
2. Se copian los archivos a `%LOCALAPPDATA%\Programs\CorrectorGcode`.
3. Se crean accesos directos en el **Escritorio** y en el **Menu Inicio**.
4. Al terminar se abre la aplicacion automaticamente.

## Archivos instalados

```
%LOCALAPPDATA%\Programs\CorrectorGcode\
  corregir_gcode.py         (logica de correccion + CLI)
  corregir_ui.py            (interfaz grafica)
  ANALISIS.md               (documentacion del analisis)
  Iniciar CorrectorGcode.bat
  Desinstalar CorrectorGcode.bat
  desinstalar.py
```

## Como desinstalar

- Ejecuta **"Desinstalar CorrectorGcode"** desde el Menu Inicio o el
  Escritorio.

## Sin instalacion (modo portable)

Si no queres instalar nada, ejecuta directamente `run.bat` desde la carpeta
principal del proyecto, o desde la consola:

```
py corregir_ui.py
```

El instalador tambien pasa los archivos fuente a la aplicacion instalada,
asi que editar `corregir_gcode.py` en el proyecto y reinstalar actualiza la
version instalada.