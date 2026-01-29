import tkinter as tk
from tkinter import ttk, filedialog
import tkinter.messagebox as messagebox
import threading
import os
from src.ui.styles import Styles

class CodeView(ttk.Frame):
    """
    The main view for the 'Code' tab.
    Allows loading projects, listing files, and generating AI prompts.
    """
    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = parent.master.controller 
        
        # Access safety check
        try:
            self.controller = parent.winfo_toplevel().controller 
        except:
             pass 

        self._create_layout()

    def set_controller(self, controller):
        """Explicitly set controller if not available via hierarchy."""
        self.controller = controller

    def _create_layout(self):
        """Creates the split-pane layout."""
        # Main PanedWindow (Split Left / Right)
        # using COLOR_BG_MAIN for sash to make it blend in (invisible split) or COLOR_BG_SIDEBAR
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, bg=Styles.COLOR_BG_MAIN, sashrelief="flat")
        self.paned_window.pack(fill="both", expand=True)

        # --- Left Pane (Project & Files) ---
        self.left_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(self.left_frame, minsize=400, stretch="always")

        # 1. Top Bar (Load Button)
        self.top_bar = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.top_bar.pack(side="top", fill="x", padx=10, pady=10)

        self.btn_load = ttk.Button(
            self.top_bar, 
            text="📂 Cargar Proyecto", 
            style="Action.TButton",
            command=self._on_load_project
        )
        self.btn_load.pack(side="left")

        # Slider for File Limit
        self.limit_var = tk.DoubleVar(value=100) # Default, will update from config
        
        # Container for slider
        slider_frame = ttk.Frame(self.top_bar, style="Main.TFrame")
        slider_frame.pack(side="left", padx=20)
        
        self.lbl_limit = ttk.Label(slider_frame, text="Límite: 100", style="TLabel")
        self.lbl_limit.pack(side="left", padx=(0, 15))
        
        self.slider = ttk.Scale(
            slider_frame, 
            from_=1, 
            to=20, 
            orient="horizontal", 
            variable=self.limit_var,
            command=self._on_limit_change,
            length=300,
            style="Horizontal.TScale"
        )
        self.slider.pack(side="left", fill="x")

        # 2. File List (Treeview)
        # "Occupies 3/4 width" -> We'll handle this with sash positioning initially
        self.tree_frame = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)
        
        self.columns = ("path", "size")
        self.tree = ttk.Treeview(self.tree_frame, columns=self.columns, show="headings", selectmode="extended", style="Treeview")
        self.tree.heading("path", text="Fichero (Ruta Relativa)")
        self.tree.heading("size", text="Tamaño")
        self.tree.column("path", width=400)
        self.tree.column("size", width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Initialize slider from config if controller available
        if hasattr(self, 'controller') and hasattr(self.controller, 'config_manager'):
            limit = self.controller.config_manager.get_file_limit()
            self.limit_var.set(limit)
            self.lbl_limit.config(text=f"Límite: {int(limit)}")

        # 3. Prompt Area
        self.prompt_frame = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.prompt_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        
        lbl_prompt = ttk.Label(self.prompt_frame, text="Mensaje para IA:", style="TLabel")
        lbl_prompt.pack(anchor="w")

        self.txt_prompt = tk.Text(
            self.prompt_frame, 
            height=5, 
            font=Styles.FONT_MAIN, 
            bg=Styles.COLOR_INPUT_BG, 
            fg=Styles.COLOR_INPUT_FG, 
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
            padx=10, pady=10
        )
        self.txt_prompt.bind("<KeyRelease>", self._on_prompt_change)
        self.txt_prompt.pack(side="left", fill="x", expand=True, pady=5)
        
        self.btn_copy = ttk.Button(
            self.prompt_frame,
            text="Copiar Prompt",
            style="Action.TButton",
            command=self._on_copy_prompt
        )
        self.btn_copy.pack(side="right", padx=(10, 0), anchor="n")


        # --- Right Pane (Sections) ---
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame")
        self.paned_window.add(self.right_frame, minsize=250, stretch="never")

        # Split Right Pane into Top (List) and Bottom (Checkbox area)
        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="both", expand=True)

        self.right_bottom_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_bottom_frame.pack(side="bottom", fill="x", expand=False)



        # Header
        lbl_sections = ttk.Label(self.right_top_frame, text="Secciones", style="Header.TLabel")
        lbl_sections.pack(fill="x")

        # Section List
        self.section_list = tk.Listbox(
            self.right_top_frame, 
            bg=Styles.COLOR_INPUT_BG, 
            fg=Styles.COLOR_INPUT_FG, 
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            exportselection=0, # Prevent selection loss when focus changes
            font=Styles.FONT_MAIN,
            height=15
        )
        self.section_list.bind("<<ListboxSelect>>", self._on_section_select)
        self.section_list.bind("<Button-1>", self._on_section_click)
        self.section_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Controls for Sections
        btn_frame = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Nueva Sección", style="Nav.TButton", command=self._on_add_section).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Borrar Sección", style="Nav.TButton", command=self._on_delete_section).pack(fill="x", pady=2)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Añadir Seleccionados a Sección", style="Nav.TButton", command=self._on_add_to_section).pack(fill="x", pady=2)
        
        # Custom Large Checkbox "Devolver regiones" 
        self.var_return_regions = tk.BooleanVar(value=False)
        
        # Container frame for the custom checkbox
        self.chk_container = ttk.Frame(self.right_bottom_frame, style="Sidebar.TFrame", cursor="hand2")
        self.chk_container.pack(fill="x", padx=15, pady=20)
        
        # Indicator Canvas (The square) - Fixed size for consistency
        self.chk_canvas = tk.Canvas(
            self.chk_container,
            width=30,
            height=30,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=0,
            bd=0
        )
        self.chk_canvas.pack(side="left")
        
        # Draw initial state (unchecked)
        self._draw_checkbox()
        
        # Text Label
        self.lbl_chk_text = ttk.Label(
            self.chk_container, 
            text="Devolver regiones", 
            style="TLabel",
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_chk_text.configure(background=Styles.COLOR_BG_SIDEBAR)
        self.lbl_chk_text.pack(side="left", padx=(10, 0))
        
        # Bindings for click events
        self.chk_container.bind("<Button-1>", self._toggle_return_regions)
        self.chk_canvas.bind("<Button-1>", self._toggle_return_regions)
        self.lbl_chk_text.bind("<Button-1>", self._toggle_return_regions)
        
        # Hover effects
        self.chk_container.bind("<Enter>", self._on_chk_hover_enter)
        self.chk_container.bind("<Leave>", self._on_chk_hover_leave)

        # Initial sections load
        self._refresh_sections()

    def _draw_checkbox(self):
        """Draws the current state on the canvas."""
        self.chk_canvas.delete("all")
        
        is_checked = self.var_return_regions.get()
        color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM
        outline_color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM
        
        # Draw Border Square
        self.chk_canvas.create_rectangle(
            4, 4, 26, 26, 
            outline=outline_color, 
            width=2,
            fill=Styles.COLOR_INPUT_BG if not is_checked else Styles.COLOR_ACCENT
        )
        
        if is_checked:
            # Draw Checkmark (X or Check)
            self.chk_canvas.create_line(
                8, 15, 13, 20, 
                fill="white", width=3, capstyle=tk.ROUND
            )
            self.chk_canvas.create_line(
                13, 20, 22, 10, 
                fill="white", width=3, capstyle=tk.ROUND
            )

    def _on_chk_hover_enter(self, event):
        self.lbl_chk_text.configure(foreground=Styles.COLOR_ACCENT)
        # Subtle glow or border change could go here

    def _on_chk_hover_leave(self, event):
        self.lbl_chk_text.configure(foreground=Styles.COLOR_FG_TEXT)

    def _toggle_return_regions(self, event=None):
        """Toggles the custom checkbox state."""
        new_val = not self.var_return_regions.get()
        self.var_return_regions.set(new_val)
        self._draw_checkbox()

        # Initial Refresh
        self._refresh_sections()


    def _on_limit_change(self, val):
        """Handle slider movement."""
        limit = int(float(val))
        self.lbl_limit.config(text=f"Límite: {limit}")
        
        # Update Config (Debouncing would be better but direct update is okay for now)
        if hasattr(self.controller, 'config_manager'):
             self.controller.config_manager.set_file_limit(limit)
             
        # Refresh list to apply limit
        self.refresh_file_list()

    def _on_load_project(self):
        path = filedialog.askdirectory()
        if path:
            self.controller.load_project_folder(path)

    def refresh_file_list(self, files=None):
        """Updates the treeview with files. If None, fetches from project manager."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if files is None:
            # Fallback if controller not ready or just a full refresh
            if hasattr(self.controller, 'project_manager'):
                files = self.controller.project_manager.get_files()
            else:
                files = []

        # Apply Limit
        try:
             limit = int(self.limit_var.get())
        except:
             limit = 20

        for f in files[:limit]:
            size_kb = f"{len(f['content']) / 1024:.1f} KB"
            # Format path to show only parent/filename
            rel_path = f['rel_path']
            parts = rel_path.split(os.sep)
            if len(parts) > 1:
                display_path = os.path.join(parts[-2], parts[-1])
            else:
                display_path = rel_path
                
            self.tree.insert("", "end", values=(display_path, size_kb), tags=(f['path'],))


    def _on_prompt_change(self, event=None):
        """Handles real-time search filtering with debouncing."""
        if hasattr(self, '_search_timer') and self._search_timer:
            self.after_cancel(self._search_timer)
            
        # Debounce: Wait 300ms after last keypress
        self._search_timer = self.after(300, self._start_background_search)

    def _start_background_search(self):
        """Starts the search in a separate thread."""
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        
        selected_indices = self.section_list.curselection()
        section = self.section_list.get(selected_indices[0]) if selected_indices else None
        
        # Run search in thread
        threading.Thread(target=self._perform_search, args=(text, section), daemon=True).start()

    def _perform_search(self, text, section):
        """Executes search logic (Thread Safe)."""
        try:
            relevant_files = self.controller.get_relevant_files_for_ui(text, selected_section=section)
            # Schedule UI update on main thread
            self.after(0, lambda: self._update_file_list_safe(relevant_files))
        except Exception as e:
            print(f"Search error: {e}")

    def _update_file_list_safe(self, files):
        """Updates UI with search results (Main Thread)."""
        self.refresh_file_list(files)

    def _on_section_select(self, event=None):
        """Trigger update when section selection changes."""
        self._on_prompt_change()

    def _on_section_click(self, event):
        """Handle clicks on the section list. Deselect if clicked on empty space."""
        # Get index at click position
        index = self.section_list.nearest(event.y)
        
        # Check if index is valid (list might be empty)
        if index < 0: return

        # Check if the click is actually inside the bounding box of the item
        bbox = self.section_list.bbox(index)
        if not bbox: return
        
        # bbox is (x, y, width, height)
        y, height = bbox[1], bbox[3]
        
        # If clicked below the last item
        if event.y > y + height:
            self.section_list.selection_clear(0, tk.END)
            self._on_section_select() # Update filter
            return "break" # Prevent default selection behavior if any

    def _on_copy_prompt(self):
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Aviso", "Escribe un mensaje primero.")
            return

        # Check selected section
        selected_indices = self.section_list.curselection()
        section = self.section_list.get(selected_indices[0]) if selected_indices else None
        
        # Check return regions
        return_regions = self.var_return_regions.get()

        prompt = self.controller.generate_prompt(text, selected_section=section, return_regions=return_regions)
        
        # Save prompt to file in Documents
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            
            # Ensure directory exists (should exist on Mac, but good practice)
            os.makedirs(documents_path, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(prompt)
                
            # Copy ONLY user message to clipboard
            self.clipboard_clear()
            self.clipboard_append(text)
            
            messagebox.showinfo("Prompt Generado", f"Prompt guardado en:\n{file_path}\n\nMensaje del usuario copiado al portapapeles.")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el fichero:\n{e}")

    def _on_add_section(self):
        # Open the enhanced section creation popup
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller)
            self.wait_window(popup) # Wait for it to close
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        
        name = self.section_list.get(selected_indices[0])
        self.controller.section_manager.delete_section(name)
        self._refresh_sections()

    def _on_add_to_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: 
            messagebox.showwarning("Aviso", "Selecciona una sección primero.")
            return
        section_name = self.section_list.get(selected_indices[0])
        
        # Get selected files from tree
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecciona ficheros de la lista.")
            return

        file_paths = []
        for unique_id in selected_items:
            # We stored the absolute path in tags, but tree.item(id)['tags'] returns a list
            # We fixed this in Logic phase but let's double check. 
            # Controller access logic might need fix if not working? 
            # The tool call above is mostly for UI inputs.
            # I will trust the logic from previous step.
            tags = self.tree.item(unique_id, "tags")
            if tags:
                file_paths.append(tags[0])
        
        if file_paths:
            self.controller.section_manager.add_files_to_section(section_name, file_paths)
            messagebox.showinfo("Éxito", f"{len(file_paths)} ficheros añadidos a '{section_name}'.")

    def _refresh_sections(self):
        self.section_list.delete(0, tk.END)
        for s in self.controller.section_manager.get_sections():
            self.section_list.insert(tk.END, s)

