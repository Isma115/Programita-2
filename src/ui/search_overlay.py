import tkinter as tk
from src.ui.styles import Styles


TYPE_ICONS = {
    'code':     '📄',
    'table':    '🗄️',
    'doc':      '📝',
    'file':     '📁',
    'function': 'λ',
    'command':  '🐚',
}

TYPE_LABELS = {
    'code':     'Código',
    'table':    'Tabla BD',
    'doc':      'Documentación',
    'file':     'Fichero',
    'function': 'Función',
    'command':  'Comando',
}


class SearchOverlay(tk.Toplevel):
    """
    VS Code-style Ctrl+P search palette overlay.
    Shows all searchable assets with live filtering and keyboard navigation.
    """

    MAX_VISIBLE = 15

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.all_assets = []
        self.filtered = []
        self.selected_index = 0

        # --- Window configuration ---
        self.overrideredirect(True)  # No window decorations
        self.configure(bg=Styles.COLOR_BG_SIDEBAR)
        self.attributes("-topmost", True)

        # Dimensions
        width = 620
        row_height = 36
        entry_height = 50
        max_list_height = self.MAX_VISIBLE * row_height

        # Position: centered horizontally at top of parent
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        x = px + (pw - width) // 2
        y = py + 50  # slight offset from top

        self.geometry(f"{width}x{entry_height + max_list_height + 12}+{x}+{y}")

        # --- Outer border frame ---
        border = tk.Frame(self, bg=Styles.COLOR_ACCENT, padx=2, pady=2)
        border.pack(fill="both", expand=True)

        inner = tk.Frame(border, bg=Styles.COLOR_BG_SIDEBAR)
        inner.pack(fill="both", expand=True)

        # --- Search entry ---
        self.entry = tk.Entry(
            inner,
            font=("Segoe UI", 16),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry.pack(fill="x", padx=8, pady=(8, 4), ipady=8)
        self.entry.insert(0, "")
        self._set_placeholder()

        # --- Results listbox ---
        self.listbox_frame = tk.Frame(inner, bg=Styles.COLOR_BG_SIDEBAR)
        self.listbox_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.listbox = tk.Listbox(
            self.listbox_frame,
            font=("Segoe UI", 14),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            height=self.MAX_VISIBLE,
        )
        self.listbox.pack(fill="both", expand=True)

        # --- Status bar ---
        self.status_label = tk.Label(
            inner,
            text="",
            font=("Segoe UI", 11),
            bg=Styles.COLOR_BG_SIDEBAR,
            fg=Styles.COLOR_DIM,
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=10, pady=(0, 4))

        # --- Load assets ---
        self.all_assets = self.controller.get_all_searchable_assets()
        self.filtered = list(self.all_assets)
        self._update_listbox()
        self._update_status(f"{len(self.all_assets)} activos disponibles")

        # --- Bindings ---
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", self._on_arrow_up)
        self.entry.bind("<Down>", self._on_arrow_down)
        self.entry.bind("<Escape>", self._on_escape)
        self.listbox.bind("<Double-Button-1>", self._on_listbox_double_click)
        self.listbox.bind("<Button-1>", self._on_listbox_click)

        # Close on click outside
        self.bind("<FocusOut>", self._on_focus_out)

        # Focus the entry
        self.entry.focus_force()

    # --- Placeholder ---
    def _set_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, "Buscar activos del proyecto...")
            self.entry.config(fg=Styles.COLOR_DIM)
            self._placeholder_active = True
        else:
            self._placeholder_active = False

    def _on_focus_in(self, event=None):
        """Clears the placeholder when the user focuses the entry."""
        if getattr(self, '_placeholder_active', False):
            self.entry.delete(0, tk.END)
            self.entry.config(fg=Styles.COLOR_INPUT_FG)
            self._placeholder_active = False

    # --- Filtering ---
    def _on_key_release(self, event=None):
        # Skip navigation keys
        if event and event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            return

        raw_query = self.entry.get()
        query = raw_query.lower()

        if query.startswith("funcion:"):
            # Function search mode
            search_term = query[len("funcion:"):].strip()
            all_functions = self.controller.get_all_functions()
            if not search_term:
                self.filtered = all_functions
            else:
                self.filtered = [f for f in all_functions if search_term in f['name'].lower()]
            self._update_status(f"🔍 Modo Función: {len(self.filtered)} encontradas")
        elif query.startswith(">"):
            # Explicit command mode (optional prefix)
            search_term = query[1:].strip()
            all_commands = self.controller.get_all_commands()
            cmds = [c for c in all_commands if search_term in c.lower()] if search_term else all_commands
            self.filtered = [{'name': c, 'type': 'command', 'path': c} for c in cmds]
            self._update_status(f"🐚 Modo Comando: {len(self.filtered)} disponibles")
        elif not query or (getattr(self, '_placeholder_active', False)):
            self.filtered = list(self.all_assets)
            self._update_status(f"{len(self.all_assets)} activos disponibles")
        else:
            self.filtered = [
                a for a in self.all_assets
                if query in a['name'].lower()
            ]
            self._update_status(f"{len(self.filtered)} coincidencias")

        self.selected_index = 0
        self._update_listbox()

    def _update_listbox(self):
        self.listbox.delete(0, tk.END)
        for asset in self.filtered[:self.MAX_VISIBLE]:
            icon = TYPE_ICONS.get(asset['type'], '📄')
            label = TYPE_LABELS.get(asset['type'], '')
            if asset['type'] == 'function':
                # Show function name and its source file
                display = f"{icon}  {asset['name']}   ({asset['file_rel_path']})   [{label}]"
            else:
                display = f"{icon}  {asset['name']}   [{label}]"
            self.listbox.insert(tk.END, display)

        if self.filtered:
            self.listbox.selection_set(self.selected_index)
            self.listbox.see(self.selected_index)

    def _update_status(self, text):
        self.status_label.config(text=text)

    # --- Navigation ---
    def _on_arrow_up(self, event=None):
        if self.filtered:
            self.selected_index = max(0, self.selected_index - 1)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.selected_index)
            self.listbox.see(self.selected_index)
        return "break"

    def _on_arrow_down(self, event=None):
        if self.filtered:
            self.selected_index = min(len(self.filtered) - 1, self.selected_index + 1)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.selected_index)
            self.listbox.see(self.selected_index)
        return "break"

    # --- Selection ---
    def _on_enter(self, event=None):
        query = self.entry.get().strip()
        if not query or getattr(self, '_placeholder_active', False):
            return "break"

        # Check if we should run as a command (if no selection or if selected is a command)
        asset = None
        if self.filtered and 0 <= self.selected_index < len(self.filtered):
            asset = self.filtered[self.selected_index]

        if asset and asset['type'] == 'command':
            # Use query if it starts with the command name to preserve arguments
            cmd_name = asset['name']
            run_text = query if query.lower().startswith(cmd_name.lower()) or query.startswith(">") else cmd_name
            self._execute_command(run_text)
        elif not asset:
            # No matching asset, try running as raw command
            self._execute_command(query)
        else:
            # Normal asset selection
            self._select_asset(asset)
        return "break"

    def _on_listbox_click(self, event=None):
        # Update selected_index from listbox click
        sel = self.listbox.curselection()
        if sel:
            self.selected_index = sel[0]

    def _on_listbox_double_click(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            if idx < len(self.filtered):
                self._select_asset(self.filtered[idx])

    def _select_asset(self, asset):
        """Processes selection: copy-to-clipboard for functions or append to codigo.txt."""
        if asset['type'] == 'command':
            self._execute_command(asset['name'])
            return

        if asset['type'] == 'function':
            self._update_status("⏳ Copiando función...")
            self.update_idletasks()
            
            success = self.controller.copy_to_clipboard(asset['content'])
            if success:
                self._update_status(f"✅ {asset['name']} copiado al portapapeles")
                self.update_idletasks()
            else:
               self._update_status("❌ Error al copiar al portapapeles")
            return

        self._update_status("⏳ Obteniendo contenido...")
        self.update_idletasks()

        content = self.controller.get_asset_content(asset)
        if content:
            success, path = self.controller.save_content_to_codigo_txt(content, append=True)
            if success:
                icon = TYPE_ICONS.get(asset['type'], '📄')
                self._update_status(f"✅ {icon} {asset['name']} → añadido a codigo.txt")
                self.update_idletasks()
            else:
                self._update_status(f"❌ Error: {path}")
        else:
            self._update_status("⚠️ El activo no tiene contenido")

    def _execute_command(self, text):
        """Executes a command and shows output."""
        self._update_status(f"⏳ Ejecutando...")
        self.update_idletasks()
        self.controller.run_command(text, output_callback=self._update_status)

    # --- Close ---
    def _on_escape(self, event=None):
        # Only close on click outside as requested
        return "break"

    
    # En src/ui/search_overlay.py, modificar el método _close
    def _close(self):
        # Restaurar el foco a la ventana principal antes de destruir
        try:
            if self.master and self.master.winfo_exists():
                self.master.focus_force()
        except:
            pass
        
        self.destroy()
