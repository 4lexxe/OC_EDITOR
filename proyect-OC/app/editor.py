import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _bootstrap_tk_libraries():
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_roots = []
    for root in (getattr(sys, "base_prefix", ""), getattr(sys, "exec_prefix", ""), os.path.dirname(sys.executable)):
        if root and root not in candidate_roots:
            candidate_roots.append(root)

    for root in candidate_roots:
        tcl_dir = os.path.join(root, "tcl", "tcl8.6")
        tk_dir = os.path.join(root, "tcl", "tk8.6")
        init_tcl = os.path.join(tcl_dir, "init.tcl")
        tk_tcl = os.path.join(tk_dir, "tk.tcl")

        if os.path.isfile(init_tcl):
            os.environ.setdefault("TCL_LIBRARY", tcl_dir)
        if os.path.isfile(tk_tcl):
            os.environ.setdefault("TK_LIBRARY", tk_dir)

        if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
            return


_bootstrap_tk_libraries()

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import scrolledtext
from bitstring import BitArray
from modelo.Von_Neumann import VonNeuman
from modelo import Inferidor
from modelo.explicacion_microops import texto_explicacion_codigo
from modelo.Generador import generar, ErrorGeneracion
from modelo.traza import simular_traza
from compilador.AnalizadorSintactico import parser, preprocesar_linea_microop  # IMPORTANTE (arriba del archivo)
from config import PreferencesManager


def _bin_a_hex_ui(s: str, bits: int) -> str:
    """Convierte cadena binaria a hex para mostrar; bits 12 → 3 dígitos, bits 1 → 0/1."""
    raw = "".join(c for c in (s or "") if c in "01")
    if bits == 1:
        if not raw:
            return "?"
        return raw[-1]
    if not raw:
        return "—"
    raw = raw.zfill(bits)[-bits:]
    try:
        v = int(raw, 2) & ((1 << bits) - 1)
        return f"{v:03X}"
    except ValueError:
        return "—"


def _hex_a_bin_ui(s: str, bits: int) -> str:
    """Parseo hex (acepta 0x, espacios) → binario en `bits` caracteres."""
    t = (s or "").strip().upper().replace("0X", "")
    if bits == 1:
        if not t:
            return "0"
        if t[-1] in "01":
            return t[-1]
        try:
            return str(int(t[-1:], 16) & 1)
        except ValueError:
            return "0"
    hx = "".join(c for c in t if c in "0123456789ABCDEF")
    if not hx:
        return "0" * bits
    try:
        v = int(hx, 16) & ((1 << bits) - 1)
    except ValueError:
        return "0" * bits
    return format(v, f"0{bits}b")


class CPU_UI:

    def __init__(self, root):
        self.root = root
        self.prefs = PreferencesManager()
        self._theme_mode = self.prefs.get("theme", "mode")
        self._zoom_percent = self.prefs.get("ui", "zoom_percent")
        self._theme_colors = {}
        self._status_label = None
        self._instruccion_label = None
        self._gen_entry = None
        self._gen_hint_label = None
        self._gen_result_label = None
        self._trace_tree = None
        self._trace_notebook = None
        self._trace_explicacion_text = None
        self._trace_after_id = None
        self._infer_after_id = None
        self._base_tk_scaling = float(self.root.tk.call("tk", "scaling"))
        self._base_named_font_sizes = self._capturar_tamanos_fuente_base()
        self._aplicar_zoom_global(self._zoom_percent)
        self.configurar_ventana()
        self.crear_menubar()
        self.cpu = VonNeuman()
        self.pc = 0  # program counter

        self.mem_vars_edit = []
        self.mem_vars_view = []
        self._suppress_reg_trace = False

        self.main = ttk.Frame(root, padding=8)
        self.main.pack(fill="both", expand=True)

        self.main.columnconfigure(0, weight=0)
        self.main.columnconfigure(1, weight=2)
        self.main.columnconfigure(2, weight=1)
        self.main.rowconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)

        self.crear_barra_izquierda()
        self.crear_editor_codigo()
        self.crear_panel_traza()
        self.crear_barra_inferior()
        # El panel de traza se crea después del primer aplicar_tema del editor; repetir tema para esos widgets
        self.aplicar_tema(self._theme_mode)
        self._programar_actualizar_inferencia()

    # ---------------------------
    # 🪟 Ventana
    # ---------------------------
    def configurar_ventana(self):
        self.root.title("Simulador CPU")
        self.root.geometry("1320x720")

    def _capturar_tamanos_fuente_base(self):
        names = [
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ]
        sizes = {}
        for name in names:
            try:
                sizes[name] = int(tkfont.nametofont(name).cget("size"))
            except (tk.TclError, ValueError, TypeError):
                continue
        return sizes

    def _aplicar_zoom_global(self, zoom_percent):
        try:
            zoom_percent = int(zoom_percent)
        except (TypeError, ValueError):
            zoom_percent = 100

        zoom_percent = max(80, min(200, zoom_percent))
        self._zoom_percent = zoom_percent
        factor = zoom_percent / 100.0

        try:
            self.root.tk.call("tk", "scaling", self._base_tk_scaling * factor)
        except tk.TclError:
            pass

        for name, base_size in self._base_named_font_sizes.items():
            try:
                named_font = tkfont.nametofont(name)
            except tk.TclError:
                continue

            sign = -1 if base_size < 0 else 1
            scaled_abs = max(7, int(round(abs(base_size) * factor)))
            named_font.configure(size=sign * scaled_abs)

    def _scaled_size(self, base_size, min_size=7):
        return max(min_size, int(round(base_size * (self._zoom_percent / 100.0))))

    def crear_menubar(self):
        menubar = tk.Menu(self.root)

        menu_archivo = tk.Menu(menubar, tearoff=0)
        menu_archivo.add_command(label="Reiniciar", command=self.reiniciar)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.root.destroy)

        menu_editar = tk.Menu(menubar, tearoff=0)
        menu_editar.add_command(label="Copiar", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        menu_editar.add_command(label="Cortar", command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
        menu_editar.add_command(label="Pegar", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        menu_editar.add_separator()
        menu_editar.add_command(label="Preferencias", command=self.abrir_preferencias)

        menu_ver = tk.Menu(menubar, tearoff=0)
        menu_ver.add_command(label="Tema claro", command=lambda: self._set_theme_from_menu("light"))
        menu_ver.add_command(label="Tema oscuro", command=lambda: self._set_theme_from_menu("dark"))
        menu_ver.add_separator()
        menu_ver.add_command(label="Zoom +", command=lambda: self._adjust_zoom(10))
        menu_ver.add_command(label="Zoom -", command=lambda: self._adjust_zoom(-10))
        menu_ver.add_command(label="Zoom 100%", command=self._reset_zoom)

        menu_ejecutar = tk.Menu(menubar, tearoff=0)
        menu_ejecutar.add_command(label="Ejecutar 1 instruccion", command=self.ejecutar_una)
        menu_ejecutar.add_command(label="Inferir instruccion", command=self.inferir_instruccion)
        menu_ejecutar.add_command(label="Generar microoperaciones", command=self.generar_microops)

        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menu_ayuda.add_command(label="Acerca de", command=self.mostrar_acerca_de)

        menubar.add_cascade(label="Archivo", menu=menu_archivo)
        menubar.add_cascade(label="Editar", menu=menu_editar)
        menubar.add_cascade(label="Ver", menu=menu_ver)
        menubar.add_cascade(label="Ejecutar", menu=menu_ejecutar)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)

        self.root.config(menu=menubar)
        self.menubar = menubar

    # ---------------------------
    # 📚 Barra Izquierda
    # ---------------------------
    def crear_barra_izquierda(self):
        left_panel = ttk.Frame(self.main)
        left_panel.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0,8))

        self.crear_registros(left_panel)
        self.crear_memoria_editable(left_panel)

    def _reg_hex_field_commit(self, name, bits, event=None):
        """Sincroniza hex → bin y normaliza hex (FocusOut / Enter en columna hex)."""
        self._suppress_reg_trace = True
        try:
            raw_bin = _hex_a_bin_ui(self.register_hex_vars[name].get(), bits)
            self.registers[name].set(raw_bin)
            self.register_hex_vars[name].set(_bin_a_hex_ui(raw_bin, bits))
        finally:
            self._suppress_reg_trace = False
        if event is not None and getattr(event, "keysym", None) == "Return":
            return "break"
        return None

    def crear_registros(self, parent):
        reg_frame = ttk.LabelFrame(parent, text="Registros (binario ↔ hex)", padding=10)
        reg_frame.pack(fill="x", anchor="nw", pady=(0, 5))

        ffam = self.prefs.get("editor", "font_family")
        fs = self._scaled_size(8)

        ttk.Label(reg_frame, text="", width=4).grid(row=0, column=0)
        ttk.Label(reg_frame, text="Binario", font=(ffam, fs)).grid(row=0, column=1, sticky="w", pady=(0, 2))
        ttk.Label(reg_frame, text="Hex", font=(ffam, fs)).grid(row=0, column=2, sticky="w", padx=(6, 0), pady=(0, 2))

        self.registers = {
            "PC": tk.StringVar(value="000000000000"),
            "ACC": tk.StringVar(value="000000000000"),
            "GPR": tk.StringVar(value="000000000000"),
            "F": tk.StringVar(value="0"),
            "M": tk.StringVar(value="000000000000"),
        }
        self.register_hex_vars = {}
        self._register_hex_entries = {}
        self._register_bin_entries = {}

        for i, (name, var) in enumerate(self.registers.items(), start=1):
            bits = 1 if name == "F" else 12
            ttk.Label(reg_frame, text=name, width=4).grid(row=i, column=0, sticky="w", pady=2)
            ent = ttk.Entry(reg_frame, textvariable=var, width=16, font=(ffam, self._scaled_size(9)))
            ent.grid(row=i, column=1, pady=2, sticky="w")
            self._register_bin_entries[name] = ent
            hx = tk.StringVar(value=_bin_a_hex_ui(var.get(), bits))
            self.register_hex_vars[name] = hx
            whex = 4 if bits == 1 else 6
            ent_h = ttk.Entry(reg_frame, textvariable=hx, width=whex, font=(ffam, self._scaled_size(9)))
            ent_h.grid(row=i, column=2, sticky="w", padx=(6, 0), pady=2)
            self._register_hex_entries[name] = ent_h

            def _mk_bin_trace(nm, b):
                def _on(*_a):
                    if self._suppress_reg_trace:
                        return
                    self.register_hex_vars[nm].set(_bin_a_hex_ui(self.registers[nm].get(), b))

                return _on

            var.trace_add("write", _mk_bin_trace(name, bits))

            ent_h.bind("<FocusOut>", lambda e, n=name, b=bits: self._reg_hex_field_commit(n, b, e))
            ent_h.bind("<Return>", lambda e, n=name, b=bits: self._reg_hex_field_commit(n, b, e))

        font_family = self.prefs.get("editor", "font_family")
        hint = (
            "Editá binario o hex; al salir del campo hex o pulsar Enter se sincroniza y normaliza (12 bits → 3 hex).\n"
            "Acepta prefijo 0x (ej. 0xA00). F: hex 0/1. "
            "PC=$20 → hex 020 o bin 000000100000.\n"
            "GPR(AD)→MAR: IR en GPR y dato en RAM en la dirección del campo AD."
        )
        self._registers_hint = ttk.Label(
            reg_frame,
            text=hint,
            justify="left",
            wraplength=260,
            font=(font_family, self._scaled_size(8)),
        )
        self._registers_hint.grid(row=len(self.registers) + 1, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def crear_memoria_editable(self, parent):
        frame = ttk.LabelFrame(parent, text="Memoria RAM", padding=8)
        frame.pack(fill="both", expand=True, pady=5)

        self.mem_vars_edit, self.mem_hex_edit = self.create_memory(frame, editable=True)

    # ---------------------------
    # 🧠 Editor de Código
    # ---------------------------
    def crear_editor_codigo(self):
        editor_frame = ttk.LabelFrame(self.main, text="Editor de Código", padding=6)
        editor_frame.grid(row=0, column=1, sticky="nsew")

        editor_frame.columnconfigure(1, weight=1)
        editor_frame.rowconfigure(0, weight=1)

        font_family = self.prefs.get("editor", "font_family")
        font_size_base = self.prefs.get("editor", "font_size")
        font_size = self._scaled_size(font_size_base, min_size=8)
        tooltip_size = self._scaled_size(max(8, font_size_base - 2), min_size=7)

        self._line_number_bg = "lightgray"

        self.line_numbers = tk.Text(editor_frame, width=4, padx=4, takefocus=0,
                                   border=0, background=self._line_number_bg,
                                   fg="#000000", state="disabled",
                                   font=(font_family, font_size))
        self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.code = tk.Text(editor_frame, font=(font_family, font_size), bg="#ffffff", fg="#000000",
                            insertbackground="#000000")
        self.code.grid(row=0, column=1, sticky="nsew")
        self.code.tag_configure("comentario", foreground="#6d6d6d", font=(font_family, font_size, "italic"))

        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=self._on_scroll)
        scrollbar.grid(row=0, column=2, sticky="ns")

        self.code.config(yscrollcommand=scrollbar.set)

        # Popup de autocompletado
        self.autocomplete_popup = tk.Toplevel(self.root)
        self.autocomplete_popup.withdraw()
        self.autocomplete_popup.overrideredirect(True)  # sin bordes de ventana
        self.autocomplete_popup.attributes("-topmost", True)

        self.autocomplete_list = tk.Listbox(
            self.autocomplete_popup,
            font=(font_family, font_size),
            height=6,
            selectbackground="#0078d7",
            selectforeground="white",
            bg="#f5f5f5",
            fg="#000000",
            bd=1,
            relief="solid"
        )
        self.autocomplete_list.pack(fill="both", expand=True)

        # Tooltip de descripción debajo del popup
        self.tooltip_var = tk.StringVar()
        self.tooltip_lbl = tk.Label(
            self.autocomplete_popup,
            textvariable=self.tooltip_var,
            font=(font_family, tooltip_size),
            bg="#ffffcc",
            fg="#000000",
            anchor="w",
            padx=4
        )
        self.tooltip_lbl.pack(fill="x")

        self.autocomplete_list.bind("<ButtonRelease-1>", self.aplicar_autocompletado)
        self.autocomplete_list.bind("<Return>", self.aplicar_autocompletado)

        self.code.bind("<KeyRelease>", self._on_key_release)
        self.code.bind("<<Modified>>", self._on_code_modified)
        self.code.bind("<Tab>", self._on_tab)
        self.code.bind("<Escape>", lambda e: self.cerrar_autocomplete())
        self.code.bind("<Down>", self._mover_seleccion)
        self.code.bind("<Up>", self._mover_seleccion)
        self.code.bind("<FocusOut>", lambda e: self.cerrar_autocomplete())

        self.actualizar_lineas()
        self.aplicar_tema(self._theme_mode)
        self._resaltar_comentarios()
        self._programar_actualizar_traza()

    # ---------------------------
    # 📈 Traza de microoperaciones (panel lateral)
    # ---------------------------
    def crear_panel_traza(self):
        font_family = self.prefs.get("editor", "font_family")
        mono_size = self._scaled_size(8, min_size=7)

        trace_frame = ttk.LabelFrame(self.main, text="Traza (tiempo real)", padding=4)
        trace_frame.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(8, 0))
        trace_frame.rowconfigure(1, weight=1)
        trace_frame.columnconfigure(0, weight=1)

        self._trace_notebook = ttk.Notebook(trace_frame)
        self._trace_notebook.grid(row=1, column=0, columnspan=2, sticky="nsew")

        tab_tabla = ttk.Frame(self._trace_notebook, padding=0)
        tab_tabla.columnconfigure(0, weight=1)
        tab_tabla.rowconfigure(0, weight=1)
        self._trace_notebook.add(tab_tabla, text="Tabla")

        opts = ttk.Frame(trace_frame)
        opts.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(opts, text="Vista:").pack(side="left", padx=(0, 4))
        self.trace_modo_var = tk.StringVar(value="Fetch + editor (estilo apuntes)")
        self._trace_modo_combo = ttk.Combobox(
            opts,
            textvariable=self.trace_modo_var,
            state="readonly",
            width=36,
            values=(
                "Solo editor (sin fetch)",
                "Fetch + editor (estilo apuntes)",
            ),
        )
        self._trace_modo_combo.pack(side="left", padx=(0, 8))
        self._trace_modo_combo.bind("<<ComboboxSelected>>", lambda e: self._programar_actualizar_traza())

        self.trace_mar_pc_dec_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts,
            text="MAR y PC en decimal",
            variable=self.trace_mar_pc_dec_var,
            command=self._programar_actualizar_traza,
        ).pack(side="left")
        self.trace_compact_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts,
            text="Solo valores que cambian",
            variable=self.trace_compact_var,
            command=self._programar_actualizar_traza,
        ).pack(side="left", padx=(8, 0))

        cols = (
            "ciclo",
            "micro",
            "PC",
            "MAR",
            "GPR",
            "GPR_OP",
            "GPR_AD",
            "OPR",
            "ACC",
            "F",
            "M",
        )
        headings = {
            "ciclo": "Ciclo",
            "micro": "Microoperación",
            "PC": "PC",
            "MAR": "MAR",
            "GPR": "GPR",
            "GPR_OP": "GPR(OP)",
            "GPR_AD": "GPR(AD)",
            "OPR": "OPR",
            "ACC": "ACC",
            "F": "F",
            "M": "M",
        }
        widths = {
            "ciclo": 44,
            "micro": 168,
            "PC": 40,
            "MAR": 44,
            "GPR": 44,
            "GPR_OP": 52,
            "GPR_AD": 52,
            "OPR": 44,
            "ACC": 44,
            "F": 28,
            "M": 44,
        }

        self._trace_tree = ttk.Treeview(
            tab_tabla,
            columns=cols,
            show="headings",
            height=22,
            selectmode="browse",
        )
        self._trace_tree.grid(row=0, column=0, sticky="nsew")
        self._trace_tree.column("#0", width=0, stretch=False)

        for c in cols:
            self._trace_tree.heading(c, text=headings[c])
            anchor = "w" if c == "micro" else "center"
            self._trace_tree.column(c, width=widths[c], anchor=anchor, stretch=False)

        ty = ttk.Scrollbar(tab_tabla, orient="vertical", command=self._trace_tree.yview)
        ty.grid(row=0, column=1, sticky="ns")
        self._trace_tree.configure(yscrollcommand=ty.set)

        tx = ttk.Scrollbar(tab_tabla, orient="horizontal", command=self._trace_tree.xview)
        tx.grid(row=1, column=0, sticky="ew")
        self._trace_tree.configure(xscrollcommand=tx.set)

        try:
            self._trace_tree.configure(font=(font_family, mono_size))
        except tk.TclError:
            pass

        mem_lf = ttk.LabelFrame(tab_tabla, text="Memoria usada en la traza", padding=4)
        mem_lf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        mem_lf.columnconfigure(0, weight=1)
        self._trace_mem_text = scrolledtext.ScrolledText(
            mem_lf,
            height=8,
            width=36,
            wrap="word",
            font=(font_family, mono_size),
            state="disabled",
        )
        self._trace_mem_text.grid(row=0, column=0, sticky="ew")
        self._habilitar_scroll_rueda_texto(self._trace_mem_text)

        tab_exp = ttk.Frame(self._trace_notebook, padding=4)
        self._trace_notebook.add(tab_exp, text="Qué hace")
        tab_exp.columnconfigure(0, weight=1)
        tab_exp.rowconfigure(1, weight=1)
        ttk.Label(
            tab_exp,
            text="Efecto de cada línea del editor (orden de arriba a abajo). Se actualiza con el código.",
            foreground="gray",
            font=(font_family, self._scaled_size(8)),
            wraplength=300,
        ).grid(row=0, column=0, sticky="w")
        self._trace_explicacion_text = scrolledtext.ScrolledText(
            tab_exp,
            height=22,
            width=40,
            wrap="word",
            font=(font_family, mono_size),
            state="disabled",
        )
        self._trace_explicacion_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self._habilitar_scroll_rueda_texto(self._trace_explicacion_text)
        self._habilitar_scroll_rueda_en_frame(tab_exp, self._trace_explicacion_text)

        tab_arch = ttk.Frame(self._trace_notebook, padding=4)
        self._trace_notebook.add(tab_arch, text="Arquitectura")
        tab_arch.columnconfigure(0, weight=1)
        tab_arch.rowconfigure(1, weight=1)

        controls_frame = ttk.Frame(tab_arch)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(2, weight=1)
        ttk.Button(controls_frame, text="Zoom -", command=lambda: self._ajustar_zoom_arquitectura(-1)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(controls_frame, text="100%", command=lambda: self._ajustar_zoom_arquitectura(0, reset=True)).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(controls_frame, text="Zoom +", command=lambda: self._ajustar_zoom_arquitectura(1)).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        canvas_frame = ttk.Frame(tab_arch)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        arch_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        arch_canvas.grid(row=0, column=0, sticky="nsew")

        arch_vscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=arch_canvas.yview)
        arch_vscroll.grid(row=0, column=1, sticky="ns")
        arch_hscroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=arch_canvas.xview)
        arch_hscroll.grid(row=1, column=0, sticky="ew")
        arch_canvas.configure(yscrollcommand=arch_vscroll.set, xscrollcommand=arch_hscroll.set)

        try:
            arch_path = os.path.join(_base_proyecto(), "images", "arq_basica.png")
            self._architecture_image_orig = tk.PhotoImage(file=arch_path)
            self._architecture_image_zoom = self._architecture_image_orig
            self._architecture_zoom_level = 1
            self._architecture_canvas = arch_canvas
            self._architecture_image_id = arch_canvas.create_image(0, 0, anchor="nw", image=self._architecture_image_zoom)
            self._architecture_canvas.config(scrollregion=(0, 0, self._architecture_image_zoom.width(), self._architecture_image_zoom.height()))
            arch_canvas.bind("<Configure>", lambda e: arch_canvas.configure(scrollregion=(0, 0, self._architecture_image_zoom.width(), self._architecture_image_zoom.height())))
            arch_canvas.bind("<Enter>", lambda e: arch_canvas.focus_set())
            arch_canvas.bind("<MouseWheel>", self._on_architecture_mouse_wheel)
            arch_canvas.bind("<Button-4>", self._on_architecture_mouse_wheel)
            arch_canvas.bind("<Button-5>", self._on_architecture_mouse_wheel)
        except tk.TclError:
            ttk.Label(
                tab_arch,
                text="No se pudo cargar la imagen de arquitectura.",
                foreground="gray",
                font=(font_family, self._scaled_size(9)),
            ).grid(row=0, column=0, sticky="nsew")

        self.trace_status_var = tk.StringVar(value="")
        ttk.Label(trace_frame, textvariable=self.trace_status_var, foreground="gray",
                  font=(font_family, self._scaled_size(8))).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._trace_last_pc_mar_dec: bool | None = None

    def _on_architecture_mouse_wheel(self, event):
        if not hasattr(self, '_architecture_canvas'):
            return "break"
        if event.delta:
            self._architecture_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self._architecture_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._architecture_canvas.yview_scroll(1, "units")
        return "break"

    def _ajustar_zoom_arquitectura(self, direction, reset=False):
        if not hasattr(self, '_architecture_image_orig'):
            return
        levels = [0.5, 1, 2, 3, 4]
        if reset:
            self._architecture_zoom_level = 1
        else:
            current = self._architecture_zoom_level
            idx = levels.index(current)
            new_idx = max(0, min(len(levels) - 1, idx + direction))
            self._architecture_zoom_level = levels[new_idx]

        zoom_factor = self._architecture_zoom_level
        if zoom_factor == 1:
            scaled = self._architecture_image_orig
        elif zoom_factor < 1:
            scaled = self._architecture_image_orig.subsample(2, 2)
        else:
            scaled = self._architecture_image_orig.zoom(int(zoom_factor), int(zoom_factor))

        self._architecture_image_zoom = scaled
        self._architecture_canvas.itemconfigure(self._architecture_image_id, image=self._architecture_image_zoom)
        self._architecture_canvas.configure(scrollregion=(0, 0, self._architecture_image_zoom.width(), self._architecture_image_zoom.height()))

    def _habilitar_scroll_rueda_texto(self, widget):
        """
        Con state=disabled, la rueda del mouse a veces no mueve el contenido (Windows).
        Enlaza explícitamente la rueda y los botones 4/5 (Linux).
        """
        def on_wheel(event):
            if event.delta:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def on_linux_up(_event):
            widget.yview_scroll(-1, "units")
            return "break"

        def on_linux_down(_event):
            widget.yview_scroll(1, "units")
            return "break"

        widget.bind("<MouseWheel>", on_wheel)
        widget.bind("<Button-4>", on_linux_up)
        widget.bind("<Button-5>", on_linux_down)
        try:
            widget.configure(takefocus=True)
        except tk.TclError:
            pass

    def _habilitar_scroll_rueda_en_frame(self, frame, text_widget):
        """Reenvía la rueda desde el frame (márgenes de la pestaña) al mismo Text."""

        def on_wheel(event):
            if event.delta:
                text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def on_up(_event):
            text_widget.yview_scroll(-1, "units")
            return "break"

        def on_down(_event):
            text_widget.yview_scroll(1, "units")
            return "break"

        frame.bind("<MouseWheel>", on_wheel)
        frame.bind("<Button-4>", on_up)
        frame.bind("<Button-5>", on_down)

    def _programar_actualizar_traza(self):
        if self._trace_after_id is not None:
            try:
                self.root.after_cancel(self._trace_after_id)
            except tk.TclError:
                pass
        self._trace_after_id = self.root.after(160, self.actualizar_traza_vista)

    def _programar_actualizar_inferencia(self):
        """Inferencia en tiempo casi real (mismo debounce que la traza)."""
        if self._infer_after_id is not None:
            try:
                self.root.after_cancel(self._infer_after_id)
            except tk.TclError:
                pass
        self._infer_after_id = self.root.after(160, self._ejecutar_inferencia_diferida)

    def _ejecutar_inferencia_diferida(self):
        self._infer_after_id = None
        self.actualizar_inferencia_vista(notificar_barra=False)

    def _ops_desde_editor(self) -> list:
        lineas = self.code.get("1.0", "end").strip().split("\n")
        ops = []
        for linea in lineas:
            linea = preprocesar_linea_microop(linea)
            if not linea:
                continue
            instr = parser.parse(linea)
            if instr:
                for t in instr:
                    if t is not None and t[0] is not None:
                        ops.append(t[0])
        return ops

    def actualizar_inferencia_vista(self, notificar_barra: bool = False):
        """
        Actualiza la etiqueta de instrucción inferida según el editor.
        notificar_barra: True solo al pulsar «Inferir instrucción» (mensaje en barra de estado).
        """
        if not hasattr(self, "instruccion_var") or self.instruccion_var is None:
            return
        ops = self._ops_desde_editor()
        if not ops:
            self.instruccion_var.set("Sin instrucciones para inferir")
            if notificar_barra:
                self.mostrar_estado("Sin instrucciones para inferir.", error=False)
            return

        resultado = Inferidor.inferir(ops)
        modo = Inferidor.clasificar_modo_direccionamiento(ops)
        self.instruccion_var.set(f"Instruccion: {resultado}  |  Modo: {modo}")
        if notificar_barra:
            self.mostrar_estado(f"Inferencia completada ({len(ops)} operaciones)", error=False)

    def actualizar_traza_vista(self):
        self._trace_after_id = None
        if self._trace_tree is None:
            return
        self.cargar_registros_desde_ui()
        self.cargar_memoria_desde_ui()
        texto = self.code.get("1.0", "end")
        modo = self.trace_modo_var.get()
        prefijo_fetch = modo.startswith("Fetch")
        mar_dec = self.trace_mar_pc_dec_var.get()
        if self._trace_last_pc_mar_dec != mar_dec:
            self._trace_last_pc_mar_dec = mar_dec
            suf = " (dec)" if mar_dec else ""
            self._trace_tree.heading("PC", text=f"PC{suf}")
            self._trace_tree.heading("MAR", text=f"MAR{suf}")

        filas, err, mem_info = simular_traza(
            texto,
            self.cpu,
            prefijo_fetch=prefijo_fetch,
            mar_pc_decimal=mar_dec,
            omitir_repetidos=self.trace_compact_var.get(),
        )
        if getattr(self, "_trace_mem_text", None) is not None:
            self._trace_mem_text.configure(state="normal")
            self._trace_mem_text.delete("1.0", "end")
            self._trace_mem_text.insert("1.0", mem_info)
            self._trace_mem_text.configure(state="disabled")
        for item in self._trace_tree.get_children():
            self._trace_tree.delete(item)
        for f in filas:
            self._trace_tree.insert(
                "",
                "end",
                values=(
                    f["ciclo"],
                    f["micro"],
                    f["PC"],
                    f["MAR"],
                    f["GPR"],
                    f["GPR_OP"],
                    f["GPR_AD"],
                    f["OPR"],
                    f["ACC"],
                    f["F"],
                    f["M"],
                ),
            )
        if err:
            self.trace_status_var.set(err)
        elif not filas:
            self.trace_status_var.set("Sin microoperaciones (escribí en el editor o revisá la sintaxis).")
        else:
            modo_txt = "fetch + código" if prefijo_fetch else "solo editor"
            dec_txt = " · MAR/PC decimal" if mar_dec else ""
            comp_txt = " · celdas compactas" if self.trace_compact_var.get() else " · tabla completa"
            self.trace_status_var.set(
                f"{len(filas)} μops · {modo_txt}{dec_txt}{comp_txt} · resto hex 12 bits"
            )

        if getattr(self, "_trace_explicacion_text", None) is not None:
            self._trace_explicacion_text.configure(state="normal")
            self._trace_explicacion_text.delete("1.0", "end")
            self._trace_explicacion_text.insert("1.0", texto_explicacion_codigo(texto))
            self._trace_explicacion_text.configure(state="disabled")

    def _on_code_modified(self, event=None):
        if self.code.edit_modified():
            self.code.edit_modified(False)
            self.actualizar_lineas()
            self._resaltar_comentarios()
            self._programar_actualizar_traza()
            self._programar_actualizar_inferencia()

    # ---------------------------
    # Instrucciones disponibles para autocompletado
    # ---------------------------
    INSTRUCCIONES = [
        ("ACC+1 -> ACC",     "Incrementa ACC en 1"),
        ("GPR+1 -> GPR",     "Incrementa GPR en 1"),
        ("ACC+GPR -> ACC",   "Suma ACC + GPR, guarda en ACC"),
        ("GPR+ACC -> ACC",   "Suma GPR + ACC, guarda en ACC"),
        ("ACC -> GPR",       "Copia ACC a GPR"),
        ("GPR -> ACC",       "Copia GPR a ACC"),
        ("GPR -> M",         "Copia GPR al registro M"),
        ("M -> GPR",         "Copia M al registro GPR"),
        ("ACC! -> ACC",      "NOT de ACC (complemento a 1)"),
        ("! ACC",            "NOT de ACC (complemento a 1)"),
        ("! F",              "NOT del flag F"),
        ("0 -> ACC",         "Pone ACC en 0"),
        ("0 -> F",           "Pone F en 0"),
        ("ROL F, ACC",       "Rota izquierda F y ACC"),
        ("ROR F, ACC",       "Rota derecha F y ACC"),
        ("GPR(AD) -> MAR",   "GPR[dirección] -> registro MAR"),
        ("PC -> MAR",        "Copia PC al registro MAR (fetch)"),
        ("PC+1 -> PC",       "Incrementa el Program Counter"),
        ("GPR(OP) -> OPR",   "GPR[operador] -> registro OPR"),
    ]

    def _on_key_release(self, event=None):
        self.actualizar_lineas()
        self._resaltar_comentarios()
        self._programar_actualizar_traza()
        self._programar_actualizar_inferencia()
        # No mostrar autocomplete con teclas de navegación o modificadores
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return",
                                       "Tab", "Escape", "BackSpace", "Delete",
                                       "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self.mostrar_autocomplete()

    def mostrar_autocomplete(self):
        # Obtener el texto de la línea actual hasta el cursor
        linea_actual = self.code.get("insert linestart", "insert")
        texto = linea_actual.lstrip()

        if len(texto) < 1:
            self.cerrar_autocomplete()
            return

        sugerencias = [
            (instr, desc) for instr, desc in self.INSTRUCCIONES
            if instr.lower().startswith(texto.lower())
        ]

        if not sugerencias:
            self.cerrar_autocomplete()
            return

        self.autocomplete_list.delete(0, "end")
        self._sugerencias_actuales = sugerencias
        for instr, _ in sugerencias:
            self.autocomplete_list.insert("end", instr)

        self.autocomplete_list.selection_set(0)
        self.tooltip_var.set(sugerencias[0][1])

        # Posicionar el popup debajo del cursor de texto
        bbox = self.code.bbox("insert")
        if not bbox:
            return
        x = self.code.winfo_rootx() + bbox[0]
        y = self.code.winfo_rooty() + bbox[1] + bbox[3]

        ancho = 280
        alto = min(len(sugerencias), 6) * 20 + 24
        self.autocomplete_popup.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.autocomplete_popup.deiconify()

    def cerrar_autocomplete(self):
        self.autocomplete_popup.withdraw()

    def aplicar_autocompletado(self, event=None):
        seleccion = self.autocomplete_list.curselection()
        if not seleccion:
            return
        instr, _ = self._sugerencias_actuales[seleccion[0]]
        # Reemplazar la línea actual completa con la instrucción seleccionada
        self.code.delete("insert linestart", "insert lineend")
        self.code.insert("insert linestart", instr)
        self._resaltar_comentarios()
        self.cerrar_autocomplete()
        self.code.focus_set()
        return "break"

    def _on_tab(self, event=None):
        if self.autocomplete_popup.winfo_viewable():
            return self.aplicar_autocompletado()
        # Tab normal: insertar espacios
        self.code.insert("insert", "    ")
        return "break"

    def _mover_seleccion(self, event=None):
        if not self.autocomplete_popup.winfo_viewable():
            return
        size = self.autocomplete_list.size()
        if size == 0:
            return
        cur = self.autocomplete_list.curselection()
        idx = cur[0] if cur else 0
        if event.keysym == "Down":
            idx = min(idx + 1, size - 1)
        elif event.keysym == "Up":
            idx = max(idx - 1, 0)
        self.autocomplete_list.selection_clear(0, "end")
        self.autocomplete_list.selection_set(idx)
        self.autocomplete_list.see(idx)
        if hasattr(self, "_sugerencias_actuales"):
            self.tooltip_var.set(self._sugerencias_actuales[idx][1])
        return "break"

    def actualizar_lineas(self, event=None):
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")

        line_count = int(self.code.index('end-1c').split('.')[0])

        for i in range(1, line_count + 1):
            self.line_numbers.insert("end", f"{i}\n")

        self.line_numbers.config(state="disabled")

    @staticmethod
    def _indice_inicio_comentario(linea: str) -> int:
        inicio = -1
        for marcador in (";", "//", "#"):
            idx = linea.find(marcador)
            if idx == -1:
                continue
            if inicio == -1 or idx < inicio:
                inicio = idx
        return inicio

    def _resaltar_comentarios(self):
        if not hasattr(self, "code") or self.code is None:
            return
        self.code.tag_remove("comentario", "1.0", "end")
        total_lineas = int(self.code.index("end-1c").split(".")[0])
        for n in range(1, total_lineas + 1):
            inicio = f"{n}.0"
            fin = f"{n}.end"
            texto = self.code.get(inicio, fin)
            idx = self._indice_inicio_comentario(texto)
            if idx < 0:
                continue
            self.code.tag_add("comentario", f"{n}.{idx}", fin)

    def _on_scroll(self, *args):
        self.code.yview(*args)
        self.line_numbers.yview(*args)

    # ---------------------------
    # 📊 Barra Inferior
    # ---------------------------
    def crear_barra_inferior(self):
        bottom = ttk.Frame(self.main)
        bottom.grid(row=1, column=1, columnspan=2, sticky="nsew", pady=(6, 0))

        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        self.crear_resultados(bottom)
        self.crear_memoria_visual(bottom)

        btn_frame = ttk.Frame(bottom)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        btn_frame.columnconfigure(2, weight=1)
        btn_frame.columnconfigure(3, weight=1)

        ejecutar_btn = ttk.Button(btn_frame, text="Ejecutar 1 instrucción", command=self.ejecutar_una)
        ejecutar_btn.grid(row=0, column=0, padx=4)

        reset_btn = ttk.Button(btn_frame, text="Reiniciar", command=self.reiniciar)
        reset_btn.grid(row=0, column=1, padx=4)

        inferir_btn = ttk.Button(btn_frame, text="Inferir instrucción", command=self.inferir_instruccion)
        inferir_btn.grid(row=0, column=2, padx=4)

        copiar_inst_btn = ttk.Button(
            btn_frame, text="Copiar instrucción", command=self.copiar_instruccion_inferida
        )
        copiar_inst_btn.grid(row=0, column=3, padx=4)

        font_family = self.prefs.get("editor", "font_family")

        self.estado_var = tk.StringVar(value="Listo.")
        self._status_label = ttk.Label(bottom, textvariable=self.estado_var, anchor="w",
                   foreground="gray", font=(font_family, self._scaled_size(9)))
        self._status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4)

        self.instruccion_var = tk.StringVar(value="")
        self._instruccion_label = ttk.Label(bottom, textvariable=self.instruccion_var, anchor="w",
                    font=(font_family, self._scaled_size(12), "bold"), foreground="blue")
        self._instruccion_label.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 4))

        # ── Panel generador: instrucción → microoperaciones ──────────
        gen_frame = ttk.LabelFrame(bottom, text="Generar microoperaciones", padding=6)
        gen_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))
        gen_frame.columnconfigure(0, weight=1)

        gen_input_frame = ttk.Frame(gen_frame)
        gen_input_frame.pack(fill="x")
        gen_input_frame.columnconfigure(0, weight=1)
        gen_input_frame.columnconfigure(1, weight=1)

        ttk.Label(gen_input_frame, text="Instrucción:").grid(row=0, column=0, sticky="w")
        ttk.Label(gen_input_frame, text="Modo dir.:").grid(row=0, column=1, sticky="w")

        self.gen_var = tk.StringVar()
        self._gen_entry = ttk.Entry(gen_input_frame, textvariable=self.gen_var,
                        font=(font_family, self._scaled_size(10)), width=32)
        self._gen_entry.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self._gen_entry.bind("<Return>", lambda e: self.generar_microops())

        self.gen_modo_var = tk.StringVar(value="Solo ejecución (sin fetch)")
        self._gen_modo_combo = ttk.Combobox(
            gen_input_frame,
            textvariable=self.gen_modo_var,
            state="readonly",
            width=34,
            values=(
                "Solo ejecución (sin fetch)",
                "Ciclo completo — implicado / inherente",
                "Ciclo completo — directo",
                "Ciclo completo — indirecto",
            ),
        )
        self._gen_modo_combo.grid(row=1, column=1, sticky="ew")

        gen_btn = ttk.Button(gen_input_frame, text="Generar", command=self.generar_microops)
        gen_btn.grid(row=1, column=2, padx=(4, 0))

        self._gen_hint_label = ttk.Label(
            gen_input_frame,
            text="Ej: ACC <- ACC - F  |  ACC <- ACC + 3M - 2F + 1  |  M <- M + ACC + 2  |  Modo + fetch",
            foreground="gray",
            font=(font_family, self._scaled_size(8)),
        )
        self._gen_hint_label.grid(row=2, column=0, columnspan=3, sticky="w")

        self.gen_resultado_var = tk.StringVar(value="")
        self._gen_result_label = ttk.Label(gen_frame, textvariable=self.gen_resultado_var,
                                           font=(font_family, self._scaled_size(9)), foreground="darkgreen",
                                           anchor="w", justify="left")
        self._gen_result_label.pack(fill="x", pady=(4, 0))

    def crear_resultados(self, parent):
        results = ttk.LabelFrame(parent, text="Resultados", padding=10)
        results.grid(row=0, column=0, sticky="nsew", padx=(0,5))

        self.result_labels = {}

        for name in ["PC", "ACC", "GPR", "M"]:
            lbl = ttk.Label(results, text=f"{name}: 000000000000")
            lbl.pack(anchor="w", pady=2)
            self.result_labels[name] = lbl

        self.flag = ttk.Label(results, text="F: 0")
        self.flag.pack(anchor="w")

    def crear_memoria_visual(self, parent):
        frame = ttk.LabelFrame(parent, text="Memoria RAM", padding=8)
        frame.grid(row=0, column=1, sticky="nsew", padx=(5,0))

        self.mem_vars_view, self.mem_hex_view = self.create_memory(frame, editable=False)

    # ---------------------------
    # 🧩 Memoria
    # ---------------------------
    def create_memory(self, parent, editable=False):
        canvas = tk.Canvas(parent, width=268)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        vars_list = []
        hex_list = []
        ff = self.prefs.get("editor", "font_family")
        fs = self._scaled_size(8)

        hdr = ttk.Frame(inner)
        hdr.pack(anchor="w")
        ttk.Label(hdr, text="Dir.", width=6, font=(ff, fs)).pack(side="left")
        ttk.Label(hdr, text="Binario", width=14, font=(ff, fs)).pack(side="left")
        ttk.Label(hdr, text="Hex", width=5, font=(ff, fs)).pack(side="left", padx=(4, 0))

        for i in range(256):
            var = tk.StringVar(value="000000000000")
            vars_list.append(var)
            hx = tk.StringVar(value="000")
            hex_list.append(hx)

            row = ttk.Frame(inner)
            row.pack(anchor="w")

            ttk.Label(row, text=f"{i:04X}", width=6).pack(side="left")

            if editable:

                def _mem_trace(idx):
                    def _on(*_a):
                        hex_list[idx].set(_bin_a_hex_ui(vars_list[idx].get(), 12))

                    return _on

                var.trace_add("write", _mem_trace(i))
                ttk.Entry(row, textvariable=var, width=14).pack(side="left")
            else:
                ttk.Label(row, textvariable=var, width=14).pack(side="left")

            ttk.Label(row, textvariable=hx, width=5, font=(ff, self._scaled_size(9))).pack(side="left", padx=(4, 0))

        return vars_list, hex_list

    # ---------------------------
    # 🔌 CONEXIÓN UI ↔ CPU
    # ---------------------------
    def cargar_memoria_desde_ui(self):
        for i, var in enumerate(self.mem_vars_edit):
            try:
                valor = int(var.get(), 2)
                self.cpu.RAM.escribir(i, valor)
            except:
                self.cpu.RAM.escribir(i, 0)

    def actualizar_memoria_ui(self):
        dump = self.cpu.RAM.dump()
        for i in range(len(dump)):
            self.mem_vars_view[i].set(dump[i])
            if hasattr(self, "mem_hex_view") and i < len(self.mem_hex_view):
                self.mem_hex_view[i].set(_bin_a_hex_ui(dump[i], 12))

    def _bitarray_desde_campo_bin(self, s: str, bits: int) -> BitArray:
        raw = "".join(c for c in (s or "") if c in "01")
        if bits == 1:
            bit = raw[-1] if raw else "0"
            return BitArray(bin=bit)
        raw = raw.zfill(bits)[-bits:]
        return BitArray(bin=raw)

    def cargar_registros_desde_ui(self):
        try:
            self.cpu.PC = self._bitarray_desde_campo_bin(self.registers["PC"].get(), 12)
        except (ValueError, TypeError):
            self.cpu.PC = BitArray(uint=0, length=12)
        try:
            self.cpu.ACC = self._bitarray_desde_campo_bin(self.registers["ACC"].get(), 12)
        except (ValueError, TypeError):
            self.cpu.ACC = BitArray(uint=0, length=12)
        try:
            self.cpu.GPR = self._bitarray_desde_campo_bin(self.registers["GPR"].get(), 12)
        except (ValueError, TypeError):
            self.cpu.GPR = BitArray(uint=0, length=12)
        try:
            self.cpu.F = self._bitarray_desde_campo_bin(self.registers["F"].get(), 1)
        except (ValueError, TypeError):
            self.cpu.F = BitArray(uint=0, length=1)
        try:
            self.cpu.M = self._bitarray_desde_campo_bin(self.registers["M"].get(), 12)
        except (ValueError, TypeError):
            self.cpu.M = BitArray(uint=0, length=12)

    def actualizar_registros_ui(self):
        self._suppress_reg_trace = True
        try:
            self.registers["PC"].set(self.cpu.PC.bin)
            self.register_hex_vars["PC"].set(f"{self.cpu.PC.uint & 0xFFF:03X}")
            self.registers["ACC"].set(self.cpu.ACC.bin)
            self.register_hex_vars["ACC"].set(f"{self.cpu.ACC.uint & 0xFFF:03X}")
            self.registers["GPR"].set(self.cpu.GPR.bin)
            self.register_hex_vars["GPR"].set(f"{self.cpu.GPR.uint & 0xFFF:03X}")
            self.registers["F"].set(self.cpu.F.bin)
            self.register_hex_vars["F"].set(_bin_a_hex_ui(self.cpu.F.bin, 1))
            self.registers["M"].set(self.cpu.M.bin)
            self.register_hex_vars["M"].set(f"{self.cpu.M.uint & 0xFFF:03X}")
        finally:
            self._suppress_reg_trace = False

        self.result_labels["PC"].config(text=f"PC: {self.cpu.PC.bin}")
        self.result_labels["ACC"].config(text=f"ACC: {self.cpu.ACC.bin}")
        self.result_labels["GPR"].config(text=f"GPR: {self.cpu.GPR.bin}")
        self.result_labels["M"].config(text=f"M: {self.cpu.M.bin}")
        self.flag.config(text=f"F: {self.cpu.F.bin}")

    # ---------------------------
    # ▶️ EJECUCIÓN
    # ---------------------------

    def ejecutar_una(self):
        if self.pc == 0:
            self.cargar_registros_desde_ui()
            self.cargar_memoria_desde_ui()

        lineas = self.code.get("1.0", "end").strip().split("\n")

        if self.pc >= len(lineas):
            self.mostrar_estado(f"Fin del programa — ACC={self.cpu.ACC.bin}", error=False)
            return

        linea = preprocesar_linea_microop(lineas[self.pc])

        if not linea:
            self.pc += 1
            return

        instr = parser.parse(linea)

        ops_linea = [t[0] for t in instr if t is not None and t[0] is not None]
        if not ops_linea:
            self.mostrar_estado(f"Línea {self.pc + 1}: error de sintaxis en '{linea}'", error=True)
            self.pc += 1
            return

        dispatch = {
            "INC_ACC":      self.cpu.INC_ACC,
            "INC_GPR":      self.cpu.INC_GPR,
            "NOT_ACC":      self.cpu.NOT_ACC,
            "NOT_F":        self.cpu.NOT_F,
            "ROL_F_ACC":    self.cpu.ROL_F_ACC,
            "ROR_F_ACC":    self.cpu.ROR_F_ACC,
            "SUM_ACC_GPR":  self.cpu.SUM_ACC_GPR,
            "ACC_TO_GPR":   self.cpu.ACC_TO_GPR,
            "GPR_TO_ACC":   self.cpu.GPR_TO_ACC,
            "ZERO_ACC":     self.cpu.ZERO_TO_ACC,
            "ZERO_F":       self.cpu.ZERO_TO_F,
            "GPR_AD_TO_MAR":self.cpu.GPR_AD_TO_MAR,
            "GPR_TO_M":     self.cpu.GPR_TO_M,
            "M_TO_GPR":     self.cpu.M_TO_GPR,
            "PC_TO_MAR":    self.cpu.PC_TO_MAR,
            "INC_PC":       self.cpu.INC_PC,
            "GPR_OP_TO_OPR":self.cpu.GPR_OP_TO_OPR,
        }

        for op in ops_linea:
            if op in dispatch:
                dispatch[op]()
            else:
                self.mostrar_estado(f"Línea {self.pc + 1}: instrucción no soportada '{op}'", error=True)
                self.pc += 1
                self.actualizar_registros_ui()
                self.actualizar_memoria_ui()
                return
        self.mostrar_estado(
            f"Línea {self.pc + 1}: {linea}  →  {' · '.join(ops_linea)}",
            error=False,
        )

        self.pc += 1
        self.actualizar_registros_ui()
        self.actualizar_memoria_ui()

    def mostrar_estado(self, mensaje, error=False):
        self.estado_var.set(mensaje)
        if not self._theme_colors:
            color = "red" if error else "green"
        else:
            color = self._theme_colors["error"] if error else self._theme_colors["success"]
        if self._status_label is not None:
            self._status_label.config(foreground=color)

    def abrir_preferencias(self):
        from preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self.root, self.prefs, self.on_preferences_changed)
        self.root.wait_window(dialog)

    def _set_theme_from_menu(self, mode):
        self.prefs.set("theme", "mode", mode)
        self.prefs.save()
        self.on_preferences_changed()

    def _adjust_zoom(self, step):
        current = self.prefs.get("ui", "zoom_percent")
        self.prefs.set("ui", "zoom_percent", current + step)
        self.prefs.save()
        self.on_preferences_changed()

    def _reset_zoom(self):
        self.prefs.set("ui", "zoom_percent", 100)
        self.prefs.save()
        self.on_preferences_changed()

    def on_preferences_changed(self):
        self._theme_mode = self.prefs.get("theme", "mode")
        self._aplicar_zoom_global(self.prefs.get("ui", "zoom_percent"))
        font_family = self.prefs.get("editor", "font_family")
        font_size_base = self.prefs.get("editor", "font_size")
        font_size = self._scaled_size(font_size_base, min_size=8)
        tooltip_size = self._scaled_size(max(8, font_size_base - 2), min_size=7)

        self.code.config(font=(font_family, font_size))
        self.code.tag_configure(
            "comentario",
            font=(font_family, font_size, "italic"),
            foreground=self._theme_colors.get("text_muted", "#6d6d6d"),
        )
        self.line_numbers.config(font=(font_family, font_size))
        self.autocomplete_list.config(font=(font_family, font_size))
        self.tooltip_lbl.config(font=(font_family, tooltip_size))

        if self._status_label is not None:
            self._status_label.config(font=(font_family, self._scaled_size(9)))
        if self._instruccion_label is not None:
            self._instruccion_label.config(font=(font_family, self._scaled_size(12), "bold"))
        if self._gen_entry is not None:
            self._gen_entry.config(font=(font_family, self._scaled_size(10)))
        if self._gen_hint_label is not None:
            self._gen_hint_label.config(font=(font_family, self._scaled_size(8)))
        if self._gen_result_label is not None:
            self._gen_result_label.config(font=(font_family, self._scaled_size(9)))
        if self._trace_tree is not None:
            try:
                self._trace_tree.configure(font=(font_family, self._scaled_size(8, min_size=7)))
            except tk.TclError:
                pass
        if getattr(self, "_trace_mem_text", None) is not None:
            try:
                self._trace_mem_text.configure(font=(font_family, self._scaled_size(8, min_size=7)))
            except tk.TclError:
                pass
        if getattr(self, "_trace_explicacion_text", None) is not None:
            try:
                self._trace_explicacion_text.configure(font=(font_family, self._scaled_size(8, min_size=7)))
            except tk.TclError:
                pass
        reg_font = (font_family, self._scaled_size(9))
        for ent in getattr(self, "_register_bin_entries", {}).values():
            try:
                ent.config(font=reg_font)
            except tk.TclError:
                pass
        for ent in getattr(self, "_register_hex_entries", {}).values():
            try:
                ent.config(font=reg_font)
            except tk.TclError:
                pass

        self.aplicar_tema(self._theme_mode)

    def aplicar_tema(self, mode):
        if mode == "dark":
            bg = "#1b1d22"
            panel_bg = "#252830"
            editor_bg = "#1e1e1e"
            editor_fg = "#d4d4d4"
            lines_bg = "#2f2f33"
            lines_fg = "#d4d4d4"
            popup_bg = "#252526"
            tooltip_bg = "#333333"
            tooltip_fg = "#f1f1f1"
            select_bg = "#0e639c"
            accent = "#3a8ee6"
            text_muted = "#9aa2ad"
            success = "#4caf50"
            error = "#ef5350"
        else:
            bg = "#f3f4f6"
            panel_bg = "#ffffff"
            editor_bg = "#ffffff"
            editor_fg = "#000000"
            lines_bg = "lightgray"
            lines_fg = "#000000"
            popup_bg = "#f5f5f5"
            tooltip_bg = "#ffffcc"
            tooltip_fg = "#000000"
            select_bg = "#0078d7"
            accent = "#005fb8"
            text_muted = "gray"
            success = "green"
            error = "red"

        self._theme_colors = {
            "bg": bg,
            "panel_bg": panel_bg,
            "editor_bg": editor_bg,
            "editor_fg": editor_fg,
            "lines_bg": lines_bg,
            "lines_fg": lines_fg,
            "popup_bg": popup_bg,
            "tooltip_bg": tooltip_bg,
            "tooltip_fg": tooltip_fg,
            "select_bg": select_bg,
            "accent": accent,
            "text_muted": text_muted,
            "success": success,
            "error": error,
        }

        self._aplicar_estilo_ttk()
        self._aplicar_tema_menus()
        self._aplicar_tema_widgets(self.main)
        self.root.configure(bg=bg)

        self.code.config(bg=editor_bg, fg=editor_fg, insertbackground=editor_fg)
        self.code.tag_configure("comentario", foreground=text_muted)
        self.line_numbers.config(background=lines_bg, fg=lines_fg)
        self.autocomplete_list.config(bg=popup_bg, fg=editor_fg, selectbackground=select_bg)
        self.tooltip_lbl.config(bg=tooltip_bg, fg=tooltip_fg)
        self.autocomplete_popup.config(bg=popup_bg)
        self._resaltar_comentarios()

        if getattr(self, "_trace_mem_text", None) is not None:
            self._trace_mem_text.configure(bg=editor_bg, fg=editor_fg, insertbackground=editor_fg)
        if getattr(self, "_trace_explicacion_text", None) is not None:
            self._trace_explicacion_text.configure(bg=editor_bg, fg=editor_fg, insertbackground=editor_fg)
        if self._instruccion_label is not None:
            self._instruccion_label.config(foreground=accent)
        if self._status_label is not None:
            self._status_label.config(foreground=text_muted)
        if getattr(self, "_registers_hint", None) is not None:
            self._registers_hint.configure(foreground=text_muted)

    def _aplicar_estilo_ttk(self):
        colors = self._theme_colors
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=colors["bg"], foreground=colors["editor_fg"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabelframe", background=colors["panel_bg"], bordercolor=colors["accent"])
        style.configure("TLabelframe.Label", background=colors["panel_bg"], foreground=colors["editor_fg"])
        style.configure("TLabel", background=colors["panel_bg"], foreground=colors["editor_fg"])
        style.configure("TButton", background=colors["panel_bg"], foreground=colors["editor_fg"], bordercolor=colors["accent"])
        style.map("TButton", background=[("active", colors["accent"]), ("pressed", colors["accent"])])
        style.configure("TEntry", fieldbackground=colors["editor_bg"], foreground=colors["editor_fg"])
        style.configure("TScrollbar", background=colors["panel_bg"], troughcolor=colors["bg"])
        style.configure(
            "Treeview",
            background=colors["editor_bg"],
            fieldbackground=colors["editor_bg"],
            foreground=colors["editor_fg"],
            rowheight=max(20, self._scaled_size(20, min_size=18)),
        )
        style.configure("Treeview.Heading", background=colors["panel_bg"], foreground=colors["editor_fg"])
        style.map("Treeview", background=[("selected", colors["select_bg"])])

    def _aplicar_tema_menus(self):
        colors = self._theme_colors
        self.root.option_add("*Menu.background", colors["panel_bg"])
        self.root.option_add("*Menu.foreground", colors["editor_fg"])
        self.root.option_add("*Menu.activeBackground", colors["accent"])
        self.root.option_add("*Menu.activeForeground", "#ffffff")

    def _aplicar_tema_widgets(self, widget):
        colors = self._theme_colors
        for child in widget.winfo_children():
            if isinstance(child, tk.Canvas):
                child.configure(bg=colors["panel_bg"], highlightthickness=0)
            elif isinstance(child, tk.Text):
                if child is self.code:
                    child.configure(bg=colors["editor_bg"], fg=colors["editor_fg"], insertbackground=colors["editor_fg"])
                elif child is self.line_numbers:
                    child.configure(bg=colors["lines_bg"], fg=colors["lines_fg"])
                else:
                    child.configure(bg=colors["editor_bg"], fg=colors["editor_fg"], insertbackground=colors["editor_fg"])
            elif isinstance(child, tk.Listbox):
                child.configure(bg=colors["popup_bg"], fg=colors["editor_fg"], selectbackground=colors["select_bg"])
            elif isinstance(child, tk.Label):
                child.configure(bg=colors["panel_bg"], fg=colors["editor_fg"])

            self._aplicar_tema_widgets(child)

    def mostrar_acerca_de(self):
        messagebox.showinfo(
            "Acerca de",
            "OC Help - Simulador CPU\n\nIncluye menu superior y preferencias de tema/fuente.",
        )

    def inferir_instruccion(self):
        self.actualizar_inferencia_vista(notificar_barra=True)

    def copiar_instruccion_inferida(self):
        """Copia al portapapeles solo el texto de la instrucción inferida (sin el modo)."""
        if not hasattr(self, "instruccion_var") or self.instruccion_var is None:
            return
        s = (self.instruccion_var.get() or "").strip()
        if not s or s.startswith("Sin instrucciones"):
            self.mostrar_estado("No hay instrucción inferida para copiar.", error=True)
            return
        prefijo = "Instruccion: "
        sep_modo = "  |  Modo:"
        if s.startswith(prefijo) and sep_modo in s:
            parte = s[len(prefijo) :].split(sep_modo, 1)[0].strip()
        else:
            parte = s
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(parte)
            self.root.update_idletasks()
        except tk.TclError:
            self.mostrar_estado("No se pudo copiar al portapapeles.", error=True)
            return
        self.mostrar_estado("Instrucción copiada al portapapeles.", error=False)

    def generar_microops(self):
        expresion = self.gen_var.get().strip()
        if not expresion:
            return
        sel = self.gen_modo_var.get()
        if sel.startswith("Ciclo completo"):
            if "implicado" in sel or "inherente" in sel:
                modo_arg = "implicado"
            elif "indirecto" in sel:
                modo_arg = "indirecto"
            else:
                modo_arg = "directo"
        else:
            modo_arg = None
        try:
            ops = generar(expresion, modo_arg)
            ok, detalle = Inferidor.verificar_equivalencia(expresion, ops)
            if not ok:
                raise ErrorGeneracion(
                    "La secuencia generada no cumple semánticamente la instrucción solicitada.\n"
                    f"{detalle}"
                )
            # Insertar en el editor
            self.code.delete("1.0", "end")
            self.code.insert("1.0", "\n".join(ops))
            self._resaltar_comentarios()
            self.actualizar_lineas()
            self.gen_resultado_var.set(f"Generadas {len(ops)} instrucciones  →  cargadas en el editor")
            self.mostrar_estado(f"Generadas {len(ops)} ops para: {expresion}", error=False)
            self._programar_actualizar_traza()
            self._programar_actualizar_inferencia()
        except ErrorGeneracion as e:
            self.gen_resultado_var.set(f"Error: {e}")
            self.mostrar_estado("Error al generar", error=True)

    def reiniciar(self):
        self.pc = 0
        self.cpu = VonNeuman()
        for name, var in self.registers.items():
            var.set("0" if name == "F" else "000000000000")
        for var in self.mem_vars_edit:
            var.set("000000000000")
        for var in self.mem_vars_view:
            var.set("000000000000")
        if hasattr(self, "mem_hex_view"):
            for hx in self.mem_hex_view:
                hx.set("000")
        self.actualizar_registros_ui()
        self.mostrar_estado("Reiniciado.", error=False)
        self._programar_actualizar_traza()
        self._programar_actualizar_inferencia()


def _base_proyecto():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ruta_logo():
    return os.path.join(_base_proyecto(), "images", "logo.png")


def _ruta_icono_app():
    return os.path.join(_base_proyecto(), "images", "LogoIconoGato.png")


def _cargar_icono_app():
    """
    Carga LogoIconoGato.png para barra de tareas y título (PNG, Tk 8.6+).
    Devuelve tk.PhotoImage o None.
    """
    try:
        ruta = _ruta_icono_app()
        if not os.path.isfile(ruta):
            return None
        img = tk.PhotoImage(file=ruta)
        wmax = 128
        while img.width() > wmax or img.height() > wmax:
            img = img.subsample(2, 2)
        return img
    except tk.TclError:
        return None


def _aplicar_icono_ventana(ventana, icono_foto, default=True):
    """Asocia el icono a la ventana; default=True aplica también a hijos (Toplevel)."""
    if icono_foto is None:
        return
    try:
        ventana.iconphoto(default, icono_foto)
        ventana._icono_app_photo = icono_foto
    except tk.TclError:
        pass


def mostrar_splash_y_luego(root, callback, icono_foto=None):
    """
    Muestra el logo sobre fondo blanco; al cerrar (clic o tiempo) ejecuta callback().
    """
    splash = tk.Toplevel(root)
    if icono_foto is not None:
        _aplicar_icono_ventana(splash, icono_foto, default=False)
    splash.overrideredirect(True)
    splash.configure(bg="white")
    splash.attributes("-topmost", True)

    img_ref = {"photo": None}
    hecho = {"ok": False}

    try:
        img_ref["photo"] = tk.PhotoImage(file=_ruta_logo())
        while img_ref["photo"].width() > 900:
            img_ref["photo"] = img_ref["photo"].subsample(2, 2)
        lbl = tk.Label(splash, image=img_ref["photo"], bg="white", bd=0)
    except tk.TclError:
        lbl = tk.Label(
            splash,
            text="DEVS PROJECT\nOC HELP",
            bg="white",
            fg="#1a237e",
            font=("Segoe UI", 22, "bold"),
            padx=48,
            pady=48,
        )

    lbl.pack()
    lbl.image = img_ref.get("photo")

    hint = tk.Label(
        splash,
        text="Clic o Enter para continuar",
        bg="white",
        fg="#888888",
        font=("Segoe UI", 9),
    )
    hint.pack(pady=(0, 12))

    splash.update_idletasks()
    w = splash.winfo_reqwidth()
    h = splash.winfo_reqheight()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    splash.geometry(f"+{x}+{y}")

    timer_id = {"id": None}

    def cerrar(_event=None):
        if hecho["ok"]:
            return
        hecho["ok"] = True
        if timer_id["id"] is not None:
            try:
                splash.after_cancel(timer_id["id"])
            except tk.TclError:
                pass
        try:
            splash.destroy()
        except tk.TclError:
            pass
        callback()

    splash.bind("<Button-1>", cerrar)
    splash.bind("<Return>", cerrar)
    splash.bind("<Escape>", cerrar)
    timer_id["id"] = splash.after(4000, cerrar)


# ---------------------------
# 🚀 MAIN
# ---------------------------
if __name__ == "__main__":
    root = tk.Tk()
    _icono_app = _cargar_icono_app()
    _aplicar_icono_ventana(root, _icono_app, default=True)
    root.withdraw()

    def iniciar_app():
        app = CPU_UI(root)
        root.deiconify()
        root.lift()
        root.focus_force()

    mostrar_splash_y_luego(root, iniciar_app, icono_foto=_icono_app)
    root.mainloop()