#!/usr/bin/env python3
"""
corregir_ui.py
Interfaz grafica (tkinter) para el Corrector G-Code de la impresora de
cemento. Permite cargar un .gcode, procesarlo y guardar la version
corregida. Usa unicamente la libreria estandar de Python.

Para abrirla:
    run.bat   (o)   py corregir_ui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from corregir_gcode import (
    ELIMINAR,
    construir_correccion,
    decodificar_contenido,
)

COLOR_FONDO = "#1e1e2e"
COLOR_PANEL = "#2a2a3d"
COLOR_TEXTO = "#e0e0e0"
COLOR_AIRE = "#3b3b52"
COLOR_ACENTO = "#4f9cf9"
COLOR_OK = "#7bd88f"
COLOR_ERROR = "#ff7b72"
FUENTE = ("Consolas", 10)


class CorrectorApp:
    def __init__(self, raiz):
        self.raiz = raiz
        self.corregido_actual = None
        self.nombre_actual = None
        self.ruta_actual = None

        raiz.title("Corrector G-Code - Impresora de Cemento")
        raiz.geometry("1100x720")
        raiz.minsize(900, 600)
        raiz.configure(bg=COLOR_FONDO)

        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TFrame", background=COLOR_FONDO)
        estilo.configure("Panel.TFrame", background=COLOR_PANEL)
        estilo.configure(
            "TLabel",
            background=COLOR_FONDO,
            foreground=COLOR_TEXTO,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Panel.TLabel",
            background=COLOR_PANEL,
            foreground=COLOR_TEXTO,
            font=("Segoe UI", 10, "bold"),
        )
        estilo.configure(
            "TCheckbutton",
            background=COLOR_PANEL,
            foreground=COLOR_TEXTO,
            font=("Segoe UI", 9),
        )
        estilo.map("TCheckbutton", background=[("active", COLOR_PANEL)])
        estilo.configure(
            "TButton",
            font=("Segoe UI", 10),
            padding=(10, 6),
        )
        estilo.configure(
            "Accion.TButton",
            background=COLOR_ACENTO,
            foreground="#0b0b14",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.configure("TNotebook", background=COLOR_FONDO)
        estilo.configure(
            "TNotebook.Tab",
            background=COLOR_PANEL,
            foreground=COLOR_TEXTO,
            padding=(14, 6),
            font=("Segoe UI", 10),
        )
        estilo.map("TNotebook.Tab", background=[("selected", COLOR_AIRE)])

        self._build_widgets()

    def _build_widgets(self):
        # ---- Barra superior: botones ----
        barra = ttk.Frame(self.raiz, style="TFrame")
        barra.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(barra, text="Cargar archivo...", command=self.cargar_archivo).pack(side="left")
        ttk.Button(
            barra,
            text="Procesar",
            style="Accion.TButton",
            command=self.procesar,
        ).pack(side="left", padx=8)
        ttk.Button(barra, text="Guardar corregido...", command=self.guardar).pack(side="left")
        ttk.Button(barra, text="Limpiar", command=self.limpiar).pack(side="left", padx=8)

        self.lbl_archivo = ttk.Label(barra, text="Sin archivo cargado", style="TLabel")
        self.lbl_archivo.pack(side="right")

        # ---- Cuerpo: paneles original / corregido ----
        contenedor = ttk.Frame(self.raiz, style="TFrame")
        contenedor.pack(fill="both", expand=True, padx=12, pady=6)

        contenedor.columnconfigure(0, weight=1, uniform="pan")
        contenedor.columnconfigure(1, weight=1, uniform="pan")
        contenedor.rowconfigure(1, weight=1)

        # Panel original
        marcos_orig = ttk.Frame(contenedor, style="Panel.TFrame")
        marcos_orig.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 6))
        ttk.Label(marcos_orig, text="ARCHIVO ORIGINAL", style="Panel.TLabel").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.txt_original = tk.Text(
            marcos_orig,
            bg=COLOR_PANEL,
            fg=COLOR_TEXTO,
            insertbackground=COLOR_TEXTO,
            font=FUENTE,
            wrap="none",
            undo=True,
            bd=0,
        )
        self.txt_original.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        _agregar_scrollbar(marcos_orig, self.txt_original, row=1)

        # Panel derecha: checkboxes + resumen
        panel_opc = ttk.Frame(contenedor, style="Panel.TFrame")
        panel_opc.grid(row=0, column=1, sticky="new", padx=(6, 0))
        ttk.Label(panel_opc, text="QUE QUITAR", style="Panel.TLabel").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.check_vars = []
        for cat in ELIMINAR:
            var = tk.BooleanVar(value=True)
            self.check_vars.append((var, cat))
            ttk.Checkbutton(panel_opc, text=cat, variable=var).pack(
                anchor="w", padx=12, pady=1
            )
        ttk.Separator(panel_opc).pack(fill="x", padx=8, pady=6)
        self.var_invertir_e = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            panel_opc,
            text="Invertir giro del extrusor (E negativo)",
            variable=self.var_invertir_e,
        ).pack(anchor="w", padx=12, pady=2)
        ttk.Label(
            panel_opc,
            text="Para maquinas que extruyen con E negativo\n(usa M83 relativo y cambia el signo de E)",
            style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)
        self.var_quitar_relleno = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            panel_opc,
            text="Quitar relleno interior (infill)",
            variable=self.var_quitar_relleno,
        ).pack(anchor="w", padx=12, pady=2)
        ttk.Label(
            panel_opc,
            text="Borra los bloques ;TYPE:FILL/INFILL de Cura\ny deja solo las paredes del objeto",
            style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)
        ttk.Separator(panel_opc).pack(fill="x", padx=8, pady=4)
        self.var_curvas = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            panel_opc,
            text="Curvas (G2/G3)",
            variable=self.var_curvas,
            command=self._alternar_tol_arc,
        ).pack(anchor="w", padx=12, pady=2)
        ttk.Label(
            panel_opc,
            text="Fusiona tramos G1 en arcos G2/G3 (arc welding)\ne inyecta G17 (plano XY). Deja el giro suave\ny el codigo mas compacto.",
            style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)
        frame_tol = ttk.Frame(panel_opc, style="Panel.TFrame")
        frame_tol.pack(anchor="w", padx=12, pady=(2, 4))
        ttk.Label(
            frame_tol, text="Tolerancia (mm):", style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(side="left")
        self.var_tol_arc = tk.StringVar(value="0.10")
        self.spin_tol_arc = ttk.Spinbox(
            frame_tol,
            from_=0.05,
            to=0.50,
            increment=0.05,
            width=5,
            textvariable=self.var_tol_arc,
        )
        self.spin_tol_arc.pack(side="left", padx=4)
        self.spin_tol_arc.state(["disabled"])
        ttk.Label(
            panel_opc,
            text="Desviacion maxima entre la curva\noriginal y el arco, en milimetros.",
            style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)
        self.var_extrusion = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            panel_opc,
            text="Configurar extrusion (M200/M221)",
            variable=self.var_extrusion,
        ).pack(anchor="w", padx=12, pady=2)
        ttk.Label(
            panel_opc,
            text="Inyecta M200 S0 + M221 S100 (flujo al 100%)\ny conserva los M220/M221 del archivo",
            style="Panel.TLabel",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)
        ttk.Button(
            panel_opc,
            text="Marcar / desmarcar todo",
            command=self._alternar_categorias,
        ).pack(anchor="w", padx=8, pady=(10, 8))

        # Reporte
        marcos_rep = ttk.Frame(contenedor, style="Panel.TFrame")
        marcos_rep.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        hab = ttk.Frame(marcos_rep, style="Panel.TFrame")
        hab.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(hab, text="REPORTE", style="Panel.TLabel").pack(side="left")
        self.lbl_estado = ttk.Label(
            hab, text="Esperando archivo...", style="Panel.TLabel"
        )
        self.lbl_estado.pack(side="right")
        self.txt_reporte = tk.Text(
            marcos_rep,
            bg=COLOR_PANEL,
            fg=COLOR_OK,
            insertbackground=COLOR_TEXTO,
            font=FUENTE,
            wrap="word",
            state="disabled",
            bd=0,
        )
        self.txt_reporte.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        _agregar_scrollbar(marcos_rep, self.txt_reporte, row=1)

        # Panel corregido
        marcos_cor = ttk.Frame(contenedor, style="Panel.TFrame")
        marcos_cor.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(6, 0))
        ttk.Label(marcos_cor, text="VISTA PREVIA CORREGIDA", style="Panel.TLabel").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.txt_corregido = tk.Text(
            marcos_cor,
            bg=COLOR_PANEL,
            fg=COLOR_TEXTO,
            insertbackground=COLOR_TEXTO,
            font=FUENTE,
            wrap="none",
            state="disabled",
            bd=0,
        )
        self.txt_corregido.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        _agregar_scrollbar(marcos_cor, self.txt_corregido, row=1)

        contenedor.columnconfigure(2, weight=1, uniform="pan")

    # ---------- API ----------
    def _categorias_activas(self):
        return [cat for var, cat in self.check_vars if var.get()]

    def _set_reporte(self, texto, color=None):
        self.txt_reporte.configure(state="normal", fg=color or COLOR_OK)
        self.txt_reporte.delete("1.0", "end")
        self.txt_reporte.insert("1.0", texto)
        self.txt_reporte.configure(state="disabled")

    def _set_corregido(self, texto):
        self.txt_corregido.configure(state="normal")
        self.txt_corregido.delete("1.0", "end")
        self.txt_corregido.insert("1.0", texto)
        self.txt_corregido.configure(state="disabled")

    # ---------- Acciones ----------
    def cargar_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo G-Code",
            filetypes=[
                ("G-Code", "*.gcode;*.gco;*.g;*.cnc"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not ruta:
            return
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
            texto = decodificar_contenido(datos)
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return

        self.txt_original.delete("1.0", "end")
        self.txt_original.insert("1.0", texto)
        self.ruta_actual = ruta
        self.nombre_actual = ruta.split("/")[-1].split("\\")[-1]
        self.corregido_actual = None
        self.lbl_archivo.configure(text=self.nombre_actual)
        self.lbl_estado.configure(text="Archivo cargado. Hace clic en Procesar.")
        self._set_reporte("Archivo cargado: %s\n\nHace clic en 'Procesar'."
                          % self.nombre_actual, COLOR_OK)

    def procesar(self):
        texto = self.txt_original.get("1.0", "end-1c")
        if not texto.strip():
            messagebox.showwarning("Sin contenido", "Carga un archivo G-Code primero.")
            return
        categorias = self._categorias_activas()
        quitar_relleno = self.var_quitar_relleno.get()
        curvas = self.var_curvas.get()
        configurar_extrusion = self.var_extrusion.get()
        if not categorias and not quitar_relleno and not curvas and not configurar_extrusion:
            messagebox.showwarning(
                "Nada que quitar",
                "No seleccionaste ninguna categoria ni opcion.",
            )
            return

        try:
            contenido, reporte = construir_correccion(
                texto,
                self.nombre_actual or "<pegado>",
                categorias,
                self.var_invertir_e.get(),
                quitar_relleno,
                curvas,
                configurar_extrusion,
                self._leer_tol_arc(),
            )
        except Exception as e:
            messagebox.showerror("Error al procesar", str(e))
            return

        self.corregido_actual = contenido
        self._set_corregido(contenido)

        e = reporte["eliminadas"]
        n_total = reporte["total_lineas"]
        lineas = []
        lineas.append("PROCESADO OK")
        lineas.append("  Lineas totales:    %d" % n_total)
        lineas.append("  Lineas escritas:   %d" % reporte["lineas_escritas"])
        lineas.append("  Lineas eliminadas: %d" % len(e))
        if reporte.get("relleno_removido"):
            lineas.append(
                "  Relleno quitado:    %d bloques / %d lineas"
                % (reporte["bloques_relleno"], reporte["relleno_removido"])
            )
        if reporte.get("arcos_procesados"):
            lineas.append(
                "  Arcos G2/G3:        %d (curvas en plano XY)" % reporte["arcos_procesados"]
            )
        if reporte.get("arcos_soldados"):
            lineas.append(
                "  Arcos soldados:     %d (G1 -> G2/G3, %d lineas ahorradas)"
                % (reporte["arcos_soldados"], reporte["lineas_ahorradas"])
            )
        if reporte.get("invirtio_e"):
            lineas.append(
                "  E invertido:       %d lineas (M83 relativo)" % reporte["e_invertidos"]
            )
        lineas.append("")
        if e:
            lineas.append("COMANDOS ELIMINADOS (%d):" % len(e))
            lineas.append("-" * 60)
            for item in e:
                t = item["texto"]
                t = t[:44] + "..." if len(t) > 44 else t
                lineas.append("  L%-5d %-6s %s" % (item["linea"], item["comando"], item["razon"]))
                lineas.append("        <%s>" % t)
        else:
            lineas.append("No habia comandos que eliminar en este archivo.")

        color = COLOR_OK if e else COLOR_TEXTO
        self._set_reporte("\n".join(lineas), color)
        self.lbl_estado.configure(
            text="%d lineas eliminadas. Podes guardar la version corregida." % len(e)
        )

    def guardar(self):
        if self.corregido_actual is None:
            messagebox.showwarning("Nada que guardar", "Procesa el archivo primero.")
            return
        base = self.nombre_actual or "gcode"
        if base.lower().endswith(".gcode"):
            sugerido = base[:-6] + "_corregido.gcode"
        else:
            sugerido = base + "_corregido.gcode"
        ruta = filedialog.asksaveasfilename(
            title="Guardar G-Code corregido",
            defaultextension=".gcode",
            initialfile=sugerido,
            filetypes=[("G-Code", "*.gcode"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(self.corregido_actual)
        except OSError as e:
            messagebox.showerror("Error al guardar", str(e))
            return
        messagebox.showinfo("Guardado", "Version corregida guardada en:\n%s" % ruta)

    def limpiar(self):
        self.txt_original.delete("1.0", "end")
        self._set_corregido("")
        self._set_reporte("Todo limpio.", COLOR_TEXTO)
        self.corregido_actual = None
        self.ruta_actual = None
        self.nombre_actual = None
        self.lbl_archivo.configure(text="Sin archivo cargado")
        self.lbl_estado.configure(text="Esperando archivo...")

    def _alternar_categorias(self):
        al_menos_uno = any(var.get() for var, _ in self.check_vars)
        for var, _ in self.check_vars:
            var.set(not al_menos_uno)

    def _alternar_tol_arc(self):
        if self.var_curvas.get():
            self.spin_tol_arc.state(["!disabled"])
        else:
            self.spin_tol_arc.state(["disabled"])

    def _leer_tol_arc(self):
        try:
            valor = float(self.var_tol_arc.get().replace(",", "."))
        except ValueError:
            return 0.1
        return valor if 0.05 <= valor <= 0.5 else 0.1


def _agregar_scrollbar(parent, widget_text, row):
    scroll = ttk.Scrollbar(parent, command=widget_text.yview)
    scroll.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
    widget_text.configure(yscrollcommand=scroll.set)


def main():
    raiz = tk.Tk()
    CorrectorApp(raiz)
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())