import logging
import os
import re
import textwrap
import tkinter as tk
from tkinter import messagebox

import pyperclip


THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
}

SECTION_HEADER_RE = re.compile(r"^[ \t]*(\[\[?[^\]\n]+\]\]?)[ \t]*$", re.MULTILINE)
DIRECT_EXPLICIT_OPENER_PATTERNS = [
    (re.compile(r"^(?:if\b.*(?:;|\s)\s*then|if\b.*\bthen\b)$", re.IGNORECASE), "shell_if"),
    (re.compile(r"^(?:for|while|until|select)\b.*(?:;|\s)\s*do$", re.IGNORECASE), "shell_loop"),
    (re.compile(r"^case\b.*\bin$", re.IGNORECASE), "shell_case"),
    (re.compile(r"^do\b$", re.IGNORECASE), "vb_do"),
    (re.compile(r"^(?:for|foreach)\b", re.IGNORECASE), "vb_for"),
    (re.compile(r"^(?:repeat)\b", re.IGNORECASE), "repeat_until"),
    (re.compile(r"^(?:local\s+)?function\b", re.IGNORECASE), "generic_end"),
    (re.compile(r"^(?:async\s+)?def\b", re.IGNORECASE), "generic_end"),
    (re.compile(r"^(?:class|module|namespace|interface|enum|struct|trait|object|impl|protocol|extension|package|library)\b", re.IGNORECASE), "generic_end"),
    (re.compile(r"^(?:sub|function|fun|procedure|proc|method|property|get|set|operator)\b", re.IGNORECASE), "generic_end"),
    (re.compile(r"^(?:begin|try|with|using|synclock|if|unless|while|until|for(?:each)?|foreach|case|match|select\s+case)\b", re.IGNORECASE), "generic_end"),
]
SHELL_HEADER_START_PATTERNS = [
    (re.compile(r"^if\b", re.IGNORECASE), "shell_if"),
    (re.compile(r"^(?:for|while|until|select)\b", re.IGNORECASE), "shell_loop"),
    (re.compile(r"^case\b", re.IGNORECASE), "shell_case"),
]


def _get_listed_code_files(app_instance):
    code_files = []

    if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
        code_view = app_instance.layout.code_view
        if hasattr(code_view, "tree"):
            for item_id in code_view.tree.get_children():
                tags = code_view.tree.item(item_id, "tags")
                if not tags:
                    continue
                file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                if file_path and os.path.exists(file_path):
                    code_files.append(file_path)

    return code_files


def _normalize_code_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _normalize_structure_header(text):
    return re.sub(r"\s+", "", (text or "").strip()).lower()


def _strip_outer_blank_lines(text):
    lines = _normalize_code_text(text).split("\n")

    while lines and not lines[0].strip():
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)


def _leading_indent(line):
    if not line:
        return ""

    match = re.match(r"[ \t]*", line)
    return match.group(0) if match else ""


def _first_non_empty_line(text):
    for line in _normalize_code_text(text).split("\n"):
        if line.strip():
            return line
    return ""


def _split_trailing_whitespace(text):
    match = re.search(r"[ \t\r\n]*\Z", text or "")
    if not match:
        return text, ""
    return text[:match.start()], text[match.start():]


def _format_replacement_block(clipboard_content, target_block):
    cleaned_block = _strip_outer_blank_lines(clipboard_content)
    if not cleaned_block.strip():
        return ""

    target_indent = _leading_indent(_first_non_empty_line(target_block))
    target_core, target_suffix = _split_trailing_whitespace(target_block)
    if not target_core.strip():
        target_suffix = ""

    dedented_block = textwrap.dedent(cleaned_block)
    formatted_lines = []
    for line in dedented_block.split("\n"):
        if line.strip():
            formatted_lines.append(f"{target_indent}{line}")
        else:
            formatted_lines.append("")

    return "\n".join(formatted_lines) + target_suffix


def _is_structure_replace_enabled(app_instance):
    try:
        if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
            code_view = app_instance.layout.code_view
            if hasattr(code_view, "var_return_structures"):
                return bool(code_view.var_return_structures.get())
    except Exception:
        pass

    try:
        if hasattr(app_instance, "controller") and hasattr(app_instance.controller, "config_manager"):
            return bool(app_instance.controller.config_manager.get_return_structures())
    except Exception:
        pass

    return False


def _indent_width(line):
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def _build_flexible_header_pattern(header_text):
    parts = []
    last_was_space = False

    for char in (header_text or "").strip():
        if char.isspace():
            if not last_was_space:
                parts.append(r"\s*")
                last_was_space = True
            continue
        parts.append(re.escape(char))
        last_was_space = False

    return "".join(parts)


def _consume_xml_token(text, start_index):
    if start_index < 0 or start_index >= len(text) or text[start_index] != "<":
        return None

    special_closers = (
        ("<!--", "-->"),
        ("<![CDATA[", "]]>"),
        ("<?", "?>"),
    )
    for prefix, closer in special_closers:
        if text.startswith(prefix, start_index):
            end_index = text.find(closer, start_index + len(prefix))
            if end_index == -1:
                return None
            return text[start_index:end_index + len(closer)], end_index + len(closer)

    if text.startswith("<!", start_index):
        end_index = text.find(">", start_index + 2)
        if end_index == -1:
            return None
        return text[start_index:end_index + 1], end_index + 1

    in_single = False
    in_double = False
    idx = start_index + 1

    while idx < len(text):
        char = text[idx]
        if char == '"' and not in_single:
            in_double = not in_double
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == ">" and not in_single and not in_double:
            return text[start_index:idx + 1], idx + 1
        idx += 1

    return None


def _iter_xml_tokens(text, search_from=0):
    idx = max(search_from, 0)

    while idx < len(text):
        lt_index = text.find("<", idx)
        if lt_index == -1:
            return

        consumed = _consume_xml_token(text, lt_index)
        if not consumed:
            idx = lt_index + 1
            continue

        token, end_index = consumed
        yield lt_index, end_index, token
        idx = end_index


def _parse_xml_tag_name(token):
    if not token or token.startswith(("<!--", "<![CDATA[", "<?", "<!")):
        return None, None

    tag_match = re.match(r"</?\s*([A-Za-z_][\w:.-]*)", token)
    if not tag_match:
        return None, None

    return tag_match.group(1), token.startswith("</")


def _find_matching_brace(text, open_index):
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    escape = False
    depth = 0
    i = open_index

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_single:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_double = False
            i += 1
            continue

        if in_backtick:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "`":
                in_backtick = False
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        if char == "'":
            in_single = True
            i += 1
            continue

        if char == '"':
            in_double = True
            i += 1
            continue

        if char == "`":
            in_backtick = True
            i += 1
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i

        i += 1

    return -1


def _find_structure_open_brace(text):
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    escape = False
    paren_depth = 0
    bracket_depth = 0
    i = 0

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_single:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_double = False
            i += 1
            continue

        if in_backtick:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "`":
                in_backtick = False
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        if char == "'":
            in_single = True
            i += 1
            continue

        if char == '"':
            in_double = True
            i += 1
            continue

        if char == "`":
            in_backtick = True
            i += 1
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
            return i

        i += 1

    return -1


def _looks_like_brace_structure_header(header_text):
    header = (header_text or "").strip()
    if not header:
        return False

    lowered = header.lower()
    keyword_prefixes = (
        "if", "else", "for", "while", "switch", "case", "try", "catch",
        "finally", "do", "function", "class", "struct", "enum",
        "interface", "namespace", "module", "sub", "macro", "impl",
        "protocol", "extension", "task", "rule"
    )
    if any(lowered.startswith(keyword) for keyword in keyword_prefixes):
        return True

    if "=>" in header:
        return True

    brace_signature_patterns = (
        r'^(?:(?:export|default|async|static|public|private|protected|internal|final|abstract|virtual|override|readonly|get|set)\s+)*'
        r'[A-Za-z_][\w<>\[\]\.:-]*\s*\([^;{}]*\)\s*(?::\s*[^{}]+)?$',
        r'^[A-Za-z_][\w.-]*\s*:\s*(?:async\s+)?(?:function\b|\([^{}]*\)\s*=>|[A-Za-z_][\w<>\[\]\.:-]*\s*\([^{}]*\))',
        r'^(?:["\'][^"\']+["\']|[A-Za-z_][\w.-]*)\s*:\s*$',
        r'^[A-Za-z_][\w.-]*\s*=\s*$',
    )
    return any(re.match(pattern, header, re.IGNORECASE) for pattern in brace_signature_patterns)


def _extract_brace_structure_from_clipboard(text):
    normalized = _normalize_code_text(text).strip()
    open_index = _find_structure_open_brace(normalized)
    if open_index == -1:
        return None

    header_text = normalized[:open_index].strip()
    if not _looks_like_brace_structure_header(header_text):
        return None

    close_index = _find_matching_brace(normalized, open_index)
    if close_index == -1:
        return None

    end_index = close_index + 1
    while end_index < len(normalized) and normalized[end_index] in " \t":
        end_index += 1
    if end_index < len(normalized) and normalized[end_index] == ";":
        end_index += 1
    while end_index < len(normalized) and normalized[end_index].isspace():
        end_index += 1

    if normalized[end_index:].strip():
        return None

    header_with_open = normalized[:open_index + 1].strip()
    if not normalized[open_index + 1:close_index].strip():
        return None

    return {
        "type": "brace",
        "header": header_with_open,
        "header_key": _normalize_structure_header(header_with_open),
    }


def _looks_like_indent_structure_header(lines):
    if not lines:
        return False

    header_text = "\n".join(line.strip() for line in lines if line.strip()).strip()
    if not header_text:
        return False

    last = lines[-1].strip()
    if last.endswith(":"):
        return True

    if re.match(r"^\[[^\]\n]+\]$", last):
        return False

    return False


def _extract_indent_structure_from_clipboard(text):
    normalized = _normalize_code_text(text).strip("\n")
    lines = normalized.split("\n")
    first_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return None

    header_lines = []
    balance = 0
    header_end_idx = None

    for idx in range(first_idx, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            if header_lines:
                header_lines.append(lines[idx])
            continue

        header_lines.append(lines[idx])
        balance += stripped.count("(") - stripped.count(")")
        balance += stripped.count("[") - stripped.count("]")
        balance += stripped.count("{") - stripped.count("}")

        if stripped.endswith(":") and balance <= 0:
            header_end_idx = idx
            break

    if header_end_idx is None or not _looks_like_indent_structure_header(header_lines):
        return None

    header_indent = _indent_width(lines[first_idx])
    body_start_idx = None
    for idx in range(header_end_idx + 1, len(lines)):
        if lines[idx].strip():
            body_start_idx = idx
            break

    if body_start_idx is None or _indent_width(lines[body_start_idx]) <= header_indent:
        return None

    end_idx = len(lines)
    for idx in range(body_start_idx + 1, len(lines)):
        if not lines[idx].strip():
            continue
        if _indent_width(lines[idx]) <= header_indent:
            end_idx = idx
            break

    block_text = "\n".join(lines[first_idx:end_idx]).strip()
    if not block_text:
        return None

    header_text = "\n".join(line.strip() for line in header_lines if line.strip()).strip()
    return {
        "type": "indent",
        "header": header_text,
        "header_key": _normalize_structure_header(header_text),
        "header_line_count": header_text.count("\n") + 1,
    }


def _extract_section_structure_from_clipboard(text):
    normalized = _normalize_code_text(text).strip("\n")
    lines = normalized.split("\n")
    first_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return None

    header_match = SECTION_HEADER_RE.match(lines[first_idx])
    if not header_match:
        return None

    end_idx = len(lines)
    for idx in range(first_idx + 1, len(lines)):
        if SECTION_HEADER_RE.match(lines[idx]):
            end_idx = idx
            break

    if end_idx == first_idx + 1:
        return None

    header_text = lines[first_idx].strip()
    return {
        "type": "section",
        "header": header_text,
        "header_key": _normalize_structure_header(header_text),
    }


def _find_matching_xml_close(text, search_from, tag_name):
    depth = 1

    for _, end_index, token in _iter_xml_tokens(text, search_from):
        tag_name_match, is_closing = _parse_xml_tag_name(token)
        if not tag_name_match:
            continue

        current_tag = tag_name_match.lower()
        if current_tag != tag_name.lower():
            continue

        if is_closing:
            depth -= 1
            if depth == 0:
                return end_index
        elif not token.rstrip().endswith("/>"):
            depth += 1

    return -1


def _extract_xml_structure_from_clipboard(text):
    normalized = _normalize_code_text(text).strip()
    if not normalized.startswith("<") or normalized.startswith("</") or normalized.startswith("<!--") or normalized.startswith("<?") or normalized.startswith("<!"):
        return None

    consumed = _consume_xml_token(normalized, 0)
    if not consumed:
        return None

    opening_tag, open_end = consumed
    tag_name, is_closing = _parse_xml_tag_name(opening_tag)
    if not tag_name or is_closing:
        return None

    if opening_tag.rstrip().endswith("/>"):
        return None

    close_end = _find_matching_xml_close(normalized, open_end, tag_name)
    if close_end == -1:
        return None

    if normalized[close_end:].strip():
        return None

    return {
        "type": "xml",
        "header": opening_tag.strip(),
        "header_key": _normalize_structure_header(opening_tag),
        "tag_name": tag_name,
    }


def _match_direct_explicit_opener(stripped_line):
    for pattern, kind in DIRECT_EXPLICIT_OPENER_PATTERNS:
        if pattern.match(stripped_line):
            return kind
    return None


def _match_pending_shell_header(lines, pending_kind):
    stripped = lines[-1].strip().lower()
    if pending_kind == "shell_if" and stripped == "then":
        return "shell_if"
    if pending_kind == "shell_loop" and stripped == "do":
        return "shell_loop"
    if pending_kind == "shell_case" and stripped == "in":
        return "shell_case"
    return None


def _next_pending_shell_kind(stripped_line):
    for pattern, kind in SHELL_HEADER_START_PATTERNS:
        if pattern.match(stripped_line):
            return kind
    return None


def _match_explicit_close_kind(stripped_line, stack_top):
    lowered = stripped_line.lower()

    if stack_top == "shell_if" and re.match(r"^fi\b", lowered):
        return True
    if stack_top == "shell_loop" and re.match(r"^done\b", lowered):
        return True
    if stack_top == "shell_case" and re.match(r"^esac\b", lowered):
        return True
    if stack_top == "repeat_until" and re.match(r"^until\b", lowered):
        return True
    if stack_top == "vb_for" and re.match(r"^next\b", lowered):
        return True
    if stack_top == "vb_do" and re.match(r"^loop\b", lowered):
        return True
    if stack_top == "generic_end" and re.match(r"^end(?:\b|\s+\w+)", lowered):
        return True

    return False


def _find_explicit_block_end(lines, header_end_idx, block_kind):
    stack = [block_kind]

    for idx in range(header_end_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue

        top = stack[-1]
        if _match_explicit_close_kind(stripped, top):
            stack.pop()
            if not stack:
                return idx
            continue

        open_kind = _match_direct_explicit_opener(stripped)
        if open_kind:
            stack.append(open_kind)

    return None


def _extract_explicit_structure_from_clipboard(text):
    normalized = _normalize_code_text(text).strip("\n")
    lines = normalized.split("\n")
    first_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return None

    header_lines = []
    balance = 0
    pending_kind = None
    block_kind = None
    header_end_idx = None

    for idx in range(first_idx, len(lines)):
        current_line = lines[idx]
        stripped = current_line.strip()
        if not stripped:
            if header_lines:
                header_lines.append(current_line)
            continue

        header_lines.append(current_line)
        balance += stripped.count("(") - stripped.count(")")
        balance += stripped.count("[") - stripped.count("]")
        balance += stripped.count("{") - stripped.count("}")

        if pending_kind:
            resolved = _match_pending_shell_header(header_lines, pending_kind)
            if resolved and balance <= 0:
                block_kind = resolved
                header_end_idx = idx
                break

        direct_kind = _match_direct_explicit_opener(stripped)
        if direct_kind and balance <= 0:
            block_kind = direct_kind
            header_end_idx = idx
            break

        if pending_kind is None:
            pending_kind = _next_pending_shell_kind(stripped)

    if not block_kind or header_end_idx is None:
        return None

    end_idx = _find_explicit_block_end(lines, header_end_idx, block_kind)
    if end_idx is None:
        return None

    if "\n".join(lines[end_idx + 1:]).strip():
        return None

    header_text = "\n".join(line.strip() for line in header_lines if line.strip()).strip()
    return {
        "type": "explicit",
        "header": header_text,
        "header_key": _normalize_structure_header(header_text),
        "header_line_count": header_text.count("\n") + 1,
        "block_kind": block_kind,
    }


def detect_code_structure(text):
    normalized = _normalize_code_text(text)
    if not normalized.strip():
        return None

    extractors = (
        _extract_xml_structure_from_clipboard,
        _extract_brace_structure_from_clipboard,
        _extract_indent_structure_from_clipboard,
        _extract_explicit_structure_from_clipboard,
        _extract_section_structure_from_clipboard,
    )

    for extractor in extractors:
        structure = extractor(normalized)
        if structure:
            return structure

    return None


def _find_indent_block_span(content, start_idx, header_line_count):
    lines = content.splitlines(True)
    if not lines:
        return None

    line_starts = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line)

    start_line_idx = 0
    for idx, line_start in enumerate(line_starts):
        if line_start > start_idx:
            break
        start_line_idx = idx

    header_end_idx = start_line_idx + max(header_line_count - 1, 0)
    if header_end_idx >= len(lines):
        return None

    header_indent = _indent_width(lines[start_line_idx])
    body_start_idx = None
    for idx in range(header_end_idx + 1, len(lines)):
        if lines[idx].strip():
            body_start_idx = idx
            break

    if body_start_idx is None or _indent_width(lines[body_start_idx]) <= header_indent:
        return None

    end_line_idx = len(lines)
    for idx in range(body_start_idx + 1, len(lines)):
        if not lines[idx].strip():
            continue
        if _indent_width(lines[idx]) <= header_indent:
            end_line_idx = idx
            break

    block_end = line_starts[end_line_idx] if end_line_idx < len(lines) else len(content)
    return start_idx, block_end


def _find_explicit_block_span(content, start_idx, structure_info):
    lines = content.splitlines(True)
    if not lines:
        return None

    line_starts = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line)

    start_line_idx = 0
    for idx, line_start in enumerate(line_starts):
        if line_start > start_idx:
            break
        start_line_idx = idx

    header_end_idx = start_line_idx + max(structure_info["header_line_count"] - 1, 0) - 1
    if header_end_idx < start_line_idx:
        header_end_idx = start_line_idx
    if header_end_idx >= len(lines):
        return None

    end_line_idx = _find_explicit_block_end(lines, header_end_idx, structure_info["block_kind"])
    if end_line_idx is None:
        return None

    end_idx = sum(len(line) for line in lines[:end_line_idx + 1])
    return start_idx, end_idx


def _find_xml_block_span(content, start_idx, tag_name):
    open_start = None
    open_end = None

    for token_start, token_end, token in _iter_xml_tokens(content, start_idx):
        current_tag, is_closing = _parse_xml_tag_name(token)
        if not current_tag or is_closing:
            continue
        if current_tag.lower() != tag_name.lower():
            continue
        open_start = token_start
        open_end = token_end
        break

    if open_start is None or open_end is None:
        return None

    close_end = _find_matching_xml_close(content, open_end, tag_name)
    if close_end == -1:
        return None

    return open_start, close_end


def _find_section_block_span(content, start_idx):
    lines = content.splitlines(True)
    if not lines:
        return None

    line_starts = []
    offset = 0
    for line in lines:
        line_starts.append(offset)
        offset += len(line)

    start_line_idx = 0
    for idx, line_start in enumerate(line_starts):
        if line_start > start_idx:
            break
        start_line_idx = idx

    end_line_idx = len(lines)
    for idx in range(start_line_idx + 1, len(lines)):
        if SECTION_HEADER_RE.match(lines[idx]):
            end_line_idx = idx
            break

    if end_line_idx == start_line_idx + 1:
        return None

    end_idx = line_starts[end_line_idx] if end_line_idx < len(lines) else len(content)
    return start_idx, end_idx


def _find_matching_structures_in_file(file_path, structure_info):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = _normalize_code_text(fh.read())
    except Exception as e:
        logging.error(f"Structure Replace: Error leyendo {file_path}: {e}")
        return []

    pattern = _build_flexible_header_pattern(structure_info["header"])
    if not pattern:
        return []

    regex = re.compile(rf"(?m)^[ \t]*{pattern}")
    results = []
    seen = set()

    for match in regex.finditer(content):
        start_idx = match.start()

        if structure_info["type"] == "brace":
            open_idx = content.find("{", match.start(), match.end())
            if open_idx == -1:
                continue
            close_idx = _find_matching_brace(content, open_idx)
            if close_idx == -1:
                continue
            end_idx = close_idx + 1
            while end_idx < len(content) and content[end_idx] in " \t":
                end_idx += 1
            if end_idx < len(content) and content[end_idx] == ";":
                end_idx += 1
        elif structure_info["type"] == "indent":
            span = _find_indent_block_span(content, start_idx, structure_info["header_line_count"])
            if not span:
                continue
            _, end_idx = span
        elif structure_info["type"] == "explicit":
            span = _find_explicit_block_span(content, start_idx, structure_info)
            if not span:
                continue
            _, end_idx = span
        elif structure_info["type"] == "xml":
            span = _find_xml_block_span(content, start_idx, structure_info["tag_name"])
            if not span:
                continue
            start_idx, end_idx = span
        else:
            span = _find_section_block_span(content, start_idx)
            if not span:
                continue
            _, end_idx = span

        key = (start_idx, end_idx)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "file_path": file_path,
            "header": match.group(0).strip(),
            "header_key": _normalize_structure_header(match.group(0)),
            "start_idx": start_idx,
            "end_idx": end_idx,
            "line_num": content[:start_idx].count("\n") + 1,
        })

    return results


def find_unique_code_structure_match(file_list, structure_info):
    matches = []
    for file_path in file_list:
        for match in _find_matching_structures_in_file(file_path, structure_info):
            if match["header_key"] == structure_info["header_key"]:
                matches.append(match)
    return matches


def _show_structure_replace_dialog(header_text, file_path):
    result = {"value": False}
    dialog = tk.Toplevel()
    dialog.title("Coincidencia de estructura detectada")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.focus_force()

    w = 780
    h = 360
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(dialog, bg=THEME["bg"], padx=22, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Se ha encontrado una unica estructura con la misma cabecera dentro de la lista de ficheros de Codigo.",
        bg=THEME["bg"],
        fg=THEME["fg"],
        font=("Segoe UI", 12),
        wraplength=720,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 14))

    tk.Label(
        frame,
        text="Fichero coincidente:",
        bg=THEME["bg"],
        fg="#569cd6",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).pack(fill="x")

    file_box = tk.Text(frame, height=2, bg="#252526", fg="#ce9178", font=("Menlo", 12), relief="flat", wrap="word")
    file_box.insert("1.0", file_path)
    file_box.config(state="disabled")
    file_box.pack(fill="x", pady=(4, 14))

    tk.Label(
        frame,
        text="Cabecera coincidente:",
        bg=THEME["bg"],
        fg="#569cd6",
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).pack(fill="x")

    header_box = tk.Text(frame, height=6, bg="#1f2430", fg="#dcdcaa", font=("Menlo", 12), relief="flat", wrap="word")
    header_box.insert("1.0", header_text)
    header_box.config(state="disabled")
    header_box.pack(fill="both", expand=True, pady=(4, 16))

    btn_frame = tk.Frame(frame, bg=THEME["bg"])
    btn_frame.pack(fill="x")

    def on_yes():
        result["value"] = True
        dialog.destroy()

    def on_no():
        dialog.destroy()

    tk.Button(
        btn_frame,
        text="Si, sustituir",
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


def _apply_structure_replacement(app_instance, structure_match, clipboard_content):
    try:
        with open(structure_match["file_path"], "r", encoding="utf-8", errors="ignore") as fh:
            current_content = _normalize_code_text(fh.read())
    except Exception as e:
        messagebox.showerror("Smart Paste", f"No se pudo leer el fichero destino:\n{e}")
        return False

    target_block = current_content[structure_match["start_idx"]:structure_match["end_idx"]]
    new_block = _format_replacement_block(clipboard_content, target_block)
    if not new_block:
        messagebox.showwarning(
            "Smart Paste",
            "El bloque del portapapeles está vacío o no contiene código utilizable."
        )
        return False

    final_content = (
        current_content[:structure_match["start_idx"]]
        + new_block
        + current_content[structure_match["end_idx"]:]
    )

    try:
        with open(structure_match["file_path"], "w", encoding="utf-8") as fh:
            fh.write(final_content)
    except Exception as e:
        messagebox.showerror("Smart Paste", f"No se pudo guardar el fichero:\n{e}")
        return False

    if hasattr(app_instance, "controller"):
        app_instance.controller.refresh_cached_file_content(structure_match["file_path"], final_content)
    if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
        app_instance.layout.code_view.refresh_file_list()

    return True


def process_structure_header_replace(app_instance):
    if not _is_structure_replace_enabled(app_instance):
        return False

    clipboard_text = pyperclip.paste()
    if not clipboard_text:
        return False

    structure_info = detect_code_structure(clipboard_text)
    if not structure_info:
        return False

    code_files = _get_listed_code_files(app_instance)
    if not code_files:
        messagebox.showwarning(
            "Smart Paste",
            "No hay archivos visibles en la seccion de Codigo para buscar la estructura."
        )
        return False

    matches = find_unique_code_structure_match(code_files, structure_info)
    if len(matches) == 0:
        return False

    if len(matches) > 1:
        messagebox.showwarning(
            "Smart Paste",
            "Se han encontrado varias estructuras con la misma cabecera en la lista de Codigo. No se realizara la sustitucion automatica."
        )
        return True

    match = matches[0]
    logging.info(
        f"Structure Replace: Coincidencia unica en {os.path.basename(match['file_path'])}:{match['line_num']}"
    )
    if _show_structure_replace_dialog(match["header"], match["file_path"]):
        _apply_structure_replacement(app_instance, match, clipboard_text)

    return True
