import tkinter as tk
import tkinter.messagebox as messagebox
from tkinter import ttk

try:
    from src.addons.Arbitrary_sus import (
        FONT_CODE as ARBITRARY_FONT_CODE,
        THEME as ARBITRARY_THEME,
        configure_tags as arbitrary_configure_tags,
        highlight_syntax as arbitrary_highlight_syntax,
    )
except Exception:
    ARBITRARY_THEME = {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "cursor": "#aeafad",
        "select_bg": "#264f78",
        "line_num_fg": "#858585",
        "sidebar_bg": "#252526",
    }
    ARBITRARY_FONT_CODE = ("Menlo", 14)
    arbitrary_configure_tags = None
    arbitrary_highlight_syntax = None

from src.logic.region_outline import build_region_outline_forest, match_region_lines
from src.logic.structure_outline import build_segment_full_text_from_items
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class SmartRegionCreationPopup(tk.Toplevel):
    """Popup that builds a saved region segment from free-form region headers."""

    BASE_SEGMENT_SIZE_BYTES = 4 * 1024

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.saved_region_name = None

        self._region_name_placeholder_text = "Nombre del segmento"
        self._region_name_placeholder_active = False
        self._detector_placeholder_text = "Escribe un encabezado de region por linea"
        self._detector_placeholder_active = False
        self._current_region_forest = []
        self._region_nodes = []
        self._file_info_by_path = {}
        self._line_matches = []
        self._match_tree_item_to_line = {}
        self._is_code_expanded = False

        self.region_name_var = tk.StringVar(value="")
        self.match_summary_var = tk.StringVar(value="Cargando regiones...")
        self.current_file_var = tk.StringVar(value="Vista previa del segmento")

        self.title("Crear inteligente")
        self.geometry(f"1480x820+{int((self.winfo_screenwidth() - 1480) / 2)}+{int((self.winfo_screenheight() - 820) / 2)}")
        self.minsize(1220, 700)
        self.configure(bg=Styles.COLOR_BG_MAIN)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._load_available_regions()
        self.detector_text.focus_set()
        self.bind("<Escape>", self._on_escape_pressed)

    def _create_widgets(self):
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(14, 8))

        ttk.Label(
            header,
            text="Crear segmento inteligente desde encabezados de regiones detectadas",
            style="Header.TLabel",
        ).pack(side="left")

        name_card = tk.Frame(
            self,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0,
        )
        name_card.pack(fill="x", padx=14, pady=(0, 10))
        name_card.columnconfigure(0, weight=1)
        name_card.columnconfigure(1, weight=0)

        actions = ttk.Frame(name_card, style="Main.TFrame")
        actions.grid(row=0, column=1, sticky="e", padx=12, pady=8)

        btn_cancel = ttk.Button(actions, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))
        attach_tooltip(btn_cancel, "Cerrar ventana sin guardar")

        btn_accept = ttk.Button(actions, text="Aceptar", style="Action.TButton", command=self._on_accept)
        btn_accept.pack(side="right")
        attach_tooltip(btn_accept, "Guardar el segmento construido desde coincidencias inteligentes")

        self.entry_region_name = tk.Entry(
            name_card,
            textvariable=self.region_name_var,
            font=(Styles.FONT_FAMILY, 12),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        Styles.strip_classic_widget_chrome(self.entry_region_name)
        self.entry_region_name.grid(row=0, column=0, sticky="ew", padx=12, pady=8, ipady=4)
        self.entry_region_name.bind("<FocusIn>", self._on_region_name_focus_in)
        self.entry_region_name.bind("<FocusOut>", self._on_region_name_focus_out)
        self._show_region_name_placeholder()

        body = ttk.Frame(self, style="Main.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        ttk.Label(
            body,
            text="Vista previa del segmento de código resultante.",
            style="TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8), padx=(0, 10))

        ttk.Label(
            body,
            text="Detector inteligente de regiones.",
            style="TLabel",
        ).grid(row=0, column=1, sticky="w", pady=(0, 8))

        self._create_code_panel(body)
        self._create_detector_panel(body)

        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Label(footer, textvariable=self.match_summary_var, style="TLabel").pack(side="left")

    def _create_code_panel(self, parent):
        code_frame = tk.Frame(
            parent,
            bg=ARBITRARY_THEME["bg"],
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0,
        )
        code_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        code_frame.columnconfigure(0, weight=1)
        code_frame.rowconfigure(1, weight=1)
        self.code_frame = code_frame

        nav_frame = tk.Frame(code_frame, bg=ARBITRARY_THEME["bg"], bd=0, highlightthickness=0)
        nav_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        nav_frame.columnconfigure(0, weight=1)

        tk.Label(
            nav_frame,
            textvariable=self.current_file_var,
            bg=ARBITRARY_THEME["bg"],
            fg="#569cd6",
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        self.btn_expand_code = ttk.Button(
            nav_frame,
            text="Expandir",
            style="ToolbarGroup.TButton",
            command=self._toggle_code_expand,
        )
        self.btn_expand_code.grid(row=0, column=1, sticky="e", padx=(8, 0))
        attach_tooltip(self.btn_expand_code, "Oculta el resto del popup y deja solo el código visible")

        viewer_frame = tk.Frame(code_frame, bg=ARBITRARY_THEME["bg"], bd=0, highlightthickness=0)
        viewer_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        viewer_frame.columnconfigure(2, weight=1)
        viewer_frame.rowconfigure(0, weight=1)

        self.marker_text = tk.Text(
            viewer_frame,
            wrap="none",
            width=2,
            font=ARBITRARY_FONT_CODE,
            bg=ARBITRARY_THEME["sidebar_bg"],
            fg=ARBITRARY_THEME["line_num_fg"],
            bd=0,
            highlightthickness=0,
            relief="flat",
            padx=2,
            pady=8,
            takefocus=0,
            state="disabled",
            insertbackground=ARBITRARY_THEME["cursor"],
            selectbackground=ARBITRARY_THEME["select_bg"],
        )
        Styles.strip_classic_widget_chrome(self.marker_text)
        self.marker_text.grid(row=0, column=0, sticky="ns")

        self.line_numbers_text = tk.Text(
            viewer_frame,
            wrap="none",
            width=4,
            font=ARBITRARY_FONT_CODE,
            bg=ARBITRARY_THEME["sidebar_bg"],
            fg=ARBITRARY_THEME["line_num_fg"],
            bd=0,
            highlightthickness=0,
            relief="flat",
            padx=4,
            pady=8,
            takefocus=0,
            state="disabled",
            insertbackground=ARBITRARY_THEME["cursor"],
            selectbackground=ARBITRARY_THEME["select_bg"],
        )
        Styles.strip_classic_widget_chrome(self.line_numbers_text)
        self.line_numbers_text.grid(row=0, column=1, sticky="ns")

        self.code_text = tk.Text(
            viewer_frame,
            wrap="none",
            font=ARBITRARY_FONT_CODE,
            bg=ARBITRARY_THEME["bg"],
            fg=ARBITRARY_THEME["fg"],
            insertbackground=ARBITRARY_THEME["cursor"],
            selectbackground=ARBITRARY_THEME["select_bg"],
            selectforeground=ARBITRARY_THEME["fg"],
            bd=0,
            highlightthickness=0,
            relief="flat",
            padx=4,
            pady=8,
            state="disabled",
        )
        Styles.strip_classic_widget_chrome(self.code_text)
        self.code_text.grid(row=0, column=2, sticky="nsew")
        self._configure_code_text_tags()

        code_scroll = ttk.Scrollbar(
            viewer_frame,
            orient="vertical",
            command=self._on_code_vertical_scroll,
            style="Vertical.TScrollbar",
        )
        code_scroll.grid(row=0, column=3, sticky="ns")
        self.code_scrollbar = code_scroll
        self.code_text.configure(yscrollcommand=self._on_code_yscroll)

        code_xscroll = ttk.Scrollbar(
            code_frame,
            orient="horizontal",
            command=self.code_text.xview,
            style="Horizontal.TScrollbar",
        )
        code_xscroll.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.code_text.configure(xscrollcommand=code_xscroll.set)

        for widget in (self.marker_text, self.code_text, self.line_numbers_text):
            widget.bind("<MouseWheel>", self._on_code_mousewheel, add="+")
            widget.bind("<Button-4>", self._on_code_mousewheel_linux_up, add="+")
            widget.bind("<Button-5>", self._on_code_mousewheel_linux_down, add="+")

    def _create_detector_panel(self, parent):
        panel = tk.Frame(
            parent,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0,
        )
        panel.grid(row=1, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=3)
        panel.rowconfigure(3, weight=2)
        self.detector_panel = panel

        tk.Label(
            panel,
            text="Encabezados detectores (uno por línea)",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        detector_frame = tk.Frame(panel, bg="#1a2a3a", bd=0, highlightthickness=0)
        detector_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        detector_frame.columnconfigure(0, weight=1)
        detector_frame.rowconfigure(0, weight=1)

        self.detector_text = tk.Text(
            detector_frame,
            wrap="word",
            font=(Styles.FONT_FAMILY, 12),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            padx=10,
            pady=10,
            undo=True,
        )
        Styles.strip_classic_widget_chrome(self.detector_text)
        self.detector_text.grid(row=0, column=0, sticky="nsew")
        self.detector_text.bind("<KeyRelease>", self._on_detector_text_change)
        self.detector_text.bind("<FocusIn>", self._on_detector_focus_in)
        self.detector_text.bind("<FocusOut>", self._on_detector_focus_out)

        detector_scroll = ttk.Scrollbar(
            detector_frame,
            orient="vertical",
            command=self.detector_text.yview,
            style="Vertical.TScrollbar",
        )
        detector_scroll.grid(row=0, column=1, sticky="ns")
        self.detector_text.configure(yscrollcommand=detector_scroll.set)
        self._show_detector_placeholder()

        matches_label_row = tk.Frame(panel, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        matches_label_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        matches_label_row.columnconfigure(0, weight=1)

        tk.Label(
            matches_label_row,
            text="Regiones coincidentes",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ttk.Button(
            matches_label_row,
            text="Limpiar",
            style="ToolbarGroup.TButton",
            command=self._clear_detector_text,
        ).grid(row=0, column=1, sticky="e")

        compact_tree_style = "SmartRegionsCompact.Treeview"
        style = ttk.Style(self)
        style.configure(compact_tree_style, rowheight=26)

        self.matches_tree = ttk.Treeview(
            panel,
            columns=("linea", "region", "archivo", "score"),
            show="headings",
            selectmode="browse",
            style=compact_tree_style,
            height=10,
        )
        self.matches_tree.heading("linea", text="Línea")
        self.matches_tree.heading("region", text="Región")
        self.matches_tree.heading("archivo", text="Archivo")
        self.matches_tree.heading("score", text="Score")
        self.matches_tree.column("linea", anchor="center", width=Styles.scale_size(60), stretch=False)
        self.matches_tree.column("region", anchor="w", width=Styles.scale_size(230))
        self.matches_tree.column("archivo", anchor="w", width=Styles.scale_size(160))
        self.matches_tree.column("score", anchor="center", width=Styles.scale_size(70), stretch=False)
        self.matches_tree.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.matches_tree.tag_configure("matched", foreground=Styles.COLOR_FG_TEXT)
        self.matches_tree.tag_configure("unmatched", foreground="#ff8a8a")

        matches_scroll = ttk.Scrollbar(
            panel,
            orient="vertical",
            command=self.matches_tree.yview,
            style="Vertical.TScrollbar",
        )
        matches_scroll.place(in_=self.matches_tree, relx=1.0, rely=0.0, relheight=1.0, x=0, y=0, anchor="ne")
        self.matches_tree.configure(yscrollcommand=matches_scroll.set)

    def _configure_code_text_tags(self):
        if arbitrary_configure_tags:
            arbitrary_configure_tags(self.code_text)
        self.code_text.tag_configure("code_default", foreground=ARBITRARY_THEME["fg"], font=ARBITRARY_FONT_CODE)
        self.code_text.tag_configure("code_hint", foreground=ARBITRARY_THEME["line_num_fg"], font=ARBITRARY_FONT_CODE)
        try:
            self.code_text.tag_lower("code_default")
        except Exception:
            pass

    def _load_available_regions(self):
        project_manager = getattr(self.controller, "project_manager", None)
        file_infos = list(project_manager.get_files()) if project_manager else []
        self._file_info_by_path = {item.get("path"): item for item in file_infos if item.get("path")}
        self._current_region_forest = build_region_outline_forest(file_infos)
        self._region_nodes = []
        for file_entry in self._current_region_forest:
            self._region_nodes.extend(file_entry.get("items", []))
        self._refresh_matches()

    def _show_region_name_placeholder(self):
        if self.region_name_var.get().strip():
            self.entry_region_name.configure(fg=Styles.COLOR_INPUT_FG)
            self._region_name_placeholder_active = False
            return
        self.entry_region_name.delete(0, tk.END)
        self.entry_region_name.insert(0, self._region_name_placeholder_text)
        self.entry_region_name.configure(fg=Styles.COLOR_DIM)
        self._region_name_placeholder_active = True

    def _hide_region_name_placeholder(self):
        if not self._region_name_placeholder_active:
            return
        self.entry_region_name.delete(0, tk.END)
        self.entry_region_name.configure(fg=Styles.COLOR_INPUT_FG)
        self._region_name_placeholder_active = False

    def _on_region_name_focus_in(self, event=None):
        self._hide_region_name_placeholder()

    def _on_region_name_focus_out(self, event=None):
        if not self.entry_region_name.get().strip():
            self._show_region_name_placeholder()

    def _show_detector_placeholder(self):
        if self._get_detector_text(raw=True).strip():
            self.detector_text.configure(fg=Styles.COLOR_INPUT_FG)
            self._detector_placeholder_active = False
            return
        self.detector_text.delete("1.0", "end")
        self.detector_text.insert("1.0", self._detector_placeholder_text)
        self.detector_text.configure(fg=Styles.COLOR_DIM)
        self._detector_placeholder_active = True

    def _hide_detector_placeholder(self):
        if not self._detector_placeholder_active:
            return
        self.detector_text.delete("1.0", "end")
        self.detector_text.configure(fg=Styles.COLOR_INPUT_FG)
        self._detector_placeholder_active = False

    def _on_detector_focus_in(self, event=None):
        self._hide_detector_placeholder()

    def _on_detector_focus_out(self, event=None):
        if not self._get_detector_text(raw=True).strip():
            self._show_detector_placeholder()

    def _clear_detector_text(self):
        self._hide_detector_placeholder()
        self.detector_text.delete("1.0", "end")
        self._refresh_matches()
        self._show_detector_placeholder()

    def _get_region_name_value(self):
        if self._region_name_placeholder_active:
            return ""
        return self.region_name_var.get().strip()

    def _get_detector_text(self, raw=False):
        text = self.detector_text.get("1.0", "end-1c")
        if not raw and self._detector_placeholder_active:
            return ""
        return text

    def _build_matched_region_items_payload(self):
        items = []
        for order_index, match in enumerate(self._line_matches):
            node = match.get("match")
            if not node:
                continue
            items.append({
                "key": node["key"],
                "file_path": node["file_path"],
                "file_rel_path": node["file_rel_path"],
                "header": node.get("header", ""),
                "type": "region",
                "name": node.get("name", ""),
                "start_line": node.get("start_line", 1),
                "end_line": node.get("end_line", 1),
                "order_index": order_index,
            })
        return items

    def _on_detector_text_change(self, event=None):
        self._refresh_matches()

    def _refresh_matches(self):
        detector_text = self._get_detector_text()
        self._line_matches = match_region_lines(self._region_nodes, detector_text, limit_per_line=5)
        self._refresh_matches_tree()
        self._refresh_preview()
        self._refresh_summary()

    def _refresh_matches_tree(self):
        self._match_tree_item_to_line = {}
        for item_id in self.matches_tree.get_children():
            self.matches_tree.delete(item_id)

        for index, match in enumerate(self._line_matches):
            node = match.get("match")
            score_text = f"{match.get('score', 0.0) * 100:.0f}%"
            item_id = f"match:{index}"
            self._match_tree_item_to_line[item_id] = match.get("line_number", index + 1)
            if node:
                values = (
                    match.get("line_number", index + 1),
                    node.get("header", ""),
                    node.get("file_rel_path", ""),
                    score_text,
                )
                tags = ("matched",)
            else:
                values = (
                    match.get("line_number", index + 1),
                    "Sin coincidencia",
                    "",
                    "0%",
                )
                tags = ("unmatched",)
            self.matches_tree.insert("", "end", iid=item_id, values=values, tags=tags)

    def _refresh_preview(self):
        code_yview = self.code_text.yview()[0] if self.code_text.winfo_exists() else 0.0
        code_xview = self.code_text.xview()[0] if self.code_text.winfo_exists() else 0.0

        self.marker_text.configure(state="normal")
        self.line_numbers_text.configure(state="normal")
        self.code_text.configure(state="normal", cursor="xterm")
        self.marker_text.delete("1.0", "end")
        self.line_numbers_text.delete("1.0", "end")
        self.code_text.delete("1.0", "end")
        self.current_file_var.set("Vista previa del segmento resultante")

        items = self._build_matched_region_items_payload()
        preview_text, copied_count = build_segment_full_text_from_items(
            list(self._file_info_by_path.values()),
            items,
        )

        if not self._region_nodes:
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert("1.0", "No se detectaron bloques #region en el proyecto cargado.", ("code_hint",))
            self._lock_code_text(code_yview, code_xview)
            return

        if not self._line_matches:
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert(
                "1.0",
                "Escribe encabezados de region en el panel derecho para construir el segmento resultante.",
                ("code_hint",),
            )
            self._lock_code_text(code_yview, code_xview)
            return

        if not items:
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert(
                "1.0",
                "No se encontraron coincidencias suficientes para construir el segmento.",
                ("code_hint",),
            )
            self._lock_code_text(code_yview, code_xview)
            return

        if not preview_text.strip():
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert("1.0", "No se pudo construir la vista previa del segmento.", ("code_hint",))
            self._lock_code_text(code_yview, code_xview)
            return

        self.current_file_var.set(f"Segmento resultante ({copied_count} regiones)")
        lines = preview_text.split("\n") or [""]
        digits = max(len(str(len(lines))), 2)

        for line_number, line_text in enumerate(lines, start=1):
            if line_number > 1:
                self.marker_text.insert("end", "\n")
                self.line_numbers_text.insert("end", "\n")
                self.code_text.insert("end", "\n")

            self.marker_text.insert("end", " ")
            self.line_numbers_text.insert("end", f"{line_number:>{digits}}", ("code_hint",))
            self.code_text.insert("end", line_text, ("code_default",))

        if arbitrary_highlight_syntax:
            try:
                arbitrary_highlight_syntax(self.code_text)
            except Exception:
                pass

        self._lock_code_text(code_yview, code_xview)

    def _lock_code_text(self, code_yview, code_xview):
        self.marker_text.configure(state="disabled")
        self.line_numbers_text.configure(state="disabled")
        self.code_text.configure(state="disabled")
        self.marker_text.yview_moveto(code_yview)
        self.code_text.yview_moveto(code_yview)
        self.line_numbers_text.yview_moveto(code_yview)
        self.code_text.xview_moveto(code_xview)

    def _refresh_summary(self):
        total_regions = len(self._region_nodes)
        total_lines = len(self._line_matches)
        matched_items = self._build_matched_region_items_payload()
        matched_lines = len(matched_items)
        selected_size_bytes = self.BASE_SEGMENT_SIZE_BYTES
        preview_text, _copied_count = build_segment_full_text_from_items(
            list(self._file_info_by_path.values()),
            matched_items,
        )
        if preview_text.strip():
            selected_size_bytes += len(preview_text.encode("utf-8", errors="ignore"))
        selected_size_kb = selected_size_bytes / 1024.0
        self.match_summary_var.set(
            f"{matched_lines}/{total_lines} lineas emparejadas | {total_regions} regiones disponibles | {selected_size_kb:.1f} KB"
        )

    def _toggle_code_expand(self):
        self._is_code_expanded = not self._is_code_expanded
        if self._is_code_expanded:
            self.detector_panel.grid_remove()
            self.btn_expand_code.configure(text="Contraer")
        else:
            self.detector_panel.grid()
            self.btn_expand_code.configure(text="Expandir")

    def _on_accept(self):
        region_name = self._get_region_name_value()
        if not region_name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el segmento.")
            return

        items = self._build_matched_region_items_payload()
        if not items:
            messagebox.showwarning("Aviso", "Escribe encabezados que produzcan al menos una coincidencia.")
            return

        try:
            self.controller.region_segment_manager.save_region_segment(region_name, items)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el segmento:\n{exc}")
            return

        self.saved_region_name = region_name
        self.destroy()

    def _on_escape_pressed(self, event=None):
        self.destroy()
        return "break"

    def _on_code_vertical_scroll(self, *args):
        for widget in (self.marker_text, self.line_numbers_text, self.code_text):
            widget.yview(*args)

    def _on_code_yscroll(self, first, last):
        self.code_scrollbar.set(first, last)
        self.marker_text.yview_moveto(first)
        self.line_numbers_text.yview_moveto(first)

    def _on_code_mousewheel(self, event):
        delta = 0
        if getattr(event, "delta", 0):
            delta = -1 * int(event.delta / 120) if event.delta else 0
        if delta:
            for widget in (self.marker_text, self.line_numbers_text, self.code_text):
                widget.yview_scroll(delta, "units")
            return "break"
        return None

    def _on_code_mousewheel_linux_up(self, event):
        for widget in (self.marker_text, self.line_numbers_text, self.code_text):
            widget.yview_scroll(-1, "units")
        return "break"

    def _on_code_mousewheel_linux_down(self, event):
        for widget in (self.marker_text, self.line_numbers_text, self.code_text):
            widget.yview_scroll(1, "units")
        return "break"
