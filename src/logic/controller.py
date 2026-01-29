
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
                
        except Exception as e:
            print(f"Error loading project: {e}")

    def generate_prompt(self, user_text, selected_section=None, return_regions=False):
        """
        Generates a prompt based on user text and selected files.
        """
        # Determine scope
        if selected_section:
            section_files = self.section_manager.get_files_in_section(selected_section)
            # Filter all loaded files to just those in the section
            all_files = self.project_manager.get_files()
            # DIRECTLY use the files in the section, ignoring search relevance
            relevant_files = [f for f in all_files if f['path'] in section_files]
        else:
            # Search everything using relevant files finding
            relevant_files = self.project_manager.find_relevant_files(user_text)
        
        # Build Prompt
        prompt = f"User Request: {user_text}\n\nContext Files:\n"
        for f in relevant_files[:10]: # Limit to top 10 matches for now
            prompt += f"\n--- File: {f['rel_path']} ---\n"
            prompt += f.get('content', '') + "\n"
            
        if return_regions:
            prompt += "\n\nIMPORTANT: First, list all the regions that need modification. Then, return ONLY the COMPLETE modified regions. Only the regions that needed modification, and they must be complete. Do not return unchanged code."
            
        return prompt

    def get_relevant_files_for_ui(self, user_text, selected_section=None):
        """Helper to get relevant files for UI display."""
        if selected_section:
            section_files = self.section_manager.get_files_in_section(selected_section)
            all_files = self.project_manager.get_files()
            # If a section is selected, return all files in that section, ignoring user_text filtering
            return [f for f in all_files if f['path'] in section_files]

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
