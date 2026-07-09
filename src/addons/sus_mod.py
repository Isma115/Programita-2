import difflib
import os
import re
from tkinter import messagebox

from src.logic.controller import strip_modification_comments


MOD_MARKER_RE = re.compile(r"\[modificaci[oó]n\]", re.IGNORECASE)


def is_sus_mod_enabled(app_instance):
    config = getattr(getattr(app_instance, "controller", None), "config_manager", None)
    if config is None:
        return False
    return bool(config.get_sus_mod_enabled())


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
    stripped = re.sub(r"^<!--\s*", "", stripped).strip()
    stripped = re.sub(r"\s*-->\s*$", "", stripped).strip()

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


def _extract_fenced_code_blocks(text):
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    blocks = []
    in_fence = False
    current = []
    prefix_lines = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                blocks.append({
                    "prefix": "".join(prefix_lines[-3:]),
                    "content": "".join(current),
                })
                current = []
                prefix_lines = []
                in_fence = False
            else:
                in_fence = True
                current = []
            continue

        if in_fence:
            current.append(line)
        else:
            prefix_lines.append(line)
            prefix_lines = prefix_lines[-3:]

    if in_fence and current:
        blocks.append({
            "prefix": "".join(prefix_lines[-3:]),
            "content": "".join(current),
        })

    return blocks


def _split_content_by_file_markers(content, inherited_hint=None):
    blocks = []
    current_hint = inherited_hint
    current_lines = []

    for line in str(content or "").splitlines(keepends=True):
        file_hint = _extract_file_marker(line)
        if file_hint:
            if "".join(current_lines).strip():
                blocks.append({"file_hint": current_hint, "content": "".join(current_lines)})
            current_hint = file_hint
            current_lines = []
            continue
        current_lines.append(line)

    if "".join(current_lines).strip():
        blocks.append({"file_hint": current_hint, "content": "".join(current_lines)})

    return blocks


def parse_sus_mod_blocks(text):
    fenced_blocks = _extract_fenced_code_blocks(text)
    if fenced_blocks:
        raw_blocks = fenced_blocks
    else:
        raw_blocks = [{"prefix": "", "content": str(text or "")}]

    blocks = []
    for raw_block in raw_blocks:
        inherited_hint = None
        for prefix_line in raw_block.get("prefix", "").splitlines():
            inherited_hint = _extract_file_marker(prefix_line) or inherited_hint
        blocks.extend(_split_content_by_file_markers(raw_block.get("content", ""), inherited_hint))

    return [
        block for block in blocks
        if MOD_MARKER_RE.search(block.get("content") or "")
    ]


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
            for file_info in project_files:
                if os.path.normpath(str(file_info.get("path") or "")) == normalized:
                    return file_info

    normalized_hint = clean_hint.replace("\\", "/").lower()
    matches = []
    for file_info in project_files:
        rel_path = str(file_info.get("rel_path") or "").replace("\\", "/").lower()
        abs_path = str(file_info.get("path") or "").replace("\\", "/").lower()
        basename = os.path.basename(rel_path)
        if normalized_hint == rel_path or abs_path.endswith("/" + normalized_hint) or normalized_hint == basename:
            matches.append(file_info)

    return matches[0] if len(matches) == 1 else None


def _normalize_line(line):
    return re.sub(r"\s+", " ", str(line or "").strip())


def _is_significant_line(normalized_line):
    if len(normalized_line) < 2:
        return False
    return bool(re.search(r"[A-Za-z0-9_)\]}\"']", normalized_line))


def _trim_outer_blank_lines(lines, marker_indices):
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1

    trimmed = lines[start:end]
    trimmed_markers = [idx - start for idx in marker_indices if start <= idx < end]
    return trimmed, trimmed_markers


def _line_index_to_offset(lines, line_index):
    return sum(len(line) for line in lines[:line_index])


def _build_match_pairs(snippet_norm, file_norm):
    matcher = difflib.SequenceMatcher(None, snippet_norm, file_norm, autojunk=False)
    pairs = []
    for block in matcher.get_matching_blocks():
        if block.size <= 0:
            continue
        for offset in range(block.size):
            snippet_index = block.a + offset
            file_index = block.b + offset
            normalized = snippet_norm[snippet_index]
            if _is_significant_line(normalized):
                pairs.append((snippet_index, file_index, normalized))
    return pairs


def _select_replacement_span(match_pairs, marker_indices, snippet_line_count):
    if not match_pairs or not marker_indices:
        return None

    first_marker = min(marker_indices)
    last_marker = max(marker_indices)
    before = [pair for pair in match_pairs if pair[0] <= first_marker]
    after = [pair for pair in match_pairs if pair[0] >= last_marker]

    if before:
        start_pair = max(before, key=lambda pair: pair[0])
        snippet_start = start_pair[0]
        file_start = start_pair[1]
    else:
        start_pair = min(match_pairs, key=lambda pair: abs(pair[0] - first_marker))
        snippet_start = 0 if start_pair[0] >= first_marker else start_pair[0]
        file_start = start_pair[1] if start_pair[0] >= first_marker else start_pair[1]

    if after:
        end_pair = min(after, key=lambda pair: pair[0])
        snippet_end = end_pair[0] + 1
        file_end = end_pair[1] + 1
    else:
        end_pair = max(match_pairs, key=lambda pair: pair[0])
        snippet_end = snippet_line_count
        file_end = end_pair[1] + 1

    if snippet_start >= snippet_end or file_start >= file_end:
        return None

    return snippet_start, snippet_end, file_start, file_end


def _build_candidate(block, file_info, require_two_anchors):
    raw_lines = str(block.get("content") or "").splitlines(keepends=True)
    marker_indices = [idx for idx, line in enumerate(raw_lines) if MOD_MARKER_RE.search(line)]
    if not marker_indices:
        return None

    cleaned_text, removed_count = strip_modification_comments("".join(raw_lines))
    if removed_count <= 0:
        return None

    snippet_lines = cleaned_text.splitlines(keepends=True)
    snippet_lines, marker_indices = _trim_outer_blank_lines(snippet_lines, marker_indices)
    if not snippet_lines or not marker_indices:
        return None

    file_content = file_info.get("content") or ""
    file_lines = file_content.splitlines(keepends=True)
    if not file_lines:
        return None

    replacement_text = "".join(snippet_lines)
    exact_start = file_content.find(replacement_text)
    if exact_start >= 0:
        return {
            "file": file_info,
            "score": 10_000 + len(replacement_text),
            "already_applied": True,
            "target_start": exact_start,
            "target_end": exact_start + len(replacement_text),
            "replacement_text": replacement_text,
            "anchor_count": len([line for line in snippet_lines if _is_significant_line(_normalize_line(line))]),
        }

    snippet_norm = [_normalize_line(line) for line in snippet_lines]
    file_norm = [_normalize_line(line) for line in file_lines]
    match_pairs = _build_match_pairs(snippet_norm, file_norm)
    span = _select_replacement_span(match_pairs, marker_indices, len(snippet_lines))
    if span is None:
        return None

    snippet_start, snippet_end, file_start, file_end = span
    selected_pairs = [
        pair for pair in match_pairs
        if snippet_start <= pair[0] < snippet_end and file_start <= pair[1] < file_end
    ]
    anchor_count = len(selected_pairs)
    if require_two_anchors and anchor_count < 2:
        return None
    if not require_two_anchors and anchor_count < 1:
        return None

    target_start = _line_index_to_offset(file_lines, file_start)
    target_end = _line_index_to_offset(file_lines, file_end)
    replacement_text = "".join(snippet_lines[snippet_start:snippet_end])
    target_text = file_content[target_start:target_end]
    score = anchor_count * 100 + sum(len(pair[2]) for pair in selected_pairs)

    return {
        "file": file_info,
        "score": score,
        "already_applied": target_text == replacement_text,
        "target_start": target_start,
        "target_end": target_end,
        "replacement_text": replacement_text,
        "anchor_count": anchor_count,
    }


def _write_candidate(app_instance, candidate):
    file_info = candidate["file"]
    file_path = file_info.get("path")
    before = file_info.get("content") or ""
    after = (
        before[:candidate["target_start"]]
        + candidate["replacement_text"]
        + before[candidate["target_end"]:]
    )

    if candidate.get("already_applied"):
        return True, before, after

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(after)
    except Exception as exc:
        return False, before, str(exc)

    file_info["content"] = after
    controller = getattr(app_instance, "controller", None)
    if controller and hasattr(controller, "refresh_cached_file_content"):
        controller.refresh_cached_file_content(file_path, after)
    return True, before, after


def apply_sus_mod_substitutions(app_instance, clipboard_text):
    project_root = _get_project_root(app_instance)
    project_files = _get_project_files(app_instance)
    if not project_root or not project_files:
        return {"success": 0, "failed": 1, "details": ["[ERROR] No hay proyecto cargado."]}

    blocks = parse_sus_mod_blocks(clipboard_text)
    if not blocks:
        return {"success": 0, "failed": 1, "details": ["[ERROR] No se encontraron comentarios [MODIFICACIÓN] en el portapapeles."]}

    results = {"success": 0, "failed": 0, "already_applied": 0, "details": []}

    for block in blocks:
        file_hint = block.get("file_hint")
        hinted_file = _resolve_file_hint(file_hint, project_root, project_files) if file_hint else None
        candidate_files = [hinted_file] if hinted_file else project_files
        candidates = []

        for file_info in candidate_files:
            if not file_info:
                continue
            candidate = _build_candidate(
                block,
                file_info,
                require_two_anchors=not bool(file_hint),
            )
            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda item: item["score"], reverse=True)
        if not candidates:
            results["failed"] += 1
            location = file_hint or "proyecto"
            results["details"].append(f"[NO MATCH] No se pudo ubicar el bloque en {location}.")
            continue

        best = candidates[0]
        if not file_hint and len(candidates) > 1 and candidates[1]["score"] >= best["score"] * 0.9:
            results["failed"] += 1
            results["details"].append("[AMBIGUO] El bloque coincide con más de un archivo con puntuación similar.")
            continue

        ok, before, after_or_error = _write_candidate(app_instance, best)
        rel_path = best["file"].get("rel_path") or best["file"].get("path") or "archivo"
        if not ok:
            results["failed"] += 1
            results["details"].append(f"[ERROR] {rel_path}: {after_or_error}")
            continue

        if best.get("already_applied"):
            results["already_applied"] += 1
            results["details"].append(f"[YA APLICADO] {rel_path}")
        else:
            results["success"] += 1
            before_lines = len(before.splitlines())
            after_lines = len(after_or_error.splitlines())
            results["details"].append(
                f"[OK] {rel_path}: {best['anchor_count']} ancla(s), {before_lines}->{after_lines} lineas"
            )

    return results


def _refresh_code_view(app_instance):
    code_view = getattr(getattr(app_instance, "layout", None), "code_view", None)
    if code_view is not None and hasattr(code_view, "refresh_file_list"):
        code_view.refresh_file_list()


def _show_results(results):
    detail_text = "\n".join(results.get("details") or [])
    if results.get("failed"):
        messagebox.showwarning(
            "sus-mod",
            (
                "sus-mod terminó con incidencias:\n\n"
                f"  Sustituciones aplicadas: {results.get('success', 0)}\n"
                f"  Ya aplicadas: {results.get('already_applied', 0)}\n"
                f"  Fallos: {results.get('failed', 0)}\n\n"
                f"Detalle:\n{detail_text}"
            ),
        )
        return

    messagebox.showinfo(
        "sus-mod",
        (
            "sus-mod completado:\n\n"
            f"  Sustituciones aplicadas: {results.get('success', 0)}\n"
            f"  Ya aplicadas: {results.get('already_applied', 0)}\n\n"
            f"Detalle:\n{detail_text}"
        ),
    )


def process_sus_mod(app_instance):
    clipboard_text = _get_clipboard_text(app_instance)
    if not clipboard_text.strip():
        messagebox.showwarning("sus-mod", "El portapapeles está vacío.")
        return True

    results = apply_sus_mod_substitutions(app_instance, clipboard_text)
    _refresh_code_view(app_instance)
    _show_results(results)
    return True
