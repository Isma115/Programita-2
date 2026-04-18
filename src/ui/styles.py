import tkinter as tk
from tkinter import ttk

class Styles:
    """
    Handles the configuration of application styles, colors, and fonts.
    HidraSmart Dark Blue Theme - Professional IDE-like appearance.
    """
    
    UI_SCALE = 0.90

    # ── HidraSmart Dark Blue Palette ──
    COLOR_BG_MAIN = "#0a1220"        # Deep navy background
    COLOR_BG_SIDEBAR = "#101a2d"     # Slightly lighter navy for sidebars/toolbar
    COLOR_FG_TEXT = "#edf3ff"        # Cool white text
    COLOR_ACCENT = "#2f80ff"         # Electric blue accent
    COLOR_ACCENT_HOVER = "#4d96ff"   # Hover blue
    COLOR_BORDER = "#263a5c"         # Subtle blue border
    COLOR_DIM = "#8b9ab6"            # Dimmed text (blue-gray)
    COLOR_PANE_DIVIDER = "#223552"   # Divider matching border

    # Input/List Colors
    COLOR_INPUT_BG = "#131f34"       # Input field background
    COLOR_INPUT_FG = "#ffffff"       # White input text
    COLOR_SELECTION_BG = "#20365a"   # Selection highlight

    # Toolbar specific
    COLOR_TOOLBAR_BG = "#0d1117"      # GitHub dark toolbar background
    COLOR_DOC_TOOLBAR_BG = "#1a1d22"  # Flat dark gray surface for docs toolbar
    COLOR_DOC_TOOLBAR_HOVER = "#242932"
    COLOR_TOOLBAR_ICON_BG = "#21262d" # GitHub button background
    COLOR_TOOLBAR_ICON_HOVER = "#30363d" # GitHub button hover
    COLOR_BUTTON_BG = "#21262d"
    COLOR_BUTTON_HOVER = "#30363d"
    COLOR_BUTTON_ACTIVE = "#262c36"
    COLOR_BUTTON_BORDER = "#30363d"
    COLOR_BUTTON_FG = "#c9d1d9"
    COLOR_BUTTON_FG_ACTIVE = "#f0f6fc"
    COLOR_SIDEBAR_CARD_BG = "#111b2b"
    COLOR_SIDEBAR_CARD_INNER = "#17253b"
    COLOR_SIDEBAR_CARD_ALT = "#1b2c47"
    COLOR_SIDEBAR_ROW_BG = "#1a2943"

    # Fonts
    FONT_FAMILY = "Segoe UI"
    BASE_FONT_MAIN = ("Segoe UI", 18, "bold")
    BASE_FONT_HEADER = ("Segoe UI", 20, "bold")
    BASE_FONT_CODE = ("Consolas", 14)
    BASE_FONT_BUTTON = ("Segoe UI", 18, "bold")
    BASE_FONT_BREADCRUMB = ("Segoe UI", 12)
    FONT_MAIN = BASE_FONT_MAIN
    FONT_HEADER = BASE_FONT_HEADER
    FONT_CODE = BASE_FONT_CODE
    FONT_BUTTON = BASE_FONT_BUTTON
    FONT_BREADCRUMB = BASE_FONT_BREADCRUMB

    # Rounded corner radius
    CORNER_RADIUS = 8
    SOFT_EDGE_BORDER = 1
    BASE_SOFT_EDGE_PADDING = 4
    SOFT_EDGE_PADDING = BASE_SOFT_EDGE_PADDING

    @staticmethod
    def scale_size(value):
        try:
            return max(int(round(float(value) * Styles.UI_SCALE)), 1)
        except Exception:
            return value

    @staticmethod
    def scale_padding(value):
        if isinstance(value, (tuple, list)):
            return tuple(Styles.scale_size(v) for v in value)
        return Styles.scale_size(value)

    @staticmethod
    def scale_font(font_value):
        if not isinstance(font_value, (tuple, list)) or len(font_value) < 2:
            return font_value

        family = font_value[0]
        size = font_value[1]
        rest = tuple(font_value[2:])

        if not isinstance(size, (int, float)):
            return tuple(font_value)

        return (family, max(int(round(size * Styles.UI_SCALE)), 1), *rest)

    @staticmethod
    def apply_tk_scaling(root):
        if getattr(root, "_programita_tk_scaled", False):
            return

        try:
            current_scaling = float(root.tk.call("tk", "scaling"))
            root.tk.call("tk", "scaling", current_scaling * Styles.UI_SCALE)
        except Exception:
            pass

        root._programita_tk_scaled = True

    @staticmethod
    def soften_classic_widget(widget):
        """
        Applies a softer border treatment to classic Tk input widgets.
        Tk does not support true border radius natively, so we use a thin
        accent-aware outline to visually soften the control.
        """
        try:
            if getattr(widget, "_skip_soften", False):
                return
            widget_class = widget.winfo_class()
        except Exception:
            return

        common = {
            "relief": "flat",
            "borderwidth": 0,
            "highlightthickness": 0,
            "highlightbackground": Styles.COLOR_BORDER,
            "highlightcolor": Styles.COLOR_ACCENT,
        }

        try:
            if widget_class == "Entry":
                widget.configure(**common)
            elif widget_class == "Text":
                widget.configure(**common)
            elif widget_class == "Listbox":
                widget.configure(**common, selectborderwidth=0, activestyle="none")
        except Exception:
            pass

    @staticmethod
    def apply_soft_widget_chrome(widget):
        """Recursively applies the softer chrome to existing classic Tk widgets."""
        Styles.soften_classic_widget(widget)
        try:
            children = widget.winfo_children()
        except Exception:
            return

        for child in children:
            Styles.apply_soft_widget_chrome(child)

    @staticmethod
    def strip_classic_widget_chrome(widget):
        """Removes borders/highlights from classic Tk widgets for flat surfaces."""
        try:
            widget_class = widget.winfo_class()
        except Exception:
            return

        common = {
            "relief": "flat",
            "borderwidth": 0,
            "highlightthickness": 0,
        }

        try:
            if widget_class in {"Entry", "Text", "Listbox", "Spinbox"}:
                widget.configure(**common)
                if widget_class == "Listbox":
                    widget.configure(selectborderwidth=0, activestyle="none")
        except Exception:
            pass

    @staticmethod
    def _bind_soft_widget_chrome(root):
        """Ensure future classic Tk inputs receive the same softened border treatment."""
        for class_name in ("Entry", "Text", "Listbox"):
            root.bind_class(
                class_name,
                "<Map>",
                lambda event: Styles.soften_classic_widget(event.widget),
                add="+"
            )

    @staticmethod
    def style_card_frame(frame, bg=None):
        frame.configure(
            bg=bg or Styles.COLOR_SIDEBAR_CARD_BG,
            bd=0,
            highlightthickness=0,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT
        )

    @staticmethod
    def style_sidebar_entry(entry):
        entry.configure(
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            relief="flat",
            bd=0,
            highlightthickness=0,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT
        )

    @staticmethod
    def style_sidebar_listbox(listbox):
        listbox.configure(
            bg=Styles.COLOR_SIDEBAR_CARD_INNER,
            fg=Styles.COLOR_INPUT_FG,
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            activestyle="none",
            selectborderwidth=0
        )

    @staticmethod
    def _init_base_config(style, root):
        style.theme_use('clam') 
        Styles.apply_tk_scaling(root)
        Styles.FONT_MAIN = Styles.scale_font(Styles.BASE_FONT_MAIN)
        Styles.FONT_HEADER = Styles.scale_font(Styles.BASE_FONT_HEADER)
        Styles.FONT_CODE = Styles.scale_font(Styles.BASE_FONT_CODE)
        Styles.FONT_BUTTON = Styles.scale_font(Styles.BASE_FONT_BUTTON)
        Styles.FONT_BREADCRUMB = Styles.scale_font(Styles.BASE_FONT_BREADCRUMB)
        Styles.SOFT_EDGE_PADDING = Styles.scale_size(Styles.BASE_SOFT_EDGE_PADDING)

        # Configure Main Window background
        root.configure(bg=Styles.COLOR_BG_MAIN)

        # Dropdown/Combobox popups handling
        root.option_add("*TCombobox*Listbox*Background", Styles.COLOR_INPUT_BG)
        root.option_add("*TCombobox*Listbox*Foreground", Styles.COLOR_INPUT_FG)
        root.option_add("*TCombobox*Listbox*selectBackground", Styles.COLOR_ACCENT)
        root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
        Styles._bind_soft_widget_chrome(root)

    @staticmethod
    def _configure_frame_styles(style):
        # Frame Styles
        style.configure("Main.TFrame", background=Styles.COLOR_BG_MAIN)
        style.configure("Sidebar.TFrame", background=Styles.COLOR_BG_SIDEBAR)
        style.configure("SidebarCard.TFrame", background=Styles.COLOR_SIDEBAR_CARD_BG)
        style.configure("SidebarInner.TFrame", background=Styles.COLOR_SIDEBAR_CARD_INNER)
        style.configure("Toolbar.TFrame", background=Styles.COLOR_TOOLBAR_BG)
        style.configure("NavBar.TFrame", background=Styles.COLOR_DOC_TOOLBAR_BG)

    @staticmethod
    def _configure_label_styles(style):
        # Label Styles
        style.configure(
            "TLabel",
            background=Styles.COLOR_BG_MAIN,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_MAIN,
            padding=Styles.scale_padding(5)
        )
        style.configure(
            "Header.TLabel",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_HEADER,
            padding=Styles.scale_padding((12, 6))
        )
        style.configure(
            "SidebarTitle.TLabel",
            background=Styles.COLOR_SIDEBAR_CARD_BG,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(("Segoe UI", 22, "bold")),
            padding=Styles.scale_padding((12, 12, 12, 6))
        )
        style.configure(
            "SidebarHint.TLabel",
            background=Styles.COLOR_SIDEBAR_CARD_BG,
            foreground=Styles.COLOR_DIM,
            font=Styles.scale_font(("Segoe UI", 11, "bold")),
            padding=Styles.scale_padding((12, 0, 12, 4))
        )
        style.configure(
            "SidebarSection.TLabel",
            background=Styles.COLOR_SIDEBAR_CARD_BG,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(("Segoe UI", 16, "bold")),
            padding=Styles.scale_padding((12, 8, 12, 6))
        )
        style.configure(
            "Breadcrumb.TLabel",
            background=Styles.COLOR_TOOLBAR_BG,
            foreground=Styles.COLOR_DIM,
            font=Styles.FONT_BREADCRUMB,
            padding=Styles.scale_padding((15, 8))
        )

    @staticmethod
    def _configure_scrollbar_styles(style):
        # Scrollbar (Modern Flat)
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=Styles.COLOR_BG_SIDEBAR,
            darkcolor=Styles.COLOR_BG_SIDEBAR,
            lightcolor=Styles.COLOR_BG_SIDEBAR,
            troughcolor=Styles.COLOR_BG_MAIN,
            bordercolor=Styles.COLOR_BORDER,
            arrowcolor=Styles.COLOR_DIM,
            relief="flat",
            borderwidth=Styles.SOFT_EDGE_BORDER
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", Styles.COLOR_SELECTION_BG)]
        )

    @staticmethod
    def _configure_button_styles(style):
        # Navigation Button Styles (Sidebar)
        style.configure(
            "Nav.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 17, "bold")),
            borderwidth=1,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((18, 12)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "Nav.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("disabled", Styles.COLOR_BUTTON_BG), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_ACCENT), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )

        style.configure(
            "NavFlat.TButton",
            background=Styles.COLOR_DOC_TOOLBAR_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 17, "bold")),
            borderwidth=0,
            focuscolor=Styles.COLOR_DOC_TOOLBAR_BG,
            padding=Styles.scale_padding((18, 12)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "NavFlat.TButton",
            background=[
                ("active", Styles.COLOR_DOC_TOOLBAR_HOVER),
                ("disabled", Styles.COLOR_DOC_TOOLBAR_BG),
                ("pressed", Styles.COLOR_DOC_TOOLBAR_HOVER)
            ],
            foreground=[
                ("active", Styles.COLOR_BUTTON_FG_ACTIVE),
                ("disabled", Styles.COLOR_ACCENT),
                ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)
            ]
        )
        # Botón Añadir Proyecto (con altura ligeramente aumentada)
        style.configure(
            "AddProject.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 18, "bold")),  # Fuente más grande
            borderwidth=1,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((12, 12)),  # Padding vertical aumentado (antes era (18,12))
            relief="flat",
            anchor="center"
        )
        style.map(
            "AddProject.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("disabled", Styles.COLOR_BUTTON_BG), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_ACCENT), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )
        style.configure(
            "SidebarToggle.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 14, "bold")),
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((10, 10)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "SidebarToggle.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE), ("disabled", Styles.COLOR_BUTTON_BG)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_DIM)]
        )

        style.configure(
            "FullscreenToggle.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 14, "bold")),
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((10, 8)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "FullscreenToggle.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )

        # Toolbar Icon Button
        style.configure(
            "ToolbarIcon.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 14)),
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((10, 6)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "ToolbarIcon.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )

        style.configure(
            "ToolbarGroup.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 14)),
            borderwidth=0,
            focuscolor=Styles.COLOR_BUTTON_BG,
            padding=Styles.scale_padding((10, 6)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "ToolbarGroup.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE), ("disabled", Styles.COLOR_BUTTON_BG)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_DIM)]
        )

        style.configure(
            "DocToolbarFlat.TButton",
            background=Styles.COLOR_DOC_TOOLBAR_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.scale_font(("Segoe UI", 14)),
            borderwidth=0,
            focuscolor=Styles.COLOR_DOC_TOOLBAR_BG,
            padding=Styles.scale_padding((10, 6)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "DocToolbarFlat.TButton",
            background=[("active", Styles.COLOR_DOC_TOOLBAR_HOVER), ("pressed", Styles.COLOR_DOC_TOOLBAR_HOVER), ("disabled", Styles.COLOR_DOC_TOOLBAR_BG)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_DIM)]
        )

        # Action Button (Primary Call to Action)
        style.configure(
            "Action.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.FONT_BUTTON,
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            padding=Styles.scale_padding((18, 10)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "Action.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )

        # Secondary Action Button (Cancel/Back)
        style.configure(
            "Secondary.TButton",
            background=Styles.COLOR_BUTTON_BG,
            foreground=Styles.COLOR_BUTTON_FG,
            font=Styles.FONT_BUTTON,
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BUTTON_BORDER,
            lightcolor=Styles.COLOR_BUTTON_BORDER,
            darkcolor=Styles.COLOR_BUTTON_BORDER,
            padding=Styles.scale_padding((18, 10)),
            relief="flat",
            anchor="center"
        )
        style.map(
            "Secondary.TButton",
            background=[("active", Styles.COLOR_BUTTON_HOVER), ("disabled", Styles.COLOR_BUTTON_BG), ("pressed", Styles.COLOR_BUTTON_ACTIVE)],
            foreground=[("active", Styles.COLOR_BUTTON_FG_ACTIVE), ("disabled", Styles.COLOR_ACCENT), ("pressed", Styles.COLOR_BUTTON_FG_ACTIVE)]
        )

    @staticmethod
    def _configure_widget_styles(style):
        # Scale (Slider) Styles
        style.configure(
            "Horizontal.TScale",
            background=Styles.COLOR_BG_MAIN,
            troughcolor=Styles.COLOR_INPUT_BG,
            bordercolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_ACCENT,
            darkcolor=Styles.COLOR_ACCENT,
            sliderlength=Styles.scale_size(40),
            sliderthickness=Styles.scale_size(40),
            borderwidth=0
        )

        # Treeview Styles
        style.configure(
            "Treeview",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BORDER,
            lightcolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_BORDER,
            relief="flat",
            font=Styles.FONT_MAIN,
            rowheight=Styles.scale_size(40)
        )
        style.configure(
            "Treeview.Heading",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(("Segoe UI", 14, "bold")),
            borderwidth=Styles.SOFT_EDGE_BORDER,
            bordercolor=Styles.COLOR_BORDER,
            lightcolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_BORDER,
            relief="flat",
            padding=Styles.scale_padding((10, 10))
        )
        style.map(
            "Treeview",
            background=[('selected', Styles.COLOR_SELECTION_BG)],
            foreground=[('selected', '#ffffff')]
        )
        
        # Separator
        style.configure(
            "Horizontal.TSeparator",
            background=Styles.COLOR_SELECTION_BG
        )

        # LabelFrame
        style.configure(
            "TLabelframe",
            background=Styles.COLOR_BG_MAIN,
            bordercolor=Styles.COLOR_BORDER,
            lightcolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_BORDER,
            borderwidth=1,
            relief="solid"
        )
        style.configure(
            "TLabelframe.Label",
            background=Styles.COLOR_BG_MAIN,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_MAIN
        )
        style.configure(
            "Borderless.TLabelframe",
            background=Styles.COLOR_BG_MAIN,
            bordercolor=Styles.COLOR_BG_MAIN,
            lightcolor=Styles.COLOR_BG_MAIN,
            darkcolor=Styles.COLOR_BG_MAIN,
            borderwidth=0,
            relief="flat"
        )
        style.configure(
            "Borderless.TLabelframe.Label",
            background=Styles.COLOR_BG_MAIN,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_MAIN
        )

        # Checkbutton
        style.configure(
            "TCheckbutton",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(("Segoe UI", 18, "bold")),
            focuscolor=Styles.COLOR_BG_SIDEBAR,
            padding=Styles.scale_padding(10)
        )
        style.map(
            "TCheckbutton",
            background=[("active", Styles.COLOR_BG_SIDEBAR)],
            foreground=[("active", Styles.COLOR_ACCENT)]
        )

        # Combobox Styles
        style.configure(
            "TCombobox",
            background=Styles.COLOR_INPUT_BG, 
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            bordercolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_INPUT_BG,
            arrowcolor=Styles.COLOR_DIM,
            padding=Styles.SOFT_EDGE_PADDING,
            relief="flat",
            borderwidth=Styles.SOFT_EDGE_BORDER
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectforeground=[("readonly", Styles.COLOR_FG_TEXT)],
            background=[("readonly", Styles.COLOR_INPUT_BG)],
            foreground=[("readonly", Styles.COLOR_FG_TEXT)]
        )
        style.configure(
            "Borderless.TCombobox",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            bordercolor=Styles.COLOR_INPUT_BG,
            darkcolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_INPUT_BG,
            arrowcolor=Styles.COLOR_DIM,
            padding=Styles.SOFT_EDGE_PADDING,
            relief="flat",
            borderwidth=0
        )
        style.map(
            "Borderless.TCombobox",
            fieldbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectforeground=[("readonly", Styles.COLOR_FG_TEXT)],
            background=[("readonly", Styles.COLOR_INPUT_BG)],
            foreground=[("readonly", Styles.COLOR_FG_TEXT)]
        )

        style.configure(
            "Borderless.Treeview",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            borderwidth=0,
            bordercolor=Styles.COLOR_INPUT_BG,
            relief="flat",
            font=Styles.FONT_MAIN,
            rowheight=Styles.scale_size(40)
        )
        style.map(
            "Borderless.Treeview",
            background=[('selected', Styles.COLOR_SELECTION_BG)],
            foreground=[('selected', '#ffffff')]
        )

        style.configure(
            "TEntry",
            fieldbackground=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            bordercolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_INPUT_BG,
            insertcolor=Styles.COLOR_INPUT_FG,
            padding=Styles.SOFT_EDGE_PADDING,
            relief="flat",
            borderwidth=Styles.SOFT_EDGE_BORDER
        )
        style.map(
            "TEntry",
            fieldbackground=[("focus", Styles.COLOR_INPUT_BG)],
            foreground=[("focus", Styles.COLOR_FG_TEXT)]
        )

    @staticmethod
    def configure_styles(root):
        """
        Configures the ttk styles for the application.
        
        Args:
            root: The root Tkinter window.
        """
        style = ttk.Style(root)
        style.theme_use('clam') 
        
        # Initialize base config
        Styles._init_base_config(style, root)
        
        # Configure specific style groups
        Styles._configure_frame_styles(style)
        Styles._configure_label_styles(style)
        Styles._configure_scrollbar_styles(style)
        Styles._configure_button_styles(style)
        Styles._configure_widget_styles(style)
