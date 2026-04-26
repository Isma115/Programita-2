import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
import os
import difflib
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip

class SectionCreationPopup(tk.Toplevel):
    BASE_SECTION_SIZE_BYTES = 4 * 1024

    def __init__(self, parent, controller, section_name=None, initial_files=None, initial_tables=None):
        super().__init__(parent)
        self.controller = controller
        self.original_section_name = section_name
        self.initial_files_data = initial_files
        self.initial_tables_data = initial_tables
        self.title("Editar Sección" if section_name else "Crear Nueva Sección")
        # Center the window
        window_width = 800
        window_height = 600
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_cordinate = int((screen_width/2) - (window_width/2))
        y_cordinate = int((screen_height/2) - (window_height/2))
        self.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
        self.configure(bg=Styles.COLOR_BG_MAIN)
        
        self.transient(parent)
        self.grab_set()
        
        self.valid_files = []
        self.valid_tables = []
        self.code_file_paths = {f["path"] for f in self.controller.project_manager.get_files()}
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Header
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(header, text="Nombre de la Sección:", style="TLabel").pack(side="left")
        self.entry_name = ttk.Entry(header, width=30)
        self.entry_name.pack(side="left", padx=5)
        
        if self.original_section_name:
            self.entry_name.insert(0, self.original_section_name)
        
        # Split View
        split_frame = ttk.Frame(self, style="Main.TFrame")
        split_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Left Pane: Relative Paths Input
        left_pane = ttk.LabelFrame(split_frame, text="Archivos y tablas (una por línea)", style="Main.TFrame")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.txt_relative = tk.Text(
            left_pane,
            wrap="none",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            font=Styles.FONT_CODE,
            borderwidth=0,
            width=35,
            padx=10, pady=10
        )
        self.txt_relative.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_relative.bind("<KeyRelease>", self._on_text_change)
        
        # Right Pane: Resolved Paths/Tables (Read Only)
        right_pane = ttk.LabelFrame(split_frame, text="Elementos Detectados", style="TLabelframe")
        right_pane.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.txt_absolute = tk.Text(
            right_pane,
            wrap="none",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            state="disabled",
            font=Styles.FONT_CODE,
            borderwidth=0,
            width=35,
            padx=10, pady=10
        )
        self.txt_absolute.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Footer
        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=10, pady=10)

        self.lbl_size_indicator = tk.Label(
            footer,
            text="Tamaño código: 0.0 KB",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_ACCENT,
            font=("Segoe UI", 11, "bold"),
            padx=12,
            pady=6
        )
        self.lbl_size_indicator.pack(side="left")
        attach_tooltip(self.lbl_size_indicator, "Suma del tamaño de los archivos de código incluidos en la sección")
        
        btn_cancel = ttk.Button(footer, text="Cancelar", style="Secondary.TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)
        attach_tooltip(btn_cancel, "Cerrar ventana")
        btn_text = "Guardar Cambios" if self.original_section_name else "Crear Sección"
        btn_save = ttk.Button(footer, text=btn_text, style="Action.TButton", command=self._on_save)
        btn_save.pack(side="right", padx=5)
        attach_tooltip(btn_save, "Guardar sección")

        # If editing, populate files and tables
        if self.original_section_name:
            self._populate_initial_data()
        else:
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
        for path in dict.fromkeys(self.valid_files):
            if path not in self.code_file_paths:
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

    def _get_available_tables(self):
        """Gets list of table names from the database view if connected."""
        try:
            db_view = self.controller.app.layout.database_view
            if db_view and db_view.connection:
                return list(db_view.table_vars.keys())
        except Exception as e:
            print(f"SectionPopup: Could not get tables: {e}")
        return []

    def _populate_initial_data(self):
        """Populate text area with existing files and tables when editing."""
        all_files = self.controller.project_manager.get_files()

        # Also include non-code files in the reverse map
        try:
            non_code_files = self.controller.project_manager.get_non_code_files()
            code_paths = {f['path'] for f in all_files}
            for nf in non_code_files:
                if nf['path'] not in code_paths:
                    all_files = all_files + [{'path': nf['path'], 'rel_path': nf['rel_path'], 'content': ''}]
        except Exception:
            pass

        abs_to_rel = {f['path']: f['rel_path'] for f in all_files}

        
        lines = []
        
        # Add file relative paths
        if self.initial_files_data:
            for abs_path in self.initial_files_data:
                if abs_path in abs_to_rel:
                    lines.append(abs_to_rel[abs_path])
                else:
                    lines.append(os.path.basename(abs_path))
        
        # Add table names (prefixed with 🗄️ to visually distinguish them in input)
        if self.initial_tables_data:
            for table_name in self.initial_tables_data:
                lines.append(table_name)
        
        self.txt_relative.insert("1.0", "\n".join(lines))
        # Trigger update
        self._on_text_change()

    def _on_text_change(self, event=None):
        """Resolves paths and table names in real-time."""
        content = self.txt_relative.get("1.0", "end-1c")
        lines = content.split('\n')
        
        resolved_lines = []
        self.valid_files = []
        self.valid_tables = []
        
        # Get all available files: code files + non-code files
        all_files = self.controller.project_manager.get_files()

        # Merge non-code files (they don't have 'content', use '' as fallback)
        try:
            non_code_files = self.controller.project_manager.get_non_code_files()
            # Convert to same dict format as code files (without content)
            code_paths = {f['path'] for f in all_files}
            for nf in non_code_files:
                if nf['path'] not in code_paths:
                    all_files = all_files + [{'path': nf['path'], 'rel_path': nf['rel_path'], 'content': ''}]
        except Exception as e:
            print(f"SectionPopup: Could not get non-code files: {e}")

        # Create lookup maps for files
        file_map = {f['rel_path']: f['path'] for f in all_files}

        
        filename_map = {}
        for rel_path in file_map.keys():
            fname = os.path.basename(rel_path)
            if fname not in filename_map:
                filename_map[fname] = []
            filename_map[fname].append(rel_path)
            
        all_rel_paths = list(file_map.keys())
        all_filenames = list(filename_map.keys())
        
        # Get available table names from DB connection
        available_tables = self._get_available_tables()
        
        for line in lines:
            query = line.strip()
            if not query:
                resolved_lines.append("")
                continue
            
            # --- PRIORITY 1: Exact Table Match (Case-insensitive) ---
            # We check tables FIRST to avoid files "stealing" exact table names
            found_table = None
            if available_tables:
                for t in available_tables:
                    if query.lower() == t.lower():
                        found_table = t
                        break
            
            if found_table:
                resolved_lines.append(f"🗄️ {found_table}")
                self.valid_tables.append(found_table)
                continue

            # --- PRIORITY 2: Exact File Match ---
            found_rel_path = None
            
            # Exact Relative Path
            if query in file_map:
                found_rel_path = query
            
            # Exact Filename
            elif query in filename_map:
                candidates = filename_map[query]
                found_rel_path = sorted(candidates, key=len)[0]
            
            if found_rel_path:
                abs_path = file_map[found_rel_path]
                parent_dir = os.path.basename(os.path.dirname(found_rel_path))
                filename = os.path.basename(found_rel_path)
                display_path = f"{parent_dir}/{filename}" if parent_dir else filename
                resolved_lines.append(f"📄 {display_path}") 
                self.valid_files.append(abs_path)
                continue

            # --- PRIORITY 3: Fuzzy File Match ---
            # Try fuzzy filename matches first
            matches_fn = difflib.get_close_matches(query, all_filenames, n=1, cutoff=0.5)
            if matches_fn:
                best_fn = matches_fn[0]
                candidates = filename_map[best_fn]
                found_rel_path = sorted(candidates, key=len)[0]
            else:
                # Fallback to fuzzy full path
                matches_rp = difflib.get_close_matches(query, all_rel_paths, n=1, cutoff=0.3)
                if matches_rp:
                    found_rel_path = matches_rp[0]
            
            if found_rel_path:
                abs_path = file_map[found_rel_path]
                parent_dir = os.path.basename(os.path.dirname(found_rel_path))
                filename = os.path.basename(found_rel_path)
                display_path = f"{parent_dir}/{filename}" if parent_dir else filename
                resolved_lines.append(f"📄 {display_path}") 
                self.valid_files.append(abs_path)
                continue

            # --- PRIORITY 4: Fuzzy Table Match (Strict) ---
            if available_tables:
                # Cutoff 0.8 as requested for "almost perfect" match
                matches_t = difflib.get_close_matches(query, available_tables, n=1, cutoff=0.8)
                if matches_t:
                    found_table = matches_t[0]
                    resolved_lines.append(f"🗄️ {found_table}")
                    self.valid_tables.append(found_table)
                    continue
            
            # --- Not found ---
            resolved_lines.append("--- No encontrado ---")
        
        # Update Right Pane
        self.txt_absolute.config(state="normal")
        self.txt_absolute.delete("1.0", "end")
        self.txt_absolute.insert("1.0", "\n".join(resolved_lines))
        self.txt_absolute.config(state="disabled")
        self._update_size_indicator()

    def _on_save(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Error", "Debes escribir un nombre para la sección.")
            return
            
        if not self.valid_files and not self.valid_tables:
             pass  # Allow empty sections

        try:
            if self.original_section_name:
                self.controller.section_manager.update_section(
                    self.original_section_name, name, 
                    self.valid_files, self.valid_tables
                )
            else:
                self.controller.section_manager.create_section(
                    name, self.valid_files, self.valid_tables
                )
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
