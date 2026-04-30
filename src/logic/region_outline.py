import os
import re


REGION_START_RE = re.compile(
    r'^\s*(?:(?://|#|--)|/\*|<!--)\s*#?region\b(?P<rest>.*?)(?:\*/|-->)?\s*$',
    re.IGNORECASE,
)
REGION_END_RE = re.compile(
    r'^\s*(?:(?://|#|--)|/\*|<!--)\s*#?endregion\b(?:.*?)(?:\*/|-->)?\s*$',
    re.IGNORECASE,
)


def extract_regions_for_files(file_infos):
    """Extracts full #region blocks for the provided file payloads."""
    regions = []
    for file_info in file_infos or []:
        regions.extend(_extract_regions_from_file(file_info))
    return regions


def build_region_outline_forest(file_infos):
    """Builds a per-file flat outline of detected code regions."""
    ordered_files = [item for item in file_infos or [] if item.get("path")]
    regions_by_path = {}
    for item in extract_regions_for_files(ordered_files):
        regions_by_path.setdefault(item["file_path"], []).append(item)

    forest = []
    for file_info in ordered_files:
        file_path = file_info.get("path")
        forest.append({
            "file_path": file_path,
            "file_rel_path": file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo",
            "items": list(regions_by_path.get(file_path, [])),
        })
    return forest


def _extract_regions_from_file(file_info):
    file_path = file_info.get("path")
    file_rel_path = file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo"
    content = file_info.get("content", "")
    lines = content.split("\n")
    stack = []
    regions = []

    for line_number, line_text in enumerate(lines, start=1):
        start_match = REGION_START_RE.match(line_text)
        if start_match:
            stack.append({
                "start_line": line_number,
                "name": _clean_region_name(start_match.group("rest")),
            })
            continue

        if REGION_END_RE.match(line_text) and stack:
            start_info = stack.pop()
            start_line = max(int(start_info.get("start_line", 1) or 1), 1)
            end_line = max(line_number, start_line)
            region_name = start_info.get("name") or f"Región {start_line}"
            regions.append({
                "key": f"region::{file_path}::{start_line}:{end_line}:{region_name}",
                "file_path": file_path,
                "file_rel_path": file_rel_path,
                "header": region_name,
                "name": region_name,
                "type": "region",
                "start_line": start_line,
                "end_line": end_line,
                "line_count": max(end_line - start_line + 1, 1),
                "content": "\n".join(lines[start_line - 1:end_line]).rstrip(),
            })

    regions.sort(key=lambda item: (int(item.get("start_line", 1) or 1), int(item.get("end_line", 1) or 1)))
    return regions


def _clean_region_name(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return ""

    for suffix in ("*/", "-->"):
        if text.endswith(suffix):
            text = text[:-len(suffix)].rstrip()

    text = text.strip().strip("\"'").strip()
    return text
