import difflib
import re
import tkinter as tk
import tkinter.messagebox as messagebox
import unicodedata
from tkinter import ttk

from src.logic.structure_outline import (
    build_outline_forest,
    get_outline_visual_role,
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
    DEFAULT_OPEN_STRUCTURE_DEPTH = 2

    def __init__(self, parent, controller, section_name, subsection_name, segment_name=None, initial_items=None):
        super().__init__(parent)
        self.controller = controller
        self.section_name = section_name
        self.subsection_name = subsection_name
        self.original_segment_name = segment_name
        self.initial_items = list(initial_items or [])
        self.saved_segment_name = None

        self._current_outline_forest = []
        self._tree_item_to_key = {}
        self._structure_tree_item_by_key = {}
        self._manual_checked_structure_keys = set()
        self._manual_unchecked_structure_keys = set()
        self._auto_checked_structure_keys = set()

        self.segment_name_var = tk.StringVar(value=segment_name or "")
        self.segment_summary_var = tk.StringVar(value="Cargando estructuras...")
        self.bulk_match_summary_var = tk.StringVar(
            value="Pega una cabecera por línea y usa el botón para aplicar las coincidencias."
        )

        self.title("Editar Segmento" if segment_name else "Crear Segmento")

        window_width = 1320
        window_height = 780
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(1100, 680)
        self.configure(bg=Styles.COLOR_BG_MAIN)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        preserve_keys = [item.get("key") for item in self.initial_items if item.get("key")]
        self._load_available_structures(preserve_keys=preserve_keys)
        self.entry_segment_name.focus_set()

    def _create_widgets(self):
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(14, 8))

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

        tk.Label(
            name_card,
            text="Nombre del segmento",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        self.entry_segment_name = tk.Entry(
            name_card,
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
        self.entry_segment_name.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10), ipady=6)

        body = ttk.Frame(self, style="Main.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
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
            text="Cabeceras para selección inteligente",
            style="TLabel"
        ).grid(row=0, column=1, sticky="w", pady=(0, 8))

        tree_frame = ttk.Frame(body, style="Main.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
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

        structure_scroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.structure_tree.yview,
            style="Vertical.TScrollbar"
        )
        structure_scroll.grid(row=0, column=1, sticky="ns")
        self.structure_tree.configure(yscrollcommand=structure_scroll.set)

        tree_footer = ttk.Frame(body, style="Main.TFrame")
        tree_footer.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(10, 0))

        btn_select_all = ttk.Button(
            tree_footer,
            text="Seleccionar todo",
            style="ToolbarGroup.TButton",
            command=self._select_all_structures
        )
        btn_select_all.pack(side="left", padx=(0, 8))
        attach_tooltip(btn_select_all, "Selecciona todas las estructuras del árbol")

        btn_clear = ttk.Button(
            tree_footer,
            text="Limpiar selección",
            style="ToolbarGroup.TButton",
            command=self._clear_structure_selection
        )
        btn_clear.pack(side="left")
        attach_tooltip(btn_clear, "Quita la selección actual sin borrar el texto de cabeceras")

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

        tk.Label(
            bulk_frame,
            text="Una estructura por línea. Solo se buscará dentro de la subsección padre.",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left"
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

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

        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=14, pady=(0, 14))

        ttk.Label(
            footer,
            textvariable=self.segment_summary_var,
            style="TLabel"
        ).pack(side="left")

        btn_cancel = ttk.Button(footer, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))
        attach_tooltip(btn_cancel, "Cerrar ventana sin guardar")

        btn_accept = ttk.Button(footer, text="Aceptar", style="Action.TButton", command=self._on_accept)
        btn_accept.pack(side="right")
        attach_tooltip(btn_accept, "Guardar el segmento dentro de la subsección")

    def _load_available_structures(self, preserve_keys=None):
        if preserve_keys is not None:
            self._manual_checked_structure_keys = set(preserve_keys)
            self._manual_unchecked_structure_keys.clear()

        file_infos = get_selected_section_file_infos(self.controller, self.section_name, self.subsection_name)
        structures = get_structures_for_files(self.controller, file_infos)
        self._current_outline_forest = build_outline_forest(file_infos, structures)
        self._populate_structure_tree()

    def _configure_structure_tree_tags(self):
        self.structure_tree.tag_configure("outline_role_file", foreground=Styles.COLOR_CODE_FILE)
        self.structure_tree.tag_configure("outline_role_default", foreground=Styles.COLOR_FG_TEXT)
        self.structure_tree.tag_configure("outline_role_view", foreground=Styles.COLOR_CODE_VIEW)
        self.structure_tree.tag_configure("outline_role_backend", foreground=Styles.COLOR_CODE_BACKEND)

    def _get_outline_tree_tags(self, file_rel_path, node=None):
        role = get_outline_visual_role(file_rel_path, structure_node=node)
        return (f"outline_role_{role}",)

    def _populate_structure_tree(self):
        self.structure_tree.delete(*self.structure_tree.get_children())
        self._tree_item_to_key = {}
        self._structure_tree_item_by_key = {}

        available_count = 0
        for file_entry in self._current_outline_forest:
            roots = file_entry.get("roots", [])
            if not roots:
                continue

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

            for root in roots:
                available_count += self._insert_structure_node(
                    file_iid,
                    root,
                    file_entry["file_rel_path"],
                    depth=1
                )

        self._refresh_visible_checkboxes()
        self._refresh_segment_summary(available_count=available_count)

    def _insert_structure_node(self, parent_iid, node, file_rel_path, depth=1):
        item_iid = f"struct:{node['key']}"
        self.structure_tree.insert(
            parent_iid,
            "end",
            iid=item_iid,
            text=self._format_tree_header(node),
            values=(self._format_structure_type_label(node.get("type", "")),),
            open=depth < self.DEFAULT_OPEN_STRUCTURE_DEPTH,
            tags=self._get_outline_tree_tags(file_rel_path, node)
        )
        self._tree_item_to_key[item_iid] = node["key"]
        self._structure_tree_item_by_key[node["key"]] = item_iid

        count = 1
        for child in node.get("children", []):
            count += self._insert_structure_node(
                item_iid,
                child,
                file_rel_path,
                depth=depth + 1
            )
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

    def _get_effective_checked_structure_keys(self):
        return (
            set(self._auto_checked_structure_keys)
            | set(self._manual_checked_structure_keys)
        ) - set(self._manual_unchecked_structure_keys)

    def _refresh_visible_checkboxes(self):
        checked_keys = self._get_effective_checked_structure_keys()
        for key, item_id in self._structure_tree_item_by_key.items():
            try:
                current_text = self.structure_tree.item(item_id, "text")
            except Exception:
                continue

            body = current_text[2:] if current_text.startswith(("☐ ", "☑ ")) else current_text
            prefix = "☑ " if key in checked_keys else "☐ "
            self.structure_tree.item(item_id, text=f"{prefix}{body}")

        self._refresh_segment_summary()

    def _refresh_segment_summary(self, available_count=None):
        if available_count is None:
            available_count = len(self._structure_tree_item_by_key)
        selected_count = len(self._get_effective_checked_structure_keys())
        self.segment_summary_var.set(
            f"{selected_count} estructuras seleccionadas de {available_count} disponibles en {self.section_name} > {self.subsection_name}."
        )

    def _select_all_structures(self):
        self._manual_checked_structure_keys.update(self._structure_tree_item_by_key.keys())
        self._manual_unchecked_structure_keys.clear()
        self._refresh_visible_checkboxes()

    def _clear_structure_selection(self):
        self._manual_checked_structure_keys.clear()
        self._manual_unchecked_structure_keys.clear()
        self._auto_checked_structure_keys.clear()
        self.bulk_match_summary_var.set(
            "Pega una cabecera por línea y usa el botón para aplicar las coincidencias."
        )
        self._refresh_visible_checkboxes()

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
        return "break"

    def _apply_bulk_structure_matching(self):
        raw_lines = self._get_bulk_match_lines()
        if not raw_lines:
            self._auto_checked_structure_keys.clear()
            self.bulk_match_summary_var.set(
                "Escribe al menos una cabecera y pulsa 'Aplicar selección'."
            )
            self._refresh_visible_checkboxes()
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
