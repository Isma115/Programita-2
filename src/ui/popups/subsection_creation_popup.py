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

        self._create_widgets()

    def _create_widgets(self):
        # ── Header ──
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=15, pady=(15, 5))

        ttk.Label(
            header,
            text=f"Sección padre: {self.section_name}",
            style="TLabel",
            font=("Segoe UI", 14)
        ).pack(side="left")

        # ── Name Entry ──
        name_frame = ttk.Frame(self, style="Main.TFrame")
        name_frame.pack(fill="x", padx=15, pady=(5, 10))

        ttk.Label(name_frame, text="Nombre de la Subsección:", style="TLabel").pack(side="left")
        self.entry_name = ttk.Entry(name_frame, width=30)
        self.entry_name.pack(side="left", padx=5)

        if self.original_sub_name:
            self.entry_name.insert(0, self.original_sub_name)

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
        parent_files = self.controller.section_manager.get_files_in_section(self.section_name)
        all_project_files = self.controller.project_manager.get_files()
        abs_to_rel = {f['path']: f['rel_path'] for f in all_project_files}

        for abs_path in parent_files:
            var = tk.BooleanVar(value=(abs_path in self.initial_files))
            self.file_vars[abs_path] = var

            # Display as parent_dir/filename for readability
            rel_path = abs_to_rel.get(abs_path, os.path.basename(abs_path))
            parts = rel_path.split(os.sep)
            if len(parts) > 1:
                display = os.path.join(parts[-2], parts[-1])
            else:
                display = rel_path

            cb = tk.Checkbutton(
                self.checks_frame,
                text=display,
                variable=var,
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_FG_TEXT,
                selectcolor=Styles.COLOR_INPUT_BG,
                activebackground=Styles.COLOR_INPUT_BG,
                activeforeground=Styles.COLOR_ACCENT,
                font=("Segoe UI", 14),
                anchor="w",
                padx=10,
                pady=3,
                highlightthickness=0,
                borderwidth=0
            )
            cb.pack(fill="x", anchor="w")

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

        btn_cancel = ttk.Button(footer, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)
        attach_tooltip(btn_cancel, "Cerrar ventana")

        btn_text = "Guardar Cambios" if self.original_sub_name else "Crear Subsección"
        btn_save = ttk.Button(footer, text=btn_text, style="Action.TButton", command=self._on_save)
        btn_save.pack(side="right", padx=5)
        attach_tooltip(btn_save, "Guardar subsección")

    def _select_all(self):
        for var in self.file_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.file_vars.values():
            var.set(False)

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
