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
