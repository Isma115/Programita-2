import tkinter as tk
import os
from src.ui.styles import Styles
from src.ui.layout import MainLayout
from src.logic.controller import Controller

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

        # 1. Configure Styles
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
        
        # 2. Initialize Logic
        self.controller = Controller(self)
        self.arbitrary_step = self.controller.config_manager.get_arbitrary_step()
        
        # Attach controller to root for easy access by views via winfo_toplevel()
        self.root.controller = self.controller

        # 3. Initialize UI (Layout)
        # Pass the controller to the layout so buttons can trigger actions
        self.layout = MainLayout(self.root, self.controller)

        # 4. Auto-load project
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

    def run(self):
        """
        Start the main event loop.
        """
        self.root.mainloop()
