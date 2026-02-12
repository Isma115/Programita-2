
from src.logic.project_manager import ProjectManager
from src.logic.section_manager import SectionManager
from src.logic.config_manager import ConfigManager
from src.logic.global_hotkeys import GlobalHotkeyListener
from src.ui.styles import Styles
import os

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

    def generate_prompt(self, user_text, selected_section=None, return_regions=False):
        """
        Generates a prompt based on user text and selected files.
        """
        # Determine scope
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
        for f in relevant_files[:10]: # Limit to top 10 matches for now (or top 10 ordered files in section)
            prompt += f"\n--- Archivo: {f['rel_path']} ---\n"
            prompt += f.get('content', '') + "\n"
            
        if return_regions:
            prompt += "\n\nIMPORTANTE: Primero, lista todas las regiones que necesitan modificación. Después, devuelve SOLO las regiones modificadas COMPLETAS. Solo las regiones que necesitaron modificación, y deben estar completas. No devuelvas código sin cambios."
        # else:
        #     prompt += "\n\nIMPORTANTE: Devolver solamente la modificación o modificaciones necesarias."
            
        return prompt

    def get_relevant_files_for_ui(self, user_text, selected_section=None):
        """Helper to get relevant files for UI display."""
        if selected_section:
            section_files_list = self.section_manager.get_files_in_section(selected_section)
            all_files = self.project_manager.get_files()
            
            # If a section is selected, return all files in that section, preserving order
            files_map = {f['path']: f for f in all_files}
            ordered_files = []
            for path in section_files_list:
                 if path in files_map:
                     ordered_files.append(files_map[path])
            return ordered_files

        if not user_text:
            return self.project_manager.get_files()
            
        return self.project_manager.find_relevant_files(user_text)

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

    def show_console_view(self):
        """
        Switch the main content area to the Console view.
        """
        print("Logic: Switching to Console View")
        self.app.layout.show_console_tab()

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
