import json
import os


class RegionSegmentManager:
    """Persists saved region-based code segments in the sections root folder."""

    STORAGE_FILENAME = "__regions__.json"
    BASE_SECTION_SIZE_BYTES = 4 * 1024

    def __init__(self, storage_root=None):
        self.storage_root = None
        self.storage_path = None
        self.region_segments = {}
        self.set_storage_root(storage_root)

    def set_storage_root(self, storage_root=None):
        self.storage_root = os.path.normpath(os.path.abspath(storage_root or os.getcwd()))
        os.makedirs(self.storage_root, exist_ok=True)
        self.storage_path = os.path.join(self.storage_root, self.STORAGE_FILENAME)
        self._load()
        return self.storage_root

    def get_storage_root(self):
        return self.storage_root

    def _load(self):
        self.region_segments = {}
        if not self.storage_path or not os.path.isfile(self.storage_path):
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print(f"RegionSegmentManager: Error loading regions file: {exc}")
            return

        raw_segments = data.get("regions", data) if isinstance(data, dict) else {}
        if not isinstance(raw_segments, dict):
            return

        for name, payload in raw_segments.items():
            if not isinstance(payload, dict):
                continue
            self.region_segments[name] = {
                "items": list(payload.get("items", [])),
            }

    def _save(self):
        if not self.storage_path:
            return

        try:
            with open(self.storage_path, "w", encoding="utf-8") as fh:
                json.dump({"regions": self.region_segments}, fh, indent=4, ensure_ascii=False)
        except Exception as exc:
            print(f"RegionSegmentManager: Error saving regions file: {exc}")

    def get_region_segments(self):
        return list(self.region_segments.keys())

    def get_region_segment(self, name):
        return self.region_segments.get(name)

    def save_region_segment(self, name, items):
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("El nombre de la región no puede estar vacío.")
        if clean_name in self.region_segments:
            raise ValueError(f"La región '{clean_name}' ya existe.")

        self.region_segments[clean_name] = {
            "items": list(items or []),
        }
        self._save()
        return clean_name

    def rename_region_segment(self, old_name, new_name, items):
        clean_old_name = (old_name or "").strip()
        clean_new_name = (new_name or "").strip()
        if not clean_old_name or clean_old_name not in self.region_segments:
            raise ValueError("La región original no existe.")
        if not clean_new_name:
            raise ValueError("El nombre de la región no puede estar vacío.")
        if clean_new_name != clean_old_name and clean_new_name in self.region_segments:
            raise ValueError(f"La región '{clean_new_name}' ya existe.")

        if clean_new_name != clean_old_name:
            del self.region_segments[clean_old_name]

        self.region_segments[clean_new_name] = {
            "items": list(items or []),
        }
        self._save()
        return clean_new_name

    def delete_region_segment(self, name):
        if name not in self.region_segments:
            return
        del self.region_segments[name]
        self._save()

    def get_region_segment_total_code_size(self, name):
        payload = self.get_region_segment(name)
        if not payload:
            return self.BASE_SECTION_SIZE_BYTES
        return self._calculate_items_code_size(payload.get("items", []))

    def _calculate_items_code_size(self, items):
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
