import os
import json

class SectionManager:
    """
    Manages 'Sections' of the application.
    A section is a named collection of specific file paths and/or database table names.
    Sections are persisted in a configurable directory (defaults to 'sections').
    
    Storage format (dict):
        {
            "files": ["/abs/path/to/file.py", ...],
            "tables": ["table_name", ...],
            "subsections": {
                "SubName": {"files": ["/abs/path/to/file.py", ...]},
                ...
            }
        }
    
    Legacy format (list) is auto-migrated on load:
        ["/abs/path/to/file.py", ...] -> {"files": [...], "tables": [], "subsections": {}}
    """
    SECTIONS_DIR = "sections"

    def __init__(self, project_manager=None, sections_path=None):
        self.project_manager = project_manager
        self.sections = {} # Dict: {'Section Name': {"files": [...], "tables": [...], "subsections": {...}}}
        self.sections_path = None
        self.set_sections_path(sections_path)

    def _resolve_sections_path(self, sections_path=None):
        """Returns the absolute directory used to persist sections."""
        if sections_path:
            return os.path.normpath(os.path.abspath(sections_path))
        return os.path.join(os.getcwd(), self.SECTIONS_DIR)

    def _ensure_sections_dir(self):
        """Creates the current sections directory if it does not exist."""
        if self.sections_path and not os.path.exists(self.sections_path):
            os.makedirs(self.sections_path, exist_ok=True)

    def get_sections_path(self):
        """Returns the active directory where sections are stored."""
        return self.sections_path

    def set_sections_path(self, sections_path=None):
        """Changes the storage directory and reloads all sections from it."""
        self.sections_path = self._resolve_sections_path(sections_path)
        self._ensure_sections_dir()
        self._load_all_sections()
        return self.sections_path

    def _load_all_sections(self):
        """Loads all sections from local JSON files, auto-migrating legacy format."""
        self.sections = {}
        if not os.path.exists(self.sections_path):
            return

        for filename in sorted(os.listdir(self.sections_path), key=str.lower):
            if filename.endswith(".json"):
                name = filename[:-5] # remove .json
                filepath = os.path.join(self.sections_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            # Legacy format: migrate to new dict format
                            self.sections[name] = {"files": data, "tables": [], "subsections": {}}
                            # Save migrated format
                            self._save_section_to_disk(name)
                        elif isinstance(data, dict):
                            # New format (with or without subsections)
                            self.sections[name] = {
                                "files": data.get("files", []),
                                "tables": data.get("tables", []),
                                "subsections": data.get("subsections", {})
                            }
                        else:
                            print(f"Warning: Unknown format for section '{name}', skipping.")
                except Exception as e:
                    print(f"Error loading section '{name}': {e}")

    def _save_section_to_disk(self, name):
        """Saves a specific section to disk."""
        if name not in self.sections:
            return
            
        filepath = os.path.join(self.sections_path, f"{name}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.sections[name], f, indent=4)
        except Exception as e:
            print(f"Error saving section '{name}': {e}")

    def _delete_section_from_disk(self, name):
        """Removes a section file from disk."""
        filepath = os.path.join(self.sections_path, f"{name}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting section file '{name}': {e}")

    def create_section(self, name, files=None, tables=None):
        """Creates a new section, optionally with files and/or tables."""
        if name in self.sections:
            raise ValueError(f"Section '{name}' already exists.")
        
        # Validate name for filename usage (basic)
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not safe_name or safe_name != name:
             pass
        if not name.strip():
             raise ValueError("Section name cannot be empty.")

        self.sections[name] = {
            "files": list(files) if files else [],
            "tables": list(tables) if tables else [],
            "subsections": {}
        }
        self._save_section_to_disk(name)

    def update_section(self, old_name, new_name, new_files, new_tables=None):
        """Updates an existing section (renaming and/or changing files/tables)."""
        if old_name not in self.sections:
             raise ValueError(f"Section '{old_name}' not found.")
        
        clean_new_name = new_name.strip()
        if not clean_new_name:
             raise ValueError("Section name cannot be empty.")
             
        # If renaming, check collision
        if clean_new_name != old_name and clean_new_name in self.sections:
             raise ValueError(f"Section '{clean_new_name}' already exists.")

        # Preserve existing subsections
        existing_subsections = self.sections[old_name].get("subsections", {})

        # Update data
        # If renaming, delete old file first
        if clean_new_name != old_name:
            self._delete_section_from_disk(old_name)
            del self.sections[old_name]
        
        self.sections[clean_new_name] = {
            "files": list(new_files) if new_files else [],
            "tables": list(new_tables) if new_tables else [],
            "subsections": existing_subsections
        }

        # Clean up subsection files that are no longer in the parent
        parent_files_set = set(self.sections[clean_new_name]["files"])
        for sub_name, sub_data in existing_subsections.items():
            sub_data["files"] = [f for f in sub_data.get("files", []) if f in parent_files_set]

        self._save_section_to_disk(clean_new_name)

    def delete_section(self, name):
        if name in self.sections:
            del self.sections[name]
            self._delete_section_from_disk(name)

    def add_files_to_section(self, section_name, file_paths):
        """Adds files to an existing section."""
        if section_name not in self.sections:
            raise ValueError(f"Section '{section_name}' not found.")
        
        updated = False
        current_files = self.sections[section_name]["files"]
        for path in file_paths:
            if path not in current_files:
                current_files.append(path)
                updated = True
        
        if updated:
            self._save_section_to_disk(section_name)

    def remove_files_from_section(self, section_name, file_paths):
        if section_name in self.sections:
            updated = False
            current_files = self.sections[section_name]["files"]
            for path in file_paths:
                if path in current_files:
                    current_files.remove(path)
                    updated = True
            
            if updated:
                self._save_section_to_disk(section_name)

    def get_sections(self):
        """Returns list of section names."""
        return list(self.sections.keys())

    def get_files_in_section(self, section_name):
        """Returns the list of file paths in a section."""
        section = self.sections.get(section_name, {})
        if isinstance(section, dict):
            return section.get("files", [])
        # Fallback for any edge case
        return section if isinstance(section, list) else []

    def get_tables_in_section(self, section_name):
        """Returns the list of table names in a section."""
        section = self.sections.get(section_name, {})
        if isinstance(section, dict):
            return section.get("tables", [])
        return []

    # ── Subsection Methods ──

    def get_subsections(self, section_name):
        """Returns list of subsection names for a given section."""
        section = self.sections.get(section_name, {})
        return list(section.get("subsections", {}).keys())

    def get_files_in_subsection(self, section_name, sub_name):
        """Returns the list of file paths in a subsection."""
        section = self.sections.get(section_name, {})
        subsections = section.get("subsections", {})
        sub = subsections.get(sub_name, {})
        return sub.get("files", [])

    def create_subsection(self, section_name, sub_name, files=None):
        """Creates a new subsection within a parent section.
        Files must be a subset of the parent section's files."""
        if section_name not in self.sections:
            raise ValueError(f"Section '{section_name}' not found.")
        
        if not sub_name or not sub_name.strip():
            raise ValueError("Subsection name cannot be empty.")
        
        sub_name = sub_name.strip()
        subsections = self.sections[section_name].setdefault("subsections", {})
        
        if sub_name in subsections:
            raise ValueError(f"Subsection '{sub_name}' already exists in '{section_name}'.")
        
        # Validate files are subset of parent
        parent_files = set(self.sections[section_name]["files"])
        valid_files = [f for f in (files or []) if f in parent_files]
        
        subsections[sub_name] = {"files": valid_files}
        self._save_section_to_disk(section_name)

    def update_subsection(self, section_name, old_sub_name, new_sub_name, new_files):
        """Updates an existing subsection (renaming and/or changing files)."""
        if section_name not in self.sections:
            raise ValueError(f"Section '{section_name}' not found.")
        
        subsections = self.sections[section_name].get("subsections", {})
        if old_sub_name not in subsections:
            raise ValueError(f"Subsection '{old_sub_name}' not found in '{section_name}'.")
        
        clean_new_name = new_sub_name.strip()
        if not clean_new_name:
            raise ValueError("Subsection name cannot be empty.")
        
        if clean_new_name != old_sub_name and clean_new_name in subsections:
            raise ValueError(f"Subsection '{clean_new_name}' already exists in '{section_name}'.")
        
        # Validate files are subset of parent
        parent_files = set(self.sections[section_name]["files"])
        valid_files = [f for f in (new_files or []) if f in parent_files]
        
        # Remove old, add new
        if clean_new_name != old_sub_name:
            del subsections[old_sub_name]
        
        subsections[clean_new_name] = {"files": valid_files}
        self._save_section_to_disk(section_name)

    def delete_subsection(self, section_name, sub_name):
        """Deletes a subsection from a parent section."""
        if section_name not in self.sections:
            return
        
        subsections = self.sections[section_name].get("subsections", {})
        if sub_name in subsections:
            del subsections[sub_name]
            self._save_section_to_disk(section_name)
