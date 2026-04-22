import tkinter as tk
from tkinter import ttk
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip
from src.ui.tabs.code_view import CodeView
from src.ui.tabs.doc_view import DocView
from src.ui.tabs.database_view import DatabaseView

class MainLayout(ttk.Frame):
    """
    The main container layout for the application.
    It holds the custom navigation bar and the content frame.
    """
    def __init__(self, parent, controller):
        """
        Initialize the MainLayout.

        Args:
            parent: The parent widget (usually the main Tkinter window).
            controller: The logic controller instance.
        """
        super().__init__(parent, style="Main.TFrame")
        self.controller = controller
        
        # Make the layout expand to fill the window
        self.pack(fill="both", expand=True)

        # Grid Configuration
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0) # Navbar fixed height
        self.rowconfigure(1, weight=1) # Content expands

        self._create_navbar()
        self._create_content_area()
        self.is_navbar_visible = True
        self._responsive_after_id = None
        self.bind("<Configure>", self._on_layout_resize)

        # Initialize with Documentation View
        self.show_docs_tab()

    def _create_navbar(self):
        """Creates the top navigation bar."""
        self.navbar = tk.Frame(self, bg=Styles.COLOR_DOC_TOOLBAR_BG, bd=0, highlightthickness=0)
        self.navbar.grid(row=0, column=0, sticky="ew")

        # Navigation Buttons Container
        # Buttons should take up the whole width
        self.nav_buttons_frame = tk.Frame(self.navbar, bg=Styles.COLOR_DOC_TOOLBAR_BG, bd=0, highlightthickness=0)
        self.nav_buttons_frame.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        # Configure columns to distribute space equally
        self.nav_buttons_frame.columnconfigure(0, weight=1)
        self.nav_buttons_frame.columnconfigure(1, weight=1)

        self.nav_tabs = {}
        self._create_nav_tab(0, "docs", "Documentación", self.controller.show_docs_view)
        self._create_nav_tab(1, "code", "Código", self.controller.show_code_view)

    def _create_nav_tab(self, column, key, text, command):
        tab_frame = tk.Frame(
            self.nav_buttons_frame,
            bg=Styles.COLOR_DOC_TOOLBAR_BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2"
        )
        tab_frame.grid(row=0, column=column, sticky="nsew", padx=0, pady=0)
    
        tab_label = tk.Label(
            tab_frame,
            text=text,
            bg=Styles.COLOR_DOC_TOOLBAR_BG,
            fg=Styles.COLOR_BUTTON_FG,
            font=("Segoe UI", 17, "bold"),
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2"
        )
        tab_label.pack(fill="both", expand=True)
    
        for widget in (tab_frame, tab_label):
            widget.bind("<Button-1>", lambda event, cmd=command: cmd())
            widget.bind("<Enter>", lambda event, name=key: self._set_nav_hover(name, True))
            widget.bind("<Leave>", lambda event, name=key: self._set_nav_hover(name, False))
    
        self.nav_tabs[key] = {"frame": tab_frame, "label": tab_label}

    def _on_layout_resize(self, event=None):
        if event is not None and event.widget is not self:
            return

        if self._responsive_after_id:
            self.after_cancel(self._responsive_after_id)
        self._responsive_after_id = self.after(40, self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self._responsive_after_id = None
        width = max(self.winfo_width(), 1)

        if width < 820:
            font_size = Styles.scale_size(13)
            padx = Styles.scale_size(12)
            pady = Styles.scale_size(8)
            outer_padx = Styles.scale_size(8)
            outer_pady = Styles.scale_size(6)
        elif width < 1080:
            font_size = Styles.scale_size(15)
            padx = Styles.scale_size(14)
            pady = Styles.scale_size(10)
            outer_padx = Styles.scale_size(10)
            outer_pady = Styles.scale_size(8)
        else:
            font_size = Styles.scale_size(17)
            padx = Styles.scale_size(18)
            pady = Styles.scale_size(12)
            outer_padx = Styles.scale_size(12)
            outer_pady = Styles.scale_size(10)

        self.nav_buttons_frame.pack_configure(padx=outer_padx, pady=outer_pady)
        for tab in self.nav_tabs.values():
            tab["label"].configure(
                font=("Segoe UI", font_size, "bold"),
                padx=padx,
                pady=pady
            )

    def _set_nav_hover(self, key, is_hovered):
        tab = self.nav_tabs.get(key)
        if not tab:
            return

        if getattr(self, "_active_nav_tab", None) == key:
            bg = Styles.COLOR_DOC_TOOLBAR_BG
            fg = Styles.COLOR_ACCENT
        else:
            bg = Styles.COLOR_DOC_TOOLBAR_HOVER if is_hovered else Styles.COLOR_DOC_TOOLBAR_BG
            fg = Styles.COLOR_BUTTON_FG_ACTIVE if is_hovered else Styles.COLOR_BUTTON_FG

        tab["frame"].configure(bg=bg)
        tab["label"].configure(bg=bg, fg=fg)

    def _set_active_nav_tab(self, key):
        self._active_nav_tab = key
        for tab_key in self.nav_tabs:
            self._set_nav_hover(tab_key, False)

    def _create_content_area(self):
        """Creates the area where tab content will be displayed."""
        self.content_frame = tk.Frame(self, bg=Styles.COLOR_BG_MAIN, bd=0, highlightthickness=0)
        self.content_frame.grid(row=1, column=0, sticky="nsew")

        # Instantiate views
        self.code_view = CodeView(self.content_frame)
        self.doc_view = DocView(self.content_frame)
        self.database_view = DatabaseView(self.content_frame)

    def show_code_tab(self):
        """Displays the Code view."""
        self._clear_content()
        self.doc_view.on_tab_hidden()
        self.set_navbar_visible(True)
        self.code_view.pack(fill="both", expand=True)
        self._set_active_nav_tab("code")
        self.update_idletasks()

    def show_docs_tab(self):
        """Displays the Documentation view."""
        self._clear_content()
        self.doc_view.pack(fill="both", expand=True)
        self.doc_view.on_tab_shown()
        self._set_active_nav_tab("docs")
        self.update_idletasks()

    def show_database_tab(self):
        """Displays the Database view."""
        self._clear_content()
        self.doc_view.on_tab_hidden()
        self.set_navbar_visible(True)
        self.database_view.pack(fill="both", expand=True)
        self._set_active_nav_tab("database")
        self.update_idletasks()

    def _clear_content(self):
        """Unpacks all views from the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.pack_forget()

    def set_navbar_visible(self, is_visible):
        """Shows or hides the top navigation bar."""
        if self.is_navbar_visible == is_visible:
            return

        if is_visible:
            self.navbar.grid()
        else:
            self.navbar.grid_remove()

        self.is_navbar_visible = is_visible
        self.update_idletasks()
