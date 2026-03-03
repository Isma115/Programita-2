import tkinter as tk
from tkinter import ttk, messagebox
import os
from src.ui.styles import Styles

class DatabaseView(ttk.Frame):
    """
    View for database management.
    Allows connecting to MySQL databases, sampling data from tables,
    and exporting results to clipboard or file.
    """
    
    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = None
        try:
            self.controller = parent.winfo_toplevel().controller
        except:
            pass
        
        self.connection = None
        self.table_vars = {}  # Store BooleanVars for checkboxes
        # Eliminamos la variable auto_refresh_job ya que no la necesitamos
        
        self._create_layout()

    def _create_layout(self):
        """Creates the main layout with connection form and results area."""
        # Main container with padding
        self.main_container = ttk.Frame(self, style="Main.TFrame")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configure grid
        self.main_container.columnconfigure(0, weight=1)
        self.main_container.columnconfigure(1, weight=2)
        self.main_container.rowconfigure(1, weight=1)
        
        # === Connection Frame (Top Left) ===
        self._create_connection_frame()
        
        # === Tables Frame (Bottom Left) ===
        self._create_tables_frame()
        
        # === Results Frame (Right) ===
        self._create_results_frame()

    def _create_connection_frame(self):
        """Creates the database connection form."""
        conn_frame = ttk.LabelFrame(
            self.main_container, 
            text="Conexión a Base de Datos",
            style="TLabelframe"
        )
        conn_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        
        # Load saved config
        db_config = {}
        if self.controller:
            db_config = self.controller.config_manager.get_db_config()

        # Form fields
        fields = [
            ("Host:", "host", db_config.get("host", "localhost")),
            ("Puerto:", "port", db_config.get("port", "3306")),
            ("Usuario:", "user", db_config.get("user", "")),
            ("Contraseña:", "password", db_config.get("password", "")),
            ("Base de Datos:", "database", db_config.get("database", "")),
        ]
        
        self.conn_entries = {}
        
        for i, (label, key, default) in enumerate(fields):
            lbl = ttk.Label(conn_frame, text=label, style="TLabel")
            lbl.grid(row=i, column=0, sticky="w", padx=10, pady=5)
            
            if key == "password":
                entry = tk.Entry(
                    conn_frame,
                    font=Styles.FONT_MAIN,
                    bg=Styles.COLOR_INPUT_BG,
                    fg=Styles.COLOR_INPUT_FG,
                    insertbackground="white",
                    show="•",
                    borderwidth=0,
                    highlightthickness=1,
                    highlightbackground=Styles.COLOR_BORDER,
                    highlightcolor=Styles.COLOR_ACCENT
                )
            else:
                entry = tk.Entry(
                    conn_frame,
                    font=Styles.FONT_MAIN,
                    bg=Styles.COLOR_INPUT_BG,
                    fg=Styles.COLOR_INPUT_FG,
                    insertbackground="white",
                    borderwidth=0,
                    highlightthickness=1,
                    highlightbackground=Styles.COLOR_BORDER,
                    highlightcolor=Styles.COLOR_ACCENT
                )
            
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky="ew", padx=10, pady=5)
            self.conn_entries[key] = entry
        
        conn_frame.columnconfigure(1, weight=1)
        
        # Connect/Disconnect/Reconnect buttons
        btn_frame = ttk.Frame(conn_frame, style="Main.TFrame")
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=15)
        
        self.btn_connect = ttk.Button(
            btn_frame,
            text="🔌 Conectar",
            style="Action.TButton",
            command=self._on_connect
        )
        self.btn_connect.pack(side="left", padx=5)
        
        self.btn_disconnect = ttk.Button(
            btn_frame,
            text="❌ Desconectar",
            style="Secondary.TButton",
            command=self._on_disconnect,
            state="disabled"
        )
        self.btn_disconnect.pack(side="left", padx=5)
        
        # Nuevo botón: Reiniciar Conexión
        self.btn_reconnect = ttk.Button(
            btn_frame,
            text="🔄 Reiniciar Conexión",
            style="Nav.TButton",
            command=self._on_reconnect,
            state="disabled"
        )
        self.btn_reconnect.pack(side="left", padx=5)
        
        # Status label
        self.lbl_status = ttk.Label(
            conn_frame,
            text="⚪ No conectado",
            style="TLabel"
        )
        self.lbl_status.grid(row=len(fields) + 1, column=0, columnspan=2, pady=5)

    def _create_tables_frame(self):
        """Creates the tables selection frame."""
        self.tables_frame = ttk.LabelFrame(
            self.main_container,
            text="Tablas Disponibles",
            style="TLabelframe"
        )
        self.tables_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 0))
        
        # Scrollable frame for checkboxes
        self.canvas = tk.Canvas(
            self.tables_frame,
            bg=Styles.COLOR_BG_MAIN,
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            self.tables_frame,
            orient="vertical",
            command=self.canvas.yview,
            style="Vertical.TScrollbar"
        )
        
        self.tables_inner_frame = ttk.Frame(self.canvas, style="Main.TFrame")
        
        self.tables_inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.tables_inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling
        self.tables_inner_frame.bind('<Enter>', self._bound_to_mousewheel)
        self.tables_inner_frame.bind('<Leave>', self._unbound_to_mousewheel)
        self.canvas.bind('<Enter>', self._bound_to_mousewheel)
        self.canvas.bind('<Leave>', self._unbound_to_mousewheel)

    def _bound_to_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbound_to_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta)), "units")

    def _create_results_frame(self):
        """Creates the results display area."""
        results_frame = ttk.LabelFrame(
            self.main_container,
            text="Resultados",
            style="TLabelframe"
        )
        results_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        
        # Text area with scrollbar
        text_frame = ttk.Frame(results_frame, style="Main.TFrame")
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.txt_results = tk.Text(
            text_frame,
            font=Styles.FONT_CODE,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            wrap="none"
        )
        
        # Scrollbars
        scrollbar_y = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.txt_results.yview,
            style="Vertical.TScrollbar"
        )
        scrollbar_x = ttk.Scrollbar(
            text_frame,
            orient="horizontal",
            command=self.txt_results.xview
        )
        
        self.txt_results.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )
        
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")
        self.txt_results.pack(side="left", fill="both", expand=True)
        
        # Export buttons
        export_frame = ttk.Frame(results_frame, style="Main.TFrame")
        export_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_sample = ttk.Button(
            export_frame,
            text="📊 Obtener Muestras",
            style="Action.TButton",
            command=self._on_get_samples,
            state="disabled"
        )
        self.btn_sample.pack(side="left", padx=5)
        
        # Sample rows selector
        lbl_rows = ttk.Label(export_frame, text="Filas:", style="TLabel")
        lbl_rows.pack(side="left", padx=(10, 2))
        
        self.sample_rows_var = tk.IntVar(value=5)
        self.spn_sample_rows = tk.Spinbox(
            export_frame,
            from_=1,
            to=1000,
            textvariable=self.sample_rows_var,
            width=6,
            font=Styles.FONT_MAIN,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            buttonbackground=Styles.COLOR_BG_MAIN,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT
        )
        self.spn_sample_rows.pack(side="left", padx=2)
        
        self.btn_export = ttk.Button(
            export_frame,
            text="📋 Copiar y Guardar",
            style="Action.TButton",
            command=self._on_copy_and_save
        )
        self.btn_export.pack(side="left", padx=5)
        
        self.btn_clear = ttk.Button(
            export_frame,
            text="🗑️ Limpiar",
            style="Secondary.TButton",
            command=self._on_clear_results
        )
        self.btn_clear.pack(side="right", padx=5)

    def _on_connect(self):
        """Handles connection button click."""
        try:
            import mysql.connector
        except ImportError:
            messagebox.showerror(
                "Error",
                "El paquete mysql-connector-python no está instalado.\n\n"
                "Ejecuta: pip install mysql-connector-python"
            )
            return
        
        host = self.conn_entries["host"].get()
        port = self.conn_entries["port"].get()
        user = self.conn_entries["user"].get()
        password = self.conn_entries["password"].get()
        database = self.conn_entries["database"].get()
        
        if not all([host, user, database]):
            messagebox.showwarning("Aviso", "Rellena al menos host, usuario y base de datos.")
            return
        
        # Save config immediately (before attempting connection)
        if self.controller:
            self.controller.config_manager.set_db_config({
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database
            })
        
        try:
            self.connection = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
            
            self.lbl_status.config(text="🟢 Conectado")
            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
            self.btn_reconnect.config(state="normal")  # Habilitar botón de reinicio
            self.btn_sample.config(state="normal")
            
            # Disable connection fields
            for entry in self.conn_entries.values():
                entry.config(state="disabled")
            
            # Load tables
            self._load_tables()
            
        except Exception as e:
            messagebox.showerror("Error de Conexión", str(e))
            self.lbl_status.config(text="🔴 Error de conexión")

    def _on_disconnect(self):
        """Handles disconnect button click."""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
        
        self.lbl_status.config(text="⚪ No conectado")
        self.btn_connect.config(state="normal")
        self.btn_disconnect.config(state="disabled")
        self.btn_reconnect.config(state="disabled")  # Deshabilitar botón de reinicio
        self.btn_sample.config(state="disabled")
        
        # Enable connection fields
        for entry in self.conn_entries.values():
            entry.config(state="normal")
        
        # Clear tables
        self._clear_tables()

    def _on_reconnect(self):
        """
        Nuevo método: Reinicia la conexión manualmente.
        Desconecta y vuelve a conectar automáticamente.
        """
        if not self.connection:
            messagebox.showwarning("Aviso", "No hay una conexión activa para reiniciar.")
            return
        
        # Guardar estado actual
        self.lbl_status.config(text="🔄 Reiniciando conexión...")
        self.update_idletasks()
        
        # 1. Desconectar
        try:
            if self.connection and self.connection.is_connected():
                self.connection.close()
        except Exception as e:
            print(f"DatabaseView: Error al desconectar durante reinicio: {e}")
        
        self.connection = None
        
        # 2. Obtener configuración actual
        host = self.conn_entries["host"].get()
        port = self.conn_entries["port"].get()
        user = self.conn_entries["user"].get()
        password = self.conn_entries["password"].get()
        database = self.conn_entries["database"].get()
        
        # 3. Reconectar
        try:
            import mysql.connector
            self.connection = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
            
            # Actualizar UI
            self.lbl_status.config(text="🟢 Conexión reiniciada")
            
            # Recargar tablas
            self._clear_tables()
            self._load_tables()
            
            messagebox.showinfo("Éxito", "Conexión reiniciada correctamente.")
            
        except Exception as e:
            self.lbl_status.config(text="🔴 Error al reconectar")
            messagebox.showerror("Error", f"No se pudo reiniciar la conexión:\n{str(e)}")
            
            # Volver a estado desconectado
            self._on_disconnect()

    def _load_tables(self):
        """Loads the list of tables from the database."""
        self._clear_tables()
        
        if not self.connection:
            return
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            cursor.close()
            
            for table in tables:
                table_name = table[0]
                var = tk.BooleanVar(value=False)
                self.table_vars[table_name] = var
                
                chk = ttk.Checkbutton(
                    self.tables_inner_frame,
                    text=table_name,
                    variable=var,
                    style="TCheckbutton"
                )
                chk.pack(anchor="w", padx=5, pady=2)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando tablas: {e}")

    def _clear_tables(self):
        """Clears the tables list."""
        self.table_vars.clear()
        for widget in self.tables_inner_frame.winfo_children():
            widget.destroy()

    def _on_get_samples(self):
        """Gets sample data and full metadata from selected tables."""
        if not self.connection:
            messagebox.showwarning("Aviso", "No hay conexión activa.")
            return
        
        selected = [name for name, var in self.table_vars.items() if var.get()]
        
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona al menos una tabla.")
            return
        
        try:
            limit = self.sample_rows_var.get()
            if limit < 1:
                limit = 5
        except (tk.TclError, ValueError):
            limit = 5
        
        # Get current database name
        database = self.conn_entries["database"].get()
        
        results = []
        
        try:
            cursor = self.connection.cursor()
            
            for table in selected:
                results.append(f"\n{'='*60}")
                results.append(f" TABLA: {table}")
                results.append(f"{'='*60}")
                
                # ── Columnas ──
                results.append(f"\nColumnas:")
                cursor.execute(f"DESCRIBE `{table}`")
                describe_rows = cursor.fetchall()
                columns = []
                for col in describe_rows:
                    col_name = col[0]
                    col_type = col[1] or ""
                    col_null = "NULL" if col[2] == "YES" else "NOT NULL"
                    col_default = f" default={col[4]}" if col[4] is not None else ""
                    col_extra = f" {col[5]}" if col[5] else ""
                    col_key = ""
                    if col[3] == "PRI":
                        col_key = " [PK]"
                    elif col[3] == "UNI":
                        col_key = " [UQ]"
                    elif col[3] == "MUL":
                        col_key = " [IDX]"
                    columns.append(col_name)
                    results.append(f"  {col_name} {col_type} {col_null}{col_key}{col_default}{col_extra}")
                
                # ── Clave primaria ──
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s
                          AND TABLE_NAME = %s
                          AND CONSTRAINT_NAME = 'PRIMARY'
                        ORDER BY ORDINAL_POSITION
                    """, (database, table))
                    pk_cols = [row[0] for row in cursor.fetchall()]
                    if pk_cols:
                        results.append(f"\nPK: ({', '.join(pk_cols)})")
                except Exception:
                    pass
                
                # ── Índices (sin incluir PRIMARY) ──
                try:
                    cursor.execute(f"SHOW INDEX FROM `{table}`")
                    index_rows = cursor.fetchall()
                    indexes = {}
                    for idx in index_rows:
                        idx_name = idx[2]
                        if idx_name == "PRIMARY":
                            continue
                        idx_unique = "UNIQUE" if idx[1] == 0 else ""
                        idx_col = idx[4]
                        if idx_name not in indexes:
                            indexes[idx_name] = {"unique": idx_unique, "columns": []}
                        indexes[idx_name]["columns"].append(idx_col)
                    if indexes:
                        results.append(f"\nÍndices:")
                        for idx_name, info in indexes.items():
                            u = " UNIQUE" if info['unique'] else ""
                            results.append(f"  {idx_name}{u}: ({', '.join(info['columns'])})")
                except Exception:
                    pass
                
                # ── FK salientes ──
                try:
                    cursor.execute("""
                        SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                        ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION
                    """, (database, table))
                    fk_rows = cursor.fetchall()
                    if fk_rows:
                        fks = {}
                        for fk in fk_rows:
                            if fk[0] not in fks:
                                fks[fk[0]] = {"cols": [], "ref_table": fk[2], "ref_cols": []}
                            fks[fk[0]]["cols"].append(fk[1])
                            fks[fk[0]]["ref_cols"].append(fk[3])
                        results.append(f"\nFK salientes:")
                        for fk_name, info in fks.items():
                            results.append(f"  ({', '.join(info['cols'])}) → {info['ref_table']}({', '.join(info['ref_cols'])})")
                except Exception:
                    pass
                
                # ── FK entrantes ──
                try:
                    cursor.execute("""
                        SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME = %s
                        ORDER BY TABLE_NAME, CONSTRAINT_NAME
                    """, (database, table))
                    ref_rows = cursor.fetchall()
                    if ref_rows:
                        refs = {}
                        for ref in ref_rows:
                            key = (ref[0], ref[2])
                            if key not in refs:
                                refs[key] = {"src_cols": [], "ref_cols": []}
                            refs[key]["src_cols"].append(ref[1])
                            refs[key]["ref_cols"].append(ref[3])
                        results.append(f"\nFK entrantes:")
                        for (src_table, _), info in refs.items():
                            results.append(f"  {src_table}({', '.join(info['src_cols'])}) → ({', '.join(info['ref_cols'])})")
                except Exception:
                    pass
                
                # ── Muestra de datos ──
                results.append(f"\nDatos ({limit} filas):")
                results.append(",".join(columns))
                
                cursor.execute(f"SELECT * FROM `{table}` LIMIT {limit}")
                rows = cursor.fetchall()
                
                if rows:
                    for row in rows:
                        formatted_row = []
                        for val in row:
                            if isinstance(val, (bytes, bytearray)):
                                val_str = "<BIN>"
                            else:
                                val_str = str(val) if val is not None else ""
                            formatted_row.append(val_str)
                        results.append(",".join(formatted_row))
                else:
                    results.append("(Sin datos)")
            
            cursor.close()
            self.txt_results.insert("end", "\n".join(results) + "\n")
            self.txt_results.see("end")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error obteniendo muestras: {e}")

    @staticmethod
    def _format_bytes(size):
        """Formats a byte count into a human-readable string."""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def _on_copy_and_save(self):
        """Copies to clipboard and appends to codigo.txt."""
        content = self.txt_results.get("1.0", tk.END).strip()
        
        if not content:
            messagebox.showwarning("Aviso", "No hay contenido para exportar.")
            return
            
        # 1. Copy to Clipboard
        self.clipboard_clear()
        self.clipboard_append(content)
        
        # 2. Save to File
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            
            # Ensure directory exists
            os.makedirs(documents_path, exist_ok=True)
            
            # Append to file
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n\n" + "="*60 + "\n")
                f.write("MUESTRAS DE BASE DE DATOS\n")
                f.write("="*60 + "\n")
                f.write(content)
                f.write("\n")
            
            messagebox.showinfo("Exportado", f"Contenido copiado al portapapeles y añadido a:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Se copió al portapapeles pero falló el guardado:\n{e}")

    def _on_clear_results(self):
        """Clears the results text area."""
        self.txt_results.delete("1.0", tk.END)
