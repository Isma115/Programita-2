import tkinter as tk
from tkinter import messagebox, simpledialog
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
        self.root.title("Programita 2")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        initial_w = min(max(int(screen_w * 0.88), 980), screen_w)
        initial_h = min(max(int(screen_h * 0.85), 720), screen_h)
        pos_x = max((screen_w - initial_w) // 2, 0)
        pos_y = max((screen_h - initial_h) // 3, 0)
        self.root.geometry(f"{initial_w}x{initial_h}+{pos_x}+{pos_y}")
        self.root.minsize(760, 520)

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
        self._create_menu_bar()
        Styles.apply_soft_widget_chrome(self.root)

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

        # Ensure pynput listeners are stopped before Tk destroys its window
        # to prevent the GIL / PyEval_RestoreThread fatal crash on macOS.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_menu_bar(self):
        """Creates the native menu bar for global options."""
        self.include_project_tree_var = tk.BooleanVar(
            value=self.controller.config_manager.get_include_project_tree()
        )
        self.export_prompts_as_folder_var = tk.BooleanVar(
            value=self.controller.config_manager.get_export_prompts_as_folder()
        )

        self.menu_bar = tk.Menu(self.root)
        self.options_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.options_menu.add_checkbutton(
            label="Incluir árbol de proyecto",
            variable=self.include_project_tree_var,
            command=self._on_toggle_include_project_tree
        )
        self.options_menu.add_checkbutton(
            label="Exportar prompts a carpeta codigo",
            variable=self.export_prompts_as_folder_var,
            command=self._on_toggle_export_prompts_as_folder
        )
        self.options_menu.add_command(
            label="Configurar máximo de Mín. Ficheros...",
            command=self._on_configure_code_file_limit_max
        )
        self.options_menu.add_command(
            label="Configurar mínimo de búsqueda Arbitrary...",
            command=self._on_configure_arbitrary_search_min_chars
        )
        self.options_menu.add_command(
            label="Configurar máximo de búsqueda Arbitrary...",
            command=self._on_configure_arbitrary_search_max_chars
        )
        self.options_menu.add_separator()
        self.options_menu.add_command(
            label="Eliminar comentarios [MODIFICACIÓN]",
            command=self._on_remove_modification_comments
        )
        self.menu_bar.add_cascade(label="Opciones", menu=self.options_menu)
        self.root.config(menu=self.menu_bar)

    def _on_toggle_include_project_tree(self):
        """Persists the menu option for including the project tree in prompts."""
        self.controller.config_manager.set_include_project_tree(
            self.include_project_tree_var.get()
        )

    def _on_toggle_export_prompts_as_folder(self):
        """Persists whether Code prompts are exported as a folder."""
        self.controller.config_manager.set_export_prompts_as_folder(
            self.export_prompts_as_folder_var.get()
        )

    def _on_configure_code_file_limit_max(self):
        """Lets the user configure the max value for the Code View file-limit slider."""
        current_max = self.controller.config_manager.get_file_limit_slider_max()
        new_max = simpledialog.askinteger(
            "Opciones",
            "Introduce el nuevo máximo para el slider 'Mín. Ficheros':",
            initialvalue=current_max,
            minvalue=20,
            parent=self.root
        )
        if new_max is None:
            return

        self.controller.config_manager.set_file_limit_slider_max(new_max)

        if hasattr(self.layout, "code_view"):
            self.layout.code_view.apply_file_limit_slider_settings(refresh=True)

    def _on_configure_arbitrary_search_min_chars(self):
        """Lets the user configure the minimum substring length for Arbitrary search."""
        config = self.controller.config_manager
        current_min = config.get_arbitrary_search_min_chars()
        current_max = config.get_arbitrary_search_max_chars()
        new_min = simpledialog.askinteger(
            "Opciones",
            "Introduce el mínimo de caracteres para la búsqueda Arbitrary:",
            initialvalue=current_min,
            minvalue=1,
            parent=self.root
        )
        if new_min is None:
            return
        if new_min > current_max:
            messagebox.showwarning(
                "Opciones",
                f"El mínimo no puede ser mayor que el máximo actual ({current_max})."
            )
            return

        config.set_arbitrary_search_min_chars(new_min)

    def _on_configure_arbitrary_search_max_chars(self):
        """Lets the user configure the maximum substring length for Arbitrary search."""
        config = self.controller.config_manager
        current_min = config.get_arbitrary_search_min_chars()
        current_max = config.get_arbitrary_search_max_chars()
        new_max = simpledialog.askinteger(
            "Opciones",
            "Introduce el máximo de caracteres para la búsqueda Arbitrary:",
            initialvalue=current_max,
            minvalue=1,
            parent=self.root
        )
        if new_max is None:
            return
        if new_max < current_min:
            messagebox.showwarning(
                "Opciones",
                f"El máximo no puede ser menor que el mínimo actual ({current_min})."
            )
            return

        config.set_arbitrary_search_max_chars(new_max)

    def _on_remove_modification_comments(self):
        """Removes all comments containing [MODIFICACIÓN] from the loaded project."""
        if not self.controller.project_manager.current_project_path:
            messagebox.showwarning("Opciones", "No hay ningún proyecto cargado.")
            return

        confirmed = messagebox.askyesno(
            "Eliminar comentarios [MODIFICACIÓN]",
            "Se eliminarán de todo el proyecto cargado todos los comentarios que contengan [MODIFICACIÓN].\n\n¿Continuar?"
        )
        if not confirmed:
            return

        changed_files, removed_comments, errors = self.controller.remove_modification_comments_from_project()

        if hasattr(self.layout, "code_view"):
            self.layout.code_view.refresh_file_list()

        if errors:
            messagebox.showerror(
                "Opciones",
                "La limpieza terminó con errores:\n\n" + "\n".join(errors[:10])
            )
            return

        messagebox.showinfo(
            "Opciones",
            f"Limpieza completada.\n\nFicheros modificados: {changed_files}\nComentarios eliminados: {removed_comments}"
        )

    def _on_close(self):
        """Gracefully stop background listeners before destroying the window."""
        try:
            if hasattr(self.controller, 'hotkey_listener'):
                self.controller.hotkey_listener.stop()
        except Exception:
            pass
        self.root.destroy()

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
