import tkinter as tk
from tkinter import ttk
from src.ui.styles import Styles
from src.ui.tabs.code_view import CodeView
from src.ui.tabs.doc_view import DocView
from src.ui.tabs.console_view import ConsoleView

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

        # Initialize with Code View
        self.show_code_tab()

    def _create_navbar(self):
        """Creates the top navigation bar."""
        self.navbar = ttk.Frame(self, style="Sidebar.TFrame")
        self.navbar.grid(row=0, column=0, sticky="ew")

        # Navigation Buttons Container
        # Buttons should take up the whole width
        self.nav_buttons_frame = ttk.Frame(self.navbar, style="Sidebar.TFrame")
        self.nav_buttons_frame.pack(side="left", fill="x", expand=True) # expand to fill navbar
        
        # Configure columns to distribute space equally (33% - 33% - 33%)
        self.nav_buttons_frame.columnconfigure(0, weight=1)
        self.nav_buttons_frame.columnconfigure(1, weight=1)
        self.nav_buttons_frame.columnconfigure(2, weight=1)

        # Tab Buttons
        self.btn_code = ttk.Button(
            self.nav_buttons_frame,
            text="Código",
            style="Nav.TButton",
            command=self.controller.show_code_view
        )
        self.btn_code.grid(row=0, column=0, sticky="nsew", padx=0, pady=0) 

        self.btn_docs = ttk.Button(
            self.nav_buttons_frame,
            text="Documentación",
            style="Nav.TButton",
            command=self.controller.show_docs_view
        )
        self.btn_docs.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        self.btn_console = ttk.Button(
            self.nav_buttons_frame,
            text="Consola",
            style="Nav.TButton",
            command=self.controller.show_console_view
        )
        self.btn_console.grid(row=0, column=2, sticky="nsew", padx=0, pady=0)

    def _create_content_area(self):
        """Creates the area where tab content will be displayed."""
        self.content_frame = ttk.Frame(self, style="Main.TFrame")
        self.content_frame.grid(row=1, column=0, sticky="nsew")

        # Instantiate views
        self.code_view = CodeView(self.content_frame)
        self.doc_view = DocView(self.content_frame)
        self.console_view = ConsoleView(self.content_frame)

    def show_code_tab(self):
        """Displays the Code view."""
        self._clear_content()
        self.code_view.pack(fill="both", expand=True)
        # Update button states (visual feedback)
        self.btn_code.state(["pressed", "disabled"]) 
        self.btn_docs.state(["!pressed", "!disabled"])
        self.btn_console.state(["!pressed", "!disabled"])
        self.update_idletasks()

    def show_docs_tab(self):
        """Displays the Documentation view."""
        self._clear_content()
        self.doc_view.pack(fill="both", expand=True)
         # Update button states
        self.btn_code.state(["!pressed", "!disabled"])
        self.btn_docs.state(["pressed", "disabled"])
        self.btn_console.state(["!pressed", "!disabled"])
        self.update_idletasks()

    def show_console_tab(self):
        """Displays the Console view."""
        self._clear_content()
        self.console_view.pack(fill="both", expand=True)
        # Update button states
        self.btn_code.state(["!pressed", "!disabled"])
        self.btn_docs.state(["!pressed", "!disabled"])
        self.btn_console.state(["pressed", "disabled"])
        self.update_idletasks()

    def _clear_content(self):
        """Unpacks all views from the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.pack_forget()
