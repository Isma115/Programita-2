import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
from src.ui.styles import Styles

class SectionCreationPopup(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Crear Nueva Sección")
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
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Header
        header = ttk.Frame(self, style="Main.TFrame")
        header.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(header, text="Nombre de la Sección:", style="TLabel").pack(side="left")
        self.entry_name = ttk.Entry(header, width=30)
        self.entry_name.pack(side="left", padx=5)
        
        # Split View
        split_frame = ttk.Frame(self, style="Main.TFrame")
        split_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Left Pane: Relative Paths Input
        left_pane = ttk.LabelFrame(split_frame, text="Archivos (Rutas relativas o nombres)", style="Main.TFrame")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.txt_relative = tk.Text(
            left_pane,
            wrap="none",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            font=Styles.FONT_CODE,
            borderwidth=0,
            width=35, # Make list narrower to fit better
            padx=10, pady=10
        )
        self.txt_relative.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_relative.bind("<KeyRelease>", self._on_text_change)
        
        # Right Pane: Resolved Absolute Paths (Read Only)
        right_pane = ttk.LabelFrame(split_frame, text="Archivos Detectados", style="TLabelframe")
        right_pane.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.txt_absolute = tk.Text(
            right_pane,
            wrap="none",
            bg=Styles.COLOR_INPUT_BG, # Same background for consistency
            fg=Styles.COLOR_DIM,      # Dim color to indicate output
            state="disabled",
            font=Styles.FONT_CODE,
            borderwidth=0,
            width=35, # Make list narrower to fit better
            padx=10, pady=10
        )
        self.txt_absolute.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Footer
        footer = ttk.Frame(self, style="Main.TFrame")
        footer.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(footer, text="Cancelar", style="Secondary.TButton", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(footer, text="Crear Sección", style="Action.TButton", command=self._on_save).pack(side="right", padx=5)
        
        # Sync scrolling
        self._sync_scrolling()

    def _sync_scrolling(self):
        # We can implement basic sync scroll if needed, but for MVP standard scrolling is fine.
        # Let's keep it simple first.
        pass

    def _on_text_change(self, event=None):
        """Resolves paths in real-time."""
        import difflib
        import os
        
        content = self.txt_relative.get("1.0", "end-1c")
        lines = content.split('\n')
        
        resolved_lines = []
        self.valid_files = [] # Store valid absolute paths
        
        # Get all available files once
        all_files = self.controller.project_manager.get_files()
        
        # Create lookup maps
        # 1. Full Relative Path -> Absolute Path
        file_map = {f['rel_path']: f['path'] for f in all_files}
        
        # 2. Filename -> List of Relative Paths (handle duplicates)
        filename_map = {}
        for rel_path in file_map.keys():
            fname = os.path.basename(rel_path)
            if fname not in filename_map:
                filename_map[fname] = []
            filename_map[fname].append(rel_path)
            
        all_rel_paths = list(file_map.keys())
        all_filenames = list(filename_map.keys())
        
        for line in lines:
            query = line.strip()
            if not query:
                resolved_lines.append("")
                continue
            
            found_rel_path = None
            
            # --- Tier 1: Exact Relative Path ---
            if query in file_map:
                found_rel_path = query
            
            # --- Tier 2: Exact Filename ---
            elif query in filename_map:
                # If multiple files have the same name, pick the shortest path (shallowest)
                candidates = filename_map[query]
                found_rel_path = sorted(candidates, key=len)[0]
            
            else:
                # --- Tier 3: Fuzzy Filename ---
                # Prioritize matching the filename itself
                matches_fn = difflib.get_close_matches(query, all_filenames, n=1, cutoff=0.5)
                if matches_fn:
                    best_fn = matches_fn[0]
                    candidates = filename_map[best_fn]
                    found_rel_path = sorted(candidates, key=len)[0]
                else:
                    # --- Tier 4: Fuzzy Full Path (Fallback) ---
                    matches_rp = difflib.get_close_matches(query, all_rel_paths, n=1, cutoff=0.3)
                    if matches_rp:
                        found_rel_path = matches_rp[0]

            if found_rel_path:
                abs_path = file_map[found_rel_path]
                resolved_lines.append(f"{found_rel_path}") 
                self.valid_files.append(abs_path)
            else:
                resolved_lines.append("--- No encontrado ---")
        
        # Update Right Pane
        self.txt_absolute.config(state="normal")
        self.txt_absolute.delete("1.0", "end")
        self.txt_absolute.insert("1.0", "\n".join(resolved_lines))
        self.txt_absolute.config(state="disabled")

    def _on_save(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Error", "Debes escribir un nombre para la sección.")
            return
            
        if not self.valid_files:
             # It's allowed to create empty section? User asked for "create sections ... writing list of files".
             # Let's warn but allow if that was the intent, but usually we want files.
             confirm = messagebox.askyesno("Confirmar", "No se han encontrado ficheros válidos. ¿Crear sección vacía?")
             if not confirm:
                 return

        try:
            self.controller.section_manager.create_section(name, self.valid_files)
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

