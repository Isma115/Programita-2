
from src.logic.project_manager import ProjectManager
from src.logic.region_segment_manager import RegionSegmentManager
from src.logic.section_manager import SectionManager
from src.logic.config_manager import ConfigManager
from src.logic.global_hotkeys import GlobalHotkeyListener
from src.logic.prompt_rules import get_file_path_comment_inline_instruction
from src.ui.styles import Styles
import os
import pyperclip
import importlib
import re
import shutil

class Controller:
    """
    Manages the application state and logic separation.
    Acts as a bridge between the UI and the data/logic.
    """
    DYNAMIC_PASTE_INTRO_PROMPT = (
        'Te voy a pasar fichero por fichero, si el fichero que te pase no tiene el codigo '
        'necesario para realizar la modificacion, escribe simplemente "Siguiente" y no digas '
        "nada mas, pero en el caso de que tengas todos los ficheros y el codigo necesarios, realiza la peticion del usuario. "
        "Devuelve solo las partes de codigo que hayan necesitado modificacion y, en cada sitio exacto "
        "donde hayas tenido que modificar el codigo, deja un comentario que incluya exactamente "
        "[MODIFICACIÓN]."
    )
    DYNAMIC_PASTE_ADVANCE_DELAY_MS = 180

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
        self.section_manager = SectionManager(
            self.project_manager,
            self.config_manager.get_sections_path()
        )
        self.region_segment_manager = RegionSegmentManager(
            self.config_manager.get_sections_path()
        )
        self.hotkey_listener = GlobalHotkeyListener(self)
        self._doc_file_cache = {}
        self._dynamic_paste_state = None

    def get_sections_directory(self):
        """Returns the current directory used to store code sections."""
        return self.section_manager.get_sections_path()

    def set_sections_directory(self, path):
        """Updates the directory used to store code sections and persists it."""
        resolved_path = self.section_manager.set_sections_path(path)
        self.region_segment_manager.set_storage_root(resolved_path)
        self.config_manager.set_sections_path(resolved_path)
        return resolved_path

    def get_code_output_prompt(self, return_files=False, return_chunks=False):
        """Returns the instruction block that defines how the AI should return code."""
        path_comment_instruction = get_file_path_comment_inline_instruction()

        if return_chunks:
            return (
                "IMPORTANTE: Antes de contestar, indica la lista de partes que tienes que modificar. "
                "Después, devuelve SOLO las partes individuales de código que hayan necesitado modificación, "
                "respetando el formato \"Archivo ruta/al/archivo.ext (parte X/Y)\". "
                "No devuelvas partes ni código sin cambios. "
                f"{path_comment_instruction}"
            )

        if return_files:
            return (
                "IMPORTANTE: Antes de contestar, indica la lista de archivos que tienes que modificar. "
                "Después, devuelve SOLO los archivos de código completos que hayan necesitado modificación. "
                "No devuelvas archivos sin cambios. "
                f"{path_comment_instruction}"
            )

        return (
            "IMPORTANTE: Devuelve SOLO las partes de código que hayan necesitado modificación. "
            "No devuelvas código sin cambios. "
            "En cada sitio exacto donde hayas tenido que modificar el código, deja un comentario "
            "que incluya exactamente [MODIFICACIÓN]. "
            f"{path_comment_instruction}"
        )

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

    def generate_prompt(
        self,
        user_text,
        selected_section=None,
        selected_subsection=None,
        return_files=False,
        return_chunks=False,
        include_file_headers=True,
        include_project_tree=False,
        min_files=10,
        file_paths=None
    ):
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
                # If a subsection is selected, use only its files
                if selected_subsection:
                    section_files_list = self.section_manager.get_files_in_subsection(selected_section, selected_subsection)
                else:
                    section_files_list = self.section_manager.get_files_in_section(selected_section)
                # Filter all loaded files to just those in the section/subsection
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
                relevant_files = self.project_manager.find_relevant_files(user_text, min_files=min_files)
        
        # Build Prompt
        prompt = f"Petición del Usuario: {user_text}\n\nArchivos de Contexto:\n"
        for f in relevant_files: # All relevant files according to min_files
            for part_label, part_content in self._split_file_for_prompt(f, return_chunks=return_chunks):
                if include_file_headers:
                    prompt += f"\n--- Archivo: {part_label} ---\n"
                    prompt += part_content + "\n"
                else:
                    prompt += part_content

        if include_project_tree:
            project_tree = self.project_manager.get_project_tree_text()
            if project_tree:
                prompt += f"\n\nÁrbol del Proyecto:\n{project_tree}"
        
        # Include table samples if section has tables
        if selected_section:
            section_tables = self.section_manager.get_tables_in_section(selected_section)
            if section_tables:
                table_samples = self._get_table_samples_for_prompt(section_tables)
                if table_samples:
                    prompt += f"\n\nMuestras de Base de Datos:\n{table_samples}"
        

            
        prompt += f"\n\n{self.get_code_output_prompt(return_files=return_files, return_chunks=return_chunks)}"
            
        return prompt

    def _split_file_for_prompt(self, file_info, return_chunks=False):
        """
        Returns either the full file or its separated parts for prompt generation.
        """
        rel_path = file_info.get("rel_path", "archivo")
        content = file_info.get("content") or ""

        if not return_chunks:
            return [(rel_path, content.rstrip("\n"))]

        lines = content.splitlines(keepends=True)

        segments = []
        current = []

        for line in lines:
            if self._is_prompt_separator_line(line):
                segment = "".join(current).rstrip("\n")
                if segment.strip():
                    segments.append(segment)
                current = []
                continue

            current.append(line)

        final_segment = "".join(current).rstrip("\n")
        if final_segment.strip() or not segments:
            segments.append(final_segment)

        prompt_parts = []
        total_parts = len(segments)
        for index, segment in enumerate(segments, start=1):
            label = f"{rel_path} (parte {index}/{total_parts})"
            prompt_parts.append((label, segment))

        return prompt_parts

    def _is_prompt_separator_line(self, line):
        """
        Returns True when the line is a standalone comment with marker [separación].
        Supports common single-line and block-comment wrappers.
        """
        stripped = line.strip()
        if not stripped:
            return False

        normalized = stripped

        if normalized.startswith("<!--") and normalized.endswith("-->"):
            normalized = normalized[4:-3].strip()
        elif normalized.startswith("/*") and normalized.endswith("*/"):
            normalized = normalized[2:-2].strip()
        elif normalized.startswith("//"):
            normalized = normalized[2:].strip()
        elif normalized.startswith("--"):
            normalized = normalized[2:].strip()
        elif normalized.startswith("#") or normalized.startswith(";"):
            normalized = normalized[1:].strip()
        elif normalized.startswith("*"):
            normalized = normalized[1:].strip()

        normalized = normalized.strip("*").strip().lower()
        return normalized in ("[separación]", "[separacion]")

    def get_project_tree_prompt_block(self):
        """Returns the project tree block formatted for prompts."""
        project_tree = self.project_manager.get_project_tree_text()
        if not project_tree:
            return ""
        return f"ÁRBOL COMPLETO DEL PROYECTO:\n{project_tree}"

    def _get_table_samples_for_prompt(self, table_names, limit=5):
        """Gets sample data for given tables using only an existing active DB connection."""
        connection = None
        
        try:
            # Try to reuse existing connection from database_view
            if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'database_view'):
                db_view = self.app.layout.database_view
                if db_view.connection and db_view.connection.is_connected():
                    connection = db_view.connection
            
            # Do not auto-connect/reconnect from config here.
            # DB lifecycle is managed manually from DatabaseView buttons.
            if not connection:
                print("Controller: No active DB connection; skipping table samples")
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

    def get_relevant_files_for_ui(
        self,
        user_text,
        selected_section=None,
        selected_subsection=None,
        extension="",
        min_files=0,
        max_files=None
    ):
        """Helper to get relevant files for UI display."""
        all_files = self.project_manager.get_files()
        
        # 1. Scope Filtering (Section/Subsection or Global)
        if selected_section:
            if selected_subsection:
                # Use only the subsection's files
                section_files_paths = self.section_manager.get_files_in_subsection(selected_section, selected_subsection)
            else:
                # Use all files from the parent section
                section_files_paths = self.section_manager.get_files_in_section(selected_section)
            files_map = {f['path']: f for f in all_files}
            pool = [files_map[p] for p in section_files_paths if p in files_map]
        else:
            pool = all_files

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
                pool = [f for f in pool if any(f['rel_path'].lower().endswith(ext) for ext in ext_list)]
        else:
            pool = [f for f in pool if self.project_manager.is_default_code_file(f['rel_path'])]
            
        # 3. Search, minimum padding and optional maximum cap
        if not user_text:
            if max_files is not None:
                try:
                    max_files = max(int(max_files), int(min_files))
                except (TypeError, ValueError):
                    max_files = None
            if max_files is not None:
                return pool[:max_files]
            return pool
        else:
            # find_relevant_files scores and ranks files, then pads up to min_files from the pool
            return self.project_manager.find_relevant_files(
                user_text,
                relevant_files_subset=pool,
                min_files=min_files,
                max_files=max_files
            )

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

    def refresh_cached_file_content(self, path, content=None):
        """
        Refreshes the in-memory cache for a project file after an external write.
        Returns True if the file belonged to the loaded project.
        """
        if content is None:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception as e:
                print(f"Controller: Error refreshing cache for {path}: {e}")
                return False

        for f in self.project_manager.get_files():
            if f['path'] == path:
                f['content'] = content
                return True

        return False

    def remove_modification_comments_from_project(self):
        """
        Removes comments containing [MODIFICACIÓN] from all loaded project files.
        Returns (changed_files, removed_comments, errors).
        """
        changed_files = 0
        removed_comments = 0
        errors = []

        for file_info in self.project_manager.get_files():
            path = file_info.get("path")
            original_content = file_info.get("content") or ""
            cleaned_content, removed_in_file = self._strip_modification_comments(original_content)

            if removed_in_file <= 0 or cleaned_content == original_content:
                continue

            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(cleaned_content)
                file_info["content"] = cleaned_content
                changed_files += 1
                removed_comments += removed_in_file
            except Exception as e:
                errors.append(f"{path}: {e}")

        return changed_files, removed_comments, errors

    def _strip_modification_comments(self, text):
        """
        Removes whole comments containing [MODIFICACIÓN] while preserving code and line structure.
        Supports common single-line and block comment syntaxes.
        """
        marker = "[modificación]"
        output = []
        removed_comments = 0
        i = 0
        text_len = len(text)
        string_delim = None
        triple_string_delim = None

        while i < text_len:
            if triple_string_delim is not None:
                if text.startswith(triple_string_delim, i):
                    output.append(triple_string_delim)
                    i += 3
                    triple_string_delim = None
                    continue

                if text[i] == "\\" and i + 1 < text_len:
                    output.append(text[i:i + 2])
                    i += 2
                    continue

                output.append(text[i])
                i += 1
                continue

            if string_delim is not None:
                if text[i] == "\\" and i + 1 < text_len:
                    output.append(text[i:i + 2])
                    i += 2
                    continue

                output.append(text[i])
                if text[i] == string_delim:
                    string_delim = None
                i += 1
                continue

            if text.startswith("'''", i) or text.startswith('"""', i):
                triple_string_delim = text[i:i + 3]
                output.append(triple_string_delim)
                i += 3
                continue

            if text[i] in ("'", '"', "`"):
                string_delim = text[i]
                output.append(text[i])
                i += 1
                continue

            if text.startswith("<!--", i):
                comment_text, end_idx = self._consume_block_comment(text, i, "-->")
                if marker in comment_text.lower():
                    self._trim_current_line_whitespace(output)
                    output.append(self._preserve_comment_newlines(comment_text))
                    removed_comments += 1
                else:
                    output.append(comment_text)
                i = end_idx
                continue

            if text.startswith("/*", i):
                comment_text, end_idx = self._consume_block_comment(text, i, "*/")
                if marker in comment_text.lower():
                    self._trim_current_line_whitespace(output)
                    output.append(self._preserve_comment_newlines(comment_text))
                    removed_comments += 1
                else:
                    output.append(comment_text)
                i = end_idx
                continue

            if text.startswith("//", i):
                comment_text, end_idx = self._consume_line_comment(text, i)
                if marker in comment_text.lower():
                    self._trim_current_line_whitespace(output)
                    removed_comments += 1
                else:
                    output.append(comment_text)
                i = end_idx
                continue

            if self._is_dash_dash_comment_start(text, i):
                comment_text, end_idx = self._consume_line_comment(text, i)
                if marker in comment_text.lower():
                    self._trim_current_line_whitespace(output)
                    removed_comments += 1
                else:
                    output.append(comment_text)
                i = end_idx
                continue

            if self._is_hash_comment_start(text, i):
                comment_text, end_idx = self._consume_line_comment(text, i)
                if marker in comment_text.lower():
                    self._trim_current_line_whitespace(output)
                    removed_comments += 1
                else:
                    output.append(comment_text)
                i = end_idx
                continue

            output.append(text[i])
            i += 1

        return "".join(output), removed_comments

    def _consume_line_comment(self, text, start_idx):
        end_idx = text.find("\n", start_idx)
        if end_idx == -1:
            end_idx = len(text)
        return text[start_idx:end_idx], end_idx

    def _consume_block_comment(self, text, start_idx, end_marker):
        end_idx = text.find(end_marker, start_idx + len(end_marker) - 1)
        if end_idx == -1:
            return text[start_idx:], len(text)
        end_idx += len(end_marker)
        return text[start_idx:end_idx], end_idx

    def _trim_current_line_whitespace(self, output):
        idx = len(output) - 1
        while idx >= 0 and output[idx] in (" ", "\t"):
            idx -= 1
        del output[idx + 1:]

    def _preserve_comment_newlines(self, comment_text):
        return "".join(ch for ch in comment_text if ch in "\r\n")

    def _is_hash_comment_start(self, text, index):
        if index < 0 or index >= len(text) or text[index] != "#":
            return False
        if index == 0:
            return True
        return text[index - 1].isspace()

    def _is_dash_dash_comment_start(self, text, index):
        if not text.startswith("--", index):
            return False

        prev_ok = index == 0 or text[index - 1].isspace()
        next_index = index + 2
        next_ok = (
            next_index >= len(text)
            or text[next_index].isspace()
            or text[next_index] == "["
        )
        return prev_ok and next_ok

    def save_content_to_codigo_txt(self, content, append=False, append_separator="\n\n"):
        """Saves or appends content to ~/Documents/codigo.txt."""
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            file_path = os.path.join(documents_path, "codigo.txt")
            os.makedirs(documents_path, exist_ok=True)
            
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                if append and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    f.write(append_separator)
                f.write(content)
            return True, file_path
        except Exception as e:
            return False, str(e)

    def export_files_to_codigo_folder(self, files_data):
        """Exports only the selected files to ~/Documents/codigo/ flatly."""
        try:
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
            folder_path = os.path.join(documents_path, "codigo")
            os.makedirs(documents_path, exist_ok=True)

            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
            os.makedirs(folder_path, exist_ok=True)

            written_files = []
            used_names = {}
            for file_info in files_data or []:
                rel_path = file_info.get("rel_path") or file_info.get("path") or "archivo.txt"
                filename = self._get_flat_export_filename(rel_path, used_names)
                target_path = os.path.join(folder_path, filename)

                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(file_info.get("content", ""))

                written_files.append(target_path)

            return True, folder_path
        except Exception as e:
            return False, str(e)

    def _get_flat_export_filename(self, rel_path, used_names):
        """Returns a safe filename for flat exports, avoiding collisions."""
        normalized = (rel_path or "").replace("\\", "/").strip()
        filename = os.path.basename(normalized) or "archivo.txt"
        filename = filename.replace("/", "_").replace("\\", "_")

        base, ext = os.path.splitext(filename)
        if not base:
            base = "archivo"

        counter = used_names.get(filename.lower(), 0)
        if counter == 0:
            used_names[filename.lower()] = 1
            return filename

        while True:
            counter += 1
            candidate = f"{base}__{counter}{ext}"
            key = candidate.lower()
            if key not in used_names:
                used_names[filename.lower()] = counter
                used_names[key] = 1
                return candidate

    def _get_doc_root(self):
        """Returns the configured documentation root folder, if valid."""
        doc_dir = self.config_manager.get_doc_path()
        if not doc_dir:
            return None
        doc_dir = os.path.abspath(doc_dir)
        if not os.path.isdir(doc_dir):
            return None
        return doc_dir

    def get_existing_doc_directories(self):
        """Returns current and historical documentation directories that still exist."""
        return self.config_manager.get_existing_doc_directories()

    def _get_doc_sections(self):
        """Returns available documentation sections as [(name, abs_path), ...]."""
        doc_root = self._get_doc_root()
        if not doc_root:
            return []
        sections = []
        try:
            for name in os.listdir(doc_root):
                section_path = os.path.join(doc_root, name)
                if os.path.isdir(section_path):
                    sections.append((name, section_path))
        except Exception:
            return []
        sections.sort(key=lambda item: item[0].lower())
        return sections

    def _get_markdown_files_for_section(self, section_path):
        """Returns sorted markdown files inside a documentation section folder."""
        files = []
        if not section_path or not os.path.isdir(section_path):
            return files
        try:
            for root, _, filenames in os.walk(section_path):
                for filename in filenames:
                    if filename.lower().endswith(".md"):
                        files.append(os.path.join(root, filename))
        except Exception:
            return []
        files.sort(key=lambda path: os.path.relpath(path, section_path).lower())
        return files

    def _read_doc_file_cached(self, path):
        """Reads a documentation file using a tiny mtime-based cache."""
        try:
            stat = os.stat(path)
        except Exception:
            return ""

        cached = self._doc_file_cache.get(path)
        cache_key = (stat.st_mtime_ns, stat.st_size)
        if cached and cached.get("key") == cache_key:
            return cached.get("content", "")

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            return ""

        self._doc_file_cache[path] = {
            "key": cache_key,
            "content": content,
        }
        return content

    def search_documentation(self, query, limit=12):
        """
        Searches across every known documentation directory whose path still exists.
        Returns ranked matches with enough metadata to open the document directly.
        """
        raw_query = (query or "").strip()
        if not raw_query:
            return {
                "results": [],
                "roots_checked": self.get_existing_doc_directories(),
            }

        normalized_query = " ".join(raw_query.lower().split())
        if not normalized_query:
            return {
                "results": [],
                "roots_checked": self.get_existing_doc_directories(),
            }

        doc_extensions = {".md", ".markdown", ".mdown", ".txt", ".rst", ".adoc"}
        results = []
        roots_checked = self.get_existing_doc_directories()

        def build_snippet(content, start_idx, query_text):
            start = max(start_idx - 80, 0)
            end = min(start_idx + len(query_text) + 120, len(content))
            snippet = content[start:end].replace("\n", " ").replace("\r", " ")
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
            return snippet

        for doc_root in roots_checked:
            for walk_root, _, filenames in os.walk(doc_root):
                for filename in filenames:
                    extension = os.path.splitext(filename)[1].lower()
                    if extension not in doc_extensions:
                        continue

                    file_path = os.path.join(walk_root, filename)
                    rel_path = os.path.relpath(file_path, doc_root)
                    rel_path_lower = rel_path.lower()
                    filename_lower = filename.lower()
                    section_name = rel_path.split(os.sep, 1)[0] if os.sep in rel_path else ""

                    content = self._read_doc_file_cached(file_path)
                    content_lower = content.lower()

                    path_match = normalized_query in rel_path_lower
                    content_idx = content_lower.find(normalized_query)
                    if not path_match and content_idx == -1:
                        continue

                    occurrences = content_lower.count(normalized_query) if content_idx != -1 else 0
                    score = 0
                    if normalized_query in filename_lower:
                        score += 220
                    if path_match:
                        score += 140
                    if section_name and normalized_query in section_name.lower():
                        score += 80
                    if content_idx != -1:
                        score += 60
                        score += min(occurrences, 8) * 12
                        score += max(0, 40 - min(content_idx, 1200) // 30)

                    results.append({
                        "score": score,
                        "query": raw_query,
                        "path": file_path,
                        "doc_root": doc_root,
                        "doc_root_name": os.path.basename(doc_root.rstrip(os.sep)) or doc_root,
                        "rel_path": rel_path,
                        "section_name": section_name,
                        "filename": filename,
                        "snippet": build_snippet(content, max(content_idx, 0), normalized_query) if content_idx != -1 else rel_path,
                        "match_count": occurrences if occurrences else (1 if path_match else 0),
                    })

        results.sort(
            key=lambda item: (
                -item["score"],
                item["rel_path"].lower(),
                item["doc_root"].lower(),
            )
        )

        return {
            "results": results[:limit],
            "roots_checked": roots_checked,
        }

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

        # 3. Documentation sections (folder-based structure)
        for section_name, section_path in self._get_doc_sections():
            assets.append({
                'name': section_name,
                'type': 'doc',
                'path': section_path
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
            # Folder-based doc sections (preferred)
            if os.path.isdir(path):
                section_path = path
                section_name = os.path.basename(section_path.rstrip(os.sep))
                section_files = self._get_markdown_files_for_section(section_path)
                parts = [f"--- Sección Doc: {section_name} ---"]
                for fpath in section_files:
                    try:
                        rel = os.path.relpath(fpath, section_path)
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                            parts.append(f"\n--- {rel} ---\n{fh.read()}")
                    except Exception:
                        pass
                return "\n".join(parts) if len(parts) > 1 else f"--- Sección Doc: {section_name} ---\n(Sin archivos)"

            # Legacy fallback: section metadata from SectionManager
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

    def get_structure_sizes(self, selected_section=None, selected_subsection=None):
        """
        Returns function sizes for the given section/subsection scope.
        If no section is provided, the whole loaded project is used.
        """
        file_paths = None

        if selected_section:
            if selected_subsection:
                file_paths = self.section_manager.get_files_in_subsection(selected_section, selected_subsection)
            else:
                file_paths = self.section_manager.get_files_in_section(selected_section)

        functions = self.project_manager.extract_functions(file_paths=file_paths)
        type_priority = {
            "function": 0,
            "method": 0,
            "procedure": 0,
            "class": 1,
            "interface": 1,
            "struct": 1,
            "enum": 1,
            "namespace": 2,
            "module": 2,
            "tag": 3
        }
        return sorted(
            functions,
            key=lambda item: (
                type_priority.get(item.get("type", ""), 9),
                -item.get("line_count", 0),
                item.get("file_rel_path", ""),
                item.get("start_line", 0),
                item.get("name", "")
            )
        )

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

    def start_dynamic_paste(self, files_data, user_text):
        """Starts a file-by-file dynamic clipboard session."""
        normalized_user_text = str(user_text or "").strip()
        entries = []
        for index, file_data in enumerate(files_data or []):
            rel_path = str(file_data.get("rel_path", "") or "").strip()
            content = str(file_data.get("content", "") or "")
            if not rel_path:
                continue
            entries.append(
                {
                    "rel_path": rel_path,
                    "clipboard_text": self._build_dynamic_paste_clipboard_text(
                        normalized_user_text,
                        rel_path,
                        content,
                        include_intro=(index == 0)
                    ),
                }
            )

        if not entries:
            return False, "No hay ficheros disponibles para el pegado dinamico."

        first_text = entries[0]["clipboard_text"]
        if not self.copy_to_clipboard(first_text):
            return False, "No se pudo copiar el primer fichero al portapapeles."

        self._dynamic_paste_state = {
            "entries": entries,
            "current_index": 0,
            "awaiting_advance": False,
            "advance_token": 0,
        }
        self._notify_dynamic_paste_state_changed()
        return True, f"Pegado dinamico iniciado con {len(entries)} fichero(s)."

    def cancel_dynamic_paste(self):
        """Stops the active dynamic clipboard session, if any."""
        if self._dynamic_paste_state is None:
            return False
        self._dynamic_paste_state = None
        self._notify_dynamic_paste_state_changed()
        return True

    def schedule_dynamic_paste_advance(self):
        """Queues the copy of the next file after the current paste shortcut."""
        state = self._dynamic_paste_state
        if not state:
            return False
        if state.get("awaiting_advance"):
            return True

        root = getattr(self.app, "root", None)
        if root is None:
            return False

        state["awaiting_advance"] = True
        state["advance_token"] = int(state.get("advance_token", 0)) + 1
        advance_token = state["advance_token"]

        def _advance():
            current_state = self._dynamic_paste_state
            if not current_state or current_state is not state:
                return
            if advance_token != current_state.get("advance_token"):
                return

            current_state["awaiting_advance"] = False
            next_index = int(current_state.get("current_index", 0)) + 1
            entries = current_state.get("entries", [])

            if next_index >= len(entries):
                self.cancel_dynamic_paste()
                return

            next_entry = entries[next_index]
            copied = self.copy_to_clipboard(next_entry.get("clipboard_text", ""))
            if not copied:
                self.cancel_dynamic_paste()
                return

            current_state["current_index"] = next_index
            self._notify_dynamic_paste_state_changed()

        root.after(self.DYNAMIC_PASTE_ADVANCE_DELAY_MS, _advance)
        return True

    def has_dynamic_paste_active(self):
        """Returns whether a dynamic clipboard session is active."""
        return bool(self._dynamic_paste_state)

    def get_dynamic_paste_status(self):
        """Returns UI-friendly information about the current dynamic clipboard session."""
        state = self._dynamic_paste_state
        if not state:
            return {
                "active": False,
                "current_number": 0,
                "total": 0,
                "current_file": "",
            }

        entries = state.get("entries", [])
        current_index = int(state.get("current_index", 0))
        current_entry = entries[current_index] if 0 <= current_index < len(entries) else {}
        return {
            "active": True,
            "current_number": current_index + 1,
            "total": len(entries),
            "current_file": current_entry.get("rel_path", ""),
        }

    def _build_dynamic_paste_clipboard_text(self, user_text, rel_path, content, include_intro=False):
        """Builds the clipboard payload for a single dynamic-paste step."""
        lines = []
        if include_intro:
            lines.extend(
                [
                    self.DYNAMIC_PASTE_INTRO_PROMPT,
                    "",
                    "Peticion del usuario:",
                    user_text,
                    "",
                ]
            )

        lines.append(f"--- Archivo: {rel_path} ---")
        lines.append(content.rstrip("\n"))
        return "\n".join(lines).rstrip() + "\n"

    def _notify_dynamic_paste_state_changed(self):
        """Refreshes the Code view controls that reflect dynamic clipboard state."""
        try:
            code_view = getattr(getattr(self.app, "layout", None), "code_view", None)
            if code_view and hasattr(code_view, "refresh_dynamic_paste_controls"):
                code_view.refresh_dynamic_paste_controls()
        except Exception as e:
            print(f"Controller: Error notifying dynamic paste state change: {e}")

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
