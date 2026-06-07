import difflib
import logging
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

import pyperclip

from src.addons.Arbitrary_sus import (
    FONT_UI,
    THEME,
    _unwrap_outer_fence,
    create_styled_text_widget,
    highlight_syntax,
)
from src.logic.syntax_validator import validate_code_syntax
from src.logic.controller import strip_modification_comments
from src.ui.styles import Styles

_MIN_STRUCTURE_CHARS = 30
_MAX_CLIPBOARD_STRUCTURES = 24
_MAX_PROJECT_STRUCTURES_PER_FILE = 300
_BRACKET_PAIRS = {"{": "}", "(": ")", "[": "]"}
_CLOSING_BRACKETS = set(_BRACKET_PAIRS.values())
_PYTHON_BLOCK_RE = re.compile(
    r"^\s*(?:async\s+def|def|class|if|elif|else|for|while|try|except|finally|with|match|case)\b.*:\s*(?:#.*)?$"
)
_ACTIVE_CLEVER_POPUP = None


class CodeStructure:
    def __init__(self, text, header, start, end, line_num, file_path=None, kind="block"):
        self.text = text
        self.header = header
        self.start = start
        self.end = end
        self.line_num = line_num
        self.file_path = file_path
        self.kind = kind


class StructureMatch:
    def __init__(self, clipboard_structure, project_structure, score, header_score, body_score):
        self.clipboard_structure = clipboard_structure
        self.project_structure = project_structure
        self.score = score
        self.header_score = header_score
        self.body_score = body_score


def _normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _normalize_for_similarity(text):
    normalized = _normalize_text(text).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _line_num_for_index(text, index):
    return text.count("\n", 0, max(0, index)) + 1


def _line_bounds(text, index):
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end == -1:
        end = len(text)
    return start, end


def _previous_non_empty_line_start(text, line_start):
    cursor = line_start - 1
    while cursor > 0:
        prev_end = cursor
        prev_start = text.rfind("\n", 0, prev_end) + 1
        if text[prev_start:prev_end].strip():
            return prev_start
        cursor = prev_start - 1
    return line_start


def _extend_to_statement_end(text, end_index):
    cursor = end_index
    while cursor < len(text) and text[cursor] in " \t;,.":
        cursor += 1
    return cursor


def _is_escaped(text, index):
    slash_count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        slash_count += 1
        cursor -= 1
    return slash_count % 2 == 1


def _extract_bracket_structures(text, file_path=None):
    structures = []
    stack = []
    quote = None
    triple_quote = None
    line_comment = False
    block_comment = False
    i = 0

    while i < len(text):
        char = text[i]
        nxt = text[i:i + 2]
        nxt3 = text[i:i + 3]

        if line_comment:
            if char == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            if nxt == "*/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue

        if triple_quote:
            if nxt3 == triple_quote:
                triple_quote = None
                i += 3
            else:
                i += 1
            continue

        if quote:
            if char == quote and not _is_escaped(text, i):
                quote = None
            i += 1
            continue

        if nxt == "//":
            line_comment = True
            i += 2
            continue
        if nxt == "/*":
            block_comment = True
            i += 2
            continue
        if nxt3 in ('"""', "'''"):
            triple_quote = nxt3
            i += 3
            continue
        if char in ('"', "'", "`"):
            quote = char
            i += 1
            continue

        if char in _BRACKET_PAIRS:
            line_start, _ = _line_bounds(text, i)
            header_start = line_start
            header = text[line_start:i + 1].strip()
            if not header:
                header_start = _previous_non_empty_line_start(text, line_start)
                header = text[header_start:i + 1].strip()
            stack.append({
                "opener": char,
                "start": header_start,
                "header": header,
            })
            i += 1
            continue

        if char in _CLOSING_BRACKETS and stack:
            opener = stack[-1]["opener"]
            if _BRACKET_PAIRS.get(opener) == char:
                frame = stack.pop()
                raw_end = _extend_to_statement_end(text, i + 1)
                block = text[frame["start"]:raw_end]
                header_line_start, header_line_end = _line_bounds(text, frame["start"])
                header = text[header_line_start:header_line_end].strip()
                if _looks_like_structure(block, header):
                    structures.append(CodeStructure(
                        text=block,
                        header=header,
                        start=frame["start"],
                        end=raw_end,
                        line_num=_line_num_for_index(text, frame["start"]),
                        file_path=file_path,
                        kind=f"bracket:{opener}",
                    ))
            i += 1
            continue

        i += 1

    return structures


def _extract_python_structures(text, file_path=None):
    lines = text.splitlines(keepends=True)
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)

    structures = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or not _PYTHON_BLOCK_RE.match(line):
            index += 1
            continue

        indent = len(line) - len(line.lstrip(" \t"))
        start = offsets[index]
        end_line = index + 1
        while end_line < len(lines):
            candidate = lines[end_line]
            candidate_stripped = candidate.strip()
            if not candidate_stripped:
                end_line += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip(" \t"))
            if candidate_indent <= indent:
                break
            end_line += 1

        if end_line > index + 1:
            end = offsets[end_line] if end_line < len(offsets) else len(text)
            block = text[start:end].rstrip("\n")
            header = stripped
            if _looks_like_structure(block, header):
                structures.append(CodeStructure(
                    text=block,
                    header=header,
                    start=start,
                    end=start + len(block),
                    line_num=index + 1,
                    file_path=file_path,
                    kind="python",
                ))
        index += 1

    return structures


def _looks_like_structure(block, header):
    stripped = (block or "").strip()
    if len(stripped) < _MIN_STRUCTURE_CHARS:
        return False
    if "\n" not in stripped and len(stripped) < 80:
        return False
    if not (header or "").strip():
        return False
    return True


def _dedupe_structures(structures, limit=None):
    deduped = []
    seen = set()
    for structure in sorted(structures, key=lambda item: (item.start, -(item.end - item.start))):
        key = (structure.start, structure.end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(structure)
        if limit and len(deduped) >= limit:
            break
    return deduped


def _filter_top_level_structures(structures):
    top_level = []
    for structure in sorted(structures, key=lambda item: (item.start, -(item.end - item.start))):
        is_child = False
        for parent in top_level:
            if parent.start <= structure.start and structure.end <= parent.end:
                is_child = True
                break
        if not is_child:
            top_level.append(structure)
    return top_level


def extract_code_structures(text, file_path=None, limit=None, top_level_only=False):
    normalized = _normalize_text(_unwrap_outer_fence(text or ""))
    structures = []
    structures.extend(_extract_bracket_structures(normalized, file_path=file_path))
    structures.extend(_extract_python_structures(normalized, file_path=file_path))
    structures = _dedupe_structures(structures)
    if top_level_only:
        structures = _filter_top_level_structures(structures)
    if limit:
        structures = structures[:limit]
    return structures


def _append_existing_file_path(paths, seen_paths, file_path):
    if not file_path:
        return
    try:
        normalized = os.path.normpath(os.path.abspath(str(file_path)))
    except Exception:
        return
    if normalized in seen_paths or not os.path.isfile(normalized):
        return
    seen_paths.add(normalized)
    paths.append(normalized)


def _append_region_item_paths(paths, seen_paths, region_payload):
    for item in (region_payload or {}).get("items", []):
        if not isinstance(item, dict):
            continue
        _append_existing_file_path(paths, seen_paths, item.get("file_path"))


def _append_section_tree_item_files(paths, seen_paths, code_view, item_id):
    controller = getattr(code_view, "controller", None)
    if not controller or not item_id:
        return

    if item_id.startswith("RSEG:"):
        region_name = item_id[5:]
        region_manager = getattr(controller, "region_segment_manager", None)
        if region_manager:
            _append_region_item_paths(paths, seen_paths, region_manager.get_region_segment(region_name))
        return

    section_manager = getattr(controller, "section_manager", None)
    if not section_manager:
        return

    try:
        if item_id.startswith("SEG:"):
            parts = item_id[4:].split("::", 2)
            if len(parts) == 3:
                for file_path in section_manager.get_files_in_segment(parts[0], parts[1], parts[2]):
                    _append_existing_file_path(paths, seen_paths, file_path)
        elif item_id.startswith("SS:"):
            parts = item_id[3:].split("::", 1)
            if len(parts) == 2:
                for file_path in section_manager.get_files_in_subsection(parts[0], parts[1]):
                    _append_existing_file_path(paths, seen_paths, file_path)
        elif item_id.startswith("S:"):
            for file_path in section_manager.get_files_in_section(item_id[2:]):
                _append_existing_file_path(paths, seen_paths, file_path)
    except Exception as exc:
        logging.info(f"Clever SUS: No se pudieron resolver ficheros para {item_id}: {exc}")


def _iter_tree_items(tree, parent=""):
    try:
        children = tree.get_children(parent)
    except Exception:
        return
    for item_id in children:
        yield item_id
        yield from _iter_tree_items(tree, item_id)


def _get_visible_code_view_files(app_instance):
    paths = []
    seen_paths = set()
    code_view = getattr(getattr(app_instance, "layout", None), "code_view", None)
    if not code_view:
        return paths

    tree = getattr(code_view, "tree", None)
    if tree:
        for item_id in tree.get_children():
            region_item = None
            if hasattr(code_view, "_get_region_row_item"):
                region_item = code_view._get_region_row_item(item_id)
            if region_item:
                _append_existing_file_path(paths, seen_paths, region_item.get("file_path"))
                continue

            file_path = None
            if hasattr(code_view, "_get_tree_item_path"):
                file_path = code_view._get_tree_item_path(item_id)
            else:
                try:
                    file_path = tree.set(item_id, "full_path")
                except Exception:
                    file_path = None
            _append_existing_file_path(paths, seen_paths, file_path)

    if paths:
        return paths

    section_tree = getattr(code_view, "section_tree", None)
    if section_tree:
        for item_id in _iter_tree_items(section_tree):
            _append_section_tree_item_files(paths, seen_paths, code_view, item_id)

    return paths


def _structure_similarity(left, right):
    left_header = _normalize_for_similarity(left.header)
    right_header = _normalize_for_similarity(right.header)
    left_body = _normalize_for_similarity(left.text)
    right_body = _normalize_for_similarity(right.text)
    header_score = difflib.SequenceMatcher(None, left_header, right_header).ratio()
    body_score = difflib.SequenceMatcher(None, left_body, right_body).ratio()
    score = (header_score * 0.68) + (body_score * 0.32)
    return score, header_score, body_score


def _load_project_structures(code_files):
    project_structures = []
    for file_path in code_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
        except Exception as exc:
            logging.info(f"Clever SUS: No se pudo leer {file_path}: {exc}")
            continue
        project_structures.extend(extract_code_structures(
            content,
            file_path=file_path,
            limit=_MAX_PROJECT_STRUCTURES_PER_FILE,
        ))
    return project_structures


def _find_best_match(clipboard_structure, project_structures):
    best = None
    for project_structure in project_structures:
        score, header_score, body_score = _structure_similarity(clipboard_structure, project_structure)
        if best is None or score > best.score:
            best = StructureMatch(
                clipboard_structure=clipboard_structure,
                project_structure=project_structure,
                score=score,
                header_score=header_score,
                body_score=body_score,
            )
    return best


def _short_path(file_path):
    try:
        return f"{os.path.basename(os.path.dirname(file_path))}/{os.path.basename(file_path)}"
    except Exception:
        return file_path or "(sin archivo)"


def _apply_structure_replacement(match, new_structure_text):
    project_structure = match.project_structure
    file_path = project_structure.file_path
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            content = _normalize_text(handle.read())

        current_slice = content[project_structure.start:project_structure.end]
        if current_slice != project_structure.text:
            refreshed = extract_code_structures(content, file_path=file_path)
            refreshed_match = None
            best_score = 0
            for candidate in refreshed:
                score, _, _ = _structure_similarity(project_structure, candidate)
                if score > best_score:
                    best_score = score
                    refreshed_match = candidate
            if refreshed_match and best_score >= 0.92:
                project_structure = refreshed_match
            else:
                messagebox.showerror(
                    "Inyeccion inteligente",
                    "La estructura del proyecto cambió desde que se abrió la ventana. Cancela y vuelve a lanzar la búsqueda.",
                )
                return False

        final_content = (
            content[:project_structure.start]
            + new_structure_text
            + content[project_structure.end:]
        )
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(final_content)
        return True
    except Exception as exc:
        logging.error(f"Clever SUS: Error escribiendo archivo: {exc}")
        messagebox.showerror("Inyeccion inteligente", f"No se pudo sustituir la estructura: {exc}")
        return False


def _refresh_app_after_write(app_instance, file_path):
    if not app_instance:
        return
    try:
        if hasattr(app_instance, "controller"):
            app_instance.controller.refresh_cached_file_content(file_path)
    except Exception:
        pass
    try:
        code_view = getattr(getattr(app_instance, "layout", None), "code_view", None)
        if code_view and hasattr(code_view, "refresh_file_list"):
            code_view.refresh_file_list()
    except Exception:
        pass


def _show_structure_popup(match, app_instance=None, on_done=None):
    global _ACTIVE_CLEVER_POPUP

    project_structure = match.project_structure
    clipboard_structure = match.clipboard_structure
    file_path = project_structure.file_path

    popup = tk.Toplevel(getattr(app_instance, "root", None))
    _ACTIVE_CLEVER_POPUP = popup
    popup.title(f"Inyeccion inteligente - {_short_path(file_path)}")
    popup.configure(bg=THEME["bg"])
    popup.minsize(900, 560)

    width = min(max(int(popup.winfo_screenwidth() * 0.82), 900), popup.winfo_screenwidth())
    height = min(max(int(popup.winfo_screenheight() * 0.78), 560), popup.winfo_screenheight())
    x = max((popup.winfo_screenwidth() - width) // 2, 0)
    y = max((popup.winfo_screenheight() - height) // 3, 0)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    header_frame = tk.Frame(popup, bg=THEME["bg"])
    header_frame.pack(fill="x", padx=12, pady=(12, 4))

    title = (
        f"Archivo: {_short_path(file_path)} | Linea aprox: {project_structure.line_num} | "
        f"Similitud: {match.score:.0%} | Cabecera: {match.header_score:.0%}"
    )
    tk.Label(
        header_frame,
        text=title,
        font=(Styles.FONT_FAMILY, 13, "bold"),
        fg="#9cdcfe",
        bg=THEME["bg"],
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        header_frame,
        text=f"Cabecera detectada: {project_structure.header}",
        font=(Styles.FONT_FAMILY, 11),
        fg="#ce9178",
        bg=THEME["bg"],
        anchor="w",
    ).pack(fill="x", pady=(4, 0))

    content_frame = tk.Frame(popup, bg=THEME["bg"])
    content_frame.pack(fill="both", expand=True, padx=12, pady=8)
    content_frame.columnconfigure(0, weight=1)
    content_frame.columnconfigure(1, weight=1)
    content_frame.rowconfigure(1, weight=1)

    tk.Label(
        content_frame,
        text="Portapapeles",
        font=FONT_UI,
        fg="#ce9178",
        bg=THEME["bg"],
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    tk.Label(
        content_frame,
        text="Proyecto: estructura mas similar",
        font=FONT_UI,
        fg="#dcdcaa",
        bg=THEME["bg"],
        anchor="w",
    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    txt_clip = create_styled_text_widget(content_frame, editable=False)
    txt_project = create_styled_text_widget(content_frame, editable=False)
    txt_clip.insert("1.0", clipboard_structure.text)
    txt_project.insert("1.0", project_structure.text)
    highlight_syntax(txt_clip, file_path)
    highlight_syntax(txt_project, file_path)
    txt_clip.config(state="disabled")
    txt_project.config(state="disabled")
    txt_clip.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(4, 0))
    txt_project.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(4, 0))

    scroll_clip = ttk.Scrollbar(content_frame, orient="vertical", command=txt_clip.yview)
    scroll_project = ttk.Scrollbar(content_frame, orient="vertical", command=txt_project.yview)
    txt_clip.config(yscrollcommand=scroll_clip.set)
    txt_project.config(yscrollcommand=scroll_project.set)
    scroll_clip.grid(row=1, column=0, sticky="nse", pady=(4, 0))
    scroll_project.grid(row=1, column=1, sticky="nse", pady=(4, 0))

    button_frame = tk.Frame(popup, bg=THEME["bg"])
    button_frame.pack(fill="x", padx=12, pady=(0, 12))

    finished = {"value": False}

    def _finish():
        if finished["value"]:
            return
        finished["value"] = True
        try:
            popup.destroy()
        except Exception:
            pass
        if on_done:
            on_done()

    def _on_replace():
        new_file_content = None
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                current_content = _normalize_text(handle.read())
            new_file_content = (
                current_content[:project_structure.start]
                + clipboard_structure.text
                + current_content[project_structure.end:]
            )
        except Exception:
            new_file_content = None

        if new_file_content is not None:
            syntax_result = validate_code_syntax(new_file_content, file_path)
            if syntax_result.get("supported") and not syntax_result.get("ok"):
                proceed = messagebox.askyesno(
                    "Sintaxis invalida",
                    (
                        f"La sustitucion generaria un error de sintaxis en la linea "
                        f"{syntax_result.get('line') or 1}, columna {syntax_result.get('column') or 1}.\n\n"
                        "¿Quieres sustituir igualmente?"
                    ),
                    parent=popup,
                )
                if not proceed:
                    return

        if _apply_structure_replacement(match, clipboard_structure.text):
            _refresh_app_after_write(app_instance, file_path)
            _finish()

    tk.Button(
        button_frame,
        text="Cancelar",
        command=_finish,
        bg="#5a1d1d",
        fg="#ffb4b4",
        font=FONT_UI,
        padx=16,
        pady=4,
    ).pack(side="right", padx=(8, 0))
    tk.Button(
        button_frame,
        text="Sustituir",
        command=_on_replace,
        bg="#6a9955",
        fg="#111827",
        font=FONT_UI,
        padx=16,
        pady=4,
    ).pack(side="right")

    popup.protocol("WM_DELETE_WINDOW", _finish)
    popup.transient(getattr(app_instance, "root", None))
    popup.lift()
    popup.focus_force()


def _show_match_sequence(matches, app_instance):
    queue = list(matches)

    def _next_popup():
        if not queue:
            return
        match = queue.pop(0)
        _show_structure_popup(match, app_instance=app_instance, on_done=_next_popup)

    _next_popup()


def is_clever_injection_enabled(app_instance):
    try:
        config_manager = getattr(getattr(app_instance, "controller", None), "config_manager", None)
        return bool(config_manager and config_manager.get_clever_injection_enabled())
    except Exception:
        return False


def process_smart_paste(app_instance):
    if not is_clever_injection_enabled(app_instance):
        return False

    clipboard_text = pyperclip.paste()
    if not clipboard_text or not clipboard_text.strip():
        logging.info("Clever SUS: Portapapeles vacío.")
        return False

    clipboard_text, _ = strip_modification_comments(clipboard_text)
    clipboard_text = clipboard_text.strip()
    if not clipboard_text:
        logging.info("Clever SUS: Portapapeles vacío tras limpiar comentarios [MODIFICACIÓN].")
        return False

    original_clipboard = pyperclip.paste()
    if clipboard_text != original_clipboard.strip():
        pyperclip.copy(clipboard_text)

    clipboard_structures = extract_code_structures(
        clipboard_text,
        limit=_MAX_CLIPBOARD_STRUCTURES,
        top_level_only=True,
    )
    if not clipboard_structures:
        logging.info("Clever SUS: No se detectaron estructuras en el portapapeles.")
        return False

    code_files = _get_visible_code_view_files(app_instance)
    if not code_files:
        messagebox.showwarning(
            "Inyeccion inteligente",
            "No se pudieron resolver archivos objetivo para comparar estructuras.",
        )
        return True

    try:
        root = getattr(app_instance, "root", None)
        if root:
            root.config(cursor="watch")
            root.update()
        project_structures = _load_project_structures(code_files)
    finally:
        root = getattr(app_instance, "root", None)
        if root:
            root.config(cursor="")

    if not project_structures:
        messagebox.showinfo(
            "Inyeccion inteligente",
            "No se detectaron estructuras comparables en los archivos objetivo.",
        )
        return True

    matches = []
    for clipboard_structure in clipboard_structures:
        match = _find_best_match(clipboard_structure, project_structures)
        if match:
            matches.append(match)

    if not matches:
        return False

    logging.info(f"Clever SUS: Abriendo {len(matches)} comparacion(es) de estructura.")
    _show_match_sequence(matches, app_instance)
    return True
