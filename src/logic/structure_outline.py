import os
import re
import textwrap

from src.addons.structure_header_replace import detect_code_structure


GENERIC_MARKUP_TAGS = {
    "article", "aside", "body", "col", "colgroup", "dd", "div", "dl", "dt",
    "footer", "header", "html", "li", "main", "nav", "ol", "p", "section",
    "span", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul"
}

DESCRIPTIVE_MARKUP_ATTRIBUTES = {
    "id", "class", "name", "role", "href", "src", "alt", "title",
    "type", "for", "key", "slot", "label"
}

HOOK_CALL_RE = re.compile(r"^(?:React\.)?(?:useEffect|useLayoutEffect|useMemo|useCallback)\s*\(")
VIEW_HEADER_RE = re.compile(r"^\s*(?:return\s*\(\s*)?<[/A-Za-z][^>]*>\s*\)?\s*$", re.IGNORECASE)
VIEW_ATTRIBUTE_RE = re.compile(
    r"\b(?:className|class|style|sx|variant|xmlns|fill|stroke|viewBox|onClick|onChange|v-if|v-for|ng-if)\s*=",
    re.IGNORECASE
)
BACKEND_SQL_RE = re.compile(
    r"\b(select|insert|update|delete|upsert|merge|truncate|replace|from|join|where|having|group\s+by|order\s+by)\b",
    re.IGNORECASE
)
BACKEND_TECH_RE = re.compile(
    r"\b(sql|sequelize|typeorm|prisma|mongoose|knex|supabase|firestore|mongodb|postgres(?:ql)?|mysql|sqlite|mariadb|oracle|redis|database|repository|dao|entity|schema|migration)\b",
    re.IGNORECASE
)

PURE_VIEW_FILE_EXTENSIONS = {
    ".css", ".scss", ".sass", ".less", ".styl", ".pcss",
    ".html", ".htm", ".xhtml", ".xml", ".svg", ".vue",
}
BACKEND_FILE_EXTENSIONS = {".sql", ".prisma"}
VIEW_PATH_HINTS = (
    "/view/", "/views/", "/component/", "/components/", "/page/", "/pages/",
    "/layout/", "/layouts/", "/template/", "/templates/", "/style/", "/styles/",
    "/css/", "/scss/", "/sass/", "/less/", "/ui/",
)
BACKEND_PATH_HINTS = (
    "/backend/", "/server/", "/api/", "/apis/", "/repository/", "/repositories/",
    "/dao/", "/dal/", "/db/", "/database/", "/model/", "/models/", "/schema/",
    "/schemas/", "/entity/", "/entities/", "/migration/", "/migrations/",
    "/seed/", "/seeds/",
)


def get_selected_section_file_infos(controller, section_name, subsection_name=None):
    """Returns cached file payloads for the requested section scope."""
    if subsection_name:
        file_paths = controller.section_manager.get_files_in_subsection(section_name, subsection_name)
    else:
        file_paths = controller.section_manager.get_files_in_section(section_name)

    project_manager = getattr(controller, "project_manager", None)
    cached_files = {}
    if project_manager:
        cached_files = {item.get("path"): item for item in project_manager.get_files()}

    file_infos = []
    for file_path in file_paths:
        if file_path in cached_files:
            file_infos.append(cached_files[file_path])
            continue

        if not os.path.isfile(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue

        project_root = getattr(project_manager, "current_project_path", None) if project_manager else None
        if project_root:
            try:
                rel_path = os.path.relpath(file_path, project_root)
            except ValueError:
                rel_path = os.path.basename(file_path)
        else:
            rel_path = os.path.basename(file_path)

        file_infos.append({
            "path": file_path,
            "rel_path": rel_path,
            "content": content,
        })

    return file_infos


def get_structures_for_files(controller, file_infos):
    """Extracts structures for the provided file list."""
    file_paths = [item["path"] for item in file_infos if item.get("path")]
    if not file_paths:
        return []
    return controller.project_manager.extract_functions(file_paths=file_paths)


def build_outline_forest(file_infos, structures):
    """Builds a per-file hierarchy of simplified structures."""
    ordered_files = [item for item in file_infos if item.get("path")]
    structures_by_path = {}
    for item in structures or []:
        file_with_line = item.get("path", "")
        file_path = file_with_line.split(":", 1)[0] if ":" in file_with_line else file_with_line
        structures_by_path.setdefault(file_path, []).append(item)

    forest = []
    for file_info in ordered_files:
        file_path = file_info.get("path")
        roots, normalized_items = _build_file_tree_nodes(structures_by_path.get(file_path, []))
        forest.append({
            "file_path": file_path,
            "file_rel_path": file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo",
            "roots": roots,
            "items": normalized_items,
        })
    return forest


def get_outline_visual_role(file_rel_path, structure_node=None):
    """Classifies outline items for UI coloring."""
    normalized_path = _normalize_outline_path(file_rel_path)
    file_extension = os.path.splitext(normalized_path)[1].lower()

    if file_extension in BACKEND_FILE_EXTENSIONS:
        return "backend"

    if file_extension in PURE_VIEW_FILE_EXTENSIONS:
        return "view"

    if structure_node and _looks_like_view_structure(structure_node):
        return "view"

    if structure_node and _looks_like_backend_structure(normalized_path, structure_node):
        return "backend"

    if structure_node is None:
        if _path_has_any_hint(normalized_path, VIEW_PATH_HINTS):
            return "view"
        if _path_has_any_hint(normalized_path, BACKEND_PATH_HINTS):
            return "backend"

    return "default"


def build_simplified_outline_text(file_infos, structures):
    """Builds the simplified section text grouped by file and nested by structure."""
    forest = build_outline_forest(file_infos, structures)
    file_blocks = []
    copied_count = 0

    for file_entry in forest:
        roots = file_entry.get("roots", [])
        if not roots:
            continue

        rendered_blocks = []
        for node in roots:
            rendered_blocks.append("\n".join(_render_structure_tree_lines(node, depth=0)))

        body = "\n\n".join(rendered_blocks).strip()
        if not body:
            continue

        file_blocks.append(f"--- Archivo: {file_entry['file_rel_path']} ---\n{body}")
        copied_count += len(file_entry.get("items", []))

    if not file_blocks:
        return "", 0

    return "\n\n\n".join(file_blocks), copied_count


def build_segment_full_text(file_infos, structures, selected_keys):
    """Builds the full code text for the chosen structures, grouped by file."""
    forest = build_outline_forest(file_infos, structures)
    selected_keys = set(selected_keys or [])
    file_map = {item.get("path"): item for item in file_infos}
    file_blocks = []
    copied_count = 0

    for file_entry in forest:
        selected_roots = []
        for root in file_entry.get("roots", []):
            selected_roots.extend(_collect_topmost_selected_nodes(root, selected_keys, ancestor_selected=False))

        if not selected_roots:
            continue

        file_info = file_map.get(file_entry.get("file_path"), {})
        content = file_info.get("content", "")
        lines = content.split("\n")
        snippets = []

        for node in selected_roots:
            start_line = max(int(node.get("start_line", 1)), 1)
            end_line = max(int(node.get("end_line", start_line)), start_line)
            snippets.append("\n".join(lines[start_line - 1:end_line]).rstrip())
            copied_count += 1

        body = "\n\n".join(snippet for snippet in snippets if snippet.strip()).strip()
        if not body:
            continue

        file_blocks.append(f"--- Archivo: {file_entry['file_rel_path']} ---\n{body}")

    if not file_blocks:
        return "", 0

    return "\n\n\n".join(file_blocks), copied_count


def build_segment_full_text_from_items(file_infos, items):
    """Builds the full code text for stored segment items using their saved line ranges."""
    file_map = {item.get("path"): item for item in file_infos or [] if item.get("path")}
    seen_items = set()
    normalized_items = []

    for position, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        file_path = item.get("file_path")
        if not file_path:
            continue
        unique_key = (
            item.get("key"),
            file_path,
            int(item.get("start_line", 1) or 1),
            int(item.get("end_line", 1) or 1),
        )
        if unique_key in seen_items:
            continue
        seen_items.add(unique_key)
        normalized_item = dict(item)
        normalized_item["_input_position"] = position
        normalized_items.append(normalized_item)

    if not normalized_items:
        return "", 0

    explicit_order_available = any(item.get("order_index") is not None for item in normalized_items)
    file_index_by_path = {
        item.get("path"): index for index, item in enumerate(file_infos or []) if item.get("path")
    }

    def sort_key(entry):
        if explicit_order_available:
            try:
                order_index = int(entry.get("order_index"))
            except (TypeError, ValueError):
                order_index = entry.get("_input_position", 0)
            return (order_index, entry.get("_input_position", 0))
        return (
            file_index_by_path.get(entry.get("file_path"), 10 ** 9),
            int(entry.get("start_line", 1) or 1),
            int(entry.get("end_line", 1) or 1),
            entry.get("_input_position", 0),
        )

    ordered_items = sorted(normalized_items, key=sort_key)
    file_blocks = []
    copied_count = 0

    current_file_path = None
    current_file_rel_path = ""
    current_snippets = []

    def flush_current_file():
        nonlocal current_file_path, current_file_rel_path, current_snippets
        body = "\n\n".join(snippet for snippet in current_snippets if snippet.strip()).strip()
        if body:
            file_blocks.append(f"--- Archivo: {current_file_rel_path} ---\n{body}")
        current_file_path = None
        current_file_rel_path = ""
        current_snippets = []

    def normalize_region_snippet(snippet_text):
        snippet_lines = snippet_text.split("\n")
        if snippet_lines and _looks_like_region_start_marker(snippet_lines[0]):
            snippet_lines = snippet_lines[1:]
        if snippet_lines and _looks_like_region_end_marker(snippet_lines[-1]):
            snippet_lines = snippet_lines[:-1]
        return "\n".join(snippet_lines).strip("\n")

    for item in ordered_items:
        file_path = item.get("file_path")
        file_info = file_map.get(file_path, {})
        if not file_info:
            continue

        content = file_info.get("content", "")
        lines = content.split("\n")
        start_line = max(int(item.get("start_line", 1) or 1), 1)
        end_line = max(int(item.get("end_line", start_line) or start_line), start_line)
        snippet = "\n".join(lines[start_line - 1:end_line]).rstrip()
        if item.get("type") == "region" or str(item.get("key", "")).startswith("region::"):
            snippet = normalize_region_snippet(snippet)
        if not snippet.strip():
            continue

        file_rel_path = file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo"
        if current_file_path != file_path and current_snippets:
            flush_current_file()
        if current_file_path != file_path:
            current_file_path = file_path
            current_file_rel_path = file_rel_path
        current_snippets.append(snippet)
        copied_count += 1

    if current_snippets:
        flush_current_file()

    if not file_blocks:
        return "", 0

    return "\n\n\n".join(file_blocks), copied_count


def _looks_like_region_start_marker(line_text):
    stripped = str(line_text or "").strip().lower()
    if not stripped:
        return False
    return bool(re.match(r'^(?:(?://|#|--)|/\*|<!--)\s*#?region\b', stripped))


def _looks_like_region_end_marker(line_text):
    stripped = str(line_text or "").strip().lower()
    if not stripped:
        return False
    return bool(re.match(r'^(?:(?://|#|--)|/\*|<!--)\s*#?endregion\b', stripped))


def extract_structure_header_text(structure_item):
    """Returns a normalized header/signature text for a detected structure."""
    structure_text = (structure_item or {}).get("content", "")
    if not structure_text.strip():
        return ""
    structure_type = structure_item.get("type", "")
    explicit_header = (structure_item.get("header") or "").strip()

    if explicit_header:
        return _sanitize_structure_header_text(explicit_header, structure_type)

    if _is_hook_call_structure(structure_text):
        hook_header = _extract_hook_call_header(structure_text)
        if hook_header:
            return _sanitize_structure_header_text(hook_header, structure_type)

    detected = detect_code_structure(structure_text)
    if detected and detected.get("header"):
        return _sanitize_structure_header_text(detected["header"].strip(), structure_type)

    fallback_header = _extract_structure_header_fallback(structure_text, structure_type)
    if fallback_header:
        return _sanitize_structure_header_text(fallback_header, structure_type)

    fallback_text = (structure_item.get("display_name") or structure_item.get("name") or "").strip()
    return _sanitize_structure_header_text(fallback_text, structure_type)


def make_structure_key(file_path, structure_item):
    """Builds a stable key for a structure selection."""
    structure_id = structure_item.get("structure_id")
    if structure_id:
        return structure_id

    start_line = int(structure_item.get("start_line", 1) or 1)
    line_count = int(structure_item.get("line_count", 1) or 1)
    end_line = max(start_line, start_line + max(line_count - 1, 0))
    return f"{file_path}::{start_line}:{end_line}:{structure_item.get('type', '')}:{structure_item.get('name', '')}"


def _build_file_tree_nodes(structures):
    normalized_items = []
    seen_keys = set()

    for item in structures:
        header_text = extract_structure_header_text(item)
        if not header_text:
            continue

        file_with_line = item.get("path", "")
        file_path = file_with_line.split(":", 1)[0] if ":" in file_with_line else file_with_line
        start_line = max(int(item.get("start_line", 1) or 1), 1)
        end_line = max(start_line, start_line + max(int(item.get("line_count", 1) or 1) - 1, 0))
        unique_key = (start_line, end_line, item.get("type", ""), header_text)
        if unique_key in seen_keys:
            continue
        seen_keys.add(unique_key)
        normalized_items.append({
            "key": make_structure_key(file_path, item),
            "start_line": start_line,
            "end_line": end_line,
            "type": item.get("type", ""),
            "name": item.get("name", ""),
            "header": header_text,
            "children": [],
        })

    if not normalized_items:
        return [], []

    normalized_items.sort(key=lambda item: (item["start_line"], -item["end_line"], item["name"]))

    roots = []
    stack = []
    for node in normalized_items:
        while stack and not _structure_contains(stack[-1], node):
            stack.pop()

        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots, normalized_items


def _normalize_outline_path(file_rel_path):
    return f"/{(file_rel_path or '').replace('\\', '/').strip('/').lower()}"


def _path_has_any_hint(normalized_path, hints):
    return any(hint in normalized_path for hint in hints)


def _looks_like_view_structure(node):
    structure_type = (node.get("type", "") or "").strip().lower()
    header = (node.get("header", "") or "").strip()
    lowered_header = header.lower()

    if structure_type == "tag":
        return True
    if not header:
        return False
    if header.startswith("<") or lowered_header.startswith("return (<"):
        return True
    if VIEW_HEADER_RE.match(header):
        return True
    if "</" in header or "/>" in header:
        return True
    if VIEW_ATTRIBUTE_RE.search(header):
        return True
    return False


def _looks_like_backend_structure(normalized_path, node):
    structure_text = " ".join(
        part for part in (
            node.get("header", ""),
            node.get("name", ""),
            node.get("type", ""),
        )
        if part
    ).lower()

    if not structure_text and not normalized_path:
        return False
    if _path_has_any_hint(normalized_path, BACKEND_PATH_HINTS):
        return True
    if BACKEND_SQL_RE.search(structure_text):
        return True
    if BACKEND_TECH_RE.search(structure_text):
        return True
    return False


def _structure_contains(parent_node, child_node):
    if not parent_node or not child_node:
        return False
    if parent_node["start_line"] > child_node["start_line"]:
        return False
    if parent_node["end_line"] < child_node["end_line"]:
        return False
    if parent_node["start_line"] == child_node["start_line"] and parent_node["end_line"] == child_node["end_line"]:
        return False
    return True


def _render_structure_tree_lines(node, depth=0):
    rendered = [_indent_structure_header(node.get("header", ""), depth)]
    for child in node.get("children", []):
        rendered.extend(_render_structure_tree_lines(child, depth + 1))
    return rendered


def _indent_structure_header(header_text, depth):
    normalized = textwrap.dedent((header_text or "").strip("\n"))
    lines = normalized.split("\n")
    base_indent = "  " * max(depth, 0)
    indented_lines = []

    for idx, line in enumerate(lines):
        if not line.strip():
            indented_lines.append("")
            continue
        if idx == 0:
            indented_lines.append(f"{base_indent}{line.lstrip()}")
        else:
            indented_lines.append(f"{base_indent}{line}")

    return "\n".join(indented_lines).rstrip()


def _collect_topmost_selected_nodes(node, selected_keys, ancestor_selected=False):
    current_selected = node.get("key") in selected_keys
    if current_selected and not ancestor_selected:
        return [node]

    results = []
    for child in node.get("children", []):
        results.extend(_collect_topmost_selected_nodes(child, selected_keys, ancestor_selected or current_selected))
    return results


def _is_hook_call_structure(structure_text):
    first_line = next(
        (line.strip() for line in (structure_text or "").split("\n") if line.strip()),
        ""
    )
    return bool(HOOK_CALL_RE.match(first_line))


def _extract_hook_call_header(structure_text):
    text = (structure_text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return ""

    header_chars = []
    in_single = False
    in_double = False
    in_backtick = False
    escape = False

    for char in text:
        header_chars.append(char)

        if escape:
            escape = False
            continue

        if char == "\\" and (in_single or in_double or in_backtick):
            escape = True
            continue

        if char == "'" and not in_double and not in_backtick:
            in_single = not in_single
            continue
        if char == '"' and not in_single and not in_backtick:
            in_double = not in_double
            continue
        if char == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            continue

        if in_single or in_double or in_backtick:
            continue

        if char == "{":
            return "".join(header_chars).strip()

    return text.split("\n", 1)[0].strip()


def _sanitize_structure_header_text(header_text, structure_type):
    cleaned = (header_text or "").strip()
    if not cleaned:
        return ""

    if (structure_type or "").strip().lower() == "tag" or cleaned.startswith("<"):
        cleaned = _remove_markup_attribute(cleaned, "style")
        if _is_generic_markup_header(cleaned):
            return ""

    return cleaned.strip()


def _is_generic_markup_header(header_text):
    match = re.match(r"^<\s*([A-Za-z][\w:.-]*)\b(.*?)/?\s*>$", (header_text or "").strip(), re.DOTALL)
    if not match:
        return False

    tag_name = match.group(1)
    attributes_chunk = match.group(2) or ""
    lower_name = tag_name.lower()

    if tag_name[:1].isupper() or "-" in tag_name:
        return False

    if lower_name not in GENERIC_MARKUP_TAGS:
        return False

    if "{..." in attributes_chunk:
        return False

    attribute_names = re.findall(r"([:@A-Za-z_][\w:.-]*)\s*(?:=|\b)", attributes_chunk)
    for attr_name in attribute_names:
        normalized = attr_name.lower()
        if normalized in DESCRIPTIVE_MARKUP_ATTRIBUTES:
            return False
        if normalized.startswith("data-") or normalized.startswith("aria-"):
            return False

    return True


def _remove_markup_attribute(header_text, attribute_name):
    text = header_text or ""
    attr_name = (attribute_name or "").strip().lower()
    if not text.startswith("<") or not attr_name:
        return text

    result = []
    idx = 0
    text_length = len(text)

    while idx < text_length:
        char = text[idx]

        if not char.isspace():
            result.append(char)
            idx += 1
            continue

        whitespace_start = idx
        while idx < text_length and text[idx].isspace():
            idx += 1
        whitespace = text[whitespace_start:idx]

        name_start = idx
        while idx < text_length and (text[idx].isalnum() or text[idx] in {"_", ":", "-", "."}):
            idx += 1
        attribute = text[name_start:idx]

        if not attribute:
            result.append(whitespace)
            continue

        if attribute.lower() != attr_name:
            result.append(whitespace)
            result.append(attribute)
            continue

        while idx < text_length and text[idx].isspace():
            idx += 1

        if idx >= text_length or text[idx] != "=":
            continue

        idx += 1
        while idx < text_length and text[idx].isspace():
            idx += 1

        idx = _consume_markup_attribute_value(text, idx)

    return "".join(result)


def _consume_markup_attribute_value(text, start_idx):
    idx = start_idx
    text_length = len(text)
    if idx >= text_length:
        return idx

    opener = text[idx]
    if opener in {'"', "'"}:
        quote = opener
        idx += 1
        while idx < text_length:
            if text[idx] == "\\" and idx + 1 < text_length:
                idx += 2
                continue
            if text[idx] == quote:
                return idx + 1
            idx += 1
        return text_length

    if opener == "{":
        return _consume_jsx_expression(text, idx)

    while idx < text_length and not text[idx].isspace() and text[idx] != ">":
        idx += 1
    return idx


def _consume_jsx_expression(text, start_idx):
    idx = start_idx
    text_length = len(text)
    brace_depth = 0
    in_single = False
    in_double = False
    in_backtick = False
    escape = False

    while idx < text_length:
        char = text[idx]

        if escape:
            escape = False
            idx += 1
            continue

        if char == "\\" and (in_single or in_double or in_backtick):
            escape = True
            idx += 1
            continue

        if char == "'" and not in_double and not in_backtick:
            in_single = not in_single
            idx += 1
            continue

        if char == '"' and not in_single and not in_backtick:
            in_double = not in_double
            idx += 1
            continue

        if char == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            idx += 1
            continue

        if in_single or in_double or in_backtick:
            idx += 1
            continue

        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth <= 0:
                return idx + 1

        idx += 1

    return text_length


def _extract_structure_header_fallback(structure_text, structure_type):
    normalized = (structure_text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return ""

    if (structure_type or "").strip().lower() == "tag":
        return _extract_markup_header_fallback(normalized)

    return _extract_code_header_fallback(normalized)


def _extract_markup_header_fallback(structure_text):
    start_index = structure_text.find("<")
    if start_index == -1:
        return ""

    in_single = False
    in_double = False

    for idx in range(start_index, len(structure_text)):
        char = structure_text[idx]
        if char == '"' and not in_single:
            in_double = not in_double
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == ">" and not in_single and not in_double:
            return structure_text[start_index:idx + 1].strip()

    return ""


def _extract_code_header_fallback(structure_text):
    lines = structure_text.split("\n")
    first_content_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_content_idx is None:
        return ""

    header_lines = []
    paren_depth = 0
    bracket_depth = 0
    in_single = False
    in_double = False
    in_backtick = False
    escape = False

    for idx in range(first_content_idx, len(lines)):
        line = lines[idx].rstrip()
        stripped = line.strip()

        if not stripped:
            if header_lines:
                header_lines.append("")
            continue

        current_line = []
        for char in line:
            current_line.append(char)

            if escape:
                escape = False
                continue

            if char == "\\" and (in_single or in_double or in_backtick):
                escape = True
                continue

            if char == "'" and not in_double and not in_backtick:
                in_single = not in_single
                continue
            if char == '"' and not in_single and not in_backtick:
                in_double = not in_double
                continue
            if char == "`" and not in_single and not in_double:
                in_backtick = not in_backtick
                continue

            if in_single or in_double or in_backtick:
                continue

            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth = max(paren_depth - 1, 0)
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth = max(bracket_depth - 1, 0)
            elif char == "{" and paren_depth == 0 and bracket_depth == 0:
                current_line_text = "".join(current_line).rstrip()
                header_lines.append(current_line_text)
                return "\n".join(line for line in header_lines if line.strip()).strip()

        header_lines.append("".join(current_line).rstrip())

        if paren_depth == 0 and bracket_depth == 0:
            lowered = stripped.lower()
            if stripped.endswith(":"):
                return "\n".join(line for line in header_lines if line.strip()).strip()
            if lowered in {"do", "then", "in"}:
                return "\n".join(line for line in header_lines if line.strip()).strip()
            if lowered.endswith(" do") or lowered.endswith(" then") or lowered.endswith(" in"):
                return "\n".join(line for line in header_lines if line.strip()).strip()

    return "\n".join(line for line in header_lines if line.strip()).strip()
