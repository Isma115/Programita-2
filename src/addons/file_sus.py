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

COMMON_CODE_WORDS = {
    "true", "false", "null", "none", "self", "this", "return", "const", "let", "var",
    "class", "function", "public", "private", "protected", "static", "async", "await",
    "import", "from", "export", "default", "new", "void", "int", "string", "bool",
    "float", "double", "if", "else", "for", "while", "switch", "case", "break",
    "continue", "try", "catch", "finally", "def", "pass", "raise", "lambda", "with",
    "using", "namespace", "package", "module", "extends", "implements", "interface",
}


def _normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _is_file_replace_enabled(app_instance):
    try:
        if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
            code_view = app_instance.layout.code_view
            if hasattr(code_view, "var_return_files"):
                return bool(code_view.var_return_files.get())
    except Exception:
        pass

    try:
        if hasattr(app_instance, "controller") and hasattr(app_instance.controller, "config_manager"):
            return bool(app_instance.controller.config_manager.get_return_files())
    except Exception:
        pass

    return False


def _get_listed_code_files(app_instance):
    listed_paths = []

    if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
        code_view = app_instance.layout.code_view
        if hasattr(code_view, "tree"):
            for item_id in code_view.tree.get_children():
                tags = code_view.tree.item(item_id, "tags")
                if not tags:
                    continue
                file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                if file_path and os.path.exists(file_path):
                    listed_paths.append(file_path)

    visible_paths = set(listed_paths)
    files = []
    controller = getattr(app_instance, "controller", None)
    project_files = controller.project_manager.get_files() if controller and hasattr(controller, "project_manager") else []

    for file_info in project_files:
        path = file_info.get("path")
        if path not in visible_paths:
            continue

        rel_path = file_info.get("rel_path") or os.path.basename(path)
        content = _normalize_text(file_info.get("content") or "")
        files.append({
            "path": path,
            "rel_path": rel_path,
            "rel_path_norm": rel_path.replace("\\", "/").lower(),
            "basename": os.path.basename(path),
            "basename_norm": os.path.basename(path).lower(),
            "content": content,
            "signature": _build_content_signature(content),
        })

    return files


def _build_content_signature(content):
    normalized = _normalize_text(content)
    lines = normalized.split("\n")

    significant_lines = []
    for line in lines:
        compact = re.sub(r"\s+", " ", line.strip())
        if len(compact) < 3:
            continue
        if re.fullmatch(r"[\W_]+", compact):
            continue
        significant_lines.append(compact[:200])

    string_literals = {
        match.strip()
        for match in re.findall(r'["\']([^"\']{3,160})["\']', normalized)
        if not re.fullmatch(r"[\W_]+", match.strip())
    }
    identifiers = {
        token.lower()
        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", normalized)
        if token.lower() not in COMMON_CODE_WORDS
    }

    return {
        "lines": set(significant_lines[:250]),
        "strings": string_literals,
        "identifiers": identifiers,
    }


def _looks_like_code(text):
    normalized = _normalize_text(text).strip()
    if not normalized:
        return False

    non_empty_lines = [line for line in normalized.split("\n") if line.strip()]
    code_markers = [
        r"\b(class|def|function|import|from|return|public|private|const|let|var|if|for|while|switch)\b",
        r"[{}();=<>]",
        r"</?[A-Za-z][^>]*>",
    ]
    joined = "\n".join(non_empty_lines[:40])
    if len(non_empty_lines) >= 2:
        return any(re.search(pattern, joined) for pattern in code_markers)
    return any(re.search(pattern, joined) for pattern in code_markers[:2]) and len(joined) >= 8


def _extract_explicit_marker_path(line):
    stripped = line.strip()
    if not stripped:
        return None

    patterns = [
        r"^-{3,}\s*(?:Archivo|Fichero|File)\s*:\s*(.+?)\s*-{3,}$",
        r"^(?:Archivo|Fichero|File)\s*:\s*(.+?)$",
        r"^#{1,6}\s*(?:Archivo|Fichero|File)\s*:\s*(.+?)$",
        r"^\*\*(?:Archivo|Fichero|File)\s*:\s*(.+?)\*\*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stripped, re.IGNORECASE)
        if match:
            candidate = _clean_path_hint(match.group(1))
            if _looks_like_path(candidate):
                return candidate
    return None


def _extract_context_path_hint(line):
    stripped = line.strip()
    if not stripped:
        return None

    explicit = _extract_explicit_marker_path(stripped)
    if explicit:
        return explicit

    wrappers = [
        (r"^#{1,6}\s+(.+?)$", 1),
        (r"^\*\*(.+?)\*\*$", 1),
        (r"^`(.+?)`$", 1),
        (r"^\((.+?)\)$", 1),
    ]
    for pattern, group in wrappers:
        match = re.match(pattern, stripped)
        if match:
            candidate = _clean_path_hint(match.group(group))
            if _looks_like_path(candidate):
                return candidate

    candidate = _clean_path_hint(stripped)
    if _looks_like_path(candidate):
        return candidate
    return None


def _clean_path_hint(text):
    cleaned = (text or "").strip()
    cleaned = cleaned.strip("`*[](){}<>")
    cleaned = cleaned.rstrip(":")
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"^(?:[ab]/)", "", cleaned)
    cleaned = re.sub(r"^\./+", "", cleaned)
    return cleaned.strip()


def _looks_like_path(text):
    candidate = (text or "").strip()
    if not candidate or len(candidate) > 260:
        return False
    if candidate.startswith("```") or " " in candidate and "/" not in candidate and "." not in candidate:
        return False
    return bool(re.search(r"(?:/|\\|[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+)$", candidate))


def _extract_file_blocks(text):
    normalized = _normalize_text(text)
    blocks = []

    marker_positions = []
    lines = normalized.split("\n")
    offset = 0
    for index, line in enumerate(lines):
        marker_path = _extract_explicit_marker_path(line)
        if marker_path:
            marker_positions.append({
                "line_index": index,
                "offset": offset,
                "path_hint": marker_path,
            })
        offset += len(line) + 1

    if marker_positions:
        for idx, marker in enumerate(marker_positions):
            start_line = marker["line_index"] + 1
            end_line = marker_positions[idx + 1]["line_index"] if idx + 1 < len(marker_positions) else len(lines)
            block_text = _unwrap_outer_fence("\n".join(lines[start_line:end_line]).strip("\n"))
            if block_text.strip() and _looks_like_code(block_text):
                blocks.append({
                    "path_hint": marker["path_hint"],
                    "content": block_text,
                    "source": "marker",
                })
        if blocks:
            return blocks

    fence_pattern = re.compile(r"(?ms)^[ \t]*(```|~~~)(?P<info>[^\n]*)\n(?P<code>.*?)(?:\n^[ \t]*\1[ \t]*$)")
    for match in fence_pattern.finditer(normalized):
        code = match.group("code").strip("\n")
        if not code.strip() or not _looks_like_code(code):
            continue

        path_hint = _extract_path_hint_near_match(normalized[:match.start()], match.group("info"))
        blocks.append({
            "path_hint": path_hint,
            "content": code,
            "source": "fence",
        })

    if blocks:
        return blocks

    stripped = normalized.strip()
    if _looks_like_code(stripped):
        return [{
            "path_hint": None,
            "content": stripped,
            "source": "raw",
        }]

    return []


def _unwrap_outer_fence(text):
    normalized = _normalize_text(text).strip()
    match = re.match(r"(?s)^\s*(?:```|~~~)[^\n]*\n(.*)\n\s*(?:```|~~~)\s*$", normalized)
    if match:
        return match.group(1).strip("\n")
    return text


def _extract_path_hint_near_match(prefix_text, fence_info):
    fence_hint = _extract_context_path_hint(_clean_path_hint(fence_info or ""))
    if fence_hint:
        return fence_hint

    recent_lines = [line for line in prefix_text.split("\n")[-5:] if line.strip()]
    for line in reversed(recent_lines):
        hint = _extract_context_path_hint(line)
        if hint:
            return hint
    return None


def _match_files_by_path_hint(path_hint, listed_files):
    if not path_hint:
        return []

    normalized_hint = _clean_path_hint(path_hint).lower()
    if not normalized_hint:
        return []

    exact_matches = [
        file_info for file_info in listed_files
        if normalized_hint == file_info["rel_path_norm"] or normalized_hint == file_info["path"].replace("\\", "/").lower()
    ]
    if exact_matches:
        return exact_matches

    suffix_matches = [
        file_info for file_info in listed_files
        if file_info["rel_path_norm"].endswith(normalized_hint)
    ]
    if suffix_matches:
        return suffix_matches

    basename = os.path.basename(normalized_hint)
    if basename:
        basename_matches = [
            file_info for file_info in listed_files
            if file_info["basename_norm"] == basename
        ]
        if basename_matches:
            return basename_matches

    return []


def _score_content_match(block_content, file_info):
    block_signature = _build_content_signature(block_content)
    file_signature = file_info["signature"]

    line_overlap = len(block_signature["lines"] & file_signature["lines"])
    string_overlap = len(block_signature["strings"] & file_signature["strings"])
    identifier_overlap = len(block_signature["identifiers"] & file_signature["identifiers"])

    score = (line_overlap * 20) + (string_overlap * 9) + min(identifier_overlap, 25)
    return {
        "score": score,
        "line_overlap": line_overlap,
        "string_overlap": string_overlap,
        "identifier_overlap": identifier_overlap,
    }


def _resolve_block_target(block, listed_files):
    candidates = _match_files_by_path_hint(block.get("path_hint"), listed_files)

    if len(candidates) == 1:
        return {"file": candidates[0], "reason": "path"}

    candidate_pool = candidates if candidates else listed_files
    scored = []
    for file_info in candidate_pool:
        metrics = _score_content_match(block["content"], file_info)
        if metrics["score"] <= 0:
            continue
        scored.append((metrics, file_info))

    scored.sort(key=lambda item: (
        item[0]["score"],
        item[0]["line_overlap"],
        item[0]["string_overlap"],
        item[0]["identifier_overlap"],
    ), reverse=True)

    if not scored:
        return {"file": None, "reason": "no_match"}

    best_metrics, best_file = scored[0]
    second_score = scored[1][0]["score"] if len(scored) > 1 else -1
    unique_enough = (
        best_metrics["score"] >= 20
        and (len(scored) == 1 or best_metrics["score"] >= second_score + 8)
    )

    if unique_enough:
        return {"file": best_file, "reason": "content"}

    return {"file": None, "reason": "ambiguous"}


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
    dialog.title("Sustitución de archivos detectada")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 860
    h = 430
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(dialog, bg=THEME["bg"], padx=22, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Se han detectado archivos completos del portapapeles que coinciden con la lista visible de Código.",
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=("Segoe UI", 12),
        wraplength=800,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 12))

    tk.Label(
        frame,
        text="Archivos que se van a sustituir:",
        bg=THEME["bg"],
        fg="#569cd6",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).pack(fill="x")

    text_box = tk.Text(
        frame,
        height=12,
        bg="#1f2430",
        fg="#dcdcaa",
        font=("Menlo", 12),
        relief="flat",
        wrap="word",
    )
    text_box.pack(fill="both", expand=True, pady=(6, 16))

    for index, replacement in enumerate(replacements, start=1):
        file_info = replacement["file"]
        match_reason = "ruta" if replacement["reason"] == "path" else "contenido"
        text_box.insert(
            "end",
            f"{index}. {file_info['rel_path']}\n   Detectado por: {match_reason}\n   Líneas nuevas: {len(replacement['new_content'].splitlines())}\n\n"
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
    dialog.title("Sustitución completada")
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
        details.insert(
            "end",
            (
                f"{item['rel_path']}\n"
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
    dialog.title("No se pudo resolver la sustitución")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 760
    h = 300
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
        wraplength=700,
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
        lines.append("No se han encontrado bloques de fichero utilizables en el portapapeles.")
    if unresolved:
        lines.append("No se han podido asociar de forma única algunos bloques del portapapeles:")
        for item in unresolved:
            hint = item.get("path_hint") or "(sin ruta detectada)"
            lines.append(f"- {hint}")
    if duplicates:
        lines.append("Se ha detectado más de un bloque dirigido al mismo archivo:")
        for rel_path in duplicates:
            lines.append(f"- {rel_path}")
    lines.append("No se ha realizado ninguna sustitución automática.")
    return "\n".join(lines)


def process_file_replacements(app_instance):
    if not _is_file_replace_enabled(app_instance):
        return False

    clipboard_text = _normalize_text(pyperclip.paste())
    if not clipboard_text.strip():
        return False

    listed_files = _get_listed_code_files(app_instance)
    if not listed_files:
        messagebox.showwarning(
            "Smart Paste",
            "No hay archivos visibles en la seccion de Codigo para buscar coincidencias de fichero."
        )
        return True

    blocks = _extract_file_blocks(clipboard_text)
    if not blocks:
        return False

    replacements = []
    unresolved = []
    duplicate_targets = []
    seen_targets = set()

    for block in blocks:
        resolved = _resolve_block_target(block, listed_files)
        target_file = resolved.get("file")
        if not target_file:
            unresolved.append(block)
            continue

        if target_file["path"] in seen_targets:
            duplicate_targets.append(target_file["rel_path"])
            continue

        seen_targets.add(target_file["path"])
        replacements.append({
            "file": target_file,
            "reason": resolved["reason"],
            "new_content": _normalize_text(block["content"]).strip("\n"),
        })

    if not replacements or unresolved or duplicate_targets:
        _show_resolution_warning(_build_resolution_error(blocks, unresolved, duplicate_targets))
        return True

    if not _show_confirmation_dialog(replacements):
        return True

    results = []
    try:
        for replacement in replacements:
            file_info = replacement["file"]
            before_text = file_info["content"]
            after_text = replacement["new_content"]

            with open(file_info["path"], "w", encoding="utf-8") as fh:
                fh.write(after_text)

            if hasattr(app_instance, "controller"):
                app_instance.controller.refresh_cached_file_content(file_info["path"], after_text)

            results.append({
                "rel_path": file_info["rel_path"],
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
