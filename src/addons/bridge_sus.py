import os
import re
import tkinter as tk
from tkinter import messagebox


def _is_anti_agent_enabled(app_instance):
    config = getattr(getattr(app_instance, "controller", None), "config_manager", None)
    if config is None:
        return False
    return bool(config.get_anti_agent_enabled())


def _get_project_root(app_instance):
    controller = getattr(app_instance, "controller", None)
    if controller is None:
        return None
    pm = getattr(controller, "project_manager", None)
    if pm is None:
        return None
    return getattr(pm, "current_project_path", None)


def _get_clipboard_text(app_instance):
    try:
        return app_instance.root.clipboard_get()
    except Exception:
        return ""


def _normalize_whitespace(text):
    return re.sub(r'[ \t]+', ' ', re.sub(r'\r\n', '\n', text))


def _map_normalized_to_original(original, norm_pos):
    norm_idx = 0
    orig_idx = 0
    while norm_idx < norm_pos and orig_idx < len(original):
        if original[orig_idx] in ('\r',):
            orig_idx += 1
            continue
        if original[orig_idx] in (' ', '\t'):
            while orig_idx < len(original) and original[orig_idx] in (' ', '\t'):
                orig_idx += 1
            if norm_idx < norm_pos:
                norm_idx += 1
        else:
            norm_idx += 1
            orig_idx += 1
    return orig_idx


def _strip_markdown_code_blocks(text):
    """Elimina las líneas de apertura/cierre de bloques markdown (```lenguaje / ```) del contenido."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned)
    if result.startswith("\n"):
        result = result[1:]
    if result.endswith("\n"):
        result = result[:-1]
    return result


def _split_patch_operations(patch_text):
    operations = []
    current = None

    for line in patch_text.split("\n"):
        op_match = re.match(r'^\s*@@\s+([A-Z_]+)\s*$', line)
        if op_match:
            if current is not None:
                operations.append(current)
            current = {"op": op_match.group(1), "body": []}
            continue
        if current is not None:
            current["body"].append(line)

    if current is not None:
        operations.append(current)

    return operations


def _parse_patch_sections(body):
    sections = {}
    current_name = None
    current_lines = []

    for line in body:
        section_match = re.match(r'^\s*(FIND|WITH|CONTENT|LINE):\s*$', line)
        if section_match:
            if current_name is not None:
                sections[current_name] = _strip_markdown_code_blocks("\n".join(current_lines))
            current_name = section_match.group(1).lower()
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        sections[current_name] = _strip_markdown_code_blocks("\n".join(current_lines))

    return sections


def _parse_patch_operations(patch_text):
    operations = []

    for raw_operation in _split_patch_operations(patch_text):
        op = raw_operation["op"].lower()
        sections = _parse_patch_sections(raw_operation["body"])
        operation = {"op": op}

        if op in ("replace", "insert_before", "insert_after", "delete"):
            operation["find"] = sections.get("find", "")
            if "line" in sections:
                operation["line"] = sections.get("line", "")
        if op == "replace":
            operation["with"] = sections.get("with", "")
        elif op in ("insert_before", "insert_after"):
            operation["content"] = sections.get("content", "")
        elif op != "delete":
            operation["unsupported"] = True

        operations.append(operation)

    return operations


def parse_ai_response(text):
    changes = []
    text = text.replace("\r\n", "\n")

    new_file_pattern = re.compile(
        r'\[\[\[\s*ARCHIVO\s+NUEVO:\s*(.+?)\s*\]\]\].*?'
        r'\]\]\]\s*CONTENIDO\s*\n(.*?)CONTENIDO\s*\[\[\[',
        re.DOTALL
    )
    for match in new_file_pattern.finditer(text):
        content = _strip_markdown_code_blocks(match.group(2))
        changes.append({
            "type": "new_file",
            "file": match.group(1).strip(),
            "content": content
        })

    patch_pattern = re.compile(
        r'\[\[\[\s*ARCHIVO:\s*(.+?)\s*\]\]\]\s*\n'
        r'\[\[\[\s*PATCH\s*\n(.*?)PATCH\s*\]\]\]',
        re.DOTALL
    )
    for match in patch_pattern.finditer(text):
        patch_text = _strip_markdown_code_blocks(match.group(2))
        operations = _parse_patch_operations(patch_text)
        changes.append({
            "type": "patch",
            "file": match.group(1).strip(),
            "operations": operations
        })

    change_pattern = re.compile(
        r'\[\[\[\s*ARCHIVO:\s*(.+?)\s*\]\]\]\s*\n'
        r'\[\[\[\s*ORIGINAL\s*\n(.*?)ORIGINAL\s*\]\]\]\s*\n'
        r'\]\]\]\s*MODIFICADO\s*\n(.*?)MODIFICADO\s*\[\[\[',
        re.DOTALL
    )
    for match in change_pattern.finditer(text):
        file_path = match.group(1).strip()
        original = _strip_markdown_code_blocks(match.group(2))
        modified = _strip_markdown_code_blocks(match.group(3))

        changes.append({
            "type": "modification",
            "file": file_path,
            "original": original,
            "modified": modified
        })

    return changes


def _find_once(content, needle):
    if not needle:
        return None, False

    start = content.find(needle)
    if start != -1:
        return (start, start + len(needle)), False

    normalized_content = _normalize_whitespace(content)
    normalized_needle = _normalize_whitespace(needle)
    start = normalized_content.find(normalized_needle)
    if start == -1:
        return None, False

    original_start = _map_normalized_to_original(content, start)
    original_end = _map_normalized_to_original(content, start + len(normalized_needle))
    return (original_start, original_end), True


def _replace_fragment(content, original, modified):
    span, fuzzy = _find_once(content, original)
    if span is None:
        return None, False
    start, end = span
    return content[:start] + modified + content[end:], fuzzy


def _parse_line_range(line_value):
    line_value = (line_value or "").strip()
    if not line_value:
        return None

    match = re.search(r'L?\s*(\d+)(?:\s*[-:]\s*L?\s*(\d+))?', line_value, re.IGNORECASE)
    if not match:
        return None

    start_line = int(match.group(1))
    end_line = int(match.group(2) or start_line)
    if start_line < 1 or end_line < start_line:
        return None
    return start_line, end_line


def _line_span(content, line_range):
    if not line_range:
        return None

    lines = content.splitlines(keepends=True)
    if not lines:
        return (0, 0) if line_range == (1, 1) else None

    start_line, end_line = line_range
    if start_line > len(lines):
        return None

    end_line = min(end_line, len(lines))
    start = sum(len(line) for line in lines[:start_line - 1])
    end = sum(len(line) for line in lines[:end_line])
    return start, end


def _insert_at_line_boundary(content, insert_at, insertion):
    prefix = ""
    suffix = ""
    if insert_at > 0 and content[insert_at - 1] != "\n" and not insertion.startswith("\n"):
        prefix = "\n"
    if insert_at < len(content) and insertion and not insertion.endswith("\n"):
        suffix = "\n"
    return content[:insert_at] + prefix + insertion + suffix + content[insert_at:]


def _apply_patch_operation_by_line(content, operation):
    span = _line_span(content, _parse_line_range(operation.get("line", "")))
    if span is None:
        return None, "ancla FIND no encontrada y LINE inválido o fuera de rango"

    start, end = span
    op = operation.get("op")
    if op == "replace":
        replacement = operation.get("with", "")
        if end > start and content[end - 1:end] == "\n" and replacement and not replacement.endswith("\n"):
            replacement += "\n"
        return content[:start] + replacement + content[end:], "line"
    if op == "delete":
        return content[:start] + content[end:], "line"
    if op == "insert_before":
        return _insert_at_line_boundary(content, start, operation.get("content", "")), "line"
    if op == "insert_after":
        return _insert_at_line_boundary(content, end, operation.get("content", "")), "line"

    return None, "operación no soportada"


def _insert_before_anchor(content, start, insertion):
    prefix = ""
    suffix = ""
    if start > 0 and content[start - 1] != "\n" and not insertion.startswith("\n"):
        prefix = "\n"
    if insertion and not insertion.endswith("\n"):
        suffix = "\n"
    return content[:start] + prefix + insertion + suffix + content[start:]


def _insert_after_anchor(content, end, insertion):
    insert_at = end
    if insert_at < len(content) and content[insert_at] == "\n":
        insert_at += 1

    prefix = ""
    suffix = ""
    if insert_at > 0 and content[insert_at - 1] != "\n" and not insertion.startswith("\n"):
        prefix = "\n"
    if insert_at < len(content) and insertion and not insertion.endswith("\n"):
        suffix = "\n"
    return content[:insert_at] + prefix + insertion + suffix + content[insert_at:]


def _apply_patch_operation(content, operation):
    if operation.get("unsupported"):
        return None, "operación no soportada"

    op = operation.get("op")
    find_text = operation.get("find", "")
    span, fuzzy = _find_once(content, find_text)
    if span is None:
        return _apply_patch_operation_by_line(content, operation)

    start, end = span
    if op == "replace":
        return content[:start] + operation.get("with", "") + content[end:], "fuzzy" if fuzzy else None
    if op == "delete":
        return content[:start] + content[end:], "fuzzy" if fuzzy else None
    if op == "insert_before":
        return _insert_before_anchor(content, start, operation.get("content", "")), "fuzzy" if fuzzy else None
    if op == "insert_after":
        return _insert_after_anchor(content, end, operation.get("content", "")), "fuzzy" if fuzzy else None

    return None, "operación no soportada"


def _apply_patch_change(content, operations):
    match_modes = set()

    for index, operation in enumerate(operations, start=1):
        updated_content, match_mode = _apply_patch_operation(content, operation)
        if updated_content is None:
            return None, f"op {index}: {match_mode}", match_modes
        content = updated_content
        if match_mode:
            match_modes.add(match_mode)

    return content, None, match_modes


def _apply_changes(project_root, changes):
    results = {"success": 0, "failed": 0, "created": 0, "details": []}

    for change in changes:
        file_path = change["file"]
        full_path = os.path.join(project_root, file_path)

        if change["type"] == "new_file":
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change["content"])
                results["created"] += 1
                results["details"].append(f"[CREADO] {file_path}")
            except Exception as e:
                results["failed"] += 1
                results["details"].append(f"[ERROR] {file_path}: {e}")
            continue

        if not os.path.exists(full_path):
            results["failed"] += 1
            results["details"].append(f"[ERROR] No existe: {file_path}")
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            results["failed"] += 1
            results["details"].append(f"[ERROR] Leyendo {file_path}: {e}")
            continue

        if change["type"] == "patch":
            operation_count = len(change.get("operations", []))
            if operation_count == 0:
                results["failed"] += 1
                results["details"].append(f"[ERROR] {file_path}: parche sin operaciones")
                continue

            updated_content, error, match_modes = _apply_patch_change(content, change["operations"])
            if error is None:
                try:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(updated_content)
                    results["success"] += operation_count
                    marker = "[OK~]" if match_modes else "[OK]"
                    mode_labels = []
                    if "fuzzy" in match_modes:
                        mode_labels.append("match fuzzy")
                    if "line" in match_modes:
                        mode_labels.append("fallback LINE")
                    suffix = f" ({', '.join(mode_labels)})" if mode_labels else ""
                    results["details"].append(
                        f"{marker} {file_path}: {operation_count} operación(es){suffix}")
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append(f"[ERROR] Escribiendo {file_path}: {e}")
            else:
                results["failed"] += 1
                results["details"].append(f"[NO MATCH] {file_path}: {error}")
            continue

        original = change["original"]
        modified = change["modified"]
        updated_content, fuzzy = _replace_fragment(content, original, modified)

        if updated_content is not None:
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                results["success"] += 1
                if fuzzy:
                    results["details"].append(f"[OK~] {file_path} (match fuzzy)")
                else:
                    results["details"].append(f"[OK] {file_path}")
            except Exception as e:
                results["failed"] += 1
                results["details"].append(f"[ERROR] Escribiendo {file_path}: {e}")
        else:
            results["failed"] += 1
            results["details"].append(
                f"[NO MATCH] {file_path}: fragmento original no encontrado")

    return results


def _show_results(app_instance, results):
    detail_text = "\n".join(results["details"])
    summary = (
        f"Inyección Anti-Agent completada:\n\n"
        f"  Modificaciones aplicadas: {results['success']}\n"
        f"  Archivos creados: {results['created']}\n"
        f"  Fallos: {results['failed']}\n\n"
        f"Detalle:\n{detail_text}"
    )
    messagebox.showinfo("Anti-Agent - Resultado", summary)


def _refresh_code_view(app_instance):
    code_view = getattr(getattr(app_instance, "layout", None), "code_view", None)
    if code_view is not None and hasattr(code_view, "refresh_file_list"):
        code_view.refresh_file_list()


def process_bridge_injection(app_instance):
    clipboard_content = _get_clipboard_text(app_instance)

    if not clipboard_content.strip():
        messagebox.showwarning("Anti-Agent", "El portapapeles está vacío. "
                               "Pega la respuesta de la IA primero.")
        return True

    changes = parse_ai_response(clipboard_content)
    if not changes:
        messagebox.showwarning(
            "Anti-Agent",
            "No se encontraron bloques de cambios válidos en el portapapeles.\n\n"
            "Asegúrate de que la IA ha usado el formato:\n"
            "[[[ ARCHIVO: ruta ]]]\n"
            "[[[ PATCH ... PATCH ]]]")
        return True

    project_root = _get_project_root(app_instance)
    if not project_root:
        messagebox.showwarning("Anti-Agent", "No hay ningún proyecto cargado.")
        return True

    if not _confirm_injection(app_instance, changes):
        return True

    results = _apply_changes(project_root, changes)
    _refresh_code_view(app_instance)
    _show_results(app_instance, results)
    return True


def _confirm_injection(app_instance, changes):
    n_mods = sum(1 for c in changes if c["type"] == "modification")
    n_patch_ops = sum(len(c.get("operations", [])) for c in changes if c["type"] == "patch")
    n_new = sum(1 for c in changes if c["type"] == "new_file")
    files_affected = set(c["file"] for c in changes)

    summary_lines = [
        f"Se van a aplicar {n_mods + n_patch_ops} modificación(es) y {n_new} fichero(s) nuevo(s)."
    ]
    summary_lines.append(f"Archivos afectados ({len(files_affected)}):")
    for f in sorted(files_affected):
        summary_lines.append(f"  - {f}")
    summary_lines.append("\n¿Continuar?")

    return messagebox.askyesno("Anti-Agent - Confirmar inyección", "\n".join(summary_lines))


def build_anti_agent_output_instruction():
    lines = [
        "=" * 60,
        "FORMATO DE RESPUESTA OBLIGATORIO",
        "=" * 60,
        "",
        "Usa parches incrementales. NO devuelvas archivos completos ni bloques",
        "originales completos. Devuelve solo las líneas nuevas o cambiadas y un",
        "ancla FIND mínima para localizar dónde aplicar cada cambio.",
        "NO envuelvas el código en bloques markdown (nada de ```). Escribe el código tal cual.",
        "",
        "[[[ ARCHIVO: ruta/del/archivo.ext ]]]",
        "[[[ PATCH",
        "@@ REPLACE",
        "LINE:",
        "123-125",
        "FIND:",
        "// texto mínimo exacto que se sustituye",
        "WITH:",
        "// texto nuevo",
        "",
        "@@ INSERT_AFTER",
        "LINE:",
        "123",
        "FIND:",
        "// ancla mínima exacta existente",
        "CONTENT:",
        "// código nuevo a insertar después del ancla",
        "",
        "@@ INSERT_BEFORE",
        "LINE:",
        "123",
        "FIND:",
        "// ancla mínima exacta existente",
        "CONTENT:",
        "// código nuevo a insertar antes del ancla",
        "",
        "@@ DELETE",
        "LINE:",
        "123-125",
        "FIND:",
        "// texto mínimo exacto que se elimina",
        "PATCH ]]]",
        "",
        "REGLAS:",
        "1. Usa @@ INSERT_AFTER o @@ INSERT_BEFORE para añadir código sin repetir",
        "   el bloque existente completo.",
        "2. Usa @@ REPLACE solo para la parte concreta que cambia, no para toda",
        "   la función si solo cambian unas líneas.",
        "3. LINE es obligatorio y debe indicar la línea o rango aproximado del",
        "   archivo original. Si FIND falla, la app usará LINE como fallback.",
        "4. FIND debe ser el ancla más corta que sea única en el archivo.",
        "5. Si hay múltiples cambios en un mismo archivo, pon varias operaciones",
        "   @@ dentro del mismo bloque PATCH, en orden de aplicación.",
        "6. INSERT_AFTER e INSERT_BEFORE están pensados para insertar líneas;",
        "   para cambios dentro de una línea usa @@ REPLACE.",
        "7. Si necesitas CREAR un archivo nuevo, usa:",
        "   [[[ ARCHIVO NUEVO: ruta/nuevo/archivo.ext ]]]",
        "   ]]] CONTENIDO",
        "   // código completo del nuevo archivo",
        "   CONTENIDO [[[",
        "8. Para eliminar código usa @@ DELETE con FIND; no generes WITH vacío.",
        "9. NO uses bloques de código markdown (```) en ningún lugar de la respuesta.",
        "",
        "FORMATO LEGADO ACEPTADO SOLO SI ES IMPRESCINDIBLE:",
        "[[[ ARCHIVO: ruta/del/archivo.ext ]]]",
        "[[[ ORIGINAL",
        "// código original exacto",
        "ORIGINAL ]]]",
        "]]] MODIFICADO",
        "// código nuevo",
        "MODIFICADO [[[",
    ]
    return "\n".join(lines)
