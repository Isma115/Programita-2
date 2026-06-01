import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
from src.ui.styles import Styles
from src.ui.tooltip import attach_tooltip


class DatabaseView(ttk.Frame):
    """
    Vista orientada a conexión completa de MySQL.
    Explora todas las bases de datos accesibles con un árbol tipo Workbench.
    """

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = None
        try:
            self.controller = parent.winfo_toplevel().controller
        except Exception:
            pass

        self.connection = None

        # Expuesto para otros módulos (controller/search popup)
        # Clave: "schema.table"
        self.table_vars = {}

        self.table_filter_var = tk.StringVar(value="")
        self.tree_item_meta = {}
        self._tree_filter_after = None

        self._create_layout()

    def _create_layout(self):
        self.main_container = ttk.Frame(self, style="Main.TFrame")
        self.main_container.pack(fill="both", expand=True, padx=18, pady=16)

        self.main_container.columnconfigure(0, weight=1)
        self.main_container.columnconfigure(1, weight=2)
        self.main_container.rowconfigure(2, weight=1)

        header_frame = tk.Frame(
            self.main_container,
            bg=Styles.COLOR_BG_MAIN,
            bd=0,
            highlightthickness=0,
        )
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        tk.Label(
            header_frame,
            text="Base de datos",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(20, "bold")),
        ).pack(anchor="w")
        tk.Label(
            header_frame,
            text="Explora toda la conexión (esquemas, tablas y columnas) y exporta muestras.",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_DIM,
            font=Styles.scale_font(Styles.ui_font(12)),
        ).pack(anchor="w", pady=(2, 0))

        self._create_connection_frame()
        self._create_tables_frame()
        self._create_results_frame()

    def _create_connection_frame(self):
        conn_frame = tk.Frame(
            self.main_container,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_BORDER,
        )
        conn_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))

        tk.Label(
            conn_frame,
            text="Conexión",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(14, "bold")),
        ).pack(anchor="w", padx=12, pady=(10, 2))

        form_frame = tk.Frame(conn_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG, bd=0, highlightthickness=0)
        form_frame.pack(fill="x", padx=12, pady=(2, 6))

        db_config = {}
        if self.controller:
            db_config = self.controller.config_manager.get_db_config()

        fields = [
            ("Host:", "host", db_config.get("host", "localhost")),
            ("Puerto:", "port", db_config.get("port", "3306")),
            ("Usuario:", "user", db_config.get("user", "")),
            ("Contraseña:", "password", db_config.get("password", "")),
            ("Base inicial (opcional):", "database", db_config.get("database", "")),
        ]

        self.conn_entries = {}

        for i, (label, key, default) in enumerate(fields):
            lbl = tk.Label(
                form_frame,
                text=label,
                bg=Styles.COLOR_SIDEBAR_CARD_BG,
                fg=Styles.COLOR_FG_TEXT,
                font=Styles.scale_font(Styles.ui_font(12, "bold")),
            )
            lbl.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=5)

            if key == "password":
                entry = tk.Entry(
                    form_frame,
                    font=Styles.scale_font(Styles.ui_font(12)),
                    bg=Styles.COLOR_INPUT_BG,
                    fg=Styles.COLOR_INPUT_FG,
                    insertbackground=Styles.COLOR_INPUT_FG,
                    show="•",
                )
            else:
                entry = tk.Entry(
                    form_frame,
                    font=Styles.scale_font(Styles.ui_font(12)),
                    bg=Styles.COLOR_INPUT_BG,
                    fg=Styles.COLOR_INPUT_FG,
                    insertbackground=Styles.COLOR_INPUT_FG,
                )

            Styles.style_sidebar_entry(entry)
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky="ew", pady=5)
            self.conn_entries[key] = entry

        form_frame.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(conn_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG, bd=0, highlightthickness=0)
        btn_frame.pack(fill="x", padx=12, pady=(2, 8))

        self.btn_connect = ttk.Button(
            btn_frame,
            text="Conectar",
            style="Action.TButton",
            command=self._on_connect,
        )
        self.btn_connect.pack(side="left", padx=(0, 6))
        attach_tooltip(self.btn_connect, "Abrir conexión")

        self.btn_disconnect = ttk.Button(
            btn_frame,
            text="Desconectar",
            style="Secondary.TButton",
            command=self._on_disconnect,
        )
        self.btn_disconnect.pack(side="left", padx=6)
        attach_tooltip(self.btn_disconnect, "Cerrar conexión")

        self.btn_reconnect = ttk.Button(
            btn_frame,
            text="Reiniciar conexión",
            style="Secondary.TButton",
            command=self._on_reconnect,
        )
        self.btn_reconnect.pack(side="left", padx=6)
        attach_tooltip(self.btn_reconnect, "Reiniciar conexión")

        def _set_button_state(button, enabled):
            button.configure(state=("normal" if enabled else "disabled"))

        self._set_btn_state = _set_button_state
        self._set_btn_state(self.btn_connect, True)
        self._set_btn_state(self.btn_disconnect, False)
        self._set_btn_state(self.btn_reconnect, False)

        self.lbl_status = tk.Label(
            conn_frame,
            text="No conectado",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_DIM,
            font=Styles.scale_font(Styles.ui_font(11, "bold")),
        )
        self.lbl_status.pack(anchor="w", padx=12, pady=(0, 12))

        self.lbl_connection_lost = tk.Label(
            conn_frame,
            text="Conexión perdida con la base de datos. Reconecta manualmente.",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg="#ff6b6b",
            font=Styles.scale_font(Styles.ui_font(11, "bold")),
            justify="left",
            wraplength=Styles.scale_size(360),
        )

    def _create_tables_frame(self):
        self.tables_frame = tk.Frame(
            self.main_container,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_BORDER,
        )
        self.tables_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 10), pady=(0, 0))

        tk.Label(
            self.tables_frame,
            text="Explorador de conexión",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(14, "bold")),
        ).pack(anchor="w", padx=12, pady=(10, 2))

        search_frame = tk.Frame(self.tables_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG, bd=0, highlightthickness=0)
        search_frame.pack(fill="x", padx=12, pady=(2, 6))

        tk.Label(
            search_frame,
            text="Buscar:",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(12, "bold")),
        ).pack(side="left", padx=(0, 6))

        self.ent_table_search = tk.Entry(
            search_frame,
            textvariable=self.table_filter_var,
            font=Styles.scale_font(Styles.ui_font(12)),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
        )
        Styles.style_sidebar_entry(self.ent_table_search)
        self.ent_table_search.pack(side="left", fill="x", expand=True)

        self.btn_reload_tree = ttk.Button(
            search_frame,
            text="Recargar",
            style="Secondary.TButton",
            command=self._load_connection_tree,
        )
        self.btn_reload_tree.pack(side="left", padx=(8, 0))
        attach_tooltip(self.btn_reload_tree, "Recargar bases de datos y tablas")

        tree_frame = tk.Frame(self.tables_frame, bg=Styles.COLOR_SIDEBAR_CARD_INNER, bd=0, highlightthickness=0)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.db_tree = ttk.Treeview(
            tree_frame,
            show="tree",
            selectmode="extended",
            style="Treeview",
        )
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.db_tree.yview, style="Vertical.TScrollbar")
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.db_tree.xview)
        self.db_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.db_tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")

        self.db_tree.tag_configure("database", foreground=Styles.COLOR_ACCENT)
        self.db_tree.tag_configure("table", foreground=Styles.COLOR_FG_TEXT)
        self.db_tree.tag_configure("view", foreground="#ffd866")
        self.db_tree.tag_configure("column", foreground=Styles.COLOR_DIM)
        self.db_tree.tag_configure("placeholder", foreground=Styles.COLOR_DIM)

        self.db_tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.db_tree.bind("<<TreeviewSelect>>", self._on_tree_selection_change)

        self.table_filter_var.trace_add("write", self._on_table_filter_change)
        self._clear_tables()

    def _create_results_frame(self):
        results_frame = tk.Frame(
            self.main_container,
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_BORDER,
        )
        results_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")

        tk.Label(
            results_frame,
            text="Resultados",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(14, "bold")),
        ).pack(anchor="w", padx=12, pady=(10, 2))

        text_frame = tk.Frame(results_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG, bd=0, highlightthickness=0)
        text_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.txt_results = tk.Text(
            text_frame,
            font=Styles.FONT_CODE,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            wrap="none",
        )

        scrollbar_y = ttk.Scrollbar(text_frame, orient="vertical", command=self.txt_results.yview, style="Vertical.TScrollbar")
        scrollbar_x = ttk.Scrollbar(text_frame, orient="horizontal", command=self.txt_results.xview)

        self.txt_results.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")
        self.txt_results.pack(side="left", fill="both", expand=True)

        export_frame = tk.Frame(results_frame, bg=Styles.COLOR_SIDEBAR_CARD_BG, bd=0, highlightthickness=0)
        export_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.btn_sample = ttk.Button(
            export_frame,
            text="Obtener muestras",
            style="Action.TButton",
            command=self._on_get_samples,
            state="disabled",
        )
        self.btn_sample.pack(side="left", padx=5)
        attach_tooltip(self.btn_sample, "Muestras de tablas seleccionadas del árbol")

        self.btn_export_sample = ttk.Button(
            export_frame,
            text="Exportar muestra",
            style="Action.TButton",
            command=self._open_export_sample_popup,
            state="disabled",
        )
        self.btn_export_sample.pack(side="left", padx=5)
        attach_tooltip(self.btn_export_sample, "Exportar metadatos completos y 20 filas por tabla")

        lbl_rows = tk.Label(
            export_frame,
            text="Filas:",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.scale_font(Styles.ui_font(12, "bold")),
        )
        lbl_rows.pack(side="left", padx=(10, 2))

        self.sample_rows_var = tk.IntVar(value=5)
        self.spn_sample_rows = tk.Spinbox(
            export_frame,
            from_=1,
            to=1000,
            textvariable=self.sample_rows_var,
            width=6,
            font=Styles.scale_font(Styles.ui_font(12)),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
            buttonbackground=Styles.COLOR_BG_MAIN,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT,
        )
        Styles.strip_classic_widget_chrome(self.spn_sample_rows)
        self.spn_sample_rows.pack(side="left", padx=2)

        self.btn_export = ttk.Button(
            export_frame,
            text="Copiar y guardar",
            style="Action.TButton",
            command=self._on_copy_and_save,
        )
        self.btn_export.pack(side="left", padx=5)
        attach_tooltip(self.btn_export, "Copiar al portapapeles y guardar en Documents/codigo.txt")

        self.btn_clear = ttk.Button(
            export_frame,
            text="Limpiar",
            style="Secondary.TButton",
            command=self._on_clear_results,
        )
        self.btn_clear.pack(side="right", padx=5)
        attach_tooltip(self.btn_clear, "Limpiar panel")

    def _set_connection_status(self, text, color=None):
        self.lbl_status.config(text=text, fg=(color or Styles.COLOR_DIM))

    def _show_connection_lost_indicator(self, visible):
        if visible:
            if not self.lbl_connection_lost.winfo_manager():
                self.lbl_connection_lost.pack(anchor="w", padx=12, pady=(0, 12))
        elif self.lbl_connection_lost.winfo_manager():
            self.lbl_connection_lost.pack_forget()

    def _mark_connection_lost(self):
        self.connection = None
        self._set_connection_status("Conexión perdida", color="#ff6b6b")
        self._show_connection_lost_indicator(True)
        self.btn_sample.config(state="disabled")
        self.btn_export_sample.config(state="disabled")
        self._set_btn_state(self.btn_connect, False)
        self._set_btn_state(self.btn_disconnect, True)
        self._set_btn_state(self.btn_reconnect, True)

    @staticmethod
    def _looks_like_connection_lost(error):
        text = str(error).lower()
        markers = (
            "mysql connection not available",
            "server has gone away",
            "lost connection",
            "connection was killed",
            "not connected",
            "connection is closed",
            "connection not available",
        )
        return any(marker in text for marker in markers)

    def _ensure_connection_alive(self):
        if not self.connection:
            self._mark_connection_lost()
            return False

        try:
            self.connection.ping(reconnect=False, attempts=1, delay=0)
            return True
        except Exception as e:
            if self._looks_like_connection_lost(e):
                self._mark_connection_lost()
            else:
                self._set_connection_status("Error de conexión", color="#ff8f8f")
            return False

    def _on_connect(self):
        try:
            import mysql.connector
        except ImportError:
            messagebox.showerror(
                "Error",
                "El paquete mysql-connector-python no está instalado.\n\n"
                "Ejecuta: pip install mysql-connector-python",
            )
            return

        host = self.conn_entries["host"].get().strip()
        port = self.conn_entries["port"].get().strip()
        user = self.conn_entries["user"].get().strip()
        password = self.conn_entries["password"].get()
        database = self.conn_entries["database"].get().strip()

        if not host or not user:
            messagebox.showwarning("Aviso", "Rellena al menos host y usuario.")
            return

        if self.controller:
            self.controller.config_manager.set_db_config(
                {
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": password,
                    "database": database,
                }
            )

        connect_kwargs = {
            "host": host,
            "port": int(port) if port else 3306,
            "user": user,
            "password": password,
        }
        if database:
            connect_kwargs["database"] = database

        try:
            self.connection = mysql.connector.connect(**connect_kwargs)

            self._set_connection_status("Conectado", color="#66d9a2")
            self._show_connection_lost_indicator(False)
            self._set_btn_state(self.btn_connect, False)
            self._set_btn_state(self.btn_disconnect, True)
            self._set_btn_state(self.btn_reconnect, True)
            self.btn_sample.config(state="normal")
            self.btn_export_sample.config(state="normal")

            for entry in self.conn_entries.values():
                entry.config(
                    state="disabled",
                    disabledbackground=Styles.COLOR_INPUT_BG,
                    disabledforeground=Styles.COLOR_DIM,
                )

            self._load_connection_tree()

        except Exception as e:
            messagebox.showerror("Error de Conexión", str(e))
            self._set_connection_status("Error de conexión", color="#ff8f8f")

    def _on_disconnect(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

        self._set_connection_status("No conectado")
        self._show_connection_lost_indicator(False)
        self._set_btn_state(self.btn_connect, True)
        self._set_btn_state(self.btn_disconnect, False)
        self._set_btn_state(self.btn_reconnect, False)
        self.btn_sample.config(state="disabled")
        self.btn_export_sample.config(state="disabled")

        for entry in self.conn_entries.values():
            entry.config(state="normal")
            Styles.style_sidebar_entry(entry)

        self._clear_tables()

    def _on_reconnect(self):
        """Reconexión manual únicamente."""
        self._set_connection_status("Reiniciando conexión...", color=Styles.COLOR_ACCENT)
        self.update_idletasks()

        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            print(f"DatabaseView: Error al desconectar durante reinicio: {e}")

        self.connection = None

        try:
            import mysql.connector
        except ImportError:
            messagebox.showerror(
                "Error",
                "El paquete mysql-connector-python no está instalado.\n\n"
                "Ejecuta: pip install mysql-connector-python",
            )
            self._set_connection_status("Error al reconectar", color="#ff8f8f")
            return

        host = self.conn_entries["host"].get().strip()
        port = self.conn_entries["port"].get().strip()
        user = self.conn_entries["user"].get().strip()
        password = self.conn_entries["password"].get()
        database = self.conn_entries["database"].get().strip()

        if not host or not user:
            messagebox.showwarning("Aviso", "Rellena al menos host y usuario.")
            self._set_connection_status("Error al reconectar", color="#ff8f8f")
            return

        connect_kwargs = {
            "host": host,
            "port": int(port) if port else 3306,
            "user": user,
            "password": password,
        }
        if database:
            connect_kwargs["database"] = database

        try:
            self.connection = mysql.connector.connect(**connect_kwargs)

            self._set_connection_status("Conexión reiniciada", color="#66d9a2")
            self._show_connection_lost_indicator(False)
            self._set_btn_state(self.btn_connect, False)
            self._set_btn_state(self.btn_disconnect, True)
            self._set_btn_state(self.btn_reconnect, True)
            self.btn_sample.config(state="normal")
            self.btn_export_sample.config(state="normal")

            for entry in self.conn_entries.values():
                entry.config(
                    state="disabled",
                    disabledbackground=Styles.COLOR_INPUT_BG,
                    disabledforeground=Styles.COLOR_DIM,
                )

            self._load_connection_tree()
            messagebox.showinfo("Éxito", "Conexión reiniciada correctamente.")

        except Exception as e:
            self._set_connection_status("Error al reconectar", color="#ff8f8f")
            messagebox.showerror("Error", f"No se pudo reiniciar la conexión:\n{e}")
            self._set_btn_state(self.btn_connect, True)
            self._set_btn_state(self.btn_disconnect, False)
            self._set_btn_state(self.btn_reconnect, False)
            self.btn_sample.config(state="disabled")
            self.btn_export_sample.config(state="disabled")
            for entry in self.conn_entries.values():
                entry.config(state="normal")
                Styles.style_sidebar_entry(entry)

    def _on_table_filter_change(self, *_):
        if self._tree_filter_after:
            self.after_cancel(self._tree_filter_after)
        self._tree_filter_after = self.after(220, self._reload_tree_from_filter)

    def _reload_tree_from_filter(self):
        self._tree_filter_after = None
        if self.connection:
            self._load_connection_tree()

    def _table_ref_key(self, schema_name, table_name):
        return f"{schema_name}.{table_name}"

    def _split_table_ref_key(self, table_ref):
        if isinstance(table_ref, (tuple, list)) and len(table_ref) == 2:
            return str(table_ref[0]), str(table_ref[1])

        text = str(table_ref)
        if "." in text:
            schema_name, table_name = text.split(".", 1)
            return schema_name, table_name

        fallback_schema = self.conn_entries.get("database").get().strip() if "database" in self.conn_entries else ""
        if not fallback_schema:
            raise ValueError(f"No se pudo inferir el esquema para la tabla '{text}'.")
        return fallback_schema, text

    def _clear_tables(self):
        self.table_vars.clear()
        self.tree_item_meta.clear()
        try:
            self.db_tree.delete(*self.db_tree.get_children())
        except Exception:
            pass

    def _load_tables(self):
        """Compatibilidad con llamadas antiguas."""
        self._load_connection_tree()

    def _load_connection_tree(self):
        self._clear_tables()

        if not self.connection:
            return
        if not self._ensure_connection_alive():
            return

        filter_text = self.table_filter_var.get().strip().lower()

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
            )
            rows = cursor.fetchall()
            cursor.close()

            by_schema = {}
            for schema_name, table_name, table_type in rows:
                schema_name = str(schema_name)
                table_name = str(table_name)
                table_type = str(table_type)

                if filter_text and filter_text not in schema_name.lower() and filter_text not in table_name.lower():
                    continue

                by_schema.setdefault(schema_name, []).append((table_name, table_type))

            if not by_schema:
                self.db_tree.insert("", "end", text="Sin resultados para el filtro actual.", tags=("placeholder",))
                return

            for schema_name in sorted(by_schema.keys(), key=lambda s: s.lower()):
                db_iid = self.db_tree.insert("", "end", text=schema_name, open=False, tags=("database",))
                self.tree_item_meta[db_iid] = {"kind": "database", "schema": schema_name}

                for table_name, table_type in sorted(by_schema[schema_name], key=lambda t: t[0].lower()):
                    table_key = self._table_ref_key(schema_name, table_name)
                    self.table_vars[table_key] = tk.BooleanVar(value=False)

                    tag = "view" if table_type.upper() == "VIEW" else "table"
                    suffix = " [VIEW]" if tag == "view" else ""
                    table_iid = self.db_tree.insert(db_iid, "end", text=f"{table_name}{suffix}", open=False, tags=(tag,))
                    self.tree_item_meta[table_iid] = {
                        "kind": "table",
                        "schema": schema_name,
                        "table": table_name,
                        "table_type": table_type,
                        "columns_loaded": False,
                    }
                    placeholder = self.db_tree.insert(table_iid, "end", text="(expandir para cargar columnas)", tags=("placeholder",))
                    self.tree_item_meta[placeholder] = {"kind": "placeholder"}

        except Exception as e:
            if self._looks_like_connection_lost(e):
                self._mark_connection_lost()
            messagebox.showerror("Error", f"Error cargando explorador de conexión: {e}")

    def _on_tree_open(self, event=None):
        item_id = self.db_tree.focus()
        meta = self.tree_item_meta.get(item_id, {})
        if meta.get("kind") != "table":
            return
        if meta.get("columns_loaded"):
            return

        schema_name = meta.get("schema")
        table_name = meta.get("table")
        try:
            self._load_table_columns(item_id, schema_name, table_name)
            meta["columns_loaded"] = True
        except Exception as e:
            if self._looks_like_connection_lost(e):
                self._mark_connection_lost()
                messagebox.showwarning("Conexión perdida", "Se perdió la conexión con la base de datos. Reconecta manualmente.")
                return
            messagebox.showerror("Error", f"No se pudieron cargar columnas de {schema_name}.{table_name}: {e}")

    def _load_table_columns(self, table_iid, schema_name, table_name):
        if not self._ensure_connection_alive():
            raise RuntimeError("Conexión no disponible")

        self.db_tree.delete(*self.db_tree.get_children(table_iid))

        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema_name, table_name),
        )
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            child = self.db_tree.insert(table_iid, "end", text="(sin columnas visibles)", tags=("placeholder",))
            self.tree_item_meta[child] = {"kind": "placeholder"}
            return

        for col_name, col_type, is_nullable, col_key, extra in rows:
            details = col_type or ""
            if is_nullable == "NO":
                details += " NOT NULL"
            if col_key:
                details += f" {col_key}"
            if extra:
                details += f" {extra}"

            col_iid = self.db_tree.insert(table_iid, "end", text=f"{col_name}: {details}", tags=("column",))
            self.tree_item_meta[col_iid] = {
                "kind": "column",
                "schema": schema_name,
                "table": table_name,
                "column": col_name,
            }

    def _on_tree_selection_change(self, event=None):
        if not self.connection:
            return
        selected_tables = self._get_selected_table_refs()
        if selected_tables:
            self._set_connection_status(f"Conectado · {len(selected_tables)} tabla(s) seleccionada(s)", color="#66d9a2")
        else:
            self._set_connection_status("Conectado", color="#66d9a2")

    def _get_selected_table_refs(self):
        selected_iids = self.db_tree.selection()
        selected_refs = set()

        for item_id in selected_iids:
            meta = self.tree_item_meta.get(item_id, {})
            kind = meta.get("kind")

            if kind == "table":
                selected_refs.add((meta.get("schema"), meta.get("table")))
            elif kind == "column":
                selected_refs.add((meta.get("schema"), meta.get("table")))
            elif kind == "database":
                schema_name = meta.get("schema")
                prefix = f"{schema_name}."
                for key in self.table_vars.keys():
                    if key.startswith(prefix):
                        selected_refs.add(self._split_table_ref_key(key))

        return sorted(selected_refs, key=lambda x: (str(x[0]).lower(), str(x[1]).lower()))

    @staticmethod
    def _escape_mysql_identifier(name):
        return str(name).replace("`", "``")

    @staticmethod
    def _format_db_value(value):
        if value is None:
            return "NULL"
        if isinstance(value, (bytes, bytearray)):
            return "<BIN>"
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="seconds")
        return str(value)

    def _append_query_dump(self, cursor, query, params, title, lines):
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = list(cursor.column_names) if getattr(cursor, "column_names", None) else []
            lines.append(f"\n{title}:")
            if not rows:
                lines.append("(Sin datos)")
                return
            lines.append(" | ".join(columns))
            for row in rows:
                lines.append(" | ".join(self._format_db_value(v) for v in row))
        except Exception as e:
            lines.append(f"\n{title}:")
            lines.append(f"(No disponible: {e})")

    def _build_table_report(self, selected_tables, limit_rows):
        if not self.connection:
            raise RuntimeError("No hay conexión activa.")
        if not self._ensure_connection_alive():
            raise RuntimeError("Se perdió la conexión con la base de datos. Reconecta manualmente.")

        normalized_tables = [self._split_table_ref_key(ref) for ref in selected_tables]
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "=" * 80,
            "REPORTE DE MUESTRAS DE BASE DE DATOS",
            f"Servidor: {self.conn_entries['host'].get()}:{self.conn_entries['port'].get()}",
            f"Generado: {generated_at}",
            f"Filas por tabla: {limit_rows}",
            "=" * 80,
        ]

        cursor = self.connection.cursor()
        try:
            for schema_name, table_name in normalized_tables:
                safe_schema = self._escape_mysql_identifier(schema_name)
                safe_table = self._escape_mysql_identifier(table_name)

                lines.append(f"\n{'='*80}")
                lines.append(f"TABLA: {schema_name}.{table_name}")
                lines.append(f"{'='*80}")

                try:
                    cursor.execute(f"SHOW CREATE TABLE `{safe_schema}`.`{safe_table}`")
                    create_row = cursor.fetchone()
                    lines.append("\nSHOW CREATE TABLE:")
                    if create_row and len(create_row) > 1:
                        lines.append(str(create_row[1]))
                    else:
                        lines.append("(Sin datos)")
                except Exception as e:
                    lines.append("\nSHOW CREATE TABLE:")
                    lines.append(f"(No disponible: {e})")

                self._append_query_dump(
                    cursor,
                    "SHOW TABLE STATUS FROM `{}` LIKE %s".format(safe_schema),
                    (table_name,),
                    "SHOW TABLE STATUS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.TABLES",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.COLUMNS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY INDEX_NAME, SEQ_IN_INDEX
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.STATISTICS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY CONSTRAINT_TYPE, CONSTRAINT_NAME
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.TABLE_CONSTRAINTS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.KEY_COLUMN_USAGE",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY CONSTRAINT_NAME
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.TRIGGERS
                    WHERE TRIGGER_SCHEMA = %s
                      AND EVENT_OBJECT_TABLE = %s
                    ORDER BY TRIGGER_NAME
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.TRIGGERS",
                    lines,
                )
                self._append_query_dump(
                    cursor,
                    """
                    SELECT *
                    FROM INFORMATION_SCHEMA.PARTITIONS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY PARTITION_ORDINAL_POSITION
                    """,
                    (schema_name, table_name),
                    "INFORMATION_SCHEMA.PARTITIONS",
                    lines,
                )

                try:
                    cursor.execute(f"SELECT * FROM `{safe_schema}`.`{safe_table}` LIMIT {int(limit_rows)}")
                    rows = cursor.fetchall()
                    columns = list(cursor.column_names) if getattr(cursor, "column_names", None) else []

                    lines.append(f"\nDATOS ({int(limit_rows)} filas):")
                    if columns:
                        lines.append(",".join(columns))
                    if rows:
                        for row in rows:
                            lines.append(",".join(self._format_db_value(v) for v in row))
                    else:
                        lines.append("(Sin datos)")
                except Exception as e:
                    lines.append(f"\nDATOS ({int(limit_rows)} filas):")
                    lines.append(f"(No disponible: {e})")

        except Exception as e:
            if self._looks_like_connection_lost(e):
                self._mark_connection_lost()
                raise RuntimeError("Se perdió la conexión con la base de datos. Reconecta manualmente.") from e
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        return "\n".join(lines) + "\n"

    def _open_export_sample_popup(self):
        if not self.connection:
            messagebox.showwarning("Aviso", "No hay conexión activa.")
            return
        if not self._ensure_connection_alive():
            messagebox.showwarning("Conexión perdida", "Se perdió la conexión con la base de datos. Reconecta manualmente.")
            return

        if not self.table_vars:
            self._load_connection_tree()

        table_keys = sorted(self.table_vars.keys(), key=lambda x: x.lower())
        if not table_keys:
            messagebox.showwarning("Aviso", "No hay tablas disponibles para exportar.")
            return

        popup = tk.Toplevel(self)
        popup.title("Exportar muestra")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.configure(bg=Styles.COLOR_BG_MAIN)
        popup.geometry("640x660")

        header = ttk.Frame(popup, style="Main.TFrame")
        header.pack(fill="x", padx=14, pady=(14, 8))
        ttk.Label(header, text="Exportar muestra", style="TLabel").pack(anchor="w")
        tk.Label(
            header,
            text="Selecciona tablas para exportar metadatos completos y 20 filas por tabla.",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_DIM,
            font=Styles.scale_font(Styles.ui_font(11)),
        ).pack(anchor="w", pady=(2, 0))

        search_var = tk.StringVar(value="")
        search_frame = ttk.Frame(popup, style="Main.TFrame")
        search_frame.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(search_frame, text="Buscar:", style="TLabel").pack(side="left", padx=(0, 6))

        ent_search = tk.Entry(
            search_frame,
            textvariable=search_var,
            font=Styles.scale_font(Styles.ui_font(12)),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground=Styles.COLOR_INPUT_FG,
        )
        Styles.style_sidebar_entry(ent_search)
        ent_search.pack(side="left", fill="x", expand=True)

        list_frame = ttk.Frame(popup, style="Main.TFrame")
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        listbox = tk.Listbox(
            list_frame,
            selectmode="multiple",
            exportselection=False,
            font=Styles.scale_font(Styles.ui_font(12)),
            activestyle="none",
        )
        Styles.style_sidebar_listbox(listbox)
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview, style="Vertical.TScrollbar")
        listbox.configure(yscrollcommand=list_scroll.set)
        listbox.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")

        visible_tables = []

        def render_table_list():
            query = search_var.get().strip().lower()
            listbox.delete(0, tk.END)
            visible_tables.clear()
            for key in table_keys:
                if query and query not in key.lower():
                    continue
                visible_tables.append(key)
                listbox.insert(tk.END, key)

        def select_all_visible():
            listbox.selection_set(0, tk.END)

        def clear_selection():
            listbox.selection_clear(0, tk.END)

        def do_export():
            indices = listbox.curselection()
            selected = [visible_tables[idx] for idx in indices]
            if not selected:
                messagebox.showwarning("Aviso", "Selecciona al menos una tabla.", parent=popup)
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"muestra_conexion_{timestamp}.txt"

            export_path = filedialog.asksaveasfilename(
                parent=popup,
                title="Guardar muestra de base de datos",
                defaultextension=".txt",
                initialfile=default_filename,
                filetypes=[("Archivo de texto", "*.txt"), ("Todos los archivos", "*.*")],
            )
            if not export_path:
                return

            try:
                report = self._build_table_report(selected, limit_rows=20)
                with open(export_path, "w", encoding="utf-8") as fh:
                    fh.write(report)

                messagebox.showinfo(
                    "Exportación completada",
                    f"Muestra exportada correctamente en:\n{export_path}",
                    parent=popup,
                )
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar la muestra:\n{e}", parent=popup)

        controls = ttk.Frame(popup, style="Main.TFrame")
        controls.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(controls, text="Seleccionar todo", style="Secondary.TButton", command=select_all_visible).pack(side="left")
        ttk.Button(controls, text="Limpiar selección", style="Secondary.TButton", command=clear_selection).pack(side="left", padx=8)

        actions = ttk.Frame(popup, style="Main.TFrame")
        actions.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(actions, text="Cancelar", style="Secondary.TButton", command=popup.destroy).pack(side="right")
        ttk.Button(actions, text="Exportar muestra", style="Action.TButton", command=do_export).pack(side="right", padx=8)

        search_var.trace_add("write", lambda *_: render_table_list())
        render_table_list()

    def _on_get_samples(self):
        if not self.connection:
            messagebox.showwarning("Aviso", "No hay conexión activa.")
            return
        if not self._ensure_connection_alive():
            messagebox.showwarning("Conexión perdida", "Se perdió la conexión con la base de datos. Reconecta manualmente.")
            return

        selected = self._get_selected_table_refs()
        if not selected:
            messagebox.showwarning(
                "Aviso",
                "Selecciona al menos una tabla en el árbol (o un esquema completo).",
            )
            return

        try:
            limit = self.sample_rows_var.get()
            if limit < 1:
                limit = 5
        except (tk.TclError, ValueError):
            limit = 5

        try:
            report = self._build_table_report(selected, limit_rows=limit)
            self.txt_results.insert("end", report)
            self.txt_results.see("end")
        except Exception as e:
            messagebox.showerror("Error", f"Error obteniendo muestras: {e}")

    @staticmethod
    def _format_bytes(size):
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def _on_copy_and_save(self):
        content = self.txt_results.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Aviso", "No hay contenido para exportar.")
            return

        self.clipboard_clear()
        self.clipboard_append(content)

        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            os.makedirs(documents_path, exist_ok=True)

            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n\n" + "=" * 60 + "\n")
                f.write("MUESTRAS DE BASE DE DATOS\n")
                f.write("=" * 60 + "\n")
                f.write(content)
                f.write("\n")

            messagebox.showinfo("Exportado", f"Contenido copiado al portapapeles y añadido a:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Se copió al portapapeles pero falló el guardado:\n{e}")

    def _on_clear_results(self):
        self.txt_results.delete("1.0", tk.END)
