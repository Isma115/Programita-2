import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, simpledialog
import tkinter.messagebox as messagebox
import difflib
import threading
import os
import re
import textwrap
import time
import webbrowser
from PIL import Image, ImageTk, ImageDraw
from src.addons.structure_header_replace import detect_code_structure
from src.addons.Arbitrary_sus import create_styled_text_widget as arb_create_styled_text_widget
from src.addons.Arbitrary_sus import highlight_syntax as arb_highlight_syntax
from src.logic.region_outline import (
    extract_regions_for_files,
    get_region_match_keywords,
    normalize_region_match_text,
    tokenize_region_match_text,
)
from src.logic.structure_outline import (
    build_segment_full_text,
    build_segment_full_text_from_items,
    strip_region_markers_from_text,
)
from src.logic.app_paths import app_support_dir, bundled_path, is_frozen
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
    MIN_REGION_LIST_LIMIT = 1
    MAX_REGION_LIST_LIMIT = 20
    DEFAULT_REGION_LIST_LIMIT = 20
    AUTO_REGION_LIST_MAX_BYTES = 50 * 1024
    GENERIC_MARKUP_TAGS = {
        "article", "aside", "body", "col", "colgroup", "dd", "div", "dl", "dt",
        "footer", "header", "html", "li", "main", "nav", "ol", "p", "section",
        "span", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul"
    }
    DESCRIPTIVE_MARKUP_ATTRIBUTES = {
        "id", "class", "name", "role", "href", "src", "alt", "title",
        "type", "for", "key", "slot", "label"
    }
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
    FILE_HEADER_LINE_RE = re.compile(r"^--- Archivo:\s*(.+?)\s*---\s*$", re.MULTILINE)

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
        self._last_selected_segment = None
        self._last_selected_region = None
        self._last_selected_scope_iid = None
        self._last_selected_scope_kind = None
        self._visible_section_ids = []
        self._responsive_after_id = None
        self._checkbox_visual_size = Styles.scale_size(30)
        self.sections_dir_var = tk.StringVar(value="")
        self.section_view_mode = tk.StringVar(value="sections")
        self.region_list_limit_var = tk.IntVar(value=self.DEFAULT_REGION_LIST_LIMIT)
        self.region_list_auto_var = tk.BooleanVar(value=False)
        self._region_list_refresh_after = None
        self._region_list_limit_save_after = None
        self._search_timer = None
        self._last_relevant_files = None
        self._last_region_list_items = []
        self._region_rows_by_iid = {}
        self._discarded_file_paths = set()
        self.file_type_icons = {}
        self.toolbar_icons = {}
        self.section_tree_icons = {}
        self.folder_chip_widgets = []
        self.file_action_widgets = []
        self.region_name_highlight_widgets = []
        self._folder_chip_refresh_after = None
        self._segment_code_preview_text = ""
        self._segment_code_preview_file_hint = None
        self._segment_code_preview_file_map = {}
        self._segment_code_file_header_tags = []
        self._code_preview_mode = None
        self.is_file_preview_fullscreen = False
        self._sidebar_visible_before_preview_fullscreen = True

        if hasattr(self.controller, "config_manager"):
            try:
                saved_region_limit = self.controller.config_manager.get_region_list_limit()
                saved_region_limit = max(self.MIN_REGION_LIST_LIMIT, min(int(saved_region_limit), self.MAX_REGION_LIST_LIMIT))
                self.region_list_limit_var.set(saved_region_limit)
            except (AttributeError, TypeError, ValueError):
                pass
            try:
                self.region_list_auto_var.set(bool(self.controller.config_manager.get_region_list_auto_enabled()))
            except AttributeError:
                pass
            try:
                self.section_view_mode.set(self.controller.config_manager.get_last_code_view_mode())
            except AttributeError:
                pass

        self._initialize_output_state()
        self._load_file_type_icons()
        self._load_toolbar_icons()
        self._load_section_tree_icons()
        self._create_layout()
        self._set_return_mode(
            self.var_return_files.get(),
            self.var_return_chunks.get(),
            self.var_return_regions.get(),
            refresh_sections=False
        )

    def _initialize_output_state(self):
        """Initializes output-related toggles without rendering in-panel checkboxes."""
        val_return_files = False
        val_return_chunks = False
        val_return_regions = False
        if hasattr(self.controller, 'config_manager'):
            val_return_files = self.controller.config_manager.get_return_files()
            val_return_chunks = self.controller.config_manager.get_return_chunks()
            val_return_regions = self.controller.config_manager.get_return_regions()

        if val_return_files and (val_return_chunks or val_return_regions):
            val_return_chunks = False
            val_return_regions = False
        elif val_return_chunks and val_return_regions:
            val_return_regions = False

        self.var_return_files = tk.BooleanVar(value=val_return_files)
        self.var_return_chunks = tk.BooleanVar(value=val_return_chunks)
        self.var_return_regions = tk.BooleanVar(value=val_return_regions)
        self.var_include_file_headers = tk.BooleanVar(value=True)

        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_return_files(val_return_files)
            self.controller.config_manager.set_return_chunks(val_return_chunks)
            self.controller.config_manager.set_return_regions(val_return_regions)
            self.controller.config_manager.set_include_file_headers_in_codigo_txt(True)

    def _load_file_type_icons(self):
        """Loads file type icons used by the code table."""
        self.file_type_icons = {}
        try:
            base_path = bundled_path("assets", "icons", "filetypes")
            legacy_js_icon_path = bundled_path("assets", "icons", "javascript_icon.png")
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

    def _load_toolbar_icons(self):
        """Loads static toolbar icons used by Code View controls."""
        self.toolbar_icons = {}
        try:
            base_path = bundled_path("assets", "icons")
            icon_size = Styles.scale_size(18)
            send_icon_size = Styles.scale_size(24)
            icon_map = {
                "reload": "reload.png",
                "view": "view_eye.png",
                "back": "arrow_back_left.png",
                "folder": "folder_open.png",
            }

            for icon_key, filename in icon_map.items():
                icon_path = os.path.join(base_path, filename)
                if not os.path.exists(icon_path):
                    continue
                image = Image.open(icon_path).convert("RGBA")
                alpha = image.getchannel("A")
                image = Image.new("RGBA", image.size, (255, 255, 255, 0))
                image.putalpha(alpha)
                image = image.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                self.toolbar_icons[icon_key] = ImageTk.PhotoImage(image)

            self.toolbar_icons["send"] = self._create_send_toolbar_icon(size=(send_icon_size, send_icon_size))
            self.toolbar_icons["project_prev"] = self._create_project_nav_icon("prev", size=(icon_size, icon_size))
            self.toolbar_icons["project_next"] = self._create_project_nav_icon("next", size=(icon_size, icon_size))
            self.toolbar_icons["fullscreen_enter"] = self._create_fullscreen_toolbar_icon("enter", size=(icon_size, icon_size))
            self.toolbar_icons["fullscreen_exit"] = self._create_fullscreen_toolbar_icon("exit", size=(icon_size, icon_size))
        except Exception as exc:
            print(f"CodeView: Error cargando iconos de toolbar: {exc}")

    def _create_send_toolbar_icon(self, size=(18, 18)):
        """Creates a crisp paper-plane send icon for prompt actions."""
        upscale = 6
        large_size = (size[0] * upscale, size[1] * upscale)
        image = Image.new("RGBA", large_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = "#eef4ff"
        stroke = max(5, round(min(large_size) / 13))
        points = [
            (round(large_size[0] * 0.14), round(large_size[1] * 0.50)),
            (round(large_size[0] * 0.84), round(large_size[1] * 0.18)),
            (round(large_size[0] * 0.62), round(large_size[1] * 0.82)),
            (round(large_size[0] * 0.51), round(large_size[1] * 0.56)),
        ]
        draw.polygon(points, outline=color, fill=None, width=stroke)
        draw.line(
            [
                (round(large_size[0] * 0.16), round(large_size[1] * 0.50)),
                (round(large_size[0] * 0.50), round(large_size[1] * 0.56)),
            ],
            fill=color,
            width=stroke,
            joint="curve",
        )
        image = image.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    def _create_project_nav_icon(self, direction, size=(18, 18)):
        """Creates a simple chevron icon for switching projects."""
        upscale = 6
        large_size = (size[0] * upscale, size[1] * upscale)
        image = Image.new("RGBA", large_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = "#eef4ff"
        stroke = max(6, round(min(large_size) / 9))

        if direction == "next":
            points = [
                (round(large_size[0] * 0.34), round(large_size[1] * 0.20)),
                (round(large_size[0] * 0.68), round(large_size[1] * 0.50)),
                (round(large_size[0] * 0.34), round(large_size[1] * 0.80)),
            ]
        else:
            points = [
                (round(large_size[0] * 0.66), round(large_size[1] * 0.20)),
                (round(large_size[0] * 0.32), round(large_size[1] * 0.50)),
                (round(large_size[0] * 0.66), round(large_size[1] * 0.80)),
            ]

        draw.line(points, fill=color, width=stroke, joint="curve")
        image = image.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    def _create_fullscreen_toolbar_icon(self, mode, size=(18, 18)):
        """Creates a crisp fullscreen enter/exit icon for the file preview header."""
        upscale = 6
        large_size = (size[0] * upscale, size[1] * upscale)
        image = Image.new("RGBA", large_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = "#eef4ff"
        stroke = max(6, round(min(large_size) / 10))
        margin = round(min(large_size) * 0.18)
        short = round(min(large_size) * 0.22)
        left = margin
        top = margin
        right = large_size[0] - margin
        bottom = large_size[1] - margin

        def segment(points):
            draw.line(points, fill=color, width=stroke, joint="curve")

        if mode == "enter":
            segment([(left + short, top), (left, top), (left, top + short)])
            segment([(right - short, top), (right, top), (right, top + short)])
            segment([(left, bottom - short), (left, bottom), (left + short, bottom)])
            segment([(right - short, bottom), (right, bottom), (right, bottom - short)])
        else:
            segment([(left, top + short), (left, top), (left + short, top)])
            segment([(right - short, top), (right, top), (right, top + short)])
            segment([(left + short, bottom), (left, bottom), (left, bottom - short)])
            segment([(right, bottom - short), (right, bottom), (right - short, bottom)])

        image = image.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    def _load_section_tree_icons(self):
        """Creates stylized expand/collapse icons for the sections tree."""
        icon_size = Styles.scale_size(14)
        self.section_tree_icons = {
            "collapsed": self._create_section_tree_arrow_icon("collapsed", size=(icon_size, icon_size)),
            "expanded": self._create_section_tree_arrow_icon("expanded", size=(icon_size, icon_size)),
            "spacer": self._create_section_tree_arrow_icon("spacer", size=(icon_size, icon_size)),
        }

    def _create_section_tree_arrow_icon(self, mode, size=(18, 18)):
        """Draws a compact two-tone arrow badge used in the sections hierarchy."""
        upscale = 6
        large_size = (size[0] * upscale, size[1] * upscale)
        image = Image.new("RGBA", large_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if mode == "spacer":
            spacer = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            return ImageTk.PhotoImage(spacer)

        badge_fill = (27, 47, 79, 220)
        badge_outline = "#3e7ee0"
        arrow_shadow = "#245fb8"
        arrow_highlight = "#f2f7ff"
        min_side = min(large_size)
        inset = round(min_side * 0.05)
        radius = round(min_side * 0.22)
        stroke_outer = max(8, round(min_side * 0.14))
        stroke_inner = max(4, round(min_side * 0.07))

        draw.rounded_rectangle(
            (inset, inset, large_size[0] - inset, large_size[1] - inset),
            radius=radius,
            fill=badge_fill,
            outline=badge_outline,
            width=max(3, round(min_side * 0.035)),
        )

        if mode == "expanded":
            points = [
                (round(large_size[0] * 0.22), round(large_size[1] * 0.34)),
                (round(large_size[0] * 0.50), round(large_size[1] * 0.68)),
                (round(large_size[0] * 0.78), round(large_size[1] * 0.34)),
            ]
        else:
            points = [
                (round(large_size[0] * 0.34), round(large_size[1] * 0.22)),
                (round(large_size[0] * 0.68), round(large_size[1] * 0.50)),
                (round(large_size[0] * 0.34), round(large_size[1] * 0.78)),
            ]

        draw.line(points, fill=arrow_shadow, width=stroke_outer, joint="curve")
        draw.line(points, fill=arrow_highlight, width=stroke_inner, joint="curve")

        image = image.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    @classmethod
    def _get_ai_config_path(cls):
        cwd_path = os.path.join(os.getcwd(), cls.AI_CONFIG_FILENAME)
        bundled_cfg_path = bundled_path(cls.AI_CONFIG_FILENAME)
        app_support_cfg_path = os.path.join(str(app_support_dir()), cls.AI_CONFIG_FILENAME)

        candidate_paths = []
        if os.path.exists(cwd_path):
            candidate_paths.append(cwd_path)
        if is_frozen():
            candidate_paths.append(app_support_cfg_path)
        candidate_paths.append(bundled_cfg_path)

        for path in candidate_paths:
            if os.path.exists(path):
                return path

        return app_support_cfg_path if is_frozen() else cwd_path

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
            text="",
            image=self.toolbar_icons.get("project_prev"),
            compound="center",
            style="Nav.TButton",
            width=2,
            command=lambda: self.controller.prev_project()
        )
        self.btn_prev_project.pack(side="left")
        attach_tooltip(self.btn_prev_project, "Proyecto previo")

        self.lbl_project_name = ttk.Label(
            self.project_bar,
            text="Sin proyecto",
            style="TLabel",
            anchor="center",
            font=(Styles.FONT_FAMILY, 18)
        )
        self.lbl_project_name.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_next_project = ttk.Button(
            self.project_bar,
            text="",
            image=self.toolbar_icons.get("project_next"),
            compound="center",
            style="Nav.TButton",
            width=2,
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

        self.btn_change_sections_dir = ttk.Button(
            self.project_bar,
            text="",
            image=self.toolbar_icons.get("folder"),
            compound="center",
            style="AddProject.TButton",
            width=2,
            command=self._on_change_sections_directory
        )
        self.btn_change_sections_dir.pack(side="left", padx=(6, 0))
        attach_tooltip(self.btn_change_sections_dir, "Cambiar carpeta de secciones")

        # Initialize project label
        self._update_project_label()

    def _create_top_bar(self, parent):
        """Creates the toolbar with path filter, AI selector and extensions."""
        self.top_bar = ttk.Frame(parent, style="Main.TFrame")
        self.top_bar.pack(side="top", fill="x", padx=10, pady=(2, 8))

        self.limit_var = tk.DoubleVar(value=self.DEFAULT_MAX_FILE_LIMIT)
        self.max_limit_var = tk.DoubleVar(value=self.DEFAULT_MAX_FILE_LIMIT)

        # Container for controls
        self.slider_frame = ttk.Frame(self.top_bar, style="Main.TFrame")
        self.slider_frame.pack(fill="x", expand=True, padx=20)
        self.slider_frame.columnconfigure(0, weight=4)
        self.slider_frame.columnconfigure(1, weight=3)
        self.slider_frame.columnconfigure(2, weight=2)
        self.slider_frame.columnconfigure(3, weight=0)
        self.slider_frame.rowconfigure(0, weight=1)

        self.path_filter_var = tk.StringVar(value="")

        self.path_filter_shell = self._create_rounded_shell(self.slider_frame)
        self.path_filter_shell.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.path_filter_title = tk.Label(
            self.path_filter_shell,
            text="Buscar...",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        )
        self.path_filter_title.pack(fill="x", padx=10, pady=(3, 0))

        self.path_filter_input_shell = tk.Frame(
            self.path_filter_shell,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        self.path_filter_input_shell.pack(fill="x", padx=8, pady=(0, 6))

        self.txt_path_filter = tk.Entry(
            self.path_filter_input_shell,
            textvariable=self.path_filter_var,
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            width=30,
            font=(Styles.FONT_FAMILY, 12)
        )
        self.txt_path_filter._skip_soften = True
        Styles.strip_classic_widget_chrome(self.txt_path_filter)
        self.txt_path_filter.pack(fill="both", expand=True, padx=(2, 2), pady=(1, 1), ipady=4)
        self.path_filter_var.trace_add("write", self._on_path_filter_change)

        # AI Selector
        self.ai_selector_shell = self._create_rounded_shell(self.slider_frame)
        self.ai_selector_shell.grid(row=0, column=1, sticky="ew", padx=8)

        self.ai_selector_title = tk.Label(
            self.ai_selector_shell,
            text="Seleccionar IA",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        )
        self.ai_selector_title.pack(fill="x", padx=10, pady=(3, 0))

        self.ai_var = tk.StringVar()
        self.cmb_ai = ttk.Combobox(
            self.ai_selector_shell,
            textvariable=self.ai_var, 
            values=self.AI_ORDER,
            state="readonly",
            width=22,
            style="Borderless.TCombobox"
        )
        self.cmb_ai.current(0)
        self.cmb_ai.pack(fill="x", padx=8, pady=(0, 6), ipady=0)

        # Extension Filter
        saved_extensions = ""
        if hasattr(self, 'controller') and hasattr(self.controller, 'config_manager'):
            saved_extensions = self.controller.config_manager.get_code_extensions_filter()
        self.ext_var = tk.StringVar(value=saved_extensions)

        self.ext_shell = self._create_rounded_shell(self.slider_frame)
        self.ext_shell.grid(row=0, column=2, sticky="ew", padx=8)

        self.ext_title = tk.Label(
            self.ext_shell,
            text="Extensiones",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        )
        self.ext_title.pack(fill="x", padx=10, pady=(3, 0))

        ext_frame = tk.Frame(
            self.ext_shell,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        ext_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.ext_input_shell = tk.Frame(
            ext_frame,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        self.ext_input_shell.pack(side="left", fill="x", expand=True)

        self.txt_ext = tk.Entry(
            self.ext_input_shell,
            textvariable=self.ext_var,
            bg="#1a2a3a",
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            bd=0,
            highlightthickness=0,
            relief="flat",
            width=17,
            font=(Styles.FONT_FAMILY, 12)
        )
        self.txt_ext._skip_soften = True
        Styles.strip_classic_widget_chrome(self.txt_ext)
        self.txt_ext.pack(fill="both", expand=True, padx=(2, 2), pady=(1, 1), ipady=4)  # [
        self.ext_var.trace_add("write", self._on_extension_change)

        self.reload_shell = self._create_rounded_shell(self.slider_frame)
        self.reload_shell.grid(row=0, column=3, sticky="ns", padx=(8, 0))

        self.reload_title = tk.Label(
            self.reload_shell,
            text="Recargar",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        )
        self.reload_title.pack(fill="x", padx=10, pady=(3, 0))

        self.reload_button_shell = tk.Frame(
            self.reload_shell,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
         # [MODIFICACIÓN] Cambiar pady=(0, 3) a pady=(0, 0) para reducir el espacio vertical
        # Esto hace que el borde azul del marco exterior se vea más bajo
        self.reload_button_shell.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_reload_project = self._create_rounded_icon_button(
            self.reload_button_shell,
            command=self._on_reload_project_files,
            icon_key="reload",
            text="↻",
            width=Styles.scale_size(52),
            height=Styles.scale_size(30),
            host_bg=Styles.COLOR_INPUT_BG
        )
        self.btn_reload_project.pack(fill="x", ipady=0, pady=(0, 0))
        attach_tooltip(self.btn_reload_project, "Recargar todos los ficheros y restaurar descartados")

        if hasattr(self, 'controller') and hasattr(self.controller, 'config_manager'):
            min_limit = self.controller.config_manager.get_file_limit()
            max_limit = self.controller.config_manager.get_max_file_limit()
            self.limit_var.set(min_limit)
            self.max_limit_var.set(max_limit)
            min_limit, max_limit = self._normalize_file_limits()
            self._persist_file_limits(min_limit, max_limit)

        self.after_idle(self._update_top_bar_alignment)

    def _create_file_tree(self, parent):
        """Creates the file listing treeview and the segment code preview area."""
        self.tree_frame = ttk.Frame(parent, style="Main.TFrame")
        self.tree_frame.pack(side="top", fill="both", expand=True, padx=10)

        self.file_list_shell = tk.Frame(
            self.tree_frame,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            highlightthickness=0,
            bd=0
        )
        self.file_list_shell.pack(fill="both", expand=True)

        self.columns = ("folder", "size", "type", "view", "full_path", "folder_chip")
        self.tree = ttk.Treeview(
            self.file_list_shell,
            columns=self.columns,
            displaycolumns=("folder", "size", "type", "view"),
            show="tree headings",
            selectmode="extended",
            style="Files.Treeview"
        )
        self.tree.heading("#0", text="Nombre")
        self.tree.heading("folder", text="Ruta")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("view", text="Ver")

        self.tree.column("#0", anchor="w", stretch=True, width=360, minwidth=240)
        self.tree.column("folder", anchor="w", stretch=True, width=180, minwidth=120)
        self.tree.column("size", anchor="center", stretch=False, width=110, minwidth=90)
        self.tree.column("type", anchor="center", stretch=False, width=140, minwidth=110)
        self.tree.column("view", anchor="center", stretch=False, width=100, minwidth=84)
        self.tree.column("full_path", width=0, stretch=False, minwidth=0)
        self.tree.column("folder_chip", width=0, stretch=False, minwidth=0)
        self._configure_file_tree_style()

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
        self.file_context_menu.add_command(label="📂 Ir a archivo", command=self._on_go_to_file_from_file_list)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="📋 Copiar al Portapapeles", command=self._on_file_copy)
        self.file_context_menu.add_command(label="➕ Concatenar al Portapapeles", command=self._on_file_concat_clipboard)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="💾 Guardar en codigo.txt", command=self._on_file_save_txt)
        self.file_context_menu.add_command(label="📥 Concatenar en codigo.txt", command=self._on_file_concat_txt)

        # Bind Right Click for Files
        self.tree.bind("<Button-2>", self._show_file_context_menu)
        self.tree.bind("<Button-3>", self._show_file_context_menu)
        self.tree.bind("<Control-Button-1>", self._show_file_context_menu)

        self.segment_code_shell = tk.Frame(
            self.tree_frame,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            highlightthickness=0,
            bd=0
        )

        self.segment_code_header_row = tk.Frame(
            self.segment_code_shell,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        self.segment_code_header_row.pack(fill="x", padx=8, pady=(8, 4))

        self.segment_code_back_button = self._create_rounded_icon_button(
            self.segment_code_header_row,
            command=self._on_preview_back,
            icon_key="back",
            text="←",
            width=Styles.scale_size(34),
            height=Styles.scale_size(30),
            host_bg=Styles.COLOR_INPUT_BG
        )
        self.segment_code_back_button.pack(side="left", padx=(0, 8))
        attach_tooltip(self.segment_code_back_button, "Volver a la lista de ficheros")

        self.btn_toggle_file_preview_fullscreen = ttk.Button(
            self.segment_code_header_row,
            image=self.toolbar_icons.get("fullscreen_enter"),
            text="",
            style="FullscreenToggle.TButton",
            command=self._toggle_file_preview_fullscreen
        )
        attach_tooltip(self.btn_toggle_file_preview_fullscreen, "Mostrar solo el código del fichero")

        self.segment_code_header = tk.Label(
            self.segment_code_header_row,
            text="Código del segmento",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            anchor="w"
        )
        self.segment_code_header.pack(side="left", fill="x", expand=True)

        self.segment_code_body = tk.Frame(
            self.segment_code_shell,
            bg=Styles.COLOR_INPUT_BG,
            bd=0,
            highlightthickness=0
        )
        self.segment_code_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.segment_code_line_numbers = tk.Text(
            self.segment_code_body,
            width=4,
            bg="#252526",
            fg="#858585",
            relief="flat",
            wrap="none",
            padx=8,
            pady=8,
            bd=0,
            highlightthickness=0,
            takefocus=0,
            state="disabled",
            cursor="arrow"
        )
        self.segment_code_line_numbers.tag_configure("line_number", justify="right")
        self.segment_code_line_numbers.pack(side="left", fill="y")

        self.segment_code_text = arb_create_styled_text_widget(self.segment_code_body, editable=False)
        self.segment_code_text.configure(wrap="none")
        self.segment_code_text.pack(side="left", fill="both", expand=True)

        self.segment_code_scrollbar = ttk.Scrollbar(
            self.segment_code_body,
            orient="vertical",
            command=self._on_segment_code_scrollbar,
            style="Vertical.TScrollbar"
        )
        self.segment_code_scrollbar.pack(side="right", fill="y")
        self.segment_code_text.configure(yscrollcommand=self._on_segment_code_yscroll)
        self.segment_code_text.configure(state="disabled")
        self.segment_code_line_numbers.configure(font=self.segment_code_text.cget("font"))
        self.segment_code_line_numbers.bind("<MouseWheel>", self._on_segment_code_mousewheel)
        self.segment_code_line_numbers.bind("<Button-4>", self._on_segment_code_mousewheel)
        self.segment_code_line_numbers.bind("<Button-5>", self._on_segment_code_mousewheel)

    def _show_file_list_view(self):
        if self.is_file_preview_fullscreen:
            self.is_file_preview_fullscreen = False
            self._apply_file_preview_fullscreen()
        if hasattr(self, "segment_code_shell") and self.segment_code_shell.winfo_manager():
            self.segment_code_shell.pack_forget()
        if hasattr(self, "file_list_shell") and not self.file_list_shell.winfo_manager():
            self.file_list_shell.pack(fill="both", expand=True)
        self._code_preview_mode = None
        self._update_file_preview_fullscreen_button()
        self._schedule_folder_chip_refresh()

    def _show_segment_code_view(self, code_text, title_text=None, file_hint=None, preview_mode="segment"):
        self._segment_code_preview_text = code_text or ""
        self._segment_code_preview_file_hint = file_hint
        self._segment_code_preview_file_map = self._build_segment_preview_file_map(self._segment_code_preview_text)
        self._code_preview_mode = preview_mode

        if preview_mode != "file" and self.is_file_preview_fullscreen:
            self.is_file_preview_fullscreen = False
            self._apply_file_preview_fullscreen()

        if hasattr(self, "file_list_shell") and self.file_list_shell.winfo_manager():
            self.file_list_shell.pack_forget()
        if hasattr(self, "segment_code_shell") and not self.segment_code_shell.winfo_manager():
            self.segment_code_shell.pack(fill="both", expand=True)

        if hasattr(self, "segment_code_header"):
            self.segment_code_header.configure(text=title_text or "Código del segmento")
        self._update_file_preview_fullscreen_button()
        self._update_segment_code_line_numbers(self._segment_code_preview_text)
        if hasattr(self, "segment_code_text"):
            self.segment_code_text.configure(state="normal")
            self.segment_code_text.delete("1.0", tk.END)
            self.segment_code_text.insert("1.0", self._segment_code_preview_text)
            try:
                arb_highlight_syntax(self.segment_code_text, file_hint)
            except Exception as exc:
                print(f"CodeView: Error applying segment preview syntax highlight: {exc}")

            if hasattr(self, "path_filter_var"):
                query = self.path_filter_var.get().strip()
                if query:
                    self._highlight_text_in_segment_code_view(query)

            self._apply_segment_code_file_header_links()
            self.segment_code_text.configure(state="disabled")

    def _build_segment_preview_file_map(self, code_text):
        """Builds a lookup from rendered relative file paths to absolute project paths."""
        project_manager = getattr(self.controller, "project_manager", None)
        files = list(project_manager.get_files()) if project_manager else []
        file_map = {}

        for file_info in files:
            rel_path = str(file_info.get("rel_path") or "").strip()
            full_path = str(file_info.get("path") or "").strip()
            if rel_path and full_path:
                file_map.setdefault(rel_path, full_path)

        project_root = getattr(project_manager, "current_project_path", None) if project_manager else None
        for match in self.FILE_HEADER_LINE_RE.finditer(code_text or ""):
            rel_path = match.group(1).strip()
            if rel_path in file_map:
                continue
            if project_root:
                candidate = os.path.abspath(os.path.join(project_root, rel_path))
                if os.path.isfile(candidate):
                    file_map[rel_path] = candidate

        return file_map

    def _clear_segment_code_file_header_links(self):
        """Removes dynamic file-header tags from the preview text widget."""
        if not hasattr(self, "segment_code_text"):
            return

        for tag_name in self._segment_code_file_header_tags:
            try:
                self.segment_code_text.tag_delete(tag_name)
            except Exception:
                pass
        self._segment_code_file_header_tags = []

    def _apply_segment_code_file_header_links(self):
        """Makes each rendered 'Archivo:' delimiter clickable."""
        if not hasattr(self, "segment_code_text"):
            return

        self._clear_segment_code_file_header_links()
        self.segment_code_text.tag_configure(
            "file_header_link_base",
            foreground=Styles.COLOR_ACCENT,
            underline=1
        )

        for index, match in enumerate(self.FILE_HEADER_LINE_RE.finditer(self._segment_code_preview_text or "")):
            rel_path = match.group(1).strip()
            full_path = self._segment_code_preview_file_map.get(rel_path)
            if not full_path:
                continue

            tag_name = f"file_header_link_{index}"
            start_index = f"1.0+{match.start()}c"
            end_index = f"1.0+{match.end()}c"
            self.segment_code_text.tag_add("file_header_link_base", start_index, end_index)
            self.segment_code_text.tag_add(tag_name, start_index, end_index)
            self.segment_code_text.tag_bind(
                tag_name,
                "<Button-1>",
                lambda _event, path=full_path: self._open_preview_file_in_external_editor(path)
            )
            self.segment_code_text.tag_bind(
                tag_name,
                "<Enter>",
                lambda _event: self.segment_code_text.configure(cursor="hand2")
            )
            self.segment_code_text.tag_bind(
                tag_name,
                "<Leave>",
                lambda _event: self.segment_code_text.configure(cursor="xterm")
            )
            self._segment_code_file_header_tags.append(tag_name)

    def _open_preview_file_in_external_editor(self, file_path):
        """Opens the chosen preview file in the user's currently running editor."""
        if not file_path:
            messagebox.showwarning("Aviso", "No se pudo resolver el archivo a abrir.")
            return "break"

        success, message = self.controller.open_file_in_external_editor(file_path)
        if not success:
            messagebox.showwarning(
                "Abrir en editor",
                f"No se pudo abrir el archivo en el editor.\n\n{message}"
            )
        return "break"

    def _highlight_text_in_segment_code_view(self, query):
        """Highlights the occurrences of the search query in the segment code view."""
        if not hasattr(self, "segment_code_text") or not self.segment_code_text:
            return
            
        self.segment_code_text.tag_remove("search_highlight", "1.0", tk.END)
        # Using a bright color with high contrast for search results
        self.segment_code_text.tag_configure("search_highlight", background="#ffff00", foreground="#000000")
        
        if not query:
            return
            
        start = "1.0"
        first_match = None
        while True:
            pos = self.segment_code_text.search(query, start, tk.END, nocase=True)
            if not pos:
                break
            if not first_match:
                first_match = pos
            end = f"{pos}+{len(query)}c"
            self.segment_code_text.tag_add("search_highlight", pos, end)
            start = end
            
        if first_match:
            self.segment_code_text.see(first_match)

    def _on_preview_back(self):
        """Returns from the code preview to the file list."""
        self._show_file_list_view()
        self._schedule_file_list_refresh()

    def _update_segment_code_line_numbers(self, code_text):
        """Refreshes the gutter with one line number per visible code line."""
        if not hasattr(self, "segment_code_line_numbers"):
            return

        normalized_text = str(code_text or "")
        line_count = max(normalized_text.count("\n") + 1, 1)
        gutter_width = max(4, len(str(line_count)) + 1)
        numbers_text = "\n".join(str(index) for index in range(1, line_count + 1))

        self.segment_code_line_numbers.configure(state="normal", width=gutter_width)
        self.segment_code_line_numbers.delete("1.0", tk.END)
        self.segment_code_line_numbers.insert("1.0", numbers_text, "line_number")
        self.segment_code_line_numbers.configure(state="disabled")
        self.segment_code_line_numbers.yview_moveto(0)

    def _on_segment_code_scrollbar(self, *args):
        """Scrolls both the code text and the line-number gutter."""
        if hasattr(self, "segment_code_text"):
            self.segment_code_text.yview(*args)
        if hasattr(self, "segment_code_line_numbers"):
            self.segment_code_line_numbers.yview(*args)

    def _on_segment_code_yscroll(self, first, last):
        """Keeps the scrollbar and gutter aligned with the code viewport."""
        if hasattr(self, "segment_code_scrollbar"):
            self.segment_code_scrollbar.set(first, last)
        if hasattr(self, "segment_code_line_numbers"):
            self.segment_code_line_numbers.yview_moveto(first)

    def _on_segment_code_mousewheel(self, event):
        """Delegates mouse-wheel scrolling from the line-number gutter to the code view."""
        if getattr(event, "delta", 0):
            step = -1 if event.delta > 0 else 1
            self._on_segment_code_scrollbar("scroll", step, "units")
        elif getattr(event, "num", None) == 4:
            self._on_segment_code_scrollbar("scroll", -1, "units")
        elif getattr(event, "num", None) == 5:
            self._on_segment_code_scrollbar("scroll", 1, "units")
        return "break"

    def _update_file_preview_fullscreen_button(self):
        """Shows header controls only when previewing a whole file."""
        if not hasattr(self, "btn_toggle_file_preview_fullscreen"):
            return

        if self._code_preview_mode == "file":
            if hasattr(self, "segment_code_back_button") and not self.segment_code_back_button.winfo_manager():
                self.segment_code_back_button.pack(side="left", padx=(0, 8))
            self.btn_toggle_file_preview_fullscreen.configure(
                image=self.toolbar_icons.get("fullscreen_exit") if self.is_file_preview_fullscreen else self.toolbar_icons.get("fullscreen_enter"),
                text="" if self.toolbar_icons.get("fullscreen_enter") else ("Salir" if self.is_file_preview_fullscreen else "Expandir")
            )
            if not self.btn_toggle_file_preview_fullscreen.winfo_manager():
                self.btn_toggle_file_preview_fullscreen.pack(side="right")
        else:
            if hasattr(self, "segment_code_back_button") and self.segment_code_back_button.winfo_manager():
                self.segment_code_back_button.pack_forget()
            if self.btn_toggle_file_preview_fullscreen.winfo_manager():
                self.btn_toggle_file_preview_fullscreen.pack_forget()

    def _toggle_file_preview_fullscreen(self):
        """Toggles a local fullscreen mode focused on the file preview."""
        if self._code_preview_mode != "file":
            return
        self.is_file_preview_fullscreen = not self.is_file_preview_fullscreen
        self._apply_file_preview_fullscreen()

    def _is_right_panel_attached(self):
        """Returns True when the sections sidebar is attached to the split view."""
        try:
            return str(self.right_frame) in self.paned_window.panes()
        except Exception:
            return False

    def _apply_file_preview_fullscreen(self):
        """Shows only the code preview area while keeping a way to restore the layout."""
        main_layout = self._get_main_layout()

        if self.is_file_preview_fullscreen:
            self._sidebar_visible_before_preview_fullscreen = self._is_right_panel_attached()
            if self._sidebar_visible_before_preview_fullscreen:
                try:
                    self.paned_window.forget(self.right_frame)
                except Exception:
                    pass

            if hasattr(self, "project_bar") and self.project_bar.winfo_manager():
                self.project_bar.pack_forget()
            if hasattr(self, "top_bar") and self.top_bar.winfo_manager():
                self.top_bar.pack_forget()
            if hasattr(self, "prompt_frame") and self.prompt_frame.winfo_manager():
                self.prompt_frame.pack_forget()
            if hasattr(self, "tree_frame"):
                self.tree_frame.pack_configure(padx=0, pady=0)

            if main_layout:
                main_layout.set_navbar_visible(False)
        else:
            if hasattr(self, "project_bar") and not self.project_bar.winfo_manager():
                self.project_bar.pack(side="top", fill="x", padx=10, pady=(6, 2), before=self.tree_frame)
            if hasattr(self, "top_bar") and not self.top_bar.winfo_manager():
                self.top_bar.pack(side="top", fill="x", padx=10, pady=(2, 8), before=self.tree_frame)
            if hasattr(self, "prompt_frame") and not self.prompt_frame.winfo_manager():
                self.prompt_frame.pack(side="bottom", fill="x", padx=10, pady=10)
            if hasattr(self, "tree_frame"):
                self.tree_frame.pack_configure(padx=10, pady=0)

            if self._sidebar_visible_before_preview_fullscreen and not self._is_right_panel_attached():
                try:
                    self.paned_window.add(self.right_frame, minsize=self.MIN_SECTIONS_PANEL_WIDTH, stretch="never")
                except Exception:
                    pass
                self.after_idle(self._set_default_sections_panel_width)

            if main_layout:
                main_layout.set_navbar_visible(True)

        self._update_file_preview_fullscreen_button()

    def _get_main_layout(self):
        parent = self.master
        while parent is not None:
            if hasattr(parent, "set_navbar_visible"):
                return parent
            parent = getattr(parent, "master", None)
        return None

    def on_tab_shown(self):
        """Reapplies fullscreen chrome rules when the tab becomes visible."""
        if self.is_file_preview_fullscreen:
            self._apply_file_preview_fullscreen()

    def on_tab_hidden(self):
        """Restores shared chrome when leaving the code tab."""
        if self.is_file_preview_fullscreen:
            self.is_file_preview_fullscreen = False
            self._apply_file_preview_fullscreen()
        else:
            main_layout = self._get_main_layout()
            if main_layout:
                main_layout.set_navbar_visible(True)

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
            font=(Styles.FONT_FAMILY, row_font_size),
            rowheight=row_height
        )
        style.configure(
            "Files.Treeview.Heading",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground="#d7e4fb",
            font=(Styles.FONT_FAMILY, heading_font_size, "bold"),
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

    def _clear_region_name_highlight_overlays(self):
        """Removes any existing region-name highlight overlays."""
        for widget in self.region_name_highlight_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.region_name_highlight_widgets = []

    def _clear_file_action_overlays(self):
        """Removes the 'Ver' button overlays from the file table."""
        for widget in self.file_action_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.file_action_widgets = []

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
        if radius <= 0:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
            return

        # Fill first without outlines to avoid visible circular corner artifacts.
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")

        for corner in (
            (x1, y1, x1 + radius * 2, y1 + radius * 2),
            (x2 - radius * 2, y1, x2, y1 + radius * 2),
            (x1, y2 - radius * 2, x1 + radius * 2, y2),
            (x2 - radius * 2, y2 - radius * 2, x2, y2),
        ):
            canvas.create_oval(*corner, fill=fill, outline="")

        if outline and width > 0:
            canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=width)
            canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=width)
            canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline, width=width)
            canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline, width=width)

            arc_boxes = (
                (x1, y1, x1 + radius * 2, y1 + radius * 2, 90),
                (x2 - radius * 2, y1, x2, y1 + radius * 2, 0),
                (x1, y2 - radius * 2, x1 + radius * 2, y2, 180),
                (x2 - radius * 2, y2 - radius * 2, x2, y2, 270),
            )
            for ax1, ay1, ax2, ay2, start in arc_boxes:
                canvas.create_arc(
                    ax1,
                    ay1,
                    ax2,
                    ay2,
                    start=start,
                    extent=90,
                    style="arc",
                    outline=outline,
                    width=width
                )

    def _create_rounded_shell(self, parent, radius=None, bg=None, outline=None):
        """Creates a canvas-based rounded shell that can host other widgets."""
        if radius is None:
            radius = Styles.scale_size(Styles.CORNER_RADIUS)
        
        bg = bg or Styles.COLOR_INPUT_BG
        outline = outline or Styles.COLOR_BORDER
        
        canvas = tk.Canvas(
            parent,
            bg=Styles.COLOR_BG_MAIN,
            bd=0,
            highlightthickness=0,
            relief="flat"
        )
        
        def on_reconfig(event):
            canvas.delete("all")
            w, h = event.width, event.height
            self._draw_rounded_rect(
                canvas, 
                1, 1, w-1, h-1, 
                radius=radius, 
                fill=bg, 
                outline=outline, 
                width=1
            )
            canvas.tag_lower("all")
            
        canvas.bind("<Configure>", on_reconfig)
        return canvas

    def _create_rounded_icon_button(
        self,
        parent,
        command,
        icon_key=None,
        text=None,
        width=None,
        height=None,
        host_bg=None
    ):
        """Builds a small rounded button using Canvas for lightweight custom chrome."""
        button_width = max(int(width or Styles.scale_size(34)), 24)
        button_height = max(int(height or Styles.scale_size(30)), 24)
        host_bg = host_bg or Styles.COLOR_INPUT_BG
        radius = max(6, min(button_height // 3, Styles.scale_size(Styles.CORNER_RADIUS)))

        canvas = tk.Canvas(
            parent,
            width=button_width,
            height=button_height,
            bg=host_bg,
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="hand2"
        )
        canvas.configure(takefocus=1)

        colors = {
            "normal": Styles.COLOR_SIDEBAR_CARD_INNER,
            "hover": Styles.COLOR_SELECTION_BG,
            "pressed": Styles.COLOR_PANE_DIVIDER,
            "border": Styles.COLOR_BORDER,
            "text": "#d9e6fb",
            "text_active": Styles.COLOR_BUTTON_FG_ACTIVE,
        }

        icon_image = self.toolbar_icons.get(icon_key) if icon_key else None
        label_font = Styles.scale_font((Styles.FONT_FAMILY, 11, "bold"))

        def redraw(state="normal"):
            canvas.delete("all")
            w = canvas.winfo_width() if canvas.winfo_width() > 1 else button_width
            h = canvas.winfo_height() if canvas.winfo_height() > 1 else button_height
            
            fill = colors.get(state, colors["normal"])
            fg = colors["text_active"] if state in {"hover", "pressed"} else colors["text"]
            self._draw_rounded_rect(
                canvas,
                1,
                1,
                w - 1,
                h - 1,
                radius=radius,
                fill=fill,
                outline=colors["border"],
                width=1
            )
            if icon_image is not None:
                canvas.create_image(w / 2, h / 2, image=icon_image)
            elif text:
                canvas.create_text(
                    w / 2,
                    h / 2,
                    text=text,
                    fill=fg,
                    font=label_font
                )

        canvas.bind("<Configure>", lambda e: redraw())

        def on_enter(_event):
            redraw("hover")

        def on_leave(_event):
            redraw("normal")

        def on_press(_event):
            redraw("pressed")

        def on_release(event):
            inside = 0 <= event.x <= button_width and 0 <= event.y <= button_height
            redraw("hover" if inside else "normal")
            if inside and callable(command):
                command()

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_press)
        canvas.bind("<ButtonRelease-1>", on_release)
        canvas.bind("<space>", lambda _event: command() if callable(command) else None)
        canvas.bind("<Return>", lambda _event: command() if callable(command) else None)

        redraw("normal")
        return canvas

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
        """Renders the extra controls layered over the file table."""
        self._folder_chip_refresh_after = None
        if not hasattr(self, "tree"):
            return

        self._clear_folder_chip_overlays()
        self._clear_region_name_highlight_overlays()
        self._clear_file_action_overlays()

        if not getattr(self, "file_list_shell", None) or not self.file_list_shell.winfo_manager():
            return

        chip_bg = "#2e3747"
        chip_fg = "#c2cad8"
        chip_font = (Styles.FONT_FAMILY, Styles.scale_size(12), "bold")
        chip_font_obj = tkfont.Font(font=chip_font)
        row_font = ttk.Style().lookup("Files.Treeview", "font") or (Styles.FONT_FAMILY, Styles.scale_size(13))
        row_font_obj = tkfont.Font(font=row_font)
        viewport_width = max(self.tree.winfo_width(), 0)
        viewport_height = max(self.tree.winfo_height(), 0)

        for item_id in self.tree.get_children():
            region_item = self._get_region_row_item(item_id)
            highlight_tokens = tuple((region_item or {}).get("_prompt_highlight_tokens") or ())
            if not region_item or not highlight_tokens:
                continue

            try:
                bbox = self.tree.bbox(item_id, "#0")
            except Exception:
                bbox = None

            if not bbox:
                continue

            x, y, width, height = bbox
            if width <= 24 or height <= 6:
                continue
            if x < 0 or y < 0:
                continue
            if (x + width) > viewport_width or (y + height) > viewport_height:
                continue

            header_text = (region_item.get("header") or region_item.get("name") or "Región").strip()
            highlight_spans = self._get_region_header_highlight_spans(header_text, highlight_tokens)
            if not highlight_spans:
                continue

            icon_reserved = Styles.scale_size(36)
            is_selected = item_id in self.tree.selection()
            row_bg = Styles.COLOR_SELECTION_BG if is_selected else self._get_file_row_background(item_id)
            match_height = row_font_obj.metrics("linespace")
            pad_x = Styles.scale_size(3)
            pad_y = 1
            for raw_word, start_pos, _end_pos in highlight_spans:
                prefix_display = f"   {header_text[:start_pos]}"
                overlay_x = x + icon_reserved + row_font_obj.measure(prefix_display) - pad_x
                overlay_width = max(row_font_obj.measure(raw_word) + (pad_x * 2), 12)
                overlay_height = max(match_height + (pad_y * 2) - 2, 10)
                overlay_y = y + max((height - overlay_height) / 2, 1)

                if overlay_x < x or (overlay_x + overlay_width) > (x + width):
                    continue

                canvas = tk.Canvas(
                    self.tree,
                    bg=row_bg,
                    bd=0,
                    highlightthickness=0,
                    relief="flat",
                    cursor="hand2"
                )
                canvas.place(x=overlay_x, y=overlay_y, width=overlay_width, height=overlay_height)

                self._draw_rounded_rect(
                    canvas,
                    0,
                    0,
                    overlay_width,
                    overlay_height,
                    radius=min(5, Styles.scale_size(5)),
                    fill="#f1c40f",
                    outline="#f1c40f",
                    width=0
                )
                canvas.create_text(
                    pad_x,
                    overlay_height / 2,
                    text=raw_word,
                    fill="#1b1b1b",
                    font=row_font,
                    anchor="w"
                )

                canvas.bind("<Button-1>", lambda event, iid=item_id: self._on_folder_chip_left_click(iid))
                canvas.bind("<Double-1>", lambda event, iid=item_id: self._on_folder_chip_double_click(iid))
                canvas.bind("<Button-2>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
                canvas.bind("<Button-3>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
                canvas.bind("<Control-Button-1>", lambda event, iid=item_id: self._on_folder_chip_right_click(event, iid))
                canvas.bind("<MouseWheel>", self._on_folder_chip_mousewheel)
                canvas.bind("<Button-4>", self._on_folder_chip_mousewheel)
                canvas.bind("<Button-5>", self._on_folder_chip_mousewheel)
                self.region_name_highlight_widgets.append(canvas)

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

        for item_id in self.tree.get_children():
            try:
                bbox = self.tree.bbox(item_id, "view")
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

            button_width = max(min(width - 12, Styles.scale_size(72)), Styles.scale_size(54))
            button_height = max(height - 10, Styles.scale_size(28))
            button = self._create_rounded_icon_button(
                self.tree,
                command=lambda iid=item_id: self._open_file_preview(iid),
                icon_key="view",
                text="Ver",
                width=button_width,
                height=button_height,
                host_bg=self._get_file_row_background(item_id)
            )
            button_x = x + max((width - button_width) // 2, 4)
            button_y = y + max((height - button_height) // 2, 3)
            button.place(x=button_x, y=button_y, width=button_width, height=button_height)
            self.file_action_widgets.append(button)

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
        view_width = max(Styles.scale_size(92), int(total_width * 0.11))
        folder_width = max(Styles.scale_size(170), int(total_width * 0.22))
        used_width = size_width + type_width + view_width + folder_width
        name_width = max(Styles.scale_size(240), total_width - used_width)

        self.tree.column("#0", width=name_width)
        self.tree.column("folder", width=folder_width)
        self.tree.column("size", width=size_width)
        self.tree.column("type", width=type_width)
        self.tree.column("view", width=view_width)
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

    def _get_region_row_item(self, item_id):
        """Returns the detected project region payload for a left-list row."""
        if not item_id:
            return None
        return self._region_rows_by_iid.get(item_id)

    def _normalize_existing_file_paths(self, file_paths):
        """Returns de-duplicated absolute file paths that exist on disk."""
        normalized_paths = []
        seen = set()

        for raw_path in file_paths or []:
            if not raw_path:
                continue
            normalized = os.path.abspath(os.path.expanduser(str(raw_path)))
            if normalized in seen:
                continue
            seen.add(normalized)
            if os.path.isfile(normalized):
                normalized_paths.append(normalized)

        return normalized_paths

    def _get_selected_scope_file_paths(self):
        """Returns files associated with the current right-side tree selection."""
        scope_kind, section_name, subsection_name, leaf_name = self._get_selected_tree_item_info()
        file_paths = []

        if scope_kind == "section" and section_name:
            file_paths = self.controller.section_manager.get_files_in_section(section_name)
        elif scope_kind == "subsection" and section_name and subsection_name:
            file_paths = self.controller.section_manager.get_files_in_subsection(section_name, subsection_name)
        elif scope_kind == "segment" and section_name and subsection_name and leaf_name:
            file_paths = self.controller.section_manager.get_files_in_segment(section_name, subsection_name, leaf_name)
        elif scope_kind == "region_segment" and leaf_name:
            region_payload = self.controller.region_segment_manager.get_region_segment(leaf_name) or {}
            seen_paths = set()
            for item in region_payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                file_path = item.get("file_path")
                if not file_path or file_path in seen_paths:
                    continue
                seen_paths.add(file_path)
                file_paths.append(file_path)

        return self._normalize_existing_file_paths(file_paths)

    def _select_file_path_for_navigation(self, file_paths, scope_label):
        """Chooses one file path to reveal in the system explorer."""
        if not file_paths:
            messagebox.showwarning("Ir a archivo", f"La {scope_label} seleccionada no tiene archivos disponibles.")
            return None

        if len(file_paths) > 1:
            messagebox.showinfo(
                "Ir a archivo",
                f"La {scope_label} contiene {len(file_paths)} archivos. Se abrirá el primero."
            )

        return file_paths[0]

    def _reveal_file_in_explorer(self, file_path):
        """Reveals one file in Finder/Explorer using the controller bridge."""
        success, message = self.controller.reveal_file_in_system_explorer(file_path)
        if not success:
            messagebox.showwarning(
                "Ir a archivo",
                f"No se pudo abrir el explorador para el archivo.\n\n{message}"
            )

    def _create_prompt_area(self, parent):
        """Creates the AI prompt text area and copy button."""
        self.prompt_frame = ttk.Frame(parent, style="Main.TFrame")
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
        self.txt_prompt.bind("<KeyRelease>", self._on_prompt_text_change)
        # Bind Ctrl+Enter (and Command+Enter on Mac) to copy prompt
        self.txt_prompt.bind("<Control-Return>", self._on_copy_prompt)
        self.txt_prompt.bind("<Command-Return>", self._on_copy_prompt)
        self.txt_prompt.pack(side="left", fill="x", expand=True, pady=5)
        
        # [MODIFICACIÓN] Se añade un Frame contenedor con padding superior para desplazar el botón hacia abajo
        btn_container = tk.Frame(self.prompt_frame, bg=Styles.COLOR_BG_MAIN) # Usar bg del tema principal o transparente si es posible, aquí se usa un frame simple
        btn_container.pack(side="right", padx=(10, 0), anchor="n", pady=(5, 0)) # pady=(5, 0) desplaza el botón 5 pixeles hacia abajo

        self.btn_copy = ttk.Button(
            btn_container, # [MODIFICACIÓN] El botón ahora se empaqueta dentro del contenedor desplazado
            text="" if self.toolbar_icons.get("send") else "Enviar",
            image=self.toolbar_icons.get("send"),
            compound="center",
            style="SendPrompt.Action.TButton",
            width=2,
            command=self._on_copy_prompt
        )
        self.btn_copy.pack(side="right") # [MODIFICACIÓN] Eliminado padx y anchor ya que están en el contenedor padre
        attach_tooltip(self.btn_copy, "Copiar prompt")

    def _create_right_pane(self):
        """Creates the right panel with sections header, search and tree."""
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame", width=self.DEFAULT_SECTIONS_PANEL_WIDTH)
        self.paned_window.add(self.right_frame, minsize=self.MIN_SECTIONS_PANEL_WIDTH, stretch="never")

        # Keep lower controls pinned to the bottom so the expandable tree cannot hide them.
        self.right_bottom_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_bottom_frame.pack(side="bottom", fill="x", expand=False)

        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="both", expand=True)

        self._create_sections_header(self.right_top_frame)
        self._create_section_search(self.right_top_frame)
        self._create_section_tree(self.right_top_frame)
        self._create_section_list_controls(self.right_bottom_frame)
        self.refresh_dynamic_paste_controls()

    def _create_sections_header(self, parent):
        """Creates the 'Secciones' header and directory label."""
        self.sections_header = ttk.Frame(parent, style="Sidebar.TFrame")
        self.sections_header.pack(fill="x")

        self.sections_header_var = tk.StringVar(value="Secciones")
        lbl_sections = ttk.Label(self.sections_header, textvariable=self.sections_header_var, style="Header.TLabel")
        lbl_sections.pack(side="left", fill="x", expand=True)

        self.lbl_sections_dir = tk.Label(
            parent,
            textvariable=self.sections_dir_var,
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            font=(Styles.FONT_FAMILY, 11),
            anchor="w",
            justify="left"
        )
        self.lbl_sections_dir.pack(fill="x", padx=12, pady=(0, 4))

        self._update_sections_directory_label()
        self._update_section_view_toggle_buttons()
        self.refresh_dynamic_paste_controls()

    def _create_section_mode_card(self, parent, column, mode, title):
        """Creates a folder-like card that switches between section list modes."""
        slot = tk.Frame(parent, bg=Styles.COLOR_INPUT_BG, cursor="hand2")
        slot.grid(row=0, column=column, sticky="sew", padx=(0, 6) if column == 0 else (6, 0))

        top_tab = tk.Frame(
            slot,
            bg=Styles.COLOR_BUTTON_BG,
            height=Styles.scale_size(10),
            width=Styles.scale_size(92),
            cursor="hand2",
            bd=0,
            highlightthickness=0
        )
        top_tab.pack(anchor="w", padx=(14, 0))
        top_tab.pack_propagate(False)

        body = tk.Frame(
            slot,
            bg=Styles.COLOR_SIDEBAR_CARD_INNER,
            cursor="hand2",
            bd=0,
            highlightthickness=0
        )
        body.pack(fill="x")

        title_label = tk.Label(
            body,
            text=title,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font((Styles.FONT_FAMILY, 15, "bold")),
            anchor="w",
            justify="left",
            padx=14,
            pady=Styles.scale_size(6)
        )
        title_label.pack(fill="x", pady=(10, 10))

        for widget in (slot, top_tab, body, title_label):
            widget.bind("<Button-1>", lambda event, selected_mode=mode: self._set_section_view_mode(selected_mode))

        attach_tooltip(body, title)
        self.section_mode_cards[mode] = {
            "slot": slot,
            "top_tab": top_tab,
            "body": body,
            "title": title_label,
        }

    def _create_section_search(self, parent):
        """Creates the section search input."""
        self.section_search_shell = tk.Frame(
            parent,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            highlightthickness=0,
            bd=0
        )
        self.section_search_shell.pack(fill="x", padx=8, pady=(4, 4))

        self.section_search_entry = tk.Entry(
            self.section_search_shell,
            font=(Styles.FONT_FAMILY, 15),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.section_search_entry.pack(fill="x", padx=10, pady=8, ipady=4)
        self.section_search_entry.bind("<KeyRelease>", self._on_section_search_change)
        self.section_search_entry.bind("<FocusIn>", self._on_section_search_focus_in)
        self.section_search_entry.bind("<FocusOut>", self._on_section_search_focus_out)
        self._section_search_placeholder_text = "Buscar..."
        self._section_search_placeholder_active = False
        self._show_section_search_placeholder()

    def _show_section_search_placeholder(self):
        """Displays the placeholder text inside the section search entry."""
        if not hasattr(self, "section_search_entry"):
            return
        self.section_search_entry.delete(0, tk.END)
        self.section_search_entry.insert(0, self._section_search_placeholder_text)
        self.section_search_entry.configure(fg=Styles.COLOR_DIM)
        self._section_search_placeholder_active = True

    def _hide_section_search_placeholder(self):
        """Clears the placeholder text before user input."""
        if not hasattr(self, "section_search_entry") or not self._section_search_placeholder_active:
            return
        self.section_search_entry.delete(0, tk.END)
        self.section_search_entry.configure(fg=Styles.COLOR_INPUT_FG)
        self._section_search_placeholder_active = False

    def _on_section_search_focus_in(self, event=None):
        """Removes the placeholder when the search entry gains focus."""
        self._hide_section_search_placeholder()

    def _on_section_search_focus_out(self, event=None):
        """Restores the placeholder when the search entry is empty."""
        if not hasattr(self, "section_search_entry"):
            return
        if not self.section_search_entry.get().strip():
            self._show_section_search_placeholder()

    def _get_section_search_query(self):
        """Returns the effective section search query excluding placeholder text."""
        if not hasattr(self, "section_search_entry") or self._section_search_placeholder_active:
            return ""
        return self.section_search_entry.get().strip().lower()

    def _create_section_tree(self, parent):
        """Creates the sections and subsections treeview."""
        self._configure_section_tree_style()
        self.section_list_shell = tk.Frame(
            parent,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            highlightthickness=0,
            bd=0
        )
        self.section_list_shell.pack(fill="both", expand=True, padx=8, pady=(4, 5))

        self.section_mode_tabs = tk.Frame(self.section_list_shell, bg=Styles.COLOR_INPUT_BG)
        self.section_mode_tabs.pack(fill="x", padx=10, pady=(0, 0))
        self.section_mode_tabs.columnconfigure(0, weight=1, uniform="section_modes")
        self.section_mode_tabs.columnconfigure(1, weight=1, uniform="section_modes")
        self.section_mode_cards = {}

        self._create_section_mode_card(
            self.section_mode_tabs,
            column=0,
            mode="sections",
            title="Secciones",
        )
        self._create_section_mode_card(
            self.section_mode_tabs,
            column=1,
            mode="regions",
            title="Regiones",
        )

        self.section_tree_body = tk.Frame(self.section_list_shell, bg=Styles.COLOR_INPUT_BG)
        self.section_tree_body.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        self.section_tree = ttk.Treeview(
            self.section_tree_body,
            show="tree",
            selectmode="browse",
            style="Section.Treeview",
            height=18
        )
        self.section_tree.column("#0", stretch=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_select)
        self.section_tree.bind("<<TreeviewOpen>>", self._on_section_tree_open, add="+")
        self.section_tree.bind("<<TreeviewClose>>", self._on_section_tree_close, add="+")
        self.section_tree.bind("<Button-1>", self._on_section_click)
        
        self.section_tree.tag_configure("section", font=(Styles.FONT_FAMILY, 15, "bold"), foreground=Styles.COLOR_FG_TEXT)
        self.section_tree.tag_configure("subsection", font=(Styles.FONT_FAMILY, 13), foreground=Styles.COLOR_FG_TEXT)
        self.section_tree.tag_configure("segment", font=(Styles.FONT_FAMILY, 12))
        self.section_tree.tag_configure("size_blue", foreground=Styles.COLOR_ACCENT)
        self.section_tree.tag_configure("size_green", foreground="#2ecc71")
        self.section_tree.tag_configure("size_yellow", foreground="#f1c40f")
        self.section_tree.tag_configure("size_red", foreground="#ff5c5c")
        
        self.section_tree.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        self.section_tree_bottom_spacer = tk.Frame(
            self.section_tree_body,
            bg=Styles.COLOR_INPUT_BG,
            height=8,
            cursor="arrow"
        )
        self.section_tree_bottom_spacer.pack(fill="x", padx=4, pady=(0, 2))
        self.section_tree_bottom_spacer.pack_propagate(False)
        self.section_tree_bottom_spacer.bind("<Button-1>", self._on_section_spacer_click)

        # Bind Right Click
        self.section_tree.bind("<Button-2>", self._show_context_menu)
        self.section_tree.bind("<Button-3>", self._show_context_menu)
        self.section_tree.bind("<Control-Button-1>", self._show_context_menu)
        self._update_section_view_toggle_buttons()

    def _configure_section_tree_style(self):
        """Uses a dedicated Treeview style without the default indicator glyph."""
        style = ttk.Style()
        row_height = Styles.scale_size(40)

        style.configure(
            "Section.Treeview",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            borderwidth=0,
            bordercolor=Styles.COLOR_INPUT_BG,
            relief="flat",
            font=Styles.FONT_MAIN,
            rowheight=row_height,
        )
        style.map(
            "Section.Treeview",
            background=[("selected", Styles.COLOR_SELECTION_BG)],
            foreground=[("selected", "#ffffff")],
        )
        style.layout(
            "Section.Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Treeitem.image", {"side": "left", "sticky": ""}),
                            (
                                "Treeitem.focus",
                                {
                                    "side": "left",
                                    "sticky": "nswe",
                                    "children": [
                                        ("Treeitem.text", {"sticky": "nswe"}),
                                    ],
                                },
                            ),
                        ],
                    },
                ),
            ],
        )

    def _create_section_list_controls(self, parent):
        """Creates controls associated with the current section/subsection selection."""
        self.dynamic_paste_status_frame = tk.Frame(
            parent,
            bg=Styles.COLOR_SIDEBAR_CARD_ALT,
            highlightthickness=0,
            bd=0
        )

        self.btn_cancel_dynamic_paste_inline = ttk.Button(
            self.dynamic_paste_status_frame,
            text="Cancelar pegado dinamico",
            style="ToolbarIcon.TButton",
            command=self._on_cancel_dynamic_paste
        )
        self.btn_cancel_dynamic_paste_inline.pack(side="top", fill="x", padx=8, pady=6)
        attach_tooltip(
            self.btn_cancel_dynamic_paste_inline,
            "Cancelar la secuencia activa de copiado y pegado dinamico"
        )

        self.region_list_limit_frame = tk.Frame(
            parent,
            bg=Styles.COLOR_SIDEBAR_CARD_ALT,
            highlightthickness=0,
            bd=0,
        )
        self.lbl_region_list_limit = tk.Label(
            self.region_list_limit_frame,
            text="Regiones listadas: 20",
            bg=Styles.COLOR_SIDEBAR_CARD_ALT,
            fg=Styles.COLOR_FG_TEXT,
            font=(Styles.FONT_FAMILY, 12, "bold"),
            anchor="w",
        )
        self.lbl_region_list_limit.pack(fill="x", padx=10, pady=(4, 0))
        self.region_list_limit_controls_row = tk.Frame(
            self.region_list_limit_frame,
            bg=Styles.COLOR_SIDEBAR_CARD_ALT,
            highlightthickness=0,
            bd=0,
        )
        self.region_list_limit_controls_row.pack(fill="x", padx=10, pady=(0, 4))
        self.region_list_limit_controls_row.columnconfigure(0, weight=1)
        self._configure_region_list_limit_slider_style()
        self.region_list_limit_slider = ttk.Scale(
            self.region_list_limit_controls_row,
            from_=self.MIN_REGION_LIST_LIMIT,
            to=self.MAX_REGION_LIST_LIMIT,
            orient=tk.HORIZONTAL,
            variable=self.region_list_limit_var,
            command=self._on_region_list_limit_change,
            style="RegionLimit.Horizontal.TScale",
            cursor="hand2",
        )
        self.region_list_limit_slider.grid(row=0, column=0, sticky="ew", pady=(2, 1))
        self.region_list_auto_check = tk.Checkbutton(
            self.region_list_limit_controls_row,
            text="Auto",
            variable=self.region_list_auto_var,
            command=self._on_region_list_auto_toggle,
            bg=Styles.COLOR_SIDEBAR_CARD_ALT,
            fg=Styles.COLOR_FG_TEXT,
            activebackground=Styles.COLOR_SIDEBAR_CARD_ALT,
            activeforeground=Styles.COLOR_FG_TEXT,
            selectcolor=Styles.COLOR_INPUT_BG,
            highlightthickness=0,
            bd=0,
            padx=6,
            pady=0,
            font=(Styles.FONT_FAMILY, 11, "bold"),
            cursor="hand2",
        )
        self.region_list_auto_check.grid(row=0, column=1, sticky="e", padx=(8, 0))
        attach_tooltip(
            self.region_list_auto_check,
            "Ajustar automáticamente las regiones visibles para no superar 50 KB acumulados"
        )
        self._apply_region_list_limit_control_state()
        self._update_region_list_limit_label()

    def _configure_region_list_limit_slider_style(self):
        """Configures a slimmer, modern-looking slider for region list controls."""
        style = ttk.Style()
        style.configure(
            "RegionLimit.Horizontal.TScale",
            background=Styles.COLOR_SIDEBAR_CARD_ALT,
            troughcolor="#1e3047",
            bordercolor="#1e3047",
            lightcolor=Styles.COLOR_ACCENT,
            darkcolor=Styles.COLOR_ACCENT,
            sliderlength=Styles.scale_size(18),
            sliderthickness=Styles.scale_size(14),
            borderwidth=0,
        )
        style.map(
            "RegionLimit.Horizontal.TScale",
            background=[("disabled", Styles.COLOR_SIDEBAR_CARD_ALT)],
        )

    def _set_section_view_mode(self, mode):
        normalized_mode = "regions" if mode == "regions" else "sections"
        if self.section_view_mode.get() == normalized_mode:
            return
        self.section_view_mode.set(normalized_mode)
        if hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_last_code_view_mode(normalized_mode)
        self._update_section_view_toggle_buttons()
        self._refresh_sections(force_reload=True)
        if self._should_show_project_regions_in_file_list():
            self._show_file_list_view()
            self._schedule_file_list_refresh()

    def _is_regions_view_active(self):
        return self.section_view_mode.get() == "regions"

    def _update_section_view_toggle_buttons(self):
        if hasattr(self, "sections_header_var"):
            self.sections_header_var.set("Regiones" if self._is_regions_view_active() else "Secciones")
        active_mode = "regions" if self._is_regions_view_active() else "sections"
        if hasattr(self, "section_mode_cards"):
            for mode, widgets in self.section_mode_cards.items():
                is_active = mode == active_mode
                body_bg = Styles.COLOR_SIDEBAR_CARD_ALT if is_active else Styles.COLOR_SIDEBAR_CARD_INNER
                tab_bg = Styles.COLOR_ACCENT if is_active else Styles.COLOR_BUTTON_BG
                title_fg = Styles.COLOR_FG_TEXT if is_active else "#c9d5ea"
                cursor = "arrow" if is_active else "hand2"

                widgets["slot"].configure(cursor=cursor)
                widgets["top_tab"].configure(bg=tab_bg, cursor=cursor)
                widgets["body"].configure(
                    bg=body_bg,
                    cursor=cursor
                )
                widgets["title"].configure(bg=body_bg, fg=title_fg, cursor=cursor)

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
            font=(Styles.FONT_FAMILY, 18, "bold")
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
            font=(Styles.FONT_FAMILY, 18, "bold")
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
            font=(Styles.FONT_FAMILY, 18, "bold")
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
        self.bind("<<BackgroundSearchDone>>", self._on_background_search_done)
        
        # Load project files initially
        self._show_file_list_view()

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
        section_dir_size = Styles.scale_size(9 if ultra_compact_height else 10 if compact_height else 11)
        section_entry_size = Styles.scale_size(13 if compact_height else 15)
        tree_section_size = Styles.scale_size(13 if compact_height else 15)
        tree_subsection_size = Styles.scale_size(11 if compact_height else 13)
        prompt_height = max(Styles.scale_size(4 if ultra_compact_height else 5 if compact_height else 8), 3)
        slider_length = Styles.scale_size(130 if compact_width else 165 if narrow_width else 200)
        ai_width = max(Styles.scale_size(16 if compact_width else 18 if narrow_width else 21), 11)
        ext_width = max(Styles.scale_size(11 if compact_width else 13 if narrow_width else 16), 9)
        spacer_height = Styles.scale_size(18 if ultra_compact_height else 28 if compact_height else 42)
        top_prompt_pady = Styles.scale_size(6 if compact_height else 10)

        file_font_size = Styles.scale_size(13 if compact_width else 14 if narrow_width else 15)
        file_heading_size = Styles.scale_size(13 if compact_width else 14 if narrow_width else 15)
        file_row_height = Styles.scale_size(42 if ultra_compact_height else 46 if compact_height else 52)
        ai_title_size = Styles.scale_size(9 if ultra_compact_height else 10 if compact_height else 11)
        path_filter_width = max(20 if compact_width else 24 if narrow_width else 30, 16)
        reload_button_width = Styles.scale_size(42 if compact_width else 46 if narrow_width else 48)

        self.lbl_project_name.configure(font=(Styles.FONT_FAMILY, project_font_size))
        self.lbl_sections_dir.configure(
            font=(Styles.FONT_FAMILY, section_dir_size),
            wraplength=max(self.right_frame.winfo_width() - 30, Styles.scale_size(180))
        )
        self.section_search_entry.configure(font=(Styles.FONT_FAMILY, section_entry_size))
        self.section_tree.tag_configure("section", font=(Styles.FONT_FAMILY, tree_section_size, "bold"))
        self.section_tree.tag_configure("subsection", font=(Styles.FONT_FAMILY, tree_subsection_size))
        self.section_tree_bottom_spacer.configure(height=spacer_height)

        self._configure_file_tree_style(
            row_font_size=file_font_size,
            heading_font_size=file_heading_size,
            row_height=file_row_height
        )
        self._update_file_tree_columns()

        self.cmb_ai.configure(width=ai_width)
        self.path_filter_title.configure(font=(Styles.FONT_FAMILY, ai_title_size, "bold"))
        self.txt_path_filter.configure(font=(Styles.FONT_FAMILY, max(ai_title_size + 2, 11)))
        self.txt_path_filter.configure(width=path_filter_width)
        self.ai_selector_title.configure(font=(Styles.FONT_FAMILY, ai_title_size, "bold"))
        self.ext_title.configure(font=(Styles.FONT_FAMILY, ai_title_size, "bold"))
        self.reload_title.configure(font=(Styles.FONT_FAMILY, ai_title_size, "bold"))
        self.txt_ext.configure(font=(Styles.FONT_FAMILY, max(ai_title_size + 2, 11)))
        self.txt_ext.configure(width=ext_width)
        self.btn_reload_project.configure(width=reload_button_width)
        self.txt_prompt.configure(height=prompt_height)
        self.prompt_frame.pack_configure(pady=top_prompt_pady)
        if hasattr(self, "region_list_limit_slider"):
            self.region_list_limit_slider.configure(length=max(Styles.scale_size(110), slider_length))
        self._update_top_bar_alignment()

    def _update_top_bar_alignment(self):
        """Keeps the top controls spacious without letting them dominate the row."""
        if not hasattr(self, "slider_frame") or not hasattr(self, "top_bar"):
            return

        try:
            self.update_idletasks()
            top_bar_width = max(self.top_bar.winfo_width(), self.winfo_width(), 1)
            max_controls_width = Styles.scale_size(980)
            side_padding = max(Styles.scale_size(10), (top_bar_width - max_controls_width) // 2)
            self.slider_frame.pack_configure(fill="x", expand=True, padx=side_padding)
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

    def _set_return_mode(self, return_files, return_chunks, return_regions, refresh_sections=True):
        """Updates return-mode selectors keeping them mutually exclusive."""
        self.var_return_files.set(bool(return_files))
        self.var_return_chunks.set(bool(return_chunks))
        self.var_return_regions.set(bool(return_regions))
        if hasattr(self, "chk_canvas"):
            self._draw_checkbox()
        if hasattr(self, "chk_chunks_canvas"):
            self._draw_chunks_checkbox()

        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_return_files(return_files)
            self.controller.config_manager.set_return_chunks(return_chunks)
            self.controller.config_manager.set_return_regions(return_regions)

        app_instance = getattr(self.winfo_toplevel(), "app_instance", None)
        if app_instance and hasattr(app_instance, "sync_output_menu_state"):
            app_instance.sync_output_menu_state(
                return_files=return_files,
                return_chunks=return_chunks,
                return_regions=return_regions
            )

        if refresh_sections:
            self._refresh_sections()

    def _toggle_return_files(self, event=None):
        """Acts like a deselectable radio button with square styling."""
        is_selected = self.var_return_files.get()
        self._set_return_mode(return_files=not is_selected, return_chunks=False, return_regions=False)

    def _toggle_return_chunks(self, event=None):
        """Acts like a deselectable radio button with square styling."""
        is_selected = self.var_return_chunks.get()
        self._set_return_mode(return_files=False, return_chunks=not is_selected, return_regions=False)

    def _toggle_return_regions(self, event=None):
        """Acts like a deselectable radio button with square styling."""
        is_selected = self.var_return_regions.get()
        self._set_return_mode(return_files=False, return_chunks=False, return_regions=not is_selected)

    def _toggle_file_headers(self, event=None):
        """Toggles whether codigo.txt exports should include file headers."""
        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_include_file_headers_in_codigo_txt(True)

    def _should_include_file_headers_in_codigo_txt(self):
        return True

    def _get_codigo_txt_append_separator(self):
        return "\n\n"

    def _build_codigo_txt_file_content(self, file_data):
        return f"--- Archivo: {file_data['rel_path']} ---\n{file_data['content']}"

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
            messagebox.showwarning("Aviso", "Selecciona una sección, subsección o segmento primero.")
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
            font=(Styles.FONT_FAMILY, 11),
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
            font=(Styles.FONT_FAMILY, 12)
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




    def _update_file_limit_labels(self, min_limit=None, max_limit=None):
        """Refreshes both file-limit labels."""
        if min_limit is None:
            min_limit = int(float(self.limit_var.get()))
        if max_limit is None:
            max_limit = int(float(self.max_limit_var.get()))
        if hasattr(self, "lbl_limit"):
            self.lbl_limit.config(text=f"Mín. Ficheros: {min_limit}")
        if hasattr(self, "lbl_max_limit"):
            self.lbl_max_limit.config(text=f"Máx. Ficheros: {max_limit}")

    def _persist_file_limits(self, min_limit, max_limit):
        """Stores the current min/max file limits in config."""
        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_file_limit(min_limit)
            self.controller.config_manager.set_max_file_limit(max_limit)

    def _normalize_file_limits(self, preferred=None):
        """Clamps and synchronizes min/max file limits so min never exceeds max."""
        min_slider_max = self._get_limit_slider_max()
        max_slider_max = self._get_max_file_limit_slider_max()

        min_limit = max(1, min(int(float(self.limit_var.get())), min_slider_max))
        max_limit = max(1, min(int(float(self.max_limit_var.get())), max_slider_max))

        if min_limit > max_limit:
            if preferred == "min":
                max_limit = min_limit
                if max_limit > max_slider_max:
                    max_limit = max_slider_max
                    min_limit = min(min_limit, max_limit)
            else:
                min_limit = max_limit
                if min_limit > min_slider_max:
                    min_limit = min_slider_max
                    max_limit = max(max_limit, min_limit)

        self.limit_var.set(min_limit)
        self.max_limit_var.set(max_limit)
        self._update_file_limit_labels(min_limit, max_limit)
        return min_limit, max_limit

    def _on_limit_change(self, val):
        """Handles minimum-file slider movement."""
        min_limit, max_limit = self._normalize_file_limits(preferred="min")
        self._persist_file_limits(min_limit, max_limit)
        self._schedule_file_list_refresh()

    def _on_max_limit_change(self, val):
        """Handles maximum-file slider movement."""
        min_limit, max_limit = self._normalize_file_limits(preferred="max")
        self._persist_file_limits(min_limit, max_limit)
        self._schedule_file_list_refresh()

    def set_file_limits(self, min_limit=None, max_limit=None, preferred="min", refresh=True):
        """Updates file limits from external controls such as the app menu."""
        if min_limit is not None:
            self.limit_var.set(min_limit)
        if max_limit is not None:
            self.max_limit_var.set(max_limit)

        min_limit, max_limit = self._normalize_file_limits(preferred=preferred)
        self._persist_file_limits(min_limit, max_limit)

        if refresh:
            self._schedule_file_list_refresh()

        return min_limit, max_limit

    def _get_limit_slider_max(self):
        """Returns the configured max value for the file-limit slider."""
        if hasattr(self.controller, 'config_manager'):
            return self.controller.config_manager.get_file_limit_slider_max()
        return self.DEFAULT_MAX_FILE_LIMIT

    def _get_max_file_limit_slider_max(self):
        """Returns the configured max value for the max-file slider."""
        if hasattr(self.controller, 'config_manager'):
            return self.controller.config_manager.get_max_file_limit_slider_max()
        return self.DEFAULT_MAX_FILE_LIMIT

    def _apply_limit_slider_ranges(self):
        """Applies the current slider ranges and clamps their values if needed."""
        if hasattr(self, "slider"):
            self.slider.configure(to=self._get_limit_slider_max())
        if hasattr(self, "max_slider"):
            self.max_slider.configure(to=self._get_max_file_limit_slider_max())
        return self._normalize_file_limits()

    def apply_file_limit_slider_settings(self, refresh=True):
        """Reapplies the configured slider ranges and refreshes search results if needed."""
        min_limit, max_limit = self._apply_limit_slider_ranges()
        self._persist_file_limits(min_limit, max_limit)

        if refresh:
            self._schedule_file_list_refresh()

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
        if self._should_show_project_regions_in_file_list():
            self._refresh_project_region_list()
            return

        self._configure_file_tree_headings_for_files()
        self._clear_folder_chip_overlays()
        self._clear_region_name_highlight_overlays()
        self._clear_file_action_overlays()
        self._region_rows_by_iid = {}
        self._last_region_list_items = []

        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if files is None:
            if hasattr(self, 'controller') and hasattr(self.controller, 'get_relevant_files_for_ui'):
                section, subsection = self._get_selected_section_info()
                extension = self.ext_var.get() if hasattr(self, 'ext_var') else ""
                min_files = 0
                max_files = None
                if hasattr(self.controller, 'config_manager'):
                    min_files = self.controller.config_manager.get_file_limit()
                    max_files = self.controller.config_manager.get_max_file_limit()
                files = self.controller.get_relevant_files_for_ui(
                    "",
                    selected_section=section,
                    selected_subsection=subsection,
                    extension=extension,
                    min_files=min_files,
                    max_files=max_files
                )
            elif hasattr(self.controller, 'project_manager'):
                files = self.controller.project_manager.get_files()
            else:
                files = []

        self._last_relevant_files = list(files or [])
        files = self._filter_discarded_files(self._last_relevant_files)
        files = self._filter_files_by_path(files)

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
                    "Ver",
                    f['path'],
                    self._build_file_folder_display(rel_path)
                ),
                tags=(row_tag,)
            )

        self._update_file_tree_columns()
        self._schedule_folder_chip_refresh()


    def _should_show_project_regions_in_file_list(self):
        """Returns True when the left list should render detected project regions."""
        if not self._is_regions_view_active():
            return False
        scope_kind, _section_name, _subsection_name, _leaf_name = self._get_selected_tree_item_info()
        return scope_kind != "region_segment"

    def _schedule_region_list_refresh(self):
        """Debounces project-region list refreshes driven by prompt text or slider changes."""
        if self._region_list_refresh_after:
            try:
                self.after_cancel(self._region_list_refresh_after)
            except Exception:
                pass
        self._region_list_refresh_after = self.after(120, self._refresh_project_region_list)

    def _refresh_project_region_list(self):
        """Renders detected #region blocks in the left list, ranked by prompt similarity."""
        self._region_list_refresh_after = None
        self._configure_file_tree_headings_for_regions()
        self._clear_folder_chip_overlays()
        self._clear_region_name_highlight_overlays()
        self._clear_file_action_overlays()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self._region_rows_by_iid = {}
        self._last_relevant_files = []

        extension = self.ext_var.get() if hasattr(self, "ext_var") else ""
        if hasattr(self.controller, "get_relevant_files_for_ui"):
            file_infos = self.controller.get_relevant_files_for_ui(
                "",
                selected_section=None,
                selected_subsection=None,
                extension=extension,
                min_files=0,
                max_files=None,
            )
        else:
            project_manager = getattr(self.controller, "project_manager", None)
            file_infos = list(project_manager.get_files()) if project_manager else []

        self._last_relevant_files = list(file_infos or [])
        region_items = extract_regions_for_files(file_infos)
        ranked_regions = self._rank_project_regions_for_prompt(region_items)
        auto_total_bytes = None
        if self._is_region_list_auto_enabled():
            visible_regions, auto_total_bytes = self._get_auto_limited_region_list(ranked_regions)
        else:
            visible_regions = ranked_regions[:self._get_region_list_limit()]
        self._last_region_list_items = visible_regions
        self._update_region_list_limit_label(
            listed_count=len(visible_regions),
            total_bytes=auto_total_bytes
        )

        for index, region in enumerate(visible_regions):
            iid = f"REGIONROW:{index}"
            row_tag = "row_even" if index % 2 == 0 else "row_odd"
            rel_path = region.get("file_rel_path") or os.path.basename(region.get("file_path") or "")
            line_span = f"L{region.get('start_line', '?')}-L{region.get('end_line', '?')}"
            display_name = self._build_region_name_display(region)
            self._region_rows_by_iid[iid] = region
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=display_name,
                image=self._get_file_icon(rel_path),
                values=(
                    "",
                    self._format_file_size(len(region.get("content", "") or "")),
                    line_span,
                    "Ver",
                    region.get("file_path") or "",
                    self._build_file_folder_display(rel_path) if rel_path else "raiz",
                ),
                tags=(row_tag,),
            )

        self._update_file_tree_columns()
        self._schedule_folder_chip_refresh()

    def _configure_file_tree_headings_for_files(self):
        if not hasattr(self, "tree"):
            return
        self.tree.heading("#0", text="Nombre")
        self.tree.heading("folder", text="Ruta")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("view", text="Ver")

    def _configure_file_tree_headings_for_regions(self):
        if not hasattr(self, "tree"):
            return
        self.tree.heading("#0", text="Región")
        self.tree.heading("folder", text="Archivo")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("type", text="Líneas")
        self.tree.heading("view", text="Ver")

    def _rank_project_regions_for_prompt(self, regions):
        """Sorts regions by string similarity to the current AI message."""
        query = ""
        if hasattr(self, "txt_prompt"):
            query = self.txt_prompt.get("1.0", "end-1c").strip()
        normalized_query = normalize_region_match_text(query)
        query_tokens = {token for token in tokenize_region_match_text(normalized_query) if token}

        scored_regions = []
        query_keywords = get_region_match_keywords(query)
        for index, region in enumerate(regions or []):
            if not isinstance(region, dict):
                continue
            region_copy = dict(region)
            region_copy["_prompt_highlight_tokens"] = self._find_region_prompt_highlight_tokens(
                query_keywords,
                region_copy.get("header") or region_copy.get("name") or ""
            )
            if not normalized_query:
                scored_regions.append((0.0, index, region_copy))
                continue

            score = self._score_project_region_for_prompt(region_copy, normalized_query, query_tokens, query_keywords)
            if region_copy["_prompt_highlight_tokens"]:
                score = min(1.0, score + min(len(region_copy["_prompt_highlight_tokens"]) * 0.04, 0.16))

            scored_regions.append((score, index, region_copy))

        scored_regions.sort(key=lambda item: (-item[0], item[1]))
        return [region for _score, _index, region in scored_regions]

    def _score_project_region_for_prompt(self, region, normalized_query, query_tokens, query_keywords):
        """Ranks regions with strong preference for the visible region header over internal code."""
        header_text = normalize_region_match_text(region.get("header") or region.get("name") or "")
        file_rel_path = normalize_region_match_text(region.get("file_rel_path") or "")
        content_text = normalize_region_match_text(region.get("content") or "")[:2200]

        header_score = self._score_region_text_against_query(normalized_query, query_tokens, query_keywords, header_text)
        path_score = self._score_region_text_against_query(normalized_query, query_tokens, query_keywords, file_rel_path)
        content_score = self._score_region_text_against_query(normalized_query, query_tokens, query_keywords, content_text)

        score = max(
            header_score,
            min(
                1.0,
                (header_score * 0.78)
                + (path_score * 0.12)
                + (content_score * 0.10),
            ),
        )

        if header_text and normalized_query in header_text:
            score = max(score, min(1.0, header_score + 0.08))

        return min(score, 1.0)

    def _score_region_text_against_query(self, normalized_query, query_tokens, query_keywords, candidate_text):
        if not normalized_query or not candidate_text:
            return 0.0

        candidate_tokens = {token for token in tokenize_region_match_text(candidate_text) if token}
        candidate_keywords = get_region_match_keywords(candidate_text)
        sequence_score = difflib.SequenceMatcher(None, normalized_query, candidate_text).ratio()
        token_overlap = 0.0
        if query_tokens and candidate_tokens:
            token_overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
        keyword_overlap = 0.0
        if query_keywords and candidate_keywords:
            keyword_overlap = len(query_keywords & candidate_keywords) / max(len(query_keywords), 1)

        exact_bonus = 0.28 if normalized_query == candidate_text else 0.0
        contains_bonus = 0.16 if normalized_query in candidate_text or candidate_text in normalized_query else 0.0
        starts_bonus = 0.10 if candidate_text.startswith(normalized_query) or normalized_query.startswith(candidate_text) else 0.0
        subset_bonus = 0.12 if query_tokens and query_tokens.issubset(candidate_tokens) else 0.0
        keyword_bonus = 0.14 if keyword_overlap > 0 else 0.0

        return min(
            1.0,
            max(
                sequence_score,
                (sequence_score * 0.52)
                + (token_overlap * 0.18)
                + (keyword_overlap * 0.16)
                + exact_bonus
                + contains_bonus
                + starts_bonus
                + subset_bonus
                + keyword_bonus
            ),
        )

    def _find_region_prompt_highlight_tokens(self, query_keywords, region_header):
        """Returns normalized header words that also appear in the prompt, excluding stop-words."""
        if not query_keywords:
            return ()

        header_tokens = []
        seen_tokens = set()
        for token in tokenize_region_match_text(region_header, exclude_stop_words=True):
            if token in query_keywords and token not in seen_tokens:
                seen_tokens.add(token)
                header_tokens.append(token)
        return tuple(header_tokens)

    def _get_region_header_highlight_spans(self, header_text, highlight_tokens):
        """Returns raw header word spans that should be painted as prompt matches."""
        raw_header = str(header_text or "")
        token_set = {token for token in (highlight_tokens or ()) if token}
        if not raw_header or not token_set:
            return []

        spans = []
        for match in re.finditer(r"\S+", raw_header):
            normalized_word = normalize_region_match_text(match.group(0))
            if normalized_word and normalized_word in token_set:
                spans.append((match.group(0), match.start(), match.end()))
        return spans

    def _build_region_name_display(self, region):
        """Builds the name column label for a project region row."""
        name = (region.get("header") or region.get("name") or "Región").strip()
        rel_path = region.get("file_rel_path") or os.path.basename(region.get("file_path") or "")
        if rel_path:
            return f"   {name} · {os.path.basename(rel_path)}"
        return f"   {name}"

    def _schedule_file_list_refresh(self, event=None):
        """Schedules a debounced refresh of the file list using scope filters only."""
        if self._should_show_project_regions_in_file_list():
            self._schedule_region_list_refresh()
            return

        if hasattr(self, '_search_timer') and self._search_timer:
            self.after_cancel(self._search_timer)
            
        # Debounce: Wait 300ms after last keypress
        self._search_timer = self.after(300, self._start_background_search)

    def _on_prompt_text_change(self, event=None):
        """Refreshes project-region ranking while keeping normal file search decoupled."""
        if self._should_show_project_regions_in_file_list():
            self._schedule_region_list_refresh()
        return None

    def _on_extension_change(self, *args):
        """Persists the extensions filter and refreshes the file search."""
        if hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_code_extensions_filter(self.ext_var.get())
        self._schedule_file_list_refresh()

    def _on_path_filter_change(self, *args):
        """Applies the local route filter over the current search results or highlights code view."""
        if hasattr(self, '_code_preview_mode') and self._code_preview_mode:
            query = self.path_filter_var.get().strip()
            self._highlight_text_in_segment_code_view(query)
        self.refresh_file_list(self._last_relevant_files)

    def _start_background_search(self):
        """Starts the scoped file refresh in a separate thread."""
        if self._should_show_project_regions_in_file_list():
            self._refresh_project_region_list()
            return

        section, subsection = self._get_selected_section_info()
        
        extension = self.ext_var.get()
        
        min_files = 0
        max_files = None
        if hasattr(self.controller, 'config_manager'):
            min_files = self.controller.config_manager.get_file_limit()
            max_files = self.controller.config_manager.get_max_file_limit()

        # Run search in thread
        threading.Thread(
            target=self._perform_search,
            args=(section, subsection, extension, min_files, max_files),
            daemon=True
        ).start()

    def _perform_search(self, section, subsection=None, extension="Todos", min_files=0, max_files=None):
        """Executes scoped file retrieval logic (Thread Safe)."""
        try:
            relevant_files = self.controller.get_relevant_files_for_ui(
                "",
                selected_section=section,
                selected_subsection=subsection,
                extension=extension,
                min_files=min_files,
                max_files=max_files
            )
            # Safe way to pass data to main thread without corrupting Tkinter's lock on macOS
            self._pending_search_results = relevant_files
            try:
                self.event_generate("<<BackgroundSearchDone>>", when="tail")
            except tk.TclError:
                pass
        except Exception as e:
            print(f"Search error: {e}")

    def _on_background_search_done(self, event=None):
        """Handles the completion of the background search on the main thread."""
        if hasattr(self, '_pending_search_results'):
            files = self._pending_search_results
            self._pending_search_results = None
            self._update_file_list_safe(files)

    def _update_file_list_safe(self, files):
        """Updates UI with search results (Main Thread)."""
        self.refresh_file_list(files)
        self.update_idletasks()

    def _filter_files_by_path(self, files):
        """Applies the local path filter to the file list."""
        filter_text = ""
        if hasattr(self, "path_filter_var"):
            filter_text = self.path_filter_var.get().strip().lower()

        if not filter_text:
            return list(files or [])

        normalized_filter = filter_text.replace("\\", "/")
        filtered_files = []

        for file_data in files or []:
            rel_path = str(file_data.get("rel_path", "") or "")
            abs_path = str(file_data.get("path", "") or "")
            candidate_paths = {
                rel_path.lower(),
                abs_path.lower(),
                rel_path.replace("\\", "/").lower(),
                abs_path.replace("\\", "/").lower(),
            }
            if any(normalized_filter in candidate for candidate in candidate_paths):
                filtered_files.append(file_data)

        return filtered_files

    def _filter_discarded_files(self, files):
        """Removes files discarded by the user until an explicit reload is requested."""
        if not self._discarded_file_paths:
            return list(files or [])
        return [
            file_data for file_data in (files or [])
            if str(file_data.get("path", "") or "") not in self._discarded_file_paths
        ]

    def _get_selected_tree_item_info(self):
        """Returns (kind, section_name, subsection_name_or_None, leaf_name_or_None) from current Treeview selection."""
        if not hasattr(self, 'section_tree'):
            return None, None, None, None
        selected = self.section_tree.selection()
        if not selected:
            return None, None, None, None
        iid = selected[0]
        if iid.startswith("RSEG:"):
            return "region_segment", None, None, iid[5:]
        if iid.startswith("SEG:"):
            rest = iid[4:]
            parts = rest.split("::", 2)
            if len(parts) == 3:
                return "segment", parts[0], parts[1], parts[2]
        if iid.startswith("SS:"):
            rest = iid[3:]
            parts = rest.split("::", 1)
            if len(parts) == 2:
                return "subsection", parts[0], parts[1], None
        elif iid.startswith("S:"):
            return "section", iid[2:], None, None
        return None, None, None, None

    def _get_selected_scope_info(self):
        """Returns (section_name, subsection_name_or_None, leaf_name_or_None) from current Treeview selection."""
        _kind, section_name, subsection_name, leaf_name = self._get_selected_tree_item_info()
        return section_name, subsection_name, leaf_name

    def _get_selected_section_info(self):
        """Returns (section_name, subsection_name_or_None) using the parent subsection when a segment is selected."""
        section_name, subsection_name, _segment_name = self._get_selected_scope_info()
        return section_name, subsection_name

    def _get_selected_segment_info(self):
        """Returns (section_name, subsection_name, segment_name) when a segment is selected."""
        return self._get_selected_scope_info()

    def _build_section_iid(self, section_name, subsection_name=None, segment_name=None):
        """Builds stable tree item ids for sections, subsections and segments."""
        if not section_name:
            return None
        if subsection_name and segment_name:
            return f"SEG:{section_name}::{subsection_name}::{segment_name}"
        if subsection_name:
            return f"SS:{section_name}::{subsection_name}"
        return f"S:{section_name}"

    def _build_region_iid(self, region_name):
        if not region_name:
            return None
        return f"RSEG:{region_name}"

    def _on_section_search_change(self, event=None):
        preferred_iid = None
        selected = self.section_tree.selection() if hasattr(self, "section_tree") else ()
        if selected:
            preferred_iid = selected[0]
        elif self._last_selected_scope_iid:
            preferred_iid = self._last_selected_scope_iid
        elif self._last_selected_section:
            preferred_iid = self._build_section_iid(
                self._last_selected_section,
                self._last_selected_subsection,
                self._last_selected_segment
            )
        self._refresh_sections(preferred_iid=preferred_iid)

    def _on_section_select(self, event=None, force_reload=False):
        """Trigger update when section selection changes."""
        scope_iid = None
        selected = self.section_tree.selection() if hasattr(self, "section_tree") else ()
        if selected:
            scope_iid = selected[0]

        scope_kind, section_name, subsection_name, leaf_name = self._get_selected_tree_item_info()
        segment_name = leaf_name if scope_kind == "segment" else None
        region_name = leaf_name if scope_kind == "region_segment" else None
        self._update_section_action_buttons(section_name, subsection_name, leaf_name)
        
        # Only reload if the selection has actually changed
        if not force_reload and scope_iid == self._last_selected_scope_iid:
            return
            
        self._last_selected_scope_iid = scope_iid
        self._last_selected_scope_kind = scope_kind
        self._last_selected_section = section_name
        self._last_selected_subsection = subsection_name
        if segment_name:
            self._last_selected_segment = segment_name
        if region_name:
            self._last_selected_region = region_name
        
        # Save selection
        if section_name:
            if hasattr(self.controller, 'config_manager'):
                self.controller.config_manager.set_last_code_section(section_name)

        if segment_name:
            self._load_selected_segment_preview(section_name, subsection_name, segment_name)
        elif region_name:
            self._load_selected_region_preview(region_name)
        else:
            self._show_file_list_view()
            self._schedule_file_list_refresh()

    def _update_section_action_buttons(self, section_name=None, subsection_name=None, segment_name=None):
        """Reserved for section actions that depend on current selection."""
        self.refresh_dynamic_paste_controls()

    def refresh_dynamic_paste_controls(self):
        """Refreshes the visibility and text of dynamic-paste controls."""
        if not hasattr(self, "btn_cancel_dynamic_paste_inline"):
            return

        status = {"active": False, "current_number": 0, "total": 0, "current_file": ""}
        if hasattr(self.controller, "get_dynamic_paste_status"):
            status = self.controller.get_dynamic_paste_status()

        if status.get("active"):
            current_number = status.get("current_number", 0)
            total = status.get("total", 0)
            self.btn_cancel_dynamic_paste_inline.configure(
                text=f"Cancelar pegado dinamico ({current_number}/{total})"
            )
            if hasattr(self, "dynamic_paste_status_frame") and not self.dynamic_paste_status_frame.winfo_manager():
                self.dynamic_paste_status_frame.pack(fill="x", padx=8, pady=(0, 6))
            if hasattr(self, "region_list_limit_frame") and self.region_list_limit_frame.winfo_manager():
                self.region_list_limit_frame.pack_forget()
        else:
            if hasattr(self, "dynamic_paste_status_frame") and self.dynamic_paste_status_frame.winfo_manager():
                self.dynamic_paste_status_frame.pack_forget()
            section_name, subsection_name, segment_name = self._get_selected_scope_info()
            self._update_section_action_buttons_without_refresh(
                section_name,
                subsection_name,
                segment_name
            )

    def _update_section_action_buttons_without_refresh(self, section_name=None, subsection_name=None, segment_name=None):
        """Updates section action buttons without re-entering dynamic-paste UI refresh."""
        if not hasattr(self, "region_list_limit_frame"):
            return

        if self._is_regions_view_active():
            if not self.region_list_limit_frame.winfo_manager():
                self.region_list_limit_frame.pack(fill="x", padx=8, pady=(0, Styles.scale_size(34)))
        else:
            if self.region_list_limit_frame.winfo_manager():
                self.region_list_limit_frame.pack_forget()

    def _get_region_list_limit(self):
        """Returns the number of project regions to show in the left list."""
        try:
            value = int(float(self.region_list_limit_var.get()))
        except (TypeError, ValueError, tk.TclError):
            value = self.DEFAULT_REGION_LIST_LIMIT
        value = max(self.MIN_REGION_LIST_LIMIT, min(value, self.MAX_REGION_LIST_LIMIT))
        if hasattr(self, "region_list_limit_var") and self.region_list_limit_var.get() != value:
            self.region_list_limit_var.set(value)
        return value

    def _is_region_list_auto_enabled(self):
        return bool(self.region_list_auto_var.get()) if hasattr(self, "region_list_auto_var") else False

    def _apply_region_list_limit_control_state(self):
        if hasattr(self, "region_list_limit_slider"):
            if isinstance(self.region_list_limit_slider, ttk.Scale):
                if self._is_region_list_auto_enabled():
                    self.region_list_limit_slider.state(["disabled"])
                else:
                    self.region_list_limit_slider.state(["!disabled"])
            else:
                self.region_list_limit_slider.configure(
                    state=(tk.DISABLED if self._is_region_list_auto_enabled() else tk.NORMAL)
                )

    def _update_region_list_limit_label(self, listed_count=None, total_bytes=None):
        if hasattr(self, "lbl_region_list_limit"):
            if self._is_region_list_auto_enabled():
                used_bytes = 0 if total_bytes is None else total_bytes
                text = (
                    f"{self._format_memory_limit_compact(used_bytes)}"
                    f"/{self._format_memory_limit_compact(self.AUTO_REGION_LIST_MAX_BYTES)}"
                )
            else:
                text = f"Regiones listadas: {self._get_region_list_limit()}"
            self.lbl_region_list_limit.configure(text=text)

    def _on_region_list_limit_change(self, _value=None):
        if _value is not None:
            try:
                snapped_value = int(round(float(_value)))
            except (TypeError, ValueError):
                snapped_value = self._get_region_list_limit()
            snapped_value = max(self.MIN_REGION_LIST_LIMIT, min(snapped_value, self.MAX_REGION_LIST_LIMIT))
            if self.region_list_limit_var.get() != snapped_value:
                self.region_list_limit_var.set(snapped_value)
        self._update_region_list_limit_label()
        self._schedule_region_list_limit_save()
        if self._should_show_project_regions_in_file_list():
            self._schedule_region_list_refresh()

    def _on_region_list_auto_toggle(self):
        self._apply_region_list_limit_control_state()
        self._update_region_list_limit_label()
        if hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_region_list_auto_enabled(self._is_region_list_auto_enabled())
        if self._should_show_project_regions_in_file_list():
            self._schedule_region_list_refresh()

    def _schedule_region_list_limit_save(self):
        if self._region_list_limit_save_after:
            try:
                self.after_cancel(self._region_list_limit_save_after)
            except Exception:
                pass
        self._region_list_limit_save_after = self.after(250, self._persist_region_list_limit)

    def _persist_region_list_limit(self):
        self._region_list_limit_save_after = None
        if hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_region_list_limit(self._get_region_list_limit())

    def _get_region_content_size_bytes(self, region):
        content = str((region or {}).get("content") or "")
        return len(content.encode("utf-8"))

    def _format_memory_limit_compact(self, num_bytes):
        """Formats memory counters as compact KB labels (e.g. 40KB)."""
        try:
            value = float(max(num_bytes, 0))
        except Exception:
            value = 0.0
        return f"{int(round(value / 1024.0))}KB"

    def _get_auto_limited_region_list(self, ranked_regions):
        visible_regions = []
        total_bytes = 0
        limit_bytes = self.AUTO_REGION_LIST_MAX_BYTES

        for region in ranked_regions or []:
            region_size = self._get_region_content_size_bytes(region)
            if total_bytes + region_size > limit_bytes:
                break
            visible_regions.append(region)
            total_bytes += region_size

        return visible_regions, total_bytes

    def _load_selected_segment_preview(self, section_name, subsection_name, segment_name):
        """Loads the selected segment code into the left preview panel."""
        segment = self.controller.section_manager.get_segment(section_name, subsection_name, segment_name)
        segment_items = list((segment or {}).get("items", []))
        if not segment_items:
            self._show_segment_code_view(
                "",
                title_text=f"Segmento: {segment_name}",
                file_hint=None,
                preview_mode="segment"
            )
            return

        file_infos = self._get_selected_section_file_infos(section_name, subsection_name)
        code_text, _copied_count = build_segment_full_text_from_items(file_infos, segment_items)

        unique_paths = []
        seen_paths = set()
        for item in segment_items:
            file_path = item.get("file_path")
            if not file_path or file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            unique_paths.append(file_path)

        file_hint = unique_paths[0] if len(unique_paths) == 1 else None
        title_text = f"Segmento: {section_name} > {subsection_name} > {segment_name}"
        self._show_segment_code_view(
            code_text,
            title_text=title_text,
            file_hint=file_hint,
            preview_mode="segment"
        )

    def _load_selected_region_preview(self, region_name):
        """Loads the selected code segment built from regions into the left preview panel."""
        region = self.controller.region_segment_manager.get_region_segment(region_name)
        region_items = list((region or {}).get("items", []))
        if not region_items:
            self._show_segment_code_view(
                "",
                title_text=f"Región: {region_name}",
                file_hint=None,
                preview_mode="region"
            )
            return

        file_infos = list(self.controller.project_manager.get_files())
        code_text, _copied_count = build_segment_full_text_from_items(file_infos, region_items)

        unique_paths = []
        seen_paths = set()
        for item in region_items:
            file_path = item.get("file_path")
            if not file_path or file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            unique_paths.append(file_path)

        file_hint = unique_paths[0] if len(unique_paths) == 1 else None
        title_text = f"Región: {region_name}"
        self._show_segment_code_view(
            code_text,
            title_text=title_text,
            file_hint=file_hint,
            preview_mode="region"
        )

    def _extract_structure_header_text(self, structure_item):
        """Returns the normalized header/signature text for a detected structure."""
        structure_text = (structure_item or {}).get("content", "")
        if not structure_text.strip():
            return ""
        structure_type = structure_item.get("type", "")
        explicit_header = (structure_item.get("header") or "").strip()

        if explicit_header:
            return self._sanitize_structure_header_text(explicit_header, structure_type)

        if self._is_hook_call_structure(structure_text):
            hook_header = self._extract_hook_call_header(structure_text)
            if hook_header:
                return self._sanitize_structure_header_text(hook_header, structure_type)

        detected = detect_code_structure(structure_text)
        if detected and detected.get("header"):
            return self._sanitize_structure_header_text(detected["header"].strip(), structure_type)

        fallback_header = self._extract_structure_header_fallback(
            structure_text,
            structure_type
        )
        if fallback_header:
            return self._sanitize_structure_header_text(fallback_header, structure_type)

        fallback_text = (structure_item.get("display_name") or structure_item.get("name") or "").strip()
        return self._sanitize_structure_header_text(fallback_text, structure_type)

    def _is_hook_call_structure(self, structure_text):
        """Returns True when the structure starts with a React-style hook call."""
        first_line = next(
            (line.strip() for line in (structure_text or "").split("\n") if line.strip()),
            ""
        )
        return bool(re.match(r"^(?:React\.)?(?:useEffect|useLayoutEffect|useMemo|useCallback)\s*\(", first_line))

    def _extract_hook_call_header(self, structure_text):
        """Extracts the opening hook header up to the callback body start."""
        text = (structure_text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        if not text:
            return ""

        header_chars = []
        in_single = False
        in_double = False
        in_backtick = False
        escape = False

        for char in text:
            header_chars.append(char)

            if escape:
                escape = False
                continue

            if char == "\\" and (in_single or in_double or in_backtick):
                escape = True
                continue

            if char == "'" and not in_double and not in_backtick:
                in_single = not in_single
                continue
            if char == '"' and not in_single and not in_backtick:
                in_double = not in_double
                continue
            if char == "`" and not in_single and not in_double:
                in_backtick = not in_backtick
                continue

            if in_single or in_double or in_backtick:
                continue

            if char == "{":
                return "".join(header_chars).strip()

        return text.split("\n", 1)[0].strip()

    def _sanitize_structure_header_text(self, header_text, structure_type):
        """Removes noisy markup attributes from copied structure headers."""
        cleaned = (header_text or "").strip()
        if not cleaned:
            return ""

        if (structure_type or "").strip().lower() == "tag" or cleaned.startswith("<"):
            cleaned = self._remove_markup_attribute(cleaned, "style")
            if self._is_generic_markup_header(cleaned):
                return ""

        return cleaned.strip()

    def _is_generic_markup_header(self, header_text):
        """Returns True when a markup header is too generic to be useful in the clipboard."""
        match = re.match(r"^<\s*([A-Za-z][\w:.-]*)\b(.*?)/?\s*>$", (header_text or "").strip(), re.DOTALL)
        if not match:
            return False

        tag_name = match.group(1)
        attributes_chunk = match.group(2) or ""
        lower_name = tag_name.lower()

        if tag_name[:1].isupper() or "-" in tag_name:
            return False

        if lower_name not in self.GENERIC_MARKUP_TAGS:
            return False

        if "{..." in attributes_chunk:
            return False

        attribute_names = re.findall(r"([:@A-Za-z_][\w:.-]*)\s*(?:=|\b)", attributes_chunk)
        for attr_name in attribute_names:
            normalized = attr_name.lower()
            if normalized in self.DESCRIPTIVE_MARKUP_ATTRIBUTES:
                return False
            if normalized.startswith("data-") or normalized.startswith("aria-"):
                return False

        return True

    def _remove_markup_attribute(self, header_text, attribute_name):
        """Removes one attribute from an opening markup tag, including JSX expression values."""
        text = header_text or ""
        attr_name = (attribute_name or "").strip().lower()
        if not text.startswith("<") or not attr_name:
            return text

        result = []
        idx = 0
        text_length = len(text)

        while idx < text_length:
            char = text[idx]

            if not char.isspace():
                result.append(char)
                idx += 1
                continue

            whitespace_start = idx
            while idx < text_length and text[idx].isspace():
                idx += 1
            whitespace = text[whitespace_start:idx]

            name_start = idx
            while idx < text_length and (text[idx].isalnum() or text[idx] in {"_", ":", "-", "."}):
                idx += 1
            attribute = text[name_start:idx]

            if not attribute:
                result.append(whitespace)
                continue

            if attribute.lower() != attr_name:
                result.append(whitespace)
                result.append(attribute)
                continue

            while idx < text_length and text[idx].isspace():
                idx += 1

            if idx >= text_length or text[idx] != "=":
                continue

            idx += 1
            while idx < text_length and text[idx].isspace():
                idx += 1

            idx = self._consume_markup_attribute_value(text, idx)

        return "".join(result)

    def _consume_markup_attribute_value(self, text, start_idx):
        """Skips a markup attribute value, handling quotes and JSX expressions."""
        idx = start_idx
        text_length = len(text)
        if idx >= text_length:
            return idx

        opener = text[idx]
        if opener in {'"', "'"}:
            quote = opener
            idx += 1
            while idx < text_length:
                if text[idx] == "\\" and idx + 1 < text_length:
                    idx += 2
                    continue
                if text[idx] == quote:
                    return idx + 1
                idx += 1
            return text_length

        if opener == "{":
            return self._consume_jsx_expression(text, idx)

        while idx < text_length and not text[idx].isspace() and text[idx] != ">":
            idx += 1
        return idx

    def _consume_jsx_expression(self, text, start_idx):
        """Skips a JSX expression value such as {expr} or {{ color: 'red' }}."""
        idx = start_idx
        text_length = len(text)
        brace_depth = 0
        in_single = False
        in_double = False
        in_backtick = False
        escape = False

        while idx < text_length:
            char = text[idx]

            if escape:
                escape = False
                idx += 1
                continue

            if char == "\\" and (in_single or in_double or in_backtick):
                escape = True
                idx += 1
                continue

            if char == "'" and not in_double and not in_backtick:
                in_single = not in_single
                idx += 1
                continue

            if char == '"' and not in_single and not in_backtick:
                in_double = not in_double
                idx += 1
                continue

            if char == "`" and not in_single and not in_double:
                in_backtick = not in_backtick
                idx += 1
                continue

            if in_single or in_double or in_backtick:
                idx += 1
                continue

            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth <= 0:
                    return idx + 1

            idx += 1

        return text_length

    def _extract_structure_header_fallback(self, structure_text, structure_type):
        """Extracts a best-effort structure header when the shared detector cannot."""
        normalized = (structure_text or "").replace("\r\n", "\n").replace("\r", "\n")
        if not normalized.strip():
            return ""

        if (structure_type or "").strip().lower() == "tag":
            return self._extract_markup_header_fallback(normalized)

        return self._extract_code_header_fallback(normalized)

    def _extract_markup_header_fallback(self, structure_text):
        """Returns the opening tag for markup blocks, including multiline tags."""
        start_index = structure_text.find("<")
        if start_index == -1:
            return ""

        in_single = False
        in_double = False

        for idx in range(start_index, len(structure_text)):
            char = structure_text[idx]
            if char == '"' and not in_single:
                in_double = not in_double
            elif char == "'" and not in_double:
                in_single = not in_single
            elif char == ">" and not in_single and not in_double:
                return structure_text[start_index:idx + 1].strip()

        return ""

    def _extract_code_header_fallback(self, structure_text):
        """Returns a best-effort signature/header for code blocks."""
        lines = structure_text.split("\n")
        first_content_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
        if first_content_idx is None:
            return ""

        header_lines = []
        paren_depth = 0
        bracket_depth = 0
        in_single = False
        in_double = False
        in_backtick = False
        escape = False

        for idx in range(first_content_idx, len(lines)):
            line = lines[idx].rstrip()
            stripped = line.strip()

            if not stripped:
                if header_lines:
                    header_lines.append("")
                continue

            current_line = []
            for char in line:
                current_line.append(char)

                if escape:
                    escape = False
                    continue

                if char == "\\" and (in_single or in_double or in_backtick):
                    escape = True
                    continue

                if char == "'" and not in_double and not in_backtick:
                    in_single = not in_single
                    continue
                if char == '"' and not in_single and not in_backtick:
                    in_double = not in_double
                    continue
                if char == "`" and not in_single and not in_double:
                    in_backtick = not in_backtick
                    continue

                if in_single or in_double or in_backtick:
                    continue

                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth = max(paren_depth - 1, 0)
                elif char == "[":
                    bracket_depth += 1
                elif char == "]":
                    bracket_depth = max(bracket_depth - 1, 0)
                elif char == "{" and paren_depth == 0 and bracket_depth == 0:
                    current_line_text = "".join(current_line).rstrip()
                    header_lines.append(current_line_text)
                    return "\n".join(line for line in header_lines if line.strip()).strip()

            header_lines.append("".join(current_line).rstrip())

            if paren_depth == 0 and bracket_depth == 0:
                lowered = stripped.lower()
                if stripped.endswith(":"):
                    return "\n".join(line for line in header_lines if line.strip()).strip()
                if lowered in {"do", "then", "in"}:
                    return "\n".join(line for line in header_lines if line.strip()).strip()
                if lowered.endswith(" do") or lowered.endswith(" then") or lowered.endswith(" in"):
                    return "\n".join(line for line in header_lines if line.strip()).strip()

        return "\n".join(line for line in header_lines if line.strip()).strip()

    def _get_selected_section_file_infos(self, section_name, subsection_name=None):
        """Returns cached file payloads for the currently selected section scope."""
        if subsection_name:
            file_paths = self.controller.section_manager.get_files_in_subsection(section_name, subsection_name)
        else:
            file_paths = self.controller.section_manager.get_files_in_section(section_name)

        project_manager = getattr(self.controller, "project_manager", None)
        cached_files = {}
        if project_manager:
            cached_files = {item.get("path"): item for item in project_manager.get_files()}

        file_infos = []
        for file_path in file_paths:
            if file_path in cached_files:
                file_infos.append(cached_files[file_path])
                continue

            if not os.path.isfile(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue

            project_root = getattr(project_manager, "current_project_path", None) if project_manager else None
            if project_root:
                try:
                    rel_path = os.path.relpath(file_path, project_root)
                except ValueError:
                    rel_path = os.path.basename(file_path)
            else:
                rel_path = os.path.basename(file_path)

            file_infos.append({
                "path": file_path,
                "rel_path": rel_path,
                "content": content,
            })

        return file_infos

    def _build_structure_headers_clipboard_text(self, file_infos, structures):
        """Builds the simplified section text grouped by file and nested by structure."""
        ordered_files = [item for item in file_infos if item.get("path")]
        if not ordered_files:
            return "", 0

        structures_by_path = {}
        for item in structures or []:
            file_with_line = item.get("path", "")
            file_path = file_with_line.split(":", 1)[0] if ":" in file_with_line else file_with_line
            structures_by_path.setdefault(file_path, []).append(item)

        file_blocks = []
        copied_count = 0

        for file_info in ordered_files:
            file_path = file_info.get("path")
            file_rel_path = file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo"
            simplified_body, body_count = self._build_simplified_file_structure_text(
                file_info,
                structures_by_path.get(file_path, [])
            )
            if not simplified_body.strip():
                continue

            file_blocks.append(f"--- Archivo: {file_rel_path} ---\n{simplified_body}")
            copied_count += body_count

        if not file_blocks:
            return "", 0

        return "\n\n\n".join(file_blocks), copied_count

    def _build_structure_selection_prompt(self, functionality_text, structure_headers_text):
        """Builds a prompt asking the AI to return only the relevant structure headers."""
        clean_functionality = (functionality_text or "").strip()
        clean_headers = (structure_headers_text or "").strip()
        if not clean_functionality or not clean_headers:
            return ""

        return (
            "Petición del Usuario:\n"
            "Devuelve una lista simple y sin información extra de las estructuras de código del contexto que estén relacionadas con esta funcionalidad: "
            f"{clean_functionality}\n\n"
            "Formato obligatorio de salida:\n"
            "- Devuelve únicamente las cabeceras exactas de las estructuras relevantes.\n"
            "- Una estructura por línea.\n"
            "- Sin explicaciones.\n"
            "- Sin numeración.\n"
            "- Sin Markdown.\n"
            "- Sin rutas de archivo.\n"
            "- Si no aplica ninguna, devuelve una respuesta vacía.\n\n"
            "Estructuras de código disponibles:\n"
            f"{clean_headers}"
        )

    def _build_simplified_file_structure_text(self, file_info, structures):
        """Builds a simplified parent/child header view for one file."""
        normalized_items = []
        seen_keys = set()

        for item in structures:
            header_text = self._extract_structure_header_text(item)
            if not header_text:
                continue

            start_line = max(int(item.get("start_line", 1) or 1), 1)
            end_line = max(start_line, start_line + max(int(item.get("line_count", 1) or 1) - 1, 0))
            key = (start_line, end_line, item.get("type", ""), header_text)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            normalized_items.append({
                "start_line": start_line,
                "end_line": end_line,
                "type": item.get("type", ""),
                "name": item.get("name", ""),
                "header": header_text,
                "children": [],
            })

        if not normalized_items:
            return "", 0

        normalized_items.sort(key=lambda item: (item["start_line"], -item["end_line"], item["name"]))

        roots = []
        stack = []
        for node in normalized_items:
            while stack and not self._structure_contains(stack[-1], node):
                stack.pop()

            if stack:
                stack[-1]["children"].append(node)
            else:
                roots.append(node)

            stack.append(node)

        rendered_blocks = []
        for node in roots:
            rendered_blocks.append("\n".join(self._render_structure_tree_lines(node, depth=0)))

        return "\n\n".join(rendered_blocks), len(normalized_items)

    def _structure_contains(self, parent_node, child_node):
        """Returns True when one structure fully contains another within the same file."""
        if not parent_node or not child_node:
            return False
        if parent_node["start_line"] > child_node["start_line"]:
            return False
        if parent_node["end_line"] < child_node["end_line"]:
            return False
        if parent_node["start_line"] == child_node["start_line"] and parent_node["end_line"] == child_node["end_line"]:
            return False
        return True

    def _render_structure_tree_lines(self, node, depth=0):
        """Renders one simplified structure tree as text lines."""
        rendered = [self._indent_structure_header(node.get("header", ""), depth)]
        for child in node.get("children", []):
            rendered.extend(self._render_structure_tree_lines(child, depth + 1))
        return rendered

    def _indent_structure_header(self, header_text, depth):
        """Normalizes and indents multiline headers for the simplified output."""
        normalized = textwrap.dedent((header_text or "").strip("\n"))
        lines = normalized.split("\n")
        base_indent = "  " * max(depth, 0)
        indented_lines = []

        for idx, line in enumerate(lines):
            if not line.strip():
                indented_lines.append("")
                continue
            if idx == 0:
                indented_lines.append(f"{base_indent}{line.lstrip()}")
            else:
                indented_lines.append(f"{base_indent}{line}")

        return "\n".join(indented_lines).rstrip()

    def _on_copy_structure_headers(self):
        """Copies an AI-ready prompt plus the current structure headers grouped by file."""
        section_name, subsection_name = self._get_selected_section_info()
        if not section_name:
            messagebox.showwarning("Aviso", "Selecciona una sección, subsección o segmento primero.")
            return

        functionality_text = simpledialog.askstring(
            "Copiar estructuras",
            "¿Qué funcionalidad quieres listar por estructuras de código?",
            parent=self.winfo_toplevel()
        )
        if not functionality_text:
            return
        functionality_text = functionality_text.strip()
        if not functionality_text:
            messagebox.showwarning(
                "Aviso",
                "Debes indicar una funcionalidad para construir el prompt."
            )
            return

        file_infos = self._get_selected_section_file_infos(section_name, subsection_name)
        if not file_infos:
            messagebox.showinfo(
                "Copiar estructuras",
                "No hay ficheros disponibles en la selección actual."
            )
            return

        try:
            file_paths = [item["path"] for item in file_infos if item.get("path")]
            structures = self.controller.project_manager.extract_functions(file_paths=file_paths)
        except Exception as e:
            print(f"Error building structure headers: {e}")
            messagebox.showerror("Error", f"No se pudieron recopilar las estructuras:\n{e}")
            return

        if not structures:
            messagebox.showinfo(
                "Copiar estructuras",
                "No se encontraron estructuras compatibles en la selección actual."
            )
            return

        structure_headers_text, copied_count = self._build_structure_headers_clipboard_text(file_infos, structures)
        if not structure_headers_text.strip():
            messagebox.showinfo(
                "Copiar estructuras",
                "No se pudieron extraer cabeceras válidas en la selección actual."
            )
            return

        clipboard_text = self._build_structure_selection_prompt(functionality_text, structure_headers_text)
        if not clipboard_text.strip():
            messagebox.showinfo(
                "Copiar estructuras",
                "No se pudo construir el prompt de estructuras."
            )
            return

        copied = False
        if hasattr(self.controller, "copy_to_clipboard"):
            copied = self.controller.copy_to_clipboard(clipboard_text)

        if not copied:
            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_text)
                copied = True
            except Exception as e:
                print(f"Error copying structure headers to clipboard: {e}")

        if not copied:
            messagebox.showerror("Error", "No se pudo copiar el contenido al portapapeles.")
            return

        scope_label = section_name
        if subsection_name:
            scope_label = f"{section_name} > {subsection_name}"

        messagebox.showinfo(
            "Copiar estructuras",
            f"Se copió un prompt con {copied_count} cabeceras agrupadas por fichero de {scope_label}."
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
            messagebox.showwarning("Aviso", "Selecciona una sección, subsección o segmento primero.")
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
        element = self.section_tree.identify("element", event.x, event.y)
        if not iid or self._is_empty_deselect_iid(iid):
            # Clicked on empty space - deselect
            selected = self.section_tree.selection()
            if selected:
                self.section_tree.selection_remove(*selected)
            self._on_section_select(force_reload=True)
            if self._is_empty_deselect_iid(iid):
                return "break"

        if (
            iid
            and element == "Treeitem.image"
            and not self._is_empty_deselect_iid(iid)
            and self.section_tree.get_children(iid)
        ):
            self.section_tree.item(iid, open=not bool(self.section_tree.item(iid, "open")))
            self.after_idle(self._refresh_section_tree_icons)
            return "break"

    def _on_section_spacer_click(self, event=None):
        """Deselect sections when clicking the fixed spacer below the tree."""
        selected = self.section_tree.selection()
        if selected:
            self.section_tree.selection_remove(*selected)
        self._on_section_select(force_reload=True)
        return "break"

    def _is_empty_deselect_iid(self, iid):
        """Returns whether the iid belongs to a dummy row used for deselection."""
        return bool(iid) and iid.startswith("EMPTY_DESELECT")

    def _on_section_tree_open(self, event=None):
        """Refreshes the custom icon when a tree item expands."""
        self.after_idle(self._refresh_section_tree_icons)

    def _on_section_tree_close(self, event=None):
        """Refreshes the custom icon when a tree item collapses."""
        self.after_idle(self._refresh_section_tree_icons)

    def _refresh_section_tree_icons(self):
        """Syncs the stylized arrow icon for every visible row in the sections tree."""
        if not hasattr(self, "section_tree"):
            return

        for item_id in self.section_tree.get_children(""):
            self._refresh_section_tree_icons_recursive(item_id)

    def _refresh_section_tree_icons_recursive(self, item_id):
        """Recursively updates the icon assigned to an item and its descendants."""
        if not item_id or not self.section_tree.exists(item_id):
            return

        self._update_section_tree_item_icon(item_id)
        for child_id in self.section_tree.get_children(item_id):
            self._refresh_section_tree_icons_recursive(child_id)

    def _update_section_tree_item_icon(self, item_id):
        """Assigns the correct icon based on whether the item can expand and its state."""
        if not item_id or not self.section_tree.exists(item_id):
            return

        if self._is_empty_deselect_iid(item_id):
            self.section_tree.item(item_id, image="")
            return

        children = self.section_tree.get_children(item_id)
        if children:
            is_open = bool(self.section_tree.item(item_id, "open"))
            icon_key = "expanded" if is_open else "collapsed"
            self.section_tree.item(item_id, image=self.section_tree_icons[icon_key])
            return

        parent_id = self.section_tree.parent(item_id)
        if parent_id:
            self.section_tree.item(item_id, image=self.section_tree_icons["spacer"])
        else:
            self.section_tree.item(item_id, image="")

    def _on_copy_prompt(self, event=None):
        # If triggered by event, prevent default behavior (newline)
        if event:
            pass # Use "break" if needed, but Text widget default binding might be separate. 
                 # Usually return "break" prevents further processing.
        
        text = self.txt_prompt.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Aviso", "Escribe un mensaje primero.")
            return

        # Check selected scope
        scope_kind, section, subsection, leaf_name = self._get_selected_tree_item_info()
        
        return_files = self.var_return_files.get()
        return_chunks = self.var_return_chunks.get()
        return_regions = self.var_return_regions.get()

        include_project_tree = False
        if hasattr(self.controller, 'config_manager'):
            include_project_tree = self.controller.config_manager.get_include_project_tree()

        min_files = 10
        if hasattr(self.controller, 'config_manager'):
            min_files = self.controller.config_manager.get_file_limit()

        if scope_kind in {"segment", "region_segment"} and leaf_name:
            if scope_kind == "segment":
                selected_entity = self.controller.section_manager.get_segment(section, subsection, leaf_name)
                segment_code = (self._segment_code_preview_text or "").strip()
            else:
                selected_entity = self.controller.region_segment_manager.get_region_segment(leaf_name)
                segment_code, _copied_count = build_segment_full_text_from_items(
                    list(self.controller.project_manager.get_files()),
                    list((selected_entity or {}).get("items", [])),
                    strip_region_markers=True,
                )
                segment_code = segment_code.strip()

            if not segment_code:
                messagebox.showwarning("Aviso", "La selección actual no tiene código visible para copiar.")
                return

            segment_items = list((selected_entity or {}).get("items", []))
            segment_file_paths = []
            seen_segment_paths = set()
            for item in segment_items:
                file_path = item.get("file_rel_path") or item.get("file_path")
                if not file_path or file_path in seen_segment_paths:
                    continue
                seen_segment_paths.add(file_path)
                segment_file_paths.append(file_path)

            files_instruction = ""
            if segment_file_paths:
                files_instruction = (
                    "Ficheros presentes en este segmento:\n"
                    + "\n".join(f"- {path}" for path in segment_file_paths)
                    + "\n\n"
                )

            clipboard_content = (
                f"Petición del Usuario:\n{text}\n\n"
                "Formato: responde en Markdown. Devuelve exclusivamente el código o los fragmentos de código modificados, sin explicaciones ni código no afectado. Cada bloque de código debe empezar con un comentario dentro del propio bloque con este texto exacto: Archivo: (ruta de archivo), usando el tipo de comentario correcto según el lenguaje. Añade también un comentario con el texto exacto [MODIFICACIÓN] en cada punto donde se haya aplicado un cambio, usando el tipo de comentario correcto según el lenguaje.\n\n"
                f"{files_instruction}"
                f"Código de Contexto:\n{segment_code}"
            )

            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_content)

                documents_path = os.path.join(os.path.expanduser("~"), "Documents")
                export_path = os.path.join(documents_path, "codigo.txt")
                os.makedirs(documents_path, exist_ok=True)
                with open(export_path, "w", encoding="utf-8") as f:
                    f.write(clipboard_content)

                selected_ai = self.cmb_ai.get()
                if selected_ai == self.AUTO_AI_OPTION:
                    selected_ai = self._get_auto_ai()

                if selected_ai != self.AGENT_AI_OPTION:
                    self._ai_usage_history.append(selected_ai)
                    if selected_ai in self.AI_URLS:
                        webbrowser.open_new_tab(self.AI_URLS[selected_ai])

            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el fichero:\n{e}")
            return

        if self._should_show_project_regions_in_file_list():
            selected_regions = self._get_regions_for_prompt()
            if not selected_regions:
                messagebox.showwarning("Aviso", "No hay regiones visibles o seleccionadas para procesar.")
                return

            clipboard_content = self._build_project_regions_prompt(
                text,
                selected_regions,
                return_files,
                return_chunks,
                return_regions
            )
            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_content)

                documents_path = os.path.join(os.path.expanduser("~"), "Documents")
                export_path = os.path.join(documents_path, "codigo.txt")
                os.makedirs(documents_path, exist_ok=True)
                with open(export_path, "w", encoding="utf-8") as f:
                    f.write(clipboard_content)

                selected_ai = self.cmb_ai.get()
                if selected_ai == self.AUTO_AI_OPTION:
                    selected_ai = self._get_auto_ai()
                if selected_ai != self.AGENT_AI_OPTION:
                    self._ai_usage_history.append(selected_ai)
                    if selected_ai in self.AI_URLS:
                        webbrowser.open_new_tab(self.AI_URLS[selected_ai])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el fichero:\n{e}")
            return

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
                return_regions=return_regions,
                include_project_tree=include_project_tree
            )

            self.clipboard_clear()
            self.clipboard_append(clipboard_content)
            print(f"Agente: Prompt copiado con {len(selected_files_data)} ficheros priorizados")
        else:
            clipboard_content = text
            clipboard_content += f"\n\n{self.controller.get_code_output_prompt(return_files=return_files, return_chunks=return_chunks, return_regions=return_regions)}"

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
                    return_regions=return_regions,
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

    def _get_regions_for_prompt(self):
        """Returns selected detected regions or, if none selected, all visible region rows."""
        items_to_process = self.tree.selection() or self.tree.get_children()
        regions = []
        for item_id in items_to_process:
            region = self._get_region_row_item(item_id)
            if region:
                regions.append(region)
        return regions

    def _build_project_regions_prompt(self, user_text, regions, return_files=False, return_chunks=False, return_regions=False):
        """Builds a prompt using detected project regions as the code context."""
        blocks = []
        for region in regions or []:
            rel_path = region.get("file_rel_path") or os.path.basename(region.get("file_path") or "archivo")
            name = region.get("header") or region.get("name") or "Región"
            start_line = region.get("start_line", "?")
            end_line = region.get("end_line", "?")
            region_content = (region.get("content", "") or "").rstrip()
            if not return_regions:
                region_content = strip_region_markers_from_text(region_content).rstrip()
            blocks.append(
                f"--- Región: {name} | Archivo: {rel_path} | Líneas: {start_line}-{end_line} ---\n"
                f"{region_content}"
            )

        return (
            f"Petición del Usuario:\n{user_text}\n\n"
            "Código de Contexto (regiones detectadas):\n"
            + "\n\n".join(blocks)
            + f"\n\n{self.controller.get_code_output_prompt(return_files=return_files, return_chunks=return_chunks, return_regions=return_regions)}"
        )

    def _on_start_dynamic_paste(self):
        """Starts the sequential clipboard flow for the current section/subsection files."""
        section_name, subsection_name, segment_name = self._get_selected_scope_info()
        if not section_name:
            messagebox.showwarning("Pegado dinamico", "Selecciona una seccion o subseccion primero.")
            return
        if segment_name:
            messagebox.showwarning(
                "Pegado dinamico",
                "El pegado dinamico funciona a nivel de seccion o subseccion, no de segmento."
            )
            return

        user_text = self.txt_prompt.get("1.0", "end-1c").strip() if hasattr(self, "txt_prompt") else ""
        if not user_text:
            messagebox.showwarning(
                "Pegado dinamico",
                "Escribe primero el mensaje para la IA antes de iniciar el pegado dinamico."
            )
            return

        files_data = self._get_files_for_prompt()
        if not files_data:
            messagebox.showwarning(
                "Pegado dinamico",
                "No hay ficheros visibles o seleccionados para iniciar el pegado dinamico."
            )
            return

        if not hasattr(self.controller, "start_dynamic_paste"):
            messagebox.showerror("Pegado dinamico", "La funcionalidad no esta disponible.")
            return

        success, message = self.controller.start_dynamic_paste(files_data, user_text)
        if not success:
            messagebox.showerror("Pegado dinamico", message)
            return

        scope_label = section_name
        if subsection_name:
            scope_label = f"{section_name} > {subsection_name}"

        self.refresh_dynamic_paste_controls()
        messagebox.showinfo(
            "Pegado dinamico",
            f"{message}\n\nSe ha copiado el primer fichero de la lista para la seccion {scope_label}."
        )

    def _on_cancel_dynamic_paste(self):
        """Cancels the active sequential clipboard flow."""
        if not hasattr(self.controller, "cancel_dynamic_paste"):
            return

        was_active = self.controller.cancel_dynamic_paste()
        self.refresh_dynamic_paste_controls()
        if was_active:
            messagebox.showinfo("Pegado dinamico", "El pegado dinamico ha sido cancelado.")

    def _build_agent_clipboard_prompt(
        self,
        text,
        selected_files,
        selected_section=None,
        selected_subsection=None,
        return_files=False,
        return_chunks=False,
        return_regions=False,
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
            self.controller.get_code_output_prompt(
                return_files=return_files,
                return_chunks=return_chunks,
                return_regions=return_regions
            )
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
            
            if not iid or self._is_empty_deselect_iid(iid):
                if self._is_regions_view_active():
                    menu.add_command(label="Nueva Región", command=self._on_add_region)
                    menu.add_command(label="Crear inteligente", command=self._on_add_smart_region)
                else:
                    menu.add_command(label="Nueva Sección", command=self._on_add_section)
            else:
                # Select the item
                self.section_tree.selection_set(iid)
                self._on_section_select()
                
                if iid.startswith("S:"):
                    # Parent section context menu
                    menu.add_command(label="Ir a archivo", command=self._on_go_to_file_from_section_tree)
                    menu.add_separator()
                    menu.add_command(label="Nueva Sección", command=self._on_add_section)
                    menu.add_command(label="Nueva Subsección", command=self._on_add_subsection)
                    menu.add_command(label="Agregar ficheros", command=self._on_add_files_to_selected_section)
                    menu.add_separator()
                    menu.add_command(label="Copiar estructuras", command=self._on_copy_structure_headers)
                    menu.add_command(label="PD", command=self._on_start_dynamic_paste)
                    menu.add_command(label="Tamaño estructuras", command=self._on_show_structure_sizes)
                    menu.add_separator()
                    menu.add_command(label="Generar Prompt Docs", command=self._on_generate_docs)
                    menu.add_separator()
                    menu.add_command(label="Editar Sección", command=self._on_edit_section)
                    menu.add_command(label="Eliminar Sección", command=self._on_delete_section)
                elif iid.startswith("SS:"):
                    # Subsection context menu
                    menu.add_command(label="Ir a archivo", command=self._on_go_to_file_from_section_tree)
                    menu.add_separator()
                    menu.add_command(label="Nuevo Segmento", command=self._on_add_segment)
                    menu.add_separator()
                    menu.add_command(label="Agregar ficheros", command=self._on_add_files_to_selected_section)
                    menu.add_separator()
                    menu.add_command(label="Copiar estructuras", command=self._on_copy_structure_headers)
                    menu.add_command(label="PD", command=self._on_start_dynamic_paste)
                    menu.add_command(label="Tamaño estructuras", command=self._on_show_structure_sizes)
                    menu.add_separator()
                    menu.add_command(label="Editar Subsección", command=self._on_edit_subsection)
                    menu.add_command(label="Eliminar Subsección", command=self._on_delete_subsection)
                    menu.add_separator()
                    menu.add_command(label="Generar Prompt Docs", command=self._on_generate_docs)
                elif iid.startswith("SEG:"):
                    menu.add_command(label="Ir a archivo", command=self._on_go_to_file_from_section_tree)
                    menu.add_separator()
                    menu.add_command(label="Copiar Segmento", command=self._on_copy_segment)
                    menu.add_separator()
                    menu.add_command(label="Editar Segmento", command=self._on_edit_segment)
                    menu.add_command(label="Eliminar Segmento", command=self._on_delete_segment)
                elif iid.startswith("RSEG:"):
                    menu.add_command(label="Ir a archivo", command=self._on_go_to_file_from_section_tree)
                    menu.add_separator()
                    menu.add_command(label="Copiar Región", command=self._on_copy_region)
                    menu.add_separator()
                    menu.add_command(label="Crear inteligente", command=self._on_add_smart_region)
                    menu.add_separator()
                    menu.add_command(label="Editar Región", command=self._on_edit_region)
                    menu.add_command(label="Eliminar Región", command=self._on_delete_region)
            
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

    def _on_add_segment(self):
        """Opens popup to create a segment inside the selected subsection."""
        section_name, sub_name, segment_name = self._get_selected_scope_info()
        if not section_name or not sub_name:
            messagebox.showwarning("Aviso", "Selecciona una subsección padre primero.")
            return

        from src.ui.popups.segment_creation_popup import SegmentCreationPopup
        try:
            popup = SegmentCreationPopup(self, self.controller, section_name, sub_name)
            self.wait_window(popup)
            if popup.saved_segment_name:
                preferred_iid = self._build_section_iid(section_name, sub_name, popup.saved_segment_name)
                self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)
        except Exception as e:
            print(f"Error opening segment popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_edit_segment(self):
        """Opens popup to edit the selected segment."""
        section_name, sub_name, segment_name = self._get_selected_scope_info()
        if not section_name or not sub_name or not segment_name:
            messagebox.showwarning("Aviso", "Selecciona un segmento para editar.")
            return

        segment = self.controller.section_manager.get_segment(section_name, sub_name, segment_name)
        initial_items = segment.get("items", []) if segment else []

        from src.ui.popups.segment_creation_popup import SegmentCreationPopup
        try:
            popup = SegmentCreationPopup(
                self,
                self.controller,
                section_name,
                sub_name,
                segment_name=segment_name,
                initial_items=initial_items
            )
            self.wait_window(popup)
            if popup.saved_segment_name:
                preferred_iid = self._build_section_iid(section_name, sub_name, popup.saved_segment_name)
                self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)
        except Exception as e:
            print(f"Error opening segment edit popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_segment(self):
        """Deletes the selected segment."""
        section_name, sub_name, segment_name = self._get_selected_scope_info()
        if not section_name or not sub_name or not segment_name:
            return

        if not messagebox.askyesno("Eliminar Segmento", f"¿Quieres eliminar el segmento '{segment_name}'?"):
            return

        self.controller.section_manager.delete_segment(section_name, sub_name, segment_name)
        self._refresh_sections(preferred_iid=self._build_section_iid(section_name, sub_name), force_reload=True)

    def _on_copy_segment(self):
        """Copies the code associated with the selected segment."""
        section_name, sub_name, segment_name = self._get_selected_scope_info()
        if not section_name or not sub_name or not segment_name:
            messagebox.showwarning("Aviso", "Selecciona un segmento para copiar.")
            return

        segment = self.controller.section_manager.get_segment(section_name, sub_name, segment_name)
        segment_items = list((segment or {}).get("items", []))
        if not segment_items:
            messagebox.showinfo("Copiar Segmento", "El segmento no tiene estructuras guardadas.")
            return

        file_infos = self._get_selected_section_file_infos(section_name, sub_name)
        if not file_infos:
            messagebox.showinfo("Copiar Segmento", "No hay ficheros disponibles en la subsección del segmento.")
            return

        clipboard_text = ""
        copied_count = 0

        selected_keys = [item.get("key") for item in segment_items if item.get("key")]
        if selected_keys:
            try:
                file_paths = [item["path"] for item in file_infos if item.get("path")]
                structures = self.controller.project_manager.extract_functions(file_paths=file_paths)
                clipboard_text, copied_count = build_segment_full_text(file_infos, structures, selected_keys)
            except Exception as e:
                print(f"Error building segment clipboard text: {e}")

        if not clipboard_text.strip():
            clipboard_text, copied_count = build_segment_full_text_from_items(file_infos, segment_items)

        if not clipboard_text.strip():
            messagebox.showinfo("Copiar Segmento", "No se pudo construir el contenido del segmento.")
            return

        copied = False
        if hasattr(self.controller, "copy_to_clipboard"):
            copied = self.controller.copy_to_clipboard(clipboard_text)

        if not copied:
            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_text)
                copied = True
            except Exception as e:
                print(f"Error copying segment to clipboard: {e}")

        if not copied:
            messagebox.showerror("Error", "No se pudo copiar el contenido del segmento al portapapeles.")
            return

        messagebox.showinfo(
            "Copiar Segmento",
            f"Se copiaron {copied_count} estructuras completas del segmento '{segment_name}'."
        )

    def _on_add_region(self):
        """Opens popup to create a saved code segment from project-wide regions."""
        if not getattr(self.controller.project_manager, "get_files", None) or not self.controller.project_manager.get_files():
            messagebox.showwarning("Aviso", "Carga primero un proyecto con código para crear regiones.")
            return
        from src.ui.popups.region_creation_popup import RegionCreationPopup
        try:
            popup = RegionCreationPopup(self, self.controller)
            self.wait_window(popup)
            if popup.saved_region_name:
                preferred_iid = self._build_region_iid(popup.saved_region_name)
                self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)
        except Exception as e:
            print(f"Error opening region popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_add_smart_region(self):
        """Opens popup to create a saved region segment using free-form header matching."""
        if not getattr(self.controller.project_manager, "get_files", None) or not self.controller.project_manager.get_files():
            messagebox.showwarning("Aviso", "Carga primero un proyecto con código para crear regiones.")
            return
        from src.ui.popups.smart_region_creation_popup import SmartRegionCreationPopup
        try:
            popup = SmartRegionCreationPopup(self, self.controller)
            self.wait_window(popup)
            if popup.saved_region_name:
                preferred_iid = self._build_region_iid(popup.saved_region_name)
                self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)
        except Exception as e:
            print(f"Error opening smart region popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup inteligente: {e}")

    def _on_edit_region(self):
        """Opens popup to edit the selected saved code segment built from regions."""
        scope_kind, _section_name, _sub_name, region_name = self._get_selected_tree_item_info()
        if scope_kind != "region_segment" or not region_name:
            messagebox.showwarning("Aviso", "Selecciona una región para editar.")
            return

        region = self.controller.region_segment_manager.get_region_segment(region_name)
        initial_items = region.get("items", []) if region else []

        from src.ui.popups.region_creation_popup import RegionCreationPopup
        try:
            popup = RegionCreationPopup(
                self,
                self.controller,
                region_name=region_name,
                initial_items=initial_items
            )
            self.wait_window(popup)
            if popup.saved_region_name:
                preferred_iid = self._build_region_iid(popup.saved_region_name)
                self._refresh_sections(preferred_iid=preferred_iid, force_reload=True)
        except Exception as e:
            print(f"Error opening region edit popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_region(self):
        """Deletes the selected saved code segment built from regions."""
        scope_kind, _section_name, _sub_name, region_name = self._get_selected_tree_item_info()
        if scope_kind != "region_segment" or not region_name:
            return

        if not messagebox.askyesno("Eliminar Región", f"¿Quieres eliminar la región '{region_name}'?"):
            return

        self.controller.region_segment_manager.delete_region_segment(region_name)
        self._refresh_sections(force_reload=True)

    def _on_copy_region(self):
        """Copies the code associated with the selected saved code segment built from regions."""
        scope_kind, _section_name, _sub_name, region_name = self._get_selected_tree_item_info()
        if scope_kind != "region_segment" or not region_name:
            messagebox.showwarning("Aviso", "Selecciona una región para copiar.")
            return

        region = self.controller.region_segment_manager.get_region_segment(region_name)
        region_items = list((region or {}).get("items", []))
        if not region_items:
            messagebox.showinfo("Copiar Región", "La región no tiene bloques guardados.")
            return

        file_infos = list(self.controller.project_manager.get_files())
        if not file_infos:
            messagebox.showinfo("Copiar Región", "No hay ficheros disponibles en el proyecto.")
            return

        clipboard_text, copied_count = build_segment_full_text_from_items(
            file_infos,
            region_items,
            strip_region_markers=True,
        )
        if not clipboard_text.strip():
            messagebox.showinfo("Copiar Región", "No se pudo construir el contenido de la región.")
            return

        copied = False
        if hasattr(self.controller, "copy_to_clipboard"):
            copied = self.controller.copy_to_clipboard(clipboard_text)

        if not copied:
            try:
                self.clipboard_clear()
                self.clipboard_append(clipboard_text)
                copied = True
            except Exception as e:
                print(f"Error copying region to clipboard: {e}")

        if not copied:
            messagebox.showerror("Error", "No se pudo copiar el contenido de la región al portapapeles.")
            return

        messagebox.showinfo(
            "Copiar Región",
            f"Se copió el contenido de {copied_count} regiones de '{region_name}'."
        )

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
        query = self._get_section_search_query()

        if self._is_regions_view_active():
            region_names = self.controller.region_segment_manager.get_region_segments()
            visible_regions = [name for name in region_names if not query or query in name.lower()]

            for region_name in visible_regions:
                region_iid = self._build_region_iid(region_name)
                region_size = self.controller.region_segment_manager.get_region_segment_total_code_size(region_name)
                self.section_tree.insert(
                    "",
                    "end",
                    iid=region_iid,
                    text=self._format_section_tree_label(region_name, region_size),
                    tags=("segment", self._get_section_size_tag(region_size))
                )
                self._visible_section_ids.append(region_iid)

            self._insert_section_tree_deselect_spacers()
            self._refresh_section_tree_icons()

            selection_candidates = []
            if preferred_iid:
                selection_candidates.append(preferred_iid)
            if self._last_selected_scope_iid:
                selection_candidates.append(self._last_selected_scope_iid)

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
                self._on_section_select(force_reload=force_reload)
            else:
                self._on_section_select(force_reload=True)
            return

        sections = self.controller.section_manager.get_sections()
        for s in sections:
            subsections = self.controller.section_manager.get_subsections(s)
            section_matches = query in s.lower() if query else False
            visible_subsections = []

            for sub in subsections:
                child_names = self.controller.section_manager.get_segments(s, sub)
                subsection_matches = query in sub.lower() if query else False
                matching_children = [name for name in child_names if query in name.lower()] if query else list(child_names)

                if query:
                    if section_matches:
                        visible_children = list(child_names)
                    elif subsection_matches:
                        visible_children = list(child_names)
                    elif matching_children:
                        visible_children = matching_children
                    else:
                        continue
                else:
                    visible_children = list(child_names)

                visible_subsections.append({
                    "name": sub,
                    "children": visible_children,
                })

            if query and not section_matches and not visible_subsections:
                continue

            # Insert parent section
            parent_iid = self._build_section_iid(s)
            section_size = self.controller.section_manager.get_section_total_code_size(s)
            self.section_tree.insert(
                "",
                "end",
                iid=parent_iid,
                text=self._format_section_tree_label(s, section_size),
                open=True,
                tags=("section",)
            )

            self._visible_section_ids.append(parent_iid)

            # Insert subsections and segments as children
            for subsection_entry in visible_subsections:
                sub = subsection_entry["name"]
                sub_iid = self._build_section_iid(s, sub)
                subsection_size = self.controller.section_manager.get_subsection_total_code_size(s, sub)
                self.section_tree.insert(
                    parent_iid,
                    "end",
                    iid=sub_iid,
                    text=self._format_section_tree_label(sub, subsection_size),
                    tags=("subsection",)
                )

                for child_name in subsection_entry["children"]:
                    child_iid = self._build_section_iid(s, sub, child_name)
                    child_size = self.controller.section_manager.get_segment_total_code_size(s, sub, child_name)
                    self.section_tree.insert(
                        sub_iid,
                        "end",
                        iid=child_iid,
                        text=self._format_section_tree_label(child_name, child_size),
                        tags=("segment", self._get_section_size_tag(child_size))
                    )

        # Insert a minimal empty space at the end to make deselection easier.
        self._insert_section_tree_deselect_spacers()
        self._refresh_section_tree_icons()

        selection_candidates = []
        if preferred_iid:
            selection_candidates.append(preferred_iid)
        if self._last_selected_scope_iid:
            selection_candidates.append(self._last_selected_scope_iid)
        if self._last_selected_section:
            if self._last_selected_segment:
                selection_candidates.append(
                    self._build_section_iid(
                        self._last_selected_section,
                        self._last_selected_subsection,
                        self._last_selected_segment
                    )
                )
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
                self._update_section_tree_item_icon(parent_iid)
            self._on_section_select(force_reload=force_reload)
        else:
            self._on_section_select(force_reload=True)

    def _format_section_tree_label(self, name, total_bytes):
        """Builds the text shown in the sections tree including the total code size."""
        return f"{name}  [{self._format_section_size_kb(total_bytes)}]"

    def _insert_section_tree_deselect_spacers(self, rows=2):
        """Adds a couple of empty rows at the end of the tree for easier deselection."""
        total_rows = max(1, int(rows))
        for index in range(total_rows):
            suffix = "" if index == 0 else f"_{index}"
            self.section_tree.insert(
                "",
                "end",
                iid=f"EMPTY_DESELECT{suffix}",
                text=" ",
                tags=("subsection",)
            )

    def _format_section_size_kb(self, total_bytes):
        """Formats the size label for sections and subsections."""
        return f"{(max(total_bytes, 0) / 1024.0):.1f} KB"

    def _get_section_size_tag(self, total_bytes):
        """Returns the color tag matching the section size thresholds."""
        size_kb = max(total_bytes, 0) / 1024.0
        if size_kb < 15:
            return "size_blue"
        if size_kb < 30:
            return "size_green"
        if size_kb <= 50:
            return "size_yellow"
        return "size_red"

    def _on_file_double_click(self, event):
        """
        Elimina el fichero seleccionado de la lista al hacer doble click.
        No elimina el fichero físico del disco, solo lo remueve de la vista.
        """
        column_id = self.tree.identify_column(event.x)
        if column_id == "#4":
            iid = self.tree.identify_row(event.y)
            if iid:
                self._open_file_preview(iid)
            return
        # Obtener el item seleccionado bajo el cursor
        iid = self.tree.identify_row(event.y)
        if iid:
            self._remove_file_tree_item(iid)

    def _remove_file_tree_item(self, item_id):
        """Removes a file row from the visible table."""
        region_item = self._get_region_row_item(item_id)
        if region_item:
            self.tree.delete(item_id)
            self._region_rows_by_iid.pop(item_id, None)
            self._last_region_list_items = [
                item for item in self._last_region_list_items
                if item is not region_item
            ]
            self._schedule_folder_chip_refresh()
            return

        file_path = self._get_tree_item_path(item_id)
        if not file_path:
            return

        self._discarded_file_paths.add(file_path)
        filename = os.path.basename(file_path)
        self.tree.delete(item_id)
        self._schedule_folder_chip_refresh()
        print(f"CodeView: Fichero '{filename}' eliminado de la lista.")

    def _on_reload_project_files(self):
        """Reloads project files from disk and restores previously discarded rows."""
        project_path = getattr(getattr(self.controller, "project_manager", None), "current_project_path", None)
        if not project_path:
            messagebox.showwarning("Aviso", "No hay ningún proyecto cargado para recargar.")
            return

        self._discarded_file_paths.clear()
        self._last_relevant_files = None
        self.controller.load_project_folder(project_path)

    def _on_go_to_file_from_section_tree(self):
        """Reveals one file for the selected section/subsection/segment/region scope."""
        scope_kind, _section_name, _sub_name, _leaf_name = self._get_selected_tree_item_info()
        scope_label = {
            "section": "sección",
            "subsection": "subsección",
            "segment": "segmento",
            "region_segment": "región",
        }.get(scope_kind, "elemento")

        file_paths = self._get_selected_scope_file_paths()
        target_path = self._select_file_path_for_navigation(file_paths, scope_label)
        if not target_path:
            return

        self._reveal_file_in_explorer(target_path)

    def _on_go_to_file_from_file_list(self):
        """Reveals the selected file (or region source file) from the left list."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Ir a archivo", "Selecciona un fichero o región primero.")
            return

        item_id = selected[0]
        region_item = self._get_region_row_item(item_id)
        if region_item:
            file_paths = self._normalize_existing_file_paths([region_item.get("file_path")])
            scope_label = "región"
        else:
            file_paths = self._normalize_existing_file_paths([self._get_tree_item_path(item_id)])
            scope_label = "fichero"

        target_path = self._select_file_path_for_navigation(file_paths, scope_label)
        if not target_path:
            return

        self._reveal_file_in_explorer(target_path)

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

    def _open_file_preview(self, item_id):
        """Shows the full code of the selected file in the preview panel."""
        if not item_id:
            return

        self._select_file_tree_item(item_id)
        region_item = self._get_region_row_item(item_id)
        if region_item:
            title = (
                f"Región: {region_item.get('header') or region_item.get('name') or 'Sin nombre'} "
                f"({region_item.get('file_rel_path') or os.path.basename(region_item.get('file_path') or '')})"
            )
            self._show_segment_code_view(
                region_item.get("content", ""),
                title_text=title,
                file_hint=region_item.get("file_path"),
                preview_mode="file"
            )
            return

        full_path = self._get_tree_item_path(item_id)
        if not full_path:
            return

        file_data = self.controller.get_file_content_by_path(full_path)
        if not file_data:
            messagebox.showwarning("Aviso", "No se pudo cargar el contenido del fichero seleccionado.")
            return

        self._show_segment_code_view(
            file_data.get("content", ""),
            title_text=f"Archivo: {file_data.get('rel_path', os.path.basename(full_path))}",
            file_hint=full_path,
            preview_mode="file"
        )

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
