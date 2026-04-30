import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
import os
import platform
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class SubsectionCreationPopup(tk.Toplevel):
    """
    Popup for creating/editing subsections within a parent section.
    Shows the parent's files as checkboxes so the user can select
    which files belong to the subsection.
    """

    BASE_SECTION_SIZE_BYTES = 4 * 1024

    def __init__(self, parent, controller, section_name, sub_name=None, initial_files=None):
        """
        Args:
            parent: Parent widget.
            controller: Application controller.
            section_name: Name of the parent section.
            sub_name: If editing, the current subsection name.
            initial_files: If editing, the currently selected files for this subsection.
        """
        super().__init__(parent)
        self.controller = controller
        self.section_name = section_name
        self.original_sub_name = sub_name
        self.initial_files = set(initial_files) if initial_files else set()

        self.title("Editar Subsección" if sub_name else "Crear Nueva Subsección")

        # Center the window
        window_width = 700
        window_height = 500
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.configure(bg=Styles.COLOR_BG_MAIN)

        self.transient(parent)
        self.grab_set()

        # Checkbox variables: {abs_path: BooleanVar}
        self.file_vars = {}
        self.file_checkbuttons = {}
        self.parent_file_paths = self.controller.section_manager.get_files_in_section(self.section_name)
        self.file_display_levels = tk.IntVar(value=2)
        self.code_file_paths = {f["path"] for f in self.controller.project_manager.get_files()}

        all_project_files = self.controller.project_manager.get_files()
        self.abs_to_rel = {f['path']: f['rel_path'] for f in all_project_files}
        self.max_display_levels = max(
            1,
            max((self._count_displayable_parts(self.abs_to_rel.get(path, os.path.basename(path))) for path in self.parent_file_paths), default=1)
        )

        if self.file_display_levels.get() > self.max_display_levels:
            self.file_display_levels.set(self.max_display_levels)

        self._create_widgets()

    def _create_widgets(self):
        # ── Header ──
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=15, pady=(15, 5))

        ttk.Label(
            header,
            text=f"Sección padre: {self.section_name}",
            style="TLabel",
            font=(Styles.FONT_FAMILY, 14)
        ).pack(side="left")

        # ── Name Entry ──
        name_frame = ttk.Frame(self, style="Main.TFrame")
        name_frame.pack(fill="x", padx=15, pady=(5, 10))

        ttk.Label(name_frame, text="Nombre de la Subsección:", style="TLabel").pack(side="left")
        self.entry_name = ttk.Entry(name_frame, width=30)
        self.entry_name.pack(side="left", padx=5)

        if self.original_sub_name:
            self.entry_name.insert(0, self.original_sub_name)

        # ── File Path Depth Slider ──
        path_depth_frame = ttk.Frame(self, style="Main.TFrame")
        path_depth_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.lbl_path_depth = ttk.Label(
            path_depth_frame,
            text="Niveles en nombre: 2",
            style="TLabel"
        )
        self.lbl_path_depth.pack(side="left", padx=(0, 15))

        self.path_depth_slider = ttk.Scale(
            path_depth_frame,
            from_=1,
            to=self.max_display_levels,
            orient="horizontal",
            variable=self.file_display_levels,
            command=self._on_path_depth_change,
            length=180,
            style="Horizontal.TScale"
        )
        self.path_depth_slider.pack(side="left", fill="x")

        if self.max_display_levels <= 1:
            self.path_depth_slider.state(["disabled"])

        self._update_path_depth_label()

        # ── Select All / Deselect All buttons ──
        btn_frame = ttk.Frame(self, style="Main.TFrame")
        btn_frame.pack(fill="x", padx=15, pady=(0, 5))

        btn_select_all = ttk.Button(
            btn_frame, text="Seleccionar todo",
            style="Secondary.TButton",
            command=self._select_all
        )
        btn_select_all.pack(side="left", padx=(0, 5))

        btn_deselect_all = ttk.Button(
            btn_frame, text="Deseleccionar todo",
            style="Secondary.TButton",
            command=self._deselect_all
        )
        btn_deselect_all.pack(side="left")

        # ── File Checkboxes (scrollable) ──
        list_frame = ttk.Frame(self, style="Main.TFrame")
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Canvas + Scrollbar for scrollable checkboxes
        canvas = tk.Canvas(
            list_frame,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=0,
            borderwidth=0
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.checks_frame = tk.Frame(canvas, bg=Styles.COLOR_INPUT_BG)
        canvas_window = canvas.create_window((0, 0), window=self.checks_frame, anchor="nw")

        self.checks_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(canvas_window, width=e.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling only while the cursor is over the list.
        system_name = platform.system()

        def _on_mousewheel(event):
            if system_name == "Darwin":
                delta = -event.delta
            else:
                delta = int(-1 * (event.delta / 120))

            if delta == 0:
                delta = -1 if event.delta > 0 else 1

            canvas.yview_scroll(delta, "units")

        def _bind_mousewheel(_event=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def _unbind_mousewheel(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        self.checks_frame.bind("<Enter>", _bind_mousewheel)
        self.checks_frame.bind("<Leave>", _unbind_mousewheel)

        # Populate checkboxes with parent section files
        for abs_path in self.parent_file_paths:
            var = tk.BooleanVar(value=(abs_path in self.initial_files))
            self.file_vars[abs_path] = var

            cb = tk.Checkbutton(
                self.checks_frame,
                text=self._format_display_path(abs_path),
                variable=var,
                command=self._update_size_indicator,
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_FG_TEXT,
                selectcolor=Styles.COLOR_INPUT_BG,
                activebackground=Styles.COLOR_INPUT_BG,
                activeforeground=Styles.COLOR_ACCENT,
                font=(Styles.FONT_FAMILY, 14),
                anchor="w",
                padx=10,
                pady=3,
                highlightthickness=0,
                borderwidth=0
            )
            cb.pack(fill="x", anchor="w")
            self.file_checkbuttons[abs_path] = cb

        # Clean up mousewheel bindings on close
        def _on_destroy(event):
            if event.widget == self:
                try:
                    _unbind_mousewheel()
                except Exception:
                    pass

        self.bind("<Destroy>", _on_destroy)

        # ── Footer ──
        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=15, pady=15)

        self.lbl_size_indicator = tk.Label(
            footer,
            text="Tamaño código: 0.0 KB",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_ACCENT,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            padx=12,
            pady=6
        )
        self.lbl_size_indicator.pack(side="left")
        attach_tooltip(self.lbl_size_indicator, "Suma del tamaño de los archivos de código seleccionados en la subsección")

        btn_cancel = ttk.Button(footer, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)
        attach_tooltip(btn_cancel, "Cerrar ventana")

        btn_text = "Guardar Cambios" if self.original_sub_name else "Crear Subsección"
        btn_save = ttk.Button(footer, text=btn_text, style="Action.TButton", command=self._on_save)
        btn_save.pack(side="right", padx=5)
        attach_tooltip(btn_save, "Guardar subsección")
        self._update_size_indicator()

    def _get_size_indicator_color(self, total_bytes):
        size_kb = total_bytes / 1024.0
        if size_kb < 15:
            return Styles.COLOR_ACCENT
        if size_kb < 30:
            return "#2ecc71"
        if size_kb <= 50:
            return "#f1c40f"
        return "#ff5c5c"

    def _calculate_selected_code_size(self):
        total_bytes = self.BASE_SECTION_SIZE_BYTES
        for path, var in self.file_vars.items():
            if not var.get() or path not in self.code_file_paths:
                continue
            try:
                total_bytes += os.path.getsize(path)
            except OSError:
                continue
        return total_bytes

    def _update_size_indicator(self):
        total_bytes = self._calculate_selected_code_size()
        total_kb = total_bytes / 1024.0
        self.lbl_size_indicator.config(
            text=f"Tamaño código: {total_kb:.1f} KB",
            fg=self._get_size_indicator_color(total_bytes)
        )

    def _normalize_rel_path_parts(self, rel_path):
        normalized_path = os.path.normpath(rel_path)
        if normalized_path in {"", "."}:
            return []
        return [part for part in normalized_path.split(os.sep) if part and part != "."]

    def _count_displayable_parts(self, rel_path):
        parts = self._normalize_rel_path_parts(rel_path)
        return max(1, len(parts)) if parts else 1

    def _format_display_path(self, abs_path):
        rel_path = self.abs_to_rel.get(abs_path, os.path.basename(abs_path))
        parts = self._normalize_rel_path_parts(rel_path)
        if not parts:
            return os.path.basename(abs_path)

        levels = min(self.file_display_levels.get(), len(parts))
        return os.path.join(*parts[-levels:])

    def _update_path_depth_label(self):
        levels = int(self.file_display_levels.get())
        self.lbl_path_depth.config(text=f"Niveles en nombre: {levels}")

    def _refresh_file_labels(self):
        for abs_path, checkbutton in self.file_checkbuttons.items():
            checkbutton.config(text=self._format_display_path(abs_path))

    def _on_path_depth_change(self, val):
        rounded_value = max(1, min(self.max_display_levels, int(round(float(val)))))
        if self.file_display_levels.get() != rounded_value:
            self.file_display_levels.set(rounded_value)

        self._update_path_depth_label()
        self._refresh_file_labels()

    def _select_all(self):
        for var in self.file_vars.values():
            var.set(True)
        self._update_size_indicator()

    def _deselect_all(self):
        for var in self.file_vars.values():
            var.set(False)
        self._update_size_indicator()

    def _on_save(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Error", "Debes escribir un nombre para la subsección.")
            return

        # Collect selected files
        selected_files = [path for path, var in self.file_vars.items() if var.get()]

        if not selected_files:
            messagebox.showwarning("Aviso", "Debes seleccionar al menos un fichero.")
            return

        try:
            if self.original_sub_name:
                self.controller.section_manager.update_subsection(
                    self.section_name, self.original_sub_name, name, selected_files
                )
            else:
                self.controller.section_manager.create_subsection(
                    self.section_name, name, selected_files
                )
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
