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

    def _normalize_path(self, path):
        """Returns a normalized absolute path when possible."""
        if not path:
            return None
        try:
            return os.path.normpath(os.path.abspath(path))
        except Exception:
            return path

    def get_sections_path(self):
        """Returns the saved code sections folder path, or the default local folder."""
        saved_path = self._normalize_path(self.config.get("sections_path"))
        if saved_path:
            return saved_path
        return self._normalize_path(os.path.join(os.getcwd(), "sections"))

    def set_sections_path(self, path):
        """Sets the code sections folder path and saves config."""
        self.config["sections_path"] = self._normalize_path(path)
        self.save_config()

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
        return self._normalize_path(self.config.get("doc_path"))

    def set_doc_path(self, path):
        """Sets the documentation folder path and saves config."""
        normalized = self._normalize_path(path)
        self.config["doc_path"] = normalized
        if normalized:
            history = self.get_doc_path_history()
            if normalized in history:
                history.remove(normalized)
            history.insert(0, normalized)
            self.config["doc_path_history"] = history
        self.save_config()

    def get_doc_path_history(self):
        """Returns the saved documentation folder history."""
        history = self.config.get("doc_path_history", [])
        if not isinstance(history, list):
            history = []

        ordered = []
        seen = set()
        current = self._normalize_path(self.config.get("doc_path"))

        for path in history:
            normalized = self._normalize_path(path)
            if not normalized or normalized in seen:
                continue
            ordered.append(normalized)
            seen.add(normalized)

        if current and current not in seen:
            ordered.insert(0, current)

        return ordered

    def get_existing_doc_directories(self):
        """Returns the doc history entries whose directories still exist."""
        existing = []
        seen = set()

        for path in self.get_doc_path_history():
            if path in seen:
                continue
            seen.add(path)
            if os.path.isdir(path):
                existing.append(path)

        return existing

    def get_prompting_path(self):
        """Returns the saved prompting folder path, or None."""
        return self.config.get("prompting_path")

    def set_prompting_path(self, path):
        """Sets the prompting folder path and saves config."""
        self.config["prompting_path"] = path
        self.save_config()

    def get_file_limit(self):
        """Returns the file limit, defaulting to 100."""
        return self.config.get("file_limit", 100)

    def set_file_limit(self, limit):
        """Sets the file limit and saves config."""
        self.config["file_limit"] = int(limit)
        self.save_config()

    def get_code_extensions_filter(self):
        """Returns the saved extensions filter for Code View."""
        value = self.config.get("code_extensions_filter", "")
        return value if isinstance(value, str) else ""

    def set_code_extensions_filter(self, value):
        """Sets the extensions filter for Code View and saves config."""
        self.config["code_extensions_filter"] = value if isinstance(value, str) else ""
        self.save_config()

    def get_return_regions(self):
        """Returns whether to return regions, defaulting to False."""
        return self.config.get("return_regions", False)

    def set_return_regions(self, value):
        """Sets whether to return regions and saves config."""
        self.config["return_regions"] = bool(value)
        self.save_config()

    def get_return_structures(self):
        """Returns whether to return complete modified structures, defaulting to False."""
        return self.config.get("return_structures", False)

    def set_return_structures(self, value):
        """Sets whether to return complete modified structures and saves config."""
        self.config["return_structures"] = bool(value)
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
            "is_editor_mode": False,
            "code_sash_ratio": 0.7,
            "is_fullscreen_mode": False,
            "markdown_preview_zoom": 1.2
        })

    def set_doc_view_settings(
        self,
        is_dark_mode,
        is_editor_mode,
        code_sash_ratio=None,
        is_fullscreen_mode=None,
        markdown_preview_zoom=None
    ):
        """Sets the DocView settings and saves config."""
        settings = {
            "is_dark_mode": bool(is_dark_mode),
            "is_editor_mode": bool(is_editor_mode)
        }
        if code_sash_ratio is not None:
            try:
                settings["code_sash_ratio"] = float(code_sash_ratio)
            except Exception:
                settings["code_sash_ratio"] = 0.7
        else:
            prev = self.config.get("doc_view_settings", {})
            if "code_sash_ratio" in prev:
                settings["code_sash_ratio"] = prev.get("code_sash_ratio")
        if is_fullscreen_mode is not None:
            settings["is_fullscreen_mode"] = bool(is_fullscreen_mode)
        else:
            prev = self.config.get("doc_view_settings", {})
            settings["is_fullscreen_mode"] = bool(prev.get("is_fullscreen_mode", False))
        if markdown_preview_zoom is not None:
            try:
                settings["markdown_preview_zoom"] = float(markdown_preview_zoom)
            except Exception:
                settings["markdown_preview_zoom"] = 1.2
        else:
            prev = self.config.get("doc_view_settings", {})
            try:
                settings["markdown_preview_zoom"] = float(prev.get("markdown_preview_zoom", 1.2))
            except Exception:
                settings["markdown_preview_zoom"] = 1.2
        self.config["doc_view_settings"] = settings
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

    def get_last_doc_file(self):
        """Returns the last loaded document file path."""
        return self.config.get("last_doc_file")

    def set_last_doc_file(self, file_path):
        """Sets the last loaded document file path and saves config."""
        self.config["last_doc_file"] = self._normalize_path(file_path)
        self.save_config()
