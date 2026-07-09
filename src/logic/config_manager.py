import json
import os
import shutil
from src.logic.app_paths import (
    bundled_path,
    config_file_path,
    default_segments_dir,
    default_sections_dir,
    ensure_app_support_dir,
    is_frozen,
    project_root,
    running_from_project_root,
)

class ConfigManager:
    """
    Manages application configuration using a JSON file.
    """
    CONFIG_FILENAME = "config.json"

    def __init__(self):
        self._project_root = str(project_root())
        self._bootstrap_runtime_data()
        self.config_path = self._resolve_config_path()
        self.config = {}
        self.load_config()

    def _bootstrap_runtime_data(self):
        """Copies bundled defaults to Application Support on first run."""
        if not is_frozen():
            return

        try:
            ensure_app_support_dir()
            self._copy_dir_if_empty(bundled_path("sections"), default_sections_dir())
            self._copy_dir_if_empty(bundled_path("segments"), default_segments_dir())
            self._copy_file_if_missing(
                bundled_path("ias_disponibles.txt"),
                os.path.join(ensure_app_support_dir(), "ias_disponibles.txt"),
            )
        except Exception as exc:
            print(f"ConfigManager: Error bootstrapping runtime data: {exc}")

    def _copy_dir_if_empty(self, source_dir, target_dir):
        if not os.path.isdir(source_dir):
            return
        os.makedirs(target_dir, exist_ok=True)
        has_files = any(name.endswith(".json") for name in os.listdir(target_dir))
        if has_files:
            return
        for filename in os.listdir(source_dir):
            if not filename.endswith(".json"):
                continue
            source = os.path.join(source_dir, filename)
            target = os.path.join(target_dir, filename)
            if os.path.isfile(source):
                shutil.copy2(source, target)

    def _copy_file_if_missing(self, source_file, target_file):
        if not os.path.isfile(source_file):
            return
        if os.path.exists(target_file):
            return
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        shutil.copy2(source_file, target_file)

    def _resolve_config_path(self):
        """Resolves where configuration should be persisted."""
        if is_frozen():
            return config_file_path()

        cwd_path = os.path.join(os.getcwd(), self.CONFIG_FILENAME)
        root_path = os.path.join(self._project_root, self.CONFIG_FILENAME)

        if os.path.exists(cwd_path):
            return cwd_path
        if os.path.exists(root_path):
            return root_path
        if running_from_project_root():
            return root_path
        return cwd_path

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

        migrated = False
        if "return_files" not in self.config:
            self.config["return_files"] = False
            migrated = True
        if "return_chunks" not in self.config:
            self.config["return_chunks"] = False
            migrated = True
        if "return_regions" not in self.config:
            self.config["return_regions"] = False
            migrated = True
        if "include_file_headers_in_codigo_txt" not in self.config:
            self.config["include_file_headers_in_codigo_txt"] = True
            migrated = True
        if "last_code_view_mode" not in self.config:
            self.config["last_code_view_mode"] = "sections"
            migrated = True
        if "remember_last_main_view" not in self.config:
            self.config["remember_last_main_view"] = True
            migrated = True
        if "last_main_view" not in self.config:
            self.config["last_main_view"] = "docs"
            migrated = True
        if "clever_injection_enabled" not in self.config:
            self.config["clever_injection_enabled"] = False
            migrated = True
        if "doc_autosave_enabled" not in self.config:
            self.config["doc_autosave_enabled"] = True
            migrated = True
        if "auto_region_sections_enabled" not in self.config:
            self.config["auto_region_sections_enabled"] = True
            migrated = True
        if "anti_agent_enabled" not in self.config:
            self.config["anti_agent_enabled"] = False
            migrated = True
        if "region_injection_enabled" not in self.config:
            self.config["region_injection_enabled"] = False
            migrated = True
        if "sus_mod_enabled" not in self.config:
            self.config["sus_mod_enabled"] = False
            migrated = True

        for legacy_key in ("return_structures",):
            if legacy_key in self.config:
                self.config.pop(legacy_key, None)
                migrated = True

        if "db_config" in self.config:
            normalized_db_config = self._normalize_db_config(self.config.get("db_config"))
            if normalized_db_config != self.config.get("db_config"):
                self.config["db_config"] = normalized_db_config
                migrated = True

        if migrated:
            self.save_config()

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
        if is_frozen():
            return self._normalize_path(default_sections_dir())
        return self._normalize_path(os.path.join(self._project_root, "sections"))

    def set_sections_path(self, path):
        """Sets the code sections folder path and saves config."""
        self.config["sections_path"] = self._normalize_path(path)
        self.save_config()

    def get_last_project(self):
        """Returns the path of the last opened project, or None."""
        return self.config.get("last_project")

    def set_last_project(self, path):
        """Sets the last opened project path and saves config."""
        normalized = self._normalize_path(path)
        self.config["last_project"] = normalized
        if normalized:
            # Also register in project_directories if not already present
            dirs = self.get_project_directories()
            if normalized not in dirs:
                dirs.append(normalized)
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

    def get_doc_autosave_enabled(self):
        """Returns whether markdown documents should auto-save while typing."""
        return bool(self.config.get("doc_autosave_enabled", True))

    def set_doc_autosave_enabled(self, value):
        """Sets whether markdown documents auto-save while typing."""
        self.config["doc_autosave_enabled"] = bool(value)
        self.save_config()

    def get_list_project_documents_enabled(self):
        """Returns whether DocView includes documents from the loaded project."""
        return bool(self.config.get("list_project_documents_enabled", False))

    def set_list_project_documents_enabled(self, value):
        """Persists the project-document listing preference for DocView."""
        self.config["list_project_documents_enabled"] = bool(value)
        self.save_config()

    def get_advanced_doc_search_enabled(self):
        """Returns whether DocView should use advanced document search."""
        return bool(self.config.get("advanced_doc_search_enabled", False))

    def set_advanced_doc_search_enabled(self, value):
        """Persists the advanced document search preference for DocView."""
        self.config["advanced_doc_search_enabled"] = bool(value)
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
        """Returns the file limit, defaulting to 20."""
        try:
            return max(1, int(self.config.get("file_limit", 20)))
        except (TypeError, ValueError):
            return 20

    def set_file_limit(self, limit):
        """Sets the file limit and saves config."""
        self.config["file_limit"] = max(1, int(limit))
        self.save_config()

    def get_max_file_limit(self):
        """Returns the maximum number of files, defaulting to 20."""
        try:
            return max(1, int(self.config.get("max_file_limit", 20)))
        except (TypeError, ValueError):
            return 20

    def set_max_file_limit(self, limit):
        """Sets the maximum number of files and saves config."""
        self.config["max_file_limit"] = max(1, int(limit))
        self.save_config()

    def get_file_limit_slider_max(self):
        """Returns the configured max value for the Code View file limit slider."""
        default_max = 20
        legacy_expanded = bool(self.config.get("expand_file_limit_range", False))
        legacy_max = 100 if legacy_expanded else default_max

        try:
            value = int(self.config.get("file_limit_slider_max", legacy_max))
        except (TypeError, ValueError):
            value = legacy_max

        return max(default_max, value)

    def set_file_limit_slider_max(self, value):
        """Sets the max value for the Code View file limit slider."""
        self.config["file_limit_slider_max"] = max(20, int(value))
        self.config.pop("expand_file_limit_range", None)
        self.save_config()

    def get_max_file_limit_slider_max(self):
        """Returns the configured max value for the Code View max-file slider."""
        default_max = 20
        try:
            value = int(self.config.get("max_file_limit_slider_max", default_max))
        except (TypeError, ValueError):
            value = default_max
        return max(default_max, value)

    def set_max_file_limit_slider_max(self, value):
        """Sets the max value for the Code View max-file slider."""
        self.config["max_file_limit_slider_max"] = max(20, int(value))
        self.save_config()

    def get_code_extensions_filter(self):
        """Returns the saved extensions filter for Code View."""
        value = self.config.get("code_extensions_filter", "")
        return value if isinstance(value, str) else ""

    def set_code_extensions_filter(self, value):
        """Sets the extensions filter for Code View and saves config."""
        self.config["code_extensions_filter"] = value if isinstance(value, str) else ""
        self.save_config()

    def get_region_list_limit(self):
        """Returns the saved limit for detected regions shown in Code View."""
        value = self.config.get("region_list_limit", 20)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 20

    def set_region_list_limit(self, value):
        """Sets the saved limit for detected regions shown in Code View."""
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = 20
        self.config["region_list_limit"] = normalized
        self.save_config()

    def get_region_list_auto_enabled(self):
        """Returns whether the detected-regions list uses the automatic 50 KB cap."""
        return bool(self.config.get("region_list_auto_enabled", False))

    def set_region_list_auto_enabled(self, value):
        """Sets whether the detected-regions list uses the automatic 50 KB cap."""
        self.config["region_list_auto_enabled"] = bool(value)
        self.save_config()

    def get_auto_region_sections_enabled(self):
        """Returns whether automatic region-group sections are enabled."""
        return bool(self.config.get("auto_region_sections_enabled", True))

    def set_auto_region_sections_enabled(self, value):
        """Sets whether automatic region-group sections are enabled."""
        self.config["auto_region_sections_enabled"] = bool(value)
        self.save_config()

    def get_include_project_tree(self):
        """Returns whether prompts should include the project tree."""
        return bool(self.config.get("include_project_tree", False))

    def set_include_project_tree(self, value):
        """Sets whether prompts should include the project tree and saves config."""
        self.config["include_project_tree"] = bool(value)
        self.save_config()

    def get_export_prompts_as_folder(self):
        """Returns whether Code prompts should export to ~/Documents/codigo/."""
        return bool(self.config.get("export_prompts_as_folder", False))

    def set_export_prompts_as_folder(self, value):
        """Sets whether Code prompts should export to ~/Documents/codigo/."""
        self.config["export_prompts_as_folder"] = bool(value)
        self.save_config()

    def get_clever_injection_enabled(self):
        """Returns whether Clever SUS should run before Arbitrary SUS."""
        return bool(self.config.get("clever_injection_enabled", False))

    def set_clever_injection_enabled(self, value):
        """Sets whether Clever SUS should run before Arbitrary SUS."""
        self.config["clever_injection_enabled"] = bool(value)
        self.save_config()

    def get_return_files(self):
        """Returns whether prompts should ask for complete modified files."""
        return bool(self.config.get("return_files", False))

    def set_return_files(self, value):
        """Sets whether prompts should ask for complete modified files and saves config."""
        self.config["return_files"] = bool(value)
        self.save_config()

    def get_return_chunks(self):
        """Returns whether prompts should work with separated file parts."""
        return bool(self.config.get("return_chunks", False))

    def set_return_chunks(self, value):
        """Sets whether prompts should work with separated file parts and saves config."""
        self.config["return_chunks"] = bool(value)
        self.save_config()

    def get_return_regions(self):
        """Returns whether prompts should ask for full modified regions."""
        return bool(self.config.get("return_regions", False))

    def set_return_regions(self, value):
        """Sets whether prompts should ask for full modified regions and saves config."""
        self.config["return_regions"] = bool(value)
        self.save_config()

    def get_anti_agent_enabled(self):
        return bool(self.config.get("anti_agent_enabled", False))

    def set_anti_agent_enabled(self, value):
        self.config["anti_agent_enabled"] = bool(value)
        self.save_config()

    def get_region_injection_enabled(self):
        """Returns whether Shift+Click should inject complete regions from clipboard."""
        return bool(self.config.get("region_injection_enabled", False))

    def set_region_injection_enabled(self, value):
        """Sets whether Shift+Click should inject complete regions from clipboard."""
        self.config["region_injection_enabled"] = bool(value)
        self.save_config()

    def get_sus_mod_enabled(self):
        """Returns whether Shift+Click should apply [MODIFICACIÓN] substitutions."""
        return bool(self.config.get("sus_mod_enabled", False))

    def set_sus_mod_enabled(self, value):
        """Sets whether Shift+Click should apply [MODIFICACIÓN] substitutions."""
        self.config["sus_mod_enabled"] = bool(value)
        self.save_config()

    def get_include_file_headers_in_codigo_txt(self):
        """Returns whether codigo.txt exports should include 'Archivo:' headers."""
        return bool(self.config.get("include_file_headers_in_codigo_txt", True))

    def set_include_file_headers_in_codigo_txt(self, value):
        """Sets whether codigo.txt exports should include 'Archivo:' headers."""
        self.config["include_file_headers_in_codigo_txt"] = bool(value)
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

    def get_arbitrary_search_min_chars(self):
        """Returns the minimum substring length for Arbitrary search."""
        default_value = 10
        try:
            value = int(self.config.get("arbitrary_search_min_chars", default_value))
        except (TypeError, ValueError):
            value = default_value
        return max(1, value)

    def set_arbitrary_search_min_chars(self, value):
        """Sets the minimum substring length for Arbitrary search and saves config."""
        self.config["arbitrary_search_min_chars"] = max(1, int(value))
        self.save_config()

    def get_arbitrary_search_max_chars(self):
        """Returns the maximum substring length for Arbitrary search."""
        default_value = 30
        try:
            value = int(self.config.get("arbitrary_search_max_chars", default_value))
        except (TypeError, ValueError):
            value = default_value
        return max(1, value)

    def set_arbitrary_search_max_chars(self, value):
        """Sets the maximum substring length for Arbitrary search and saves config."""
        self.config["arbitrary_search_max_chars"] = max(1, int(value))
        self.save_config()

    def get_db_config(self):
        """Returns the saved database configuration or an empty dict."""
        return self._normalize_db_config(self.config.get("db_config"))

    def set_db_config(self, db_config):
        """Sets the database configuration and saves config."""
        self.config["db_config"] = self._normalize_db_config(db_config)
        self.save_config()

    def _normalize_db_config(self, db_config):
        """Returns a stable db_config dict with defaults and normalized paths."""
        defaults = {
            "host": "localhost",
            "port": "3306",
            "user": "",
            "password": "",
            "database": "",
            "pem_file": "",
        }

        normalized = dict(db_config) if isinstance(db_config, dict) else {}
        for key, value in defaults.items():
            if key not in normalized or normalized[key] is None:
                normalized[key] = value

        normalized["host"] = str(normalized.get("host", "")).strip()
        normalized["port"] = str(normalized.get("port", "3306")).strip() or "3306"
        normalized["user"] = str(normalized.get("user", "")).strip()
        normalized["password"] = "" if normalized.get("password") is None else str(normalized.get("password"))
        normalized["database"] = str(normalized.get("database", "")).strip()
        normalized["pem_file"] = self._normalize_path(normalized.get("pem_file")) or ""

        return normalized

    def get_doc_view_settings(self):
        """Returns the saved DocView settings or default values."""
        return self.config.get("doc_view_settings", {
            "is_dark_mode": True,
            "is_editor_mode": False,
            "code_sash_ratio": 0.7,
            "is_fullscreen_mode": False,
            "markdown_preview_zoom": 1.2,
            "markdown_editor_font_size": 12
        })

    def set_doc_view_settings(
        self,
        is_dark_mode,
        is_editor_mode,
        code_sash_ratio=None,
        is_fullscreen_mode=None,
        markdown_preview_zoom=None,
        markdown_editor_font_size=None
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
        if markdown_editor_font_size is not None:
            try:
                settings["markdown_editor_font_size"] = int(markdown_editor_font_size)
            except Exception:
                settings["markdown_editor_font_size"] = 12
        else:
            prev = self.config.get("doc_view_settings", {})
            try:
                settings["markdown_editor_font_size"] = int(prev.get("markdown_editor_font_size", 12))
            except Exception:
                settings["markdown_editor_font_size"] = 12
        self.config["doc_view_settings"] = settings
        self.save_config()

    def get_last_code_section(self):
        """Returns the last selected section in Code View."""
        return self.config.get("last_code_section")

    def set_last_code_section(self, section_name):
        """Sets the last selected section in Code View and saves config."""
        self.config["last_code_section"] = section_name
        self.save_config()

    def get_last_code_view_mode(self):
        """Returns the last selected list mode in Code View."""
        mode = self.config.get("last_code_view_mode", "sections")
        return "regions" if mode == "regions" else "sections"

    def set_last_code_view_mode(self, mode):
        """Sets the last selected list mode in Code View and saves config."""
        self.config["last_code_view_mode"] = "regions" if mode == "regions" else "sections"
        self.save_config()

    def get_remember_last_main_view(self):
        """Returns whether Programita should restore the last main view on startup."""
        return bool(self.config.get("remember_last_main_view", True))

    def set_remember_last_main_view(self, value):
        """Sets whether Programita should restore the last main view on startup."""
        self.config["remember_last_main_view"] = bool(value)
        self.save_config()

    def get_last_main_view(self):
        """Returns the last selected main view key ('code', 'docs' or 'database')."""
        view = self.config.get("last_main_view", "docs")
        if view in {"code", "docs", "database"}:
            return view
        return "docs"

    def set_last_main_view(self, view):
        """Sets the last selected main view key ('code', 'docs' or 'database')."""
        self.config["last_main_view"] = view if view in {"code", "docs", "database"} else "docs"
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
