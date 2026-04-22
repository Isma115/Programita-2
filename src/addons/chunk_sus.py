import difflib
import os
import re
import tkinter as tk
from tkinter import messagebox

import pyperclip


THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
}


def _normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _is_chunk_replace_enabled(app_instance):
    try:
        if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
            code_view = app_instance.layout.code_view
            if hasattr(code_view, "var_return_chunks"):
                return bool(code_view.var_return_chunks.get())
    except Exception:
        pass

    try:
        if hasattr(app_instance, "controller") and hasattr(app_instance.controller, "config_manager"):
            return bool(app_instance.controller.config_manager.get_return_chunks())
    except Exception:
        pass

    return False


def _clean_path_hint(text):
    cleaned = (text or "").strip()
    cleaned = cleaned.strip("`*[]{}<>")
    cleaned = cleaned.rstrip(":")
    cleaned = re.sub(r"^(?:[ab]/)", "", cleaned)
    cleaned = re.sub(r"^\./+", "", cleaned)
    return cleaned.strip()


def _extract_explicit_part_marker(line):
    stripped = (line or "").strip()
    if not stripped:
        return None

    wrappers = [
        (r"^-{3,}\s*(.+?)\s*-{3,}$", 1),
        (r"^#{1,6}\s*(.+?)$", 1),
        (r"^\*\*(.+?)\*\*$", 1),
        (r"^`(.+?)`$", 1),
    ]
    for pattern, group in wrappers:
        match = re.match(pattern, stripped)
        if match:
            stripped = match.group(group).strip()
            break

    match = re.match(
        r"^(?:(?:Archivo|Fichero|File)\s*:?\s*)?(.+?)\s*\((?:parte|part)\s+(\d+)\s*/\s*(\d+)\)\s*$",
        stripped,
        re.IGNORECASE,
    )
    if not match:
        return None

    path_hint = _clean_path_hint(match.group(1))
    if not path_hint:
        return None

    part_index = int(match.group(2))
    total_parts = int(match.group(3))
    if part_index < 1 or total_parts < 1 or part_index > total_parts:
        return None

    return {
        "path_hint": path_hint,
        "part_index": part_index,
        "total_parts": total_parts,
    }


def _unwrap_outer_fence(text):
    normalized = _normalize_text(text).strip()
    match = re.match(r"(?s)^\s*(?:```|~~~)[^\n]*\n(.*)\n\s*(?:```|~~~)\s*$", normalized)
    if match:
        return match.group(1).strip("\n")
    return text


def _extract_chunk_blocks(text):
    normalized = _normalize_text(text)
    lines = normalized.split("\n")
    markers = []

    for index, line in enumerate(lines):
        marker = _extract_explicit_part_marker(line)
        if marker:
            marker["line_index"] = index
            markers.append(marker)

    blocks = []
    if markers:
        for idx, marker in enumerate(markers):
            start_line = marker["line_index"] + 1
            end_line = markers[idx + 1]["line_index"] if idx + 1 < len(markers) else len(lines)
            block_text = _unwrap_outer_fence("\n".join(lines[start_line:end_line]).strip("\n"))
            if not block_text.strip():
                continue
            blocks.append({
                "path_hint": marker["path_hint"],
                "part_index": marker["part_index"],
                "total_parts": marker["total_parts"],
                "content": block_text,
            })
        if blocks:
            return blocks

    fence_pattern = re.compile(r"(?ms)^[ \t]*(```|~~~)[^\n]*\n(?P<code>.*?)(?:\n^[ \t]*\1[ \t]*$)")
    for match in fence_pattern.finditer(normalized):
        recent_lines = [line for line in normalized[:match.start()].split("\n")[-5:] if line.strip()]
        marker = None
        for line in reversed(recent_lines):
            marker = _extract_explicit_part_marker(line)
            if marker:
                break
        if not marker:
            continue

        code = match.group("code").strip("\n")
        if not code.strip():
            continue

        blocks.append({
            "path_hint": marker["path_hint"],
            "part_index": marker["part_index"],
            "total_parts": marker["total_parts"],
            "content": code,
        })

    return blocks


def _split_file_into_chunks(controller, file_info):
    rel_path = file_info.get("rel_path") or os.path.basename(file_info.get("path", "")) or "archivo"
    content = _normalize_text(file_info.get("content") or "")
    lines = content.splitlines(keepends=True)

    segments = []
    separators = []
    current = []

    for line in lines:
        if controller._is_prompt_separator_line(line):
            segments.append("".join(current))
            separators.append(_normalize_text(line))
            current = []
            continue
        current.append(line)

    segments.append("".join(current))
    if not segments:
        segments = [""]

    total_parts = len(segments)
    chunks = []
    for index, segment in enumerate(segments, start=1):
        chunks.append({
            "path": file_info["path"],
            "rel_path": rel_path,
            "rel_path_norm": rel_path.replace("\\", "/").lower(),
            "part_index": index,
            "total_parts": total_parts,
            "label": f"{rel_path} (parte {index}/{total_parts})",
            "content": segment.rstrip("\n"),
        })

    return {
        "chunks": chunks,
        "segments": segments,
        "separators": separators,
    }


def _get_listed_chunk_targets(app_instance):
    listed_paths = []

    if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
        code_view = app_instance.layout.code_view
        if hasattr(code_view, "tree"):
            for item_id in code_view.tree.get_children():
                file_path = None
                if hasattr(code_view, "_get_tree_item_path"):
                    file_path = code_view._get_tree_item_path(item_id)
                else:
                    tags = code_view.tree.item(item_id, "tags")
                    if tags:
                        file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                if file_path and os.path.exists(file_path):
                    listed_paths.append(file_path)

    visible_paths = set(listed_paths)
    controller = getattr(app_instance, "controller", None)
    if not controller or not hasattr(controller, "project_manager"):
        return {}

    targets = {}
    for file_info in controller.project_manager.get_files():
        path = file_info.get("path")
        if path not in visible_paths:
            continue
        targets[path] = _split_file_into_chunks(controller, file_info)

    return targets


def _match_targets_by_path(path_hint, targets):
    normalized_hint = _clean_path_hint(path_hint).replace("\\", "/").lower()
    if not normalized_hint:
        return []

    exact = []
    suffix = []
    basename = os.path.basename(normalized_hint)

    for file_target in targets.values():
        rel_path_norm = file_target["chunks"][0]["rel_path_norm"]
        abs_path_norm = file_target["chunks"][0]["path"].replace("\\", "/").lower()
        if normalized_hint == rel_path_norm or normalized_hint == abs_path_norm:
            exact.append(file_target)
        elif rel_path_norm.endswith(normalized_hint):
            suffix.append(file_target)

    if exact:
        return exact
    if suffix:
        return suffix

    if basename:
        basename_matches = [
            file_target
            for file_target in targets.values()
            if os.path.basename(file_target["chunks"][0]["rel_path_norm"]) == basename
        ]
        if basename_matches:
            return basename_matches

    return []


def _resolve_block_target(block, targets):
    candidates = _match_targets_by_path(block.get("path_hint"), targets)
    if len(candidates) != 1:
        return None, "ambiguous_path" if candidates else "no_path_match"

    file_target = candidates[0]
    if file_target["chunks"][0]["total_parts"] != block["total_parts"]:
        return None, "part_count_mismatch"

    target_index = block["part_index"] - 1
    if target_index < 0 or target_index >= len(file_target["chunks"]):
        return None, "invalid_part"

    chunk = file_target["chunks"][target_index]
    return {
        "file_path": chunk["path"],
        "rel_path": chunk["rel_path"],
        "part_index": chunk["part_index"],
        "total_parts": chunk["total_parts"],
        "label": chunk["label"],
        "new_content": _normalize_text(block["content"]).strip("\n"),
    }, "path"


def _rebuild_content(segments, separators):
    pieces = []
    for index, segment in enumerate(segments):
        piece = segment
        if index < len(separators):
            if piece and not piece.endswith("\n"):
                piece += "\n"
            pieces.append(piece)
            pieces.append(separators[index])
        else:
            pieces.append(piece)
    return "".join(pieces)


def _count_changed_lines(before_text, after_text):
    before_lines = _normalize_text(before_text).split("\n")
    after_lines = _normalize_text(after_text).split("\n")
    changed = 0

    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed += max(i2 - i1, j2 - j1)

    return changed


def _show_confirmation_dialog(replacements):
    result = {"value": False}
    dialog = tk.Toplevel()
    dialog.title("Sustitución de trozos detectada")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 900
    h = 460
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(dialog, bg=THEME["bg"], padx=22, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Se han detectado trozos del portapapeles que coinciden con las partes visibles de Código.",
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=("Segoe UI", 12),
        wraplength=840,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    tk.Label(
        frame,
        text="Partes que se van a sustituir:",
        bg=THEME["bg"],
        fg="#569cd6",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).pack(fill="x")

    text_box = tk.Text(
        frame,
        height=13,
        bg="#1f2430",
        fg="#dcdcaa",
        font=("Menlo", 12),
        relief="flat",
        wrap="word",
    )
    text_box.pack(fill="both", expand=True, pady=(6, 16))

    for index, replacement in enumerate(replacements, start=1):
        text_box.insert(
            "end",
            (
                f"{index}. {replacement['label']}\n"
                f"   Archivo: {replacement['rel_path']}\n"
                f"   Líneas nuevas: {len(replacement['new_content'].splitlines())}\n\n"
            )
        )

    text_box.config(state="disabled")

    btn_frame = tk.Frame(frame, bg=THEME["bg"])
    btn_frame.pack(fill="x")

    def on_yes():
        result["value"] = True
        dialog.destroy()

    def on_no():
        dialog.destroy()

    tk.Button(
        btn_frame,
        text="Sí, sustituir",
        command=on_yes,
        bg="#6a9955",
        fg="black",
        font=("Segoe UI", 11, "bold"),
        padx=15,
        pady=5,
        cursor="hand2",
    ).pack(side="right", padx=(10, 0))

    tk.Button(
        btn_frame,
        text="Cancelar",
        command=on_no,
        bg="#f44336",
        fg="black",
        font=("Segoe UI", 11),
        padx=15,
        pady=5,
        cursor="hand2",
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", on_no)
    dialog.grab_set()
    dialog.wait_window()
    return result["value"]


def _show_result_dialog(results):
    dialog = tk.Toplevel()
    dialog.title("Sustitución de trozos completada")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 920
    h = 470
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    total_before = sum(item["before_lines"] for item in results)
    total_after = sum(item["after_lines"] for item in results)
    total_changed = sum(item["changed_lines"] for item in results)

    frame = tk.Frame(dialog, bg=THEME["bg"], padx=22, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text=(
            f"Sustitución completada en {len(results)} archivo(s).\n"
            f"Líneas antes: {total_before} | líneas ahora: {total_after} | líneas afectadas: {total_changed}"
        ),
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=("Segoe UI", 12),
        wraplength=860,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    details = tk.Text(
        frame,
        height=14,
        bg="#1f2430",
        fg="#dcdcaa",
        font=("Menlo", 12),
        relief="flat",
        wrap="word",
    )
    details.pack(fill="both", expand=True, pady=(6, 16))

    for item in results:
        replaced_labels = ", ".join(item["replaced_labels"])
        details.insert(
            "end",
            (
                f"{item['rel_path']}\n"
                f"   Partes sustituidas: {replaced_labels}\n"
                f"   Líneas antes: {item['before_lines']}\n"
                f"   Líneas ahora: {item['after_lines']}\n"
                f"   Líneas afectadas: {item['changed_lines']}\n\n"
            )
        )
    details.config(state="disabled")

    tk.Button(
        frame,
        text="Cerrar",
        command=dialog.destroy,
        bg="#6a9955",
        fg="black",
        font=("Segoe UI", 11, "bold"),
        padx=16,
        pady=6,
        cursor="hand2",
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    dialog.wait_window()


def _show_resolution_warning(message):
    dialog = tk.Toplevel()
    dialog.title("No se pudo resolver la sustitución por trozos")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 780
    h = 320
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(dialog, bg=THEME["bg"], padx=22, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text=message,
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=("Segoe UI", 12),
        wraplength=720,
        justify="left",
        anchor="w",
    ).pack(fill="both", expand=True)

    tk.Button(
        frame,
        text="Cerrar",
        command=dialog.destroy,
        bg="#f44336",
        fg="black",
        font=("Segoe UI", 11, "bold"),
        padx=16,
        pady=6,
        cursor="hand2",
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    dialog.wait_window()


def _build_resolution_error(blocks, unresolved, duplicates):
    lines = []
    if not blocks:
        lines.append("No se han encontrado bloques de trozo utilizables en el portapapeles.")
    if unresolved:
        lines.append("No se han podido asociar de forma única algunos trozos del portapapeles:")
        for item in unresolved:
            label = item.get("label") or "(sin etiqueta válida)"
            reason = item.get("reason")
            if reason == "part_count_mismatch":
                label += " [número de partes distinto al fichero actual]"
            elif reason == "invalid_part":
                label += " [índice de parte inválido]"
            elif reason == "ambiguous_path":
                label += " [ruta ambigua]"
            lines.append(f"- {label}")
    if duplicates:
        lines.append("Se ha detectado más de un bloque dirigido a la misma parte:")
        for label in duplicates:
            lines.append(f"- {label}")
    lines.append("No se ha realizado ninguna sustitución automática.")
    return "\n".join(lines)


def process_chunk_replacements(app_instance):
    if not _is_chunk_replace_enabled(app_instance):
        return False

    clipboard_text = _normalize_text(pyperclip.paste())
    if not clipboard_text.strip():
        return False

    targets = _get_listed_chunk_targets(app_instance)
    if not targets:
        messagebox.showwarning(
            "Smart Paste",
            "No hay archivos visibles en la seccion de Codigo para buscar coincidencias por trozos."
        )
        return True

    blocks = _extract_chunk_blocks(clipboard_text)
    if not blocks:
        return False

    replacements = []
    unresolved = []
    duplicate_targets = []
    seen_targets = set()

    for block in blocks:
        replacement, reason = _resolve_block_target(block, targets)
        label = f"{block['path_hint']} (parte {block['part_index']}/{block['total_parts']})"

        if not replacement:
            unresolved.append({"label": label, "reason": reason})
            continue

        target_key = (replacement["file_path"], replacement["part_index"], replacement["total_parts"])
        if target_key in seen_targets:
            duplicate_targets.append(replacement["label"])
            continue

        seen_targets.add(target_key)
        replacements.append(replacement)

    if not replacements or unresolved or duplicate_targets:
        _show_resolution_warning(_build_resolution_error(blocks, unresolved, duplicate_targets))
        return True

    if not _show_confirmation_dialog(replacements):
        return True

    grouped = {}
    for replacement in replacements:
        grouped.setdefault(replacement["file_path"], []).append(replacement)

    results = []
    try:
        for file_path, file_replacements in grouped.items():
            file_target = targets[file_path]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                before_text = _normalize_text(fh.read())
            refreshed_info = {
                "path": file_path,
                "rel_path": file_target["chunks"][0]["rel_path"],
                "content": before_text,
            }
            current_split = _split_file_into_chunks(app_instance.controller, refreshed_info)
            segments = list(current_split["segments"])
            separators = list(current_split["separators"])

            expected_total_parts = file_replacements[0]["total_parts"]
            if len(segments) != expected_total_parts:
                raise ValueError(f"No se ha podido recalcular las partes de {file_target['chunks'][0]['rel_path']}.")

            for replacement in sorted(file_replacements, key=lambda item: item["part_index"]):
                index = replacement["part_index"] - 1
                new_segment = replacement["new_content"]
                if index < len(separators) and new_segment and not new_segment.endswith("\n"):
                    new_segment += "\n"
                elif index == len(segments) - 1 and segments[index].endswith("\n") and new_segment and not new_segment.endswith("\n"):
                    new_segment += "\n"
                segments[index] = new_segment

            after_text = _rebuild_content(segments, separators)

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(after_text)

            if hasattr(app_instance, "controller"):
                app_instance.controller.refresh_cached_file_content(file_path, after_text)

            results.append({
                "rel_path": file_target["chunks"][0]["rel_path"],
                "replaced_labels": [item["label"] for item in sorted(file_replacements, key=lambda item: item["part_index"])],
                "before_lines": len(before_text.splitlines()),
                "after_lines": len(after_text.splitlines()),
                "changed_lines": _count_changed_lines(before_text, after_text),
            })
    except Exception as e:
        messagebox.showerror("Smart Paste", f"No se pudo guardar uno de los archivos:\n{e}")
        return True

    if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
        app_instance.layout.code_view.refresh_file_list()

    _show_result_dialog(results)
    return True
