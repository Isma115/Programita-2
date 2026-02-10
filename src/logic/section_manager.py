import os
import json

class SectionManager:
    """
    Manages 'Sections' of the application.
    A section is a named collection of specific file paths.
    Sections are persisted in the 'sections' directory.
    """
    SECTIONS_DIR = "sections"

    def __init__(self, project_manager=None):
        self.project_manager = project_manager
        # Ensure sections  persist directory exists
        self.sections_path = os.path.join(os.getcwd(), self.SECTIONS_DIR)
        if not os.path.exists(self.sections_path):
            os.makedirs(self.sections_path)

        self.sections = {} # Dict: {'Section Name': {set of absolute file paths}}
        self._load_all_sections()

    def _load_all_sections(self):
        """Loads all sections from local JSON files."""
        self.sections = {}
        if not os.path.exists(self.sections_path):
            return

        for filename in os.listdir(self.sections_path):
            if filename.endswith(".json"):
                name = filename[:-5] # remove .json
                filepath = os.path.join(self.sections_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self.sections[name] = data # Keep as list
                except Exception as e:
                    print(f"Error loading section '{name}': {e}")

    def _save_section_to_disk(self, name):
        """Saves a specific section to disk."""
        if name not in self.sections:
            return
            
        filepath = os.path.join(self.sections_path, f"{name}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Dump list directly
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

    def create_section(self, name, files=None):
        """Creates a new section, optionally with files."""
        if name in self.sections:
            raise ValueError(f"Section '{name}' already exists.")
        
        # Validate name for filename usage (basic)
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not safe_name or safe_name != name:
             pass
        if not name.strip():
             raise ValueError("Section name cannot be empty.")

        self.sections[name] = list(files) if files else []
        self._save_section_to_disk(name)

    def update_section(self, old_name, new_name, new_files):
        """Updates an existing section (renaming and/or changing files)."""
        if old_name not in self.sections:
             raise ValueError(f"Section '{old_name}' not found.")
        
        clean_new_name = new_name.strip()
        if not clean_new_name:
             raise ValueError("Section name cannot be empty.")
             
        # If renaming, check collision
        if clean_new_name != old_name and clean_new_name in self.sections:
             raise ValueError(f"Section '{clean_new_name}' already exists.")

        # Update data
        # If renaming, delete old file first
        if clean_new_name != old_name:
            self._delete_section_from_disk(old_name)
            del self.sections[old_name]
        
        self.sections[clean_new_name] = list(new_files) if new_files else []
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
        current_files = self.sections[section_name]
        for path in file_paths:
            if path not in current_files:
                current_files.append(path)
                updated = True
        
        if updated:
            self._save_section_to_disk(section_name)

    def remove_files_from_section(self, section_name, file_paths):
        if section_name in self.sections:
            updated = False
            current_files = self.sections[section_name]
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
        return self.sections.get(section_name, [])
