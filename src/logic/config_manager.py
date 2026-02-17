import json
import os

class ConfigManager:
    """
    Manages application configuration using a JSON file.
    """
    CONFIG_FILENAME = "config.json"

    def __init__(self):
        # Determine config file path (current working directory or next to main.py)
        # We will iterate to find a good place. For now, let's use the current working directory
        # which is usually the project root where main.py is run from.
        self.config_path = os.path.join(os.getcwd(), self.CONFIG_FILENAME)
        self.config = {}
        self.load_config()

    def load_config(self):
        """Loads configuration from the JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"ConfigManager: Error loading config: {e}")
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        """Saves current configuration to the JSON file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"ConfigManager: Error saving config: {e}")

    def get_last_project(self):
        """Returns the path of the last opened project, or None."""
        return self.config.get("last_project")

    def set_last_project(self, path):
        """Sets the last opened project path and saves config."""
        self.config["last_project"] = path
        # Also register in project_directories if not already present
        dirs = self.get_project_directories()
        if path not in dirs:
            dirs.append(path)
            self.config["project_directories"] = dirs
        self.save_config()

    def get_project_directories(self):
        """Returns the list of registered project directories."""
        return self.config.get("project_directories", [])

    def set_project_directories(self, dirs):
        """Sets the list of project directories and saves config."""
        self.config["project_directories"] = list(dirs)
        self.save_config()

    def get_current_project_index(self):
        """Returns the index of the currently selected project."""
        return self.config.get("current_project_index", 0)

    def set_current_project_index(self, idx):
        """Sets the current project index and saves config."""
        self.config["current_project_index"] = int(idx)
        self.save_config()

    def get_doc_path(self):
        """Returns the saved documentation folder path, or None."""
        return self.config.get("doc_path")

    def set_doc_path(self, path):
        """Sets the documentation folder path and saves config."""
        self.config["doc_path"] = path
        self.save_config()

    def get_file_limit(self):
        """Returns the file limit, defaulting to 100."""
        return self.config.get("file_limit", 100)

    def set_file_limit(self, limit):
        """Sets the file limit and saves config."""
        self.config["file_limit"] = int(limit)
        self.save_config()

    def get_return_regions(self):
        """Returns whether to return regions, defaulting to False."""
        return self.config.get("return_regions", False)

    def set_return_regions(self, value):
        """Sets whether to return regions and saves config."""
        self.config["return_regions"] = bool(value)
        self.save_config()

    def get_enable_hotkeys(self):
        """Returns whether global hotkeys are enabled, defaulting to True."""
        return self.config.get("enable_hotkeys", True)

    def set_enable_hotkeys(self, value):
        """Sets whether global hotkeys are enabled and saves config."""
        self.config["enable_hotkeys"] = bool(value)
        self.save_config()

    def get_theme_colors(self):
        """Returns the saved theme colors or None if default."""
        return self.config.get("theme_colors")

    def set_theme_colors(self, accent, hover):
        """Sets the theme accent colors and saves config."""
        self.config["theme_colors"] = {
            "COLOR_ACCENT": accent,
            "COLOR_ACCENT_HOVER": hover
        }
        self.save_config()

    def get_arbitrary_step(self):
        """Returns the arbitrary search step, defaulting to 1."""
        return self.config.get("arbitrary_step", 1)

    def set_arbitrary_step(self, step):
        """Sets the arbitrary search step and saves config."""
        self.config["arbitrary_step"] = int(step)
        self.save_config()

    def get_db_config(self):
        """Returns the saved database configuration or an empty dict."""
        return self.config.get("db_config", {})

    def set_db_config(self, db_config):
        """Sets the database configuration and saves config."""
        self.config["db_config"] = db_config
        self.save_config()

    def get_doc_view_settings(self):
        """Returns the saved DocView settings or default values."""
        return self.config.get("doc_view_settings", {
            "is_dark_mode": False,
            "is_editor_mode": False
        })

    def set_doc_view_settings(self, is_dark_mode, is_editor_mode):
        """Sets the DocView settings and saves config."""
        self.config["doc_view_settings"] = {
            "is_dark_mode": bool(is_dark_mode),
            "is_editor_mode": bool(is_editor_mode)
        }
        self.save_config()

    def get_last_code_section(self):
        """Returns the last selected section in Code View."""
        return self.config.get("last_code_section")

    def set_last_code_section(self, section_name):
        """Sets the last selected section in Code View and saves config."""
        self.config["last_code_section"] = section_name
        self.save_config()

    def get_last_doc_section(self):
        """Returns the last selected section in Doc View."""
        return self.config.get("last_doc_section")

    def set_last_doc_section(self, section_name):
        """Sets the last selected section in Doc View and saves config."""
        self.config["last_doc_section"] = section_name
        self.save_config()

    def get_implementation_mode(self):
        """Returns whether implementation mode is enabled, defaulting to False."""
        return self.config.get("implementation_mode", False)

    def set_implementation_mode(self, value):
        """Sets whether implementation mode is enabled and saves config."""
        self.config["implementation_mode"] = bool(value)
        self.save_config()
