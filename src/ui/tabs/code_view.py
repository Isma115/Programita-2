import tkinter as tk
from tkinter import ttk, filedialog
import tkinter.messagebox as messagebox
import threading
import os
import webbrowser
from src.ui.styles import Styles

class CodeView(ttk.Frame):
    """
    The main view for the 'Code' tab.
    Allows loading projects, listing files, and generating AI prompts.
    """
    
    
    # AI List sorted by estimated coding/reasoning quality (Mixed Western & Chinese)
    AI_MODELS = [
        "DeepSeek (R1/V3)", 
        "Claude (Sonnet 3.5)", 
        "ChatGPT (o1/4o)", 
        "Gemini (1.5 Pro)", 
        "Qwen (Max/2.5)", 
        "Kimi (Moonshot)", 
        "GLM (Zhipu)", 
        "Mistral (Le Chat)",
        "Perplexity",
        "Grok"
    ]

    # Combobox values: Auto mode first, then individual models
    AI_ORDER = ["⚡ Automático", "🤖 Agente"] + AI_MODELS

    # Max consecutive uses of the same AI before rotating
    MAX_CONSECUTIVE = 3

    AI_URLS = {
        "DeepSeek (R1/V3)": "https://chat.deepseek.com",
        "Claude (Sonnet 3.5)": "https://claude.ai",
        "ChatGPT (o1/4o)": "https://chat.openai.com",
        "Gemini (1.5 Pro)": "https://gemini.google.com",
        "Qwen (Max/2.5)": "https://tongyi.aliyun.com",
        "Kimi (Moonshot)": "https://kimi.moonshot.cn",
        "GLM (Zhipu)": "https://chatglm.cn",
        "Mistral (Le Chat)": "https://chat.mistral.ai",
        "Perplexity": "https://www.perplexity.ai",
        "Grok": "https://x.com/i/grok"
    }

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = parent.master.controller 
        
        # In-memory AI usage history (resets on restart)
        self._ai_usage_history = []
        
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

        # === Project Switcher Bar (compact, above everything) ===
        self.project_bar = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.project_bar.pack(side="top", fill="x", padx=10, pady=(6, 2))

        self.btn_prev_project = ttk.Button(
            self.project_bar,
            text="◀",
            style="Nav.TButton",
            width=1,
            command=lambda: self.controller.prev_project()
        )
        self.btn_prev_project.pack(side="left")

        self.lbl_project_name = ttk.Label(
            self.project_bar,
            text="Sin proyecto",
            style="TLabel",
            anchor="center",
            font=("Segoe UI", 13)
        )
        self.lbl_project_name.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_next_project = ttk.Button(
            self.project_bar,
            text="▶",
            style="Nav.TButton",
            width=1,
            command=lambda: self.controller.next_project()
        )
        self.btn_next_project.pack(side="left")

        self.btn_add_project = ttk.Button(
            self.project_bar,
            text="＋",
            style="Action.TButton",
            width=1,
            command=self._on_add_project
        )
        self.btn_add_project.pack(side="left", padx=(6, 0))

        # Initialize project label
        self._update_project_label()

        # 1. Top Bar (Load Button)
        self.top_bar = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.top_bar.pack(side="top", fill="x", padx=10, pady=(2, 8))



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
            length=200,
            style="Horizontal.TScale"
        )
        self.slider.pack(side="left", fill="x")

        # AI Selector
        self.ai_var = tk.StringVar()
        self.cmb_ai = ttk.Combobox(
            slider_frame, 
            textvariable=self.ai_var, 
            values=self.AI_ORDER,
            state="readonly",
            width=20,
            style="TCombobox"
        )
        self.cmb_ai.current(0) # Default to first item (Best Quality)
        self.cmb_ai.pack(side="left", padx=(20, 0))

        # 2. File List (Treeview)
        # "Occupies 3/4 width" -> We'll handle this with sash positioning initially
        self.tree_frame = ttk.Frame(self.left_frame, style="Main.TFrame")
        # Pack this LATER, after prompt_frame is packed to the bottom
        # self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)
        
        self.columns = ("path", "size")
        self.tree = ttk.Treeview(self.tree_frame, columns=self.columns, show="", selectmode="extended", style="Treeview")
        # Headings removed as requested
        # self.tree.heading("path", text="Fichero (Ruta Relativa)")
        # self.tree.heading("size", text="Tamaño")
        self.tree.column("path", width=400)
        self.tree.column("size", width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Binding para doble click
        self.tree.bind("<Double-1>", self._on_file_double_click)
        
        # Context Menu for Files
        self.file_context_menu = tk.Menu(self, tearoff=0)
        self.file_context_menu.add_command(label="📋 Copiar al Portapapeles", command=self._on_file_copy)
        self.file_context_menu.add_command(label="➕ Concatenar al Portapapeles", command=self._on_file_concat_clipboard)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="💾 Guardar en codigo.txt", command=self._on_file_save_txt)
        self.file_context_menu.add_command(label="📥 Concatenar en codigo.txt", command=self._on_file_concat_txt)

        # Bind Right Click for Files
        self.tree.bind("<Button-2>", self._show_file_context_menu)
        self.tree.bind("<Button-3>", self._show_file_context_menu)
        self.tree.bind("<Control-Button-1>", self._show_file_context_menu)
        
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
            height=8, 
            font=Styles.FONT_MAIN, 
            bg=Styles.COLOR_INPUT_BG, 
            fg=Styles.COLOR_INPUT_FG, 
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
            padx=10, pady=10
        )
        self.txt_prompt.bind("<KeyRelease>", self._on_prompt_change)
        # Bind Ctrl+Enter (and Command+Enter on Mac) to copy prompt
        self.txt_prompt.bind("<Control-Return>", self._on_copy_prompt)
        self.txt_prompt.bind("<Command-Return>", self._on_copy_prompt)
        self.txt_prompt.pack(side="left", fill="x", expand=True, pady=5)
        
        self.btn_copy = ttk.Button(
            self.prompt_frame,
            text="Copiar Prompt",
            style="Action.TButton",
            command=self._on_copy_prompt
        )
        self.btn_copy.pack(side="right", padx=(10, 0), anchor="n")

        # NOW pack the tree frame to fill the REMAINING space
        self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)


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
        
        button_width = 25 # Approximate characters

        ttk.Button(btn_frame, text="Nueva Sección", style="Nav.TButton", command=self._on_add_section).pack(fill="x", pady=2)

        # Context Menu for Sections
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Editar", command=self._on_edit_section)
        self.context_menu.add_command(label="Eliminar", command=self._on_delete_section)

        # Bind Right Click (Mac & Windows/Linux)
        self.section_list.bind("<Button-2>", self._show_context_menu) # Mac 2-finger click often maps to Button-2 or Button-3 depending on TK setup
        self.section_list.bind("<Button-3>", self._show_context_menu)
        self.section_list.bind("<Control-Button-1>", self._show_context_menu) # Mac Ctrl+Click

        
        # Custom Large Checkbox "Devolver regiones" 
        val_regions = False
        if hasattr(self.controller, 'config_manager'):
            val_regions = self.controller.config_manager.get_return_regions()
            
        self.var_return_regions = tk.BooleanVar(value=val_regions)
        
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

    def _on_ai_selected(self, event=None):
        pass

    def _get_auto_ai(self):
        """
        Selects the best available AI automatically.
        If the same AI has been used MAX_CONSECUTIVE times in a row,
        it moves to the next one in the quality-sorted list.
        """
        for ai in self.AI_MODELS:
            # Count consecutive recent uses of this AI
            consecutive = 0
            for past_ai in reversed(self._ai_usage_history):
                if past_ai == ai:
                    consecutive += 1
                else:
                    break  # Stop counting at first different AI
            
            if consecutive < self.MAX_CONSECUTIVE:
                return ai
        
        # Fallback: all AIs exhausted (very unlikely), reset and start over
        self._ai_usage_history.clear()
        return self.AI_MODELS[0]

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

        # Update Config
        if hasattr(self.controller, 'config_manager'):
             self.controller.config_manager.set_return_regions(new_val)

        # Initial Refresh
        self._refresh_sections()


    def _on_limit_change(self, val):
        """Handle slider movement."""
        limit = int(float(val))
        self.lbl_limit.config(text=f"Límite: {limit}")
        
        # Update Config (Debouncing would be better but direct update is okay for now)
        if hasattr(self.controller, 'config_manager'):
             self.controller.config_manager.set_file_limit(limit)
             
        # Refresh list to apply limit (re-run search so filter is preserved)
        self._on_prompt_change()

    def _on_load_project(self):
        path = filedialog.askdirectory()
        if path:
            self.controller.add_project_directory(path)

    def _on_add_project(self):
        """Opens folder dialog and adds a new project directory."""
        path = filedialog.askdirectory()
        if path:
            self.controller.add_project_directory(path)

    def _update_project_label(self):
        """Updates the project name label and arrow button states."""
        dirs = self.controller.get_project_directories()
        if not dirs:
            self.lbl_project_name.config(text="Sin proyecto")
            return
        idx = self.controller.get_current_project_index()
        idx = idx % len(dirs) if dirs else 0
        project_name = os.path.basename(dirs[idx])
        self.lbl_project_name.config(text=f"📁 {project_name}  ({idx + 1}/{len(dirs)})")

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
        self.update_idletasks()

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

    def _on_copy_prompt(self, event=None):
        # If triggered by event, prevent default behavior (newline)
        if event:
            pass # Use "break" if needed, but Text widget default binding might be separate. 
                 # Usually return "break" prevents further processing.
        
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Aviso", "Escribe un mensaje primero.")
            return

        # Check selected section
        selected_indices = self.section_list.curselection()
        section = self.section_list.get(selected_indices[0]) if selected_indices else None
        
        # Check return regions
        return_regions = self.var_return_regions.get()

        # Get file limit from slider
        try:
            file_limit = int(self.limit_var.get())
        except:
            file_limit = 10

        prompt = self.controller.generate_prompt(text, selected_section=section, return_regions=return_regions, file_limit=file_limit)
        
        # Save prompt to file in Documents
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            
            # Ensure directory exists (should exist on Mac, but good practice)
            os.makedirs(documents_path, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(prompt)
                
            # Resolve AI selection (auto mode or manual)
            selected_ai = self.cmb_ai.get()
            if selected_ai == "⚡ Automático":
                selected_ai = self._get_auto_ai()
            
            if selected_ai == "🤖 Agente":
                # --- Modo Agente: mensaje + instrucciones agente + @fichero refs ---
                file_refs = []
                for item in self.tree.get_children():
                    tags = self.tree.item(item, 'tags')
                    if tags:
                        file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                        filename = os.path.basename(file_path)
                        file_refs.append(f"@{filename}")
                
                clipboard_content = text
                if return_regions:
                    clipboard_content += "\n\nIMPORTANTE: Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
                if file_refs:
                    clipboard_content += "\n\nFicheros que podrían estar relacionados: " + " ".join(file_refs)
                
                self.clipboard_clear()
                self.clipboard_append(clipboard_content)
                print(f"Agente: Prompt copiado con {len(file_refs)} referencias de ficheros")
            else:
                # --- Modo normal: mensaje + instrucciones regiones ---
                clipboard_content = text
                if return_regions:
                    clipboard_content += "\n\nIMPORTANTE: Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
                
                self.clipboard_clear()
                self.clipboard_append(clipboard_content)
                
                # Record usage & open AI URL
                self._ai_usage_history.append(selected_ai)
                
                if selected_ai in self.AI_URLS:
                    url = self.AI_URLS[selected_ai]
                    webbrowser.open_new_tab(url)
                    print(f"AutoAI: Abriendo {selected_ai} (usos recientes: {self._ai_usage_history[-5:]})")

            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el fichero:\n{e}")

    def _show_context_menu(self, event):
        """Shows the context menu on right click."""
        try:
            # Get index at click position
            index = self.section_list.nearest(event.y)
            
            # Check if index is valid
            if index < 0: return

            # Check if the click is actually inside the bounding box of the item
            bbox = self.section_list.bbox(index)
            if not bbox: return
            
            # bbox is (x, y, width, height)
            y_item, height = bbox[1], bbox[3]
            
            # If clicked below the last item
            if event.y > y_item + height:
                return

            # Select the item
            self.section_list.selection_clear(0, tk.END)
            self.section_list.selection_set(index)
            self.section_list.activate(index)
            self._on_section_select() # Update filter

            # Show menu
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                # Make sure to release the grab
                self.context_menu.grab_release()
        except Exception as e:
            print(f"Error showing context menu: {e}")

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

    def _on_edit_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: 
            messagebox.showwarning("Aviso", "Selecciona una sección para editar.")
            return
            
        section_name = self.section_list.get(selected_indices[0])
        files = self.controller.section_manager.get_files_in_section(section_name)
        
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller, section_name=section_name, initial_files=files)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening popup for edit: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        
        name = self.section_list.get(selected_indices[0])
        self.controller.section_manager.delete_section(name)
        self._refresh_sections()

    def _refresh_sections(self):
        self.section_list.delete(0, tk.END)
        for s in self.controller.section_manager.get_sections():
            self.section_list.insert(tk.END, s)

    def _on_file_double_click(self, event):
        """
        Elimina el fichero seleccionado de la lista al hacer doble click.
        No elimina el fichero físico del disco, solo lo remueve de la vista.
        """
        # Obtener el item seleccionado bajo el cursor
        iid = self.tree.identify_row(event.y)
        if iid:
            # Obtener la información del fichero antes de eliminarlo
            tags = self.tree.item(iid, 'tags')
            if tags:
                file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                
                # Obtener el nombre del fichero para mostrarlo en el log
                filename = os.path.basename(file_path)
                
                # Eliminar el item del treeview
                self.tree.delete(iid)
                
                # Log de la acción
                print(f"CodeView: Fichero '{filename}' eliminado de la lista.")

    def _show_file_context_menu(self, event):
        """Shows the context menu on right click for files."""
        # Select item under cursor
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.file_context_menu.tk_popup(event.x_root, event.y_root)
        else:
            self.tree.selection_remove(self.tree.selection())

    def _get_selected_file_content(self):
        """Helper to get content and metadata of selected file in tree."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona un fichero primero.")
            return None
        
        tags = self.tree.item(selected[0], "tags")
        if not tags:
            return None
            
        full_path = tags[0]
        file_data = self.controller.get_file_content_by_path(full_path)
        if file_data:
            # Prepend header
            header = f"--- Archivo: {file_data['rel_path']} ---\n"
            file_data['full_content'] = header + file_data['content']
            return file_data
        return None

    def _on_file_copy(self):
        file_data = self._get_selected_file_content()
        if file_data:
            self.clipboard_clear()
            self.clipboard_append(file_data['full_content'])
            print(f"CodeView: Copied {file_data['rel_path']} to clipboard")

    def _on_file_concat_clipboard(self):
        file_data = self._get_selected_file_content()
        if file_data:
            try:
                current = self.clipboard_get()
                new_content = current + "\n\n" + file_data['full_content']
            except:
                new_content = file_data['full_content']
            
            self.clipboard_clear()
            self.clipboard_append(new_content)
            print(f"CodeView: Concatenated {file_data['rel_path']} to clipboard")

    def _on_file_save_txt(self):
        file_data = self._get_selected_file_content()
        if file_data:
            success, result = self.controller.save_content_to_codigo_txt(file_data['full_content'], append=False)
            if success:
                print(f"CodeView: Saved {file_data['rel_path']} to {result}")
            else:
                messagebox.showerror("Error", f"No se pudo guardar: {result}")

    def _on_file_concat_txt(self):
        file_data = self._get_selected_file_content()
        if file_data:
            success, result = self.controller.save_content_to_codigo_txt(file_data['full_content'], append=True)
            if success:
                print(f"CodeView: Concatenated {file_data['rel_path']} to {result}")
            else:
                messagebox.showerror("Error", f"No se pudo guardar: {result}")

