
from src.logic.project_manager import ProjectManager
from src.logic.section_manager import SectionManager
from src.logic.config_manager import ConfigManager
from src.logic.global_hotkeys import GlobalHotkeyListener
from src.ui.styles import Styles
import os
import pyperclip
import importlib

class Controller:
    """
    Manages the application state and logic separation.
    Acts as a bridge between the UI and the data/logic.
    """
    def __init__(self, app):
        """
        Initialize the controller.
        
        Args:
            app: Reference to the main Application instance.
        """
        self.app = app
        self.config_manager = ConfigManager()
        
        # Load Theme from Config
        theme_colors = self.config_manager.get_theme_colors()
        if theme_colors:
            Styles.COLOR_ACCENT = theme_colors.get("COLOR_ACCENT", Styles.COLOR_ACCENT)
            Styles.COLOR_ACCENT_HOVER = theme_colors.get("COLOR_ACCENT_HOVER", Styles.COLOR_ACCENT_HOVER)
        
        self.project_manager = ProjectManager(self.config_manager)
        self.section_manager = SectionManager(self.project_manager)
        self.hotkey_listener = GlobalHotkeyListener(self)

    def load_project_folder(self, path):
        """Loads a project folder and updates the UI."""
        print(f"Controller: Loading project from {path}")
        try:
            self.project_manager.load_project(path)
            # Save to config
            self.config_manager.set_last_project(path)
            
            # Update Window Title
            project_name = os.path.basename(path)
            self.app.root.title(f"Programita 2 - {project_name}")
            
            # Refresh UI File List if the view is active
            if hasattr(self.app.layout, 'code_view'):
                self.app.layout.code_view.refresh_file_list()
                self.app.layout.code_view._update_project_label()
                
        except Exception as e:
            print(f"Error loading project: {e}")

    def get_project_directories(self):
        """Returns the list of registered project directories."""
        return self.config_manager.get_project_directories()

    def get_current_project_index(self):
        """Returns the index of the currently selected project."""
        return self.config_manager.get_current_project_index()

    def switch_to_project(self, index):
        """Switch to the project at the given index."""
        dirs = self.config_manager.get_project_directories()
        if not dirs:
            return
        # Clamp index
        index = index % len(dirs)
        path = dirs[index]
        if os.path.exists(path):
            self.config_manager.set_current_project_index(index)
            self.load_project_folder(path)
        else:
            print(f"Controller: Project path no longer exists: {path}")

    def next_project(self):
        """Navigate to the next project (cyclic)."""
        dirs = self.config_manager.get_project_directories()
        if len(dirs) <= 1:
            return
        idx = (self.config_manager.get_current_project_index() + 1) % len(dirs)
        self.switch_to_project(idx)

    def prev_project(self):
        """Navigate to the previous project (cyclic)."""
        dirs = self.config_manager.get_project_directories()
        if len(dirs) <= 1:
            return
        idx = (self.config_manager.get_current_project_index() - 1) % len(dirs)
        self.switch_to_project(idx)

    def add_project_directory(self, path):
        """Add a new project directory and switch to it."""
        dirs = self.config_manager.get_project_directories()
        if path not in dirs:
            dirs.append(path)
            self.config_manager.set_project_directories(dirs)
        new_idx = dirs.index(path)
        self.config_manager.set_current_project_index(new_idx)
        self.load_project_folder(path)

    def generate_prompt(self, user_text, selected_section=None, return_regions=False, file_limit=10, implementation_mode=False, file_paths=None):
        """
        Generates a prompt based on user text and selected files.
        """
        # Determine scope
        if file_paths is not None:
            all_files = self.project_manager.get_files()
            files_map = {f['path']: f for f in all_files}
            relevant_files = [files_map[p] for p in file_paths if p in files_map]
        else:
            if selected_section:
                section_files_list = self.section_manager.get_files_in_section(selected_section)
                # Filter all loaded files to just those in the section
                all_files = self.project_manager.get_files()
                
                # Create a lookup for all files {path: file_obj} for O(1) access
                files_map = {f['path']: f for f in all_files}
                
                # Build relevant_files list ensuring order from section_files_list
                relevant_files = []
                for path in section_files_list:
                    if path in files_map:
                        relevant_files.append(files_map[path])
            else:
                # Search everything using relevant files finding
                relevant_files = self.project_manager.find_relevant_files(user_text)
        
        # Build Prompt
        prompt = f"Petición del Usuario: {user_text}\n\nArchivos de Contexto:\n"
        for f in relevant_files[:file_limit]: # Limit to slider value
            prompt += f"\n--- Archivo: {f['rel_path']} ---\n"
            prompt += f.get('content', '') + "\n"
        
        # Include table samples if section has tables
        if selected_section:
            section_tables = self.section_manager.get_tables_in_section(selected_section)
            if section_tables:
                table_samples = self._get_table_samples_for_prompt(section_tables)
                if table_samples:
                    prompt += f"\n\nMuestras de Base de Datos:\n{table_samples}"
        
        # Implementation mode: include directory tree and implementation instructions
        if implementation_mode:
            dir_tree = self.project_manager.get_directory_tree()
            if dir_tree:
                prompt += f"\n\n--- Árbol de Directorios del Proyecto ---\n{dir_tree}\n"
            
            prompt += "\n\nINSTRUCCIONES DE IMPLEMENTACIÓN:"
            prompt += "\n1. Realiza TODAS las modificaciones necesarias en el código."
            prompt += "\n2. Si es necesario crear, mover o eliminar ficheros o carpetas, proporciona los COMANDOS DE CONSOLA exactos a ejecutar."
            prompt += "\n3. Todos los comandos deben ejecutarse desde la RAÍZ del proyecto."
            prompt += "\n4. Formato de comandos: agrúpalos en un bloque al final con el título '## Comandos de Consola'."
            prompt += "\n5. Usa comandos compatibles con el sistema operativo del usuario (macOS/Linux: mkdir, rm, mv, cp, touch)."
            
        if return_regions:
            prompt += "\n\nIMPORTANTE: Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
            
        return prompt

    def _get_table_samples_for_prompt(self, table_names, limit=5):
        """Connects to DB (if needed) and gets sample data for given tables."""
        connection = None
        created_connection = False
        
        try:
            # Try to reuse existing connection from database_view
            if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'database_view'):
                db_view = self.app.layout.database_view
                if db_view.connection and db_view.connection.is_connected():
                    connection = db_view.connection
            
            # If no existing connection, create one from config
            if not connection:
                db_config = self.config_manager.get_db_config()
                if not db_config or not db_config.get('host'):
                    print("Controller: No DB config available for table samples")
                    return ""
                
                try:
                    import mysql.connector
                    connection = mysql.connector.connect(
                        host=db_config.get('host', 'localhost'),
                        port=int(db_config.get('port', 3306)),
                        user=db_config.get('user', ''),
                        password=db_config.get('password', ''),
                        database=db_config.get('database', '')
                    )
                    created_connection = True
                except ImportError:
                    print("Controller: mysql-connector-python not installed")
                    return ""
                except Exception as e:
                    print(f"Controller: DB connection error: {e}")
                    return ""
            
            # Fetch samples
            results = []
            cursor = connection.cursor()
            
            for table in table_names:
                results.append(f"\n{'='*60}")
                results.append(f"TABLA: {table}")
                results.append(f"{'='*60}\n")
                
                try:
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
                except Exception as e:
                    results.append(f"Error: {e}")
                
                results.append("")
            
            cursor.close()
            return "\n".join(results)
            
        except Exception as e:
            print(f"Controller: Error getting table samples: {e}")
            return ""
        finally:
            if created_connection and connection:
                try:
                    connection.close()
                except:
                    pass

    def get_relevant_files_for_ui(self, user_text, selected_section=None, extension=""):
        """Helper to get relevant files for UI display."""
        all_files = self.project_manager.get_files()
        
        # 1. Scope Filtering (Section or Global)
        if selected_section:
            section_files_paths = self.section_manager.get_files_in_section(selected_section)
            files_map = {f['path']: f for f in all_files}
            base_files = [files_map[p] for p in section_files_paths if p in files_map]
        else:
            if not user_text:
                base_files = all_files
            else:
                base_files = self.project_manager.find_relevant_files(user_text)

        # 2. Extension Filtering (Support multiple comma-separated extensions)
        if extension and extension.strip():
            # Parse extensions: split by comma, strip whitespace, ensure dot prefix
            ext_list = []
            for e in extension.split(','):
                e = e.strip().lower()
                if e:
                    if not e.startswith('.'):
                        e = '.' + e
                    ext_list.append(e)
            
            if ext_list:
                base_files = [f for f in base_files if any(f['rel_path'].lower().endswith(ext) for ext in ext_list)]
            
        return base_files

    def show_code_view(self):
        """
        Switch the main content area to the Code view.
        """
        print("Logic: Switching to Code View")
        self.app.layout.show_code_tab()

    def show_docs_view(self):
        """
        Switch the main content area to the Documentation view.
        """
        print("Logic: Switching to Docs View")
        self.app.layout.show_docs_tab()


    def show_database_view(self):
        """
        Switch the main content area to the Database view.
        """
        print("Logic: Switching to Database View")
        self.app.layout.show_database_tab()

    def replace_region_from_clipboard(self, region_name, content):
        """
        Bridges the hotkey trigger to the project manager.
        """
        print(f"Controller: Attempting to replace region '{region_name}'")
        success = self.project_manager.replace_region(region_name, content)
        if success:
            print(f"Controller: Successfully replaced region '{region_name}'")
            # Refresh UI if needed
            if hasattr(self.app.layout, 'code_view'):
                self.app.layout.code_view.refresh_file_list()
            return True
        else:
            print(f"Controller: Region '{region_name}' not found in project.")
            return False

    def get_file_content_by_path(self, path):
        """Returns the content and relative path of a file given its absolute path."""
        for f in self.project_manager.get_files():
            if f['path'] == path:
                return {
                    'content': f['content'],
                    'rel_path': f['rel_path']
                }
        return None

    def save_content_to_codigo_txt(self, content, append=False):
        """Saves or appends content to ~/Documents/codigo.txt."""
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            os.makedirs(documents_path, exist_ok=True)
            
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                if append and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    f.write("\n\n") # Separator for append
                f.write(content)
            return True, file_path
        except Exception as e:
            return False, str(e)

    def get_all_searchable_assets(self):
        """
        Returns a flat list of all searchable project assets.
        Each item: {'name': str, 'type': str, 'path': str}
        Types: 'code', 'table', 'doc', 'file'
        """
        assets = []

        # 1. Code files
        for f in self.project_manager.get_files():
            assets.append({
                'name': f['rel_path'],
                'type': 'code',
                'path': f['path']
            })

        # 2. Database tables (if connected)
        try:
            if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'database_view'):
                db_view = self.app.layout.database_view
                for table_name in db_view.table_vars.keys():
                    assets.append({
                        'name': table_name,
                        'type': 'table',
                        'path': table_name
                    })
        except Exception:
            pass

        # 3. Documentation sections
        for section_name in self.section_manager.get_sections():
            assets.append({
                'name': section_name,
                'type': 'doc',
                'path': section_name
            })

        # 4. Non-code files
        for f in self.project_manager.get_non_code_files():
            assets.append({
                'name': f['rel_path'],
                'type': 'file',
                'path': f['path']
            })

        # 5. Commands
        for cmd in self.get_all_commands():
            assets.append({
                'name': cmd,
                'type': 'command',
                'path': cmd
            })

        return assets

    def get_asset_content(self, asset):
        """
        Returns the string content for a given asset dict.
        """
        asset_type = asset['type']
        path = asset['path']

        if asset_type == 'code':
            # Read from cached files or disk
            for f in self.project_manager.get_files():
                if f['path'] == path:
                    return f"--- Archivo: {f['rel_path']} ---\n{f['content']}"
            # Fallback: read from disk
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                rel = os.path.relpath(path, self.project_manager.current_project_path or '')
                return f"--- Archivo: {rel} ---\n{content}"
            except Exception:
                return ""

        elif asset_type == 'table':
            # Get table description + sample
            table_name = path
            result = self._get_table_samples_for_prompt([table_name], limit=5)
            return result if result else f"--- Tabla: {table_name} ---\n(Sin datos disponibles)"

        elif asset_type == 'doc':
            # Read documentation section content
            section_name = path
            section_files = self.section_manager.get_files_in_section(section_name)
            parts = [f"--- Sección Doc: {section_name} ---"]
            for fpath in section_files:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                        parts.append(f"\n--- {os.path.basename(fpath)} ---\n{fh.read()}")
                except Exception:
                    pass
            return "\n".join(parts) if len(parts) > 1 else f"--- Sección Doc: {section_name} ---\n(Sin archivos)"

        elif asset_type == 'file':
            # Read non-code file
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                rel = os.path.relpath(path, self.project_manager.current_project_path or '')
                return f"--- Archivo: {rel} ---\n{content}"
            except Exception:
                return f"--- Archivo: {os.path.basename(path)} ---\n(No se pudo leer)"

        return ""

    def get_all_functions(self):
        """
        Returns all functions extracted from the project.
        """
        return self.project_manager.extract_functions()

    def copy_to_clipboard(self, text):
        """
        Copies the given text to the system clipboard.
        """
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            print(f"Controller: Error copying to clipboard: {e}")
            return False

    def get_all_commands(self):
        """Returns a list of all available commands (built-in + addons)."""
        commands = ["help", "clear", "exit", "set_step"]
        
        # Scan for addons
        try:
            addon_dir = os.path.join("src", "addons")
            if os.path.exists(addon_dir):
                for f in os.listdir(addon_dir):
                    if f.endswith(".py") and f != "__init__.py":
                        cmd_name = f[:-3].replace("_", " ")
                        if cmd_name not in commands:
                            commands.append(cmd_name)
        except Exception as e:
            print(f"Controller: Error scanning addons: {e}")
            
        return sorted(commands)

    def run_command(self, text, output_callback=None):
        """
        Executes a command string.
        output_callback: function that takes a string to display feedback.
        """
        def log(msg):
            if output_callback:
                output_callback(msg)
            else:
                print(f"Command Output: {msg}")

        text = text.strip()
        if not text:
            return
            
        # Remove prefix '>' if present
        if text.startswith(">"):
            text = text[1:].strip()

        parts = text.split()
        if not parts: return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 1. Built-in Commands
        if cmd == "help":
            log("Comandos: help, clear, exit, set_step [n], [addon_name]")
            return
        elif cmd == "clear":
            # clear might not make sense without a dedicated console, 
            # but we keep it for compatibility or future use.
            log("Consola limpiada (simulado)")
            return
        elif cmd == "exit":
            self.app.root.quit()
            return
        elif cmd == "set_step":
            if not args:
                log("Uso: set_step [numero]")
                return
            try:
                new_step = int(args[0])
                self.app.arbitrary_step = new_step
                self.config_manager.set_arbitrary_step(new_step)
                log(f"Step actualizado a: {new_step}")
            except ValueError:
                log("Error: El valor debe ser un entero.")
            return

        # 2. Addons search
        try:
            # Try to find the longest matching addon command
            module_name = None
            remaining_args = []
            all_words = [cmd] + args
            
            for i in range(len(all_words), 0, -1):
                potential_name = "_".join(all_words[:i])
                addon_path = os.path.join("src", "addons", f"{potential_name}.py")
                if os.path.exists(addon_path):
                    module_name = potential_name
                    remaining_args = all_words[i:]
                    break
            
            if module_name:
                module = importlib.import_module(f"src.addons.{module_name}")
                importlib.reload(module)
                
                if hasattr(module, 'run'):
                    result = module.run(self.app, remaining_args)
                    if result:
                        log(str(result))
                else:
                    log(f"Error: El addon '{module_name}' no tiene función run().")
            else:
                log(f"Comando '{cmd}' no encontrado.")
                
        except Exception as e:
            log(f"Error ejecutando comando: {e}")
