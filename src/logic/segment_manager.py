import json
import os


class SegmentManager:
    """
    Persists code segments as JSON files in a local directory.
    """
    SEGMENTS_DIR = "segments"

    def __init__(self, segments_path=None):
        self.segments = {}
        self.segments_path = None
        self.set_segments_path(segments_path)

    def _resolve_segments_path(self, segments_path=None):
        if segments_path:
            return os.path.normpath(os.path.abspath(segments_path))
        return os.path.join(os.getcwd(), self.SEGMENTS_DIR)

    def _ensure_segments_dir(self):
        if self.segments_path and not os.path.exists(self.segments_path):
            os.makedirs(self.segments_path, exist_ok=True)

    def set_segments_path(self, segments_path=None):
        self.segments_path = self._resolve_segments_path(segments_path)
        self._ensure_segments_dir()
        self._load_all_segments()
        return self.segments_path

    def get_segments_path(self):
        return self.segments_path

    def _load_all_segments(self):
        self.segments = {}
        if not os.path.isdir(self.segments_path):
            return

        for filename in sorted(os.listdir(self.segments_path), key=str.lower):
            if not filename.endswith(".json"):
                continue
            name = filename[:-5]
            file_path = os.path.join(self.segments_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception as exc:
                print(f"SegmentManager: Error loading segment '{name}': {exc}")
                continue

            if not isinstance(data, dict):
                continue

            self.segments[name] = {
                "source_section": data.get("source_section", ""),
                "source_subsection": data.get("source_subsection", ""),
                "items": list(data.get("items", [])),
            }

    def _save_segment_to_disk(self, name):
        if name not in self.segments:
            return

        file_path = os.path.join(self.segments_path, f"{name}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                json.dump(self.segments[name], fh, indent=4, ensure_ascii=False)
        except Exception as exc:
            print(f"SegmentManager: Error saving segment '{name}': {exc}")

    def _delete_segment_from_disk(self, name):
        file_path = os.path.join(self.segments_path, f"{name}.json")
        if not os.path.exists(file_path):
            return
        try:
            os.remove(file_path)
        except Exception as exc:
            print(f"SegmentManager: Error deleting segment '{name}': {exc}")

    def get_segments(self):
        return list(self.segments.keys())

    def get_segment(self, name):
        return self.segments.get(name)

    def save_segment(self, name, source_section, source_subsection, items):
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("El nombre del segmento no puede estar vacío.")

        self.segments[clean_name] = {
            "source_section": (source_section or "").strip(),
            "source_subsection": (source_subsection or "").strip(),
            "items": list(items or []),
        }
        self._save_segment_to_disk(clean_name)
        return clean_name

    def delete_segment(self, name):
        if name not in self.segments:
            return
        del self.segments[name]
        self._delete_segment_from_disk(name)
