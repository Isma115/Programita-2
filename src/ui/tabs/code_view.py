import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
import tkinter.messagebox as messagebox
import threading
import os
import time
import webbrowser
from PIL import Image, ImageTk
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip

class CodeView(ttk.Frame):
    """
    The main view for the 'Code' tab.
    Allows loading projects, listing files, and generating AI prompts.
    """

    AI_CONFIG_FILENAME = "ias_disponibles.txt"
    AUTO_AI_OPTION = "Automático"
    AGENT_AI_OPTION = "Agente"

    # Orden por defecto, usado también como fallback si el fichero no existe o es inválido.
    DEFAULT_AI_SOURCES = [
        ("DeepSeek (R1/V3)", "https://chat.deepseek.com"),
        ("Claude (Sonnet 3.5)", "https://claude.ai"),
        ("ChatGPT (o1/4o)", "https://chat.openai.com"),
        ("Gemini (1.5 Pro)", "https://gemini.google.com"),
        ("Qwen (Max/2.5)", "https://tongyi.aliyun.com"),
        ("Kimi (Moonshot)", "https://kimi.moonshot.cn"),
        ("GLM (Zhipu)", "https://chatglm.cn"),
        ("Mistral (Le Chat)", "https://chat.mistral.ai"),
        ("Perplexity", "https://www.perplexity.ai"),
        ("Grok", "https://x.com/i/grok"),
    ]

    # Max consecutive uses of the same AI before rotating
    MAX_CONSECUTIVE = 3
    DEFAULT_SECTIONS_PANEL_WIDTH = Styles.scale_size(300)
    MIN_LEFT_PANEL_WIDTH = Styles.scale_size(320)
    MIN_SECTIONS_PANEL_WIDTH = Styles.scale_size(260)
    DEFAULT_MAX_FILE_LIMIT = 20
    FILE_ICON_EXTENSION_MAP = {
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "react",
        ".ts": "typescript",
        ".tsx": "react",
        ".py": "python",
        ".pyw": "python",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".groovy": "groovy",
        ".gradle": "gradle",
        ".scala": "scala",
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".hh": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".cs": "csharp",
        ".vb": "dotnet",
        ".fs": "fsharp",
        ".fsx": "fsharp",
        ".go": "go",
        ".rs": "rust",
        ".zig": "zig",
        ".swift": "swift",
        ".m": "objectivec",
        ".mm": "objectivec",
        ".php": "php",
        ".phtml": "php",
        ".rb": "ruby",
        ".pl": "perl",
        ".pm": "perl",
        ".lua": "lua",
        ".r": "r",
        ".jl": "julia",
        ".dart": "dart",
        ".ex": "elixir",
        ".exs": "elixir",
        ".erl": "erlang",
        ".hrl": "erlang",
        ".html": "html",
        ".htm": "html",
        ".xhtml": "html",
        ".css": "css",
        ".scss": "sass",
        ".sass": "sass",
        ".less": "less",
        ".vue": "vue",
        ".svelte": "svelte",
        ".astro": "astro",
        ".ejs": "template",
        ".hbs": "handlebars",
        ".handlebars": "handlebars",
        ".mustache": "template",
        ".njk": "template",
        ".twig": "template",
        ".jinja": "template",
        ".jinja2": "template",
        ".tpl": "template",
        ".sql": "sql",
        ".graphql": "graphql",
        ".gql": "graphql",
        ".proto": "protobuf",
        ".json": "json",
        ".jsonc": "json",
        ".xml": "xml",
        ".xsd": "xml",
        ".xsl": "xml",
        ".wsdl": "xml",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".ini": "config",
        ".cfg": "config",
        ".conf": "config",
        ".properties": "config",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".fish": "shell",
        ".bat": "batch",
        ".cmd": "batch",
        ".ps1": "powershell",
        ".psm1": "powershell",
        ".psd1": "powershell",
        ".dockerignore": "docker",
        ".editorconfig": "editorconfig",
        ".md": "markdown",
    }
    FILE_ICON_FILENAME_MAP = {
        "Dockerfile": "docker",
        "Containerfile": "docker",
        "Makefile": "makefile",
        "CMakeLists.txt": "cmake",
        "Jenkinsfile": "jenkins",
        "Procfile": "config",
        "Rakefile": "ruby",
        "Gemfile": "ruby",
        "Podfile": "swift",
        "Brewfile": "homebrew",
        "Vagrantfile": "vagrant",
    }

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = parent.master.controller 

        self.AI_MODELS, self.AI_URLS = self._load_available_ais()
        self.AI_ORDER = [self.AUTO_AI_OPTION, self.AGENT_AI_OPTION] + self.AI_MODELS
        
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
        self._responsive_after_id = None
        self._checkbox_visual_size = Styles.scale_size(30)
        self.sections_dir_var = tk.StringVar(value="")
        self.file_type_icons = {}
        self.folder_chip_widgets = []
        self._folder_chip_refresh_after = None

        self._load_file_type_icons()
        self._create_layout()

    def _load_file_type_icons(self):
        """Loads file type icons used by the code table."""
        self.file_type_icons = {}
        try:
            base_path = os.path.join(os.getcwd(), "assets", "icons", "filetypes")
            legacy_js_icon_path = os.path.join(os.getcwd(), "assets", "icons", "javascript_icon.png")
            icon_size = Styles.scale_size(18)

            if os.path.isdir(base_path):
                for filename in sorted(os.listdir(base_path)):
                    if not filename.lower().endswith(".png"):
                        continue
                    icon_key = os.path.splitext(filename)[0]
                    icon_path = os.path.join(base_path, filename)
                    image = Image.open(icon_path).convert("RGBA")
                    image = image.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    self.file_type_icons[icon_key] = ImageTk.PhotoImage(image)

            if "javascript" not in self.file_type_icons and os.path.exists(legacy_js_icon_path):
                image = Image.open(legacy_js_icon_path).convert("RGBA")
                image = image.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                self.file_type_icons["javascript"] = ImageTk.PhotoImage(image)
        except Exception as exc:
            print(f"CodeView: Error cargando iconos de ficheros: {exc}")

    @classmethod
    def _get_ai_config_path(cls):
        cwd_path = os.path.join(os.getcwd(), cls.AI_CONFIG_FILENAME)
        bundled_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", cls.AI_CONFIG_FILENAME)
        )

        if os.path.exists(cwd_path):
            return cwd_path
        if os.path.exists(bundled_path):
            return bundled_path
        return cwd_path

    @classmethod
    def _parse_ai_config_line(cls, raw_line):
        for separator in ("|", "\t", ";"):
            if separator in raw_line:
                name, url = raw_line.split(separator, 1)
                name = name.strip()
                url = url.strip()
                if name and url:
                    return name, url
                break
        return None, None

    @classmethod
    def _load_available_ais(cls):
        ai_models = []
        ai_urls = {}
        config_path = cls._get_ai_config_path()

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as config_file:
                    for line_number, raw_line in enumerate(config_file, start=1):
                        cleaned_line = raw_line.strip()
                        if not cleaned_line or cleaned_line.startswith("#"):
                            continue

                        name, url = cls._parse_ai_config_line(cleaned_line)
                        if not name or not url:
                            print(
                                f"CodeView: Ignorando línea inválida en {config_path}:{line_number} -> {cleaned_line}"
                            )
                            continue

                        if name not in ai_urls:
                            ai_models.append(name)
                        ai_urls[name] = url
            except Exception as exc:
                print(f"CodeView: Error cargando {config_path}: {exc}")

        if ai_models:
            return ai_models, ai_urls

        fallback_models = [name for name, _ in cls.DEFAULT_AI_SOURCES]
        fallback_urls = dict(cls.DEFAULT_AI_SOURCES)
        return fallback_models, fallback_urls

    def set_controller(self, controller):
        """Explicitly set controller if not available via hierarchy."""
        self.controller = controller

    def _create_left_pane(self):
        """Creates the left panel with project switcher, toolbar, file list and prompt area."""
        self.left_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(self.left_frame, minsize=self.MIN_LEFT_PANEL_WIDTH, stretch="always")

        self._create_project_bar(self.left_frame)
        self._create_top_bar(self.left_frame)
        self._create_prompt_area(self.left_frame)
        self._create_file_tree(self.left_frame)

    def _create_project_bar(self, parent):
        """Creates the compact project switcher bar."""
        self.project_bar = ttk.Frame(parent, style="Main.TFrame")
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
            font=("Segoe UI", 18)
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
            text="+",
            style="AddProject.TButton",  # Estilo personalizado para este botón
            width=2,
            command=self._on_add_project
        )
        self.btn_add_project.pack(side="left", padx=(6, 0))
        attach_tooltip(self.btn_add_project, "Añadir proyecto")

        # Initialize project label
        self._update_project_label()

    def _create_top_bar(self, parent):
        """Creates the toolbar with file limit, AI selector and extensions."""
        self.top_bar = ttk.Frame(parent, style="Main.TFrame")
        self.top_bar.pack(side="top", fill="x", padx=10, pady=(2, 8))

        # Slider for File Limit
        self.limit_var = tk.DoubleVar(value=self.DEFAULT_MAX_FILE_LIMIT)

        # Container for slider
        slider_frame = ttk.Frame(self.top_bar, style="Main.TFrame")
        slider_frame.pack(side="left", padx=20)

        self.lbl_limit = ttk.Label(
            slider_frame,
            text=f"Mín. Ficheros: {self.DEFAULT_MAX_FILE_LIMIT}",
            style="TLabel"
        )
        self.lbl_limit.pack(side="left", padx=(0, 15))

        self.slider = ttk.Scale(
            slider_frame, 
            from_=1, 
            to=self.DEFAULT_MAX_FILE_LIMIT, 
            orient="horizontal", 
            variable=self.limit_var,
            command=self._on_limit_change,
            length=200,
            style="Horizontal.TScale"
        )
        self.slider.pack(side="left", fill="x")

        # AI Selector
        self.ai_selector_shell = tk.Frame(
            slider_frame,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.ai_selector_shell.pack(side="left", padx=(20, 0))

        self.ai_selector_title = tk.Label(
            self.ai_selector_shell,
            text="Seleccionar IA",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        )
        self.ai_selector_title.pack(fill="x", padx=10, pady=(7, 0))

        self.ai_var = tk.StringVar()
        self.cmb_ai = ttk.Combobox(
            self.ai_selector_shell,
            textvariable=self.ai_var, 
            values=self.AI_ORDER,
            state="readonly",
            width=20,
            style="Borderless.TCombobox"
        )
        self.cmb_ai.current(0)
        self.cmb_ai.pack(fill="x", padx=8, pady=(2, 6), ipady=2)

        # Extension Filter - BORDE TOTALMENTE ELIMINADO
        saved_extensions = ""
        if hasattr(self, 'controller') and hasattr(self.controller, 'config_manager'):
            saved_extensions = self.controller.config_manager.get_code_extensions_filter()
        self.ext_var = tk.StringVar(value=saved_extensions)

        lbl_ext = ttk.Label(slider_frame, text="Exts:", style="TLabel")
        lbl_ext.pack(side="left", padx=(20, 5))

        ext_frame = tk.Frame(
            slider_frame,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        ext_frame.pack(side="left", padx=(0, 0))

        self.txt_ext = tk.Entry(
            ext_frame,
            textvariable=self.ext_var,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            width=15,
            font=Styles.FONT_MAIN
        )
        self.txt_ext._skip_soften = True
        Styles.strip_classic_widget_chrome(self.txt_ext)
        self.txt_ext.pack(fill="both", expand=True, ipady=2)  # ipady aumenta altura vertical
        self.ext_var.trace_add("write", self._on_extension_change)

        self._apply_limit_slider_range()

        # Initialize slider from config if controller available
        if hasattr(self, 'controller') and hasattr(self.controller, 'config_manager'):
            limit = self.controller.config_manager.get_file_limit()
            self._apply_limit_slider_range()
            limit = min(limit, self._get_limit_slider_max())
            self.limit_var.set(limit)
            self.lbl_limit.config(text=f"Mín. Ficheros: {int(limit)}")
            self.controller.config_manager.set_file_limit(limit)

    def _create_file_tree(self, parent):
        """Creates the file listing treeview and its context menu."""
        self.tree_frame = ttk.Frame(parent, style="Main.TFrame")

        self.file_list_shell = tk.Frame(
            self.tree_frame,
            bg=Styles.COLOR_INPUT_BG,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.file_list_shell.pack(fill="both", expand=True)

        self.columns = ("folder", "size", "type", "full_path", "folder_chip")
        self.tree = ttk.Treeview(
            self.file_list_shell,
            columns=self.columns,
            displaycolumns=("folder", "size", "type"),
            show="tree headings",
            selectmode="extended",
            style="Files.Treeview"
        )
        self.tree.heading("#0", text="Nombre")
        self.tree.heading("folder", text="Ruta")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("type", text="Tipo")

        self.tree.column("#0", anchor="w", stretch=True, width=360, minwidth=240)
        self.tree.column("folder", anchor="w", stretch=True, width=180, minwidth=120)
        self.tree.column("size", anchor="center", stretch=False, width=110, minwidth=90)
        self.tree.column("type", anchor="center", stretch=False, width=140, minwidth=110)
        self.tree.column("full_path", width=0, stretch=False, minwidth=0)
        self.tree.column("folder_chip", width=0, stretch=False, minwidth=0)
        self._configure_file_tree_style()

        # Scrollbar
        self.file_tree_scrollbar = ttk.Scrollbar(
            self.file_list_shell,
            orient="vertical",
            command=self._on_file_tree_scroll,
            style="Vertical.TScrollbar"
        )
        self.tree.configure(yscrollcommand=self._on_file_tree_yscroll)

        self.tree.pack(side="left", fill="both", expand=True)
        self.file_tree_scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Configure>", self._on_file_tree_resize)
        self.tree.bind("<<TreeviewSelect>>", self._schedule_folder_chip_refresh, add="+")
        self.tree.bind("<ButtonRelease-1>", self._schedule_folder_chip_refresh, add="+")
        self.tree.bind("<ButtonRelease-3>", self._schedule_folder_chip_refresh, add="+")
        self.tree.bind("<MouseWheel>", self._schedule_folder_chip_refresh, add="+")
        self.tree.bind("<Button-4>", self._schedule_folder_chip_refresh, add="+")
        self.tree.bind("<Button-5>", self._schedule_folder_chip_refresh, add="+")

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

        # NOW pack the tree frame to fill the REMAINING space
        self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)

    def _configure_file_tree_style(self, row_font_size=None, heading_font_size=None, row_height=None):
        """Creates a richer table style for the file list."""
        style = ttk.Style()
        row_font_size = row_font_size or Styles.scale_size(13)
        heading_font_size = heading_font_size or Styles.scale_size(13)
        row_height = row_height or Styles.scale_size(44)

        style.configure(
            "Files.Treeview",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", row_font_size),
            rowheight=row_height
        )
        style.configure(
            "Files.Treeview.Heading",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground="#d7e4fb",
            font=("Segoe UI", heading_font_size, "bold"),
            borderwidth=0,
            relief="flat",
            padding=Styles.scale_padding((14, 12))
        )
        style.map(
            "Files.Treeview",
            background=[("selected", Styles.COLOR_SELECTION_BG)],
            foreground=[("selected", "#ffffff")]
        )
        style.map(
            "Files.Treeview.Heading",
            background=[("active", Styles.COLOR_BG_SIDEBAR)]
        )

        if hasattr(self, "tree"):
            self.tree.tag_configure("row_even", background=Styles.COLOR_INPUT_BG, foreground=Styles.COLOR_FG_TEXT)
            self.tree.tag_configure("row_odd", background="#16243a", foreground=Styles.COLOR_FG_TEXT)

    def _on_file_tree_resize(self, event=None):
        """Keeps the file list proportions balanced."""
        self._update_file_tree_columns()
        self._schedule_folder_chip_refresh()

    def _on_file_tree_scroll(self, *args):
        """Scrolls the file table and refreshes route chips."""
        self.tree.yview(*args)
        self._schedule_folder_chip_refresh()

    def _on_file_tree_yscroll(self, first, last):
        """Keeps scrollbar and route chips in sync with tree scrolling."""
        if hasattr(self, "file_tree_scrollbar"):
            self.file_tree_scrollbar.set(first, last)
        self._schedule_folder_chip_refresh()

    def _schedule_folder_chip_refresh(self, event=None):
        """Debounces route-chip overlay updates."""
        if self._folder_chip_refresh_after:
            try:
                self.after_cancel(self._folder_chip_refresh_after)
            except Exception:
                pass
        self._folder_chip_refresh_after = self.after(15, self._refresh_folder_chip_overlays)

    def _clear_folder_chip_overlays(self):
        """Removes any existing route chip overlays."""
        for widget in self.folder_chip_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.folder_chip_widgets = []

    def _get_file_row_background(self, item_id):
        """Returns the visual row background for a given tree item."""
        try:
            tags = self.tree.item(item_id, "tags") or ()
        except Exception:
            tags = ()

        if "row_odd" in tags:
            return "#16243a"
        return Styles.COLOR_INPUT_BG

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill, outline, width):
        """Draws a rounded rectangle in a canvas."""
        radius = max(0, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))

        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=outline, width=width)
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline=outline, width=width)

        for corner in (
            (x1, y1, x1 + radius * 2, y1 + radius * 2),
            (x2 - radius * 2, y1, x2, y1 + radius * 2),
            (x1, y2 - radius * 2, x1 + radius * 2, y2),
            (x2 - radius * 2, y2 - radius * 2, x2, y2),
        ):
            canvas.create_oval(*corner, fill=fill, outline=outline, width=width)

    def _on_folder_chip_mousewheel(self, event):
        """Delegates scroll events captured by the Ruta chip overlay."""
        if getattr(event, "delta", 0):
            step = -1 if event.delta > 0 else 1
            self.tree.yview_scroll(step, "units")
        elif getattr(event, "num", None) == 4:
            self.tree.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.tree.yview_scroll(1, "units")
        self._schedule_folder_chip_refresh()
        return "break"

    def _refresh_folder_chip_overlays(self):
        """Renders a gray chip over each visible Ruta cell."""
        self._folder_chip_refresh_after = None
        if not hasattr(self, "tree"):
            return

        self._clear_folder_chip_overlays()

        chip_bg = "#2e3747"
        chip_fg = "#c2cad8"
        chip_font = ("Segoe UI", Styles.scale_size(12), "bold")
        chip_font_obj = tkfont.Font(font=chip_font)
        viewport_width = max(self.tree.winfo_width(), 0)
        viewport_height = max(self.tree.winfo_height(), 0)

        for item_id in self.tree.get_children():
            try:
                bbox = self.tree.bbox(item_id, "folder")
            except Exception:
                bbox = None

            if not bbox:
                continue

            x, y, width, height = bbox
            if width <= 8 or height <= 6:
                continue
            if x < 0 or y < 0:
                continue
            if (x + width) > viewport_width or (y + height) > viewport_height:
                continue

            folder_text = self.tree.set(item_id, "folder_chip")
            if not folder_text:
                continue

            text_width = chip_font_obj.measure(folder_text)
            text_height = chip_font_obj.metrics("linespace")
            chip_width = min(max(text_width + 14, 28), max(width - 10, 28))
            chip_height = min(max(text_height + 6, 18), max(height - 10, 18))
            row_bg = self._get_file_row_background(item_id)
            canvas = tk.Canvas(
                self.tree,
                bg=row_bg,
                bd=0,
                highlightthickness=0,
                relief="flat"
            )
            chip_x = x + max((width - chip_width) // 2, 4)
            chip_y = y + max((height - chip_height) // 2, 3)
            canvas.place(x=chip_x, y=chip_y, width=chip_width, height=chip_height)
            self._draw_rounded_rect(
                canvas,
                1,
                1,
                chip_width - 2,
                chip_height - 2,
                radius=min(7, int(chip_height * 0.26)),
                fill=chip_bg,
                outline=chip_bg,
                width=0
            )
            canvas.create_text(
                chip_width / 2,
                chip_height / 2,
                text=folder_text,
                fill=chip_fg,
                font=chip_font
            )
            canvas.bind("<Button-1>", lambda event, iid=item_id: self._on_folder_chip_left_click(iid))
            canvas.bind("<Double-1>", lambda event, iid=item_id: self._on_folder_chip_double_click(iid))
            canvas.bind("<Button-2>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
            canvas.bind("<Button-3>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
            canvas.bind("<Control-Button-1>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
            canvas.bind("<MouseWheel>", self._on_folder_chip_mousewheel)
            canvas.bind("<Button-4>", self._on_folder_chip_mousewheel)
            canvas.bind("<Button-5>", self._on_folder_chip_mousewheel)
            self.folder_chip_widgets.append(canvas)

    def _select_file_tree_item(self, item_id):
        """Selects one file row in the table."""
        if not item_id:
            return
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)

    def _on_folder_chip_left_click(self, item_id):
        self._select_file_tree_item(item_id)

    def _on_folder_chip_double_click(self, item_id):
        self._select_file_tree_item(item_id)
        self._remove_file_tree_item(item_id)

    def _on_folder_chip_right_click(self, event, item_id):
        self._select_file_tree_item(item_id)
        self.file_context_menu.tk_popup(event.x_root, event.y_root)

    def _update_file_tree_columns(self):
        """Recomputes column widths to keep a dashboard-like layout."""
        if not hasattr(self, "tree"):
            return

        total_width = max(self.tree.winfo_width(), 780)
        size_width = max(Styles.scale_size(110), int(total_width * 0.11))
        type_width = max(Styles.scale_size(130), int(total_width * 0.14))
        folder_width = max(Styles.scale_size(170), int(total_width * 0.22))
        used_width = size_width + type_width + folder_width
        name_width = max(Styles.scale_size(240), total_width - used_width)

        self.tree.column("#0", width=name_width)
        self.tree.column("folder", width=folder_width)
        self.tree.column("size", width=size_width)
        self.tree.column("type", width=type_width)
        self._schedule_folder_chip_refresh()

    def _format_file_size(self, num_bytes):
        """Formats file sizes in a compact explorer-friendly way."""
        try:
            size = float(max(num_bytes, 0))
        except Exception:
            return "0 B"

        units = ("B", "KB", "MB", "GB")
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.1f} {units[unit_index]}"

    def _format_modified_time(self, file_path):
        """Returns a compact relative label for the file modification time."""
        try:
            modified_at = os.path.getmtime(file_path)
        except Exception:
            return "desconocido"

        delta_seconds = max(int(time.time() - modified_at), 0)
        if delta_seconds < 60:
            return "ahora"
        if delta_seconds < 3600:
            minutes = max(delta_seconds // 60, 1)
            return f"hace {minutes} min"
        if delta_seconds < 86400:
            hours = max(delta_seconds // 3600, 1)
            return f"hace {hours} h"
        if delta_seconds < 172800:
            return "ayer"
        if delta_seconds < 604800:
            days = max(delta_seconds // 86400, 1)
            return f"hace {days} d"
        if delta_seconds < 2592000:
            weeks = max(delta_seconds // 604800, 1)
            return f"hace {weeks} sem"
        months = max(delta_seconds // 2592000, 1)
        return f"hace {months} mes{'es' if months != 1 else ''}"

    def _get_file_type_label(self, rel_path):
        """Maps file extensions to cleaner type names for the list."""
        ext = os.path.splitext(rel_path)[1].lower()
        type_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "React",
            ".ts": "TypeScript",
            ".tsx": "React TS",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "Sass",
            ".less": "Less",
            ".json": "JSON",
            ".jsonc": "JSONC",
            ".yml": "YAML",
            ".yaml": "YAML",
            ".md": "Markdown",
            ".sql": "SQL",
            ".sh": "Shell",
            ".zsh": "Shell",
            ".bat": "Batch",
            ".ps1": "PowerShell",
            ".php": "PHP",
            ".java": "Java",
            ".kt": "Kotlin",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".h": "Header",
            ".hpp": "C++ Header",
            ".xml": "XML",
            ".vue": "Vue",
            ".svelte": "Svelte",
        }

        if ext in type_map:
            return type_map[ext]

        basename = os.path.basename(rel_path)
        if basename in {"Dockerfile", "Containerfile"}:
            return "Docker"
        if basename in {"Makefile", "CMakeLists.txt"}:
            return "Build"
        return ext[1:].upper() if ext else "Archivo"

    def _get_file_icon(self, rel_path):
        """Returns the icon image for the file name column when available."""
        basename = os.path.basename(rel_path)
        ext = os.path.splitext(rel_path)[1].lower()
        icon_key = self.FILE_ICON_FILENAME_MAP.get(basename) or self.FILE_ICON_EXTENSION_MAP.get(ext)
        if not icon_key:
            return None
        return self.file_type_icons.get(icon_key)

    def _build_file_name_display(self, rel_path):
        """Builds an icon-like label for the file name column."""
        normalized_path = rel_path.replace(os.sep, "/")
        parts = [part for part in normalized_path.split("/") if part]
        if len(parts) >= 2:
            display_name = "/".join(parts[-2:])
        elif parts:
            display_name = parts[-1]
        else:
            display_name = rel_path
        return f"   {display_name}"

    def _build_file_folder_display(self, rel_path):
        """Builds the ancestor path shown in the Ruta column."""
        normalized_path = rel_path.replace(os.sep, "/")
        parts = [part for part in normalized_path.split("/") if part]
        if len(parts) <= 2:
            return "raiz"
        ancestor_parts = parts[:-2]
        return "/".join(ancestor_parts[-2:])

    def _get_tree_item_path(self, item_id):
        """Returns the hidden absolute path stored for a file row."""
        if not item_id:
            return None
        try:
            file_path = self.tree.set(item_id, "full_path")
            return file_path or None
        except Exception:
            return None

    def _create_prompt_area(self, parent):
        """Creates the AI prompt text area and copy button."""
        self.prompt_frame = ttk.Frame(parent, style="Main.TFrame")
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

    def _create_right_pane(self):
        """Creates the right panel with sections header, search and tree."""
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame", width=self.DEFAULT_SECTIONS_PANEL_WIDTH)
        self.paned_window.add(self.right_frame, minsize=self.MIN_SECTIONS_PANEL_WIDTH, stretch="never")

        # Split Right Pane into Top (List), Bottom (Checkbox area) and Bottom Spacer
        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="x", expand=False)

        self.right_bottom_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_bottom_frame.pack(side="top", fill="x", expand=False)

        # Bottom spacer to push everything up
        self.right_bottom_spacer = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_bottom_spacer.pack(side="top", fill="both", expand=True)

        self._create_sections_header(self.right_top_frame)
        self._create_section_search(self.right_top_frame)
        self._create_section_actions(self.right_top_frame)
        self._create_section_tree(self.right_top_frame)
        self._create_return_files_checkbox(self.right_bottom_frame)
        self._create_return_chunks_checkbox(self.right_bottom_frame)
        self._create_file_headers_checkbox(self.right_bottom_frame)

    def _create_sections_header(self, parent):
        """Creates the 'Secciones' header and directory label."""
        self.sections_header = ttk.Frame(parent, style="Sidebar.TFrame")
        self.sections_header.pack(fill="x")

        lbl_sections = ttk.Label(self.sections_header, text="Secciones", style="Header.TLabel")
        lbl_sections.pack(side="left", fill="x", expand=True)

        self.btn_change_sections_dir = ttk.Button(
            self.sections_header,
            text="Carpeta",
            style="ToolbarIcon.TButton",
            command=self._on_change_sections_directory
        )
        self.btn_change_sections_dir.pack(side="right", padx=(0, 8), pady=(4, 0))
        attach_tooltip(self.btn_change_sections_dir, "Cambiar carpeta de secciones")

        self.lbl_sections_dir = tk.Label(
            parent,
            textvariable=self.sections_dir_var,
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left"
        )
        self.lbl_sections_dir.pack(fill="x", padx=12, pady=(0, 4))
        self._update_sections_directory_label()

    def _create_section_search(self, parent):
        """Creates the section search input."""
        self.section_search_shell = tk.Frame(
            parent,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.section_search_shell.pack(fill="x", padx=8, pady=(4, 4))

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
        self.section_search_entry.pack(fill="x", padx=10, pady=(4, 6), ipady=4)
        self.section_search_entry.bind("<KeyRelease>", self._on_section_search_change)

    def _create_section_actions(self, parent):
        """Creates action buttons for the selected section/subsection."""
        self.section_actions_frame = ttk.Frame(parent, style="Sidebar.TFrame")
        self.section_actions_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.btn_add_files_to_section = ttk.Button(
            self.section_actions_frame,
            text="Agregar ficheros",
            style="Action.TButton",
            command=self._on_add_files_to_selected_section,
            state="disabled"
        )
        self.btn_add_files_to_section.pack(fill="x")
        attach_tooltip(
            self.btn_add_files_to_section,
            "Añadir varios ficheros a la sección o subsección seleccionada"
        )

    def _create_section_tree(self, parent):
        """Creates the sections and subsections treeview."""
        self.section_tree = ttk.Treeview(
            parent,
            show="tree",
            selectmode="browse",
            style="Borderless.Treeview",
            height=12
        )
        self.section_tree.column("#0", stretch=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_select)
        self.section_tree.bind("<Button-1>", self._on_section_click)
        
        self.section_tree.tag_configure("section", font=("Segoe UI", 15, "bold"))
        self.section_tree.tag_configure("subsection", font=("Segoe UI", 13))
        
        self.section_tree.pack(fill="x", expand=False, padx=5, pady=(2, 5))

        self.section_tree_bottom_spacer = tk.Frame(
            parent,
            bg=Styles.COLOR_BG_SIDEBAR,
            height=8,
            cursor="arrow"
        )
        self.section_tree_bottom_spacer.pack(fill="x", padx=5, pady=(0, 2))
        self.section_tree_bottom_spacer.pack_propagate(False)
        self.section_tree_bottom_spacer.bind("<Button-1>", self._on_section_spacer_click)

        # Bind Right Click
        self.section_tree.bind("<Button-2>", self._show_context_menu)
        self.section_tree.bind("<Button-3>", self._show_context_menu)
        self.section_tree.bind("<Control-Button-1>", self._show_context_menu)

    def _create_return_files_checkbox(self, parent):
        """Creates the custom 'Devolver archivos' checkbox."""
        val_return_files = False
        if hasattr(self.controller, 'config_manager'):
            val_return_files = self.controller.config_manager.get_return_files()

        self.var_return_files = tk.BooleanVar(value=val_return_files)
        
        self.chk_container = ttk.Frame(parent, style="Sidebar.TFrame", cursor="hand2")
        self.chk_container.pack(fill="x", padx=15, pady=(0, 1))
        
        self.chk_canvas = tk.Canvas(
            self.chk_container,
            width=30,
            height=30,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=0,
            bd=0
        )
        self.chk_canvas.pack(side="left")
        self._draw_checkbox()
        
        self.lbl_chk_text = ttk.Label(
            self.chk_container, 
            text="Devolver archivos", 
            style="TLabel",
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_chk_text.configure(background=Styles.COLOR_BG_SIDEBAR)
        self.lbl_chk_text.pack(side="left", padx=(10, 0))
        
        self.chk_container.bind("<Button-1>", self._toggle_return_files)
        self.chk_canvas.bind("<Button-1>", self._toggle_return_files)
        self.lbl_chk_text.bind("<Button-1>", self._toggle_return_files)
        
        self.chk_container.bind("<Enter>", self._on_chk_hover_enter)
        self.chk_container.bind("<Leave>", self._on_chk_hover_leave)

    def _create_return_chunks_checkbox(self, parent):
        """Creates the custom 'Devolver Trozos' checkbox."""
        val_return_chunks = False
        if hasattr(self.controller, 'config_manager'):
            val_return_chunks = self.controller.config_manager.get_return_chunks()
        if hasattr(self, "var_return_files") and self.var_return_files.get() and val_return_chunks:
            val_return_chunks = False

        self.var_return_chunks = tk.BooleanVar(value=val_return_chunks)

        self.chk_chunks_container = ttk.Frame(parent, style="Sidebar.TFrame", cursor="hand2")
        self.chk_chunks_container.pack(fill="x", padx=15, pady=(0, 1))

        self.chk_chunks_canvas = tk.Canvas(
            self.chk_chunks_container,
            width=30,
            height=30,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=0,
            bd=0
        )
        self.chk_chunks_canvas.pack(side="left")
        self._draw_chunks_checkbox()

        self.lbl_chk_chunks_text = ttk.Label(
            self.chk_chunks_container,
            text="Devolver Trozos",
            style="TLabel",
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_chk_chunks_text.configure(background=Styles.COLOR_BG_SIDEBAR)
        self.lbl_chk_chunks_text.pack(side="left", padx=(10, 0))

        self.chk_chunks_container.bind("<Button-1>", self._toggle_return_chunks)
        self.chk_chunks_canvas.bind("<Button-1>", self._toggle_return_chunks)
        self.lbl_chk_chunks_text.bind("<Button-1>", self._toggle_return_chunks)

        self.chk_chunks_container.bind("<Enter>", self._on_chk_chunks_hover_enter)
        self.chk_chunks_container.bind("<Leave>", self._on_chk_chunks_hover_leave)

    def _create_file_headers_checkbox(self, parent):
        """Creates the custom 'Cabecera Archivo' checkbox used for codigo.txt exports."""
        include_headers = True
        if hasattr(self.controller, 'config_manager'):
            include_headers = self.controller.config_manager.get_include_file_headers_in_codigo_txt()

        self.var_include_file_headers = tk.BooleanVar(value=include_headers)

        self.chk_headers_container = ttk.Frame(parent, style="Sidebar.TFrame", cursor="hand2")
        self.chk_headers_container.pack(fill="x", padx=15, pady=(0, 1))

        self.chk_headers_canvas = tk.Canvas(
            self.chk_headers_container,
            width=30,
            height=30,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=0,
            bd=0
        )
        self.chk_headers_canvas.pack(side="left")
        self._draw_file_headers_checkbox()

        self.lbl_chk_headers_text = ttk.Label(
            self.chk_headers_container,
            text="Cabecera Archivo",
            style="TLabel",
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_chk_headers_text.configure(background=Styles.COLOR_BG_SIDEBAR)
        self.lbl_chk_headers_text.pack(side="left", padx=(10, 0))

        self.chk_headers_container.bind("<Button-1>", self._toggle_file_headers)
        self.chk_headers_canvas.bind("<Button-1>", self._toggle_file_headers)
        self.lbl_chk_headers_text.bind("<Button-1>", self._toggle_file_headers)

        self.chk_headers_container.bind("<Enter>", self._on_chk_headers_hover_enter)
        self.chk_headers_container.bind("<Leave>", self._on_chk_headers_hover_leave)

    def _create_layout(self):
        """Creates the split-pane layout."""
        # Main PanedWindow (Split Left / Right)
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, bg=Styles.COLOR_BG_MAIN, sashrelief="flat")
        self.paned_window.pack(fill="both", expand=True)

        self._create_left_pane()
        self._create_right_pane()

        # Initial sections load
        self._refresh_sections()
        self.after_idle(self._set_default_sections_panel_width)
        self.bind("<Configure>", self._on_resize)

    def _set_default_sections_panel_width(self):
        try:
            self.update_idletasks()
            total_width = self.paned_window.winfo_width()
            if total_width <= self.DEFAULT_SECTIONS_PANEL_WIDTH:
                return
            right_width = min(max(self.MIN_SECTIONS_PANEL_WIDTH, int(total_width * 0.30)), self.DEFAULT_SECTIONS_PANEL_WIDTH)
            left_width = max(self.MIN_LEFT_PANEL_WIDTH, total_width - right_width)
            self.paned_window.sash_place(0, left_width, 0)
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
        width = max(self.winfo_width(), self.winfo_toplevel().winfo_width())
        height = max(self.winfo_height(), self.winfo_toplevel().winfo_height())

        compact_height = height < 760
        ultra_compact_height = height < 640
        narrow_width = width < 1150
        compact_width = width < 960

        project_font_size = Styles.scale_size(14 if compact_height else 18)
        section_label_size = Styles.scale_size(11 if compact_height else 13)
        section_dir_size = Styles.scale_size(9 if ultra_compact_height else 10 if compact_height else 11)
        section_entry_size = Styles.scale_size(13 if compact_height else 15)
        tree_section_size = Styles.scale_size(13 if compact_height else 15)
        tree_subsection_size = Styles.scale_size(11 if compact_height else 13)
        checkbox_font_size = Styles.scale_size(14 if ultra_compact_height else 16 if compact_height else 18)
        self._checkbox_visual_size = Styles.scale_size(24 if ultra_compact_height else 26 if compact_height else 30)
        prompt_height = max(Styles.scale_size(4 if ultra_compact_height else 5 if compact_height else 8), 3)
        slider_length = Styles.scale_size(110 if compact_width else 150 if narrow_width else 200)
        ai_width = max(Styles.scale_size(14 if compact_width else 17 if narrow_width else 20), 10)
        ext_width = max(Styles.scale_size(10 if compact_width else 12 if narrow_width else 15), 8)
        spacer_height = Styles.scale_size(18 if ultra_compact_height else 28 if compact_height else 42)
        top_prompt_pady = Styles.scale_size(6 if compact_height else 10)
        chk_bottom_pady = Styles.scale_padding((0, 5))

        file_font_size = Styles.scale_size(13 if compact_width else 14 if narrow_width else 15)
        file_heading_size = Styles.scale_size(13 if compact_width else 14 if narrow_width else 15)
        file_row_height = Styles.scale_size(42 if ultra_compact_height else 46 if compact_height else 52)
        ai_title_size = Styles.scale_size(9 if ultra_compact_height else 10 if compact_height else 11)

        self.lbl_project_name.configure(font=("Segoe UI", project_font_size))
        self.section_search_label.configure(font=("Segoe UI", section_label_size, "bold"))
        self.lbl_sections_dir.configure(
            font=("Segoe UI", section_dir_size),
            wraplength=max(self.right_frame.winfo_width() - 30, Styles.scale_size(180))
        )
        self.section_search_entry.configure(font=("Segoe UI", section_entry_size))
        self.section_tree.tag_configure("section", font=("Segoe UI", tree_section_size, "bold"))
        self.section_tree.tag_configure("subsection", font=("Segoe UI", tree_subsection_size))
        self.section_tree_bottom_spacer.configure(height=spacer_height)

        self._configure_file_tree_style(
            row_font_size=file_font_size,
            heading_font_size=file_heading_size,
            row_height=file_row_height
        )
        self._update_file_tree_columns()

        self.slider.configure(length=slider_length)
        self.cmb_ai.configure(width=ai_width)
        self.ai_selector_title.configure(font=("Segoe UI", ai_title_size, "bold"))
        self.txt_ext.configure(width=ext_width)
        self.txt_prompt.configure(height=prompt_height)
        self.prompt_frame.pack_configure(pady=top_prompt_pady)

        self.chk_canvas.configure(width=self._checkbox_visual_size, height=self._checkbox_visual_size)
        self.chk_chunks_canvas.configure(width=self._checkbox_visual_size, height=self._checkbox_visual_size)
        self.chk_headers_canvas.configure(width=self._checkbox_visual_size, height=self._checkbox_visual_size)
        self.lbl_chk_text.configure(font=("Segoe UI", checkbox_font_size, "bold"))
        self.lbl_chk_chunks_text.configure(font=("Segoe UI", checkbox_font_size, "bold"))
        self.lbl_chk_headers_text.configure(font=("Segoe UI", checkbox_font_size, "bold"))

        self.chk_container.pack_configure(pady=chk_bottom_pady)
        self.chk_chunks_container.pack_configure(pady=chk_bottom_pady)
        self.chk_headers_container.pack_configure(pady=chk_bottom_pady)

        self._draw_checkbox()
        self._draw_chunks_checkbox()
        self._draw_file_headers_checkbox()

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
        size = max(int(getattr(self, "_checkbox_visual_size", 30)), 20)
        factor = size / 30.0
        rect_start = max(int(round(4 * factor)), 3)
        rect_end = size - rect_start
        line_width = max(int(round(3 * factor)), 2)

        is_checked = self.var_return_files.get()
        outline_color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM

        self.chk_canvas.create_rectangle(
            rect_start, rect_start, rect_end, rect_end,
            outline=outline_color,
            width=2,
            fill=Styles.COLOR_INPUT_BG if not is_checked else Styles.COLOR_ACCENT
        )

        if is_checked:
            self.chk_canvas.create_line(
                int(round(8 * factor)), int(round(15 * factor)),
                int(round(13 * factor)), int(round(20 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )
            self.chk_canvas.create_line(
                int(round(13 * factor)), int(round(20 * factor)),
                int(round(22 * factor)), int(round(10 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )

    def _draw_chunks_checkbox(self):
        """Draws the current state on the chunks checkbox canvas."""
        self.chk_chunks_canvas.delete("all")
        size = max(int(getattr(self, "_checkbox_visual_size", 30)), 20)
        factor = size / 30.0
        rect_start = max(int(round(4 * factor)), 3)
        rect_end = size - rect_start
        line_width = max(int(round(3 * factor)), 2)

        is_checked = self.var_return_chunks.get()
        outline_color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM

        self.chk_chunks_canvas.create_rectangle(
            rect_start, rect_start, rect_end, rect_end,
            outline=outline_color,
            width=2,
            fill=Styles.COLOR_INPUT_BG if not is_checked else Styles.COLOR_ACCENT
        )

        if is_checked:
            self.chk_chunks_canvas.create_line(
                int(round(8 * factor)), int(round(15 * factor)),
                int(round(13 * factor)), int(round(20 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )
            self.chk_chunks_canvas.create_line(
                int(round(13 * factor)), int(round(20 * factor)),
                int(round(22 * factor)), int(round(10 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )

    def _draw_file_headers_checkbox(self):
        """Draws the current state on the file headers checkbox canvas."""
        self.chk_headers_canvas.delete("all")
        size = max(int(getattr(self, "_checkbox_visual_size", 30)), 20)
        factor = size / 30.0
        rect_start = max(int(round(4 * factor)), 3)
        rect_end = size - rect_start
        line_width = max(int(round(3 * factor)), 2)

        is_checked = self.var_include_file_headers.get()
        outline_color = Styles.COLOR_ACCENT if is_checked else Styles.COLOR_DIM

        self.chk_headers_canvas.create_rectangle(
            rect_start, rect_start, rect_end, rect_end,
            outline=outline_color,
            width=2,
            fill=Styles.COLOR_INPUT_BG if not is_checked else Styles.COLOR_ACCENT
        )

        if is_checked:
            self.chk_headers_canvas.create_line(
                int(round(8 * factor)), int(round(15 * factor)),
                int(round(13 * factor)), int(round(20 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )
            self.chk_headers_canvas.create_line(
                int(round(13 * factor)), int(round(20 * factor)),
                int(round(22 * factor)), int(round(10 * factor)),
                fill="white", width=line_width, capstyle=tk.ROUND
            )

    def _on_chk_hover_enter(self, event):
        self.lbl_chk_text.configure(foreground=Styles.COLOR_ACCENT)
        # Subtle glow or border change could go here

    def _on_chk_hover_leave(self, event):
        self.lbl_chk_text.configure(foreground=Styles.COLOR_FG_TEXT)

    def _on_chk_chunks_hover_enter(self, event):
        self.lbl_chk_chunks_text.configure(foreground=Styles.COLOR_ACCENT)

    def _on_chk_chunks_hover_leave(self, event):
        self.lbl_chk_chunks_text.configure(foreground=Styles.COLOR_FG_TEXT)

    def _on_chk_headers_hover_enter(self, event):
        self.lbl_chk_headers_text.configure(foreground=Styles.COLOR_ACCENT)

    def _on_chk_headers_hover_leave(self, event):
        self.lbl_chk_headers_text.configure(foreground=Styles.COLOR_FG_TEXT)

    def _set_return_mode(self, return_files, return_chunks, refresh_sections=True):
        """Updates both return-mode selectors keeping them mutually exclusive."""
        self.var_return_files.set(bool(return_files))
        self.var_return_chunks.set(bool(return_chunks))
        self._draw_checkbox()
        self._draw_chunks_checkbox()

        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_return_files(return_files)
            self.controller.config_manager.set_return_chunks(return_chunks)

        if refresh_sections:
            self._refresh_sections()

    def _toggle_return_files(self, event=None):
        """Acts like a deselectable radio button with square styling."""
        is_selected = self.var_return_files.get()
        self._set_return_mode(return_files=not is_selected, return_chunks=False)

    def _toggle_return_chunks(self, event=None):
        """Acts like a deselectable radio button with square styling."""
        is_selected = self.var_return_chunks.get()
        self._set_return_mode(return_files=False, return_chunks=not is_selected)

    def _toggle_file_headers(self, event=None):
        """Toggles whether codigo.txt exports should include file headers."""
        is_selected = self.var_include_file_headers.get()
        self.var_include_file_headers.set(not is_selected)
        self._draw_file_headers_checkbox()
        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_include_file_headers_in_codigo_txt(not is_selected)

    def _should_include_file_headers_in_codigo_txt(self):
        return bool(getattr(self, "var_include_file_headers", tk.BooleanVar(value=True)).get())

    def _get_codigo_txt_append_separator(self):
        return "\n\n" if self._should_include_file_headers_in_codigo_txt() else ""

    def _build_codigo_txt_file_content(self, file_data):
        if self._should_include_file_headers_in_codigo_txt():
            return f"--- Archivo: {file_data['rel_path']} ---\n{file_data['content']}"
        return file_data['content']

    def _get_structure_size_tag(self, line_count):
        """Returns the visual severity tag for a structure size row."""
        if line_count > 600:
            return "structure_size_critical"
        if line_count <= 100:
            return "structure_size_ok"
        if line_count <= 300:
            return "structure_size_warning"
        return "structure_size_danger"

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
        if not normalized:
            return "Estructura"
        return normalized.replace("_", " ").title()

    def _on_show_structure_sizes(self):
        """Shows a popup with the detected functions and their line counts."""
        section_name, subsection_name = self._get_selected_section_info()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección o subsección primero.")
            return

        try:
            structures = self.controller.get_structure_sizes(
                selected_section=section_name,
                selected_subsection=subsection_name
            )
        except Exception as e:
            print(f"Error calculating structure sizes: {e}")
            messagebox.showerror("Error", f"No se pudo calcular el tamaño de las estructuras:\n{e}")
            return

        if not structures:
            messagebox.showinfo(
                "Tamaño estructuras",
                "No se encontraron estructuras compatibles en la selección actual."
            )
            return

        scope_label = section_name
        if subsection_name:
            scope_label = f"{section_name} > {subsection_name}"

        popup = tk.Toplevel(self)
        popup.title(f"Tamaño estructuras - {scope_label}")
        popup.transient(self.winfo_toplevel())
        popup.geometry("980x520")
        popup.configure(bg=Styles.COLOR_BG_MAIN)

        header = ttk.Frame(popup, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(12, 6))

        count_label = ttk.Label(
            header,
            text=f"{len(structures)} estructuras detectadas en {scope_label}",
            style="TLabel"
        )
        count_label.pack(anchor="w")

        legend = tk.Label(
            header,
            text="Verde: 0-100 | Amarillo: 101-300 | Rojo: 301-600 | Rojo oscuro: más de 600",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_DIM,
            font=("Segoe UI", 11),
            anchor="w"
        )
        legend.pack(fill="x", pady=(2, 0))

        filter_row = ttk.Frame(header, style="Main.TFrame")
        filter_row.pack(fill="x", pady=(10, 0))

        ttk.Label(
            filter_row,
            text="Tipo:",
            style="TLabel"
        ).pack(side="left")

        type_order = {
            "function": 0,
            "method": 1,
            "procedure": 2,
            "class": 3,
            "interface": 4,
            "struct": 5,
            "enum": 6,
            "namespace": 7,
            "module": 8,
            "tag": 9,
        }
        available_types = sorted(
            {item.get("type", "").strip().lower() for item in structures if item.get("type")},
            key=lambda item: (type_order.get(item, 99), item)
        )
        filter_options = [("Todas", "__all__")]
        filter_options.extend((self._format_structure_type_label(item), item) for item in available_types)
        filter_labels = [label for label, _ in filter_options]
        filter_value_by_label = {label: value for label, value in filter_options}

        selected_type_var = tk.StringVar(value="Todas")
        type_filter = ttk.Combobox(
            filter_row,
            state="readonly",
            values=filter_labels,
            textvariable=selected_type_var,
            width=18,
            font=("Segoe UI", 12)
        )
        type_filter.pack(side="left", padx=(8, 0))

        table_frame = ttk.Frame(popup, style="Main.TFrame")
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        columns = ("type", "name", "lines", "file")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", style="Treeview")
        table.heading("type", text="Tipo")
        table.heading("name", text="Estructura")
        table.heading("lines", text="Líneas")
        table.heading("file", text="Archivo")
        table.column("type", width=110, anchor="center")
        table.column("name", width=280, anchor="w")
        table.column("lines", width=100, anchor="center")
        table.column("file", width=450, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview, style="Vertical.TScrollbar")
        table.configure(yscrollcommand=scrollbar.set)

        table.tag_configure("structure_size_ok", background="#1f6f43", foreground="#f4fff7")
        table.tag_configure("structure_size_warning", background="#d6a41c", foreground="#1b1b1b")
        table.tag_configure("structure_size_danger", background="#b33a2f", foreground=Styles.COLOR_FG_TEXT)
        table.tag_configure("structure_size_critical", background="#5b0d0d", foreground="#ffffff")

        def populate_table():
            selected_type = filter_value_by_label.get(selected_type_var.get(), "__all__")
            filtered_structures = [
                item for item in structures
                if selected_type == "__all__" or item.get("type", "").strip().lower() == selected_type
            ]

            table.delete(*table.get_children())
            count_label.config(text=f"{len(filtered_structures)} estructuras detectadas en {scope_label}")

            for item in filtered_structures:
                display_name = item.get('display_name') or item.get('name', 'sin_nombre')
                structure_type = self._format_structure_type_label(item.get('type', 'estructura'))
                if item.get("start_line"):
                    display_file = f"{item.get('file_rel_path', '')}:{item['start_line']}"
                else:
                    display_file = item.get("file_rel_path", "")

                line_count = int(item.get("line_count", 0))
                table.insert(
                    "",
                    "end",
                    values=(structure_type, display_name, line_count, display_file),
                    tags=(self._get_structure_size_tag(line_count),)
                )

        type_filter.bind("<<ComboboxSelected>>", lambda event: populate_table())
        populate_table()

        table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        buttons = ttk.Frame(popup, style="Main.TFrame")
        buttons.pack(fill="x", padx=14, pady=(0, 12))

        ttk.Button(
            buttons,
            text="Cerrar",
            style="Secondary.TButton",
            command=popup.destroy
        ).pack(side="right")




    def _on_limit_change(self, val):
        """Handle slider movement."""
        limit = int(float(val))
        self.lbl_limit.config(text=f"Mín. Ficheros: {limit}")
        
        # Update Config (Debouncing would be better but direct update is okay for now)
        if hasattr(self.controller, 'config_manager'):
             self.controller.config_manager.set_file_limit(limit)
             
        # Refresh list to apply limit (re-run search so filter is preserved)
        self._on_prompt_change()

    def _get_limit_slider_max(self):
        """Returns the configured max value for the file-limit slider."""
        if hasattr(self.controller, 'config_manager'):
            return self.controller.config_manager.get_file_limit_slider_max()
        return self.DEFAULT_MAX_FILE_LIMIT

    def _apply_limit_slider_range(self):
        """Applies the current slider range and clamps the value if needed."""
        max_limit = self._get_limit_slider_max()
        self.slider.configure(to=max_limit)

        current_limit = int(float(self.limit_var.get()))
        if current_limit > max_limit:
            current_limit = max_limit
            self.limit_var.set(current_limit)

        self.lbl_limit.config(text=f"Mín. Ficheros: {current_limit}")
        return current_limit

    def apply_file_limit_slider_settings(self, refresh=True):
        """Reapplies the configured slider max and refreshes search results if needed."""
        current_limit = self._apply_limit_slider_range()

        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_file_limit(current_limit)

        if refresh:
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
        self.lbl_project_name.config(text=f"{project_name}")

    def _update_sections_directory_label(self):
        """Displays the active directory used to store sections and subsections."""
        path = None
        if hasattr(self.controller, "get_sections_directory"):
            path = self.controller.get_sections_directory()

        if not path:
            self.sections_dir_var.set("Carpeta: sin configurar")
            return

        home = os.path.expanduser("~")
        display_path = path
        if display_path.startswith(home):
            display_path = f"~{display_path[len(home):]}"

        self.sections_dir_var.set(f"Carpeta: {display_path}")

    def _on_change_sections_directory(self):
        """Allows selecting another folder for stored sections and subsections."""
        initial_dir = os.getcwd()
        if hasattr(self.controller, "get_sections_directory"):
            initial_dir = self.controller.get_sections_directory() or initial_dir

        selected_path = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Selecciona la carpeta para las secciones de código"
        )
        if not selected_path:
            return

        try:
            current_path = self.controller.get_sections_directory()
            if current_path and os.path.normpath(selected_path) == os.path.normpath(current_path):
                return

            self.controller.set_sections_directory(selected_path)
            self._update_sections_directory_label()
            self._refresh_sections(force_reload=True)
        except Exception as e:
            print(f"Error changing sections directory: {e}")
            messagebox.showerror("Error", f"No se pudo cambiar la carpeta de secciones:\n{e}")

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
        for index, f in enumerate(files):
            rel_path = f['rel_path']
            size_label = self._format_file_size(len(f.get('content', '') or ""))
            type_label = self._get_file_type_label(rel_path)
            row_tag = "row_even" if index % 2 == 0 else "row_odd"

            self.tree.insert(
                "",
                "end",
                text=self._build_file_name_display(rel_path),
                image=self._get_file_icon(rel_path),
                values=(
                    "",
                    size_label,
                    type_label,
                    f['path'],
                    self._build_file_folder_display(rel_path)
                ),
                tags=(row_tag,)
            )

        self._update_file_tree_columns()
        self._schedule_folder_chip_refresh()


    def _on_prompt_change(self, event=None):
        """Handles real-time search filtering with debouncing."""
        if hasattr(self, '_search_timer') and self._search_timer:
            self.after_cancel(self._search_timer)
            
        # Debounce: Wait 300ms after last keypress
        self._search_timer = self.after(300, self._start_background_search)

    def _on_extension_change(self, *args):
        """Persists the extensions filter and refreshes the file search."""
        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_code_extensions_filter(self.ext_var.get())
        self._on_prompt_change()

    def _start_background_search(self):
        """Starts the search in a separate thread."""
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        
        section, subsection = self._get_selected_section_info()
        
        extension = self.ext_var.get()
        
        min_files = 0
        if hasattr(self.controller, 'config_manager'):
            min_files = self.controller.config_manager.get_file_limit()

        # Run search in thread
        threading.Thread(target=self._perform_search, args=(text, section, subsection, extension, min_files), daemon=True).start()

    def _perform_search(self, text, section, subsection=None, extension="Todos", min_files=0):
        """Executes search logic (Thread Safe)."""
        try:
            relevant_files = self.controller.get_relevant_files_for_ui(
                text, selected_section=section, selected_subsection=subsection, extension=extension, min_files=min_files
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
        self._update_section_action_buttons(section_name, subsection_name)
        
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

    def _update_section_action_buttons(self, section_name=None, subsection_name=None):
        """Enables action buttons only when a valid section scope is selected."""
        if not hasattr(self, "btn_add_files_to_section"):
            return

        if section_name is None and subsection_name is None:
            section_name, subsection_name = self._get_selected_section_info()

        is_enabled = bool(section_name)
        self.btn_add_files_to_section.configure(
            state=("normal" if is_enabled else "disabled")
        )

    def _is_path_inside_project(self, file_path, project_path):
        """Returns True when the selected file belongs to the loaded project."""
        try:
            normalized_file = os.path.normcase(os.path.abspath(file_path))
            normalized_project = os.path.normcase(os.path.abspath(project_path))
            return os.path.commonpath([normalized_file, normalized_project]) == normalized_project
        except ValueError:
            return False

    def _on_add_files_to_selected_section(self):
        """Opens a native multi-file picker and adds the chosen files to the current scope."""
        section_name, subsection_name = self._get_selected_section_info()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección o subsección primero.")
            return

        project_path = getattr(self.controller.project_manager, "current_project_path", None)
        if not project_path or not os.path.isdir(project_path):
            messagebox.showwarning("Aviso", "Carga un proyecto antes de agregar ficheros.")
            return

        selected_paths = filedialog.askopenfilenames(
            parent=self.winfo_toplevel(),
            title="Selecciona los ficheros que quieres agregar",
            initialdir=project_path
        )
        if not selected_paths:
            return

        normalized_paths = []
        skipped_outside_project = []
        skipped_unavailable = []
        available_project_files = {
            os.path.normpath(os.path.abspath(file_info["path"]))
            for file_info in self.controller.project_manager.get_files()
        }

        for raw_path in selected_paths:
            abs_path = os.path.normpath(os.path.abspath(raw_path))
            if not self._is_path_inside_project(abs_path, project_path):
                skipped_outside_project.append(abs_path)
                continue
            if abs_path not in available_project_files:
                skipped_unavailable.append(abs_path)
                continue
            if abs_path not in normalized_paths:
                normalized_paths.append(abs_path)

        if not normalized_paths:
            details = []
            if skipped_outside_project:
                details.append("Los ficheros deben pertenecer al proyecto cargado.")
            if skipped_unavailable:
                details.append("Solo se admiten ficheros que el proyecto tenga cargados en la vista de código.")
            extra = f"\n\n{'\n'.join(details)}" if details else ""
            messagebox.showwarning("Aviso", f"No se añadió ningún fichero.{extra}")
            return

        existing_section_files = set(
            self.controller.section_manager.get_files_in_section(section_name)
        )
        files_to_add = [path for path in normalized_paths if path not in existing_section_files]

        if not files_to_add:
            messagebox.showinfo(
                "Sin cambios",
                "Todos los ficheros seleccionados ya estaban incluidos."
            )
            return

        self.controller.section_manager.add_files_to_section(section_name, files_to_add)

        if subsection_name:
            current_subsection_files = self.controller.section_manager.get_files_in_subsection(
                section_name,
                subsection_name
            )
            merged_subsection_files = list(current_subsection_files)
            for path in files_to_add:
                if path not in merged_subsection_files:
                    merged_subsection_files.append(path)
            self.controller.section_manager.update_subsection(
                section_name,
                subsection_name,
                subsection_name,
                merged_subsection_files
            )

        preferred_iid = self._build_section_iid(section_name, subsection_name)
        self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)

        summary_lines = [f"Se añadieron {len(files_to_add)} fichero(s)."]
        if subsection_name:
            summary_lines.append(f"También se incorporaron a la subsección '{subsection_name}'.")
        if skipped_outside_project:
            summary_lines.append(
                f"Se omitieron {len(skipped_outside_project)} fichero(s) por estar fuera del proyecto."
            )
        if skipped_unavailable:
            summary_lines.append(
                f"Se omitieron {len(skipped_unavailable)} fichero(s) por no estar cargados en la vista de código."
            )

        messagebox.showinfo("Ficheros agregados", "\n".join(summary_lines))

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

    def _on_section_spacer_click(self, event=None):
        """Deselect sections when clicking the fixed spacer below the tree."""
        selected = self.section_tree.selection()
        if selected:
            self.section_tree.selection_remove(*selected)
        self._on_section_select(force_reload=True)
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
        
        return_files = self.var_return_files.get()
        return_chunks = self.var_return_chunks.get()

        include_project_tree = False
        if hasattr(self.controller, 'config_manager'):
            include_project_tree = self.controller.config_manager.get_include_project_tree()

        # Get file limit from slider
        try:
            min_files = int(self.limit_var.get())
        except:
            min_files = 10

        selected_files_data = self._get_files_for_prompt()
        selected_file_paths = [f['path'] for f in selected_files_data]

        # Resolve AI selection (auto mode or manual)
        selected_ai = self.cmb_ai.get()
        if selected_ai == self.AUTO_AI_OPTION:
            selected_ai = self._get_auto_ai()

        if selected_ai == self.AGENT_AI_OPTION:
            clipboard_content = self._build_agent_clipboard_prompt(
                text=text,
                selected_files=selected_files_data,
                selected_section=section,
                selected_subsection=subsection,
                return_files=return_files,
                return_chunks=return_chunks,
                include_project_tree=include_project_tree
            )

            self.clipboard_clear()
            self.clipboard_append(clipboard_content)
            print(f"Agente: Prompt copiado con {len(selected_files_data)} ficheros priorizados")
        else:
            clipboard_content = text
            clipboard_content += f"\n\n{self.controller.get_code_output_prompt(return_files=return_files, return_chunks=return_chunks)}"

            if include_project_tree:
                project_tree_block = self.controller.get_project_tree_prompt_block()
                if project_tree_block:
                    clipboard_content += f"\n\n{project_tree_block}"

            self.clipboard_clear()
            self.clipboard_append(clipboard_content)

        try:
            if self._should_export_prompts_as_folder():
                success, export_path = self.controller.export_files_to_codigo_folder(selected_files_data)
                if not success:
                    raise RuntimeError(export_path)
            else:
                prompt = self.controller.generate_prompt(
                    text,
                    selected_section=section,
                    selected_subsection=subsection,
                    return_files=return_files,
                    return_chunks=return_chunks,
                    include_file_headers=self._should_include_file_headers_in_codigo_txt(),
                    include_project_tree=include_project_tree,
                    min_files=min_files,
                    file_paths=selected_file_paths
                )

                documents_path = os.path.join(os.path.expanduser("~"), "Documents")
                export_path = os.path.join(documents_path, "codigo.txt")

                # Ensure directory exists (should exist on Mac, but good practice)
                os.makedirs(documents_path, exist_ok=True)

                with open(export_path, "w", encoding="utf-8") as f:
                    f.write(prompt)

            if selected_ai != self.AGENT_AI_OPTION:
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
            file_path = self._get_tree_item_path(item)
            if file_path in files_map:
                selected_files_data.append(files_map[file_path])

        return selected_files_data

    def _build_agent_clipboard_prompt(
        self,
        text,
        selected_files,
        selected_section=None,
        selected_subsection=None,
        return_files=False,
        return_chunks=False,
        include_project_tree=False
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

        if include_project_tree:
            project_tree_block = self.controller.get_project_tree_prompt_block()
            if project_tree_block:
                lines.extend(["", project_tree_block])

        lines.extend([
            "",
            "FORMA DE TRABAJO:",
            "- Prioriza solución rápida, concreta y correcta.",
            "- No hagas exploración amplia si ya encuentras solución en lista prioritaria.",
            "- Antes de modificar, identifica qué archivos vas a tocar.",
            "- Si hay varias opciones, elige la menos invasiva compatible con la tarea."
        ])
        lines.extend([
            "",
            self.controller.get_code_output_prompt(return_files=return_files, return_chunks=return_chunks)
        ])

        return "\n".join(lines)

    def _should_export_prompts_as_folder(self):
        """Returns whether prompt exports should use ~/Documents/codigo/."""
        if hasattr(self.controller, "config_manager"):
            return bool(self.controller.config_manager.get_export_prompts_as_folder())
        return False

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
                    menu.add_command(label="Agregar ficheros", command=self._on_add_files_to_selected_section)
                    menu.add_separator()
                    menu.add_command(label="Tamaño estructuras", command=self._on_show_structure_sizes)
                    menu.add_separator()
                    menu.add_command(label="Generar Prompt Docs", command=self._on_generate_docs)
                    menu.add_separator()
                    menu.add_command(label="Editar Sección", command=self._on_edit_section)
                    menu.add_command(label="Eliminar Sección", command=self._on_delete_section)
                elif iid.startswith("SS:"):
                    # Subsection context menu
                    menu.add_command(label="Agregar ficheros", command=self._on_add_files_to_selected_section)
                    menu.add_separator()
                    menu.add_command(label="Tamaño estructuras", command=self._on_show_structure_sizes)
                    menu.add_separator()
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
            file_path = self._get_tree_item_path(item)
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
            if self._should_export_prompts_as_folder():
                success, result = self.controller.export_files_to_codigo_folder(selected_files_data)
            else:
                # 2. Build prompt manually for the specific list of files
                prompt = f"Petición del Usuario: {prompt_instruction}\n\nArchivos de Contexto:\n"
                for f in selected_files_data:
                    if self._should_include_file_headers_in_codigo_txt():
                        prompt += f"\n--- Archivo: {f['rel_path']} ---\n"
                        prompt += f.get('content', '') + "\n"
                    else:
                        prompt += f.get('content', '')

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
                if selected_ai == self.AUTO_AI_OPTION:
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
            self._remove_file_tree_item(iid)

    def _remove_file_tree_item(self, item_id):
        """Removes a file row from the visible table."""
        file_path = self._get_tree_item_path(item_id)
        if not file_path:
            return

        filename = os.path.basename(file_path)
        self.tree.delete(item_id)
        self._schedule_folder_chip_refresh()
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
        
        full_path = self._get_tree_item_path(selected[0])
        if not full_path:
            return None

        file_data = self.controller.get_file_content_by_path(full_path)
        if file_data:
            return file_data
        return None

    def _on_file_copy(self):
        file_data = self._get_selected_file_content()
        if file_data:
            self.clipboard_clear()
            self.clipboard_append(f"--- Archivo: {file_data['rel_path']} ---\n{file_data['content']}")
            print(f"CodeView: Copied {file_data['rel_path']} to clipboard")

    def _on_file_concat_clipboard(self):
        file_data = self._get_selected_file_content()
        if file_data:
            clipboard_content = f"--- Archivo: {file_data['rel_path']} ---\n{file_data['content']}"
            try:
                current = self.clipboard_get()
                new_content = current + "\n\n" + clipboard_content
            except:
                new_content = clipboard_content
            
            self.clipboard_clear()
            self.clipboard_append(new_content)
            print(f"CodeView: Concatenated {file_data['rel_path']} to clipboard")

    def _on_file_save_txt(self):
        file_data = self._get_selected_file_content()
        if file_data:
            success, result = self.controller.save_content_to_codigo_txt(
                self._build_codigo_txt_file_content(file_data),
                append=False
            )
            if success:
                print(f"CodeView: Saved {file_data['rel_path']} to {result}")
            else:
                messagebox.showerror("Error", f"No se pudo guardar: {result}")

    def _on_file_concat_txt(self):
        file_data = self._get_selected_file_content()
        if file_data:
            success, result = self.controller.save_content_to_codigo_txt(
                self._build_codigo_txt_file_content(file_data),
                append=True,
                append_separator=self._get_codigo_txt_append_separator()
            )
            if success:
                print(f"CodeView: Concatenated {file_data['rel_path']} to {result}")
            else:
                messagebox.showerror("Error", f"No se pudo guardar: {result}")
