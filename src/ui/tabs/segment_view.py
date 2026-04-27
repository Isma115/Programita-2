import difflib
import re
import tkinter as tk
import tkinter.messagebox as messagebox
import unicodedata
from tkinter import ttk

from src.logic.structure_outline import (
    build_outline_forest,
    build_segment_full_text,
    get_outline_visual_role,
    get_selected_section_file_infos,
    get_structures_for_files,
)
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class SegmentView(ttk.Frame):
    """
    Segment editor based on code-section structures.
    """

    NO_SUBSECTION_VALUE = "__none__"
    DEFAULT_SIDEBAR_WIDTH = Styles.scale_size(340)
    MIN_SIDEBAR_WIDTH = Styles.scale_size(280)

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = parent.master.controller
        self._current_outline_forest = []
        self._tree_item_to_key = {}
        self._structure_tree_item_by_key = {}
        self._manual_checked_structure_keys = set()
        self._manual_unchecked_structure_keys = set()
        self._auto_checked_structure_keys = set()
        self._current_segment_name = None

        self.segment_name_var = tk.StringVar(value="")
        self.base_section_var = tk.StringVar(value="")
        self.base_subsection_var = tk.StringVar(value="")
        self.structure_search_var = tk.StringVar(value="")
        self.segment_summary_var = tk.StringVar(value="Sin segmento cargado")
        self.bulk_match_summary_var = tk.StringVar(
            value="Pega una cabecera por línea y usa el botón para aplicar las coincidencias."
        )
        self._responsive_after_id = None

        self._create_layout()
        self.refresh_segments()
        self.refresh_section_options()
        self._reload_available_structures()

    def _create_layout(self):
        self.paned_window = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            bg=Styles.COLOR_BG_MAIN,
            sashrelief="flat"
        )
        self.paned_window.pack(fill="both", expand=True)

        self.sidebar = ttk.Frame(self.paned_window, style="Sidebar.TFrame", width=self.DEFAULT_SIDEBAR_WIDTH)
        self.sidebar.grid_propagate(False)
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(1, weight=1)

        self.content = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(2, weight=1)

        self.paned_window.add(self.sidebar, minsize=self.MIN_SIDEBAR_WIDTH, stretch="never")
        self.paned_window.add(self.content, minsize=Styles.scale_size(620), stretch="always")

        self._create_sidebar()
        self._create_editor()
        self.after_idle(self._set_default_sidebar_width)
        self.bind("<Configure>", self._on_resize)

    def _set_default_sidebar_width(self):
        try:
            self.update_idletasks()
            total_width = self.paned_window.winfo_width()
            if total_width <= self.DEFAULT_SIDEBAR_WIDTH:
                return
            sidebar_width = min(max(self.MIN_SIDEBAR_WIDTH, int(total_width * 0.24)), self.DEFAULT_SIDEBAR_WIDTH)
            self.paned_window.sash_place(0, sidebar_width, 0)
        except Exception:
            pass

    def _on_resize(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self._responsive_after_id:
            self.after_cancel(self._responsive_after_id)
        self._responsive_after_id = self.after(50, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self._responsive_after_id = None
        total_width = max(self.winfo_width(), 1)
        summary_wrap = max(total_width - Styles.scale_size(420), Styles.scale_size(280))

        if hasattr(self, "summary_label"):
            self.summary_label.configure(wraplength=summary_wrap)

        if hasattr(self, "structure_tree"):
            type_width = Styles.scale_size(130 if total_width < 1200 else 150)
            self.structure_tree.column("kind", width=type_width, minwidth=Styles.scale_size(110), anchor="center")

    def _create_sidebar(self):
        header = ttk.Label(self.sidebar, text="Segmentos", style="Header.TLabel")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        list_frame = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.segment_list = ttk.Treeview(
            list_frame,
            columns=("name",),
            show="tree",
            selectmode="browse",
            style="Borderless.Treeview"
        )
        self.segment_list.grid(row=0, column=0, sticky="nsew")
        self.segment_list.bind("<<TreeviewSelect>>", self._on_segment_select)

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.segment_list.yview, style="Vertical.TScrollbar")
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.segment_list.configure(yscrollcommand=list_scroll.set)

        btn_row = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        btn_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)
        btn_row.rowconfigure(0, weight=1)
        btn_row.rowconfigure(1, weight=1)

        self.btn_new = ttk.Button(btn_row, text="Nuevo", style="ToolbarGroup.TButton", command=self._on_new_segment)
        self.btn_new.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_delete = ttk.Button(btn_row, text="Eliminar", style="ToolbarGroup.TButton", command=self._on_delete_segment)
        self.btn_delete.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.btn_copy = ttk.Button(btn_row, text="Copiar segmento", style="Action.TButton", command=self._on_copy_segment)
        self.btn_copy.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _create_editor(self):
        top_card = tk.Frame(
            self.content,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        top_card.grid(row=0, column=0, sticky="ew", padx=(10, 10), pady=(10, 0))
        top_card.columnconfigure(0, weight=1)
        top_card.columnconfigure(1, weight=1)
        top_card.columnconfigure(2, weight=0)

        name_field = self._create_form_field(top_card, "Nombre")
        name_field["field"].grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=(12, 8))
        self.entry_segment_name = tk.Entry(
            name_field["input_parent"],
            textvariable=self.segment_name_var,
            font=("Segoe UI", 13),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat"
        )
        Styles.strip_classic_widget_chrome(self.entry_segment_name)
        self.entry_segment_name.pack(fill="x", padx=1, pady=1, ipady=5)

        section_field = self._create_form_field(top_card, "Sección base")
        section_field["field"].grid(row=0, column=1, sticky="ew", padx=(8, 12), pady=(12, 8))
        self.cmb_section = ttk.Combobox(
            section_field["input_parent"],
            state="readonly",
            textvariable=self.base_section_var,
            font=("Segoe UI", 12),
            style="Borderless.TCombobox"
        )
        self.cmb_section.pack(fill="x", padx=1, pady=1)
        self.cmb_section.bind("<<ComboboxSelected>>", self._on_base_section_change)

        subsection_field = self._create_form_field(top_card, "Subsección")
        subsection_field["field"].grid(row=1, column=0, sticky="ew", padx=(12, 8), pady=(0, 12))
        self.cmb_subsection = ttk.Combobox(
            subsection_field["input_parent"],
            state="readonly",
            textvariable=self.base_subsection_var,
            font=("Segoe UI", 12),
            style="Borderless.TCombobox"
        )
        self.cmb_subsection.pack(fill="x", padx=1, pady=1)
        self.cmb_subsection.bind("<<ComboboxSelected>>", self._on_base_subsection_change)

        search_field = self._create_form_field(top_card, "Buscar estructura")
        search_field["field"].grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(0, 12))
        self.entry_structure_search = tk.Entry(
            search_field["input_parent"],
            textvariable=self.structure_search_var,
            font=("Segoe UI", 13),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat"
        )
        Styles.strip_classic_widget_chrome(self.entry_structure_search)
        self.entry_structure_search.pack(fill="x", padx=1, pady=1, ipady=5)
        self.structure_search_var.trace_add("write", self._on_structure_search_change)

        actions = ttk.Frame(top_card, style="Main.TFrame")
        actions.grid(row=1, column=2, sticky="e", padx=(8, 12), pady=(0, 12))

        self.btn_reload = ttk.Button(actions, text="Cargar estructuras", style="ToolbarGroup.TButton", command=self._reload_available_structures)
        self.btn_reload.pack(side="left", padx=(0, 8))
        self.btn_save = ttk.Button(actions, text="Guardar segmento", style="ToolbarGroup.TButton", command=self._on_save_segment)
        self.btn_save.pack(side="left")

        self.summary_label = ttk.Label(
            self.content,
            textvariable=self.segment_summary_var,
            style="TLabel",
            justify="left",
            anchor="w"
        )
        self.summary_label.grid(row=1, column=0, sticky="ew", padx=(10, 10), pady=(10, 8))

        body = ttk.Frame(self.content, style="Main.TFrame")
        body.grid(row=2, column=0, sticky="nsew", padx=(10, 10), pady=(0, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        ttk.Label(
            body,
            text="Marca las estructuras del segmento usando los checkboxes del árbol.",
            style="TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 8), padx=(0, 10))

        ttk.Label(
            body,
            text="Cabeceras para selección automática",
            style="TLabel"
        ).grid(row=0, column=1, sticky="w", pady=(0, 8))

        tree_frame = ttk.Frame(body, style="Main.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.structure_tree = ttk.Treeview(
            tree_frame,
            columns=("kind",),
            show="tree headings",
            selectmode="extended",
            style="Treeview"
        )
        self.structure_tree.heading("#0", text="Estructura")
        self.structure_tree.heading("kind", text="Tipo")
        self.structure_tree.column("#0", width=Styles.scale_size(780), minwidth=Styles.scale_size(420), anchor="w")
        self.structure_tree.column("kind", width=Styles.scale_size(150), minwidth=Styles.scale_size(110), anchor="center")
        self.structure_tree.grid(row=0, column=0, sticky="nsew")
        self._configure_structure_tree_tags()
        self.structure_tree.bind("<Button-1>", self._on_structure_tree_click, add="+")

        structure_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.structure_tree.yview, style="Vertical.TScrollbar")
        structure_scroll.grid(row=0, column=1, sticky="ns")
        self.structure_tree.configure(yscrollcommand=structure_scroll.set)

        bulk_frame = tk.Frame(
            body,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        bulk_frame.grid(row=1, column=1, sticky="nsew")
        bulk_frame.columnconfigure(0, weight=1)
        bulk_frame.rowconfigure(2, weight=1)

        bulk_hint = tk.Label(
            bulk_frame,
            text="Una estructura por línea. Usa el botón para marcar las coincidencias más similares.",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left"
        )
        bulk_hint.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        bulk_actions = tk.Frame(bulk_frame, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        bulk_actions.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        self.btn_apply_bulk_match = ttk.Button(
            bulk_actions,
            text="Aplicar selección",
            style="ToolbarGroup.TButton",
            command=self._on_apply_bulk_match
        )
        self.btn_apply_bulk_match.grid(row=0, column=0, sticky="w")

        self.btn_clear_bulk_match = ttk.Button(
            bulk_actions,
            text="Limpiar selección",
            style="ToolbarGroup.TButton",
            command=self._clear_structure_selection
        )
        self.btn_clear_bulk_match.grid(row=0, column=1, sticky="w", padx=(8, 0))

        bulk_text_frame = tk.Frame(bulk_frame, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        bulk_text_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        bulk_text_frame.columnconfigure(0, weight=1)
        bulk_text_frame.rowconfigure(0, weight=1)

        self.bulk_match_text = tk.Text(
            bulk_text_frame,
            wrap="word",
            height=12,
            font=("Consolas", 11),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            undo=True
        )
        Styles.strip_classic_widget_chrome(self.bulk_match_text)
        self.bulk_match_text.grid(row=0, column=0, sticky="nsew")

        bulk_scroll = ttk.Scrollbar(
            bulk_text_frame,
            orient="vertical",
            command=self.bulk_match_text.yview,
            style="Vertical.TScrollbar"
        )
        bulk_scroll.grid(row=0, column=1, sticky="ns")
        self.bulk_match_text.configure(yscrollcommand=bulk_scroll.set)

        self.bulk_match_status_label = ttk.Label(
            bulk_frame,
            textvariable=self.bulk_match_summary_var,
            style="TLabel",
            justify="left",
            anchor="w"
        )
        self.bulk_match_status_label.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

        footer = ttk.Frame(body, style="Main.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        btn_select_all = ttk.Button(footer, text="Seleccionar todo", style="ToolbarGroup.TButton", command=self._select_all_structures)
        btn_select_all.pack(side="left", padx=(0, 8))
        attach_tooltip(btn_select_all, "Selecciona todas las estructuras del árbol")

        btn_clear = ttk.Button(footer, text="Limpiar selección", style="ToolbarGroup.TButton", command=self._clear_structure_selection)
        btn_clear.pack(side="left")
        attach_tooltip(btn_clear, "Quita la selección actual")

    def _create_form_field(self, parent, label_text):
        field = tk.Frame(
            parent,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        field.columnconfigure(0, weight=1)

        label = tk.Label(
            field,
            text=label_text,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        )
        label.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        input_shell = tk.Frame(
            field,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        input_shell.grid(row=1, column=0, sticky="ew")
        input_shell.columnconfigure(0, weight=1)

        return {"field": field, "input_parent": input_shell}

    def refresh_segments(self):
        self.segment_list.delete(*self.segment_list.get_children())
        for segment_name in self.controller.segment_manager.get_segments():
            self.segment_list.insert("", "end", iid=f"segment:{segment_name}", text=segment_name)

    def refresh_section_options(self):
        sections = sorted(self.controller.section_manager.get_sections(), key=str.lower)
        self.cmb_section.configure(values=sections)
        if not sections:
            self.base_section_var.set("")
            self.cmb_subsection.configure(values=[])
            self.base_subsection_var.set("")
            return

        if self.base_section_var.get() not in sections:
            self.base_section_var.set(sections[0])
        self._refresh_subsection_options()

    def _refresh_subsection_options(self):
        section_name = self.base_section_var.get().strip()
        if not section_name:
            self.cmb_subsection.configure(values=[])
            self.base_subsection_var.set("")
            return

        subsections = sorted(self.controller.section_manager.get_subsections(section_name), key=str.lower)
        values = ["(Sin subsección)"] + subsections
        self.cmb_subsection.configure(values=values)
        current = self.base_subsection_var.get().strip()
        if current not in values:
            self.base_subsection_var.set("(Sin subsección)")

    def _on_base_section_change(self, event=None):
        self._clear_selection_sources(clear_bulk_text=False)
        self._refresh_subsection_options()
        self._reload_available_structures()

    def _on_base_subsection_change(self, event=None):
        self._clear_selection_sources(clear_bulk_text=False)
        self._reload_available_structures()

    def _on_structure_search_change(self, *args):
        self._populate_structure_tree(preserve_keys=self._get_selected_structure_keys())

    def _normalize_selected_subsection(self):
        value = self.base_subsection_var.get().strip()
        if not value or value == "(Sin subsección)":
            return None
        return value

    def _reload_available_structures(self, preserve_keys=None):
        section_name = self.base_section_var.get().strip()
        subsection_name = self._normalize_selected_subsection()
        self._current_outline_forest = []

        if preserve_keys is not None:
            self._manual_checked_structure_keys = set(preserve_keys)
            self._manual_unchecked_structure_keys.clear()

        if not section_name:
            self.structure_tree.delete(*self.structure_tree.get_children())
            self._auto_checked_structure_keys.clear()
            self.bulk_match_summary_var.set(
                "Pega una cabecera por línea y usa el botón para aplicar las coincidencias."
            )
            self.segment_summary_var.set("Selecciona una sección base para cargar estructuras.")
            return

        file_infos = get_selected_section_file_infos(self.controller, section_name, subsection_name)
        structures = get_structures_for_files(self.controller, file_infos)
        self._current_outline_forest = build_outline_forest(file_infos, structures)
        self._populate_structure_tree(preserve_keys=preserve_keys)

    def _populate_structure_tree(self, preserve_keys=None):
        self.structure_tree.delete(*self.structure_tree.get_children())
        self._tree_item_to_key = {}
        self._structure_tree_item_by_key = {}

        section_name = self.base_section_var.get().strip()
        subsection_name = self._normalize_selected_subsection()
        search_query = self.structure_search_var.get().strip().lower()

        visible_count = 0
        visible_files = 0
        for file_entry in self._current_outline_forest:
            filtered_roots = self._filter_structure_nodes(
                file_entry.get("roots", []),
                search_query,
                file_entry.get("file_rel_path", "")
            )
            if not filtered_roots:
                continue

            visible_files += 1
            file_iid = f"file:{file_entry['file_path']}"
            self.structure_tree.insert(
                "",
                "end",
                iid=file_iid,
                text=file_entry["file_rel_path"],
                values=("Archivo",),
                open=True,
                tags=("outline_role_file",)
            )

            for root in filtered_roots:
                visible_count += self._insert_structure_node(file_iid, root, file_entry["file_rel_path"])

        summary = f"{visible_count} estructuras disponibles en {section_name}"
        if subsection_name:
            summary += f" > {subsection_name}"
        if search_query:
            summary += f" | filtro: {visible_files} archivos, {visible_count} estructuras"
        self.segment_summary_var.set(summary)

        if preserve_keys is not None:
            self._restore_checked_structure_keys()

    def _filter_structure_nodes(self, nodes, query, file_rel_path):
        if not query:
            return list(nodes or [])

        filtered = []
        for node in nodes or []:
            child_matches = self._filter_structure_nodes(node.get("children", []), query, file_rel_path)
            haystack = " ".join((
                node.get("header", ""),
                node.get("name", ""),
                node.get("type", ""),
                file_rel_path or "",
            )).lower()
            if query in haystack or child_matches:
                clone = dict(node)
                clone["children"] = child_matches
                filtered.append(clone)
        return filtered

    def _configure_structure_tree_tags(self):
        self.structure_tree.tag_configure("outline_role_file", foreground=Styles.COLOR_CODE_FILE)
        self.structure_tree.tag_configure("outline_role_default", foreground=Styles.COLOR_FG_TEXT)
        self.structure_tree.tag_configure("outline_role_view", foreground=Styles.COLOR_CODE_VIEW)
        self.structure_tree.tag_configure("outline_role_backend", foreground=Styles.COLOR_CODE_BACKEND)

    def _get_outline_tree_tags(self, file_rel_path, node=None):
        role = get_outline_visual_role(file_rel_path, structure_node=node)
        return (f"outline_role_{role}",)

    def _insert_structure_node(self, parent_iid, node, file_rel_path):
        item_iid = f"struct:{node['key']}"
        type_label = self._format_structure_type_label(node.get("type", ""))
        self.structure_tree.insert(
            parent_iid,
            "end",
            iid=item_iid,
            text=self._format_tree_header(node),
            values=(type_label,),
            open=True,
            tags=self._get_outline_tree_tags(file_rel_path, node)
        )
        self._tree_item_to_key[item_iid] = node["key"]
        self._structure_tree_item_by_key[node["key"]] = item_iid

        count = 1
        for child in node.get("children", []):
            count += self._insert_structure_node(item_iid, child, file_rel_path)
        return count

    def _format_tree_header(self, node):
        header_text = " ".join((node.get("header", "") or "").split())
        prefix = "☑ " if node.get("key") in self._get_effective_checked_structure_keys() else "☐ "
        return f"{prefix}{header_text}"

    def _format_structure_type_label(self, structure_type):
        mapping = {
            "function": "Función",
            "method": "Método",
            "procedure": "Procedimiento",
            "class": "Clase",
            "interface": "Interfaz",
            "struct": "Struct",
            "enum": "Enum",
            "namespace": "Namespace",
            "module": "Módulo",
            "tag": "Tag",
        }
        normalized = (structure_type or "").strip().lower()
        if normalized in mapping:
            return mapping[normalized]
        return normalized.replace("_", " ").title() if normalized else "Estructura"

    def _select_all_structures(self):
        self._manual_checked_structure_keys.update(self._structure_tree_item_by_key.keys())
        self._manual_unchecked_structure_keys.clear()
        self._refresh_visible_checkboxes()
        self._autosave_segment_state()

    def _clear_structure_selection(self):
        self._clear_selection_sources(clear_bulk_text=False)
        self._refresh_visible_checkboxes()
        self._autosave_segment_state()

    def _get_selected_structure_keys(self):
        return sorted(self._get_effective_checked_structure_keys())

    def _restore_checked_structure_keys(self):
        self._refresh_visible_checkboxes()

    def _get_effective_checked_structure_keys(self):
        return (
            set(self._auto_checked_structure_keys)
            | set(self._manual_checked_structure_keys)
        ) - set(self._manual_unchecked_structure_keys)

    def _clear_selection_sources(self, clear_bulk_text=False):
        self._manual_checked_structure_keys.clear()
        self._manual_unchecked_structure_keys.clear()
        self._auto_checked_structure_keys.clear()
        if clear_bulk_text and hasattr(self, "bulk_match_text"):
            self._set_bulk_match_text("", trigger=False)
        self.bulk_match_summary_var.set(
            "Pega una cabecera por línea y usa el botón para aplicar las coincidencias."
        )

    def _autosave_segment_state(self):
        segment_name = self.segment_name_var.get().strip()
        section_name = self.base_section_var.get().strip()
        if not segment_name or not section_name:
            return False

        items = self._build_segment_items_payload()
        if not items:
            return False

        subsection_name = self._normalize_selected_subsection() or ""

        try:
            saved_name = self.controller.segment_manager.save_segment(
                segment_name,
                section_name,
                subsection_name,
                items
            )
        except Exception:
            return False

        self._current_segment_name = saved_name
        self.refresh_segments()
        try:
            self.segment_list.selection_set(f"segment:{saved_name}")
        except Exception:
            pass
        return True

    def _refresh_visible_checkboxes(self):
        checked_keys = self._get_effective_checked_structure_keys()
        for key, item_id in self._structure_tree_item_by_key.items():
            try:
                current_text = self.structure_tree.item(item_id, "text")
            except Exception:
                continue
            if current_text.startswith(("☐ ", "☑ ")):
                body = current_text[2:]
            else:
                body = current_text
            prefix = "☑ " if key in checked_keys else "☐ "
            self.structure_tree.item(item_id, text=f"{prefix}{body}")

    def _on_structure_tree_click(self, event):
        region = self.structure_tree.identify("region", event.x, event.y)
        if region not in {"tree", "cell"}:
            return

        item_id = self.structure_tree.identify_row(event.y)
        if not item_id or not item_id.startswith("struct:"):
            return

        element = self.structure_tree.identify("element", event.x, event.y)
        if element == "Treeitem.indicator":
            return

        key = self._tree_item_to_key.get(item_id)
        if not key:
            return

        if key in self._get_effective_checked_structure_keys():
            self._manual_checked_structure_keys.discard(key)
            self._manual_unchecked_structure_keys.add(key)
        else:
            self._manual_unchecked_structure_keys.discard(key)
            self._manual_checked_structure_keys.add(key)

        self._refresh_visible_checkboxes()
        self._autosave_segment_state()
        return "break"

    def _set_bulk_match_text(self, text, trigger=True):
        if not hasattr(self, "bulk_match_text"):
            return
        self.bulk_match_text.delete("1.0", "end")
        if text:
            self.bulk_match_text.insert("1.0", text)
        self.bulk_match_text.edit_modified(False)
        if trigger:
            self._apply_bulk_structure_matching()

    def _on_apply_bulk_match(self):
        self._apply_bulk_structure_matching()

    def _apply_bulk_structure_matching(self, autosave=True):
        raw_lines = self._get_bulk_match_lines()
        if not raw_lines:
            self._auto_checked_structure_keys.clear()
            self.bulk_match_summary_var.set(
                "Escribe al menos una cabecera y pulsa 'Aplicar selección'."
            )
            self._refresh_visible_checkboxes()
            if autosave:
                self._autosave_segment_state()
            return

        self._manual_unchecked_structure_keys.clear()
        matched_keys = set()
        matched_lines = 0
        unmatched_lines = []

        for line in raw_lines:
            best_matches = self._find_best_matching_structure_keys(line)
            if best_matches:
                matched_lines += 1
                matched_keys.update(best_matches)
            else:
                unmatched_lines.append(line)

        self._auto_checked_structure_keys = matched_keys
        total_matches = len(matched_keys)
        summary = f"{matched_lines}/{len(raw_lines)} líneas con coincidencias automáticas. {total_matches} estructuras marcadas."
        if unmatched_lines:
            summary += f" Sin coincidencia: {', '.join(unmatched_lines[:2])}"
            if len(unmatched_lines) > 2:
                summary += "..."
        self.bulk_match_summary_var.set(summary)
        self._refresh_visible_checkboxes()
        if autosave:
            self._autosave_segment_state()

    def _get_bulk_match_lines(self):
        if not hasattr(self, "bulk_match_text"):
            return []
        raw_text = self.bulk_match_text.get("1.0", "end-1c")
        return [line.strip() for line in raw_text.splitlines() if line.strip()]

    def _find_best_matching_structure_keys(self, query_line):
        query_norm = self._normalize_match_text(query_line)
        query_compact = self._compact_match_text(query_line)
        query_tokens = self._tokenize_match_text(query_line)
        if not query_norm and not query_compact:
            return []

        scored_matches = []
        for file_entry in self._current_outline_forest:
            for node in file_entry.get("items", []):
                score = self._score_structure_similarity(node, query_norm, query_compact, query_tokens)
                if score <= 0:
                    continue
                scored_matches.append((score, node.get("key")))

        if not scored_matches:
            return []

        scored_matches.sort(key=lambda item: item[0], reverse=True)
        best_score = scored_matches[0][0]
        minimum_score = 0.58
        if best_score < minimum_score:
            return []

        tolerance = 0.015 if best_score >= 0.95 else 0.03 if best_score >= 0.78 else 0.045
        selected_keys = []
        for score, key in scored_matches:
            if best_score - score > tolerance:
                break
            selected_keys.append(key)
        return selected_keys

    def _score_structure_similarity(self, node, query_norm, query_compact, query_tokens):
        candidates = [
            node.get("header", ""),
            node.get("name", ""),
        ]
        best_score = 0.0
        for candidate in candidates:
            score = self._score_text_similarity(query_norm, query_compact, query_tokens, candidate)
            if score > best_score:
                best_score = score
        return best_score

    def _score_text_similarity(self, query_norm, query_compact, query_tokens, candidate_text):
        candidate_norm = self._normalize_match_text(candidate_text)
        candidate_compact = self._compact_match_text(candidate_text)
        candidate_tokens = self._tokenize_match_text(candidate_text)

        if not candidate_norm and not candidate_compact:
            return 0.0

        if query_norm and candidate_norm and query_norm == candidate_norm:
            return 1.0
        if query_compact and candidate_compact and query_compact == candidate_compact:
            return 0.99

        best_score = 0.0
        if query_norm and candidate_norm and (query_norm in candidate_norm or candidate_norm in query_norm):
            coverage = min(len(query_compact), len(candidate_compact)) / max(len(query_compact), len(candidate_compact), 1)
            best_score = max(best_score, 0.86 + (coverage * 0.1))

        if query_tokens and candidate_tokens:
            overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), len(candidate_tokens), 1)
            if query_tokens.issubset(candidate_tokens):
                best_score = max(best_score, 0.9)
            best_score = max(best_score, overlap * 0.8)

        if query_norm and candidate_norm:
            seq_ratio = difflib.SequenceMatcher(None, query_norm, candidate_norm).ratio()
            best_score = max(best_score, seq_ratio * 0.84)

        if query_compact and candidate_compact:
            compact_ratio = difflib.SequenceMatcher(None, query_compact, candidate_compact).ratio()
            best_score = max(best_score, compact_ratio * 0.9)

        return min(best_score, 0.995)

    def _normalize_match_text(self, text):
        normalized = unicodedata.normalize("NFKD", (text or "").strip().lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("_", " ")
        normalized = re.sub(r"[^\w<>/]+", " ", normalized)
        return " ".join(normalized.split())

    def _compact_match_text(self, text):
        normalized = self._normalize_match_text(text)
        return re.sub(r"[^a-z0-9]+", "", normalized)

    def _tokenize_match_text(self, text):
        normalized = self._normalize_match_text(text)
        return {token for token in normalized.split() if token}

    def _build_segment_items_payload(self):
        selected_keys = set(self._get_selected_structure_keys())
        if not selected_keys:
            return []

        items = []
        for file_entry in self._current_outline_forest:
            for node in file_entry.get("items", []):
                if node["key"] not in selected_keys:
                    continue
                items.append({
                    "key": node["key"],
                    "file_path": file_entry["file_path"],
                    "file_rel_path": file_entry["file_rel_path"],
                    "header": node.get("header", ""),
                    "type": node.get("type", ""),
                    "name": node.get("name", ""),
                    "start_line": node.get("start_line", 1),
                    "end_line": node.get("end_line", 1),
                })
        return items

    def _on_save_segment(self):
        segment_name = self.segment_name_var.get().strip()
        if not segment_name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el segmento.")
            return

        section_name = self.base_section_var.get().strip()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección base.")
            return

        items = self._build_segment_items_payload()
        if not items:
            messagebox.showwarning("Aviso", "Selecciona al menos una estructura.")
            return

        subsection_name = self._normalize_selected_subsection() or ""

        try:
            saved_name = self.controller.segment_manager.save_segment(
                segment_name,
                section_name,
                subsection_name,
                items
            )
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el segmento:\n{exc}")
            return

        self._current_segment_name = saved_name
        self.refresh_segments()
        self.segment_list.selection_set(f"segment:{saved_name}")
        self.segment_summary_var.set(f"Segmento '{saved_name}' guardado con {len(items)} estructuras.")

    def _on_new_segment(self):
        self._current_segment_name = None
        self._clear_selection_sources(clear_bulk_text=False)
        self.segment_name_var.set("")
        self.refresh_section_options()
        self._refresh_visible_checkboxes()
        self._reload_available_structures()
        self.segment_summary_var.set("Nuevo segmento listo para editar.")

    def _on_delete_segment(self):
        selected = self.segment_list.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona un segmento primero.")
            return

        segment_name = selected[0].split("segment:", 1)[-1]
        if not messagebox.askyesno("Eliminar segmento", f"¿Quieres eliminar el segmento '{segment_name}'?"):
            return

        self.controller.segment_manager.delete_segment(segment_name)
        self._on_new_segment()
        self.refresh_segments()

    def _on_segment_select(self, event=None):
        selected = self.segment_list.selection()
        if not selected:
            return

        segment_name = selected[0].split("segment:", 1)[-1]
        segment = self.controller.segment_manager.get_segment(segment_name)
        if not segment:
            return

        self._current_segment_name = segment_name
        self.segment_name_var.set(segment_name)
        self.refresh_section_options()

        source_section = segment.get("source_section", "")
        source_subsection = segment.get("source_subsection", "")
        if source_section:
            self.base_section_var.set(source_section)
        self._refresh_subsection_options()
        self.base_subsection_var.set(source_subsection if source_subsection else "(Sin subsección)")

        self._clear_selection_sources(clear_bulk_text=False)
        preserve_keys = [item.get("key") for item in segment.get("items", []) if item.get("key")]
        self._reload_available_structures(preserve_keys=preserve_keys)
        self.segment_summary_var.set(
            f"Segmento '{segment_name}' cargado con {len(preserve_keys)} estructuras seleccionadas."
        )

    def _on_copy_segment(self):
        segment_name = self.segment_name_var.get().strip()
        section_name = self.base_section_var.get().strip()
        subsection_name = self._normalize_selected_subsection()
        selected_keys = self._get_selected_structure_keys()

        if not segment_name:
            messagebox.showwarning("Aviso", "Carga o crea un segmento antes de copiar.")
            return
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección base.")
            return
        if not selected_keys:
            messagebox.showwarning("Aviso", "Selecciona al menos una estructura para copiar.")
            return

        file_infos = get_selected_section_file_infos(self.controller, section_name, subsection_name)
        structures = get_structures_for_files(self.controller, file_infos)
        clipboard_text, copied_count = build_segment_full_text(file_infos, structures, selected_keys)
        if not clipboard_text.strip():
            messagebox.showinfo("Copiar segmento", "No se pudo construir el contenido del segmento.")
            return

        copied = False
        if hasattr(self.controller, "copy_to_clipboard"):
            copied = self.controller.copy_to_clipboard(clipboard_text)

        if not copied:
            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_text)
                copied = True
            except Exception:
                copied = False

        if not copied:
            messagebox.showerror("Error", "No se pudo copiar el segmento al portapapeles.")
            return

        messagebox.showinfo(
            "Copiar segmento",
            f"Se copiaron {copied_count} estructuras completas del segmento '{segment_name}'."
        )
