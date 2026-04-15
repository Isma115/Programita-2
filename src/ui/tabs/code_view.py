import tkinter as tk
from tkinter import ttk, filedialog
import tkinter.messagebox as messagebox
import threading
import os
import webbrowser
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip

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
    DEFAULT_SECTIONS_PANEL_WIDTH = 340

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
        
        self._last_selected_section = None
        self._last_selected_subsection = None
        self._visible_section_ids = []

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
        attach_tooltip(self.btn_prev_project, "Proyecto previo")

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
        attach_tooltip(self.btn_next_project, "Proyecto siguiente")

        self.btn_add_project = ttk.Button(
            self.project_bar,
            text="＋",
            style="Action.TButton",
            width=1,
            command=self._on_add_project
        )
        self.btn_add_project.pack(side="left", padx=(6, 0))
        attach_tooltip(self.btn_add_project, "Añadir proyecto")

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
        
        self.lbl_limit = ttk.Label(slider_frame, text="Mín. Ficheros: 100", style="TLabel")
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

        # Extension Filter
        self.ext_var = tk.StringVar(value="")
        
        lbl_ext = ttk.Label(slider_frame, text="Exts:", style="TLabel")
        lbl_ext.pack(side="left", padx=(20, 5))

        self.txt_ext = tk.Entry(
            slider_frame,
            textvariable=self.ext_var,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
            width=15,
            font=Styles.FONT_MAIN
        )
        self.txt_ext.bind("<KeyRelease>", self._on_prompt_change)
        self.txt_ext.pack(side="left", padx=(0, 0))

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
            self.lbl_limit.config(text=f"Mín. Ficheros: {int(limit)}")

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
        attach_tooltip(self.btn_copy, "Copiar prompt")

        # NOW pack the tree frame to fill the REMAINING space
        self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)


        # --- Right Pane (Sections) ---
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame", width=self.DEFAULT_SECTIONS_PANEL_WIDTH)
        self.paned_window.add(self.right_frame, minsize=self.DEFAULT_SECTIONS_PANEL_WIDTH, stretch="never")

        # Split Right Pane into Top (List) and Bottom (Checkbox area)
        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="both", expand=True)

        self.right_bottom_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_bottom_frame.pack(side="bottom", fill="x", expand=False)



        # Header
        lbl_sections = ttk.Label(self.right_top_frame, text="Secciones", style="Header.TLabel")
        lbl_sections.pack(fill="x")

        self.section_search_shell = tk.Frame(
            self.right_top_frame,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.section_search_shell.pack(fill="x", padx=8, pady=(8, 6))

        self.section_search_label = tk.Label(
            self.section_search_shell,
            text="Buscar sección o subsección",
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 13, "bold"),
            anchor="w"
        )
        self.section_search_label.pack(fill="x", padx=10, pady=(8, 0))

        self.section_search_entry = tk.Entry(
            self.section_search_shell,
            font=("Segoe UI", 15),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.section_search_entry.pack(fill="x", padx=10, pady=(6, 10), ipady=8)
        self.section_search_entry.bind("<KeyRelease>", self._on_section_search_change)

        # Section Tree (replaces Listbox for subsection hierarchy support)
        self.section_tree = ttk.Treeview(
            self.right_top_frame,
            show="tree",
            selectmode="browse",
            style="Treeview"
        )
        self.section_tree.column("#0", stretch=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_select)
        self.section_tree.bind("<Button-1>", self._on_section_click)
        
        self.section_tree.tag_configure("section", font=("Segoe UI", 16, "bold"))
        self.section_tree.tag_configure("subsection", font=("Segoe UI", 14))
        
        self.section_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Context menu is built dynamically in _show_context_menu

        # Bind Right Click (Mac & Windows/Linux)
        self.section_tree.bind("<Button-2>", self._show_context_menu)
        self.section_tree.bind("<Button-3>", self._show_context_menu)
        self.section_tree.bind("<Control-Button-1>", self._show_context_menu)

        
        # Custom Large Checkbox "Devolver regiones" 
        val_regions = False
        if hasattr(self.controller, 'config_manager'):
            val_regions = self.controller.config_manager.get_return_regions()
            
        self.var_return_regions = tk.BooleanVar(value=val_regions)
        
        # Container frame for the custom checkbox
        self.chk_container = ttk.Frame(self.right_bottom_frame, style="Sidebar.TFrame", cursor="hand2")
        self.chk_container.pack(fill="x", padx=15, pady=(20, 5))
        
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

        # Custom Large Checkbox "Implementación"
        val_impl = False
        if hasattr(self.controller, 'config_manager'):
            val_impl = self.controller.config_manager.get_implementation_mode()
            
        self.var_implementation_mode = tk.BooleanVar(value=val_impl)
        
        # Container frame for the implementation checkbox
        self.impl_container = ttk.Frame(self.right_bottom_frame, style="Sidebar.TFrame", cursor="hand2")
        self.impl_container.pack(fill="x", padx=15, pady=(5, 20))
        
        # Indicator Canvas
        self.impl_canvas = tk.Canvas(
            self.impl_container,
            width=30,
            height=30,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=0,
            bd=0
        )
        self.impl_canvas.pack(side="left")
        
        # Draw initial state
        self._draw_impl_checkbox()
        
        # Text Label
        self.lbl_impl_text = ttk.Label(
            self.impl_container, 
            text="Implementación", 
            style="TLabel",
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_impl_text.configure(background=Styles.COLOR_BG_SIDEBAR)
        self.lbl_impl_text.pack(side="left", padx=(10, 0))
        
        # Bindings for click events
        self.impl_container.bind("<Button-1>", self._toggle_implementation)
        self.impl_canvas.bind("<Button-1>", self._toggle_implementation)
        self.lbl_impl_text.bind("<Button-1>", self._toggle_implementation)
        
        # Hover effects
        self.impl_container.bind("<Enter>", self._on_impl_hover_enter)
        self.impl_container.bind("<Leave>", self._on_impl_hover_leave)

        # Initial sections load
        self._refresh_sections()
        self.after_idle(self._set_default_sections_panel_width)

    def _set_default_sections_panel_width(self):
        try:
            self.update_idletasks()
            total_width = self.paned_window.winfo_width()
            if total_width <= self.DEFAULT_SECTIONS_PANEL_WIDTH:
                return
            left_width = max(400, total_width - self.DEFAULT_SECTIONS_PANEL_WIDTH)
            self.paned_window.sash_place(0, left_width, 0)
        except Exception:
            pass

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

    def _draw_impl_checkbox(self):
        """Draws the current state on the implementation checkbox canvas."""
        self.impl_canvas.delete("all")
        
        is_checked = self.var_implementation_mode.get()
        color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM
        outline_color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM
        
        # Draw Border Square
        self.impl_canvas.create_rectangle(
            4, 4, 26, 26, 
            outline=outline_color, 
            width=2,
            fill=Styles.COLOR_INPUT_BG if not is_checked else Styles.COLOR_ACCENT
        )
        
        if is_checked:
            # Draw Checkmark
            self.impl_canvas.create_line(
                8, 15, 13, 20, 
                fill="white", width=3, capstyle=tk.ROUND
            )
            self.impl_canvas.create_line(
                13, 20, 22, 10, 
                fill="white", width=3, capstyle=tk.ROUND
            )

    def _on_impl_hover_enter(self, event):
        self.lbl_impl_text.configure(foreground=Styles.COLOR_ACCENT)

    def _on_impl_hover_leave(self, event):
        self.lbl_impl_text.configure(foreground=Styles.COLOR_FG_TEXT)

    def _toggle_implementation(self, event=None):
        """Toggles the implementation mode checkbox state."""
        new_val = not self.var_implementation_mode.get()
        self.var_implementation_mode.set(new_val)
        self._draw_impl_checkbox()

        # Update Config
        if hasattr(self.controller, 'config_manager'):
             self.controller.config_manager.set_implementation_mode(new_val)


    def _on_limit_change(self, val):
        """Handle slider movement."""
        limit = int(float(val))
        self.lbl_limit.config(text=f"Mín. Ficheros: {limit}")
        
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
            if hasattr(self, 'controller') and hasattr(self.controller, 'get_relevant_files_for_ui'):
                text = self.txt_prompt.get("1.0", "end-1c").strip() if hasattr(self, 'txt_prompt') else ""
                section, subsection = self._get_selected_section_info()
                extension = self.ext_var.get() if hasattr(self, 'ext_var') else ""
                min_files = int(self.limit_var.get()) if hasattr(self, 'limit_var') else 0
                files = self.controller.get_relevant_files_for_ui(
                    text,
                    selected_section=section,
                    selected_subsection=subsection,
                    extension=extension,
                    min_files=min_files
                )
            elif hasattr(self.controller, 'project_manager'):
                files = self.controller.project_manager.get_files()
            else:
                files = []

        # We no longer apply a hard limit here; we show all files returned
        # (the padding for minimum files is already handled in find_relevant_files)
        for f in files:
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
        
        section, subsection = self._get_selected_section_info()
        
        extension = self.ext_var.get()
        
        # Run search in thread
        threading.Thread(target=self._perform_search, args=(text, section, subsection, extension), daemon=True).start()

    def _perform_search(self, text, section, subsection=None, extension="Todos"):
        """Executes search logic (Thread Safe)."""
        try:
            relevant_files = self.controller.get_relevant_files_for_ui(
                text, selected_section=section, selected_subsection=subsection, extension=extension
            )
            # Schedule UI update on main thread
            self.after(0, lambda: self._update_file_list_safe(relevant_files))
        except Exception as e:
            print(f"Search error: {e}")

    def _update_file_list_safe(self, files):
        """Updates UI with search results (Main Thread)."""
        self.refresh_file_list(files)
        self.update_idletasks()

    def _get_selected_section_info(self):
        """Returns (section_name, subsection_name_or_None) from current Treeview selection."""
        if not hasattr(self, 'section_tree'):
            return None, None
        selected = self.section_tree.selection()
        if not selected:
            return None, None
        iid = selected[0]
        if iid.startswith("SS:"):
            # Subsection: "SS:ParentName::SubName"
            rest = iid[3:]
            parts = rest.split("::", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        elif iid.startswith("S:"):
            # Parent section: "S:SectionName"
            return iid[2:], None
        return None, None

    def _build_section_iid(self, section_name, subsection_name=None):
        """Builds stable tree item ids for sections and subsections."""
        if not section_name:
            return None
        if subsection_name:
            return f"SS:{section_name}::{subsection_name}"
        return f"S:{section_name}"

    def _on_section_search_change(self, event=None):
        preferred_iid = None
        selected = self.section_tree.selection() if hasattr(self, "section_tree") else ()
        if selected:
            preferred_iid = selected[0]
        elif self._last_selected_section:
            preferred_iid = self._build_section_iid(
                self._last_selected_section,
                self._last_selected_subsection
            )
        self._refresh_sections(preferred_iid=preferred_iid)

    def _on_section_select(self, event=None, force_reload=False):
        """Trigger update when section selection changes."""
        section_name, subsection_name = self._get_selected_section_info()
        
        # Only reload if the selection has actually changed
        if not force_reload and section_name == self._last_selected_section and subsection_name == self._last_selected_subsection:
            return
            
        self._last_selected_section = section_name
        self._last_selected_subsection = subsection_name
        
        # Save selection
        if section_name:
            if hasattr(self.controller, 'config_manager'):
                self.controller.config_manager.set_last_code_section(section_name)
        
        self._on_prompt_change()

    def _on_section_click(self, event):
        """Handle clicks on the section tree. Deselect if clicked on empty space."""
        iid = self.section_tree.identify_row(event.y)
        if not iid or iid == "EMPTY_DESELECT":
            # Clicked on empty space - deselect
            selected = self.section_tree.selection()
            if selected:
                self.section_tree.selection_remove(*selected)
            self._on_section_select(force_reload=True)
            if iid == "EMPTY_DESELECT":
                return "break"

    def _on_copy_prompt(self, event=None):
        # If triggered by event, prevent default behavior (newline)
        if event:
            pass # Use "break" if needed, but Text widget default binding might be separate. 
                 # Usually return "break" prevents further processing.
        
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Aviso", "Escribe un mensaje primero.")
            return

        # Check selected section/subsection
        section, subsection = self._get_selected_section_info()
        
        # Check return regions
        return_regions = self.var_return_regions.get()

        # Check implementation mode
        implementation_mode = self.var_implementation_mode.get()

        # Get file limit from slider
        try:
            min_files = int(self.limit_var.get())
        except:
            min_files = 10

        selected_files_data = self._get_files_for_prompt()
        selected_file_paths = [f['path'] for f in selected_files_data]

        prompt = self.controller.generate_prompt(
            text, 
            selected_section=section,
            selected_subsection=subsection,
            return_regions=return_regions, 
            min_files=min_files, 
            implementation_mode=implementation_mode,
            file_paths=selected_file_paths
        )
        
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
                clipboard_content = self._build_agent_clipboard_prompt(
                    text=text,
                    selected_files=selected_files_data,
                    selected_section=section,
                    selected_subsection=subsection,
                    return_regions=return_regions,
                    implementation_mode=implementation_mode
                )
                
                self.clipboard_clear()
                self.clipboard_append(clipboard_content)
                print(f"Agente: Prompt copiado con {len(selected_files_data)} ficheros priorizados")
            else:
                # --- Modo normal: mensaje + instrucciones regiones ---
                clipboard_content = text
                if return_regions:
                    clipboard_content += "\n\nIMPORTANTE: Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
                if implementation_mode:
                    clipboard_content += "\n\nINSTRUCCIONES DE IMPLEMENTACIÓN:"
                    clipboard_content += "\n1. Realiza TODAS las modificaciones necesarias en el código."
                    clipboard_content += "\n2. Si es necesario crear, mover o eliminar ficheros o carpetas, proporciona los COMANDOS DE CONSOLA exactos a ejecutar."
                    clipboard_content += "\n3. Todos los comandos deben ejecutarse desde la RAÍZ del proyecto."
                
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

    def _get_files_for_prompt(self):
        """Returns selected files or, if none selected, all visible files in the tree."""
        items_to_process = self.tree.selection() or self.tree.get_children()
        if not items_to_process:
            return []

        all_files = self.controller.project_manager.get_files()
        files_map = {f['path']: f for f in all_files}
        selected_files_data = []

        for item in items_to_process:
            tags = self.tree.item(item, 'tags')
            if not tags:
                continue

            file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
            if file_path in files_map:
                selected_files_data.append(files_map[file_path])

        return selected_files_data

    def _build_agent_clipboard_prompt(
        self,
        text,
        selected_files,
        selected_section=None,
        selected_subsection=None,
        return_regions=False,
        implementation_mode=False
    ):
        """Builds a clipboard prompt tailored for coding agents."""
        lines = [
            "Actúa como un agente de código senior, pragmático y orientado a resolver la tarea en una sola pasada siempre que sea posible.",
            "",
            "TAREA:",
            text
        ]

        if selected_section:
            scope = f"Sección prioritaria: {selected_section}"
            if selected_subsection:
                scope += f" > {selected_subsection}"
            lines.extend(["", scope])

        lines.extend([
            "",
            "PRIORIDAD DE LECTURA Y CAMBIO:",
            "1. Lee primero y con prioridad absoluta los ficheros listados abajo.",
            "2. Intenta localizar y resolver la tarea dentro de esos ficheros o en sus dependencias directas inmediatas.",
            "3. Modifica primero esos ficheros si ahí está solución más rápida y correcta.",
            "4. Solo si en esos ficheros no está código relevante o falta contexto imprescindible, busca en otras partes del proyecto.",
            "5. Si necesitas salir de lista prioritaria, sigue imports, llamadas, referencias o archivos vecinos directamente conectados con esos ficheros."
        ])

        if selected_files:
            lines.extend(["", "FICHEROS PRIORITARIOS (léelos antes que nada):"])
            for index, file_data in enumerate(selected_files, start=1):
                lines.append(f"{index}. {file_data['rel_path']}")
        else:
            lines.extend([
                "",
                "FICHEROS PRIORITARIOS:",
                "No hay ficheros seleccionados o visibles. Empieza por localizar el punto mínimo necesario para resolver la tarea."
            ])

        lines.extend([
            "",
            "FORMA DE TRABAJO:",
            "- Prioriza solución rápida, concreta y correcta.",
            "- No hagas exploración amplia si ya encuentras solución en lista prioritaria.",
            "- Antes de modificar, identifica qué archivos vas a tocar.",
            "- Si hay varias opciones, elige la menos invasiva compatible con la tarea."
        ])

        if implementation_mode:
            lines.extend([
                "",
                "INSTRUCCIONES DE IMPLEMENTACIÓN:",
                "1. Realiza TODAS las modificaciones necesarias en el código.",
                "2. Si es necesario crear, mover o eliminar ficheros o carpetas, proporciona los COMANDOS DE CONSOLA exactos a ejecutar.",
                "3. Todos los comandos deben ejecutarse desde la RAÍZ del proyecto."
            ])

        if return_regions:
            lines.extend([
                "",
                "IMPORTANTE:",
                "Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
            ])

        return "\n".join(lines)

    def _show_context_menu(self, event):
        """Shows the appropriate context menu on right click."""
        try:
            iid = self.section_tree.identify_row(event.y)
            
            # Build context menu dynamically based on what was clicked
            menu = tk.Menu(self, tearoff=0)
            
            if not iid:
                # Clicked on empty space - only show "Nueva Sección"
                menu.add_command(label="Nueva Sección", command=self._on_add_section)
            else:
                # Select the item
                self.section_tree.selection_set(iid)
                self._on_section_select()
                
                if iid.startswith("S:"):
                    # Parent section context menu
                    menu.add_command(label="Nueva Sección", command=self._on_add_section)
                    menu.add_command(label="Nueva Subsección", command=self._on_add_subsection)
                    menu.add_separator()
                    menu.add_command(label="Generar Prompt Docs", command=self._on_generate_docs)
                    menu.add_separator()
                    menu.add_command(label="Editar Sección", command=self._on_edit_section)
                    menu.add_command(label="Eliminar Sección", command=self._on_delete_section)
                elif iid.startswith("SS:"):
                    # Subsection context menu
                    menu.add_command(label="Editar Subsección", command=self._on_edit_subsection)
                    menu.add_command(label="Eliminar Subsección", command=self._on_delete_subsection)
                    menu.add_separator()
                    menu.add_command(label="Generar Prompt Docs", command=self._on_generate_docs)
            
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
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
        section_name, _ = self._get_selected_section_info()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección para editar.")
            return
            
        files = self.controller.section_manager.get_files_in_section(section_name)
        tables = self.controller.section_manager.get_tables_in_section(section_name)
        
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller, section_name=section_name, initial_files=files, initial_tables=tables)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening popup for edit: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_section(self):
        section_name, _ = self._get_selected_section_info()
        if not section_name: return
        
        self.controller.section_manager.delete_section(section_name)
        self._refresh_sections()

    def _on_add_subsection(self):
        """Opens popup to create a subsection within the selected parent section."""
        section_name, _ = self._get_selected_section_info()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección padre primero.")
            return
        
        from src.ui.popups.subsection_creation_popup import SubsectionCreationPopup
        try:
            popup = SubsectionCreationPopup(self, self.controller, section_name)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening subsection popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_edit_subsection(self):
        """Opens popup to edit the selected subsection."""
        section_name, sub_name = self._get_selected_section_info()
        if not section_name or not sub_name:
            messagebox.showwarning("Aviso", "Selecciona una subsección para editar.")
            return
        
        files = self.controller.section_manager.get_files_in_subsection(section_name, sub_name)
        
        from src.ui.popups.subsection_creation_popup import SubsectionCreationPopup
        try:
            popup = SubsectionCreationPopup(self, self.controller, section_name, sub_name=sub_name, initial_files=files)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening subsection edit popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_subsection(self):
        """Deletes the selected subsection."""
        section_name, sub_name = self._get_selected_section_info()
        if not section_name or not sub_name: return
        
        self.controller.section_manager.delete_subsection(section_name, sub_name)
        self._refresh_sections()

    def _on_generate_docs(self):
        """Generates a documentation prompt for the selected files or visible files."""
        # 1. Get selected files from Treeview
        selected_items = self.tree.selection()
        
        # Fallback: if no selection, use ALL VISIBLE items in Treeview
        items_to_process = selected_items if selected_items else self.tree.get_children()
        
        if not items_to_process:
            messagebox.showwarning("Aviso", "No hay ficheros visibles o seleccionados para procesar.")
            return

        selected_files_data = []
        all_files = self.controller.project_manager.get_files()
        files_map = {f['path']: f for f in all_files}
        
        for item in items_to_process:
            tags = self.tree.item(item, 'tags')
            if tags:
                file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                if file_path in files_map:
                    selected_files_data.append(files_map[file_path])
        
        if not selected_files_data:
            messagebox.showwarning("Aviso", "No se han encontrado datos para los ficheros procesados.")
            return

        # Instruction text (same as DocView)
        prompt_instruction = (
            "Genera una documentación técnica detallada en formato Markdown para los siguientes ficheros y tablas. "
            "Analiza el código y estructura la documentación de forma clara, incluyendo propósito, parámetros, "
            "retornos y ejemplos si procede."
        )

        try:
            # 2. Build prompt manually for the specific list of files
            prompt = f"Petición del Usuario: {prompt_instruction}\n\nArchivos de Contexto:\n"
            for f in selected_files_data:
                prompt += f"\n--- Archivo: {f['rel_path']} ---\n"
                prompt += f.get('content', '') + "\n"

            # 3. Save to Documents/codigo.txt
            success, result = self.controller.save_content_to_codigo_txt(prompt, append=False)
            
            if success:
                # 4. Copy Instruction to Clipboard
                self.clipboard_clear()
                self.clipboard_append(prompt_instruction)
                
                messagebox.showinfo(
                    "Éxito", 
                    f"Prompt de documentación generado.\n\n"
                    f"✅ Instrucción copiada al portapapeles\n"
                    f"✅ Contenido completo guardado en {result}"
                )
                
                # 5. Open AI URL
                selected_ai = self.cmb_ai.get()
                if selected_ai == "⚡ Automático":
                    selected_ai = self._get_auto_ai()
                
                if selected_ai in self.AI_URLS:
                    url = self.AI_URLS[selected_ai]
                    webbrowser.open_new_tab(url)
            else:
                messagebox.showerror("Error", f"No se pudo guardar: {result}")

        except Exception as e:
            print(f"Error generating docs prompt: {e}")
            messagebox.showerror("Error", f"Error generando prompt: {e}")

    def _refresh_sections(self, preferred_iid=None, force_reload=False):
        # Clear existing tree items
        for item in self.section_tree.get_children():
            self.section_tree.delete(item)

        self._visible_section_ids = []
        query = self.section_search_entry.get().strip().lower() if hasattr(self, "section_search_entry") else ""
        sections = self.controller.section_manager.get_sections()
        for s in sections:
            subsections = self.controller.section_manager.get_subsections(s)

            if query:
                section_matches = query in s.lower()
                matching_subsections = [sub for sub in subsections if query in sub.lower()]
                if not section_matches and not matching_subsections:
                    continue
                visible_subsections = subsections if section_matches else matching_subsections
            else:
                visible_subsections = subsections

            # Insert parent section
            parent_iid = self._build_section_iid(s)
            self.section_tree.insert("", "end", iid=parent_iid, text=f"{s}", open=True, tags=("section",))

            self._visible_section_ids.append(parent_iid)

            # Insert subsections as children
            for sub in visible_subsections:
                sub_iid = self._build_section_iid(s, sub)
                self.section_tree.insert(parent_iid, "end", iid=sub_iid, text=f"{sub}", tags=("subsection",))

        # Insert dummy empty space at the end to allow deselection
        self.section_tree.insert("", "end", iid="EMPTY_DESELECT", text=" ", tags=("subsection",))

        selection_candidates = []
        if preferred_iid:
            selection_candidates.append(preferred_iid)
        if self._last_selected_section:
            selection_candidates.append(
                self._build_section_iid(self._last_selected_section, self._last_selected_subsection)
            )
            selection_candidates.append(self._build_section_iid(self._last_selected_section))

        # Restore last selection
        if hasattr(self.controller, 'config_manager'):
            last_section = self.controller.config_manager.get_last_code_section()
            if last_section:
                selection_candidates.append(self._build_section_iid(last_section))

        if self._visible_section_ids:
            selection_candidates.append(self._visible_section_ids[0])

        target_iid = None
        for iid in selection_candidates:
            if iid and self.section_tree.exists(iid):
                target_iid = iid
                break

        current_selection = self.section_tree.selection()
        if current_selection:
            self.section_tree.selection_remove(*current_selection)

        if target_iid:
            self.section_tree.selection_set(target_iid)
            self.section_tree.see(target_iid)
            parent_iid = self.section_tree.parent(target_iid)
            if parent_iid:
                self.section_tree.item(parent_iid, open=True)
            self._on_section_select(force_reload=force_reload)
        else:
            self._on_section_select(force_reload=True)

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
