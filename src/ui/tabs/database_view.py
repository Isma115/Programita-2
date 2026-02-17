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
        self.auto_refresh_job = None  # To store the 'after' job ID
        
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
        
        # Connect button
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
            self.btn_sample.config(state="normal")
            
            # Disable connection fields
            for entry in self.conn_entries.values():
                entry.config(state="disabled")
            
            # Load tables
            self._load_tables()

            # Start auto-refresh loop
            self._start_auto_refresh_loop()

            
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
        self.btn_sample.config(state="disabled")
        
        # Enable connection fields
        for entry in self.conn_entries.values():
            entry.config(state="normal")
        
        # Clear tables
        self._clear_tables()
        
        # Stop auto-refresh loop
        self._stop_auto_refresh_loop()
    
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
        """Gets sample data from selected tables."""
        if not self.connection:
            messagebox.showwarning("Aviso", "No hay conexión activa.")
            return
        
        selected = [name for name, var in self.table_vars.items() if var.get()]
        
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona al menos una tabla.")
            return
        
        limit = 5
        
        results = []
        
        try:
            cursor = self.connection.cursor()
            
            for table in selected:
                results.append(f"\n{'='*60}")
                results.append(f"TABLA: {table}")
                results.append(f"{'='*60}\n")
                
                # Get columns
                cursor.execute(f"DESCRIBE `{table}`")
                columns = [col[0] for col in cursor.fetchall()]
                results.append(",".join(columns))
                
                # Get sample data
                cursor.execute(f"SELECT * FROM `{table}` LIMIT {limit}")
                rows = cursor.fetchall()
                
                if rows:
                    for row in rows:
                        formatted_row = []
                        for i, val in enumerate(row):
                            # Format binary/long data representation
                            if isinstance(val, (bytes, bytearray)):
                                val_str = "<DATOS BINARIOS / GEOMETRÍA>"
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

    def _start_auto_refresh_loop(self):
        """Starts the 2-minute auto-refresh cycle."""
        self._stop_auto_refresh_loop() # Ensure no duplicate loops
        print("DatabaseView: Iniciando ciclo de re-conexión automática (2 min)")
        self.auto_refresh_job = self.after(120000, self._auto_refresh_connection)

    def _stop_auto_refresh_loop(self):
        """Stops the auto-refresh cycle."""
        if self.auto_refresh_job:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

    def _auto_refresh_connection(self):
        """Attempts to keep the connection alive or reconnects."""
        if self.connection:
            try:
                print("DatabaseView: Ejecutando re-conexión automática (Keep-alive)...")
                # ping() with reconnect=True tries to re-establish the connection if it dropped
                self.connection.ping(reconnect=True, attempts=3, delay=2)
                
                if self.connection.is_connected():
                    print("DatabaseView: Conexión mantenida con éxito.")
                    # Optionally refresh labels or something very subtle
                    self.lbl_status.config(text="🟢 Conectado (Refrescado)")
                else:
                    print("DatabaseView: La conexión se perdió, intentando re-conectar...")
                    self._silent_reconnect()
            except Exception as e:
                print(f"DatabaseView: Error en auto-refresco: {e}")
                self._silent_reconnect()
        
        # Schedule next refresh
        self.auto_refresh_job = self.after(120000, self._auto_refresh_connection)

    def _silent_reconnect(self):
        """Helper to reconnect without showing message boxes (unless critical)."""
        host = self.conn_entries["host"].get()
        port = self.conn_entries["port"].get()
        user = self.conn_entries["user"].get()
        password = self.conn_entries["password"].get()
        database = self.conn_entries["database"].get()
        
        if not all([host, user, database]):
            return

        try:
            import mysql.connector
            if self.connection:
                try: self.connection.close()
                except: pass
                
            self.connection = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
            print("DatabaseView: Re-conexión silenciosa exitosa.")
            self.lbl_status.config(text="🟢 Conectado (Auto)")
        except Exception as e:
            print(f"DatabaseView: Error en re-conexión silenciosa: {e}")
            self.lbl_status.config(text="🔴 Error de auto-conexión")
            self._on_disconnect() # Revert to disconnected state if failed
    
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
