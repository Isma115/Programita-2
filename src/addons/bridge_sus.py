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

        original = change["original"]
        modified = change["modified"]

        if original in content:
            content = content.replace(original, modified, 1)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                results["success"] += 1
                results["details"].append(f"[OK] {file_path}")
            except Exception as e:
                results["failed"] += 1
                results["details"].append(f"[ERROR] Escribiendo {file_path}: {e}")
        else:
            normalized_content = _normalize_whitespace(content)
            normalized_original = _normalize_whitespace(original)
            if normalized_original in normalized_content:
                start_idx = normalized_content.index(normalized_original)
                original_start = _map_normalized_to_original(content, start_idx)
                original_end = _map_normalized_to_original(
                    content, start_idx + len(normalized_original))
                content = content[:original_start] + modified + content[original_end:]
                try:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    results["success"] += 1
                    results["details"].append(f"[OK~] {file_path} (match fuzzy)")
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append(f"[ERROR] {file_path}: {e}")
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
            "[[[ ORIGINAL ... ORIGINAL ]]]\n"
            "]]] MODIFICADO ... MODIFICADO [[[")
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
    n_new = sum(1 for c in changes if c["type"] == "new_file")
    files_affected = set(c["file"] for c in changes)

    summary_lines = [f"Se van a aplicar {n_mods} modificación(es) y {n_new} fichero(s) nuevo(s)."]
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
        "Para CADA modificación que realices, debes devolverla EXACTAMENTE",
        "en el siguiente formato (respeta los marcadores al pie de la letra).",
        "NO envuelvas el código en bloques markdown (nada de ```). Escribe el código tal cual.",
        "",
        "[[[ ARCHIVO: ruta/del/archivo.ext ]]]",
        "[[[ ORIGINAL",
        "// código ORIGINAL exacto que vas a reemplazar",
        "ORIGINAL ]]]",
        "]]] MODIFICADO",
        "// código NUEVO que reemplaza al original",
        "MODIFICADO [[["
        "",
        "REGLAS:",
        "1. El bloque [[[ ORIGINAL debe contener código EXACTO del archivo,",
        "   carácter por carácter, para que pueda encontrarse y reemplazarse.",
        "2. Incluye suficiente contexto (2-3 líneas antes/después) para que",
        "   la búsqueda sea única y no ambigua.",
        "3. Si hay múltiples cambios en un mismo archivo, usa múltiples bloques.",
        "4. Si necesitas CREAR un archivo nuevo, usa:",
        "   [[[ ARCHIVO NUEVO: ruta/nuevo/archivo.ext ]]]",
        "   ]]] CONTENIDO",
        "   // código completo del nuevo archivo",
        "   CONTENIDO [[[",
        "5. Si necesitas ELIMINAR código, deja el bloque MODIFICADO vacío.",
        "6. NO uses bloques de código markdown (```) en ningún lugar de la respuesta.",
    ]
    return "\n".join(lines)
