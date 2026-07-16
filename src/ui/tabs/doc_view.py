import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
import io
import json
import os
import webbrowser
import logging
import re
import time
import shutil
from difflib import SequenceMatcher
from urllib.parse import quote, unquote
from html import escape as html_escape
from src.logic.prompt_rules import ensure_file_path_comment_instruction
from markdown_it import MarkdownIt
from tkinterweb import HtmlFrame
from PIL import Image, ImageDraw, ImageTk
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Text
from src.ui.popups.diagram_editor import DiagramEditorWindow
from src.logic.app_paths import bundled_path
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except Exception:
    cairosvg = None
    CAIROSVG_AVAILABLE = False
try:
    from src.addons.Arbitrary_sus import create_styled_text_widget as arb_create_styled_text_widget
    from src.addons.Arbitrary_sus import highlight_syntax as arb_highlight_syntax
    from src.addons.Arbitrary_sus import THEME as ARB_THEME
    from src.addons.Arbitrary_sus import FONT_CODE as ARB_FONT_CODE
    ARB_STYLE_AVAILABLE = True
except Exception:
    ARB_STYLE_AVAILABLE = False
    ARB_THEME = {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "cursor": "#aeafad",
        "select_bg": "#264f78",
    }
    ARB_FONT_CODE = ("Menlo", 14)
    def arb_create_styled_text_widget(parent):
        return tk.Text(
            parent,
            font=ARB_FONT_CODE,
            bg=ARB_THEME["bg"],
            fg=ARB_THEME["fg"],
            relief="flat",
            wrap="none",
            insertbackground=ARB_THEME["cursor"],
            selectbackground=ARB_THEME["select_bg"]
        )
    def arb_highlight_syntax(text_widget, file_path=None):
        return None


class VsCodeDarkStyle(Style):
    background_color = "#0a1628"
    default_style = "#d4d4d4"
    styles = {
        Text: "#d4d4d4",
        Comment: "italic #6a9955",
        Keyword: "#569cd6",
        Operator: "#d4d4d4",
        Operator.Word: "#569cd6",
        Name: "#9cdcfe",
        Name.Builtin: "#4ec9b0",
        Name.Function: "#dcdcaa",
        Name.Class: "#4ec9b0",
        Name.Decorator: "#c586c0",
        Name.Attribute: "#9cdcfe",
        Name.Variable: "#9cdcfe",
        Name.Variable.Instance: "#9cdcfe",
        Name.Variable.Class: "#9cdcfe",
        Name.Variable.Global: "#9cdcfe",
        Name.Other: "#9cdcfe",
        String: "#ce9178",
        Number: "#b5cea8",
    }


class VsCodeLightStyle(Style):
    background_color = "#f5f5f5"
    default_style = "#24292f"
    styles = {
        Text: "#24292f",
        Comment: "italic #008000",
        Keyword: "#0000ff",
        Operator: "#24292f",
        Name.Builtin: "#267f99",
        Name.Function: "#795e26",
        Name.Class: "#267f99",
        Name.Decorator: "#af00db",
        String: "#a31515",
        Number: "#098658",
    }

class DocView(ttk.Frame):
    """
    The view responsible for displaying the 'Documentation' section.
    Includes a sections panel, a markdown viewer/editor with CRUD functionality,
    and a selector for multiple matching documents.
    """
    DRAG_SASH_WIDTH = 18
    DRAG_HANDLE_SIZE = 14
    MARKDOWN_EDITOR_INDENT = "    "
    MARKDOWN_PREVIEW_ZOOM = 1.2
    MARKDOWN_PREVIEW_FONTSCALE = 1.08
    MARKDOWN_PREVIEW_ZOOM_STEP = 0.1
    MARKDOWN_PREVIEW_ZOOM_MIN = 0.8
    MARKDOWN_PREVIEW_ZOOM_MAX = 2.2
    MARKDOWN_EDITOR_FONT_SIZE_DEFAULT = 12
    MARKDOWN_EDITOR_FONT_SIZE_STEP = 1
    MARKDOWN_EDITOR_FONT_SIZE_MIN = 9
    MARKDOWN_EDITOR_FONT_SIZE_MAX = 32
    DEFAULT_SECTIONS_PANEL_WIDTH = 340
    NO_DOCUMENTATION_PATH_LABEL = "Ninguna"
    AUTOSAVE_DELAY_MS = 3000
    FULLSCREEN_ENTER_SVG = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f2f3f5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 9L4 4"/>
      <path d="M4 8V4H8"/>
      <path d="M15 9L20 4"/>
      <path d="M16 4H20V8"/>
      <path d="M9 15L4 20"/>
      <path d="M4 16V20H8"/>
      <path d="M15 15L20 20"/>
      <path d="M16 20H20V16"/>
    </svg>
    """
    FULLSCREEN_EXIT_SVG = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f2f3f5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 4L9 9"/>
      <path d="M5 9H9V5"/>
      <path d="M20 4L15 9"/>
      <path d="M15 5V9H19"/>
      <path d="M4 20L9 15"/>
      <path d="M5 15H9V19"/>
      <path d="M20 20L15 15"/>
      <path d="M15 19V15H19"/>
    </svg>
    """

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        
        self.controller = None
        self.current_file_path = None
        self.highlight_timer = None   # For debounce
        self.autosave_timer = None
        self.autosave_enabled = False
        self.is_dark_mode = True      # Default to Dark
        self.is_editor_mode = False   # Default to Viewer (False=Viewer, True=Editor)
        self.is_right_panel_visible = True
        self.is_code_panel_visible = False
        self.is_fullscreen_mode = False
        self._last_code_token = None
        self._sidebar_visible_before_fullscreen = True
        self._editable_blocks = {}
        self._editable_block_seq = 0
        self._pending_web_view_scroll = None
        self._pending_web_view_fragment = None
        self._pending_document_search_query = ""
        self._document_search_scroll_token = 0
        self._preserve_section_selection = True
        self._code_highlight_job = None
        self._active_code_file_path = None
        self.diagram_editor_window = None
        self.doc_path_options = {}
        self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
        self.markdown_preview_fontscale = self.MARKDOWN_PREVIEW_FONTSCALE
        self.markdown_editor_font_size = self.MARKDOWN_EDITOR_FONT_SIZE_DEFAULT
        self.code_font_family = self._resolve_code_font_family()
        self.doc_sidebar_font_family = self._resolve_doc_sidebar_font_family()
        self.code_font_size = ARB_FONT_CODE[1] if ARB_FONT_CODE else 14
        self.toolbar_surface_bg = Styles.COLOR_DOC_TOOLBAR_BG
        self._doc_tree_drag_source = None
        self._doc_tree_drag_start = None
        self._doc_tree_drag_active = False
        self._doc_tree_drop_target = None
        self.advanced_doc_search_var = tk.BooleanVar(value=False)
        self._doc_search_content_cache = {}
        self._doc_search_placeholder_active = False
        self._section_search_debounce_job = None
        self._advanced_doc_search_scope = None
        self.list_project_documents_var = tk.BooleanVar(value=False)
        self._show_all_doc_sections = False
        self.DOC_SECTIONS_INITIAL_LIMIT = 10
        self.DOC_SECTIONS_EXPANDED_VISIBLE_ROWS = 20
        self._section_colors = {}

        try:
            self.controller = parent.master.controller
        except:
            try:
                self.controller = parent.winfo_toplevel().controller
            except:
                pass
        
        self._last_selected_section = None

        # Load settings if available
        if self.controller and hasattr(self.controller, 'config_manager'):
            settings = self.controller.config_manager.get_doc_view_settings()
            self.is_dark_mode = settings.get("is_dark_mode", True)
            self.is_editor_mode = settings.get("is_editor_mode", False)
            self.code_sash_ratio = settings.get("code_sash_ratio", 0.7)
            self.is_fullscreen_mode = settings.get("is_fullscreen_mode", False)
            self.markdown_preview_zoom = settings.get("markdown_preview_zoom", self.MARKDOWN_PREVIEW_ZOOM)
            self.markdown_editor_font_size = settings.get(
                "markdown_editor_font_size",
                self.MARKDOWN_EDITOR_FONT_SIZE_DEFAULT
            )
            self.autosave_enabled = bool(self.controller.config_manager.get_doc_autosave_enabled())
            self.list_project_documents_var.set(
                bool(self.controller.config_manager.get_list_project_documents_enabled())
            )
            self.advanced_doc_search_var.set(
                bool(self.controller.config_manager.get_advanced_doc_search_enabled())
            )
        else:
            self.code_sash_ratio = 0.7
            self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
            self.markdown_editor_font_size = self.MARKDOWN_EDITOR_FONT_SIZE_DEFAULT
        try:
            self.code_sash_ratio = float(self.code_sash_ratio)
        except Exception:
            self.code_sash_ratio = 0.7
        self.code_sash_ratio = max(0.2, min(0.9, self.code_sash_ratio))
        try:
            self.markdown_preview_zoom = float(self.markdown_preview_zoom)
        except Exception:
            self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
        self.markdown_preview_zoom = max(
            self.MARKDOWN_PREVIEW_ZOOM_MIN,
            min(self.markdown_preview_zoom, self.MARKDOWN_PREVIEW_ZOOM_MAX)
        )
        self.markdown_preview_fontscale = self._compute_markdown_preview_fontscale(self.markdown_preview_zoom)
        try:
            self.markdown_editor_font_size = int(self.markdown_editor_font_size)
        except Exception:
            self.markdown_editor_font_size = self.MARKDOWN_EDITOR_FONT_SIZE_DEFAULT
        self.markdown_editor_font_size = max(
            self.MARKDOWN_EDITOR_FONT_SIZE_MIN,
            min(self.markdown_editor_font_size, self.MARKDOWN_EDITOR_FONT_SIZE_MAX)
        )

        self._load_icons()
        self._create_layout()

    def _resolve_code_font_family(self):
        preferred_families = ["Consolas", "Menlo", "Monaco", "Courier New", "Courier"]
        try:
            available = set(tkfont.families())
        except Exception:
            return "Consolas"

        for family in preferred_families:
            if family in available:
                return family
        return "Courier"

    def _resolve_doc_sidebar_font_family(self):
        return Styles.FONT_FAMILY

    def _load_icons(self):
        """Loads icons from assets directory."""
        self.icons = {}
        icon_paths = {
            "folder_open": ("folder_open.png",),
            "file_plus": ("file_plus.png",),
            "save": ("save.png",),
            "delete": ("delete.png",),
            "edit": ("edit.png",),
            "view": ("view.png",),
            "moon": ("moon.png",),
            "sun": ("sun.png",),
            "prompt": ("prompt.png",),
        }
        try:
            base_path = bundled_path("assets", "icons")
            for name, relative_parts in icon_paths.items():
                path = os.path.join(base_path, *relative_parts)
                if os.path.exists(path):
                    img = Image.open(path).resize((20, 20), Image.Resampling.LANCZOS)
                    self.icons[name] = ImageTk.PhotoImage(img)
                else:
                    self.icons[name] = None
        except Exception as e:
            logging.error(f"Error loading icons: {e}")
        self.icons["fullscreen_enter"] = self._create_svg_icon(self.FULLSCREEN_ENTER_SVG, mode="enter")
        self.icons["fullscreen_exit"] = self._create_svg_icon(self.FULLSCREEN_EXIT_SVG, mode="exit")

    def _create_svg_icon(self, svg_markup, mode, size=(22, 22)):
        try:
            if CAIROSVG_AVAILABLE:
                png_bytes = cairosvg.svg2png(
                    bytestring=svg_markup.encode("utf-8"),
                    output_width=size[0],
                    output_height=size[1]
                )
                image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
                return ImageTk.PhotoImage(image)
        except Exception as e:
            logging.warning(f"Error rendering SVG icon '{mode}': {e}")

        return ImageTk.PhotoImage(self._draw_fullscreen_fallback_icon(mode, size))

    def _draw_fullscreen_fallback_icon(self, mode, size):
        upscale = 6
        large_size = (size[0] * upscale, size[1] * upscale)
        image = Image.new("RGBA", large_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = "#f2f3f5"
        scale_x = large_size[0] / 24.0
        scale_y = large_size[1] / 24.0
        stroke = max(8, round(min(large_size) / 10))

        def point(x, y):
            return (round(x * scale_x), round(y * scale_y))

        def segment(start, end):
            draw.line([point(*start), point(*end)], fill=color, width=stroke, joint="curve")

        if mode == "enter":
            segments = [
                ((10, 10), (4.5, 4.5)),
                ((4.5, 8.8), (4.5, 4.5)),
                ((4.5, 4.5), (8.8, 4.5)),
                ((14, 10), (19.5, 4.5)),
                ((15.2, 4.5), (19.5, 4.5)),
                ((19.5, 4.5), (19.5, 8.8)),
                ((10, 14), (4.5, 19.5)),
                ((4.5, 15.2), (4.5, 19.5)),
                ((4.5, 19.5), (8.8, 19.5)),
                ((14, 14), (19.5, 19.5)),
                ((15.2, 19.5), (19.5, 19.5)),
                ((19.5, 15.2), (19.5, 19.5)),
            ]
        else:
            segments = [
                ((4.5, 4.5), (10, 10)),
                ((5.2, 10), (10, 10)),
                ((10, 5.2), (10, 10)),
                ((19.5, 4.5), (14, 10)),
                ((14, 5.2), (14, 10)),
                ((14, 10), (18.8, 10)),
                ((4.5, 19.5), (10, 14)),
                ((5.2, 14), (10, 14)),
                ((10, 14), (10, 18.8)),
                ((19.5, 19.5), (14, 14)),
                ((14, 14), (14, 18.8)),
                ((14, 14), (18.8, 14)),
            ]

        for start, end in segments:
            segment(start, end)

        return image.resize(size, Image.Resampling.LANCZOS)

    def set_controller(self, controller):
        """Explicitly set controller if not available via hierarchy."""
        self.controller = controller
        self._refresh_sections()

    def _create_layout(self):
        """Creates the split-pane layout."""
        self.paned_window = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=self.DRAG_SASH_WIDTH,
            handlesize=self.DRAG_HANDLE_SIZE,
            showhandle=True,
            bg=Styles.COLOR_BG_MAIN,
            sashrelief="flat",
            bd=0,
            borderwidth=0,
            relief="flat"
        )
        self.paned_window.pack(fill="both", expand=True)
        self.paned_window.bind("<Configure>", self._schedule_sidebar_toggle_position, add="+")
        self.paned_window.bind("<B1-Motion>", self._schedule_sidebar_toggle_position, add="+")
        self.paned_window.bind("<ButtonRelease-1>", self._schedule_sidebar_toggle_position, add="+")

        # --- Left Pane (Markdown Content) ---
        self.left_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(self.left_frame, minsize=400, stretch="always")

        # Header with actions - Toolbar style
        self.header_frame = tk.Frame(
            self.left_frame,
            bg=self.toolbar_surface_bg,
            bd=0,
            highlightthickness=0
        )
        self.header_frame.pack(side="top", fill="x")
        
        # Action Buttons Row (Toolbar)
        self.actions_row = tk.Frame(self.header_frame, bg=self.toolbar_surface_bg)
        self.actions_row.pack(side="top", fill="x", padx=5, pady=8)  # Reducido padx a 5
        
        self.toolbar_buttons_group = self._create_toolbar_group(self.actions_row, side="left")
                
        self.btn_load = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,  # Reducido de 0 a 1 para un pequeño espacio entre botones
            style="DocToolbarFlat.TButton",
            image=self.icons.get("folder_open"),
            text="Abrir",
            command=self._on_load_docs,
            tooltip_text="Abrir docs"
        )
        
        self.btn_new = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=self.icons.get("file_plus"),
            text="Nuevo",
            command=self._on_new_doc,
            tooltip_text="Nuevo doc"
        )
        
        self.btn_save = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=self.icons.get("save"),
            text="Guardar",
            command=self._on_save_doc,
            tooltip_text="Guardar doc"
        )
        
        self.btn_prompt_template = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=self.icons.get("prompt"),
            text="Prompt",
            command=self._safe_open_prompt_builder,
            tooltip_text="Crear prompt"
        )
        
        # View Toggles
        mode_icon = self.icons.get("edit") if not self.is_editor_mode else self.icons.get("view")
        self.btn_mode = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=mode_icon,
            text="Editar" if not self.is_editor_mode else "Vista",
            command=self._toggle_mode,
            tooltip_text="Cambiar vista"
        )
        
        # self.btn_diagrams = self._create_toolbar_button(
        #     self.toolbar_buttons_group,
        #     side="left",
        #     padx=1,
        #     style="DocToolbarFlat.TButton",
        #     text="Diagrama",
        #     command=self._open_diagram_editor,
        #     tooltip_text="Crear diagrama"
        # )
        
        theme_icon = self.icons.get("moon") if not self.is_dark_mode else self.icons.get("sun")
        self.btn_theme = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=theme_icon,
            text="Tema",
            command=self._toggle_theme,
            tooltip_text="Cambiar tema"
        )
        
        self.btn_toggle_fullscreen = self._create_toolbar_button(
            self.toolbar_buttons_group,
            side="left",
            padx=1,
            style="DocToolbarFlat.TButton",
            image=self.icons.get("fullscreen_enter"),
            text="Pantalla",
            command=self._toggle_fullscreen_mode,
            tooltip_text="Pantalla completa"
        )

        # File Selector for Multiple Matches - HIDDEN as it is redundant now
        self.selector_row = tk.Frame(self.header_frame, bg=self.toolbar_surface_bg)
        # self.selector_row.pack(side="top", fill="x", padx=15, pady=(0, 6))

        self.lbl_file_count = tk.Label(self.selector_row, text="Documentos:",
            font=(Styles.FONT_FAMILY, 12), bg=self.toolbar_surface_bg, fg=Styles.COLOR_DIM)
        # self.lbl_file_count.pack(side="left", padx=(0, 10))

        self.cmb_files = ttk.Combobox(self.selector_row, state="readonly", width=40, font=(Styles.FONT_FAMILY, 14))
        # self.cmb_files.pack(side="left", fill="x", expand=True)
        self.cmb_files.bind("<<ComboboxSelected>>", self._on_file_selected_via_combo)

        # self.btn_copy_doc = ttk.Button(
        #    self.actions_row, # Moved to main toolbar
        #    text="Copiar",
        #    style="ToolbarIcon.TButton",
        #    command=self._on_copy_doc_content
        #)
        #self.btn_copy_doc.pack(side="right", padx=(10, 0))
        #self.btn_copy_doc.state(["disabled"])
        #attach_tooltip(self.btn_copy_doc, "Copiar contenido del documento")
        
        # Increase dropdown list font size
        self.master.option_add('*TCombobox*Listbox.font', (Styles.FONT_FAMILY, 14))



        # Inner Content Area (Markdown + optional Code Panel)
        self.content_area = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.content_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.content_pane = tk.PanedWindow(
            self.content_area,
            orient=tk.HORIZONTAL,
            sashwidth=self.DRAG_SASH_WIDTH,
            handlesize=self.DRAG_HANDLE_SIZE,
            showhandle=True,
            bg=Styles.COLOR_PANE_DIVIDER,
            sashrelief="flat",
            bd=0,
            borderwidth=0,
            relief="flat"
        )
        self.content_pane.pack(fill="both", expand=True)
        self.content_pane.bind("<ButtonRelease-1>", self._on_content_pane_release)

        self.left_content_frame = ttk.Frame(self.content_pane, style="Main.TFrame")
        self.content_pane.add(self.left_content_frame, minsize=520, stretch="always")

        # 1. Editor (Hidden by default)
        self.editor_frame = ttk.Frame(self.left_content_frame, style="Main.TFrame")
        
        # Editor Label (Optional, maybe remove if single view is clear enough)
        # ttk.Label(self.editor_frame, text="EDITOR (Markdown)", font=(Styles.FONT_FAMILY, 10, "bold"), foreground=Styles.COLOR_DIM).pack(anchor="w", padx=5)

        self.txt_content = tk.Text(
            self.editor_frame,
            font=(self.code_font_family, self.markdown_editor_font_size),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground="white",
            relief="flat",
            padx=10, pady=10,
            wrap="word",
            state="disabled",
            undo=True 
        )
        self.txt_content.pack(fill="both", expand=True)
        self.txt_content.bind("<KeyRelease>", self._on_content_change)
        self.txt_content.bind("<Control-s>", self._on_save_doc_shortcut)
        self.txt_content.bind("<Control-z>", self._on_undo_markdown_shortcut)
        self.txt_content.bind("<Control-y>", self._on_redo_markdown_shortcut)
        self.txt_content.bind("<Command-s>", self._on_save_doc_shortcut)
        self.txt_content.bind("<Command-z>", self._on_undo_markdown_shortcut)
        self.txt_content.bind("<Command-y>", self._on_redo_markdown_shortcut)
        self._bind_markdown_editor_zoom_controls()

        # 2. Previewer (Visible by default)
        self.preview_frame = ttk.Frame(self.left_content_frame, style="Main.TFrame")

        # Preview Label
        # ttk.Label(self.preview_frame, text="PREVISUALIZACIÓN (Web)", font=(Styles.FONT_FAMILY, 10, "bold"), foreground=Styles.COLOR_DIM).pack(anchor="w", padx=5)

        # Use HtmlFrame for true web-based rendering
        self.web_view = HtmlFrame(
            self.preview_frame,
            messages_enabled=False,
            on_link_click=self._on_web_link_click,
            zoom=self.markdown_preview_zoom,
            fontscale=self.markdown_preview_fontscale
        )
        self.web_view.pack(fill="both", expand=True)
        self.web_view.bind("<Button-1>", self._activate_markdown_preview, add="+")
        self.web_view.bind("<Button-2>", self._on_markdown_selection_right_click)
        self.web_view.bind("<Button-3>", self._on_markdown_selection_right_click)
        self.web_view.bind("<Control-Button-1>", self._on_markdown_selection_right_click)
        self.web_view.bind("<<DoneLoading>>", self._on_web_view_done_loading)
        self._bind_markdown_preview_zoom_controls()

        # 3. Code Panel (Hidden by default)
        self.code_frame = ttk.Frame(self.content_pane, style="Main.TFrame")
        self.code_header = ttk.Frame(self.code_frame, style="Main.TFrame")
        self.code_header.pack(fill="x", padx=8, pady=(8, 4))
        self.code_controls = ttk.Frame(self.code_header, style="Main.TFrame")
        self.code_controls.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.lbl_code_file = ttk.Label(
            self.code_controls,
            text="Sin fichero seleccionado",
            style="TLabel"
        )
        self.lbl_code_file.pack(fill="x")

        self.btn_save_code = ttk.Button(
            self.code_header,
            text="Guardar",
            style="Action.TButton",
            command=self._save_active_code_file
        )
        self.btn_save_code.pack(side="right", padx=(0, 8))
        attach_tooltip(self.btn_save_code, "Guardar código")

        self.btn_close_code = ttk.Button(self.code_header, text="x", width=3, style="Nav.TButton", command=self._hide_code_panel)
        self.btn_close_code.pack(side="right")
        attach_tooltip(self.btn_close_code, "Cerrar panel")

        self.code_body = ttk.Frame(self.code_frame, style="Main.TFrame")
        self.code_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.code_text = arb_create_styled_text_widget(self.code_body)
        self.code_text.configure(font=(self.code_font_family, self.code_font_size))
        self.code_text.configure(padx=10, pady=10)
        self.code_text.pack(side="left", fill="both", expand=True)
        self.code_text.bind("<Button-1>", self._clear_code_match_highlight)
        self.code_text.bind("<<Modified>>", self._on_code_text_modified)
        self.code_text.bind("<Control-s>", self._on_save_code_shortcut)
        self.code_text.bind("<Control-z>", self._on_undo_code_shortcut)
        self.code_text.bind("<Control-y>", self._on_redo_code_shortcut)
        self.code_text.bind("<Command-s>", self._on_save_code_shortcut)
        self.code_text.bind("<Command-z>", self._on_undo_code_shortcut)
        self.code_text.bind("<Command-y>", self._on_redo_code_shortcut)

        self.code_scroll = ttk.Scrollbar(self.code_body, orient="vertical", command=self.code_text.yview)
        self.code_scroll.pack(side="right", fill="y")
        self.code_text.configure(yscrollcommand=self.code_scroll.set)
        self.code_text.tag_configure("match_highlight", background="#fff9c4", foreground="#111827")
        self.code_text.config(state="disabled")
        self.btn_save_code.state(["disabled"])

        # Initial View State
        self._update_view_mode()
        
        # Configure tags for Editor highlighting
        self._configure_markdown_tags()

        # --- Right Pane (Sections) ---
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame", width=self.DEFAULT_SECTIONS_PANEL_WIDTH)
        self.paned_window.add(self.right_frame, minsize=self.DEFAULT_SECTIONS_PANEL_WIDTH, stretch="never")


        self.btn_toggle_sidebar = tk.Label(
            self.paned_window,
            text="›",
            font=(self.doc_sidebar_font_family, 14, "bold"),
            fg=Styles.COLOR_BUTTON_FG,
            bg=Styles.COLOR_DOC_TOOLBAR_BG,
            cursor="hand2",
            width=2,  # Ancho en caracteres
            anchor="center"
        )
        self.btn_toggle_sidebar.bind("<Button-1>", lambda e: self._toggle_sidebar())
        attach_tooltip(self.btn_toggle_sidebar, "Alternar panel")

        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="both", expand=True)

        lbl_sections = ttk.Label(
            self.right_top_frame,
            text="Secciones",
            style="Header.TLabel",
            font=(self.doc_sidebar_font_family, 20, "bold")
        )
        lbl_sections.pack(fill="x")

        self.doc_paths_row = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        self.doc_paths_row.pack(fill="x", padx=8, pady=(8, 4))

        self.cmb_doc_paths = ttk.Combobox(
            self.doc_paths_row,
            state="readonly",
            font=(self.doc_sidebar_font_family, 14, "bold")
        )
        self.cmb_doc_paths.pack(fill="x")
        self.cmb_doc_paths.bind("<<ComboboxSelected>>", self._on_doc_path_selected)

        self.list_project_documents_check = tk.Checkbutton(
            self.right_top_frame,
            text="Listar documentos de proyecto",
            variable=self.list_project_documents_var,
            command=self._toggle_project_document_listing,
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            activebackground=Styles.COLOR_BG_SIDEBAR,
            activeforeground=Styles.COLOR_FG_TEXT,
            selectcolor=Styles.COLOR_INPUT_BG,
            font=(self.doc_sidebar_font_family, 11),
            anchor="w",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=2
        )
        self.list_project_documents_check.pack(fill="x", padx=8, pady=(0, 4))

        self.section_search_shell = tk.Frame(
            self.right_top_frame,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.section_search_shell.pack(fill="x", padx=8, pady=(4, 6))

        self.section_search_input_row = tk.Frame(
            self.section_search_shell,
            bg=Styles.COLOR_BG_SIDEBAR
        )
        self.section_search_input_row.pack(fill="x", padx=10, pady=(10, 10))

        self.section_search_entry = tk.Entry(
            self.section_search_input_row,
            font=(self.doc_sidebar_font_family, 15),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.section_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=8)
        self.section_search_entry.bind("<KeyRelease>", self._on_section_search_change)
        self.section_search_entry.bind("<Return>", self._on_advanced_doc_search_submit)
        self.section_search_entry.bind("<FocusIn>", self._on_doc_search_focus_in)
        self.section_search_entry.bind("<FocusOut>", self._on_doc_search_focus_out)

        self.advanced_search_toggle = tk.Label(
            self.section_search_input_row,
            text="",
            width=2,
            font=(self.doc_sidebar_font_family, 11, "bold"),
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0,
            padx=8,
            pady=8,
            cursor="hand2"
        )
        self.advanced_search_toggle.pack(side="right")
        self.advanced_search_toggle.bind("<Button-1>", lambda _e: self._toggle_advanced_doc_search())
        attach_tooltip(
            self.advanced_search_toggle,
            "Búsqueda avanzada: por similitud en todos los documentos"
        )
        self._show_doc_search_placeholder()
        self._update_advanced_doc_search_toggle()

        # Section Tree (replaces Listbox for hierarchical support)
        self.section_tree_frame = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        self.section_tree_frame.pack(fill="x", expand=False, padx=5, pady=5)

        self.section_tree = ttk.Treeview(
            self.section_tree_frame,
            show="tree",
            selectmode="extended",
            style="Treeview",
            height=self.DOC_SECTIONS_INITIAL_LIMIT
        )
        self.section_tree.column("#0", stretch=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_select)
        self.section_tree.bind("<Button-1>", self._on_section_click)
        self.section_tree.bind("<ButtonPress-1>", self._on_section_tree_press, add="+")
        self.section_tree.bind("<B1-Motion>", self._on_section_tree_drag_motion, add="+")
        self.section_tree.bind("<ButtonRelease-1>", self._on_section_tree_release, add="+")
        self.section_tree.bind("<BackSpace>", self._on_delete_section_shortcut)
        self.section_tree.bind("<Delete>", self._on_delete_section_shortcut)
        
        # Tags for different file types and folders
        self.section_tree.tag_configure("folder", font=(self.doc_sidebar_font_family, 16, "bold"), foreground=Styles.COLOR_ACCENT)
        self.section_tree.tag_configure("md", font=(self.doc_sidebar_font_family, 14))
        self.section_tree.tag_configure("document", font=(self.doc_sidebar_font_family, 14), foreground=Styles.COLOR_DIM)
        self.section_tree.tag_configure("drop_target", background="#244b74", foreground="#f4f7fb")

        doc_scrollbar_style = ttk.Style(self)
        doc_scrollbar_style.configure(
            "Documentation.Vertical.TScrollbar",
            gripcount=0,
            background="#5d6878",
            darkcolor="#5d6878",
            lightcolor="#5d6878",
            troughcolor=Styles.COLOR_BG_MAIN,
            bordercolor=Styles.COLOR_BG_MAIN,
            arrowcolor=Styles.COLOR_DIM,
            relief="flat",
            borderwidth=0
        )
        doc_scrollbar_style.map(
            "Documentation.Vertical.TScrollbar",
            background=[("active", "#748196")]
        )
        
        self.section_scrollbar = ttk.Scrollbar(
            self.section_tree_frame,
            orient="vertical",
            command=self.section_tree.yview,
            style="Documentation.Vertical.TScrollbar"
        )
        self.section_tree.configure(yscrollcommand=self.section_scrollbar.set)
        self.section_tree.pack(side="left", fill="both", expand=True)
        self.section_scrollbar.pack_forget()
                
        btn_frame = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        btn_frame.pack(fill="x", padx=5, pady=5)

        # Se muestra solo cuando hay más de diez entradas en la raíz. Es un
        # enlace textual, sin fondo ni borde, para no añadir otro botón visual
        # al panel de documentación.
        self.btn_show_more_sections = tk.Label(
            btn_frame,
            text="Mostrar más",
            font=(self.doc_sidebar_font_family, 13),
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            cursor="hand2",
            anchor="w",
            padx=5,
            pady=2
        )
        self.btn_show_more_sections.bind("<Button-1>", self._show_all_sections)
        self.btn_show_more_sections.bind(
            "<Enter>",
            lambda _event: self.btn_show_more_sections.configure(fg=Styles.COLOR_FG_TEXT)
        )
        self.btn_show_more_sections.bind(
            "<Leave>",
            lambda _event: self.btn_show_more_sections.configure(fg=Styles.COLOR_DIM)
        )
        
        
        # Nueva Sección moved to context menu
        
        # Context Menu for Sections (same as CodeView)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Nueva Sección", command=self._on_add_section)
        self.context_menu.add_command(label="Crear documento nuevo", command=self._on_new_doc)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Editar", command=self._on_edit_section)
        self.context_menu.add_command(label="Eliminar", command=self._on_delete_section)

        # Bind Right Click (Mac & Windows/Linux)
        self.section_tree.bind("<Button-2>", self._show_context_menu)
        self.section_tree.bind("<Button-3>", self._show_context_menu)
        self.section_tree.bind("<Control-Button-1>", self._show_context_menu)

        if self.controller:
            self._refresh_sections()


        self.after_idle(self._set_default_sections_panel_width)
        self._update_sidebar_toggle()
        self._update_fullscreen_button()
        self.after_idle(self._position_sidebar_toggle)

    def _create_toolbar_button(
        self,
        parent,
        side,
        padx,
        style,
        command,
        image=None,
        text="",
        tooltip_text=""
    ):
        parent_bg = self.toolbar_surface_bg
        slot_bg = self.toolbar_surface_bg if str(style).startswith("DocToolbarFlat") else parent_bg
        has_label = bool(text)

        # Ya no usamos slot_width fijo - permitimos que se expanda
        slot = tk.Frame(parent, bg=slot_bg, height=42)
        # Cambiado: expand=True para que ocupe espacio, fill="x" para expandir horizontalmente
        slot.pack(side=side, fill="x", expand=True, padx=padx)
        slot.pack_propagate(False)

        button = ttk.Button(
            slot,
            image=image,
            text=text,
            style=style,
            command=command,
            compound="left"
        )
        button.pack(fill="both", expand=True)
        if tooltip_text:
            attach_tooltip(button, tooltip_text)
        return button

    def _create_toolbar_group(self, parent, side):
        group = tk.Frame(
            parent,
            bg=self.toolbar_surface_bg,
            highlightthickness=0,
            bd=0
        )
        # Cambiado: ahora el grupo se expande para ocupar todo el espacio
        group.pack(side=side, fill="x", expand=True, padx=0)
        return group

    def _on_load_docs(self):
        path = filedialog.askdirectory()
        if path:
            if self.controller and hasattr(self.controller, 'config_manager'):
                self.controller.config_manager.set_doc_path(path)
            self._refresh_sections()

    def _open_diagram_editor(self):
        if self.diagram_editor_window and self.diagram_editor_window.winfo_exists():
            self.diagram_editor_window.deiconify()
            self.diagram_editor_window.lift()
            self.diagram_editor_window.focus_force()
            return

        self.diagram_editor_window = DiagramEditorWindow(
            self,
            on_close=self._on_diagram_editor_closed
        )

    def _on_diagram_editor_closed(self):
        self.diagram_editor_window = None

    def _bind_markdown_preview_zoom_controls(self):
        widgets = [self.web_view]
        html_widget = getattr(self.web_view, "_html", None)
        if html_widget is not None:
            widgets.append(html_widget)

        bindings = [
            ("<Control-plus>", self._zoom_in_markdown_preview),
            ("<Control-equal>", self._zoom_in_markdown_preview),
            ("<Control-KP_Add>", self._zoom_in_markdown_preview),
            ("<Command-plus>", self._zoom_in_markdown_preview),
            ("<Command-equal>", self._zoom_in_markdown_preview),
            ("<Command-KP_Add>", self._zoom_in_markdown_preview),
            ("<Control-minus>", self._zoom_out_markdown_preview),
            ("<Control-KP_Subtract>", self._zoom_out_markdown_preview),
            ("<Command-minus>", self._zoom_out_markdown_preview),
            ("<Command-KP_Subtract>", self._zoom_out_markdown_preview),
            ("<Control-0>", self._reset_markdown_preview_zoom),
            ("<Control-KP_0>", self._reset_markdown_preview_zoom),
            ("<Command-0>", self._reset_markdown_preview_zoom),
            ("<Command-KP_0>", self._reset_markdown_preview_zoom),
            ("<Button-1>", self._activate_markdown_preview),
        ]

        for widget in widgets:
            try:
                widget.configure(takefocus=True)
            except Exception:
                pass
            for sequence, handler in bindings:
                try:
                    widget.bind(sequence, handler, add="+")
                except Exception:
                    pass

    def _activate_markdown_preview(self, event=None):
        html_widget = getattr(self.web_view, "_html", None)
        try:
            if html_widget is not None:
                html_widget.focus_set()
            else:
                self.web_view.focus_set()
        except Exception:
            pass

    def _safe_focus_get(self):
        try:
            return self.focus_get()
        except Exception:
            return None

    def _is_descendant_widget(self, widget, ancestor):
        if widget is None or ancestor is None:
            return False

        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _is_markdown_preview_active(self):
        if self.is_editor_mode or not self.preview_frame.winfo_ismapped():
            return False

        focus_widget = self._safe_focus_get()
        html_widget = getattr(self.web_view, "_html", None)
        return (
            self._is_descendant_widget(focus_widget, self.preview_frame)
            or self._is_descendant_widget(focus_widget, self.web_view)
            or self._is_descendant_widget(focus_widget, html_widget)
        )

    def _is_markdown_editor_active(self):
        if not self.is_editor_mode or not self.editor_frame.winfo_ismapped():
            return False

        focus_widget = self._safe_focus_get()
        return (
            self._is_descendant_widget(focus_widget, self.editor_frame)
            or self._is_descendant_widget(focus_widget, self.txt_content)
        )

    def _bind_markdown_editor_zoom_controls(self):
        bindings = [
            ("<Control-plus>", self._zoom_in_markdown_editor),
            ("<Control-equal>", self._zoom_in_markdown_editor),
            ("<Control-KP_Add>", self._zoom_in_markdown_editor),
            ("<Command-plus>", self._zoom_in_markdown_editor),
            ("<Command-equal>", self._zoom_in_markdown_editor),
            ("<Command-KP_Add>", self._zoom_in_markdown_editor),
            ("<Control-minus>", self._zoom_out_markdown_editor),
            ("<Control-KP_Subtract>", self._zoom_out_markdown_editor),
            ("<Command-minus>", self._zoom_out_markdown_editor),
            ("<Command-KP_Subtract>", self._zoom_out_markdown_editor),
            ("<Control-0>", self._reset_markdown_editor_zoom),
            ("<Control-KP_0>", self._reset_markdown_editor_zoom),
            ("<Command-0>", self._reset_markdown_editor_zoom),
            ("<Command-KP_0>", self._reset_markdown_editor_zoom),
        ]
        for sequence, handler in bindings:
            try:
                self.txt_content.bind(sequence, handler, add="+")
            except Exception:
                pass

    def _apply_markdown_editor_font_size(self):
        self.markdown_editor_font_size = max(
            self.MARKDOWN_EDITOR_FONT_SIZE_MIN,
            min(self.markdown_editor_font_size, self.MARKDOWN_EDITOR_FONT_SIZE_MAX)
        )
        try:
            self.txt_content.configure(font=(self.code_font_family, self.markdown_editor_font_size))
        except Exception:
            return
        self._configure_markdown_tags()
        self._save_settings()

    def _zoom_in_markdown_editor(self, event=None):
        if not self._is_markdown_editor_active():
            return None
        self.markdown_editor_font_size += self.MARKDOWN_EDITOR_FONT_SIZE_STEP
        self._apply_markdown_editor_font_size()
        return "break"

    def _zoom_out_markdown_editor(self, event=None):
        if not self._is_markdown_editor_active():
            return None
        self.markdown_editor_font_size -= self.MARKDOWN_EDITOR_FONT_SIZE_STEP
        self._apply_markdown_editor_font_size()
        return "break"

    def _reset_markdown_editor_zoom(self, event=None):
        if not self._is_markdown_editor_active():
            return None
        self.markdown_editor_font_size = self.MARKDOWN_EDITOR_FONT_SIZE_DEFAULT
        self._apply_markdown_editor_font_size()
        return "break"

    def _compute_markdown_preview_fontscale(self, zoom_value):
        return 1.0 + ((zoom_value - 1.0) * 0.4)

    def _apply_markdown_preview_scale(self):
        self.markdown_preview_zoom = max(
            self.MARKDOWN_PREVIEW_ZOOM_MIN,
            min(self.markdown_preview_zoom, self.MARKDOWN_PREVIEW_ZOOM_MAX)
        )
        self.markdown_preview_fontscale = self._compute_markdown_preview_fontscale(self.markdown_preview_zoom)
        try:
            self.web_view.configure(
                zoom=self.markdown_preview_zoom,
                fontscale=self.markdown_preview_fontscale
            )
        except Exception:
            pass
        self._save_settings()

    def _zoom_in_markdown_preview(self, event=None):
        if not self._is_markdown_preview_active():
            return None
        self.markdown_preview_zoom += self.MARKDOWN_PREVIEW_ZOOM_STEP
        self._apply_markdown_preview_scale()
        return "break"

    def _zoom_out_markdown_preview(self, event=None):
        if not self._is_markdown_preview_active():
            return None
        self.markdown_preview_zoom -= self.MARKDOWN_PREVIEW_ZOOM_STEP
        self._apply_markdown_preview_scale()
        return "break"

    def _reset_markdown_preview_zoom(self, event=None):
        if not self._is_markdown_preview_active():
            return None
        self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
        self._apply_markdown_preview_scale()
        return "break"

    def _on_section_search_change(self, event=None):
        # Keep the selection that existed when this search burst started. The
        # advanced search refresh can clear the Treeview selection before the
        # user presses Enter.
        if self.advanced_doc_search_var.get():
            current_selection = tuple(self.section_tree.selection())
            if current_selection:
                self._advanced_doc_search_scope = current_selection
            elif self._advanced_doc_search_scope is None:
                self._advanced_doc_search_scope = ()
        else:
            self._advanced_doc_search_scope = None

        if self._section_search_debounce_job is not None:
            try:
                self.after_cancel(self._section_search_debounce_job)
            except Exception:
                pass
        self._section_search_debounce_job = self.after(500, self._apply_debounced_section_search)

    def _apply_debounced_section_search(self):
        self._section_search_debounce_job = None
        preferred_path = None
        # Durante la búsqueda avanzada no conservamos la selección anterior:
        # al reconstruir el árbol, su evento de selección podría volver a
        # abrir el documento y sobrescribir el salto realizado con Enter.
        if not self.advanced_doc_search_var.get():
            selected = self.section_tree.selection()
            if selected:
                preferred_path = selected[0]
        self._preserve_section_selection = not self.advanced_doc_search_var.get()
        try:
            self._refresh_sections(preferred_path=preferred_path)
        finally:
            self._preserve_section_selection = True

    def _iter_section_tree_items(self, parent=""):
        for item_id in self.section_tree.get_children(parent):
            yield item_id
            yield from self._iter_section_tree_items(item_id)

    def _get_document_search_candidates(self, selected_items):
        """Returns Markdown paths allowed by the current tree selection.

        With no selected items the complete tree is a valid search scope. An
        empty result with a selection means that none of its items is a
        searchable Markdown document or section.
        """
        all_candidates = [
            item_id
            for item_id in self._iter_section_tree_items()
            if os.path.isfile(item_id)
            and os.path.splitext(item_id)[1].lower() == ".md"
        ]
        if not selected_items:
            return all_candidates

        selected_paths = [
            os.path.normpath(item_id)
            for item_id in selected_items
            if item_id and os.path.exists(item_id)
        ]
        if not selected_paths:
            return []

        candidates = []
        for item_id in all_candidates:
            normalized_item = os.path.normpath(item_id)
            if any(
                normalized_item == selected_path
                or (
                    os.path.isdir(selected_path)
                    and self._is_descendant_path(selected_path, normalized_item)
                )
                for selected_path in selected_paths
            ):
                candidates.append(item_id)
        return candidates

    def _on_advanced_doc_search_submit(self, event=None):
        """Opens the first matching Markdown document and jumps to its match."""
        if not self.advanced_doc_search_var.get():
            return None

        # Capture the scope before applying a pending tree refresh. In
        # advanced mode that refresh intentionally clears the old selection.
        selected_items = tuple(self.section_tree.selection())
        if not selected_items and self._advanced_doc_search_scope:
            selected_items = self._advanced_doc_search_scope
        if self._section_search_debounce_job is not None:
            try:
                self.after_cancel(self._section_search_debounce_job)
            except Exception:
                pass
            self._section_search_debounce_job = None
            self._apply_debounced_section_search()

        query = self._get_doc_search_query()
        if not query:
            self._advanced_doc_search_scope = None
            return "break"

        exact_match = None
        search_candidates = self._get_document_search_candidates(selected_items)
        for item_id in search_candidates:
            normalized_content = self._read_text_document_for_search(item_id)
            if query in normalized_content and exact_match is None:
                exact_match = item_id

        match_path = exact_match
        if match_path:
            if self.section_tree.exists(match_path):
                self.section_tree.see(match_path)
            self._display_file_content(match_path, search_query=query)
        self._advanced_doc_search_scope = None
        return "break"

    def _toggle_advanced_doc_search(self):
        self.advanced_doc_search_var.set(not self.advanced_doc_search_var.get())
        self._advanced_doc_search_scope = None
        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_advanced_doc_search_enabled(
                self.advanced_doc_search_var.get()
            )
        if self._doc_search_placeholder_active or not self.section_search_entry.get().strip():
            self._show_doc_search_placeholder(force=True)
        self._update_advanced_doc_search_toggle()
        preferred_path = None
        selected = self.section_tree.selection() if hasattr(self, "section_tree") else ()
        if selected:
            preferred_path = selected[0]
        self._refresh_sections(preferred_path=preferred_path)

    def _update_advanced_doc_search_toggle(self):
        enabled = bool(self.advanced_doc_search_var.get())
        bg_color = "#2f4057" if not enabled else "#1f6feb"
        border_color = "#49648a" if not enabled else "#3b82f6"
        fg_color = "#d9e2ef" if not enabled else "#ffffff"
        self.advanced_search_toggle.configure(
            text="✓" if enabled else "",
            fg=fg_color,
            bg=bg_color,
            highlightbackground=border_color
        )

    def _get_doc_search_placeholder_text(self):
        if self.advanced_doc_search_var.get():
            return "Búsqueda avanzada..."
        return "Buscar..."

    def _show_doc_search_placeholder(self, force=False):
        if not hasattr(self, "section_search_entry"):
            return
        if not force and self.section_search_entry.get().strip() and not self._doc_search_placeholder_active:
            return
        self.section_search_entry.delete(0, tk.END)
        self.section_search_entry.insert(0, self._get_doc_search_placeholder_text())
        self.section_search_entry.configure(fg=Styles.COLOR_DIM)
        self._doc_search_placeholder_active = True

    def _hide_doc_search_placeholder(self):
        if not hasattr(self, "section_search_entry") or not self._doc_search_placeholder_active:
            return
        self.section_search_entry.delete(0, tk.END)
        self.section_search_entry.configure(fg=Styles.COLOR_INPUT_FG)
        self._doc_search_placeholder_active = False

    def _on_doc_search_focus_in(self, event=None):
        self._hide_doc_search_placeholder()

    def _on_doc_search_focus_out(self, event=None):
        if not hasattr(self, "section_search_entry"):
            return
        if not self.section_search_entry.get().strip():
            self._show_doc_search_placeholder()

    def _get_doc_search_query(self):
        if not hasattr(self, "section_search_entry") or self._doc_search_placeholder_active:
            return ""
        return self._normalize_doc_search_text(self.section_search_entry.get())

    def _normalize_doc_search_text(self, value):
        value = (value or "").strip().lower()
        return re.sub(r"\s+", " ", value)

    def _read_text_document_for_search(self, full_path):
        try:
            stat = os.stat(full_path)
        except Exception:
            return ""

        cache_key = (full_path, stat.st_mtime, stat.st_size)
        cached = self._doc_search_content_cache.get(full_path)
        if cached and cached.get("key") == cache_key:
            return cached.get("content", "")

        raw_content = ""
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(full_path, "r", encoding=encoding, errors="ignore") as f:
                    raw_content = f.read()
                break
            except Exception:
                continue

        normalized = self._normalize_doc_search_text(raw_content)
        self._doc_search_content_cache[full_path] = {"key": cache_key, "content": normalized}
        return normalized

    def _matches_advanced_doc_query(self, full_path, name, ext, query):
        if not query:
            return True

        name_norm = self._normalize_doc_search_text(name)
        if query in name_norm:
            return True

        tokens = [token for token in query.split(" ") if token]
        if not tokens:
            return True

        name_hits = sum(1 for token in tokens if token in name_norm)
        if name_hits / len(tokens) >= 0.7:
            return True
        if SequenceMatcher(None, query, name_norm).ratio() >= 0.72:
            return True

        text_search_exts = {".md", ".txt"}
        if ext not in text_search_exts:
            return False

        content = self._read_text_document_for_search(full_path)
        if not content:
            return False
        if query in content:
            return True

        content_hits = sum(1 for token in tokens if token in content)
        if content_hits / len(tokens) >= 0.7:
            return True

        candidate_lines = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(token in line for token in tokens):
                candidate_lines.append(line[:260])
            if len(candidate_lines) >= 120:
                break

        for line in candidate_lines:
            if SequenceMatcher(None, query, line).ratio() >= 0.78:
                return True

        return False

    def _on_doc_path_selected(self, event=None):
        selected_label = self.cmb_doc_paths.get().strip()
        if selected_label == self.NO_DOCUMENTATION_PATH_LABEL:
            self._show_all_doc_sections = False
            if self.controller and hasattr(self.controller, "config_manager"):
                self.controller.config_manager.set_doc_path(None)
            self._refresh_sections()
            return

        selected_path = self.doc_path_options.get(selected_label)
        if not selected_path:
            return

        current_path = self._get_doc_root()
        if current_path and os.path.normpath(current_path) == os.path.normpath(selected_path):
            return

        self._show_all_doc_sections = False
        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_doc_path(selected_path)
        self._refresh_sections()

    def _toggle_project_document_listing(self):
        """Switches between the documentation folder and the loaded project."""
        self._show_all_doc_sections = False
        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_list_project_documents_enabled(
                self.list_project_documents_var.get()
            )
        self._refresh_sections()

    def _get_project_root(self):
        if not self.controller or not hasattr(self.controller, "project_manager"):
            return None
        project_root = getattr(self.controller.project_manager, "current_project_path", None)
        if not project_root:
            return None
        project_root = os.path.abspath(project_root)
        return project_root if os.path.isdir(project_root) else None

    @staticmethod
    def _project_document_extensions():
        return {".md", ".pdf", ".doc", ".docx"}

    def _project_directory_has_documents(self, directory):
        extensions = self._project_document_extensions()
        ignored_dirs = {
            ".git", ".hg", ".svn", "__pycache__", ".venv", "venv",
            "node_modules", "dist", "build", ".idea", ".vscode"
        }
        try:
            for current_root, dirnames, filenames in os.walk(directory):
                dirnames[:] = [name for name in dirnames if name not in ignored_dirs]
                if any(os.path.splitext(name)[1].lower() in extensions for name in filenames):
                    return True
        except OSError:
            return False
        return False

    def _get_doc_root(self):
        if not self.controller or not hasattr(self.controller, "config_manager"):
            return None
        doc_dir = self.controller.config_manager.get_doc_path()
        if not doc_dir:
            return None
        doc_dir = os.path.abspath(doc_dir)
        if not os.path.isdir(doc_dir):
            return None
        return doc_dir

    def _get_section_dir(self, section_name):
        doc_dir = self._get_doc_root()
        if not doc_dir:
            return None
        return os.path.join(doc_dir, section_name)

    def _has_path_separator(self, value):
        if os.sep in value:
            return True
        if os.altsep and os.altsep in value:
            return True
        return False

    def _reset_doc_tree_drag_state(self):
        self._set_doc_tree_drop_target(None)
        self._doc_tree_drag_source = None
        self._doc_tree_drag_start = None
        self._doc_tree_drag_active = False
        try:
            self.section_tree.configure(cursor="")
        except Exception:
            pass

    def _set_doc_tree_drop_target(self, target_iid):
        previous = self._doc_tree_drop_target
        if previous and self.section_tree.exists(previous):
            tags = tuple(tag for tag in self.section_tree.item(previous, "tags") if tag != "drop_target")
            self.section_tree.item(previous, tags=tags)

        self._doc_tree_drop_target = None
        if not target_iid or not self.section_tree.exists(target_iid):
            return

        tags = list(self.section_tree.item(target_iid, "tags"))
        if "drop_target" not in tags:
            tags.append("drop_target")
            self.section_tree.item(target_iid, tags=tuple(tags))
        self._doc_tree_drop_target = target_iid

    def _is_descendant_path(self, base_path, candidate_path):
        try:
            return os.path.commonpath([os.path.normpath(base_path), os.path.normpath(candidate_path)]) == os.path.normpath(base_path)
        except Exception:
            return False

    def _resolve_doc_tree_drop_target(self, event):
        source_path = self._doc_tree_drag_source
        if not source_path or not os.path.exists(source_path):
            return None

        target_iid = self.section_tree.identify_row(event.y)
        if not target_iid or not self.section_tree.exists(target_iid):
            return None
        if target_iid == source_path:
            return None
        if not os.path.isdir(target_iid):
            return None

        normalized_source = os.path.normpath(source_path)
        normalized_target = os.path.normpath(target_iid)
        if os.path.dirname(normalized_source) == normalized_target:
            return None

        if os.path.isdir(source_path) and self._is_descendant_path(normalized_source, normalized_target):
            return None

        return target_iid

    def _get_path_after_move(self, current_path, source_path, moved_path):
        if not current_path:
            return current_path

        normalized_current = os.path.normpath(current_path)
        normalized_source = os.path.normpath(source_path)
        normalized_moved = os.path.normpath(moved_path)

        if normalized_current == normalized_source:
            return normalized_moved

        if os.path.isdir(source_path) and self._is_descendant_path(normalized_source, normalized_current):
            relative_path = os.path.relpath(normalized_current, normalized_source)
            return os.path.join(normalized_moved, relative_path)

        return current_path

    def _perform_doc_tree_drop(self, source_path, target_dir):
        source_path = os.path.normpath(source_path)
        target_dir = os.path.normpath(target_dir)
        destination_path = os.path.join(target_dir, os.path.basename(source_path))

        if os.path.exists(destination_path):
            messagebox.showwarning(
                "Mover en Documentación",
                f"Ya existe '{os.path.basename(source_path)}' dentro de '{os.path.basename(target_dir)}'."
            )
            return False

        confirmed = messagebox.askyesno(
            "Mover en Documentación",
            f"¿Mover '{os.path.basename(source_path)}' dentro de '{os.path.basename(target_dir)}'?"
        )
        if not confirmed:
            return False

        new_current_file_path = self._get_path_after_move(self.current_file_path, source_path, destination_path)

        try:
            shutil.move(source_path, target_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mover: {e}")
            return False

        if self.current_file_path and new_current_file_path != self.current_file_path:
            self.current_file_path = new_current_file_path
            self._update_breadcrumb(new_current_file_path)
            if self.controller and hasattr(self.controller, "config_manager"):
                self.controller.config_manager.set_last_doc_file(new_current_file_path)

        preferred_path = new_current_file_path if new_current_file_path and os.path.exists(new_current_file_path) else destination_path
        self._refresh_sections(preferred_path=preferred_path)
        return True

    def _on_section_tree_press(self, event):
        self._reset_doc_tree_drag_state()

        iid = self.section_tree.identify_row(event.y)
        if not iid or not self.section_tree.exists(iid):
            return

        self._doc_tree_drag_source = iid
        self._doc_tree_drag_start = (event.x, event.y)

    def _on_section_tree_drag_motion(self, event):
        if not self._doc_tree_drag_source or not self._doc_tree_drag_start:
            return

        delta_x = abs(event.x - self._doc_tree_drag_start[0])
        delta_y = abs(event.y - self._doc_tree_drag_start[1])
        if not self._doc_tree_drag_active and max(delta_x, delta_y) < 6:
            return

        self._doc_tree_drag_active = True
        try:
            self.section_tree.configure(cursor="hand2")
        except Exception:
            pass

        target_iid = self._resolve_doc_tree_drop_target(event)
        self._set_doc_tree_drop_target(target_iid)
        return "break"

    def _on_section_tree_release(self, event):
        if not self._doc_tree_drag_active:
            self._reset_doc_tree_drag_state()
            return

        source_path = self._doc_tree_drag_source
        target_iid = self._resolve_doc_tree_drop_target(event)
        self._reset_doc_tree_drag_state()

        if not source_path or not target_iid:
            return "break"

        self._perform_doc_tree_drop(source_path, target_iid)
        return "break"

    def _on_section_select(self, event=None, force_reload=False):
        if self._doc_tree_drag_active:
            return

        selected_items = self.section_tree.selection()
        if not selected_items:
            # self._display_message("Selecciona un documento o carpeta.")
            return

        # Con selección múltiple no se abre ni se pliega ningún elemento: la
        # selección queda preparada para operaciones sobre varias secciones.
        if len(selected_items) > 1:
            return
            
        item_id = selected_items[0]
        item_data = self.section_tree.item(item_id)
        path = item_id # Item ID is the full path
        
        if not path or not os.path.exists(path):
            return

        if os.path.isdir(path):
            # It's a directory - toggle expansion
            if self.section_tree.item(item_id, "open"):
                self.section_tree.item(item_id, open=False)
            else:
                self.section_tree.item(item_id, open=True)
            return

        # It's a file
        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_last_doc_file(path)

        ext = os.path.splitext(path)[1].lower()
        if ext == '.md':
            self._display_file_content(path)
        else:
            # Other file types: open with system default
            try:
                import webbrowser
                webbrowser.open(path)
            except Exception as e:
                logging.error(f"Error opening file {path}: {e}")
                messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")

    def _on_file_selected_via_combo(self, event=None):
        """Redundant with the tree."""
        pass

    def _on_copy_doc_content(self):
        if not self.current_file_path:
            messagebox.showwarning("Aviso", "No hay ningún documento abierto para copiar.")
            return

        content = self.txt_content.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("Aviso", "El documento está vacío.")
            return

        try:
            if self.controller and hasattr(self.controller, "copy_to_clipboard"):
                copied = self.controller.copy_to_clipboard(content)
                if copied:
                    return
            self.clipboard_clear()
            self.clipboard_append(content)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo copiar el documento: {e}")
            return

    def _display_file_content(self, file_path, search_query=""):
        try:
            self._document_search_scroll_token += 1
            self._cancel_autosave_timer()
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.current_file_path = file_path
            #self.btn_copy_doc.state(["!disabled"])
            self.txt_content.config(state="normal")
            self.txt_content.delete("1.0", tk.END)
            # Use empty content if file is empty to ensure editable state
            self.txt_content.insert("1.0", content)
            self.txt_content.edit_reset() # Clear undo stack
            
            # Update breadcrumb
            self._update_breadcrumb(file_path)
            
            # Apply highlighting
            self._pending_document_search_query = search_query if search_query else ""
            self._pending_web_view_fragment = "doc-search-match" if search_query else None
            self._apply_markdown_rendering()
            if search_query:
                self._schedule_document_search_scroll()
            self._pending_document_search_query = ""
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer: {e}")

    def _update_breadcrumb(self, file_path=None):
        """Updates the breadcrumb navigation label."""
        parts = ["HidraSmart"]
        
        # Add section name
        if self._last_selected_section:
            parts.append(self._last_selected_section)
        else:
            parts.append("Documentos")
        
        # Add filename
        if file_path:
            parts.append(os.path.basename(file_path))
        
        breadcrumb_text = "  /  ".join(parts)
        try:
            self.breadcrumb_label.config(text=breadcrumb_text)
        except Exception:
            pass

    def _save_current_document(self, show_errors=False):
        """Saves the active markdown document to disk."""
        if not self.current_file_path:
            if show_errors:
                messagebox.showwarning("Aviso", "No hay ningún documento abierto para guardar.")
            return False

        try:
            content = self.txt_content.get("1.0", "end-1c")
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"DocView: Guardado {self.current_file_path}")
            return True
        except Exception as e:
            logging.error(f"DocView: Error al guardar {self.current_file_path}: {e}")
            if show_errors:
                messagebox.showerror("Error", f"Error al guardar: {e}")
            return False

    def _on_save_doc(self):
        self._save_current_document(show_errors=True)

    def _on_save_doc_shortcut(self, event=None):
        self._on_save_doc()
        return "break"

    def set_autosave_enabled(self, enabled):
        """Enables/disables markdown auto-save for editor typing events."""
        self.autosave_enabled = bool(enabled)
        if not self.autosave_enabled:
            self._cancel_autosave_timer()

    def _cancel_autosave_timer(self):
        if self.autosave_timer:
            try:
                self.after_cancel(self.autosave_timer)
            except Exception:
                pass
            self.autosave_timer = None

    def _schedule_autosave(self):
        self._cancel_autosave_timer()
        self.autosave_timer = self.after(self.AUTOSAVE_DELAY_MS, self._on_autosave_timer)

    def _on_autosave_timer(self):
        self.autosave_timer = None
        if self.autosave_enabled:
            self._save_current_document(show_errors=False)

    def _on_undo_markdown_shortcut(self, event=None):
        if str(self.txt_content.cget("state")) != "normal":
            return "break"
        try:
            self.txt_content.edit_undo()
        except tk.TclError:
            return "break"
        self._on_content_change()
        return "break"

    def _on_redo_markdown_shortcut(self, event=None):
        if str(self.txt_content.cget("state")) != "normal":
            return "break"
        try:
            self.txt_content.edit_redo()
        except tk.TclError:
            return "break"
        self._on_content_change()
        return "break"

    def _on_new_doc(self):
        doc_dir = self._get_doc_root()
        if not doc_dir:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        selected_items = self.section_tree.selection()
        if not selected_items:
            messagebox.showwarning("Aviso", "Selecciona una carpeta o archivo para crear el documento.")
            return

        selected_path = selected_items[0]
        if os.path.isdir(selected_path):
            section_dir = selected_path
        else:
            section_dir = os.path.dirname(selected_path)
        suggestion = "documentacion.md"

        # Ask for filename
        filename = simpledialog.askstring("Nuevo Documento", "Nombre del archivo (.md):", initialvalue=suggestion)
        if not filename:
            return
        filename = filename.strip()
        if not filename:
            messagebox.showwarning("Aviso", "El nombre del documento no puede estar vacío.")
            return
        if self._has_path_separator(filename):
            messagebox.showwarning("Aviso", "El nombre del documento no puede contener separadores de ruta.")
            return
        if not filename.lower().endswith(".md"):
            filename += ".md"

        os.makedirs(section_dir, exist_ok=True)
        file_path = os.path.join(section_dir, filename)
        if os.path.exists(file_path):
            if not messagebox.askyesno("Confirmar", "El archivo ya existe. ¿Sobrescribir?"):
                return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {filename[:-3]}\n\n")

            self._refresh_sections(preferred_path=file_path)
            self._display_file_content(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear: {e}")

    def _get_documentation_prompts(self):
        """Returns the editable prompt definitions stored in the configuration."""
        if not self.controller or not hasattr(self.controller, "config_manager"):
            return []
        return self.controller.config_manager.get_documentation_prompts()

    def _open_prompt_builder(self):
        """Opens the prompt selector using the configured Documentation templates."""
        prompt_configs = self._get_documentation_prompts()
        if not prompt_configs:
            messagebox.showinfo(
                "Prompt",
                "No hay prompts configurados. Añade uno desde Opciones > Prompts.",
                parent=self.winfo_toplevel(),
            )
            return

        parent = self.winfo_toplevel()
        dialog = tk.Toplevel(parent)
        dialog.withdraw()
        dialog.title("Prompt")
        dialog.transient(parent)
        dialog.resizable(False, False)
        dialog.configure(bg=Styles.COLOR_BG_MAIN)

        prompt_index = {"value": 0}
        prompt_values = [{} for _ in prompt_configs]
        field_vars = {}

        style = ttk.Style(dialog)
        style.configure(
            "PromptCompact.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=(self.doc_sidebar_font_family, 14, "bold"),
            padding=(10, 6),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "PromptCompact.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)],
        )
        style.configure(
            "PromptCopy.TButton",
            background=Styles.COLOR_ACCENT,
            foreground="#ffffff",
            font=(self.doc_sidebar_font_family, 13, "bold"),
            padding=(20, 7),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "PromptCopy.TButton",
            background=[("active", Styles.COLOR_ACCENT_HOVER), ("pressed", Styles.COLOR_ACCENT)],
        )

        wrapper = tk.Frame(dialog, bg=Styles.COLOR_BG_MAIN)
        wrapper.pack(fill="both", expand=True, padx=16, pady=14)

        navigation = tk.Frame(wrapper, bg=Styles.COLOR_BG_SIDEBAR)
        navigation.pack(fill="x")
        navigation.columnconfigure(1, weight=1)

        title_var = tk.StringVar()
        btn_prev = ttk.Button(
            navigation,
            text="‹",
            style="PromptCompact.TButton",
            command=lambda: switch_prompt(-1),
            width=2,
        )
        btn_prev.grid(row=0, column=0, padx=(8, 4), pady=8)
        attach_tooltip(btn_prev, "Prompt anterior")
        title_label = tk.Label(
            navigation,
            textvariable=title_var,
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_FG_TEXT,
            font=(self.doc_sidebar_font_family, 16, "bold"),
        )
        title_label.grid(row=0, column=1, sticky="ew", pady=8)
        btn_next = ttk.Button(
            navigation,
            text="›",
            style="PromptCompact.TButton",
            command=lambda: switch_prompt(1),
            width=2,
        )
        btn_next.grid(row=0, column=2, padx=(4, 8), pady=8)
        attach_tooltip(btn_next, "Prompt siguiente")

        input_card = tk.Frame(wrapper, bg=Styles.COLOR_SIDEBAR_CARD_BG)
        input_card.pack(fill="x", pady=(10, 0))
        input_label_var = tk.StringVar()
        tk.Label(
            input_card,
            textvariable=input_label_var,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=(self.doc_sidebar_font_family, 11, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=10, pady=(8, 3))
        fields_frame = tk.Frame(input_card, bg=Styles.COLOR_SIDEBAR_CARD_BG)
        fields_frame.pack(fill="x", padx=10, pady=(0, 9))

        def refresh_input_fields():
            nonlocal field_vars
            config = prompt_configs[prompt_index["value"]]
            for child in fields_frame.winfo_children():
                child.destroy()
            field_vars = {}

            placeholders = []
            for match in re.finditer(r"\[(.*?)\]", config.get("template", "")):
                placeholder = match.group(1).strip()
                if placeholder not in placeholders:
                    placeholders.append(placeholder)

            if not placeholders:
                tk.Label(
                    fields_frame,
                    text="Este prompt no necesita datos adicionales.",
                    bg=Styles.COLOR_SIDEBAR_CARD_BG,
                    fg=Styles.COLOR_DIM,
                    font=(self.doc_sidebar_font_family, 10),
                    anchor="w",
                ).pack(fill="x", pady=(0, 2))
                return

            saved_values = prompt_values[prompt_index["value"]]
            for position, placeholder in enumerate(placeholders, start=1):
                row = tk.Frame(fields_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG)
                row.pack(fill="x", pady=(3 if position > 1 else 0, 0))
                value_var = tk.StringVar(value=saved_values.get(placeholder, ""))
                field_vars[placeholder] = value_var
                entry = tk.Entry(
                    row,
                    textvariable=value_var,
                    font=(self.doc_sidebar_font_family, 11),
                    bg=Styles.COLOR_INPUT_BG,
                    fg=Styles.COLOR_FG_TEXT,
                    insertbackground=Styles.COLOR_FG_TEXT,
                )
                entry.pack(fill="x", expand=True, ipady=4)
                Styles.soften_classic_widget(entry)

        def build_prompt_content():
            config = prompt_configs[prompt_index["value"]]
            values = {name: var.get() for name, var in field_vars.items()}

            def replace_placeholder(match):
                placeholder = match.group(1).strip()
                value = values.get(placeholder, "")
                return value if value.strip() else match.group(0)

            content = re.sub(r"\[(.*?)\]", replace_placeholder, config.get("template", ""))
            if config.get("include_file_path_instruction", True):
                content = ensure_file_path_comment_instruction(content)
            return content

        def show_copy_notice():
            notice = tk.Toplevel(dialog)
            notice.overrideredirect(True)
            notice.configure(bg="#263448")
            tk.Label(
                notice,
                text="Prompt copiado",
                bg="#263448",
                fg="#ffffff",
                font=(self.doc_sidebar_font_family, 9),
                padx=6,
                pady=3,
            ).pack()
            notice.update_idletasks()
            x = dialog.winfo_rootx() + (dialog.winfo_width() - notice.winfo_width()) // 2
            y = dialog.winfo_rooty() + dialog.winfo_height() + 6
            notice.geometry(f"+{x}+{y}")
            notice.after(1100, notice.destroy)

        def center_dialog():
            dialog.update_idletasks()
            width = max(dialog.winfo_reqwidth(), 520)
            height = max(dialog.winfo_reqheight(), 230)
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
            x = parent_x + max((parent_width - width) // 2, 0)
            y = parent_y + max((parent_height - height) // 2, 0)
            x = min(max(x, 0), max(screen_width - width, 0))
            y = min(max(y, 0), max(screen_height - height, 0))
            dialog.geometry(f"{width}x{height}+{x}+{y}")
            if not dialog.winfo_viewable():
                dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            dialog.grab_set()

        def copy_prompt():
            content = build_prompt_content().strip()
            try:
                copied = False
                if self.controller and hasattr(self.controller, "copy_to_clipboard"):
                    copied = bool(self.controller.copy_to_clipboard(content))
                if not copied:
                    dialog.clipboard_clear()
                    dialog.clipboard_append(content)
                    dialog.update()
                show_copy_notice()
            except Exception as exc:
                messagebox.showerror("Error", f"No se pudo copiar el prompt: {exc}", parent=dialog)

        def save_current_field_values():
            prompt_values[prompt_index["value"]] = {
                name: variable.get() for name, variable in field_vars.items()
            }

        ttk.Button(
            wrapper,
            text="Copiar",
            style="PromptCopy.TButton",
            command=copy_prompt,
        ).pack(pady=(14, 0))

        def sync_prompt_selector():
            config = prompt_configs[prompt_index["value"]]
            title_var.set(config.get("title", "(Sin título)"))
            dialog.title(config.get("title", "Prompt"))
            input_label_var.set(config.get("input_label", "Completa los datos del prompt"))
            refresh_input_fields()
            dialog.after_idle(center_dialog)

        def switch_prompt(delta):
            save_current_field_values()
            prompt_index["value"] = (prompt_index["value"] + delta) % len(prompt_configs)
            sync_prompt_selector()

        def on_prev_prompt(event=None):
            switch_prompt(-1)
            return "break"

        def on_next_prompt(event=None):
            switch_prompt(1)
            return "break"

        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.bind("<Control-Left>", on_prev_prompt)
        dialog.bind("<Control-Right>", on_next_prompt)
        dialog.bind("<Command-Left>", on_prev_prompt)
        dialog.bind("<Command-Right>", on_next_prompt)
        sync_prompt_selector()

    def _safe_open_prompt_builder(self):
        """Opens the prompt popup without allowing a UI exception to be silent."""
        try:
            self._open_prompt_builder()
        except Exception as exc:
            logging.exception("No se pudo abrir el popup de Prompt")
            messagebox.showerror("Prompt", f"No se pudo abrir el popup de Prompt: {exc}")

    def _display_message(self, message):

        self.txt_content.config(state="normal")
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", message)
        self.txt_content.config(state="disabled")
        #self.btn_copy_doc.state(["disabled"])

        # Determine Colors based on mode (or default to light for message)
        # We can respect the current mode
        if self.is_dark_mode:
            bg_color = "#0d1117"
            text_color = "#c9d1d9"
        else:
            bg_color = "#ffffff"
            text_color = "#24292f"

        # Load simple message into web view
        html = f"<html><body style='background-color:{bg_color}; color:{text_color}; font-family:{Styles.WEB_UI_FONT_STACK}; padding:20px; font-size:15px;'>{message}</body></html>"
        self.web_view.load_html(html)

    def _capture_web_view_scroll(self):
        """Returns the current vertical scroll fraction of the markdown preview."""
        try:
            yview = self.web_view.yview()
            if isinstance(yview, tuple) and yview:
                return float(yview[0])
        except Exception:
            pass
        return 0.0

    def _restore_web_view_scroll(self, position):
        """Restores the vertical scroll position of the markdown preview."""
        try:
            self.web_view.yview_moveto(position)
        except Exception:
            pass

    def _schedule_document_search_scroll(self):
        """Retries the search target after HtmlFrame layout and CSS settle."""
        self._document_search_scroll_token += 1
        token = self._document_search_scroll_token

        def scroll_to_match():
            if token != self._document_search_scroll_token:
                return
            try:
                html_widget = getattr(self.web_view, "_html", None)
                node = html_widget.search("[id='doc-search-match']") if html_widget else None
                if node:
                    self.web_view.yview(node)
            except Exception:
                pass

        for delay in (0, 80, 220, 420, 800, 1400):
            self.after(delay, scroll_to_match)

    def _on_web_view_done_loading(self, event=None):
        """Restores scroll once tkinterweb finishes loading the rendered markdown."""
        if self._pending_web_view_fragment is not None:
            self._pending_web_view_fragment = None
            self._pending_web_view_scroll = None
            self._schedule_document_search_scroll()
            return
        if self._pending_web_view_scroll is None:
            return
        position = self._pending_web_view_scroll
        self._pending_web_view_scroll = None
        self.after_idle(lambda pos=position: self._restore_web_view_scroll(pos))
        self.after(50, lambda pos=position: self._restore_web_view_scroll(pos))

    def _on_web_link_click(self, url):
        """Handles clicks inside the markdown viewer."""
        if url.startswith("edit://"):
            block_id = unquote(url.replace("edit://", "", 1)).strip()
            if block_id:
                self._open_markdown_block_editor(block_id)
            return

        if url.startswith("code://"):
            token = unquote(url.replace("code://", "", 1)).strip()
            if token:
                self._open_code_snippet(token)
            return

        try:
            webbrowser.open(url)
        except Exception:
            try:
                self.web_view.load_url(url)
            except Exception:
                pass

    def _on_markdown_selection_right_click(self, event=None):
        """Searches the currently selected Markdown text in the project code."""
        try:
            selected_text = self._get_markdown_search_selection()
        except Exception:
            selected_text = ""

        if not selected_text:
            return

        self._open_code_snippet(selected_text)
        return "break"

    def _get_markdown_search_selection(self):
        """Normalizes the HtmlFrame selection used for code search."""
        selected_text = ""

        try:
            selection_info = self.web_view.get_selection_position(return_elements=False)
        except Exception:
            selection_info = None

        if selection_info:
            try:
                page_text, start_idx, end_idx = selection_info
                selected_text = page_text[start_idx:end_idx]
            except Exception:
                selected_text = ""

        if not selected_text:
            selected_text = self.web_view.get_selection() or ""

        selected_text = selected_text.replace("\u00a0", " ").replace("\u200b", "").replace("\r", "")
        return selected_text.strip("\n")

    def _next_editable_block_id(self):
        self._editable_block_seq += 1
        return f"mdblock-{self._editable_block_seq}"

    def _anchor_id_for_line(self, start_line):
        return f"mdblock-line-{int(start_line)}"

    def _register_editable_block(self, token, block_kind, content, language_hint=""):
        """Stores the line range for a rendered Markdown block."""
        if not getattr(token, "map", None):
            return None

        start_line, end_line = token.map
        if start_line is None or end_line is None:
            return None

        lines = content.splitlines(keepends=True)
        block_text = "".join(lines[start_line:end_line])
        block_id = self._next_editable_block_id()
        self._editable_blocks[block_id] = {
            "start_line": int(start_line),
            "end_line": int(end_line),
            "kind": block_kind,
            "text": block_text,
            "display_text": token.content if block_kind == "bloque de código" else block_text,
            "language_hint": (language_hint or "").strip(),
            "token_type": getattr(token, "type", ""),
            "fence_markup": getattr(token, "markup", "") or "```",
            "fence_info": (getattr(token, "info", "") or "").strip(),
            "code_indent": self._detect_code_block_indent(block_text) if getattr(token, "type", "") == "code_block" else "",
            "anchor_id": self._anchor_id_for_line(start_line),
        }
        return block_id

    def _detect_code_block_indent(self, block_text):
        lines = block_text.splitlines()
        for line in lines:
            if line.strip():
                match = re.match(r"^[ \t]+", line)
                if match:
                    return match.group(0)
                break
        return "    "

    def _rebuild_code_block_markdown(self, block_info, edited_content):
        token_type = block_info.get("token_type", "")
        normalized = (edited_content or "").replace("\r", "")

        if token_type == "fence":
            fence_markup = block_info.get("fence_markup") or "```"
            fence_info = (block_info.get("fence_info") or "").strip()
            opening_line = f"{fence_markup} {fence_info}".rstrip()
            body = normalized
            if body and not body.endswith("\n"):
                body += "\n"
            return f"{opening_line}\n{body}{fence_markup}"

        if token_type == "code_block":
            indent = block_info.get("code_indent") or "    "
            if not normalized:
                return indent

            lines = normalized.splitlines(keepends=True)
            indented = "".join(f"{indent}{line}" for line in lines)
            if normalized and not normalized.endswith("\n"):
                return indented
            return indented

        return normalized

    def _build_edit_button_html(self, block_id):
        if not block_id:
            return ""
        return (
            f'<a class="edit-handle" href="edit://{quote(block_id, safe="")}" '
            f'title="Editar bloque">&#9998;</a>'
        )

    def _outdent_line_text(self, line_text, indent_unit=None):
        indent_unit = indent_unit or self.MARKDOWN_EDITOR_INDENT
        if line_text.startswith(indent_unit):
            return line_text[len(indent_unit):]
        if line_text.startswith("\t"):
            return line_text[1:]

        leading_spaces = len(line_text) - len(line_text.lstrip(" "))
        if leading_spaces <= 0:
            return line_text
        return line_text[min(leading_spaces, len(indent_unit)):]

    def _indent_block_editor_selection(self, widget, backwards=False, indent_unit=None):
        indent_unit = indent_unit or self.MARKDOWN_EDITOR_INDENT

        try:
            sel_start = widget.index("sel.first")
            sel_end = widget.index("sel.last")
            has_selection = True
        except tk.TclError:
            sel_start = widget.index("insert")
            sel_end = sel_start
            has_selection = False

        if has_selection:
            start_idx = widget.index(f"{sel_start} linestart")
            effective_end = sel_end
            if (
                widget.compare(sel_end, ">", sel_start)
                and widget.compare(widget.index(f"{sel_end} linestart"), "==", sel_end)
            ):
                effective_end = widget.index(f"{sel_end} -1c")
            end_idx = widget.index(f"{effective_end} lineend")
            original_text = widget.get(start_idx, end_idx)
            lines = original_text.split("\n")
            if backwards:
                updated_lines = [self._outdent_line_text(line, indent_unit) for line in lines]
            else:
                updated_lines = [f"{indent_unit}{line}" for line in lines]
            updated_text = "\n".join(updated_lines)

            widget.edit_separator()
            widget.delete(start_idx, end_idx)
            widget.insert(start_idx, updated_text)
            widget.tag_remove("sel", "1.0", tk.END)
            widget.tag_add("sel", start_idx, widget.index(f"{start_idx} + {len(updated_text)}c"))
            widget.mark_set("insert", start_idx)
            widget.see(start_idx)
            return "break"

        insert_idx = widget.index("insert")
        if backwards:
            line_start = widget.index(f"{insert_idx} linestart")
            line_end = widget.index(f"{insert_idx} lineend")
            line_text = widget.get(line_start, line_end)
            updated_line = self._outdent_line_text(line_text, indent_unit)
            if updated_line == line_text:
                return "break"
            widget.edit_separator()
            widget.delete(line_start, line_end)
            widget.insert(line_start, updated_line)

            try:
                line_no, col_no = map(int, insert_idx.split("."))
            except Exception:
                line_no, col_no = 1, 0
            removed = len(line_text) - len(updated_line)
            widget.mark_set("insert", f"{line_no}.{max(0, col_no - removed)}")
            widget.see("insert")
            return "break"

        widget.insert(insert_idx, indent_unit)
        widget.see("insert")
        return "break"

    def _replace_markdown_block(self, block_id, replacement_text):
        block_info = self._editable_blocks.get(block_id)
        if not block_info:
            messagebox.showwarning("Aviso", "No se pudo localizar el bloque para editar.")
            return

        content = self.txt_content.get("1.0", "end-1c")
        lines = content.splitlines(keepends=True)
        start_line = block_info["start_line"]
        end_line = block_info["end_line"]
        original_text = "".join(lines[start_line:end_line])

        replacement = replacement_text
        if block_info.get("kind") == "bloque de código":
            replacement = self._rebuild_code_block_markdown(block_info, replacement_text)
        if original_text.endswith(("\n", "\r")) and replacement and not replacement.endswith(("\n", "\r")):
            replacement += "\n"

        updated_content = "".join(lines[:start_line]) + replacement + "".join(lines[end_line:])
        self._pending_web_view_fragment = self._anchor_id_for_line(start_line)

        self.txt_content.config(state="normal")
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", updated_content)
        if self.current_file_path:
            try:
                with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}")
                return
        self._apply_markdown_rendering()

    def _open_markdown_block_editor(self, block_id):
        block_info = self._editable_blocks.get(block_id)
        if not block_info:
            messagebox.showwarning("Aviso", "No se pudo localizar el bloque para editar.")
            return

        is_code_block = block_info.get("kind") == "bloque de código"
        dialog = tk.Toplevel(self)
        dialog.title("Editar bloque Markdown")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        screen_width = max(dialog.winfo_screenwidth(), 1200)
        screen_height = max(dialog.winfo_screenheight(), 800)
        width = min(int(screen_width * 0.88), 1680)
        height = min(int(screen_height * 0.82), 1080)
        pos_x = max((screen_width - width) // 2, 0)
        pos_y = max((screen_height - height) // 2, 0)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.minsize(920, 620)
        dialog.configure(bg=Styles.COLOR_BG_MAIN)

        header = ttk.Frame(dialog, style="Main.TFrame")
        header.pack(fill="x", padx=18, pady=(18, 0))
        ttk.Label(
            header,
            text=f"Editar {block_info['kind']}",
            style="Header.TLabel"
        ).pack(fill="x")

        editor_frame = ttk.Frame(dialog, style="Main.TFrame")
        editor_frame.pack(fill="both", expand=True, padx=18, pady=18)

        if is_code_block:
            editor = arb_create_styled_text_widget(editor_frame)
            editor.configure(
                font=(self.code_font_family, self.code_font_size),
                padx=18,
                pady=16,
                borderwidth=0,
                highlightthickness=0,
                wrap="none"
            )
        else:
            editor = tk.Text(
                editor_frame,
                font=("Consolas", 12),
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_FG_TEXT,
                insertbackground=Styles.COLOR_FG_TEXT,
                relief="flat",
                wrap="word",
                padx=12,
                pady=12,
                undo=True
            )
        editor.pack(side="left", fill="both", expand=True)
        editor.insert("1.0", block_info.get("display_text", block_info.get("text", "")))

        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=editor.yview)
        scrollbar.pack(side="right", fill="y")
        editor.configure(yscrollcommand=scrollbar.set)

        highlight_job = {"id": None}

        def schedule_code_highlight(event=None):
            if not is_code_block:
                return
            if highlight_job["id"]:
                dialog.after_cancel(highlight_job["id"])
            highlight_job["id"] = dialog.after(180, apply_code_highlight)

        def apply_code_highlight():
            highlight_job["id"] = None
            if not is_code_block:
                return
            try:
                arb_highlight_syntax(editor, self._build_markdown_code_preview_path(block_info))
                self._normalize_text_widget_fonts(editor)
            except Exception:
                pass

        def indent_selection(event=None):
            result = self._indent_block_editor_selection(editor, backwards=False)
            if is_code_block:
                schedule_code_highlight()
            return result

        def outdent_selection(event=None):
            result = self._indent_block_editor_selection(editor, backwards=True)
            if is_code_block:
                schedule_code_highlight()
            return result

        if is_code_block:
            editor.edit_reset()
            editor.bind("<KeyRelease>", schedule_code_highlight, add="+")
            apply_code_highlight()

        editor.bind("<Tab>", indent_selection)
        editor.bind("<Shift-Tab>", outdent_selection)
        editor.bind("<ISO_Left_Tab>", outdent_selection)

        buttons = ttk.Frame(dialog, style="Main.TFrame")
        buttons.pack(fill="x", padx=18, pady=(0, 18))

        def save_changes(event=None):
            self._replace_markdown_block(block_id, editor.get("1.0", "end-1c"))
            dialog.destroy()
            return "break"

        btn_save_changes = ttk.Button(buttons, text="Guardar cambios", style="Action.TButton", command=save_changes)
        btn_save_changes.pack(side="right", padx=(8, 0))
        attach_tooltip(btn_save_changes, "Guardar cambios")

        btn_cancel_changes = ttk.Button(buttons, text="Cancelar", style="Secondary.TButton", command=dialog.destroy)
        btn_cancel_changes.pack(side="right")
        attach_tooltip(btn_cancel_changes, "Cancelar edición")

        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.bind("<Control-Return>", save_changes)
        dialog.bind("<Command-Return>", save_changes)
        editor.focus_set()

    def _ensure_code_panel_visible(self):
        if not self.is_code_panel_visible:
            try:
                self.content_pane.add(self.code_frame, minsize=260, stretch="never")
            except Exception:
                pass
            self.is_code_panel_visible = True
            self._set_code_sash()

    def _hide_code_panel(self):
        if not self._confirm_pending_code_changes():
            return
        if self.is_code_panel_visible:
            try:
                self.content_pane.forget(self.code_frame)
            except Exception:
                pass
            self.is_code_panel_visible = False

    def _set_code_sash(self):
        try:
            self.update_idletasks()
            total = self.content_pane.winfo_width()
            if total > 0 and self.is_code_panel_visible:
                left = int(total * self.code_sash_ratio)
                self.content_pane.sash_place(0, left, 0)
        except Exception:
            pass

    def _on_margin_change(self, value=None):
        return

    def _on_content_pane_release(self, event=None):
        if not self.is_code_panel_visible:
            return
        try:
            total = self.content_pane.winfo_width()
            if total <= 0:
                return
            x, _ = self.content_pane.sash_coord(0)
            ratio = x / total if total else self.code_sash_ratio
            ratio = max(0.2, min(0.9, ratio))
            if abs(ratio - self.code_sash_ratio) > 0.005:
                self.code_sash_ratio = ratio
                self._save_settings()
        except Exception:
            pass

    def _show_code_panel_message(self, message):
        self._ensure_code_panel_visible()
        self._set_active_code_context()
        self.code_text.config(state="normal")
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", message)
        self._normalize_code_text_fonts()
        self.code_text.edit_reset()
        self.code_text.edit_modified(False)
        self.code_text.config(state="disabled")

    def _format_code_reference(self, file_path):
        if not file_path:
            return ""

        path = os.path.abspath(file_path)
        project_root = None
        if self.controller and hasattr(self.controller, "project_manager"):
            project_root = getattr(self.controller.project_manager, "current_project_path", None)

        if project_root:
            try:
                if os.path.commonpath([path, project_root]) == os.path.abspath(project_root):
                    return os.path.relpath(path, project_root)
            except Exception:
                pass

        return path

    def _set_active_code_context(self, file_path=None, line_no=None, dirty=False):
        self._active_code_file_path = file_path
        self._active_code_line_no = line_no if file_path else None
        self._is_code_dirty = bool(dirty and file_path)

        if not file_path:
            self.lbl_code_file.config(text="Sin fichero seleccionado")
            self.btn_save_code.state(["disabled"])
            return

        reference = self._format_code_reference(file_path)
        line_suffix = f" · línea {line_no}" if line_no else ""
        dirty_prefix = "* " if self._is_code_dirty else ""
        self.lbl_code_file.config(text=f"{dirty_prefix}{reference}{line_suffix}")
        self.btn_save_code.state(["!disabled"])

    def _sync_project_file_cache(self, file_path, content):
        if not self.controller or not hasattr(self.controller, "project_manager"):
            return

        project_manager = self.controller.project_manager
        normalized_target = os.path.normpath(os.path.abspath(file_path))

        for file_data in project_manager.get_files():
            if os.path.normpath(os.path.abspath(file_data.get("path", ""))) == normalized_target:
                file_data["content"] = content
                return

        project_root = getattr(project_manager, "current_project_path", None)
        if not project_root:
            return

        try:
            project_root = os.path.abspath(project_root)
            if os.path.commonpath([normalized_target, project_root]) != project_root:
                return
            rel_path = os.path.relpath(normalized_target, project_root)
        except Exception:
            return

        project_manager.files.append({
            "path": normalized_target,
            "rel_path": rel_path,
            "content": content,
        })

    def _schedule_code_highlight(self):
        if self._code_highlight_job:
            self.after_cancel(self._code_highlight_job)
        self._code_highlight_job = self.after(250, self._apply_code_highlight)

    def _apply_code_highlight(self):
        self._code_highlight_job = None
        if not self._active_code_file_path:
            return
        try:
            arb_highlight_syntax(self.code_text, self._active_code_file_path)
            self._normalize_code_text_fonts()
        except Exception:
            pass

    def _on_code_text_modified(self, event=None):
        try:
            modified = self.code_text.edit_modified()
        except Exception:
            return

        if not modified:
            return

        if self._active_code_file_path:
            self._set_active_code_context(
                self._active_code_file_path,
                self._active_code_line_no,
                dirty=True
            )
            self._schedule_code_highlight()

        try:
            self.code_text.edit_modified(False)
        except Exception:
            pass

    def _save_active_code_file(self):
        if not self._active_code_file_path:
            return False

        try:
            content = self.code_text.get("1.0", "end-1c")
            with open(self._active_code_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._sync_project_file_cache(self._active_code_file_path, content)
            self.code_text.edit_modified(False)
            self._set_active_code_context(
                self._active_code_file_path,
                self._active_code_line_no,
                dirty=False
            )
            logging.info(f"DocView: Guardado fichero fuente {self._active_code_file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el fichero fuente: {e}")
            return False

    def _confirm_pending_code_changes(self):
        if not self._active_code_file_path or not self._is_code_dirty:
            return True

        filename = os.path.basename(self._active_code_file_path)
        response = messagebox.askyesnocancel(
            "Guardar cambios",
            f"Hay cambios sin guardar en '{filename}'. ¿Quieres guardarlos antes de continuar?"
        )
        if response is None:
            return False
        if response:
            return self._save_active_code_file()
        return True

    def _on_save_code_shortcut(self, event=None):
        self._save_active_code_file()
        return "break"

    def _on_undo_code_shortcut(self, event=None):
        if str(self.code_text.cget("state")) != "normal":
            return "break"
        try:
            self.code_text.edit_undo()
        except tk.TclError:
            return "break"
        self._schedule_code_highlight()
        return "break"

    def _on_redo_code_shortcut(self, event=None):
        if str(self.code_text.cget("state")) != "normal":
            return "break"
        try:
            self.code_text.edit_redo()
        except tk.TclError:
            return "break"
        self._schedule_code_highlight()
        return "break"

    def _clear_code_match_highlight(self, event=None):
        """Removes the temporary yellow highlight when the user interacts with the code panel."""
        try:
            self.code_text.tag_remove("match_highlight", "1.0", tk.END)
        except Exception:
            pass

    def _center_code_match(self, match_index):
        """Scrolls the code viewer so the selected match sits near the vertical center."""
        try:
            self.code_text.update_idletasks()

            line_no = int(str(match_index).split(".", 1)[0])
            total_lines = max(int(self.code_text.index("end-1c").split(".", 1)[0]), 1)

            line_info = self.code_text.dlineinfo(match_index)
            if line_info:
                line_height = max(int(line_info[3]), 1)
            else:
                line_height = 20

            widget_height = max(self.code_text.winfo_height(), line_height)
            visible_lines = max(widget_height // line_height, 1)
            top_line = max(1, line_no - (visible_lines // 2))

            if total_lines <= visible_lines:
                self.code_text.yview_moveto(0.0)
                return

            max_top_line = max(1, total_lines - visible_lines + 1)
            top_line = min(top_line, max_top_line)
            self.code_text.yview_moveto((top_line - 1) / max(total_lines - 1, 1))
        except Exception:
            try:
                self.code_text.see(match_index)
            except Exception:
                pass

    def _open_code_snippet(self, token):
        self._last_code_token = token
        if not self._confirm_pending_code_changes():
            return

        result = self._find_code_match(token)
        if not result:
            self._show_code_panel_message(f"No se encontró \"{token}\" en el proyecto.")
            return

        file_path = result["file_path"]
        line_no = result["line_no"]
        file_content = result["content"]
        match_start = result["match_start"]
        match_end = result["match_end"]
        self._ensure_code_panel_visible()

        self.code_text.config(state="normal")
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", file_content)
        arb_highlight_syntax(self.code_text, file_path)
        self._normalize_code_text_fonts()
        self.code_text.edit_reset()
        self.code_text.edit_modified(False)
        self._set_active_code_context(file_path, line_no, dirty=False)

        self.code_text.tag_remove("match_highlight", "1.0", tk.END)
        first_match_idx = None
        try:
            start_idx = self._idx_to_tk(match_start, self.code_text)
            end_idx = self._idx_to_tk(match_end, self.code_text)
            self.code_text.tag_add("match_highlight", start_idx, end_idx)
            first_match_idx = start_idx
        except Exception:
            first_match_idx = None
        self.code_text.tag_lower("match_highlight")
        if first_match_idx:
            self.after_idle(lambda match_idx=first_match_idx: self._center_code_match(match_idx))
        self.code_text.focus_set()

    def _normalize_text_widget_fonts(self, widget):
        try:
            widget.configure(font=(self.code_font_family, self.code_font_size))
        except Exception:
            return

        for tag_name in widget.tag_names():
            try:
                current_font = widget.tag_cget(tag_name, "font")
            except Exception:
                continue

            if not current_font:
                continue

            try:
                tag_font = tkfont.Font(font=current_font)
                weight = tag_font.cget("weight")
                slant = tag_font.cget("slant")
                style_parts = []
                if weight == "bold":
                    style_parts.append("bold")
                if slant == "italic":
                    style_parts.append("italic")
                font_spec = (self.code_font_family, self.code_font_size)
                if style_parts:
                    font_spec = (self.code_font_family, self.code_font_size, " ".join(style_parts))
                widget.tag_configure(
                    tag_name,
                    font=font_spec
                )
            except Exception:
                continue

    def _normalize_code_text_fonts(self):
        self._normalize_text_widget_fonts(self.code_text)

    def _build_markdown_code_preview_path(self, block_info):
        language_hint = (block_info.get("language_hint") or "").strip().lower()
        extension_map = {
            "py": ".py",
            "python": ".py",
            "js": ".js",
            "javascript": ".js",
            "jsx": ".jsx",
            "ts": ".ts",
            "typescript": ".ts",
            "tsx": ".tsx",
            "html": ".html",
            "css": ".css",
            "scss": ".scss",
            "sass": ".sass",
            "json": ".json",
            "sql": ".sql",
            "sh": ".sh",
            "bash": ".sh",
            "zsh": ".zsh",
            "md": ".md",
            "markdown": ".md",
            "xml": ".xml",
            "yaml": ".yml",
            "yml": ".yml",
            "php": ".php",
            "java": ".java",
            "c": ".c",
            "cpp": ".cpp",
            "csharp": ".cs",
            "cs": ".cs",
            "go": ".go",
            "rs": ".rs",
            "rust": ".rs",
        }
        extension = extension_map.get(language_hint, ".txt")
        return f"markdown_block{extension}"

    def _find_code_match(self, token):
        token = (token or "").replace("\r", "").strip("\n")
        if not token:
            return None
        deadline = time.monotonic() + 7.0

        def build_result(path, content, idx, end_idx, nocase):
            line_no = content.count("\n", 0, idx) + 1
            return {
                "file_path": path,
                "line_no": line_no,
                "content": content,
                "nocase": nocase,
                "match_start": idx,
                "match_end": end_idx,
            }

        def find_in_content(path, content):
            if time.monotonic() > deadline:
                return None
            idx = content.find(token)
            if idx != -1:
                return build_result(path, content, idx, idx + len(token), False)
            return None

        # Prefer ProjectManager cache (correct root even if cwd changes)
        if self.controller and hasattr(self.controller, "project_manager"):
            files = self.controller.project_manager.get_files()
            for f in files:
                if time.monotonic() > deadline:
                    return None
                content = f.get("content") or ""
                try:
                    with open(f["path"], "r", encoding="utf-8", errors="ignore") as file_obj:
                        content = file_obj.read()
                except Exception:
                    pass
                result = find_in_content(f["path"], content)
                if result:
                    return result

        # Fallback: scan filesystem from current project or cwd
        root = os.path.abspath(os.getcwd())
        include_exts = {
            ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
            ".cs", ".vb", ".fs", ".fsx",
            ".go", ".rs", ".zig",
            ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
            ".swift", ".m", ".mm",
            ".py", ".pyw", ".rb", ".php", ".phtml",
            ".pl", ".pm", ".lua", ".r", ".jl", ".dart",
            ".ex", ".exs", ".erl", ".hrl",
            ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
            ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
            ".vue", ".svelte", ".astro",
            ".ejs", ".hbs", ".handlebars", ".mustache", ".njk", ".twig", ".jinja", ".jinja2", ".tpl",
            ".sql", ".graphql", ".gql", ".proto",
            ".json", ".jsonc", ".xml", ".xsd", ".xsl", ".wsdl",
            ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".properties",
            ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1", ".psm1", ".psd1",
            ".dockerignore", ".editorconfig"
        }
        include_filenames = {
            "Dockerfile", "Containerfile", "Makefile", "CMakeLists.txt",
            "Jenkinsfile", "Procfile", "Rakefile", "Gemfile", "Podfile",
            "Brewfile", "Vagrantfile"
        }
        if self.controller and hasattr(self.controller, "project_manager"):
            pm = self.controller.project_manager
            if getattr(pm, "current_project_path", None):
                root = pm.current_project_path
            if getattr(pm, "CODE_EXTENSIONS", None):
                include_exts = set(pm.CODE_EXTENSIONS)
            if getattr(pm, "CODE_FILENAMES", None):
                include_filenames = set(pm.CODE_FILENAMES)

        skip_dirs = {
            ".git", "__pycache__", ".venv", "venv", "node_modules", "dist",
            "build", ".idea", ".vscode"
        }

        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() > deadline:
                return None
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if time.monotonic() > deadline:
                    return None
                if os.path.splitext(fname)[1].lower() not in include_exts and fname not in include_filenames:
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                result = find_in_content(path, content)
                if result:
                    return result

        return None

    def _on_section_click(self, event):
        """Handle clicks on the section tree. Deselect if clicked on empty space."""
        iid = self.section_tree.identify_row(event.y)
        if not iid:
            # Clicked on empty space - deselect
            self._advanced_doc_search_scope = None
            selected = self.section_tree.selection()
            if selected:
                self.section_tree.selection_remove(*selected)
            return "break"

    def _show_context_menu(self, event):
        """Shows the context menu on right click."""
        try:
            iid = self.section_tree.identify_row(event.y)
            if iid:
                # Clicked on an item - select it and show menu
                if iid not in self.section_tree.selection():
                    self.section_tree.selection_set(iid)
                try:
                    self.context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    self.context_menu.grab_release()
            else:
                # Clicked on empty space - clear selection and show menu (for adding new)
                self.section_tree.selection_remove(*self.section_tree.selection())
                try:
                    self.context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    self.context_menu.grab_release()
        except Exception as e:
            logging.error(f"Error showing documentation context menu: {e}")

    def _on_add_section(self):
        doc_root = self._get_doc_root()
        if not doc_root:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        # Try to get selected folder as parent
        selected = self.section_tree.selection()
        parent_dir = doc_root
        if selected:
            path = selected[0]
            if os.path.isdir(path):
                parent_dir = path
            else:
                parent_dir = os.path.dirname(path)

        section_name = simpledialog.askstring("Nueva Carpeta", "Nombre de la nueva carpeta:")
        if not section_name:
            return
        section_name = section_name.strip()
        if not section_name or self._has_path_separator(section_name):
            messagebox.showwarning("Aviso", "Nombre inválido.")
            return

        section_dir = os.path.join(parent_dir, section_name)
        if os.path.exists(section_dir):
            messagebox.showwarning("Aviso", "Ya existe.")
            return

        try:
            os.makedirs(section_dir, exist_ok=False)
            self._refresh_sections(preferred_path=section_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear: {e}")

    def _on_edit_section(self):
        selected = self.section_tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona una carpeta o archivo para editar.")
            return

        old_path = selected[0]
        old_name = os.path.basename(old_path)
        base_tag = "folder" if os.path.isdir(old_path) else (
            "md" if os.path.splitext(old_name)[1].lower() == ".md" else "document"
        )
        color = self._section_colors.get(
            self._section_color_key(old_path),
            self._default_section_color(old_path, base_tag)
        )

        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title("Editar sección")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        dialog.configure(bg=Styles.COLOR_BG_SIDEBAR)

        dialog_style = ttk.Style(dialog)
        dialog_style.configure(
            "DocEdit.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=(self.doc_sidebar_font_family, 12, "bold"),
            padding=(9, 5),
            borderwidth=0,
            relief="flat"
        )
        dialog_style.map(
            "DocEdit.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )
        dialog_style.configure(
            "DocEditPrimary.TButton",
            background=Styles.COLOR_ACCENT,
            foreground="#ffffff",
            font=(self.doc_sidebar_font_family, 12, "bold"),
            padding=(10, 5),
            borderwidth=0,
            relief="flat"
        )
        dialog_style.map(
            "DocEditPrimary.TButton",
            background=[("active", Styles.COLOR_ACCENT_HOVER), ("pressed", Styles.COLOR_ACCENT)]
        )

        body = tk.Frame(dialog, bg=Styles.COLOR_BG_SIDEBAR)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(
            body,
            text="Nombre:",
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_FG_TEXT,
            anchor="w"
        ).pack(fill="x")
        name_entry = tk.Entry(
            body,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            width=32
        )
        name_entry.pack(fill="x", pady=(4, 14), ipady=5)
        name_entry.insert(0, old_name)

        color_row = tk.Frame(body, bg=Styles.COLOR_BG_SIDEBAR)
        color_row.pack(fill="x")
        tk.Label(
            color_row,
            text="Color del título:",
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_FG_TEXT
        ).pack(side="left")
        color_preview = tk.Label(
            color_row,
            text=color,
            bg=color,
            fg="#ffffff",
            width=10,
            padx=8,
            pady=5,
            cursor="hand2"
        )
        color_preview.pack(side="right", padx=(8, 0))

        def copy_color_to_clipboard(event=None):
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(color)
                dialog.update()
            except tk.TclError:
                return

            notice = tk.Toplevel(dialog)
            notice.overrideredirect(True)
            notice.configure(bg="#263448")
            tk.Label(
                notice,
                text="Color copiado",
                bg="#263448",
                fg="#ffffff",
                font=(self.doc_sidebar_font_family, 9),
                padx=5,
                pady=2
            ).pack()
            notice.update_idletasks()
            x = (event.x_root + 8) if event else dialog.winfo_rootx() + 8
            y = (event.y_root + 8) if event else dialog.winfo_rooty() + 8
            notice.geometry(f"+{x}+{y}")
            notice.after(1100, notice.destroy)

        color_preview.bind("<Double-Button-1>", copy_color_to_clipboard)

        color_button = ttk.Button(
            color_row,
            text="Elegir color",
            style="DocEdit.TButton"
        )
        color_button.pack(side="right")

        def choose_color():
            nonlocal color
            chosen = colorchooser.askcolor(color=color, parent=dialog, title="Color del título")
            if chosen and chosen[1]:
                color = chosen[1]
                color_preview.configure(text=color, bg=color)

        color_button.configure(command=choose_color)

        buttons = tk.Frame(body, bg=Styles.COLOR_BG_SIDEBAR)
        buttons.pack(fill="x", pady=(18, 0))

        def cancel():
            dialog.destroy()

        def save():
            new_name = name_entry.get().strip()
            if not new_name or self._has_path_separator(new_name):
                messagebox.showwarning("Aviso", "Nombre inválido.", parent=dialog)
                return

            new_path = os.path.join(os.path.dirname(old_path), new_name)
            if new_path != old_path and os.path.exists(new_path):
                messagebox.showwarning("Aviso", "Ya existe.", parent=dialog)
                return

            try:
                if new_path != old_path:
                    os.rename(old_path, new_path)
                    self._section_colors.pop(self._section_color_key(old_path), None)
                self._section_colors[self._section_color_key(new_path)] = color
                self._save_section_colors()
                dialog.destroy()
                self._refresh_sections(preferred_path=new_path)
            except Exception as exc:
                messagebox.showerror("Error", f"No se pudo editar: {exc}", parent=dialog)

        ttk.Button(
            buttons,
            text="Cancelar",
            command=cancel,
            style="DocEdit.TButton"
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            buttons,
            text="Guardar",
            command=save,
            style="DocEditPrimary.TButton"
        ).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.grab_set()
        name_entry.focus_set()
        name_entry.selection_range(0, tk.END)
        dialog.wait_window()

    def _on_delete_section(self):
        selected = [path for path in self.section_tree.selection() if os.path.exists(path)]
        if not selected:
            return

        # Si se selecciona una carpeta y también alguno de sus hijos, solo se
        # elimina la carpeta para evitar intentar borrar dos veces el mismo
        # contenido.
        selected.sort(key=lambda path: (len(os.path.normpath(path)), os.path.normcase(path)))
        paths = []
        for path in selected:
            normalized_path = os.path.normpath(path)
            if any(
                os.path.isdir(parent_path)
                and normalized_path != parent_path
                and os.path.commonpath((normalized_path, parent_path)) == parent_path
                for parent_path in paths
            ):
                continue
            paths.append(normalized_path)

        confirm = messagebox.askyesno(
            "Eliminar secciones",
            (
                f"¿Estás seguro de que quieres eliminar estas {len(paths)} secciones?\n\n"
                + "\n".join(f"• {os.path.basename(path)}" for path in paths[:12])
                + ("\n…" if len(paths) > 12 else "")
            ) if len(paths) > 1 else
            f"¿Estás seguro de que quieres eliminar '{os.path.basename(paths[0])}'?"
        )
        if not confirm:
            return

        try:
            for path in paths:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

            current_deleted = self.current_file_path and any(
                self.current_file_path == path
                or (
                    os.path.isdir(path)
                    and os.path.commonpath((os.path.normpath(self.current_file_path), path)) == path
                )
                for path in paths
            )
            if current_deleted:
                self.current_file_path = None
                self._display_message("Documento eliminado.")

            # Elimina también los colores asociados a rutas que ya no existen.
            self._section_colors = {
                key: color for key, color in self._section_colors.items()
                if os.path.exists(os.path.join(self._get_doc_root(), key))
            }
            self._save_section_colors()
            self._refresh_sections()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron eliminar las secciones: {e}")

    def _on_delete_section_shortcut(self, event=None):
        selected = self.section_tree.selection()
        if not selected:
            return "break"
        self._on_delete_section()
        return "break"

    def _refresh_sections(self, preferred_path=None):
        self._refresh_doc_path_history()
        
        # Clear existing
        try:
            for item in self.section_tree.get_children():
                self.section_tree.delete(item)
        except Exception:
            pass
            
        doc_root = self._get_doc_root()
        project_root = self._get_project_root() if self.list_project_documents_var.get() else None
        if not doc_root and not project_root:
            return

        self.section_tree.configure(
            height=(
                self.DOC_SECTIONS_EXPANDED_VISIBLE_ROWS
                if self._show_all_doc_sections
                else self.DOC_SECTIONS_INITIAL_LIMIT
            )
        )
        self._load_section_colors(doc_root)
        self._tree_root_items_added = 0
        self._tree_inserted_paths = set()
        documentation_exts = {'.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.png', '.jpg', '.jpeg'}
        if doc_root:
            self._build_tree(
                doc_root,
                "",
                supported_exts=documentation_exts,
                project_documents_only=False
            )
        if project_root and os.path.normcase(project_root) != os.path.normcase(doc_root or ""):
            self._build_tree(
                project_root,
                "",
                supported_exts=self._project_document_extensions(),
                project_documents_only=True
            )
        self._update_show_more_sections(doc_root, project_root)
        
        if self._preserve_section_selection and not preferred_path:
            if not self.current_file_path and self.controller and hasattr(self.controller, "config_manager"):
                preferred_path = self.controller.config_manager.get_last_doc_file()
            else:
                preferred_path = self.current_file_path
                
        if self._preserve_section_selection and preferred_path and self.section_tree.exists(preferred_path):
            self.section_tree.selection_set(preferred_path)
            self.section_tree.see(preferred_path)
            if not self.current_file_path and os.path.isfile(preferred_path):
                self._on_section_select()

    def _build_tree(self, root_path, parent_id, supported_exts=None, project_documents_only=None):
        """Recursively builds the Treeview structure."""
        try:
            if not os.path.isdir(root_path): return
            if supported_exts is None:
                supported_exts = {'.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.png', '.jpg', '.jpeg'}
            project_mode = (
                bool(self.list_project_documents_var.get())
                if project_documents_only is None else bool(project_documents_only)
            )
            items = []
            for name in os.listdir(root_path):
                full_path = os.path.join(root_path, name)
                if os.path.isdir(full_path):
                    if not project_mode or self._project_directory_has_documents(full_path):
                        items.append(name)
                elif os.path.splitext(name)[1].lower() in supported_exts:
                    items.append(name)

            # En macOS st_birthtime representa la creación real. En otros
            # sistemas se usa ctime y, como último recurso, mtime.
            items.sort(key=lambda name: self._doc_creation_sort_key(os.path.join(root_path, name)))

            # La paginación solo afecta a las secciones de primer nivel; el
            # contenido de cada carpeta se construye completo al desplegarla.
            if not parent_id and not self._show_all_doc_sections and not self._get_doc_search_query():
                remaining = max(self.DOC_SECTIONS_INITIAL_LIMIT - self._tree_root_items_added, 0)
                items = items[:remaining]
                self._tree_root_items_added += len(items)
            
            query = self._get_doc_search_query()
            advanced_search_enabled = bool(self.advanced_doc_search_var.get())

            for name in items:
                full_path = os.path.join(root_path, name)
                is_dir = os.path.isdir(full_path)

                if full_path in self._tree_inserted_paths:
                    continue
                
                ext = os.path.splitext(name)[1].lower()
                if is_dir:
                    # Create node
                    node_id = full_path

                    color_tag = self._configure_section_color_tag(full_path, "folder")
                    self.section_tree.insert(parent_id, "end", iid=node_id, text=f"{name}", tags=(color_tag,), open=bool(query))
                    self._tree_inserted_paths.add(full_path)
                    self._build_tree(full_path, node_id, supported_exts, project_documents_only)
                    
                    if query:
                        if advanced_search_enabled:
                            if not self.section_tree.get_children(node_id):
                                self.section_tree.delete(node_id)
                        elif query not in name.lower() and not self.section_tree.get_children(node_id):
                            self.section_tree.delete(node_id)
                else:
                    include_file = False
                    if not query:
                        include_file = True
                    elif advanced_search_enabled:
                        include_file = self._matches_advanced_doc_query(full_path, name, ext, query)
                    else:
                        include_file = query in name.lower()

                    if include_file:
                        tag = "md" if ext == ".md" else "document"
                        color_tag = self._configure_section_color_tag(full_path, tag)
                        self.section_tree.insert(parent_id, "end", iid=full_path, text=f"{name}", tags=(color_tag,))
                        self._tree_inserted_paths.add(full_path)
        except Exception as e:
            logging.error(f"Error building tree for {root_path}: {e}")

    @staticmethod
    def _doc_creation_sort_key(path):
        """Returns a stable creation-time key for files and folders."""
        try:
            stat = os.stat(path)
            creation_time = getattr(stat, "st_birthtime", None)
            if creation_time is None:
                creation_time = getattr(stat, "st_ctime", None)
            if creation_time is None:
                creation_time = stat.st_mtime
            return (float(creation_time), os.path.basename(path).casefold())
        except OSError:
            return (float("inf"), os.path.basename(path).casefold())

    def _section_colors_path(self, doc_root):
        return os.path.join(doc_root, ".section_colors.json")

    def _load_section_colors(self, doc_root):
        self._section_colors = {}
        if not doc_root:
            return
        try:
            with open(self._section_colors_path(doc_root), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._section_colors = {
                    str(path): str(color)
                    for path, color in data.items()
                    if isinstance(color, str) and color.startswith("#")
                }
        except (OSError, json.JSONDecodeError):
            pass

    def _save_section_colors(self):
        doc_root = self._get_doc_root()
        if not doc_root:
            return
        try:
            with open(self._section_colors_path(doc_root), "w", encoding="utf-8") as fh:
                json.dump(self._section_colors, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logging.warning("No se pudieron guardar los colores de las secciones: %s", exc)

    def _section_color_key(self, path):
        doc_root = self._get_doc_root()
        if not doc_root:
            return os.path.normpath(path)
        try:
            return os.path.relpath(path, doc_root)
        except ValueError:
            return os.path.normpath(path)

    def _default_section_color(self, path, base_tag):
        if base_tag == "folder":
            return Styles.COLOR_ACCENT
        if base_tag == "document":
            return Styles.COLOR_DIM
        return Styles.COLOR_FG_TEXT

    def _configure_section_color_tag(self, path, base_tag):
        color = self._section_colors.get(self._section_color_key(path))
        if not color:
            color = self._default_section_color(path, base_tag)
        tag = f"section_color_{abs(hash(os.path.normcase(path)))}"
        font = (self.doc_sidebar_font_family, 16, "bold") if base_tag == "folder" else (
            self.doc_sidebar_font_family, 14
        )
        self.section_tree.tag_configure(tag, foreground=color, font=font)
        return tag

    def _update_show_more_sections(self, doc_root, project_root=None):
        """Updates the visibility of the textual root-list expansion control."""
        if not hasattr(self, "btn_show_more_sections") or not hasattr(self, "section_scrollbar"):
            return

        try:
            root_entries = []
            documentation_exts = {'.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.png', '.jpg', '.jpeg'}

            def collect_root_entries(root_path, supported_exts, project_documents_only=False):
                if not root_path or not os.path.isdir(root_path):
                    return
                for name in os.listdir(root_path):
                    path = os.path.join(root_path, name)
                    if os.path.isdir(path):
                        if not project_documents_only or self._project_directory_has_documents(path):
                            root_entries.append(os.path.normcase(path))
                    elif os.path.splitext(name)[1].lower() in supported_exts:
                        root_entries.append(os.path.normcase(path))

            collect_root_entries(doc_root, documentation_exts)
            if project_root and os.path.normcase(project_root) != os.path.normcase(doc_root or ""):
                collect_root_entries(project_root, self._project_document_extensions(), True)
            has_more = (
                not self._show_all_doc_sections
                and not self._get_doc_search_query()
                and len(set(root_entries)) > self.DOC_SECTIONS_INITIAL_LIMIT
            )
        except OSError:
            has_more = False

        if has_more or self._show_all_doc_sections:
            self.section_scrollbar.pack(side="right", fill="y", pady=5)
        else:
            self.section_scrollbar.pack_forget()

        if has_more:
            self.btn_show_more_sections.pack(fill="x", padx=5, pady=(0, 2))
        else:
            self.btn_show_more_sections.pack_forget()

    def _show_all_sections(self, event=None):
        self._show_all_doc_sections = True
        self._refresh_sections()

    def _refresh_doc_path_history(self):
        self.doc_path_options = {}
        values = [self.NO_DOCUMENTATION_PATH_LABEL]
        if self.controller and hasattr(self.controller, "get_existing_doc_directories"):
            for path in self.controller.get_existing_doc_directories():
                label = self._format_doc_path_option(path)
                self.doc_path_options[label] = path
                values.append(label)

        self.cmb_doc_paths.config(values=values)

        current_path = self._get_doc_root()
        if current_path:
            current_label = self._format_doc_path_option(current_path)
            if current_label not in self.doc_path_options:
                self.doc_path_options[current_label] = current_path
                values.insert(0, current_label)
                self.cmb_doc_paths.config(values=values)
            self.cmb_doc_paths.set(current_label)
        elif values:
            self.cmb_doc_paths.set(self.NO_DOCUMENTATION_PATH_LABEL)
        else:
            self.cmb_doc_paths.set("")

    def _format_doc_path_option(self, path):
        path = os.path.normpath(path)
        base_name = os.path.basename(path) or path
        return f"{base_name}  ·  {path}"

    def _apply_section_filter(self, preferred_section=None, force_reload=False):
        """Filtering is now integrated into _refresh_sections."""
        self._refresh_sections()

    def _toggle_mode(self):
        """Toggles between Editor and Viewer modes."""
        self.is_editor_mode = not self.is_editor_mode
        self._save_settings()
        self._update_view_mode()

    def _update_view_mode(self):
        """Updates the visible frame based on mode."""
        if self.is_editor_mode:
            # Show Editor
            self.preview_frame.pack_forget()
            self.editor_frame.pack(fill="both", expand=True)
            self.btn_mode.config(image=self.icons.get("view"))
            # If switching to editor, we might want to ensure content is fresh? 
            # Usually txt_content is the source of truth, so it's fine.
        else:
            # Show Viewer
            self.editor_frame.pack_forget()
            self.preview_frame.pack(fill="both", expand=True)
            self.btn_mode.config(image=self.icons.get("edit"))
            # Refresh render when entering view mode
            self._apply_markdown_rendering()

    def _toggle_theme(self):
        """Toggles between Dark and Light theme for the Viewer."""
        self.is_dark_mode = not self.is_dark_mode
        self._save_settings()
        self.btn_theme.config(image=self.icons.get("sun") if self.is_dark_mode else self.icons.get("moon"))
        self._apply_markdown_rendering()

    def _toggle_sidebar(self):
        """Shows or hides the right-side sections panel."""
        if self.is_fullscreen_mode:
            return

        if self.is_right_panel_visible:
            try:
                self.paned_window.forget(self.right_frame)
            except Exception:
                pass
            self.is_right_panel_visible = False
        else:
            try:
                self.paned_window.add(self.right_frame, minsize=self.DEFAULT_SECTIONS_PANEL_WIDTH, stretch="never")
            except Exception:
                pass
            self.is_right_panel_visible = True
            self.after_idle(self._set_default_sections_panel_width)

        self._update_sidebar_toggle()

    def _update_sidebar_toggle(self):
        if self.is_fullscreen_mode:
            self.btn_toggle_sidebar.place_forget()
        else:
            self._schedule_sidebar_toggle_position()

        if self.is_right_panel_visible:
            self.btn_toggle_sidebar.config(text=">")
        else:
            self.btn_toggle_sidebar.config(text="<")

    def _update_fullscreen_button(self):
        self.btn_toggle_fullscreen.config(
            image=self.icons.get("fullscreen_exit") if self.is_fullscreen_mode else self.icons.get("fullscreen_enter"),
            text=""
        )

    def _toggle_fullscreen_mode(self):
        self.is_fullscreen_mode = not self.is_fullscreen_mode
        self._apply_fullscreen_mode()
        self._save_settings()

    def _apply_fullscreen_mode(self):
        main_layout = self._get_main_layout()

        if self.is_fullscreen_mode:
            self._sidebar_visible_before_fullscreen = self.is_right_panel_visible
            if self.is_right_panel_visible:
                try:
                    self.paned_window.forget(self.right_frame)
                except Exception:
                    pass
                self.is_right_panel_visible = False
            if main_layout and self.winfo_manager():
                main_layout.set_navbar_visible(False)
        else:
            if self._sidebar_visible_before_fullscreen and not self.is_right_panel_visible:
                try:
                    self.paned_window.add(self.right_frame, minsize=self.DEFAULT_SECTIONS_PANEL_WIDTH, stretch="never")
                except Exception:
                    pass
                self.is_right_panel_visible = True
                self.after_idle(self._set_default_sections_panel_width)
            elif not self._sidebar_visible_before_fullscreen and self.is_right_panel_visible:
                try:
                    self.paned_window.forget(self.right_frame)
                except Exception:
                    pass
                self.is_right_panel_visible = False

            if main_layout:
                main_layout.set_navbar_visible(True)

        self._update_sidebar_toggle()
        self._update_fullscreen_button()
        self.after_idle(self._set_code_sash)

    def _schedule_sidebar_toggle_position(self, event=None):
        self.after_idle(self._position_sidebar_toggle)

    def _position_sidebar_toggle(self):
        if self.is_fullscreen_mode or not getattr(self, "btn_toggle_sidebar", None):
            return

        try:
            self.paned_window.update_idletasks()
        except Exception:
            return

        btn_width = max(self.btn_toggle_sidebar.winfo_reqwidth(), self.btn_toggle_sidebar.winfo_width(), 1)
        btn_height = max(self.btn_toggle_sidebar.winfo_reqheight(), self.btn_toggle_sidebar.winfo_height(), 1)
        pane_width = max(self.paned_window.winfo_width(), btn_width)
        pane_height = max(self.paned_window.winfo_height(), btn_height)

        if self.is_right_panel_visible and len(self.paned_window.panes()) > 1:
            try:
                sash_x, _ = self.paned_window.sash_coord(0)
                x_pos = sash_x + max(self.DRAG_SASH_WIDTH // 2, 1)
            except tk.TclError:
                x_pos = self.left_frame.winfo_width()
        else:
            x_pos = pane_width - max((btn_width // 2) + 2, 1)

        y_pos = pane_height // 2
        x_pos = max(btn_width // 2, min(x_pos, pane_width - (btn_width // 2)))
        y_pos = max(btn_height // 2, min(y_pos, pane_height - (btn_height // 2)))

        self.btn_toggle_sidebar.place(x=x_pos, y=y_pos, anchor="center")
        self.btn_toggle_sidebar.lift()

    def _set_default_sections_panel_width(self):
        if not self.is_right_panel_visible or len(self.paned_window.panes()) <= 1:
            return
        try:
            self.paned_window.update_idletasks()
            total_width = self.paned_window.winfo_width()
            if total_width <= self.DEFAULT_SECTIONS_PANEL_WIDTH:
                return
            left_width = max(400, total_width - self.DEFAULT_SECTIONS_PANEL_WIDTH)
            self.paned_window.sash_place(0, left_width, 0)
            self.after_idle(self._position_sidebar_toggle)
        except Exception:
            pass

    def _get_main_layout(self):
        parent = self.master
        while parent is not None:
            if hasattr(parent, "set_navbar_visible"):
                return parent
            parent = getattr(parent, "master", None)
        return None

    def on_tab_shown(self):
        """Reapplies the correct layout state when the tab becomes visible."""
        self._apply_fullscreen_mode()

    def on_tab_hidden(self):
        """Restores shared UI when leaving the documentation tab."""
        main_layout = self._get_main_layout()
        if main_layout:
            main_layout.set_navbar_visible(True)

    def _save_settings(self):
        """Saves current view settings."""
        if self.controller and hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_doc_view_settings(
                self.is_dark_mode,
                self.is_editor_mode,
                self.code_sash_ratio,
                self.is_fullscreen_mode,
                self.markdown_preview_zoom,
                self.markdown_editor_font_size
            )

    # --- Markdown Highlighting & Rendering Logic ---

    def _configure_markdown_tags(self):
        """Configures Tkinter tags for Markdown syntax highlighting in the EDITOR."""
        w = self.txt_content
        base_size = max(self.MARKDOWN_EDITOR_FONT_SIZE_MIN, int(self.markdown_editor_font_size))
        # Headers
        w.tag_configure("MD_H1", foreground="#569cd6", font=(self.code_font_family, base_size + 4, "bold"))
        w.tag_configure("MD_H2", foreground="#569cd6", font=(self.code_font_family, base_size + 2, "bold"))
        w.tag_configure("MD_H3", foreground="#569cd6", font=(self.code_font_family, base_size + 1, "bold"))
        
        # Formatting
        w.tag_configure("MD_BOLD", font=(self.code_font_family, base_size, "bold"), foreground="#ce9178")
        w.tag_configure("MD_ITALIC", font=(self.code_font_family, base_size, "italic"))
        
        # Structure
        w.tag_configure(
            "MD_CODE",
            font=(self.code_font_family, max(self.MARKDOWN_EDITOR_FONT_SIZE_MIN, base_size - 1)),
            foreground="#dcdcaa",
            background="#2d2d2d"
        )
        w.tag_configure("MD_SYMBOL", foreground="#606060")

    def _on_content_change(self, event=None):
        """Handles text change with debounce."""
        if self.highlight_timer:
            self.after_cancel(self.highlight_timer)
        self.highlight_timer = self.after(300, self._apply_markdown_rendering)
        if self.autosave_enabled:
            self._schedule_autosave()

    def _render_markdown_code_block(self, code_text, language_hint, is_dark_mode):
        """Renders fenced Markdown code blocks with VS Code-like syntax colors."""
        formatter = HtmlFormatter(
            nowrap=True,
            noclasses=True,
            style=VsCodeDarkStyle if is_dark_mode else VsCodeLightStyle
        )

        lexer = None
        language_hint = (language_hint or "").strip()
        if language_hint:
            try:
                lexer = get_lexer_by_name(language_hint, stripall=False)
            except Exception:
                lexer = None

        if lexer is None and code_text.strip():
            try:
                lexer = guess_lexer(code_text)
            except Exception:
                lexer = None

        if lexer is None:
            lexer = TextLexer(stripall=False)

        try:
            highlighted = pygments_highlight(code_text, lexer, formatter)
        except Exception:
            highlighted = html_escape(code_text)

        return highlighted

    def _apply_markdown_rendering(self):
        """Highlights Editor and renders Markdown to HTML for the Web View."""
        content = self.txt_content.get("1.0", "end-1c")
        search_query = getattr(self, "_pending_document_search_query", "")
        previous_scroll = self._capture_web_view_scroll()
        # La búsqueda tiene su propio destino; restaurar el scroll anterior
        # después de cargar el HTML volvería a llevar la vista al principio.
        self._pending_web_view_scroll = None if search_query else previous_scroll
        if search_query:
            self._pending_web_view_fragment = None
        
        # 1. Highlight Editor (Source view)
        self._highlight_editor(content)
        
        # 2. Render to Web View
        if self.is_dark_mode:
            bg_color = "#0f1923"
            text_color = "#e2e8f0"
            link_color = "#2dd4bf" 
            border_color = "#1e3a5f"
            code_bg = "#0a1628"
            header_border = "#1e3a5f"
            quote_color = "#8899aa"
            table_bg = "#0f1923"
            th_bg = "#162234"
            code_link_color = "#f59e0b"
            code_link_bg = "#1a1a0a"
        else:
            bg_color = "#ffffff"
            text_color = "#24292f"
            link_color = "#0969da"
            border_color = "#d0d7de"
            code_bg = "#f6f8fa"
            header_border = "#d0d7de"
            quote_color = "#57606a"
            table_bg = "#ffffff"
            th_bg = "#f6f8fa"
            code_link_color = "#d97706"
            code_link_bg = "#fff7ed"

        try:
            # Handle empty content
            if not content.strip():
                empty_html = f"<html><body style='background-color:{bg_color}; color:{text_color}; font-family:{Styles.WEB_UI_FONT_STACK}; padding:20px; font-size:15px;'><i>Documento vacío</i></body></html>"
                self.web_view.load_html(empty_html)
                return

            # IMPORTANT: Avoid "gfm-like" as it requires linkify-it-py
            # We use a completely manual setup to ensure it works without extra dependencies
            md = MarkdownIt()
            md.options.update({"linkify": False, "typographer": False})
            md.enable("table")
            md.enable("strikethrough")
            self._editable_blocks = {}
            self._editable_block_seq = 0

            def render_code_inline(tokens, idx, options, env):
                code_text = tokens[idx].content
                escaped = html_escape(code_text)
                href = "code://" + quote(code_text, safe="")
                return f'<a class="code-link" href="{href}"><span class="code-inline">{escaped}</span></a>'

            def render_wrapped_open(block_kind, wrapper_class, render_tag_first=False):
                def renderer(tokens, idx, options, env):
                    token = tokens[idx]
                    stack = env.setdefault("editable_wrapper_stack", [])
                    is_nested = len(stack) > 0
                    
                    block_id = self._register_editable_block(token, block_kind, content)
                    
                    # Only show edit button for the outermost block to avoid duplicate pencils
                    button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                    anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                    
                    stack.append(wrapper_class)
                    
                    open_html = md.renderer.renderToken(tokens, idx, options, env)
                    if render_tag_first:
                        return open_html + f'<div id="{anchor_id}" class="editable-block {wrapper_class}">{button_html}'
                    return f'<div id="{anchor_id}" class="editable-block {wrapper_class}">{button_html}' + open_html
                return renderer

            def render_wrapped_close(render_tag_last=False):
                def renderer(tokens, idx, options, env):
                    wrapper_class = ""
                    if env.get("editable_wrapper_stack"):
                        wrapper_class = env["editable_wrapper_stack"].pop()
                    close_html = md.renderer.renderToken(tokens, idx, options, env)
                    if render_tag_last and wrapper_class:
                        return "</div>" + close_html
                    if wrapper_class:
                        return close_html + "</div>"
                    return close_html
                return renderer

            def render_fence(tokens, idx, options, env):
                token = tokens[idx]
                language_hint = ""
                if token.info:
                    language_hint = token.info.strip().split()[0]
                
                stack = env.setdefault("editable_wrapper_stack", [])
                is_nested = len(stack) > 0
                
                block_id = self._register_editable_block(token, "bloque de código", content, language_hint=language_hint)
                button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                highlighted = self._render_markdown_code_block(token.content, language_hint, self.is_dark_mode)
                return f'<div id="{anchor_id}" class="editable-block editable-code">{button_html}<pre class="code-block"><code>{highlighted}</code></pre></div>'

            def render_code_block(tokens, idx, options, env):
                token = tokens[idx]
                stack = env.setdefault("editable_wrapper_stack", [])
                is_nested = len(stack) > 0
                
                block_id = self._register_editable_block(token, "bloque de código", content)
                button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                highlighted = self._render_markdown_code_block(token.content, "", self.is_dark_mode)
                return f'<div id="{anchor_id}" class="editable-block editable-code">{button_html}<pre class="code-block"><code>{highlighted}</code></pre></div>'

            md.renderer.rules["code_inline"] = render_code_inline
            md.renderer.rules["fence"] = render_fence
            md.renderer.rules["code_block"] = render_code_block
            md.renderer.rules["paragraph_open"] = render_wrapped_open("párrafo", "editable-paragraph")
            md.renderer.rules["paragraph_close"] = render_wrapped_close()
            md.renderer.rules["heading_open"] = render_wrapped_open("título", "editable-heading")
            md.renderer.rules["heading_close"] = render_wrapped_close()
            md.renderer.rules["blockquote_open"] = render_wrapped_open("bloque de cita", "editable-quote")
            md.renderer.rules["blockquote_close"] = render_wrapped_close()
            md.renderer.rules["table_open"] = render_wrapped_open("tabla", "editable-table")
            md.renderer.rules["table_close"] = render_wrapped_close()
            md.renderer.rules["list_item_open"] = render_wrapped_open("elemento de lista", "editable-list-item", render_tag_first=True)
            md.renderer.rules["list_item_close"] = render_wrapped_close(render_tag_last=True)
            
            html_content = md.render(content)
            if search_query:
                html_content = self._highlight_document_search_match(html_content, search_query)
            
            # Simplified CSS for tkhtml (tkinterweb) compatibility
            # tkhtml is primitive: avoid nth-child, display:block on tables, and complex flex/grid
            css = f"""
            <style>
                body {{
                    font-family: {Styles.WEB_UI_FONT_STACK};
                    font-size: 15px;
                    line-height: 1.7;
                    color: {text_color};
                    background-color: {bg_color};
                    padding: 28px 32px;
                }}
                h1 {{ color: {text_color}; font-size: 26px; font-weight: 700; border-bottom: 1px solid {header_border}; padding-bottom: 8px; margin-top: 28px; margin-bottom: 18px; }}
                h2 {{ color: {text_color}; font-size: 20px; font-weight: 700; border-bottom: 1px solid {header_border}; padding-bottom: 5px; margin-top: 24px; margin-bottom: 14px; }}
                h3 {{ color: {text_color}; font-size: 17px; font-weight: 700; margin-top: 20px; margin-bottom: 12px; }}
                a {{ color: {link_color}; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                p {{ margin-bottom: 16px; }}
                strong {{ color: {text_color}; font-weight: 700; }}
                code {{ font-family: '{self.code_font_family}', 'Courier New', monospace; background-color: {code_bg}; padding: 3px 6px; border-radius: 4px; font-size: 13px; color: {text_color}; }}
                a.code-link {{ text-decoration: none; }}
                a.code-link .code-inline {{ font-family: '{self.code_font_family}', 'Courier New', monospace; background-color: {code_link_bg}; padding: 3px 6px; border-radius: 4px; font-size: 13px; color: {code_link_color}; border: 1px solid {border_color}; }}
                pre {{ background-color: {code_bg}; padding: 18px; border-radius: 10px; overflow: auto; margin-bottom: 18px; border: 1px solid {border_color}; }}
                pre code {{ background-color: transparent; padding: 0; color: {text_color}; }}
                pre.code-block {{
                    background-color: {VsCodeDarkStyle.background_color if self.is_dark_mode else VsCodeLightStyle.background_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 20px;
                }}
                pre.code-block code {{
                    display: block;
                    font-family: '{self.code_font_family}', 'Courier New', monospace;
                    font-size: 13px;
                    line-height: 1.65;
                    white-space: pre;
                }}
                .editable-block {{
                    position: relative;
                    margin-bottom: 10px;
                    padding-left: 36px;
                }}
                .editable-list-item {{
                    padding-left: 30px;
                }}
                .editable-code {{
                    padding-left: 0;
                }}
                .editable-code .edit-handle {{
                    left: auto;
                    right: 12px;
                    top: 10px;
                    border-radius: 8px;
                    padding: 4px 10px;
                    font-size: 12px;
                    background-color: {border_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                }}
                .edit-handle {{
                    position: absolute;
                    left: 4px;
                    top: 6px;
                    width: 24px;
                    height: 24px;
                    line-height: 24px;
                    text-align: center;
                    text-decoration: none;
                    border-radius: 6px;
                    border: 1px solid {border_color};
                    background-color: {code_link_bg};
                    color: {code_link_color};
                    font-size: 14px;
                    font-weight: bold;
                    visibility: hidden;
                }}
                .editable-block:hover .edit-handle {{ visibility: visible; }}
                blockquote {{ border-left: 4px solid {link_color}; padding-left: 16px; color: {quote_color}; margin-left: 0; margin-bottom: 16px; }}
                ul, ol {{ margin-bottom: 16px; padding-left: 24px; }}
                li {{ margin-bottom: 6px; }}
                
                /* Table styling optimized for tkhtml */
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; border: 1px solid {border_color}; border-radius: 8px; }}
                th, td {{ border: 1px solid {border_color}; padding: 10px 14px; text-align: left; }}
                th {{ background-color: {th_bg}; color: {text_color}; font-weight: 700; }}
                tr {{ background-color: {table_bg}; }}
                mark.doc-search-match {{ background-color: #fff3a3; color: #111827; padding: 1px 2px; border-radius: 2px; }}
            </style>
            """
            
            full_html = f"<html><head>{css}</head><body>{html_content}</body></html>"
            self.web_view.load_html(
                full_html,
                fragment=None if search_query else self._pending_web_view_fragment
            )
            
        except Exception as e:
            logging.error(f"Web Render error: {e}")

    def _highlight_document_search_match(self, html_content, search_query):
        """Wraps the first visible HTML text match in a yellow mark element."""
        query = (search_query or "").strip()
        if not query:
            return html_content

        candidates = [query, html_escape(query)]
        parts = re.split(r"(<[^>]+>)", html_content)
        for index in range(0, len(parts), 2):
            text_part = parts[index]
            for candidate in candidates:
                if candidate and re.search(re.escape(candidate), text_part, flags=re.IGNORECASE):
                    parts[index] = re.sub(
                        re.escape(candidate),
                        lambda match: f'<mark id="doc-search-match" class="doc-search-match">{match.group(0)}</mark>',
                        text_part,
                        count=1,
                        flags=re.IGNORECASE
                    )
                    return "".join(parts)
        return html_content

    def _highlight_editor(self, content):
        """Applies basic color highlights to the source editor."""
        for t in ["MD_H1", "MD_H2", "MD_H3", "MD_BOLD", "MD_ITALIC", "MD_CODE", "MD_SYMBOL"]:
            self.txt_content.tag_remove(t, "1.0", tk.END)

        # Headers
        for m in re.finditer(r"^(#+)(.*)$", content, re.MULTILINE):
            s, e = m.span()
            symbols_end = m.start(2)
            self.txt_content.tag_add("MD_SYMBOL", self._idx_to_tk(s, self.txt_content), self._idx_to_tk(symbols_end, self.txt_content))
            level = len(m.group(1))
            tag = f"MD_H{level}" if level <= 3 else "MD_H3"
            self.txt_content.tag_add(tag, self._idx_to_tk(symbols_end, self.txt_content), self._idx_to_tk(e, self.txt_content))

        # Inline formatting (Regex-based for Editor)
        self._apply_regex_tags(content, r"\*\*(.*?)\*\*", "MD_BOLD", self.txt_content)
        self._apply_regex_tags(content, r"\*(.*?)\*", "MD_ITALIC", self.txt_content)
        self._apply_regex_tags(content, r"`(.*?)`", "MD_CODE", self.txt_content)

    def _apply_regex_tags(self, content, pattern, tag, widget):
        for m in re.finditer(pattern, content):
            s, e = m.span()
            widget.tag_add(tag, self._idx_to_tk(s, widget), self._idx_to_tk(e, widget))

    def _idx_to_tk(self, index, widget):
        """Converts character index to Tkinter line.col index."""
        content_up_to = widget.get("1.0", f"1.0 + {index} chars")
        lines = content_up_to.split('\n')
        line = len(lines)
        col = len(lines[-1])
        return f"{line}.{col}"
