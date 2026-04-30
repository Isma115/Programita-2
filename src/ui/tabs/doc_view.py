import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog
import io
import os
import webbrowser
import logging
import re
import time
import shutil
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
    DEFAULT_SECTIONS_PANEL_WIDTH = 340
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
        self.is_dark_mode = False     # Default to Light
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
        self._code_highlight_job = None
        self._active_code_file_path = None
        self.diagram_editor_window = None
        self.doc_path_options = {}
        self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
        self.markdown_preview_fontscale = self.MARKDOWN_PREVIEW_FONTSCALE
        self.code_font_family = self._resolve_code_font_family()
        self.doc_sidebar_font_family = self._resolve_doc_sidebar_font_family()
        self.code_font_size = ARB_FONT_CODE[1] if ARB_FONT_CODE else 14
        self.toolbar_surface_bg = Styles.COLOR_DOC_TOOLBAR_BG
        self._doc_tree_drag_source = None
        self._doc_tree_drag_start = None
        self._doc_tree_drag_active = False
        self._doc_tree_drop_target = None

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
            self.is_dark_mode = settings.get("is_dark_mode", False)
            self.is_editor_mode = settings.get("is_editor_mode", False)
            self.code_sash_ratio = settings.get("code_sash_ratio", 0.7)
            self.is_fullscreen_mode = settings.get("is_fullscreen_mode", False)
            self.markdown_preview_zoom = settings.get("markdown_preview_zoom", self.MARKDOWN_PREVIEW_ZOOM)
        else:
            self.code_sash_ratio = 0.7
            self.markdown_preview_zoom = self.MARKDOWN_PREVIEW_ZOOM
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
            # Assuming assets is at project root
            base_path = os.path.join(os.getcwd(), "assets", "icons")
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
            command=self._open_prompt_builder,
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
            font=("Consolas", 12),
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

        self.section_search_shell = tk.Frame(
            self.right_top_frame,
            bg=Styles.COLOR_BG_SIDEBAR,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
            bd=0
        )
        self.section_search_shell.pack(fill="x", padx=8, pady=(4, 6))

        self.section_search_label = tk.Label(
            self.section_search_shell,
            text="Buscar...",
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            font=(self.doc_sidebar_font_family, 13, "bold"),
            anchor="w"
        )
        self.section_search_label.pack(fill="x", padx=10, pady=(8, 0))

        self.section_search_entry = tk.Entry(
            self.section_search_shell,
            font=(self.doc_sidebar_font_family, 15),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        self.section_search_entry.pack(fill="x", padx=10, pady=(6, 10), ipady=8)
        self.section_search_entry.bind("<KeyRelease>", self._on_section_search_change)

        # Section Tree (replaces Listbox for hierarchical support)
        self.section_tree = ttk.Treeview(
            self.right_top_frame,
            show="tree",
            selectmode="browse",
            style="Treeview"
        )
        self.section_tree.column("#0", stretch=True)
        self.section_tree.bind("<<TreeviewSelect>>", self._on_section_select)
        self.section_tree.bind("<Button-1>", self._on_section_click)
        self.section_tree.bind("<ButtonPress-1>", self._on_section_tree_press, add="+")
        self.section_tree.bind("<B1-Motion>", self._on_section_tree_drag_motion, add="+")
        self.section_tree.bind("<ButtonRelease-1>", self._on_section_tree_release, add="+")
        
        # Tags for different file types and folders
        self.section_tree.tag_configure("folder", font=(self.doc_sidebar_font_family, 16, "bold"), foreground=Styles.COLOR_ACCENT)
        self.section_tree.tag_configure("md", font=(self.doc_sidebar_font_family, 14))
        self.section_tree.tag_configure("document", font=(self.doc_sidebar_font_family, 14), foreground=Styles.COLOR_DIM)
        self.section_tree.tag_configure("drop_target", background="#244b74", foreground="#f4f7fb")
        
        self.section_tree.pack(fill="both", expand=True, padx=5, pady=5)
                
        btn_frame = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        
        # Nueva Sección moved to context menu
        
        # Context Menu for Sections (same as CodeView)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Nueva Sección", command=self._on_add_section)
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
        preferred_path = None
        selected = self.section_tree.selection()
        if selected:
            preferred_path = selected[0]
        self._refresh_sections(preferred_path=preferred_path)

    def _on_doc_path_selected(self, event=None):
        selected_label = self.cmb_doc_paths.get().strip()
        selected_path = self.doc_path_options.get(selected_label)
        if not selected_path:
            return

        current_path = self._get_doc_root()
        if current_path and os.path.normpath(current_path) == os.path.normpath(selected_path):
            return

        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_doc_path(selected_path)
        self._refresh_sections()

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

    def _display_file_content(self, file_path):
        try:
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
            self._apply_markdown_rendering()
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

    def _on_save_doc(self):
        if not self.current_file_path:
            messagebox.showwarning("Aviso", "No hay ningún documento abierto para guardar.")
            return

        try:
            content = self.txt_content.get("1.0", "end-1c")
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"DocView: Guardado {self.current_file_path}")
            # Optional: visual feedback
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {e}")

    def _on_save_doc_shortcut(self, event=None):
        self._on_save_doc()
        return "break"

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

        # Get current section name as suggestion
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Aviso", "Selecciona una sección para crear el documento.")
            return
        section_name = self.section_list.get(selected_indices[0])
        suggestion = "documentacion.md"

        # Ask for filename
        filename = simpledialog.askstring("Nuevo Documento", "Nombre del archivo (.md):", initialvalue=suggestion)
        if not filename: return
        filename = filename.strip()
        if not filename:
            messagebox.showwarning("Aviso", "El nombre del documento no puede estar vacío.")
            return
        if self._has_path_separator(filename):
            messagebox.showwarning("Aviso", "El nombre del documento no puede contener separadores de ruta.")
            return
        if not filename.endswith(".md"): filename += ".md"

        section_dir = os.path.join(doc_dir, section_name)
        os.makedirs(section_dir, exist_ok=True)
        file_path = os.path.join(section_dir, filename)
        if os.path.exists(file_path):
            if not messagebox.askyesno("Confirmar", "El archivo ya existe. ¿Sobrescribir?"):
                return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {filename[:-3]}\n\n")
            
            # Refresh current section view to find the new file
            self._last_selected_section = section_name
            self._find_markdown_files(section_name, selected_file_path=file_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear: {e}")

    def _build_documentation_prompt(self, functionality_name):
        functionality_name = (functionality_name or "").strip()

        return (
            f"Genera un documento markdown para conocer de forma simple y directa el flujo de la funcionalidad del software "
            f"\"{functionality_name}\".\n\n"
            "Junto con referencias al código y funciones, variables o elementos importantes relacionados con el flujo. "
            "Incluye una pequeña descripción de lo que hace cada paso y documenta cada funcionalidad implicada. "
            "Agrega trozos de código en cada apartado para saber qué código se está ejecutando en cada paso.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Primero escribe el flujo en lenguaje no técnico, simple y directo.\n"
            "2. Después añade el apartado equivalente en lenguaje técnico.\n"
            "3. Divide el documento por pasos claros del flujo.\n"
            "4. En cada paso, indica referencias al código relacionado.\n"
            "5. Señala funciones, variables, componentes, endpoints, consultas o tablas importantes si aplica.\n"
            "6. Añade fragmentos de código útiles y concretos en cada apartado.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Explicación clara y directa.\n"
            "- Primero visión funcional y después visión técnica.\n"
            "- Código de apoyo en cada sección relevante.\n\n"
            "Guarda el documento en docs."
        )

    def _build_specific_flow_documentation_prompt(self, functionality_name):
        functionality_name = (functionality_name or "").strip()

        return (
            f"Documenta el flujo de código de {functionality_name} con las siguientes normas:\n\n"
            "- Divide el Markdown por pasos\n"
            "- Cada paso tiene que tener esta estructura:\n"
            "   1. x número de paso\n"
            "   2. Descripción sencilla pero detallada de lo que se hace en este paso\n"
            "   3. Trozo de código exacto o algoritmo que se ejecuta solamente en este paso\n"
            "   4. No te dejes partes del flujo que sean relevantes, tanto frontend como backend y rutas deben incluirse\n"
            "   5. Añade comentarios extra al código si es necesario, para explicar de manera sencilla y fácil que hace cada cosa\n"
            "   6. Repetir para los pasos numerados siguientes hasta el paso final en el fin del documento\n"
            "- Guarda el documento markdown en una carpeta docs"
        )

    def _build_optimization_prompt(self, target_name):
        target_name = (target_name or "").strip()

        return (
            f"Genera un documento markdown con un plan claro para optimizar la parte del código "
            f"\"{target_name}\".\n\n"
            "El objetivo es hacer esa zona más legible, mantenible y eficiente sin romper el comportamiento actual. "
            "Analiza nombres, responsabilidades, complejidad, duplicidad, estructura, posibles mejoras de rendimiento "
            "y riesgos del refactor.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Resume qué hace actualmente esa parte del código en lenguaje simple.\n"
            "2. Describe los problemas detectados de legibilidad, diseño, mantenimiento y rendimiento.\n"
            "3. Propón una secuencia de pasos concreta para optimizarla.\n"
            "4. En cada paso, indica archivos, funciones, clases, variables o componentes implicados.\n"
            "5. Explica el beneficio esperado de cada cambio.\n"
            "6. Añade fragmentos de código o pseudocódigo cuando ayuden a entender el cambio.\n"
            "7. Cierra con una checklist de validación para confirmar que el refactor no rompe nada.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Pasos ordenados y accionables.\n"
            "- Explicación directa, sin relleno.\n"
            "- Con referencias concretas al código.\n\n"
            "Guarda el documento en docs."
        )

    def _build_test_prompt(self, feature_name):
        feature_name = (feature_name or "").strip()

        return (
            f"Propón una prueba manual para validar la característica del software "
            f"\"{feature_name}\".\n\n"
            "El objetivo es definir una comprobación simple, clara y fácil de seguir para verificar manualmente que "
            "esa característica funciona correctamente.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Resume qué se quiere comprobar y cuál es el comportamiento esperado de la característica.\n"
            "2. Indica el contexto previo necesario para hacer la prueba manual.\n"
            "3. Describe los pasos exactos que debe seguir una persona dentro de la app/web/software.\n"
            "4. Explica qué debe comprobar manualmente en cada paso.\n"
            "5. Indica el resultado esperado final para dar la prueba por válida.\n"
            "6. Añade una breve lista de señales claras de que la prueba ha fallado.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Explicación directa y accionable.\n"
            "- Pasos numerados y fáciles de seguir.\n"
            "- Solo prueba manual, sin tests automáticos.\n\n"
            "Guarda el documento en docs."
        )

    def _build_relevant_files_list_prompt(self, target_name):
        target_name = (target_name or "").strip()

        return (
            "Actúa como un agente de código senior.\n\n"
            f"Tu tarea es identificar los archivos de código relevantes para la parte del sistema "
            f"\"{target_name}\".\n\n"
            "Devuelve únicamente una lista simple de rutas de archivos de código relevantes.\n"
            "No añadas explicaciones, descripciones, encabezados, categorías, viñetas anidadas, comentarios ni texto extra.\n"
            "No incluyas archivos no relacionados.\n"
            "Prioriza archivos donde esté la lógica principal, los puntos de entrada, dependencias directas y piezas claramente implicadas.\n\n"
            "Formato obligatorio de salida:\n"
            "- Una ruta por línea.\n"
            "- Solo texto plano con las rutas.\n"
            "- Sin nada antes ni después de la lista."
        )

    def _open_prompt_builder(self):
        dialog = tk.Toplevel(self)
        dialog.title("Prompt")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("980x820")
        dialog.minsize(760, 520)
        dialog.configure(bg=Styles.COLOR_BG_MAIN)

        wrapper = ttk.Frame(dialog, style="Main.TFrame")
        wrapper.pack(fill="both", expand=True, padx=12, pady=12)

        prompt_configs = [
            {
                "name": "Documentación",
                "input_label": "Funcionalidad",
                "placeholder": "[FUNCIONALIDAD]",
                "builder": self._build_documentation_prompt,
            },
            {
                "name": "Documentación funcional",
                "input_label": "Funcionalidad específica",
                "placeholder": "[X]",
                "builder": self._build_specific_flow_documentation_prompt,
            },
            {
                "name": "Optimización",
                "input_label": "Parte del código",
                "placeholder": "[PARTE_CODIGO]",
                "builder": self._build_optimization_prompt,
            },
            {
                "name": "Test",
                "input_label": "Característica a probar",
                "placeholder": "[CARACTERISTICA]",
                "builder": self._build_test_prompt,
            },
            {
                "name": "Lista de ficheros",
                "input_label": "Parte del código",
                "placeholder": "[PARTE_CODIGO]",
                "builder": self._build_relevant_files_list_prompt,
                "include_file_path_instruction": False,
            },
        ]
        prompt_index = {"value": 0}
        prompt_title_var = tk.StringVar()
        input_label_var = tk.StringVar()
        prompt_placeholder_active = {"value": False}

        selector_row = ttk.Frame(wrapper, style="Main.TFrame")
        selector_row.pack(fill="x", pady=(0, 12))
        selector_row.columnconfigure(1, weight=1)

        btn_prev = ttk.Button(
            selector_row,
            text="←",
            width=3,
            style="Nav.TButton",
            command=lambda: switch_prompt(-1)
        )
        btn_prev.grid(row=0, column=0, sticky="ew")
        attach_tooltip(btn_prev, "Prompt previo")

        ttk.Frame(selector_row, style="Main.TFrame").grid(row=0, column=1, sticky="ew", padx=10)

        btn_next = ttk.Button(
            selector_row,
            text="→",
            width=3,
            style="Nav.TButton",
            command=lambda: switch_prompt(1)
        )
        btn_next.grid(row=0, column=2, sticky="ew")
        attach_tooltip(btn_next, "Prompt siguiente")

        ttk.Label(wrapper, textvariable=input_label_var, style="Header.TLabel").pack(fill="x")

        functionality_var = tk.StringVar()

        entry = tk.Entry(
            wrapper,
            textvariable=functionality_var,
            font=(Styles.FONT_FAMILY, 16),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground=Styles.COLOR_FG_TEXT,
            relief="flat"
        )
        entry.pack(fill="x", pady=(10, 12), ipady=10)

        ttk.Label(wrapper, text="Plantilla del prompt", style="TLabel").pack(anchor="w")

        prompt_text = tk.Text(
            wrapper,
            font=("Consolas", 13),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground=Styles.COLOR_FG_TEXT,
            relief="flat",
            wrap="word",
            padx=12,
            pady=12
        )
        prompt_text.pack(fill="both", expand=True, pady=(8, 12))

        prompt_scroll = ttk.Scrollbar(wrapper, orient="vertical", command=prompt_text.yview)
        prompt_scroll.place(relx=1.0, rely=0.23, relheight=0.66, anchor="ne")
        prompt_text.configure(yscrollcommand=prompt_scroll.set)

        def build_prompt_content():
            config = prompt_configs[prompt_index["value"]]
            functionality_name = ""
            if not prompt_placeholder_active["value"]:
                functionality_name = functionality_var.get().strip()
            functionality_name = functionality_name or config["placeholder"]
            prompt = config["builder"](functionality_name)
            if config.get("include_file_path_instruction", True):
                prompt = ensure_file_path_comment_instruction(prompt)
            return prompt

        def show_prompt_placeholder():
            if functionality_var.get().strip():
                return
            prompt_placeholder_active["value"] = True
            entry.configure(fg=Styles.COLOR_DIM)
            functionality_var.set(prompt_title_var.get())

        def hide_prompt_placeholder():
            if not prompt_placeholder_active["value"]:
                return
            prompt_placeholder_active["value"] = False
            entry.configure(fg=Styles.COLOR_FG_TEXT)
            functionality_var.set("")

        def refresh_prompt(event=None):
            prompt_text.delete("1.0", tk.END)
            prompt_text.insert("1.0", build_prompt_content())

        def sync_prompt_selector():
            config = prompt_configs[prompt_index["value"]]
            prompt_title_var.set(f"Prompt: {config['name']}")
            input_label_var.set(config["input_label"])
            dialog.title(prompt_title_var.get())
            if prompt_placeholder_active["value"] or not functionality_var.get().strip():
                functionality_var.set("")
                show_prompt_placeholder()

        def switch_prompt(delta):
            prompt_index["value"] = (prompt_index["value"] + delta) % len(prompt_configs)
            sync_prompt_selector()
            refresh_prompt()

        def on_prev_prompt(event=None):
            switch_prompt(-1)
            return "break"

        def on_next_prompt(event=None):
            switch_prompt(1)
            return "break"

        def on_entry_focus_in(event=None):
            hide_prompt_placeholder()

        def on_entry_focus_out(event=None):
            if not functionality_var.get().strip():
                show_prompt_placeholder()

        def copy_prompt():
            config = prompt_configs[prompt_index["value"]]
            content = prompt_text.get("1.0", "end-1c").strip()
            if config.get("include_file_path_instruction", True):
                content = ensure_file_path_comment_instruction(content)
            if not content:
                return
            try:
                if self.controller and hasattr(self.controller, "copy_to_clipboard"):
                    copied = self.controller.copy_to_clipboard(content)
                    if copied:
                        messagebox.showinfo("Prompt", "Prompt copiado al portapapeles.")
                        return
                self.clipboard_clear()
                self.clipboard_append(content)
                messagebox.showinfo("Prompt", "Prompt copiado al portapapeles.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo copiar el prompt: {e}")

        button_row = ttk.Frame(wrapper, style="Main.TFrame")
        button_row.pack(fill="x")

        button_group = ttk.Frame(button_row, style="Main.TFrame")
        button_group.pack(side="right")
        button_group.columnconfigure(0, weight=1, uniform="prompt_actions")
        button_group.columnconfigure(1, minsize=8)
        button_group.columnconfigure(2, weight=1, uniform="prompt_actions")

        btn_close_prompt = ttk.Button(
            button_group,
            text="Cerrar",
            style="Secondary.TButton",
            command=dialog.destroy
        )
        btn_close_prompt.grid(row=0, column=0, sticky="ew")
        attach_tooltip(btn_close_prompt, "Cerrar ventana")

        btn_copy_prompt = ttk.Button(
            button_group,
            text="Copiar prompt",
            style="Action.TButton",
            command=copy_prompt
        )
        btn_copy_prompt.grid(row=0, column=2, sticky="ew")
        attach_tooltip(btn_copy_prompt, "Copiar prompt")

        dialog.update_idletasks()
        max_button_width = max(
            btn_close_prompt.winfo_reqwidth(),
            btn_copy_prompt.winfo_reqwidth()
        )
        button_group.columnconfigure(0, minsize=max_button_width)
        button_group.columnconfigure(2, minsize=max_button_width)

        functionality_var.trace_add("write", lambda *_: refresh_prompt())
        entry.bind("<FocusIn>", on_entry_focus_in)
        entry.bind("<FocusOut>", on_entry_focus_out)
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.bind("<Control-Left>", on_prev_prompt)
        dialog.bind("<Control-Right>", on_next_prompt)
        dialog.bind("<Command-Left>", on_prev_prompt)
        dialog.bind("<Command-Right>", on_next_prompt)
        sync_prompt_selector()
        refresh_prompt()

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

    def _on_web_view_done_loading(self, event=None):
        """Restores scroll once tkinterweb finishes loading the rendered markdown."""
        if self._pending_web_view_fragment is not None:
            self._pending_web_view_fragment = None
            self._pending_web_view_scroll = None
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
            messagebox.showwarning("Aviso", "Selecciona una carpeta o archivo para renombrar.")
            return

        old_path = selected[0]
        old_name = os.path.basename(old_path)
        new_name = simpledialog.askstring("Renombrar", "Nuevo nombre:", initialvalue=old_name)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or self._has_path_separator(new_name) or new_name == old_name:
            return

        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if os.path.exists(new_path):
            messagebox.showwarning("Aviso", "Ya existe.")
            return

        try:
            os.rename(old_path, new_path)
            self._refresh_sections(preferred_path=new_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar: {e}")

    def _on_delete_section(self):
        selected = self.section_tree.selection()
        if not selected:
            return

        path = selected[0]
        name = os.path.basename(path)
        is_dir = os.path.isdir(path)

        confirm = messagebox.askyesno(
            "Eliminar",
            f"¿Estás seguro de que quieres eliminar '{name}'?"
        )
        if not confirm:
            return

        try:
            if is_dir:
                shutil.rmtree(path)
            else:
                os.remove(path)
            
            if self.current_file_path == path:
                self.current_file_path = None
                self._display_message("Documento eliminado.")
                
            self._refresh_sections()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar: {e}")

    def _refresh_sections(self, preferred_path=None):
        self._refresh_doc_path_history()
        
        # Clear existing
        try:
            for item in self.section_tree.get_children():
                self.section_tree.delete(item)
        except Exception:
            pass
            
        doc_root = self._get_doc_root()
        if not doc_root:
            self._display_message("⚠️ Carga una carpeta de documentación.")
            return

        self._build_tree(doc_root, "")
        
        if not preferred_path:
            if not self.current_file_path and self.controller and hasattr(self.controller, "config_manager"):
                preferred_path = self.controller.config_manager.get_last_doc_file()
            else:
                preferred_path = self.current_file_path
                
        if preferred_path and self.section_tree.exists(preferred_path):
            self.section_tree.selection_set(preferred_path)
            self.section_tree.see(preferred_path)
            if not self.current_file_path and os.path.isfile(preferred_path):
                self._on_section_select()

    def _build_tree(self, root_path, parent_id):
        """Recursively builds the Treeview structure."""
        try:
            if not os.path.isdir(root_path): return
            items = os.listdir(root_path)
            # Sort items: directories first, then files
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(root_path, x)), x.lower()))
            
            query = self.section_search_entry.get().strip().lower() if hasattr(self, "section_search_entry") else ""

            for name in items:
                if name.startswith('.'): continue
                full_path = os.path.join(root_path, name)
                is_dir = os.path.isdir(full_path)
                
                # Check for supported extensions
                ext = os.path.splitext(name)[1].lower()
                supported_exts = {'.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.png', '.jpg', '.jpeg'}
                
                if not is_dir and ext not in supported_exts:
                    continue

                if is_dir:
                    # Create node
                    node_id = full_path

                    self.section_tree.insert(parent_id, "end", iid=node_id, text=f"{name}", tags=("folder",), open=bool(query))
                    self._build_tree(full_path, node_id)
                    
                    # If query is active and this folder has no children after recursion, and doesn't match itself, remove it
                    if query and query not in name.lower() and not self.section_tree.get_children(node_id):
                        self.section_tree.delete(node_id)
                else:
                    if not query or query in name.lower():

                        tag = "md" if ext == ".md" else "document"
                        self.section_tree.insert(parent_id, "end", iid=full_path, text=f"{name}", tags=(tag,))
        except Exception as e:
            logging.error(f"Error building tree for {root_path}: {e}")

    def _refresh_doc_path_history(self):
        self.doc_path_options = {}
        values = []
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
            self.cmb_doc_paths.set(values[0])
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
                self.markdown_preview_zoom
            )

    # --- Markdown Highlighting & Rendering Logic ---

    def _configure_markdown_tags(self):
        """Configures Tkinter tags for Markdown syntax highlighting in the EDITOR."""
        w = self.txt_content
        # Headers
        w.tag_configure("MD_H1", foreground="#569cd6", font=(Styles.FONT_FAMILY, 16, "bold"))
        w.tag_configure("MD_H2", foreground="#569cd6", font=(Styles.FONT_FAMILY, 14, "bold"))
        w.tag_configure("MD_H3", foreground="#569cd6", font=(Styles.FONT_FAMILY, 13, "bold"))
        
        # Formatting
        w.tag_configure("MD_BOLD", font=(Styles.FONT_FAMILY, 12, "bold"), foreground="#ce9178")
        w.tag_configure("MD_ITALIC", font=(Styles.FONT_FAMILY, 12, "italic"))
        
        # Structure
        w.tag_configure("MD_CODE", font=(self.code_font_family, 11), foreground="#dcdcaa", background="#2d2d2d")
        w.tag_configure("MD_SYMBOL", foreground="#606060")

    def _on_content_change(self, event=None):
        """Handles text change with debounce."""
        if self.highlight_timer:
            self.after_cancel(self.highlight_timer)
        self.highlight_timer = self.after(300, self._apply_markdown_rendering)

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
        previous_scroll = self._capture_web_view_scroll()
        self._pending_web_view_scroll = previous_scroll
        
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
            </style>
            """
            
            full_html = f"<html><head>{css}</head><body>{html_content}</body></html>"
            self.web_view.load_html(full_html, fragment=self._pending_web_view_fragment)
            
        except Exception as e:
            logging.error(f"Web Render error: {e}")

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
