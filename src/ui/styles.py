import tkinter as tk
from tkinter import ttk

class Styles:
    """
    Handles the configuration of application styles, colors, and fonts.
    """
    
    # Modern Dark Palette
    COLOR_BG_MAIN = "#1e1f22"       # Deep dark gray (Discord-like)
    COLOR_BG_SIDEBAR = "#2b2d31"    # Lighter gray for sidebars
    COLOR_FG_TEXT = "#f2f3f5"       # Almost white text
    COLOR_ACCENT = "#5865F2"        # Vibrant Blurple (Modern Accent)
    COLOR_ACCENT_HOVER = "#4752c4"  # Darker blurple for hover
    COLOR_BORDER = "#2b2d31"        # Matches sidebar for seamless look
    COLOR_DIM = "#949ba4"           # Dimmed text
    COLOR_PANE_DIVIDER = "#6b7280"  # Higher-contrast divider for draggable panes
    
    # Input/List Colors
    COLOR_INPUT_BG = "#313338"      # Slightly lighter than sidebar
    COLOR_INPUT_FG = "#ffffff"      # White input text
    COLOR_SELECTION_BG = "#404249"  # Selection background
    
    # Fonts (Larger and cleaner)
    FONT_FAMILY = "Segoe UI" # Fallback to standard if needed
    FONT_MAIN = ("Segoe UI", 18, "bold")        
    FONT_HEADER = ("Segoe UI", 20, "bold")
    FONT_CODE = ("Consolas", 14)       
    FONT_BUTTON = ("Segoe UI", 18, "bold")

    @staticmethod
    def configure_styles(root):
        """
        Configures the ttk styles for the application.
        
        Args:
            root: The root Tkinter window.
        """
        style = ttk.Style(root)
        style.theme_use('clam') 

        # Configure Main Window background
        root.configure(bg=Styles.COLOR_BG_MAIN)

        # Dropdown/Combobox popups handling
        root.option_add("*TCombobox*Listbox*Background", Styles.COLOR_INPUT_BG)
        root.option_add("*TCombobox*Listbox*Foreground", Styles.COLOR_INPUT_FG)
        root.option_add("*TCombobox*Listbox*selectBackground", Styles.COLOR_ACCENT)
        root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")

        # Frame Styles
        style.configure("Main.TFrame", background=Styles.COLOR_BG_MAIN)
        style.configure("Sidebar.TFrame", background=Styles.COLOR_BG_SIDEBAR)

        # Label Styles
        style.configure(
            "TLabel",
            background=Styles.COLOR_BG_MAIN,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_MAIN,
            padding=5
        )
        style.configure(
            "Header.TLabel",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_HEADER,
            padding=(15, 10)
        )

        # Scrollbar (Modern Flat)
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=Styles.COLOR_BG_SIDEBAR,
            darkcolor=Styles.COLOR_BG_SIDEBAR,
            lightcolor=Styles.COLOR_BG_SIDEBAR,
            troughcolor=Styles.COLOR_BG_MAIN,
            bordercolor=Styles.COLOR_BG_MAIN,
            arrowcolor=Styles.COLOR_DIM,
            relief="flat",
            borderwidth=0
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", Styles.COLOR_SELECTION_BG)]
        )

        # Navigation Button Styles (Sidebar)
        style.configure(
            "Nav.TButton",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_DIM,
            font=Styles.FONT_BUTTON,
            borderwidth=1,
            bordercolor="#3a3d44",
            lightcolor="#343840",
            darkcolor="#2f3238",
            focuscolor=Styles.COLOR_BG_SIDEBAR,
            padding=(20, 15),
            relief="solid",
            anchor="center" # Center the text
        )
        style.map(
            "Nav.TButton",
            background=[("active", Styles.COLOR_SELECTION_BG), ("disabled", Styles.COLOR_BG_SIDEBAR), ("pressed", Styles.COLOR_BG_SIDEBAR)],
            bordercolor=[("active", "#515866"), ("pressed", "#4a5160"), ("disabled", "#353840")],
            foreground=[("active", "#ffffff"), ("disabled", Styles.COLOR_ACCENT), ("pressed", Styles.COLOR_ACCENT)]
        )

        style.configure(
            "SidebarToggle.TButton",
            background="#5f636b",
            foreground="#f2f3f5",
            font=("Segoe UI", 14, "bold"),
            borderwidth=1,
            bordercolor="#727780",
            lightcolor="#79808a",
            darkcolor="#565b64",
            focuscolor="#5f636b",
            padding=(8, 8),
            relief="solid",
            anchor="center"
        )
        style.map(
            "SidebarToggle.TButton",
            background=[("active", "#727780"), ("pressed", "#52565e"), ("disabled", "#4f5258")],
            bordercolor=[("active", "#8b919a"), ("pressed", "#5f636b"), ("disabled", "#4f5258")],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff"), ("disabled", "#c7c9ce")]
        )

        style.configure(
            "FullscreenToggle.TButton",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=("Segoe UI", 14, "bold"),
            borderwidth=1,
            bordercolor="#3a3d44",
            lightcolor="#343840",
            darkcolor="#2f3238",
            focuscolor=Styles.COLOR_BG_SIDEBAR,
            padding=(10, 8),
            relief="solid",
            anchor="center"
        )
        style.map(
            "FullscreenToggle.TButton",
            background=[("active", Styles.COLOR_SELECTION_BG), ("pressed", Styles.COLOR_BG_SIDEBAR)],
            bordercolor=[("active", "#515866"), ("pressed", "#4a5160")],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")]
        )

        # Action Button (Primary Call to Action)
        style.configure(
            "Action.TButton",
            background=Styles.COLOR_ACCENT,
            foreground="#ffffff",
            font=Styles.FONT_BUTTON,
            borderwidth=1,
            bordercolor="#6f7cf7",
            lightcolor="#7a86fb",
            darkcolor="#4d59d9",
            padding=(20, 10),
            relief="solid",
            anchor="center"
        )
        style.map(
            "Action.TButton",
            background=[("active", Styles.COLOR_ACCENT_HOVER), ("pressed", Styles.COLOR_ACCENT)],
            bordercolor=[("active", "#8d98ff"), ("pressed", "#616df3")]
        )

        # Secondary Action Button (Cancel/Back - Matches Action geometry)
        style.configure(
            "Secondary.TButton",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_DIM,
            font=Styles.FONT_BUTTON,
            borderwidth=1,
            bordercolor="#3a3d44",
            lightcolor="#343840",
            darkcolor="#2f3238",
            padding=(20, 10), # Matches Action.TButton
            relief="solid",
            anchor="center"
        )
        style.map(
            "Secondary.TButton",
            background=[("active", Styles.COLOR_SELECTION_BG), ("disabled", Styles.COLOR_BG_SIDEBAR), ("pressed", Styles.COLOR_BG_SIDEBAR)],
            bordercolor=[("active", "#515866"), ("pressed", "#4a5160"), ("disabled", "#353840")],
            foreground=[("active", "#ffffff"), ("disabled", Styles.COLOR_ACCENT), ("pressed", Styles.COLOR_ACCENT)]
        )
        
        # Scale (Slider) Styles - Cleaner
        style.configure(
            "Horizontal.TScale",
            background=Styles.COLOR_BG_MAIN,
            troughcolor=Styles.COLOR_INPUT_BG,
            bordercolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_ACCENT,
            darkcolor=Styles.COLOR_ACCENT,
            sliderlength=40,   # Bigger handle
            sliderthickness=40, # Much thicker track
            borderwidth=0
        )

        # Treeview Styles
        style.configure(
            "Treeview",
            background=Styles.COLOR_INPUT_BG,
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            borderwidth=0,
            relief="flat",
            font=Styles.FONT_MAIN,
            rowheight=55 # Even more room for larger bold font
        )
        style.configure(
            "Treeview.Heading",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=("Segoe UI", 14, "bold"),
            borderwidth=0,
            relief="flat",
            padding=(10, 10)
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
            borderwidth=1,
            relief="solid"
        )
        style.configure(
            "TLabelframe.Label",
            background=Styles.COLOR_BG_MAIN,
            foreground=Styles.COLOR_FG_TEXT,
            font=Styles.FONT_MAIN
        )

        # Checkbutton
        style.configure(
            "TCheckbutton",
            background=Styles.COLOR_BG_SIDEBAR,
            foreground=Styles.COLOR_FG_TEXT,
            font=("Segoe UI", 18, "bold"), # Larger and bolder
            focuscolor=Styles.COLOR_BG_SIDEBAR,
            padding=10
        )
        style.map(
            "TCheckbutton",
            background=[("active", Styles.COLOR_BG_SIDEBAR)],
            foreground=[("active", Styles.COLOR_ACCENT)]
        )



        # Combobox Styles (Matching the Theme)
        style.configure(
            "TCombobox",
            background=Styles.COLOR_INPUT_BG, 
            foreground=Styles.COLOR_FG_TEXT,
            fieldbackground=Styles.COLOR_INPUT_BG,
            bordercolor=Styles.COLOR_BORDER,
            darkcolor=Styles.COLOR_INPUT_BG,
            lightcolor=Styles.COLOR_INPUT_BG,
            arrowcolor=Styles.COLOR_DIM,
            padding=5,
            relief="flat",
            borderwidth=0
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectbackground=[("readonly", Styles.COLOR_INPUT_BG)],
            selectforeground=[("readonly", Styles.COLOR_FG_TEXT)],
            background=[("readonly", Styles.COLOR_INPUT_BG)],
            foreground=[("readonly", Styles.COLOR_FG_TEXT)]
        )
