import tkinter as tk
import os
from src.ui.styles import Styles
from src.ui.layout import MainLayout
from src.logic.controller import Controller
from src.ui.search_overlay import SearchOverlay

class Application:
    """
    The main application class.
    Assemble the UI and Logic components.
    """
    def __init__(self):
        """
        Initialize the Application.
        """
        self.root = tk.Tk()
        self.root.title("Programita 2 - Modular UI")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # Initialize Logic (Controller loads config and updates Style constants)
        self.controller = Controller(self)
        self.arbitrary_step = self.controller.config_manager.get_arbitrary_step()

        # Attach controller to root for easy access by views via winfo_toplevel()
        if not hasattr(self.root, 'controller'):
            self.root.controller = self.controller

        # Configure Styles AFTER loading config (so theme colors are correct)
        Styles.configure_styles(self.root)

        # Fullscreen / Maximized
        # User requested "Windowed mode but occupying the full screen"
        # On macOS, 'zoomed' attribute simulates the green maximize button.
        try:
             # Try macOS specific maximize
            self.root.attributes('-zoomed', True)
            self.root.attributes('-fullscreen', False) # Ensure fullscreen is off
        except tk.TclError:
            # Fallback for other systems
            self.root.state('zoomed')

        # Initialize UI (Layout)
        # Pass the controller to the layout so buttons can trigger actions
        self.layout = MainLayout(self.root, self.controller)

        # --- Global Hotkey: Ctrl+F / Cmd+F → Search Overlay ---
        self._search_overlay = None
        self.root.bind("<Control-f>", self._open_search_overlay)
        self.root.bind("<Control-F>", self._open_search_overlay)
        self.root.bind("<Command-f>", self._open_search_overlay)
        self.root.bind("<Command-F>", self._open_search_overlay)

        # Auto-load project
        dirs = self.controller.config_manager.get_project_directories()
        if dirs:
            idx = self.controller.config_manager.get_current_project_index()
            idx = idx % len(dirs)
            if os.path.exists(dirs[idx]):
                self.controller.switch_to_project(idx)
        else:
            last_project = self.controller.config_manager.get_last_project()
            if last_project and os.path.exists(last_project):
                self.controller.load_project_folder(last_project)

    def _open_search_overlay(self, event=None):
        """Opens the global search overlay if not already open."""
        # Check if overlay exists and is still alive
        if self._search_overlay and self._search_overlay.winfo_exists():
            self._search_overlay.entry.focus_force()
            return "break"
        self._search_overlay = SearchOverlay(self.root, self.controller)
        return "break"

    def run(self):
        """
        Start the main event loop.
        """
        self.root.mainloop()
