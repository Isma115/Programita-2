import os
import re
from tkinter import messagebox

from src.logic.region_outline import (
    REGION_END_RE,
    REGION_START_RE,
    extract_regions_for_files,
    normalize_region_match_text,
)


def _is_region_injection_enabled(app_instance):
    config = getattr(getattr(app_instance, "controller", None), "config_manager", None)
    if config is None:
        return False
    return bool(config.get_region_injection_enabled())


def _get_project_root(app_instance):
    project_manager = getattr(getattr(app_instance, "controller", None), "project_manager", None)
    return getattr(project_manager, "current_project_path", None)


def _get_project_files(app_instance):
    project_manager = getattr(getattr(app_instance, "controller", None), "project_manager", None)
    if project_manager is None or not hasattr(project_manager, "get_files"):
        return []
    return list(project_manager.get_files() or [])


def _get_clipboard_text(app_instance):
    try:
        return app_instance.root.clipboard_get()
    except Exception:
        return ""


def _strip_markdown_fence_lines(text):
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line for line in lines if not line.strip().startswith("```"))


def _clean_path_hint(value):
    cleaned = str(value or "").strip().strip("`*[](){}<>\"'")
    cleaned = cleaned.rstrip(":")
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"^\./+", "", cleaned)
    return cleaned.strip()


def _extract_file_marker(line):
    stripped = str(line or "").strip()
    if not stripped:
        return None
    stripped = re.sub(r"^(?://|#|--|;|/\*+|\*+)\s*", "", stripped).strip()
    stripped = re.sub(r"\s*\*/\s*$", "", stripped).strip()

    patterns = [
        r"^-{3,}\s*(?:Archivo|Fichero|File)\s*:\s*(.+?)\s*-{3,}$",
        r"^(?:Archivo|Fichero|File)\s*:\s*(.+?)$",
        r"^#{1,6}\s*(?:Archivo|Fichero|File)\s*:\s*(.+?)$",
        r"^\*\*(?:Archivo|Fichero|File)\s*:\s*(.+?)\*\*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stripped, re.IGNORECASE)
        if match:
            return _clean_path_hint(match.group(1))
    return None


def _clean_region_name(raw_text):
    text = (raw_text or "").strip()
    for suffix in ("*/}", "*/", "-->"):
        if text.endswith(suffix):
            text = text[:-len(suffix)].rstrip()
    return text.strip().strip("\"'").strip()


def parse_clipboard_regions(text):
    lines = _strip_markdown_fence_lines(text).split("\n")
    regions = []
    current_file = None
    index = 0

    while index < len(lines):
        file_hint = _extract_file_marker(lines[index])
        if file_hint:
            current_file = file_hint
            index += 1
            continue

        start_match = REGION_START_RE.match(lines[index])
        if not start_match:
            index += 1
            continue

        depth = 1
        start_index = index
        index += 1
        while index < len(lines):
            if REGION_START_RE.match(lines[index]):
                depth += 1
            elif REGION_END_RE.match(lines[index]):
                depth -= 1
                if depth == 0:
                    end_index = index
                    regions.append({
                        "file_hint": current_file,
                        "header": _clean_region_name(start_match.group("rest")),
                        "content": "\n".join(lines[start_index:end_index + 1]).rstrip(),
                    })
                    break
            index += 1
        index += 1

    return regions


def _resolve_file_hint(file_hint, project_root, project_files):
    clean_hint = _clean_path_hint(file_hint)
    if not clean_hint:
        return None

    direct_candidates = []
    if os.path.isabs(clean_hint):
        direct_candidates.append(clean_hint)
    elif project_root:
        direct_candidates.append(os.path.join(project_root, clean_hint))

    for candidate in direct_candidates:
        normalized = os.path.normpath(candidate)
        if os.path.isfile(normalized):
            return normalized

    normalized_hint = clean_hint.lower()
    matches = []
    for file_info in project_files:
        file_path = os.path.normpath(str(file_info.get("path") or ""))
        rel_path = str(file_info.get("rel_path") or "").replace("\\", "/").lower()
        abs_path = file_path.replace("\\", "/").lower()
        if normalized_hint == rel_path or abs_path.endswith(normalized_hint):
            matches.append(file_path)
    return matches[0] if len(matches) == 1 else None


def _find_target_region(clipboard_region, project_root, project_files):
    target_file = _resolve_file_hint(clipboard_region.get("file_hint"), project_root, project_files)
    file_infos = [
        file_info for file_info in project_files
        if not target_file or os.path.normpath(str(file_info.get("path") or "")) == target_file
    ]
    candidates = extract_regions_for_files(file_infos)

    normalized_header = normalize_region_match_text(clipboard_region.get("header") or "")
    matches = [
        region for region in candidates
        if normalize_region_match_text(region.get("header") or region.get("name") or "") == normalized_header
    ]

    if len(matches) == 1:
        return matches[0], None
    if not matches:
        location = clipboard_region.get("file_hint") or "proyecto"
        return None, f"region no encontrada: {clipboard_region.get('header') or 'sin nombre'} ({location})"
    return None, f"region ambigua: {clipboard_region.get('header') or 'sin nombre'}"


def _replace_region_in_file(target_region, new_region_content):
    file_path = target_region.get("file_path")
    start_line = int(target_region.get("start_line") or 0)
    end_line = int(target_region.get("end_line") or 0)
    if not file_path or start_line < 1 or end_line < start_line:
        return None, "coordenadas de region invalidas"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            original_content = fh.read()
    except Exception as exc:
        return None, f"leyendo fichero: {exc}"

    lines = original_content.splitlines(keepends=True)
    if start_line > len(lines):
        return None, "linea inicial fuera de rango"

    replacement = new_region_content.rstrip("\n")
    if end_line <= len(lines) and lines[end_line - 1].endswith("\n"):
        replacement += "\n"

    updated_lines = lines[:start_line - 1] + [replacement] + lines[end_line:]
    updated_content = "".join(updated_lines)

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(updated_content)
    except Exception as exc:
        return None, f"escribiendo fichero: {exc}"

    return updated_content, None


def apply_region_injections(app_instance, clipboard_text):
    project_root = _get_project_root(app_instance)
    project_files = _get_project_files(app_instance)
    if not project_root or not project_files:
        return {"success": 0, "failed": 1, "details": ["[ERROR] No hay proyecto cargado."]}

    clipboard_regions = parse_clipboard_regions(clipboard_text)
    if not clipboard_regions:
        return {"success": 0, "failed": 1, "details": ["[ERROR] No se encontraron regiones completas en el portapapeles."]}

    results = {"success": 0, "failed": 0, "details": []}
    updated_files = {}

    for clipboard_region in clipboard_regions:
        target_region, error = _find_target_region(clipboard_region, project_root, project_files)
        if error:
            results["failed"] += 1
            results["details"].append(f"[NO MATCH] {error}")
            continue

        updated_content, write_error = _replace_region_in_file(target_region, clipboard_region["content"])
        if write_error:
            results["failed"] += 1
            results["details"].append(f"[ERROR] {target_region.get('file_rel_path')}: {write_error}")
            continue

        file_path = target_region.get("file_path")
        updated_files[file_path] = updated_content
        for file_info in project_files:
            if os.path.normpath(str(file_info.get("path") or "")) == os.path.normpath(str(file_path or "")):
                file_info["content"] = updated_content
                break
        results["success"] += 1
        results["details"].append(
            f"[OK] {target_region.get('file_rel_path')}: {target_region.get('header') or target_region.get('name')}"
        )

    controller = getattr(app_instance, "controller", None)
    for file_path, content in updated_files.items():
        if controller and hasattr(controller, "refresh_cached_file_content"):
            controller.refresh_cached_file_content(file_path, content)

    return results


def _refresh_code_view(app_instance):
    code_view = getattr(getattr(app_instance, "layout", None), "code_view", None)
    if code_view is not None and hasattr(code_view, "refresh_file_list"):
        code_view.refresh_file_list()


def _show_errors(results):
    if not results.get("failed"):
        return
    detail_text = "\n".join(results["details"])
    messagebox.showerror(
        "Inyectar regiones - Error",
        (
            "No se pudieron aplicar todas las regiones:\n\n"
            f"  Regiones sustituidas: {results['success']}\n"
            f"  Fallos: {results['failed']}\n\n"
            f"Detalle:\n{detail_text}"
        ),
    )


def process_region_injection(app_instance):
    clipboard_text = _get_clipboard_text(app_instance)
    if not clipboard_text.strip():
        messagebox.showerror("Inyectar regiones - Error", "El portapapeles esta vacio.")
        return True

    preview_regions = parse_clipboard_regions(clipboard_text)
    if not preview_regions:
        messagebox.showerror(
            "Inyectar regiones - Error",
            "No se encontraron regiones completas en el portapapeles.\n\n"
            "Debe haber bloques desde #region hasta #endregion.",
        )
        return True

    results = apply_region_injections(app_instance, clipboard_text)
    _refresh_code_view(app_instance)
    _show_errors(results)
    return True
