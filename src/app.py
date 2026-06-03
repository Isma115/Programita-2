import tkinter as tk
from tkinter import messagebox, simpledialog
from datetime import datetime
import os
from src.ui.styles import Styles
from src.ui.layout import MainLayout
from src.logic.controller import Controller
from src.ui.search_overlay import SearchOverlay
from src.logic.app_paths import bundled_path

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
        self._set_app_icon()
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
        self.root.app_instance = self

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
        self._hotkey_warning_scheduled = False
        self.root.after(250, self._show_hotkey_startup_warning_if_needed)

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

    def _show_hotkey_startup_warning_if_needed(self):
        """Shows a visible warning when the global hotkey backend could not start cleanly."""
        if getattr(self, "_hotkey_warning_scheduled", False):
            return
        self._hotkey_warning_scheduled = True

        listener = getattr(getattr(self, "controller", None), "hotkey_listener", None)
        if listener is None or not hasattr(listener, "has_startup_issues"):
            return
        if not listener.has_startup_issues():
            return

        issues = listener.get_startup_issue_summary()
        message = (
            "La captura global de hotkeys no arrancó del todo en esta build.\n\n"
            f"{issues}\n\n"
            "Si acabas de recompilar la app, vuelve a autorizar esta copia exacta en "
            "Privacidad y seguridad > Accesibilidad y Monitorización de entrada."
        )
        messagebox.showwarning("Hotkeys globales", message)

    def _set_app_icon(self):
        """Sets the main app icon from assets/icons/app_icon.png when available."""
        icon_path = bundled_path("assets", "icons", "app_icon.png")
        if not os.path.exists(icon_path):
            return
        try:
            self._app_icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self._app_icon_image)
        except tk.TclError:
            # Some environments do not support custom window icons.
            pass

    def _create_menu_bar(self):
        """Creates the native menu bar for global options."""
        current_return_files = self.controller.config_manager.get_return_files()
        current_return_chunks = self.controller.config_manager.get_return_chunks()
        current_return_regions = self.controller.config_manager.get_return_regions()
        if current_return_files and (current_return_chunks or current_return_regions):
            current_return_chunks = False
            current_return_regions = False
            self.controller.config_manager.set_return_chunks(False)
            self.controller.config_manager.set_return_regions(False)
        elif current_return_chunks and current_return_regions:
            current_return_regions = False
            self.controller.config_manager.set_return_regions(False)

        self.output_return_files_var = tk.BooleanVar(value=current_return_files)
        self.output_return_chunks_var = tk.BooleanVar(value=current_return_chunks)
        self.output_return_regions_var = tk.BooleanVar(value=current_return_regions)
        self.include_project_tree_var = tk.BooleanVar(
            value=self.controller.config_manager.get_include_project_tree()
        )
        self.export_prompts_as_folder_var = tk.BooleanVar(
            value=self.controller.config_manager.get_export_prompts_as_folder()
        )
        self.remember_last_main_view_var = tk.BooleanVar(
            value=self.controller.config_manager.get_remember_last_main_view()
        )
        self.clever_injection_var = tk.BooleanVar(
            value=self.controller.config_manager.get_clever_injection_enabled()
        )
        self.doc_autosave_var = tk.BooleanVar(
            value=self.controller.config_manager.get_doc_autosave_enabled()
        )
        self.auto_region_sections_var = tk.BooleanVar(
            value=self.controller.config_manager.get_auto_region_sections_enabled()
        )

        self.menu_bar = tk.Menu(self.root)
        self.output_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.output_menu.add_checkbutton(
            label="Devolver archivos",
            variable=self.output_return_files_var,
            command=self._on_toggle_output_return_files
        )
        self.output_menu.add_checkbutton(
            label="Devolver trozos",
            variable=self.output_return_chunks_var,
            command=self._on_toggle_output_return_chunks
        )
        self.output_menu.add_checkbutton(
            label="Devolver regiones",
            variable=self.output_return_regions_var,
            command=self._on_toggle_output_return_regions
        )
        self.configure_params_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.configure_params_menu.add_command(
            label="Configurar Mín. Ficheros...",
            command=self._on_configure_code_file_limit
        )
        self.configure_params_menu.add_command(
            label="Configurar Máx. Ficheros...",
            command=self._on_configure_code_max_file_limit
        )
        self.configure_params_menu.add_command(
            label="Configurar mínimo de búsqueda Arbitrary...",
            command=self._on_configure_arbitrary_search_min_chars
        )
        self.configure_params_menu.add_command(
            label="Configurar máximo de búsqueda Arbitrary...",
            command=self._on_configure_arbitrary_search_max_chars
        )
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
        self.options_menu.add_checkbutton(
            label="Recordar última vista (Código/Documentación/Base de datos)",
            variable=self.remember_last_main_view_var,
            command=self._on_toggle_remember_last_main_view
        )
        self.options_menu.add_checkbutton(
            label="Inyección inteligente",
            variable=self.clever_injection_var,
            command=self._on_toggle_clever_injection
        )
        self.options_menu.add_checkbutton(
            label="Autoguardado",
            variable=self.doc_autosave_var,
            command=self._on_toggle_doc_autosave
        )
        self.options_menu.add_checkbutton(
            label="Secciones automáticas",
            variable=self.auto_region_sections_var,
            command=self._on_toggle_auto_region_sections
        )
        self.options_menu.add_separator()
        self.options_menu.add_command(
            label="Regionar",
            command=self._on_regionize_clipboard
        )
        self.options_menu.add_separator()
        self.options_menu.add_command(
            label="Volver a memoria",
            command=self._on_open_memory_restore_popup
        )
        self.options_menu.add_separator()
        self.options_menu.add_command(
            label="Eliminar comentarios [MODIFICACIÓN]",
            command=self._on_remove_modification_comments
        )
        self.menu_bar.add_cascade(label="Output", menu=self.output_menu)
        self.menu_bar.add_cascade(label="Configurar parámetros", menu=self.configure_params_menu)
        self.menu_bar.add_cascade(label="Opciones", menu=self.options_menu)
        self.root.config(menu=self.menu_bar)
        self.sync_output_menu_state()

    def sync_output_menu_state(self, return_files=None, return_chunks=None, return_regions=None):
        """Keeps the Output menu vars in sync with CodeView state."""
        if (
            not hasattr(self, "output_return_files_var")
            or not hasattr(self, "output_return_chunks_var")
            or not hasattr(self, "output_return_regions_var")
        ):
            return

        if return_files is None or return_chunks is None or return_regions is None:
            code_view = getattr(getattr(self, "layout", None), "code_view", None)
            if (
                code_view is not None
                and hasattr(code_view, "var_return_files")
                and hasattr(code_view, "var_return_chunks")
                and hasattr(code_view, "var_return_regions")
            ):
                return_files = bool(code_view.var_return_files.get())
                return_chunks = bool(code_view.var_return_chunks.get())
                return_regions = bool(code_view.var_return_regions.get())
            else:
                return_files = self.controller.config_manager.get_return_files()
                return_chunks = self.controller.config_manager.get_return_chunks()
                return_regions = self.controller.config_manager.get_return_regions()

        self.output_return_files_var.set(bool(return_files))
        self.output_return_chunks_var.set(bool(return_chunks))
        self.output_return_regions_var.set(bool(return_regions))

    def _on_toggle_output_return_files(self):
        """Updates the return-files mode from the Output menu."""
        code_view = getattr(getattr(self, "layout", None), "code_view", None)
        if code_view is None:
            return

        should_enable = bool(self.output_return_files_var.get())
        code_view._set_return_mode(return_files=should_enable, return_chunks=False, return_regions=False)
        self.sync_output_menu_state()

    def _on_toggle_output_return_chunks(self):
        """Updates the return-chunks mode from the Output menu."""
        code_view = getattr(getattr(self, "layout", None), "code_view", None)
        if code_view is None:
            return

        should_enable = bool(self.output_return_chunks_var.get())
        code_view._set_return_mode(return_files=False, return_chunks=should_enable, return_regions=False)
        self.sync_output_menu_state()

    def _on_toggle_output_return_regions(self):
        """Updates the return-regions mode from the Output menu."""
        code_view = getattr(getattr(self, "layout", None), "code_view", None)
        if code_view is None:
            return

        should_enable = bool(self.output_return_regions_var.get())
        code_view._set_return_mode(return_files=False, return_chunks=False, return_regions=should_enable)
        self.sync_output_menu_state()

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

    def _on_toggle_remember_last_main_view(self):
        """Persists whether Programita should restore the last top-level view."""
        should_remember = bool(self.remember_last_main_view_var.get())
        self.controller.config_manager.set_remember_last_main_view(should_remember)

        if should_remember and hasattr(self, "layout"):
            active_view = self.layout.get_active_main_view()
            self.controller.config_manager.set_last_main_view(active_view)

    def _on_toggle_clever_injection(self):
        """Persists whether Clever SUS should run before Arbitrary SUS."""
        self.controller.config_manager.set_clever_injection_enabled(
            self.clever_injection_var.get()
        )

    def _on_toggle_doc_autosave(self):
        """Persists and applies markdown auto-save from the Options menu."""
        is_enabled = bool(self.doc_autosave_var.get())
        self.controller.config_manager.set_doc_autosave_enabled(is_enabled)

        doc_view = getattr(getattr(self, "layout", None), "doc_view", None)
        if doc_view is not None and hasattr(doc_view, "set_autosave_enabled"):
            doc_view.set_autosave_enabled(is_enabled)

    def _on_toggle_auto_region_sections(self):
        """Persists and applies automatic grouping sections for detected regions."""
        is_enabled = bool(self.auto_region_sections_var.get())
        self.controller.config_manager.set_auto_region_sections_enabled(is_enabled)

        code_view = getattr(getattr(self, "layout", None), "code_view", None)
        if code_view is not None and hasattr(code_view, "_should_show_project_regions_in_file_list"):
            if code_view._should_show_project_regions_in_file_list():
                code_view._schedule_region_list_refresh()

    def _set_code_file_limits(self, min_limit=None, max_limit=None, preferred="min", refresh=True):
        """Updates Code View min/max file limits, even if the view is not available yet."""
        config = self.controller.config_manager

        if min_limit is None:
            min_limit = config.get_file_limit()
        if max_limit is None:
            max_limit = config.get_max_file_limit()

        try:
            min_limit = max(1, int(min_limit))
        except (TypeError, ValueError):
            min_limit = config.get_file_limit()

        try:
            max_limit = max(1, int(max_limit))
        except (TypeError, ValueError):
            max_limit = config.get_max_file_limit()

        min_slider_max = config.get_file_limit_slider_max()
        max_slider_max = config.get_max_file_limit_slider_max()
        min_limit = min(min_limit, min_slider_max)
        max_limit = min(max_limit, max_slider_max)

        if min_limit > max_limit:
            if preferred == "min":
                max_limit = min(min_limit, max_slider_max)
                min_limit = min(min_limit, max_limit)
            else:
                min_limit = min(max_limit, min_slider_max)
                max_limit = max(max_limit, min_limit)

        config.set_file_limit(min_limit)
        config.set_max_file_limit(max_limit)

        code_view = getattr(getattr(self, "layout", None), "code_view", None)
        if code_view is not None and hasattr(code_view, "set_file_limits"):
            code_view.set_file_limits(
                min_limit=min_limit,
                max_limit=max_limit,
                preferred=preferred,
                refresh=refresh
            )

        return min_limit, max_limit

    def _on_configure_code_file_limit(self):
        """Lets the user configure the minimum number of files for Code View."""
        config = self.controller.config_manager
        current_value = config.get_file_limit()
        current_max = config.get_max_file_limit()
        new_limit = simpledialog.askinteger(
            "Opciones",
            "Introduce el valor para 'Mín. Ficheros':",
            initialvalue=current_value,
            minvalue=1,
            parent=self.root
        )
        if new_limit is None:
            return

        min_limit, max_limit = self._set_code_file_limits(
            min_limit=new_limit,
            preferred="min",
            refresh=True
        )

        if min_limit != new_limit or max_limit != current_max:
            messagebox.showinfo(
                "Opciones",
                f"Se ajustaron los límites a Mín. Ficheros = {min_limit} y Máx. Ficheros = {max_limit}."
            )

    def _on_configure_code_max_file_limit(self):
        """Lets the user configure the maximum number of files for Code View."""
        config = self.controller.config_manager
        current_min = config.get_file_limit()
        current_value = config.get_max_file_limit()
        new_limit = simpledialog.askinteger(
            "Opciones",
            "Introduce el valor para 'Máx. Ficheros':",
            initialvalue=current_value,
            minvalue=1,
            parent=self.root
        )
        if new_limit is None:
            return

        min_limit, max_limit = self._set_code_file_limits(
            max_limit=new_limit,
            preferred="max",
            refresh=True
        )

        if max_limit != new_limit or min_limit != current_min:
            messagebox.showinfo(
                "Opciones",
                f"Se ajustaron los límites a Mín. Ficheros = {min_limit} y Máx. Ficheros = {max_limit}."
            )

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

    def _on_regionize_clipboard(self):
        """Builds and copies a prompt that asks an AI to split clipboard code by regions."""
        success, message = self.controller.regionize_clipboard_code()
        if not success:
            messagebox.showwarning("Opciones", message)

    def _on_open_memory_restore_popup(self):
        """Shows a popup with available memory backups to restore."""
        backups = self.controller.list_code_memory_backups()

        if not backups:
            messagebox.showinfo("Volver a memoria", "No hay memorias disponibles.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Volver a memoria")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=Styles.COLOR_BG_MAIN)
        dialog.minsize(560, 360)

        width = 720
        height = 420
        self.root.update_idletasks()
        pos_x = self.root.winfo_rootx() + max((self.root.winfo_width() - width) // 2, 0)
        pos_y = self.root.winfo_rooty() + max((self.root.winfo_height() - height) // 3, 0)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

        header = tk.Label(
            dialog,
            text="Selecciona la memoria a la que quieres volver:",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.ui_font(13, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=16, pady=(16, 8))

        list_frame = tk.Frame(dialog, bg=Styles.COLOR_BG_MAIN)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        memory_list = tk.Listbox(
            list_frame,
            activestyle="dotbox",
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            relief="flat",
            font=Styles.ui_font(12),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=memory_list.yview)
        memory_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for backup in backups:
            memory_list.insert(tk.END, self._format_memory_menu_label(backup))
        memory_list.selection_set(0)
        memory_list.activate(0)
        memory_list.focus_set()

        button_row = tk.Frame(dialog, bg=Styles.COLOR_BG_MAIN)
        button_row.pack(fill="x", padx=16, pady=(0, 16))

        def restore_selected(event=None):
            selection = memory_list.curselection()
            if not selection:
                messagebox.showwarning("Volver a memoria", "Selecciona una memoria primero.")
                return "break"

            selected_backup = backups[int(selection[0])]
            dialog.destroy()
            self._on_restore_memory_backup(selected_backup)
            return "break"

        btn_cancel = tk.Button(
            button_row,
            text="Cancelar",
            command=dialog.destroy,
            bg=Styles.COLOR_BUTTON_BG,
            fg=Styles.COLOR_FG_TEXT,
            activebackground=Styles.COLOR_BUTTON_HOVER,
            activeforeground=Styles.COLOR_FG_TEXT,
            relief="flat",
            padx=16,
            pady=8
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_restore = tk.Button(
            button_row,
            text="Volver",
            command=restore_selected,
            bg=Styles.COLOR_ACCENT,
            fg="#ffffff",
            activebackground=Styles.COLOR_ACCENT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            padx=18,
            pady=8
        )
        btn_restore.pack(side="right")

        memory_list.bind("<Double-Button-1>", restore_selected)
        dialog.bind("<Return>", restore_selected)
        dialog.bind("<Escape>", lambda event: dialog.destroy())

    def _format_memory_menu_label(self, backup):
        """Formats a backup entry for display."""
        name = backup.get("name") or "memoria"
        file_count = int(backup.get("file_count") or 0)
        created_at = backup.get("created_at") or 0

        if created_at:
            try:
                date_label = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
                return f"{name} · {date_label} · {file_count} fichero(s)"
            except Exception:
                pass

        return f"{name} · {file_count} fichero(s)"

    def _on_restore_memory_backup(self, backup):
        """Confirms and restores a selected memory backup into the loaded project."""
        project_path = getattr(self.controller.project_manager, "current_project_path", None)
        if not project_path:
            messagebox.showwarning("Volver a memoria", "No hay ningún proyecto cargado.")
            return

        backup_name = backup.get("name") or "memoria seleccionada"
        file_count = int(backup.get("file_count") or 0)
        confirmed = messagebox.askyesno(
            "Volver a memoria",
            f"Vas a volver a la memoria:\n\n{backup_name}\n\n"
            f"Se sustituirán en el proyecto cargado los {file_count} fichero(s) guardados en esa memoria.\n"
            "Esta acción sobrescribe el código actual de esos ficheros.\n\n"
            "¿Quieres continuar?"
        )
        if not confirmed:
            return

        success, result, restored_count = self.controller.restore_code_memory_backup(backup.get("path"))
        if hasattr(self.layout, "code_view"):
            self.layout.code_view.refresh_file_list()

        if not success:
            messagebox.showerror(
                "Volver a memoria",
                f"No se pudo completar la restauración.\n\nFicheros restaurados: {restored_count}\n\n{result}"
            )
            return

        messagebox.showinfo(
            "Volver a memoria",
            f"Memoria restaurada correctamente.\n\nFicheros restaurados: {restored_count}"
        )

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
