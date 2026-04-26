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
                "SubName": {
                    "files": ["/abs/path/to/file.py", ...],
                    "segments": {
                        "SegmentName": {
                            "items": [{...}]
                        }
                    }
                },
                ...
            }
        }
    
    Legacy format (list) is auto-migrated on load:
        ["/abs/path/to/file.py", ...] -> {"files": [...], "tables": [], "subsections": {}}
    """
    BASE_SECTION_SIZE_BYTES = 4 * 1024
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
                                "subsections": self._normalize_subsections_payload(data.get("subsections", {}))
                            }
                        else:
                            print(f"Warning: Unknown format for section '{name}', skipping.")
                except Exception as e:
                    print(f"Error loading section '{name}': {e}")

    def _normalize_subsections_payload(self, raw_subsections):
        normalized = {}
        if not isinstance(raw_subsections, dict):
            return normalized

        for sub_name, sub_data in raw_subsections.items():
            normalized[sub_name] = self._normalize_subsection_payload(sub_data)
        return normalized

    def _normalize_subsection_payload(self, sub_data):
        if isinstance(sub_data, list):
            return {"files": list(sub_data), "segments": {}}

        if not isinstance(sub_data, dict):
            return {"files": [], "segments": {}}

        segments = {}
        raw_segments = sub_data.get("segments", {})
        if isinstance(raw_segments, dict):
            for segment_name, segment_data in raw_segments.items():
                segments[segment_name] = self._normalize_segment_payload(segment_data)

        return {
            "files": list(sub_data.get("files", [])),
            "segments": segments,
        }

    def _normalize_segment_payload(self, segment_data):
        if not isinstance(segment_data, dict):
            return {"items": []}
        return {"items": list(segment_data.get("items", []))}

    def _filter_segment_items_for_files(self, items, valid_files):
        valid_paths = set(valid_files or [])
        filtered_items = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            if item.get("file_path") not in valid_paths:
                continue
            filtered_items.append(dict(item))
        return filtered_items

    def _cleanup_subsection_segments(self, subsection_data):
        subsection_data = subsection_data if isinstance(subsection_data, dict) else {}
        valid_files = subsection_data.get("files", [])
        segments = subsection_data.get("segments", {})
        if not isinstance(segments, dict):
            subsection_data["segments"] = {}
            return

        for segment_name, segment_data in list(segments.items()):
            normalized_segment = self._normalize_segment_payload(segment_data)
            normalized_segment["items"] = self._filter_segment_items_for_files(
                normalized_segment.get("items", []),
                valid_files
            )
            segments[segment_name] = normalized_segment

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
            self._cleanup_subsection_segments(sub_data)

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

    def _calculate_total_code_size(self, file_paths=None):
        """Returns the total size in bytes for code files, including the base section margin."""
        total_bytes = self.BASE_SECTION_SIZE_BYTES
        seen_paths = set()

        for path in file_paths or []:
            normalized_path = os.path.abspath(path)
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)

            if self.project_manager and not self.project_manager.is_code_file(os.path.basename(path)):
                continue

            try:
                total_bytes += os.path.getsize(path)
            except OSError:
                continue

        return total_bytes

    def get_section_total_code_size(self, section_name):
        """Returns the total byte size for a section, counting only code files."""
        return self._calculate_total_code_size(self.get_files_in_section(section_name))

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

    def get_subsection_total_code_size(self, section_name, sub_name):
        """Returns the total byte size for a subsection, counting only code files."""
        return self._calculate_total_code_size(self.get_files_in_subsection(section_name, sub_name))

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
        
        subsections[sub_name] = {"files": valid_files, "segments": {}}
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
        existing_segments = self._normalize_subsection_payload(subsections.get(old_sub_name, {})).get("segments", {})

        # Remove old, add new
        if clean_new_name != old_sub_name:
            del subsections[old_sub_name]

        subsections[clean_new_name] = {
            "files": valid_files,
            "segments": existing_segments,
        }
        self._cleanup_subsection_segments(subsections[clean_new_name])
        self._save_section_to_disk(section_name)

    def delete_subsection(self, section_name, sub_name):
        """Deletes a subsection from a parent section."""
        if section_name not in self.sections:
            return
        
        subsections = self.sections[section_name].get("subsections", {})
        if sub_name in subsections:
            del subsections[sub_name]
            self._save_section_to_disk(section_name)

    # ── Segment Methods ──

    def get_segments(self, section_name, sub_name):
        """Returns list of segment names for a subsection."""
        section = self.sections.get(section_name, {})
        subsections = section.get("subsections", {})
        subsection = self._normalize_subsection_payload(subsections.get(sub_name, {}))
        return list(subsection.get("segments", {}).keys())

    def get_segment(self, section_name, sub_name, segment_name):
        """Returns the stored segment payload for a subsection."""
        section = self.sections.get(section_name, {})
        subsections = section.get("subsections", {})
        subsection = self._normalize_subsection_payload(subsections.get(sub_name, {}))
        segment = subsection.get("segments", {}).get(segment_name)
        if not segment:
            return None
        return self._normalize_segment_payload(segment)

    def get_files_in_segment(self, section_name, sub_name, segment_name):
        """Returns the distinct files touched by a segment, falling back to the parent subsection files."""
        segment = self.get_segment(section_name, sub_name, segment_name)
        if not segment:
            return self.get_files_in_subsection(section_name, sub_name)

        file_paths = []
        seen_paths = set()
        for item in segment.get("items", []):
            file_path = item.get("file_path")
            if not file_path or file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            file_paths.append(file_path)

        return file_paths or self.get_files_in_subsection(section_name, sub_name)

    def _calculate_segment_items_code_size(self, items=None):
        total_bytes = self.BASE_SECTION_SIZE_BYTES
        items_by_path = {}
        for item in items or []:
            if not isinstance(item, dict):
                continue
            file_path = item.get("file_path")
            if not file_path:
                continue
            items_by_path.setdefault(file_path, []).append(item)

        for file_path, file_items in items_by_path.items():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except OSError:
                continue

            for item in file_items:
                start_line = max(int(item.get("start_line", 1) or 1), 1)
                end_line = max(int(item.get("end_line", start_line) or start_line), start_line)
                snippet = "".join(lines[start_line - 1:end_line])
                total_bytes += len(snippet.encode("utf-8", errors="ignore"))

        return total_bytes

    def get_segment_total_code_size(self, section_name, sub_name, segment_name):
        """Returns the total byte size for a segment based on its selected code structures."""
        segment = self.get_segment(section_name, sub_name, segment_name)
        if not segment:
            return self.BASE_SECTION_SIZE_BYTES
        return self._calculate_segment_items_code_size(segment.get("items", []))

    def create_segment(self, section_name, sub_name, segment_name, items=None):
        """Creates a segment inside a subsection using selected structure items."""
        if section_name not in self.sections:
            raise ValueError(f"Section '{section_name}' not found.")

        subsections = self.sections[section_name].get("subsections", {})
        if sub_name not in subsections:
            raise ValueError(f"Subsection '{sub_name}' not found in '{section_name}'.")

        clean_name = (segment_name or "").strip()
        if not clean_name:
            raise ValueError("Segment name cannot be empty.")

        subsection = self._normalize_subsection_payload(subsections[sub_name])
        segments = subsection.setdefault("segments", {})
        if clean_name in segments:
            raise ValueError(f"Segment '{clean_name}' already exists in '{sub_name}'.")

        segments[clean_name] = {
            "items": self._filter_segment_items_for_files(items, subsection.get("files", []))
        }
        subsections[sub_name] = subsection
        self._save_section_to_disk(section_name)

    def update_segment(self, section_name, sub_name, old_segment_name, new_segment_name, items=None):
        """Updates an existing segment inside a subsection."""
        if section_name not in self.sections:
            raise ValueError(f"Section '{section_name}' not found.")

        subsections = self.sections[section_name].get("subsections", {})
        if sub_name not in subsections:
            raise ValueError(f"Subsection '{sub_name}' not found in '{section_name}'.")

        subsection = self._normalize_subsection_payload(subsections[sub_name])
        segments = subsection.setdefault("segments", {})
        if old_segment_name not in segments:
            raise ValueError(f"Segment '{old_segment_name}' not found in '{sub_name}'.")

        clean_name = (new_segment_name or "").strip()
        if not clean_name:
            raise ValueError("Segment name cannot be empty.")
        if clean_name != old_segment_name and clean_name in segments:
            raise ValueError(f"Segment '{clean_name}' already exists in '{sub_name}'.")

        if clean_name != old_segment_name:
            del segments[old_segment_name]

        segments[clean_name] = {
            "items": self._filter_segment_items_for_files(items, subsection.get("files", []))
        }
        subsections[sub_name] = subsection
        self._save_section_to_disk(section_name)

    def delete_segment(self, section_name, sub_name, segment_name):
        """Deletes a segment from a subsection."""
        if section_name not in self.sections:
            return

        subsections = self.sections[section_name].get("subsections", {})
        subsection = self._normalize_subsection_payload(subsections.get(sub_name, {}))
        segments = subsection.get("segments", {})
        if segment_name in segments:
            del segments[segment_name]
            subsections[sub_name] = subsection
            self._save_section_to_disk(section_name)
