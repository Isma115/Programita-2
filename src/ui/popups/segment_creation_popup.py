import difflib
import re
import tkinter as tk
import tkinter.messagebox as messagebox
import unicodedata
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

from src.logic.structure_outline import (
    build_outline_forest,
    get_selected_section_file_infos,
    get_structures_for_files,
)
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class SegmentCreationPopup(tk.Toplevel):
    """
    Popup for creating/editing segments inside a subsection.
    A segment is a structure-based subset of the parent subsection.
    """

    CODE_MARKER_SELECTED = "●"
    CODE_MARKER_UNSELECTED = "○"

    def __init__(self, parent, controller, section_name, subsection_name, segment_name=None, initial_items=None):
        super().__init__(parent)
        self.controller = controller
        self.section_name = section_name
        self.subsection_name = subsection_name
        self.original_segment_name = segment_name
        self.initial_items = list(initial_items or [])
        self.saved_segment_name = None

        self._current_outline_forest = []
        self._outline_file_entries = []
        self._structure_node_by_key = {}
        self._file_info_by_path = {}
        self._current_file_index = 0
        self._manual_checked_structure_keys = set()
        self._manual_unchecked_structure_keys = set()
        self._auto_checked_structure_keys = set()
        self._is_code_expanded = False

        self.segment_name_var = tk.StringVar(value=segment_name or "")
        self.segment_summary_var = tk.StringVar(value="Cargando estructuras...")
        self.bulk_match_summary_var = tk.StringVar(value="Sin cabeceras señaladas.")
        self.current_file_var = tk.StringVar(value="Sin archivo cargado")
        self.current_file_summary_var = tk.StringVar(value="")

        self.title("Editar Segmento" if segment_name else "Crear Segmento")

        window_width = 1320
        window_height = 780
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(1120, 680)
        self.configure(bg=Styles.COLOR_BG_MAIN)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        preserve_keys = [item.get("key") for item in self.initial_items if item.get("key")]
        self._load_available_structures(preserve_keys=preserve_keys)
        self.entry_segment_name.focus_set()
        self.bind("<Escape>", self._on_escape_pressed)

    def _create_widgets(self):
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(14, 8))
        self.header_frame = header

        ttk.Label(
            header,
            text=f"Subsección padre: {self.section_name} > {self.subsection_name}",
            style="Header.TLabel"
        ).pack(side="left")

        name_card = tk.Frame(
            self,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        name_card.pack(fill="x", padx=14, pady=(0, 10))
        name_card.columnconfigure(0, weight=1)
        self.name_card = name_card

        tk.Label(
            name_card,
            text="Nombre del segmento",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        name_actions = ttk.Frame(name_card, style="Main.TFrame")
        name_actions.grid(row=1, column=1, sticky="e", padx=(8, 12), pady=(0, 10))
        self.name_actions_frame = name_actions

        self.btn_cancel = ttk.Button(name_actions, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        self.btn_cancel.pack(side="right", padx=(8, 0))
        attach_tooltip(self.btn_cancel, "Cerrar ventana sin guardar")

        self.btn_accept = ttk.Button(name_actions, text="Aceptar", style="Action.TButton", command=self._on_accept)
        self.btn_accept.pack(side="right")
        attach_tooltip(self.btn_accept, "Guardar el segmento dentro de la subsección")

        self.entry_segment_name = tk.Entry(
            name_card,
            textvariable=self.segment_name_var,
            font=(Styles.FONT_FAMILY, 13),
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat"
        )
        Styles.strip_classic_widget_chrome(self.entry_segment_name)
        self.entry_segment_name.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10), ipady=6)

        body = ttk.Frame(self, style="Main.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)
        self.body_frame = body

        code_frame = tk.Frame(
            body,
            bg=ARBITRARY_THEME["bg"],
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
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
            width=3
        )
        self.btn_prev_file.grid(row=0, column=0, sticky="w")
        attach_tooltip(self.btn_prev_file, "Mostrar el archivo anterior")

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
            justify="left"
        ).grid(row=0, column=0, sticky="ew")

        self.btn_next_file = ttk.Button(
            nav_frame,
            text=">",
            style="ToolbarGroup.TButton",
            command=lambda: self._change_current_file(1),
            width=3
        )
        self.btn_next_file.grid(row=0, column=2, sticky="e")
        attach_tooltip(self.btn_next_file, "Mostrar el archivo siguiente")

        self.btn_expand_code = ttk.Button(
            nav_frame,
            text="Expandir",
            style="ToolbarGroup.TButton",
            command=self._toggle_code_expand
        )
        self.btn_expand_code.grid(row=0, column=3, sticky="e", padx=(8, 0))
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
            selectbackground=ARBITRARY_THEME["select_bg"]
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
            selectbackground=ARBITRARY_THEME["select_bg"]
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
            state="disabled"
        )
        Styles.strip_classic_widget_chrome(self.code_text)
        self.code_text.grid(row=0, column=2, sticky="nsew")
        self._configure_code_text_tags()

        code_scroll = ttk.Scrollbar(
            viewer_frame,
            orient="vertical",
            command=self._on_code_vertical_scroll,
            style="Vertical.TScrollbar"
        )
        code_scroll.grid(row=0, column=3, sticky="ns")
        self.code_scrollbar = code_scroll
        self.code_text.configure(yscrollcommand=self._on_code_yscroll)

        code_xscroll = ttk.Scrollbar(
            code_frame,
            orient="horizontal",
            command=self.code_text.xview,
            style="Horizontal.TScrollbar"
        )
        code_xscroll.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.code_text.configure(xscrollcommand=code_xscroll.set)

        for widget in (self.marker_text, self.code_text, self.line_numbers_text):
            widget.bind("<MouseWheel>", self._on_code_mousewheel, add="+")
            widget.bind("<Button-4>", self._on_code_mousewheel_linux_up, add="+")
            widget.bind("<Button-5>", self._on_code_mousewheel_linux_down, add="+")

        tree_footer = ttk.Frame(body, style="Main.TFrame")
        tree_footer.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(10, 0))
        self.tree_footer = tree_footer

        btn_select_all = ttk.Button(
            tree_footer,
            text="Seleccionar todo",
            style="ToolbarGroup.TButton",
            command=self._select_all_structures
        )
        btn_select_all.pack(side="left", padx=(0, 8))
        attach_tooltip(btn_select_all, "Selecciona todas las cabeceras detectadas")

        btn_clear = ttk.Button(
            tree_footer,
            text="Limpiar selección",
            style="ToolbarGroup.TButton",
            command=self._clear_structure_selection
        )
        btn_clear.pack(side="left")
        attach_tooltip(btn_clear, "Quita la selección actual y vacía la lista de cabeceras")

        bulk_frame = tk.Frame(
            body,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        bulk_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")
        bulk_frame.columnconfigure(0, weight=1)
        bulk_frame.rowconfigure(2, weight=1)
        self.bulk_frame = bulk_frame

        bulk_actions = tk.Frame(bulk_frame, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        bulk_actions.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        self.btn_apply_bulk_match = ttk.Button(
            bulk_actions,
            text="Aplicar selección",
            style="ToolbarGroup.TButton",
            command=self._apply_bulk_structure_matching
        )
        self.btn_apply_bulk_match.grid(row=0, column=0, sticky="w")

        self.btn_clear_bulk_selection = ttk.Button(
            bulk_actions,
            text="Limpiar selección",
            style="ToolbarGroup.TButton",
            command=self._clear_structure_selection
        )
        self.btn_clear_bulk_selection.grid(row=0, column=1, sticky="w", padx=(8, 0))

        bulk_text_frame = tk.Frame(bulk_frame, bg=Styles.COLOR_INPUT_BG, bd=0, highlightthickness=0)
        bulk_text_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        bulk_text_frame.columnconfigure(0, weight=1)
        bulk_text_frame.rowconfigure(0, weight=1)

        self.bulk_match_text = tk.Text(
            bulk_text_frame,
            wrap="word",
            height=14,
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

        ttk.Label(
            bulk_frame,
            textvariable=self.bulk_match_summary_var,
            style="TLabel",
            justify="left",
            anchor="w"
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _configure_code_text_tags(self):
        if arbitrary_configure_tags:
            arbitrary_configure_tags(self.code_text)
        self.code_text.tag_configure("code_default", foreground=ARBITRARY_THEME["fg"], font=ARBITRARY_FONT_CODE)
        self.code_text.tag_configure("code_hint", foreground=ARBITRARY_THEME["line_num_fg"], font=ARBITRARY_FONT_CODE)
        self.code_text.tag_configure("header_selected", background=ARBITRARY_THEME["select_bg"])
        self.marker_text.tag_configure(
            "marker_selected",
            foreground="#f44747",
            font=(ARBITRARY_FONT_CODE[0], ARBITRARY_FONT_CODE[1], "bold")
        )
        self.marker_text.tag_configure(
            "marker_unselected",
            foreground="#6b7280",
            font=(ARBITRARY_FONT_CODE[0], ARBITRARY_FONT_CODE[1], "bold")
        )
        try:
            self.code_text.tag_lower("code_default")
        except Exception:
            pass

    def _on_code_yscroll(self, first, last):
        self.code_scrollbar.set(first, last)
        try:
            self.marker_text.yview_moveto(first)
        except Exception:
            pass
        try:
            self.line_numbers_text.yview_moveto(first)
        except Exception:
            pass

    def _on_code_vertical_scroll(self, *args):
        self.marker_text.yview(*args)
        self.code_text.yview(*args)
        self.line_numbers_text.yview(*args)

    def _on_code_mousewheel(self, event):
        delta = 0
        if getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
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
            self.left_panel_label.grid_remove()
            self.right_panel_label.grid_remove()
            self.code_hint_label.grid_remove()
            self.bulk_frame.grid_remove()
            self.tree_footer.grid_remove()
            self.body_frame.pack_configure(fill="both", expand=True, padx=0, pady=0)
            self.body_frame.columnconfigure(0, weight=1)
            self.body_frame.columnconfigure(1, weight=0)
            self.body_frame.rowconfigure(0, weight=1)
            self.body_frame.rowconfigure(1, weight=0)
            self.body_frame.rowconfigure(2, weight=0)
            self.code_frame.grid_configure(column=0, row=0, rowspan=3, columnspan=2, padx=0, pady=0)
            self.btn_expand_code.configure(text="Contraer")
        else:
            self.header_frame.pack(fill="x", padx=14, pady=(14, 8), before=self.body_frame)
            self.name_card.pack(fill="x", padx=14, pady=(0, 10), before=self.body_frame)
            self.body_frame.pack_configure(fill="both", expand=True, padx=14, pady=(0, 10))
            self.body_frame.columnconfigure(0, weight=3)
            self.body_frame.columnconfigure(1, weight=2)
            self.body_frame.rowconfigure(0, weight=0)
            self.body_frame.rowconfigure(1, weight=1)
            self.body_frame.rowconfigure(2, weight=0)
            self.left_panel_label.grid()
            self.right_panel_label.grid()
            self.code_hint_label.grid()
            self.bulk_frame.grid()
            self.tree_footer.grid()
            self.code_frame.grid_configure(column=0, row=1, rowspan=1, columnspan=1, padx=(0, 10), pady=0)
            self.btn_expand_code.configure(text="Expandir")

        self.update_idletasks()
        self._render_current_file_code()

    def _load_available_structures(self, preserve_keys=None):
        if preserve_keys is not None:
            self._manual_checked_structure_keys = set(preserve_keys)
            self._manual_unchecked_structure_keys.clear()

        previous_file_path = self._get_current_file_path()
        file_infos = get_selected_section_file_infos(self.controller, self.section_name, self.subsection_name)
        self._file_info_by_path = {item.get("path"): item for item in file_infos if item.get("path")}

        structures = get_structures_for_files(self.controller, file_infos)
        self._current_outline_forest = build_outline_forest(file_infos, structures)
        self._outline_file_entries = [entry for entry in self._current_outline_forest if entry.get("roots")]

        self._structure_node_by_key = {}
        for file_entry in self._current_outline_forest:
            for node in file_entry.get("items", []):
                self._structure_node_by_key[node["key"]] = node

        preferred_keys = preserve_keys if preserve_keys is not None else list(self._get_effective_checked_structure_keys())
        self._set_current_file_index(previous_file_path=previous_file_path, preferred_keys=preferred_keys)
        self._refresh_selection_ui()

    def _set_current_file_index(self, previous_file_path=None, preferred_keys=None):
        if not self._outline_file_entries:
            self._current_file_index = 0
            return

        preferred_file_path = self._find_first_file_path_for_keys(preferred_keys or [])
        if preferred_file_path:
            for idx, file_entry in enumerate(self._outline_file_entries):
                if file_entry.get("file_path") == preferred_file_path:
                    self._current_file_index = idx
                    return

        if previous_file_path:
            for idx, file_entry in enumerate(self._outline_file_entries):
                if file_entry.get("file_path") == previous_file_path:
                    self._current_file_index = idx
                    return

        self._current_file_index = 0

    def _find_first_file_path_for_keys(self, keys):
        key_set = {key for key in (keys or []) if key}
        if not key_set:
            return None
        for file_entry in self._outline_file_entries:
            if any(node.get("key") in key_set for node in file_entry.get("items", [])):
                return file_entry.get("file_path")
        return None

    def _get_current_file_path(self):
        current_entry = self._get_current_file_entry()
        return current_entry.get("file_path") if current_entry else None

    def _get_current_file_entry(self):
        if not self._outline_file_entries:
            return None
        if self._current_file_index < 0 or self._current_file_index >= len(self._outline_file_entries):
            self._current_file_index = 0
        return self._outline_file_entries[self._current_file_index]

    def _change_current_file(self, step):
        if not self._outline_file_entries:
            return
        self._current_file_index = (self._current_file_index + step) % len(self._outline_file_entries)
        self._render_current_file_code()

    def _render_current_file_code(self):
        current_entry = self._get_current_file_entry()
        code_yview = self.code_text.yview()[0] if self.code_text.winfo_exists() else 0.0
        code_xview = self.code_text.xview()[0] if self.code_text.winfo_exists() else 0.0

        self.marker_text.configure(state="normal")
        self.line_numbers_text.configure(state="normal")
        self.code_text.configure(state="normal", cursor="xterm")
        self.marker_text.delete("1.0", "end")
        self.line_numbers_text.delete("1.0", "end")
        self.code_text.delete("1.0", "end")

        if not current_entry:
            self.current_file_var.set("Sin archivo con estructuras detectadas")
            self.current_file_summary_var.set("")
            self.marker_text.insert("1.0", " ")
            self.line_numbers_text.insert("1.0", "1")
            self.code_text.insert("1.0", "No se detectaron cabeceras seleccionables en esta subsección.", ("code_hint",))
            self.marker_text.configure(state="disabled")
            self.line_numbers_text.configure(state="disabled")
            self.code_text.configure(state="disabled")
            self.btn_prev_file.state(["disabled"])
            self.btn_next_file.state(["disabled"])
            return

        file_info = self._file_info_by_path.get(current_entry.get("file_path"), {})
        content = file_info.get("content", "")
        lines = content.split("\n")
        if not lines:
            lines = [""]

        self.current_file_var.set(current_entry.get("file_rel_path") or "sin_archivo")
        self.current_file_summary_var.set("")
        line_count = len(lines)

        digits = max(len(str(line_count)), 2)
        structures_by_line = {}
        for node in current_entry.get("items", []):
            structures_by_line.setdefault(int(node.get("start_line", 1) or 1), []).append(node)

        for line_number, line_text in enumerate(lines, start=1):
            if line_number > 1:
                self.marker_text.insert("end", "\n")
                self.line_numbers_text.insert("end", "\n")
                self.code_text.insert("end", "\n")

            header_nodes = sorted(
                structures_by_line.get(line_number, []),
                key=lambda node: (int(node.get("start_line", 1) or 1), int(node.get("end_line", 1) or 1), node.get("header", ""))
            )

            if header_nodes:
                for node_index, node in enumerate(header_nodes):
                    marker_tag = f"marker_{line_number}_{node_index}"
                    selected = node.get("key") in self._get_effective_checked_structure_keys()
                    marker = self.CODE_MARKER_SELECTED if selected else self.CODE_MARKER_UNSELECTED
                    marker_style = "marker_selected" if selected else "marker_unselected"
                    self.marker_text.insert("end", marker, (marker_tag, marker_style))
                    self.marker_text.tag_bind(marker_tag, "<Button-1>", lambda event, key=node["key"]: self._toggle_structure_key(key))
                    self.marker_text.tag_bind(marker_tag, "<Enter>", lambda event: self.marker_text.configure(cursor="hand2"))
                    self.marker_text.tag_bind(marker_tag, "<Leave>", lambda event: self.marker_text.configure(cursor="xterm"))
                    if node_index < len(header_nodes) - 1:
                        self.marker_text.insert("end", " ")
            else:
                self.marker_text.insert("end", " ")

            self.line_numbers_text.insert("end", f"{line_number:>{digits}}", ("code_hint",))
            line_start_index = self.code_text.index("end")
            self.code_text.insert("end", line_text)
            line_end_index = self.code_text.index("end")
            if header_nodes and any(node.get("key") in self._get_effective_checked_structure_keys() for node in header_nodes):
                self.code_text.tag_add("header_selected", line_start_index, line_end_index)

        if arbitrary_highlight_syntax and current_entry.get("file_path"):
            try:
                arbitrary_highlight_syntax(self.code_text, current_entry.get("file_path"))
            except Exception:
                pass

        self.code_text.tag_raise("header_selected")

        self.marker_text.configure(state="disabled")
        self.line_numbers_text.configure(state="disabled")
        self.code_text.configure(state="disabled")
        self.marker_text.yview_moveto(code_yview)
        self.code_text.yview_moveto(code_yview)
        self.line_numbers_text.yview_moveto(code_yview)
        self.code_text.xview_moveto(code_xview)

        if len(self._outline_file_entries) > 1:
            self.btn_prev_file.state(["!disabled"])
            self.btn_next_file.state(["!disabled"])
        else:
            self.btn_prev_file.state(["disabled"])
            self.btn_next_file.state(["disabled"])

    def _get_effective_checked_structure_keys(self):
        return (
            set(self._auto_checked_structure_keys)
            | set(self._manual_checked_structure_keys)
        ) - set(self._manual_unchecked_structure_keys)

    def _get_available_structure_keys(self):
        return set(self._structure_node_by_key.keys())

    def _refresh_selection_ui(self, bulk_message=None):
        self._sync_selected_headers_text()
        self._refresh_segment_summary()
        if bulk_message is None:
            selected_count = len(self._get_effective_checked_structure_keys() & self._get_available_structure_keys())
            self.bulk_match_summary_var.set(
                "Sin cabeceras señaladas." if selected_count == 0 else f"{selected_count} cabeceras señaladas."
            )
        else:
            self.bulk_match_summary_var.set(bulk_message)
        self._render_current_file_code()

    def _refresh_segment_summary(self):
        available_count = len(self._get_available_structure_keys())
        selected_count = len(self._get_effective_checked_structure_keys() & self._get_available_structure_keys())
        if available_count == 0:
            self.segment_summary_var.set(
                f"No se detectaron estructuras disponibles en {self.section_name} > {self.subsection_name}."
            )
            return
        self.segment_summary_var.set(
            f"{selected_count} estructuras seleccionadas de {available_count} disponibles en {self.section_name} > {self.subsection_name}."
        )

    def _iter_selected_structure_items(self):
        selected_keys = self._get_effective_checked_structure_keys()
        for file_entry in self._current_outline_forest:
            for node in sorted(
                file_entry.get("items", []),
                key=lambda item: (int(item.get("start_line", 1) or 1), int(item.get("end_line", 1) or 1), item.get("header", ""))
            ):
                if node.get("key") in selected_keys:
                    yield file_entry, node

    def _format_header_for_bulk_text(self, header_text):
        """Flattens multiline headers into a single editable line for smart selection."""
        return " ".join((header_text or "").split())

    def _sync_selected_headers_text(self):
        lines = [
            self._format_header_for_bulk_text(node.get("header", ""))
            for _, node in self._iter_selected_structure_items()
            if node.get("header", "").strip()
        ]
        self.bulk_match_text.delete("1.0", "end")
        if lines:
            self.bulk_match_text.insert("1.0", "\n".join(lines))

    def _select_all_structures(self):
        self._manual_checked_structure_keys.update(self._get_available_structure_keys())
        self._manual_unchecked_structure_keys.clear()
        self._refresh_selection_ui()

    def _clear_structure_selection(self):
        self._manual_checked_structure_keys.clear()
        self._manual_unchecked_structure_keys.clear()
        self._auto_checked_structure_keys.clear()
        self._refresh_selection_ui(bulk_message="Sin cabeceras señaladas.")

    def _toggle_structure_key(self, key):
        if not key or key not in self._get_available_structure_keys():
            return

        if key in self._get_effective_checked_structure_keys():
            self._manual_checked_structure_keys.discard(key)
            self._manual_unchecked_structure_keys.add(key)
        else:
            self._manual_unchecked_structure_keys.discard(key)
            self._manual_checked_structure_keys.add(key)

        self._refresh_selection_ui()

    def _apply_bulk_structure_matching(self):
        raw_lines = self._get_bulk_match_lines()
        if not raw_lines:
            self._auto_checked_structure_keys.clear()
            self._refresh_selection_ui(
                bulk_message="Escribe al menos una cabecera y pulsa 'Aplicar selección'."
            )
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
        self._refresh_selection_ui(bulk_message=summary)

    def _get_bulk_match_lines(self):
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
        if best_score < 0.58:
            return []

        tolerance = 0.015 if best_score >= 0.95 else 0.03 if best_score >= 0.78 else 0.045
        selected_keys = []
        for score, key in scored_matches:
            if best_score - score > tolerance:
                break
            selected_keys.append(key)
        return selected_keys

    def _score_structure_similarity(self, node, query_norm, query_compact, query_tokens):
        candidates = [node.get("header", ""), node.get("name", "")]
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
            best_score = max(best_score, difflib.SequenceMatcher(None, query_norm, candidate_norm).ratio() * 0.84)
        if query_compact and candidate_compact:
            best_score = max(best_score, difflib.SequenceMatcher(None, query_compact, candidate_compact).ratio() * 0.9)

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
        selected_keys = set(self._get_effective_checked_structure_keys())
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

    def _on_accept(self):
        segment_name = self.segment_name_var.get().strip()
        if not segment_name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el segmento.")
            return

        items = self._build_segment_items_payload()
        if not items:
            messagebox.showwarning("Aviso", "Selecciona al menos una estructura.")
            return

        try:
            if self.original_segment_name:
                self.controller.section_manager.update_segment(
                    self.section_name,
                    self.subsection_name,
                    self.original_segment_name,
                    segment_name,
                    items
                )
            else:
                self.controller.section_manager.create_segment(
                    self.section_name,
                    self.subsection_name,
                    segment_name,
                    items
                )
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el segmento:\n{exc}")
            return

        self.saved_segment_name = segment_name
        self.destroy()
