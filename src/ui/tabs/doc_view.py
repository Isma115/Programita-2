import tkinter as tk
from tkinter import ttk

class DocView(ttk.Frame):
    """
    The view responsible for displaying the 'Documentation' section.
    Currently a placeholder for future functionality.
    """
    def __init__(self, parent):
        """
        Initialize the DocView.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent, style="Main.TFrame")

        # Grid configuration for centering
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Placeholder Content
        self.label = ttk.Label(
            self, 
            text="Vista de Documentación\n(Funcionalidad pendiente)", 
            style="TLabel",
            justify="center",
            font=("Segoe UI", 16)
        )
        self.label.grid(row=0, column=0)
