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

from src.logic.region_outline import build_region_outline_forest
from src.logic.structure_outline import build_segment_full_text_from_items
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class RegionCreationPopup(tk.Toplevel):
    """Popup for creating/editing saved region-based code segments."""

    CODE_MARKER_SELECTED = "●"
    CODE_MARKER_UNSELECTED = "○"
    BASE_SEGMENT_SIZE_BYTES = 4 * 1024

    def __init__(self, parent, controller, region_name=None, initial_items=None):
        super().__init__(parent)
        self.controller = controller
        self.original_region_name = region_name
        self.initial_items = list(initial_items or [])
        self.saved_region_name = None

        self._current_region_forest = []
        self._outline_file_entries = []
        self._region_node_by_key = {}
        self._selected_region_keys = []
        self._selected_list_index_to_key = []
        self._available_tree_item_to_key = {}
        self._file_info_by_path = {}
        self._current_file_index = 0
        self._is_code_expanded = False
        self._region_name_placeholder_text = "Nombre del segmento"
        self._region_name_placeholder_active = False

        self.region_name_var = tk.StringVar(value=region_name or "")
        self.region_summary_var = tk.StringVar(value="Cargando regiones...")
        self.available_search_var = tk.StringVar(value="")
        self.available_summary_var = tk.StringVar(value="")
        self.current_file_var = tk.StringVar(value="Vista previa del segmento")
        self.current_file_summary_var = tk.StringVar(value="")

        self.title("Editar Regiones" if region_name else "Crear Regiones")
        self.geometry(f"1360x720+{int((self.winfo_screenwidth() - 1360) / 2)}+{int((self.winfo_screenheight() - 720) / 2)}")
        self.minsize(1160, 620)
        self.configure(bg=Styles.COLOR_BG_MAIN)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._load_available_regions()
        if self.original_region_name:
            self.entry_region_name.focus_set()
        self.bind("<Escape>", self._on_escape_pressed)

    def _create_widgets(self):
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(14, 8))
        self.header_frame = header

        ttk.Label(
            header,
            text="Origen: regiones detectadas en todo el proyecto cargado",
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
        self.name_card = name_card

        top_actions = ttk.Frame(name_card, style="Main.TFrame")
        top_actions.grid(row=0, column=1, sticky="e", padx=12, pady=8)

        btn_cancel = ttk.Button(top_actions, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))
        attach_tooltip(btn_cancel, "Cerrar ventana sin guardar")

        btn_accept = ttk.Button(top_actions, text="Aceptar", style="Action.TButton", command=self._on_accept)
        btn_accept.pack(side="right")
        attach_tooltip(btn_accept, "Guardar el segmento construido con regiones")

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
        self.body_frame = body

        self.left_panel_label = ttk.Label(
            body,
            text="Vista previa del segmento de código resultante.",
            style="TLabel",
        )
        self.left_panel_label.grid(row=0, column=0, sticky="w", pady=(0, 8), padx=(0, 10))

        self.right_panel_label = ttk.Label(
            body,
            text="Lista de regiones disponibles y seleccionadas",
            style="TLabel",
        )
        self.right_panel_label.grid(row=0, column=1, sticky="w", pady=(0, 8))

        self._create_code_panel(body)
        self._create_region_lists(body)

        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=14, pady=(0, 14))
        self.footer_frame = footer

        ttk.Label(footer, textvariable=self.region_summary_var, style="TLabel").pack(side="left")

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
        nav_frame.columnconfigure(1, weight=1)
        self.code_nav_frame = nav_frame

        self.btn_prev_file = ttk.Button(
            nav_frame,
            text="<",
            style="ToolbarGroup.TButton",
            command=lambda: self._change_current_file(-1),
            width=3,
        )
        self.btn_prev_file.grid(row=0, column=0, sticky="w")
        attach_tooltip(self.btn_prev_file, "No disponible en la vista previa del segmento")

        file_labels = tk.Frame(nav_frame, bg=ARBITRARY_THEME["bg"], bd=0, highlightthickness=0)
        file_labels.grid(row=0, column=1, sticky="ew", padx=10)
        file_labels.columnconfigure(0, weight=1)

        tk.Label(
            file_labels,
            textvariable=self.current_file_var,
            bg=ARBITRARY_THEME["bg"],
            fg="#569cd6",
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        self.btn_next_file = ttk.Button(
            nav_frame,
            text=">",
            style="ToolbarGroup.TButton",
            command=lambda: self._change_current_file(1),
            width=3,
        )
        self.btn_next_file.grid(row=0, column=2, sticky="e")
        attach_tooltip(self.btn_next_file, "No disponible en la vista previa del segmento")

        self.btn_expand_code = ttk.Button(
            nav_frame,
            text="Expandir",
            style="ToolbarGroup.TButton",
            command=self._toggle_code_expand,
        )
        self.btn_expand_code.grid(row=0, column=3, sticky="e", padx=(8, 0))
        attach_tooltip(self.btn_expand_code, "Oculta el resto del popup y deja solo el código visible")
        self.btn_prev_file.grid_remove()
        self.btn_next_file.grid_remove()

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

    def _create_region_lists(self, parent):
        list_frame = tk.Frame(
            parent,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0,
        )
        list_frame.grid(row=1, column=1, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=5)
        list_frame.rowconfigure(2, weight=2)
        self.list_frame = list_frame

        search_entry = tk.Entry(
            list_frame,
            textvariable=self.available_search_var,
            font=(Styles.FONT_FAMILY, 12),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        Styles.strip_classic_widget_chrome(search_entry)
        search_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8), ipady=4)
        self.available_search_var.trace_add("write", self._on_available_search_change)

        compact_tree_style = "RegionsCompact.Treeview"
        style = ttk.Style(self)
        style.configure(compact_tree_style, rowheight=26)

        self.available_regions_tree = ttk.Treeview(
            list_frame,
            columns=("region",),
            show="headings",
            selectmode="extended",
            style=compact_tree_style,
            height=10,
        )
        self.available_regions_tree.heading("region", text="Región")
        self.available_regions_tree.column("region", anchor="w", width=Styles.scale_size(360))
        self.available_regions_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.available_regions_tree.bind("<Double-1>", self._on_add_regions)
        self.available_regions_tree.bind("<<TreeviewSelect>>", self._on_available_tree_select)
        self.available_regions_tree.tag_configure("compact", font=(Styles.FONT_FAMILY, 9))

        available_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.available_regions_tree.yview,
            style="Vertical.TScrollbar",
        )
        available_scroll.place(in_=self.available_regions_tree, relx=1.0, rely=0.0, relheight=1.0, x=0, y=0, anchor="ne")
        self.available_regions_tree.configure(yscrollcommand=available_scroll.set)

        selected_list_frame = tk.Frame(list_frame, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        selected_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        selected_list_frame.columnconfigure(0, weight=1)
        selected_list_frame.rowconfigure(0, weight=1)

        self.selected_regions_list = tk.Listbox(
            selected_list_frame,
            font=(Styles.FONT_FAMILY, 8),
            bg="#16233a",
            fg=Styles.COLOR_INPUT_FG,
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            activestyle="none"
        )
        Styles.strip_classic_widget_chrome(self.selected_regions_list)
        self.selected_regions_list.grid(row=0, column=0, sticky="nsew")
        self.selected_regions_list.bind("<Double-1>", self._on_remove_regions)
        self.selected_regions_list.bind("<<ListboxSelect>>", self._on_selected_list_select)

        selected_scroll = ttk.Scrollbar(
            selected_list_frame,
            orient="vertical",
            command=self.selected_regions_list.yview,
            style="Vertical.TScrollbar",
        )
        selected_scroll.grid(row=0, column=1, sticky="ns")
        self.selected_regions_list.configure(yscrollcommand=selected_scroll.set)

        bottom_actions = ttk.Frame(list_frame, style="Main.TFrame")
        bottom_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_actions.columnconfigure((0, 1), weight=1)
        ttk.Button(bottom_actions, text="Seleccionar todo", style="ToolbarGroup.TButton", command=self._select_all_regions).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(bottom_actions, text="Limpiar", style="ToolbarGroup.TButton", command=self._clear_region_selection).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _configure_code_text_tags(self):
        if arbitrary_configure_tags:
            arbitrary_configure_tags(self.code_text)
        self.code_text.tag_configure("code_default", foreground=ARBITRARY_THEME["fg"], font=ARBITRARY_FONT_CODE)
        self.code_text.tag_configure("code_hint", foreground=ARBITRARY_THEME["line_num_fg"], font=ARBITRARY_FONT_CODE)
        self.marker_text.tag_configure("marker_selected", foreground="#f44747", font=(ARBITRARY_FONT_CODE[0], ARBITRARY_FONT_CODE[1], "bold"))
        self.marker_text.tag_configure("marker_unselected", foreground="#6b7280", font=(ARBITRARY_FONT_CODE[0], ARBITRARY_FONT_CODE[1], "bold"))
        try:
            self.code_text.tag_lower("code_default")
        except Exception:
            pass

    def _load_available_regions(self):
        project_manager = getattr(self.controller, "project_manager", None)
        file_infos = list(project_manager.get_files()) if project_manager else []
        self._file_info_by_path = {item.get("path"): item for item in file_infos if item.get("path")}
        self._current_region_forest = build_region_outline_forest(file_infos)
        self._outline_file_entries = [entry for entry in self._current_region_forest if entry.get("items")]
        self._region_node_by_key = {}
        for file_entry in self._current_region_forest:
            for node in file_entry.get("items", []):
                self._region_node_by_key[node["key"]] = node

        initial_keys = []
        sorted_initial_items = sorted(
            [item for item in self.initial_items if isinstance(item, dict)],
            key=lambda entry: int(entry.get("order_index", 10 ** 9)) if str(entry.get("order_index", "")).strip() else 10 ** 9
        )
        for item in sorted_initial_items:
            key = item.get("key") if isinstance(item, dict) else None
            if key and key in self._region_node_by_key and key not in initial_keys:
                initial_keys.append(key)
        self._selected_region_keys = initial_keys

        self._refresh_selection_ui()

    def _set_current_file_index(self, preferred_key=None):
        if not self._outline_file_entries:
            self._current_file_index = 0
            return
        target_key = preferred_key or (self._selected_region_keys[0] if self._selected_region_keys else None)
        if target_key and target_key in self._region_node_by_key:
            target_path = self._region_node_by_key[target_key].get("file_path")
            for index, file_entry in enumerate(self._outline_file_entries):
                if file_entry.get("file_path") == target_path:
                    self._current_file_index = index
                    return
        self._current_file_index = 0

    def _get_current_file_entry(self):
        if not self._outline_file_entries:
            return None
        if self._current_file_index < 0 or self._current_file_index >= len(self._outline_file_entries):
            self._current_file_index = 0
        return self._outline_file_entries[self._current_file_index]

    def _change_current_file(self, step):
        return

    def _refresh_selection_ui(self):
        self._refresh_available_regions_tree()
        self._refresh_selected_regions_tree()
        self._refresh_region_summary()
        self._render_current_file_code()

    def _refresh_region_summary(self):
        available_count = len(self._region_node_by_key)
        selected_count = len(self._selected_region_keys)
        selected_size_bytes = self._calculate_selected_region_size_bytes()
        selected_size_kb = selected_size_bytes / 1024.0
        if available_count == 0:
            self.region_summary_var.set(f"0 regiones | {selected_size_kb:.1f} KB")
            self.available_summary_var.set("No hay bloques #region detectados.")
            return
        self.region_summary_var.set(f"{selected_count}/{available_count} regiones | {selected_size_kb:.1f} KB")
        self.available_summary_var.set(
            f"{len(self._available_tree_item_to_key)} regiones visibles en la búsqueda. {selected_count} seleccionadas."
        )

    def _calculate_selected_region_size_bytes(self):
        total_bytes = self.BASE_SEGMENT_SIZE_BYTES
        for key in self._selected_region_keys:
            node = self._region_node_by_key.get(key)
            if not node:
                continue
            file_info = self._file_info_by_path.get(node.get("file_path"), {})
            content = file_info.get("content", "")
            lines = content.split("\n")
            start_line = max(int(node.get("start_line", 1) or 1), 1)
            end_line = max(int(node.get("end_line", start_line) or start_line), start_line)
            snippet = "\n".join(lines[start_line - 1:end_line]).rstrip()
            total_bytes += len(snippet.encode("utf-8", errors="ignore"))
        return total_bytes

    def _iter_all_regions(self):
        for file_entry in self._current_region_forest:
            for node in file_entry.get("items", []):
                yield file_entry, node

    def _iter_selected_regions(self):
        for key in self._selected_region_keys:
            node = self._region_node_by_key.get(key)
            if not node:
                continue
            yield node

    def _refresh_available_regions_tree(self, *_args):
        query = self.available_search_var.get().strip().lower()
        self._available_tree_item_to_key = {}
        for item_id in self.available_regions_tree.get_children():
            self.available_regions_tree.delete(item_id)

        for index, (_file_entry, node) in enumerate(self._iter_all_regions()):
            haystack = f"{node.get('header', '')} {node.get('file_rel_path', '')}".lower()
            if query and query not in haystack:
                continue
            item_id = f"available:{index}"
            self._available_tree_item_to_key[item_id] = node["key"]
            values = (node.get("header", ""),)
            tags = ("compact", "selected") if node["key"] in self._selected_region_keys else ("compact",)
            self.available_regions_tree.insert("", "end", iid=item_id, values=values, tags=tags)

    def _refresh_selected_regions_tree(self):
        self._selected_list_index_to_key = []
        self.selected_regions_list.delete(0, "end")

        for node in self._iter_selected_regions():
            self._selected_list_index_to_key.append(node["key"])
            self.selected_regions_list.insert("end", node.get("header", ""))

    def _render_current_file_code(self):
        code_yview = self.code_text.yview()[0] if self.code_text.winfo_exists() else 0.0
        code_xview = self.code_text.xview()[0] if self.code_text.winfo_exists() else 0.0

        self.marker_text.configure(state="normal")
        self.line_numbers_text.configure(state="normal")
        self.code_text.configure(state="normal", cursor="xterm")
        self.marker_text.delete("1.0", "end")
        self.line_numbers_text.delete("1.0", "end")
        self.code_text.delete("1.0", "end")
        self.current_file_var.set("Vista previa del segmento resultante")
        self.current_file_summary_var.set("")

        items = self._build_region_items_payload()
        preview_text, copied_count = build_segment_full_text_from_items(
            list(self._file_info_by_path.values()),
            items,
        )

        if not self._region_node_by_key:
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert("1.0", "No se detectaron bloques #region en el proyecto cargado.", ("code_hint",))
            self.marker_text.configure(state="disabled")
            self.line_numbers_text.configure(state="disabled")
            self.code_text.configure(state="disabled")
            return

        if not items:
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert(
                "1.0",
                "Selecciona regiones de la lista de la derecha para construir el segmento resultante.",
                ("code_hint",),
            )
            self.marker_text.configure(state="disabled")
            self.line_numbers_text.configure(state="disabled")
            self.code_text.configure(state="disabled")
            return

        if not preview_text.strip():
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert("1.0", "No se pudo construir la vista previa del segmento.", ("code_hint",))
            self.marker_text.configure(state="disabled")
            self.line_numbers_text.configure(state="disabled")
            self.code_text.configure(state="disabled")
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

        self.marker_text.configure(state="disabled")
        self.line_numbers_text.configure(state="disabled")
        self.code_text.configure(state="disabled")
        self.marker_text.yview_moveto(code_yview)
        self.code_text.yview_moveto(code_yview)
        self.line_numbers_text.yview_moveto(code_yview)
        self.code_text.xview_moveto(code_xview)

    def _toggle_region_key(self, key):
        if key in self._selected_region_keys:
            self._selected_region_keys = [item for item in self._selected_region_keys if item != key]
        elif key in self._region_node_by_key:
            self._selected_region_keys.append(key)
        self._refresh_selection_ui()

    def _get_selected_available_keys(self):
        keys = []
        for item_id in self.available_regions_tree.selection():
            key = self._available_tree_item_to_key.get(item_id)
            if key:
                keys.append(key)
        return keys

    def _on_add_regions(self, event=None):
        changed = False
        for key in self._get_selected_available_keys():
            if key not in self._selected_region_keys:
                self._selected_region_keys.append(key)
                changed = True
        if changed:
            self._refresh_selection_ui()

    def _on_remove_regions(self, event=None):
        selected_indices = list(self.selected_regions_list.curselection())
        selected_keys = [
            self._selected_list_index_to_key[index]
            for index in selected_indices
            if 0 <= index < len(self._selected_list_index_to_key)
        ]
        if not selected_keys:
            return
        self._selected_region_keys = [key for key in self._selected_region_keys if key not in set(selected_keys)]
        self._refresh_selection_ui()

    def _select_all_regions(self):
        self._selected_region_keys = [node["key"] for _entry, node in self._iter_all_regions()]
        self._refresh_selection_ui()

    def _clear_region_selection(self):
        self._selected_region_keys = []
        self._refresh_selection_ui()

    def _on_available_search_change(self, *_args):
        self._refresh_selection_ui()

    def _on_available_tree_select(self, event=None):
        selection = self.available_regions_tree.selection()
        if not selection:
            return
        key = self._available_tree_item_to_key.get(selection[0])
        if key:
            self._focus_region(key)

    def _on_selected_list_select(self, event=None):
        selection = self.selected_regions_list.curselection()
        if not selection:
            return
        index = selection[0]
        key = self._selected_list_index_to_key[index] if 0 <= index < len(self._selected_list_index_to_key) else None
        if key:
            self._focus_region(key)

    def _focus_region(self, key):
        return

    def _build_region_items_payload(self):
        items = []
        for order_index, key in enumerate(self._selected_region_keys):
            node = self._region_node_by_key.get(key)
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

    def _get_region_name_value(self):
        if self._region_name_placeholder_active:
            return ""
        return self.region_name_var.get().strip()

    def _on_accept(self):
        region_name = self._get_region_name_value()
        if not region_name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el segmento.")
            return

        items = self._build_region_items_payload()
        if not items:
            messagebox.showwarning("Aviso", "Selecciona al menos una región para construir el segmento.")
            return

        try:
            if self.original_region_name:
                self.controller.region_segment_manager.rename_region_segment(
                    self.original_region_name,
                    region_name,
                    items,
                )
            else:
                self.controller.region_segment_manager.save_region_segment(
                    region_name,
                    items,
                )
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el segmento:\n{exc}")
            return

        self.saved_region_name = region_name
        self.destroy()

    def _on_code_yscroll(self, first, last):
        self.code_scrollbar.set(first, last)
        try:
            self.marker_text.yview_moveto(first)
            self.line_numbers_text.yview_moveto(first)
        except Exception:
            pass

    def _on_code_vertical_scroll(self, *args):
        self.marker_text.yview(*args)
        self.code_text.yview(*args)
        self.line_numbers_text.yview(*args)

    def _on_code_mousewheel(self, event):
        delta = -1 if getattr(event, "delta", 0) > 0 else 1 if getattr(event, "delta", 0) < 0 else 0
        if delta:
            self.marker_text.yview_scroll(delta, "units")
            self.code_text.yview_scroll(delta, "units")
            self.line_numbers_text.yview_scroll(delta, "units")
            return "break"
        return None

    def _on_code_mousewheel_linux_up(self, event):
        self.marker_text.yview_scroll(-1, "units")
        self.code_text.yview_scroll(-1, "units")
        self.line_numbers_text.yview_scroll(-1, "units")
        return "break"

    def _on_code_mousewheel_linux_down(self, event):
        self.marker_text.yview_scroll(1, "units")
        self.code_text.yview_scroll(1, "units")
        self.line_numbers_text.yview_scroll(1, "units")
        return "break"

    def _on_escape_pressed(self, event=None):
        if self._is_code_expanded:
            self._toggle_code_expand()
            return "break"
        return None

    def _toggle_code_expand(self):
        self._is_code_expanded = not self._is_code_expanded
        if self._is_code_expanded:
            self.header_frame.pack_forget()
            self.name_card.pack_forget()
            self.footer_frame.pack_forget()
            self.left_panel_label.grid_remove()
            self.right_panel_label.grid_remove()
            self.list_frame.grid_remove()
            self.body_frame.pack_configure(fill="both", expand=True, padx=0, pady=0)
            self.body_frame.columnconfigure(0, weight=1)
            self.body_frame.columnconfigure(1, weight=0)
            self.body_frame.rowconfigure(0, weight=1)
            self.body_frame.rowconfigure(1, weight=0)
            self.code_frame.grid_configure(column=0, row=0, rowspan=2, columnspan=2, padx=0, pady=0)
            self.btn_expand_code.configure(text="Contraer")
        else:
            self.header_frame.pack(fill="x", padx=14, pady=(14, 8), before=self.body_frame)
            self.name_card.pack(fill="x", padx=14, pady=(0, 10), before=self.body_frame)
            self.body_frame.pack_configure(fill="both", expand=True, padx=14, pady=(0, 10))
            self.body_frame.columnconfigure(0, weight=3)
            self.body_frame.columnconfigure(1, weight=2)
            self.left_panel_label.grid()
            self.right_panel_label.grid()
            self.list_frame.grid()
            self.code_frame.grid_configure(column=0, row=1, rowspan=1, columnspan=1, padx=(0, 10), pady=0)
            self.footer_frame.pack(fill="x", padx=14, pady=(0, 14))
            self.btn_expand_code.configure(text="Expandir")

        self.update_idletasks()
        self._render_current_file_code()
