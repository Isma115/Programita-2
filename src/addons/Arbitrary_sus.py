import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import os
import pyperclip
import logging
import difflib
import re
import subprocess
import shlex
import threading

from src.logic.syntax_validator import validate_code_syntax
from src.logic.controller import strip_modification_comments

# --- PYGMENTS (Syntax Highlighting profesional) ---
from pygments import lex
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.token import Token
from src.ui.styles import Styles

# --- CONFIGURACIÓN DE ESTILOS VS CODE ---
THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "cursor": "#aeafad",
    "select_bg": "#264f78",
    "line_num_fg": "#858585",
    "sidebar_bg": "#252526",
}

# --- MAPEO DE TOKENS PYGMENTS → COLORES VS CODE ---
# Replica exacta de los colores de Visual Studio Code Dark+
VSCODE_TOKEN_COLORS = {
    # Keywords (azul)
    Token.Keyword:              {"fg": "#569cd6"},
    Token.Keyword.Declaration:  {"fg": "#569cd6"},
    Token.Keyword.Namespace:    {"fg": "#c586c0"},  # import/from/export → purple
    Token.Keyword.Constant:     {"fg": "#569cd6"},  # true/false/null
    Token.Keyword.Type:         {"fg": "#4ec9b0"},  # int, float, string types → teal
    Token.Keyword.Pseudo:       {"fg": "#569cd6"},  # self, this
    Token.Keyword.Reserved:     {"fg": "#569cd6"},
    
    # Control flow (purple)
    Token.Keyword:              {"fg": "#569cd6"},
    
    # Nombres
    Token.Name:                 {"fg": "#9cdcfe"},  # variables → light blue
    Token.Name.Function:        {"fg": "#dcdcaa"},  # funciones → yellow
    Token.Name.Function.Magic:  {"fg": "#dcdcaa"},  # __init__ etc
    Token.Name.Class:           {"fg": "#4ec9b0"},  # clases → teal
    Token.Name.Decorator:       {"fg": "#dcdcaa"},  # @decorator → yellow
    Token.Name.Builtin:         {"fg": "#4ec9b0"},  # print, len, etc → teal
    Token.Name.Builtin.Pseudo:  {"fg": "#569cd6"},  # self, cls
    Token.Name.Variable:        {"fg": "#9cdcfe"},  # variables → light blue
    Token.Name.Variable.Instance: {"fg": "#9cdcfe"},
    Token.Name.Variable.Class:  {"fg": "#9cdcfe"},
    Token.Name.Variable.Global: {"fg": "#9cdcfe"},
    Token.Name.Variable.Magic:  {"fg": "#9cdcfe"},
    Token.Name.Attribute:       {"fg": "#9cdcfe"},  # obj.attr
    Token.Name.Tag:             {"fg": "#569cd6"},  # HTML/JSX tags → blue
    Token.Name.Entity:          {"fg": "#569cd6"},
    Token.Name.Label:           {"fg": "#9cdcfe"},
    Token.Name.Exception:       {"fg": "#4ec9b0"},  # Exception classes → teal
    Token.Name.Other:           {"fg": "#9cdcfe"},  # JSX component names, etc
    Token.Name.Property:        {"fg": "#9cdcfe"},  # CSS properties → light blue
    Token.Name.Namespace:       {"fg": "#4ec9b0"},
    
    # Strings (naranja)
    Token.Literal.String:           {"fg": "#ce9178"},
    Token.Literal.String.Single:    {"fg": "#ce9178"},
    Token.Literal.String.Double:    {"fg": "#ce9178"},
    Token.Literal.String.Backtick:  {"fg": "#ce9178"},  # Template literals
    Token.Literal.String.Doc:       {"fg": "#6a9955"},  # Docstrings → green
    Token.Literal.String.Escape:    {"fg": "#d7ba7d"},  # \n, \t → gold
    Token.Literal.String.Interpol:  {"fg": "#569cd6"},  # ${} → blue
    Token.Literal.String.Regex:     {"fg": "#d16969"},  # Regex → red
    Token.Literal.String.Other:     {"fg": "#ce9178"},
    Token.Literal.String.Affix:     {"fg": "#569cd6"},  # f"", b"" prefix
    Token.String:                   {"fg": "#ce9178"},
    
    # Numbers (light green)
    Token.Literal.Number:           {"fg": "#b5cea8"},
    Token.Literal.Number.Integer:   {"fg": "#b5cea8"},
    Token.Literal.Number.Float:     {"fg": "#b5cea8"},
    Token.Literal.Number.Hex:       {"fg": "#b5cea8"},
    Token.Literal.Number.Oct:       {"fg": "#b5cea8"},
    Token.Literal.Number.Bin:       {"fg": "#b5cea8"},
    Token.Number:                   {"fg": "#b5cea8"},
    
    # Comments (green)
    Token.Comment:                  {"fg": "#6a9955", "italic": True},
    Token.Comment.Single:           {"fg": "#6a9955", "italic": True},
    Token.Comment.Multiline:        {"fg": "#6a9955", "italic": True},
    Token.Comment.Special:          {"fg": "#6a9955", "italic": True},
    Token.Comment.Preproc:          {"fg": "#c586c0"},  # Preprocessor
    Token.Comment.PreprocFile:      {"fg": "#ce9178"},
    Token.Comment.Hashbang:         {"fg": "#6a9955", "italic": True},
    
    # Operators
    Token.Operator:                 {"fg": "#d4d4d4"},
    Token.Operator.Word:            {"fg": "#569cd6"},  # and, or, not → blue
    
    # Punctuation
    Token.Punctuation:              {"fg": "#d4d4d4"},
    Token.Punctuation.Marker:       {"fg": "#d4d4d4"},
    
    # CSS-specific
    Token.Name.Builtin:             {"fg": "#4ec9b0"},
    
    # Generic (diff, etc)
    Token.Generic.Inserted:         {"fg": "#b5cea8"},
    Token.Generic.Deleted:          {"fg": "#ce9178"},
    Token.Generic.Heading:          {"fg": "#569cd6", "bold": True},
    Token.Generic.Subheading:       {"fg": "#569cd6"},
    Token.Generic.Emph:             {"italic": True},
    Token.Generic.Strong:           {"bold": True},
    
    # Fallback
    Token.Text:                     {"fg": "#d4d4d4"},
    Token.Error:                    {"fg": "#f44747"},
}

# Fuente de código forzada a Menlo (estilo VS Code en Mac)
FONT_CODE_FAMILY = "Menlo"
FONT_CODE = (FONT_CODE_FAMILY, 14)
FONT_UI = (Styles.FONT_FAMILY, 14) # Aumentado tamano base a 14
_ACTIVE_ARBITRARY_POPUP = None

def _normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _clean_path_hint(text):
    cleaned = (text or "").strip()
    cleaned = cleaned.strip("`*[](){}<>")
    cleaned = cleaned.rstrip(":")
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"^(?:[ab]/)", "", cleaned)
    cleaned = re.sub(r"^\./+", "", cleaned)
    return cleaned.strip()


def _extract_explicit_file_marker(line):
    stripped = (line or "").strip()
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
            return _clean_path_hint(match.group(1))
    return None


def _unwrap_outer_fence(text):
    normalized = _normalize_text(text).strip()
    match = re.match(r"(?s)^\s*(?:```|~~~)[^\n]*\n(.*)\n\s*(?:```|~~~)\s*$", normalized)
    if match:
        return match.group(1).strip("\n")
    return text


def _extract_clipboard_file_hint(search_text):
    normalized = _normalize_text(search_text).strip()
    if not normalized:
        return None, ""

    lines = normalized.split("\n")
    for index, line in enumerate(lines[:8]):
        path_hint = _extract_explicit_file_marker(line)
        if not path_hint:
            continue

        remaining_text = "\n".join(lines[index + 1:]).strip("\n")
        cleaned_text = _unwrap_outer_fence(remaining_text).strip()
        return path_hint, cleaned_text or normalized

    return None, normalized


def _match_code_files_by_path_hint(path_hint, code_files):
    normalized_hint = _clean_path_hint(path_hint).lower()
    if not normalized_hint:
        return []

    exact_matches = [
        file_path for file_path in code_files
        if normalized_hint == file_path.replace("\\", "/").lower()
    ]
    if exact_matches:
        return exact_matches

    suffix_matches = [
        file_path for file_path in code_files
        if file_path.replace("\\", "/").lower().endswith(normalized_hint)
    ]
    if suffix_matches:
        return suffix_matches

    basename = os.path.basename(normalized_hint)
    if basename:
        basename_matches = [
            file_path for file_path in code_files
            if os.path.basename(file_path).lower() == basename
        ]
        if basename_matches:
            return basename_matches

    return []


def _should_prioritize_clipboard_file_hint(app_instance):
    return_files = False
    return_chunks = False

    try:
        if hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
            code_view = app_instance.layout.code_view
            if hasattr(code_view, "var_return_files"):
                return_files = bool(code_view.var_return_files.get())
            if hasattr(code_view, "var_return_chunks"):
                return_chunks = bool(code_view.var_return_chunks.get())
    except Exception:
        pass

    return not return_files and not return_chunks


def _get_arbitrary_search_bounds(app_instance, search_text):
    text_len = len(search_text or "")
    default_min = 10
    default_max = 30
    min_search_len = default_min
    max_search_len = min(text_len, default_max) if text_len else default_max

    try:
        config_manager = getattr(getattr(app_instance, "controller", None), "config_manager", None)
        if config_manager:
            min_search_len = max(1, int(config_manager.get_arbitrary_search_min_chars()))
            max_search_len = max(1, int(config_manager.get_arbitrary_search_max_chars()))
    except Exception:
        min_search_len = default_min
        max_search_len = default_max

    if text_len:
        min_search_len = min(min_search_len, text_len)
        max_search_len = min(max_search_len, text_len)

    if max_search_len < min_search_len:
        max_search_len = min_search_len

    return min_search_len, max_search_len


def _load_file_contents(file_list):
    """
    Carga el contenido de todos los ficheros en memoria.
    Devuelve una lista de tuplas (file_path, content).
    """
    loaded = []
    for file_info in file_list:
        if isinstance(file_info, dict):
            file_path = file_info.get('full_path')
        else:
            file_path = file_info
        if not file_path or not os.path.exists(file_path):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            loaded.append((file_path, content))
        except Exception:
            pass
    return loaded


def _normalize_for_match(text):
    """Normaliza texto para comparación difusa: colapsa espacios en blanco a uno solo."""
    return re.sub(r'\s+', ' ', text).strip()


def _compute_line_fingerprint(line):
    """Computa una huella normalizada de una línea para comparación rápida."""
    stripped = line.strip()
    if not stripped:
        return ""
    return _normalize_for_match(stripped)


def find_unique_substring(search_text, loaded_files, min_len=20, max_len=None, step=10):
    """
    Algoritmo de búsqueda por coincidencia exacta única.

    Estrategia:
    - Prueba substrings de diferentes tamaños y posiciones del texto.
    - Registra TODOS los resultados únicos encontrados.
    - Prioriza el substring con más caracteres no vacíos.
    - Si hay empate, prefiere el que tenga menos espacios en blanco.
    - Si sigue habiendo empate, prefiere el más largo.
    - Si todavía hay empate, prefiere el de mayor posición de inicio.
    - Devuelve (match_text, file_path, line_num) o (None, None, -1) si no se encuentra.

    Parámetros:
    - min_len: longitud mínima del substring a probar.
    - max_len: longitud máxima (por defecto, longitud total del texto).
    - step: incremento de tamaño entre iteraciones.
    """
    text_len = len(search_text)
    if text_len == 0:
        return None, None, -1
    if max_len is None:
        max_len = text_len

    min_len = min(min_len, text_len)
    max_len = min(max_len, text_len)
    if max_len < min_len:
        max_len = min_len

    logging.info(f"[Arbitrary] Buscando substring único. Texto: {text_len} chars, "
                 f"rango [{min_len}..{max_len}], step={step}")

    best_substring = None
    best_file_path = None
    best_line_num = -1
    best_quality = None
    best_start = -1

    for substr_len in range(max_len, min_len - 1, -step):
        if best_quality and best_quality["non_whitespace_chars"] > substr_len:
            break

        positions = set()
        positions.add(0)
        positions.add(max(0, text_len // 4 - substr_len // 2))
        positions.add(max(0, text_len // 2 - substr_len // 2))
        positions.add(max(0, 3 * text_len // 4 - substr_len // 2))
        positions.add(max(0, text_len - substr_len))

        for start in sorted(positions):
            end = start + substr_len
            if end > text_len:
                break
            substring = search_text[start:end]

            if not substring.strip():
                continue

            nw = sum(1 for c in substring if not c.isspace())
            ws = len(substring) - nw
            quality = {"non_whitespace_chars": nw, "whitespace_chars": ws, "length": len(substring)}

            matching_files = []
            for file_path, content in loaded_files:
                if substring in content:
                    matching_files.append(file_path)

            if len(matching_files) != 1:
                continue

            should_replace = False
            if best_quality is None:
                should_replace = True
            elif nw > best_quality["non_whitespace_chars"]:
                should_replace = True
            elif nw == best_quality["non_whitespace_chars"]:
                if ws < best_quality["whitespace_chars"]:
                    should_replace = True
                elif ws == best_quality["whitespace_chars"]:
                    if quality["length"] > best_quality["length"]:
                        should_replace = True
                    elif quality["length"] == best_quality["length"] and start > best_start:
                        should_replace = True

            if should_replace:
                file_path = matching_files[0]
                content = next(c for fp, c in loaded_files if fp == file_path)
                idx = content.find(substring)
                line_num = content[:idx].count('\n') + 1

                best_substring = substring
                best_file_path = file_path
                best_line_num = line_num
                best_quality = quality
                best_start = start

                logging.info(
                    f"[Arbitrary] Candidato único: útiles={nw}, len={substr_len}, "
                    f"fichero={os.path.basename(file_path)}, línea={line_num}"
                )

    if best_substring and best_file_path:
        logging.info(
            f"[Arbitrary] Mejor exacto: útiles={best_quality['non_whitespace_chars']}, "
            f"len={best_quality['length']}, fichero={os.path.basename(best_file_path)}, línea={best_line_num}"
        )
        return best_substring, best_file_path, best_line_num

    logging.info("[Arbitrary] No se encontró substring único exacto.")
    return None, None, -1


def _fuzzy_match_region(search_text, loaded_files):
    """
    Fallback difuso cuando la búsqueda exacta falla.

    Estrategia:
    1. Normaliza y compara líneas usando SequenceMatcher.
    2. Para cada fichero, encuentra el bloque contiguo de líneas con mayor similitud.
    3. Devuelve (match_text, file_path, ratio, line_num) con la mejor coincidencia.
    """

    search_lines = search_text.splitlines()
    if not search_lines:
        logging.info("[Arbitrary] Fuzzy: texto de búsqueda vacío.")
        return None, None, 0.0, -1

    search_norms = [_compute_line_fingerprint(l) for l in search_lines]
    search_norms_filtered = [n for n in search_norms if n]

    if not search_norms_filtered:
        logging.info("[Arbitrary] Fuzzy: texto de búsqueda sin contenido significativo.")
        return None, None, 0.0, -1

    best_file_path = None
    best_match_text = None
    best_ratio = 0.0
    best_line_num = 1
    best_match_start_line = 0
    best_match_end_line = 0

    MIN_RATIO_THRESHOLD = 0.25
    MAX_FILE_LINES_FOR_WINDOW = 2000
    MAX_COMPARISONS_PER_FILE = 500

    for file_path, content in loaded_files:
        file_lines = content.splitlines()
        if not file_lines:
            continue

        file_norms = [_compute_line_fingerprint(l) for l in file_lines]
        full_search_norm = "\n".join(search_norms_filtered)
        file_norms_joined = "\n".join(file_norms)

        sm = difflib.SequenceMatcher(None, full_search_norm, file_norms_joined, autojunk=False)
        longest = sm.find_longest_match(0, len(search_norms_filtered), 0, len(file_norms_joined))

        if longest.size > 3:
            partial_ratio = longest.size / max(len(search_norms_filtered), 1)
            if partial_ratio > best_ratio:
                best_ratio = partial_ratio
                best_file_path = file_path
                best_line_num = 1
                start_line = file_norms_joined[:longest.b].count("\n") if longest.b > 0 else 0
                match_in_lines = file_norms_joined[longest.b:longest.b + longest.size]
                end_line = start_line + match_in_lines.count("\n") + 1
                best_match_start_line = start_line
                best_match_end_line = end_line

        window_sizes = _compute_fuzzy_window_sizes(len(search_norms_filtered))

        file_line_limit = min(len(file_lines), MAX_FILE_LINES_FOR_WINDOW)
        step = max(1, file_line_limit // MAX_COMPARISONS_PER_FILE)

        for window_size in window_sizes:
            window_text = "\n".join(search_norms_filtered[:window_size])
            if not window_text.strip():
                continue

            for start in range(0, file_line_limit - window_size + 1, step):
                chunk = "\n".join(file_norms[start:start + window_size])
                if not chunk.strip():
                    continue

                ratio = difflib.SequenceMatcher(None, window_text, chunk, autojunk=False).ratio()

                end_line = min(start + window_size, len(file_lines))

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_file_path = file_path
                    best_match_start_line = start
                    best_match_end_line = end_line
                    best_line_num = start + 1

    if best_ratio < MIN_RATIO_THRESHOLD or best_file_path is None:
        logging.info(f"[Arbitrary] Fuzzy: mejor ratio {best_ratio:.2f} insuficiente (mínimo {MIN_RATIO_THRESHOLD}).")
        return None, None, 0.0, -1

    content = next(c for fp, c in loaded_files if fp == best_file_path)
    file_lines = content.splitlines()
    start_idx = max(0, best_match_start_line)
    end_idx = min(len(file_lines), best_match_end_line)
    if end_idx <= start_idx:
        end_idx = min(start_idx + len(search_lines), len(file_lines))
    match_text = "\n".join(file_lines[start_idx:end_idx])

    logging.info(
        f"[Arbitrary] Fuzzy: ratio={best_ratio:.2f}, "
        f"fichero={os.path.basename(best_file_path)}, "
        f"líneas={start_idx + 1}-{end_idx}"
    )

    return match_text, best_file_path, best_ratio, best_line_num


def _compute_fuzzy_window_sizes(num_search_lines):
    """Calcula tamaños de ventana para la búsqueda difusa por líneas."""
    if num_search_lines <= 0:
        return [1]
    sizes = set()
    sizes.add(num_search_lines)
    sizes.add(max(1, num_search_lines // 2))
    sizes.add(max(1, num_search_lines // 4))
    sizes.add(min(num_search_lines, 8))
    sizes.add(min(num_search_lines, 4))
    return sorted(sizes, reverse=True)


def find_similar_region(file_list, search_text, step=None, forced_file=None, min_search_len=None, max_search_len=None):
    """
    Busca la región de código con coincidencia exacta primero, luego difusa.

    1. Carga todos los ficheros en memoria.
    2. Si forced_file, filtra solo ese fichero.
    3. Intenta coincidencia exacta con find_unique_substring.
    4. Si falla, intenta coincidencia difusa por líneas con _fuzzy_match_region.
    5. Siempre devuelve la mejor coincidencia encontrada.

    Devuelve (match_text, file_path, ratio, line_num).
    ratio=1.0 para coincidencia exacta, <1.0 para difusa.
    """
    if not file_list:
        return None, None, 0, -1

    loaded_files = _load_file_contents(file_list)

    if not loaded_files:
        return None, None, 0, -1

    if forced_file:
        loaded_files = [(fp, c) for fp, c in loaded_files if fp == forced_file]
        logging.info(f"[Arbitrary] Fichero forzado: {os.path.basename(forced_file)}")

    text_len = len(search_text)
    if max_search_len is None:
        max_search_len = text_len
    if min_search_len is None:
        min_search_len = min(10, text_len) if text_len else 1
    max_search_len = min(max_search_len, text_len) if text_len else max_search_len
    min_search_len = min(min_search_len, text_len) if text_len else min_search_len
    if max_search_len < min_search_len:
        max_search_len = min_search_len
    substr_step = max(2, min(text_len // 20, 50)) if text_len else 2

    substring, file_path, line_num = find_unique_substring(
        search_text, loaded_files,
        min_len=min_search_len,
        max_len=max_search_len,
        step=substr_step
    )

    if substring and file_path:
        return substring, file_path, 1.0, line_num

    logging.info("[Arbitrary] Coincidencia exacta no encontrada, intentando búsqueda difusa...")

    match_text, fuzzy_file, fuzzy_ratio, fuzzy_line = _fuzzy_match_region(search_text, loaded_files)

    if match_text and fuzzy_file and fuzzy_ratio > 0:
        return match_text, fuzzy_file, fuzzy_ratio, fuzzy_line

    logging.info("[Arbitrary] Búsqueda difusa tampoco encontró coincidencias suficientes.")

    if loaded_files:
        best_fp = loaded_files[0][0]
        best_content = loaded_files[0][1]
        best_ratio_line = 0.0
        search_norm = _normalize_for_match(search_text)
        for fp, content in loaded_files:
            file_norm = _normalize_for_match(content)
            ratio = difflib.SequenceMatcher(None, search_norm, file_norm, autojunk=False).ratio()
            if ratio > best_ratio_line:
                best_ratio_line = ratio
                best_fp = fp
                best_content = content

        match_text = best_content
        file_path = best_fp
        line_num = 1
        ratio = best_ratio_line

        if ratio > 0.05:
            logging.info(
                f"[Arbitrary] Fallback último recurso: ratio={ratio:.2f}, "
                f"fichero={os.path.basename(file_path)}"
            )
            return match_text, file_path, ratio, line_num

    return None, None, 0, -1


def identify_best_file(file_list, search_text):
    """
    Identifica el archivo candidato usando el algoritmo de substring único.
    Devuelve (file_path, score) donde score=1.0 si hay coincidencia única, <1.0 si es difusa.
    """
    loaded_files = _load_file_contents(file_list)
    if not loaded_files:
        return None, 0

    text_len = len(search_text)
    min_len = min(20, text_len)
    substr_step = max(5, text_len // 20)

    substring, file_path, line_num = find_unique_substring(
        search_text, loaded_files,
        min_len=min_len,
        max_len=text_len,
        step=substr_step
    )

    if file_path:
        logging.info(f"[Arbitrary] Fichero identificado: {os.path.basename(file_path)} (Score: 1.0)")
        return file_path, 1.0

    match_text, fuzzy_file, fuzzy_ratio, fuzzy_line = _fuzzy_match_region(search_text, loaded_files)

    if fuzzy_file and fuzzy_ratio > 0:
        logging.info(f"[Arbitrary] Fichero identificado (fuzzy): {os.path.basename(fuzzy_file)} (Score: {fuzzy_ratio:.2f})")
        return fuzzy_file, fuzzy_ratio

    logging.info("[Arbitrary] No se pudo identificar fichero único.")
    return None, 0

_ARBITRARY_STRUCTURE_MIN_SCORE = 0.4
_ARBITRARY_MAX_CLIPBOARD_STRUCTURES = 12
_ARBITRARY_MAX_PROJECT_STRUCTURES_PER_FILE = 50


def _find_match_by_structures(search_text, code_files, min_score=_ARBITRARY_STRUCTURE_MIN_SCORE, forced_file=None):
    """
    Primera capa del algoritmo: identifica estructuras de codigo en el
    portapapeles (cabeceras de funciones, clases, bloques entre llaves,
    corchetes, componentes, etc.) y las compara con las estructuras del
    proyecto para localizar el fichero y la linea de la coincidencia mas
    probable.

    Devuelve (match_text, file_path, ratio, line_num) o (None, None, 0, -1).
    """
    try:
        from src.addons.clever_sus import (
            extract_code_structures,
            _structure_similarity,
            StructureMatch,
        )
    except ImportError:
        logging.warning("[Arbitrary] Estructuras: no se pudo importar clever_sus.")
        return None, None, 0, -1

    clipboard_structures = extract_code_structures(
        search_text,
        limit=_ARBITRARY_MAX_CLIPBOARD_STRUCTURES,
        top_level_only=True,
    )

    if not clipboard_structures:
        logging.info("[Arbitrary] Estructuras: no se detectaron estructuras en el portapapeles.")
        return None, None, 0, -1

    logging.info(f"[Arbitrary] Estructuras: {len(clipboard_structures)} estructura(es) en portapapeles.")

    loaded_files = _load_file_contents(code_files)
    if not loaded_files:
        return None, None, 0, -1

    if forced_file:
        loaded_files = [(fp, c) for fp, c in loaded_files if fp == forced_file]
        logging.info(f"[Arbitrary] Estructuras: fichero forzado {os.path.basename(forced_file)}")

    project_structures = []
    for fp, content in loaded_files:
        file_structs = extract_code_structures(
            content,
            file_path=fp,
            limit=_ARBITRARY_MAX_PROJECT_STRUCTURES_PER_FILE,
        )
        project_structures.extend(file_structs)

    if not project_structures:
        logging.info("[Arbitrary] Estructuras: no se detectaron estructuras en los archivos del proyecto.")
        return None, None, 0, -1

    logging.info(f"[Arbitrary] Estructuras: {len(project_structures)} estructura(es) en proyecto.")

    best_match = None
    best_score = 0.0

    for clip_struct in clipboard_structures:
        for proj_struct in project_structures:
            score, header_score, body_score = _structure_similarity(clip_struct, proj_struct)
            if score > best_score:
                best_score = score
                best_match = StructureMatch(
                    clipboard_structure=clip_struct,
                    project_structure=proj_struct,
                    score=score,
                    header_score=header_score,
                    body_score=body_score,
                )

    if best_match and best_score >= min_score:
        proj = best_match.project_structure
        logging.info(
            f"[Arbitrary] Estructuras: coincidencia score={best_score:.2f}, "
            f"fichero={os.path.basename(proj.file_path or '')}, "
            f"linea={proj.line_num}, cabecera='{proj.header[:80]}'"
        )
        return proj.text, proj.file_path, best_score, proj.line_num

    logging.info(
        f"[Arbitrary] Estructuras: mejor score {best_score:.2f} insuficiente (umbral {min_score})."
    )
    return None, None, 0, -1


def get_match_context(file_path, match_text, approximate_line_num):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        content_norm = content.replace("\r\n", "\n")
        match_norm = match_text.replace("\r\n", "\n")
        
        pattern = re.escape(match_norm)
        matches = list(re.finditer(pattern, content_norm))
        
        if not matches:
            clipped = match_norm[:200] if len(match_norm) > 200 else match_norm
            lines = content_norm.split('\n')
            approx_line = max(0, approximate_line_num - 1)
            approx_index = sum(len(l) + 1 for l in lines[:approx_line])
            approx_char = min(approx_index, len(content_norm))
            return content_norm, 0, len(content_norm), approx_char

        lines = content_norm.split('\n')
        approx_index = sum(len(line) + 1 for line in lines[:approximate_line_num-1])
        
        best_diff = float('inf')
        selected_match = None
        
        for m in matches:
            diff = abs(m.start() - approx_index)
            if diff < best_diff:
                best_diff = diff
                selected_match = m
        
        if not selected_match:
            return content_norm, 0, len(content_norm), 0
            
        start_idx = selected_match.start()

        return content_norm, 0, len(content_norm), start_idx

    except Exception as e:
        logging.error(f"Error obteniendo contexto: {e}")
        return None, 0, 0, 0

def apply_replacement(file_path, start_idx, end_idx, new_content):
    """(Sin cambios funcionales - escritura de archivo)"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        content_norm = content.replace("\r\n", "\n")
        
        prefix = content_norm[:start_idx]
        suffix = content_norm[end_idx:]
        
        final_content = prefix + new_content + suffix
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        logging.info(f"Archivo modificado: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error escribiendo archivo: {e}")
        messagebox.showerror("Error", f"No se pudo guardar el archivo: {e}")
        return False

# === HIGHLIGHTING LOGIC (PYGMENTS) ===

def _get_token_tag_name(token_type):
    """Convierte un tipo de token Pygments en un nombre de tag Tkinter."""
    return "PYG_" + str(token_type).replace(".", "_")

def _resolve_token_style(token_type):
    """
    Busca el estilo para un token, subiendo por la jerarquía si no hay match directo.
    Ej: Token.Keyword.Pseudo → Token.Keyword → Token → fallback
    """
    t = token_type
    while t:
        if t in VSCODE_TOKEN_COLORS:
            return VSCODE_TOKEN_COLORS[t]
        t = t.parent
    return {"fg": "#d4d4d4"}

def _get_lexer_for_file(file_path):
    """
    Obtiene el lexer Pygments adecuado para un archivo.
    Fallback a TextLexer si no se reconoce la extensión.
    """
    if not file_path:
        return TextLexer()
    try:
        return get_lexer_for_filename(file_path, stripnl=False, stripall=False)
    except Exception:
        return TextLexer()


def _apply_syntax_tokens(text_widget, content, lexer, start_line=1, start_col=0):
    """Aplica los tokens de Pygments a una región concreta del widget."""
    line = start_line
    col = start_col

    for token_type, token_value in lex(content, lexer):
        if not token_value:
            continue

        start_index = f"{line}.{col}"
        lines_in_token = token_value.split("\n")
        if len(lines_in_token) > 1:
            end_line = line + len(lines_in_token) - 1
            end_col = len(lines_in_token[-1])
        else:
            end_line = line
            end_col = col + len(token_value)

        end_index = f"{end_line}.{end_col}"

        if token_type != Token.Text and token_type != Token.Text.Whitespace:
            style = _resolve_token_style(token_type)
            if style.get("fg") and style["fg"] != "#d4d4d4":
                tag_name = _get_token_tag_name(token_type)
                if tag_name not in text_widget.tag_names():
                    config = {}
                    if "fg" in style:
                        config["foreground"] = style["fg"]
                    if style.get("bold"):
                        config["font"] = (FONT_CODE[0], FONT_CODE[1], "bold")
                    if style.get("italic"):
                        config["font"] = (FONT_CODE[0], FONT_CODE[1], "italic")
                    if style.get("bold") and style.get("italic"):
                        config["font"] = (FONT_CODE[0], FONT_CODE[1], "bold italic")
                    text_widget.tag_configure(tag_name, **config)
                text_widget.tag_add(tag_name, start_index, end_index)

        if len(lines_in_token) > 1:
            line = end_line
            col = end_col
        else:
            col = end_col


def _split_multifile_highlight_sections(content, default_file_path=None):
    """Divide previews con cabeceras de archivo para colorear cada bloque con su lexer."""
    normalized = _normalize_text(content)
    lines = normalized.split("\n")
    markers = []

    for index, line in enumerate(lines):
        path_hint = _extract_explicit_file_marker(line)
        if path_hint:
            markers.append((index, path_hint))

    if not markers:
        return [{
            "start_line": 1,
            "text": normalized,
            "file_path": default_file_path,
        }]

    sections = []
    if markers[0][0] > 0:
        leading_text = "\n".join(lines[:markers[0][0]])
        if leading_text.strip():
            sections.append({
                "start_line": 1,
                "text": leading_text,
                "file_path": default_file_path,
            })

    for idx, (marker_line, path_hint) in enumerate(markers):
        content_start = marker_line + 1
        content_end = markers[idx + 1][0] if idx + 1 < len(markers) else len(lines)
        block_text = "\n".join(lines[content_start:content_end])
        if not block_text:
            continue
        sections.append({
            "start_line": content_start + 1,
            "text": block_text,
            "file_path": path_hint or default_file_path,
        })

    return sections

def configure_tags(text_widget):
    """
    Configura los tags de colores estilo VS Code en el widget de texto.
    Crea un tag Tkinter para cada tipo de token definido en VSCODE_TOKEN_COLORS.
    """
    for token_type, style_dict in VSCODE_TOKEN_COLORS.items():
        tag_name = _get_token_tag_name(token_type)
        config = {"font": FONT_CODE}  # <-- Forzar fuente de código unificada
        if "fg" in style_dict:
            config["foreground"] = style_dict["fg"]
        if style_dict.get("bold"):
            config["font"] = (FONT_CODE[0], FONT_CODE[1], "bold")
        if style_dict.get("italic"):
            config["font"] = (FONT_CODE[0], FONT_CODE[1], "italic")
        if style_dict.get("bold") and style_dict.get("italic"):
            config["font"] = (FONT_CODE[0], FONT_CODE[1], "bold italic")
        text_widget.tag_configure(tag_name, **config)

def highlight_syntax(text_widget, file_path=None):
    """
    Aplica resaltado de sintaxis usando Pygments.
    Detecta automáticamente el lenguaje a partir de la extensión del archivo.
    Soporta: JS, JSX, CSS, Python, HTML, TS, TSX, JSON, y 500+ lenguajes más.
    """
    content = text_widget.get("1.0", "end-1c")
    if not content.strip():
        return
    
    # Limpiar tags previos de Pygments
    for tag in text_widget.tag_names():
        if tag.startswith("PYG_"):
            text_widget.tag_remove(tag, "1.0", tk.END)

    sections = _split_multifile_highlight_sections(content, default_file_path=file_path)
    for section in sections:
        section_text = section.get("text", "")
        if not section_text.strip():
            continue
        lexer = _get_lexer_for_file(section.get("file_path"))
        _apply_syntax_tokens(
            text_widget,
            section_text,
            lexer,
            start_line=section.get("start_line", 1),
            start_col=0,
        )


def create_styled_text_widget(parent, editable=True):
    """Crea un widget de texto preconfigurado con estilo VS Code"""
    txt = tk.Text(
        parent, 
        font=FONT_CODE, 
        bg=THEME["bg"], 
        fg=THEME["fg"], 
        relief="flat", 
        wrap="none",
        insertbackground=THEME["cursor"],
        selectbackground=THEME["select_bg"],
        undo=True,
        maxundo=-1,
        autoseparators=True
    )
    # Configurar tags después de crear el widget
    configure_tags(txt)
    
    # FORZAR que la fuente base se mantenga para texto sin tags
    txt.tag_configure("default", font=FONT_CODE, foreground=THEME["fg"])
    
    return txt

def show_popup(clipboard_text, match_text, file_path, ratio, line_num, app_instance=None):
    """
    Muestra popup de 3 paneles con estilo VS Code Highlighting.
    """
    global _ACTIVE_ARBITRARY_POPUP

    if not match_text:
        return

    previous_popup = None
    try:
        if _ACTIVE_ARBITRARY_POPUP and _ACTIVE_ARBITRARY_POPUP.winfo_exists():
            previous_popup = _ACTIVE_ARBITRARY_POPUP
    except Exception:
        previous_popup = None

    # Estado mutable
    state = {
        "start_idx": 0,
        "end_idx": 0,
        "editor_job": None, # Para debounce
        "syntax_job": None,
        "search_job": None,
        "search_current_start": None,
        "search_current_end": None,
        "search_trace_suspended": False,
        "syntax_result": None,
        "syntax_running": False,
        "syntax_pending_payload": None,
        "syntax_request_seq": 0,
        "syntax_applied_seq": 0,
        "syntax_destroyed": False,
    }

    # Popup
    popup = tk.Toplevel()
    _ACTIVE_ARBITRARY_POPUP = popup
    ratio_pct = f"{ratio:.0%}" if ratio < 1.0 else ""
    ratio_label = f" ({ratio_pct})" if ratio_pct else ""
    popup.title(f"✨ Comparación y Edición{ratio_label} - {os.path.basename(file_path)}")
    
    # Centrar ventana
    # Maximizar ventana (modo ventana ocupando toda la pantalla)
    ws = popup.winfo_screenwidth()
    hs = popup.winfo_screenheight()
    popup.geometry(f"{ws}x{hs}+0+0")
    
    # Intentar estado 'zoomed' si el SO lo soporta (Windows/Linux)
    try:
        popup.state('zoomed')
    except:
        pass
    
    popup.configure(bg=THEME["bg"])

    # Info Header (File Path & Line)
    info_frame = tk.Frame(popup, bg=THEME["bg"])
    info_frame.pack(fill="x", padx=10, pady=(10, 0))
    
    # Label: Archivo
    tk.Label(
        info_frame, text="📂 Archivo:", 
        font=(Styles.FONT_FAMILY, 16, "bold"), fg="#569cd6", bg=THEME["bg"]
    ).pack(side="left")
    
    # Value: Path (Label)
    # Formato solicitado: directorio_padre/nombre_archivo
    try:
        parent_dir = os.path.basename(os.path.dirname(file_path))
        filename = os.path.basename(file_path)
        short_path = f"{parent_dir}/{filename}"
    except:
        short_path = file_path

    lbl_path = tk.Label(
        info_frame, text=short_path, 
        font=(Styles.FONT_FAMILY, 16), fg="#ce9178", bg=THEME["bg"]
    )
    lbl_path.pack(side="left", padx=5)

    # Label: Line
    tk.Label(
        info_frame, text="| 🔢 Línea aprox:", 
        font=(Styles.FONT_FAMILY, 16, "bold"), fg="#569cd6", bg=THEME["bg"]
    ).pack(side="left", padx=(15, 0))
    
    tk.Label(
        info_frame, text=str(line_num), 
        font=(Styles.FONT_FAMILY, 16), fg="#b5cea8", bg=THEME["bg"]
    ).pack(side="left", padx=5)

    # Header Controls
    control_frame = tk.Frame(popup, bg=THEME["bg"])
    control_frame.pack(fill="x", padx=10, pady=5)

    # --- BUTTONS (Header Right) ---
    def on_accept():
        # txt_edit se define más abajo, pero estará disponible cuando se pulse el botón
        new_content = txt_edit.get("1.0", "end-1c")
        syntax_result = validate_code_syntax(new_content, file_path)
        _apply_syntax_validation_result(syntax_result)
        if syntax_result.get("supported") and not syntax_result.get("ok"):
            proceed = messagebox.askyesno(
                "Sintaxis invalida",
                (
                    f"Se ha detectado un error de sintaxis en la linea "
                    f"{syntax_result.get('line') or 1}, columna {syntax_result.get('column') or 1}.\n\n"
                    "El fichero se puede guardar igualmente. ¿Quieres continuar?"
                ),
            )
            if not proceed:
                return
        # Confirmación automática
        success = apply_replacement(file_path, state["start_idx"], state["end_idx"], new_content)
        if success:
            if app_instance and hasattr(app_instance, "controller"):
                app_instance.controller.refresh_cached_file_content(file_path)
            if app_instance and hasattr(app_instance, "layout") and hasattr(app_instance.layout, "code_view"):
                app_instance.layout.code_view.refresh_file_list()
            # messagebox.showinfo("Éxito", "Actualizado.") # Removed popup
            popup.destroy()

    tk.Button(
        control_frame, text="✅ Aceptar y Sustituir", command=on_accept, 
        bg="#6a9955", fg="black", font=FONT_UI, padx=10, pady=2
    ).pack(side="right", padx=5)

    # Cancel button (Rightmost - legacy, maybe should be removed but kept for safety)
    tk.Button(
        control_frame, text="❌ Cancelar", command=popup.destroy, 
        bg="#f44336", fg="black", font=FONT_UI, padx=10, pady=2
    ).pack(side="right", padx=5)

    # Content Grid
    content_frame = tk.Frame(popup, bg=THEME["bg"])
    content_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    content_frame.columnconfigure(0, weight=1)
    content_frame.columnconfigure(1, weight=1)
    content_frame.rowconfigure(1, weight=1)
    
    # --- PANELES ---
    
    # 1. Clipboard
    lbl_clip = tk.Label(content_frame, text="📋 Portapapeles", bg=THEME["bg"], fg="#ce9178", font=FONT_UI)
    lbl_clip.grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
    
    txt_clip = create_styled_text_widget(content_frame, editable=False)
    txt_clip.insert("1.0", clipboard_text)
    highlight_syntax(txt_clip, file_path)  # Highlight con detección de lenguaje
    txt_clip.tag_configure("match_highlight", background="#fff792", foreground="#111827")

    def on_clip_right_click(event=None):
        """Relanza Arbitrary Search con el texto seleccionado del panel izquierdo."""
        if app_instance is None:
            return "break"

        try:
            selected_text = txt_clip.get("sel.first", "sel.last").strip()
        except tk.TclError:
            logging.info("Arbitrary: Click derecho sin selección en el panel izquierdo.")
            return "break"

        if not selected_text:
            logging.info("Arbitrary: La selección del panel izquierdo está vacía.")
            return "break"

        logging.info("Arbitrary: Nueva búsqueda lanzada desde selección del panel izquierdo.")
        if app_instance and hasattr(app_instance, "root"):
            app_instance.root.after_idle(
                lambda: run_arbitrary_search_with_text(
                    app_instance,
                    selected_text,
                    display_clipboard_text=clipboard_text,
                )
            )
        else:
            run_arbitrary_search_with_text(
                app_instance,
                selected_text,
                display_clipboard_text=clipboard_text,
            )
        return "break"

    txt_clip.bind("<Button-2>", on_clip_right_click)
    txt_clip.bind("<Button-3>", on_clip_right_click)
    txt_clip.bind("<Control-Button-1>", on_clip_right_click)
    txt_clip.config(state="disabled")
    txt_clip.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    edit_header_frame = tk.Frame(content_frame, bg=THEME["bg"])
    edit_header_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=(5, 0))
    edit_header_frame.columnconfigure(0, weight=1)

    lbl_edit = tk.Label(
        edit_header_frame,
        text="✏️ Editor (VS Code Style)",
        bg=THEME["bg"],
        fg="#dcdcaa",
        font=FONT_UI,
    )
    lbl_edit.grid(row=0, column=0, sticky="w")

    syntax_status_var = tk.StringVar(value="")
    syntax_status = tk.Label(
        edit_header_frame,
        textvariable=syntax_status_var,
        bg=THEME["bg"],
        fg="#858585",
        font=(Styles.FONT_FAMILY, 11),
        anchor="w",
        justify="left",
    )
    syntax_status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    search_host = tk.Frame(edit_header_frame, bg=THEME["bg"])
    search_host.grid(row=0, column=1, sticky="e")
    
    txt_edit = create_styled_text_widget(content_frame, editable=True)
    # Borde para distinguir editor
    txt_edit.config(bd=1, relief="solid") 
    txt_edit.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

    txt_edit.tag_configure("search_match", background="#264f78")
    txt_edit.tag_configure("search_current", background="#d7ba7d", foreground="#111827")
    txt_edit.tag_configure("syntax_error_line", background="#45212a")
    txt_edit.tag_configure("syntax_error_token", background="#7f1d1d", foreground="#ffffff", underline=True)

    search_var = tk.StringVar()
    search_frame = tk.Frame(search_host, bg="#252526", bd=1, relief="solid")
    search_status_var = tk.StringVar(value="")
    search_bar_visible = {"value": False}
    search_live_delay_ms = 120
    search_live_min_chars = 2
    search_highlight_limit = 250

    tk.Label(
        search_frame,
        text="Buscar:",
        bg="#252526",
        fg="#d4d4d4",
        font=(Styles.FONT_FAMILY, 11, "bold")
    ).pack(side="left", padx=(8, 6), pady=6)

    search_entry = tk.Entry(
        search_frame,
        textvariable=search_var,
        font=(Styles.FONT_FAMILY, 11),
        bg=THEME["bg"],
        fg=THEME["fg"],
        insertbackground=THEME["cursor"],
        relief="flat",
        width=28,
    )
    search_entry.pack(side="left", padx=(0, 6), pady=6, ipady=2)

    search_status = tk.Label(
        search_frame,
        textvariable=search_status_var,
        bg="#252526",
        fg="#9cdcfe",
        font=(Styles.FONT_FAMILY, 10),
        width=14,
        anchor="w"
    )
    search_status.pack(side="left", padx=(0, 6), pady=6)

    content_frame.columnconfigure(2, weight=0)  # columna para scrollbar compartida

    # Scrollbar independiente para cada panel (no sincronizamos por fracción,
    # sino por unidades absolutas en el mousewheel para mantener la alineación)
    scroll_clip = ttk.Scrollbar(content_frame, orient="vertical", command=txt_clip.yview)
    scroll_clip.grid(row=1, column=0, sticky="nse", pady=5)
    txt_clip.config(yscrollcommand=scroll_clip.set)

    scroll_edit = ttk.Scrollbar(content_frame, orient="vertical", command=txt_edit.yview)
    scroll_edit.grid(row=1, column=1, sticky="nse", pady=5)
    txt_edit.config(yscrollcommand=scroll_edit.set)

    def on_edit_right_click(event=None):
        """Busca la selección del editor en el portapapeles (panel izquierdo)."""
        try:
            selected_text = txt_edit.get("sel.first", "sel.last").strip()
        except tk.TclError:
            logging.info("Arbitrary: Click derecho sin selección en el panel editor.")
            return "break"

        if not selected_text:
            logging.info("Arbitrary: La selección del panel editor está vacía.")
            return "break"

        txt_clip.tag_remove("match_highlight", "1.0", tk.END)

        content = txt_clip.get("1.0", "end-1c")
        norm_selected = _normalize_text(selected_text)
        norm_content = _normalize_text(content)

        all_ranges = []

        idx = norm_content.find(norm_selected)
        if idx >= 0:
            line_start = norm_content.count("\n", 0, idx) + 1
            col_start = idx - norm_content.rfind("\n", 0, idx) - 1
            end_idx = idx + len(norm_selected)
            line_end = norm_content.count("\n", 0, end_idx) + 1
            col_end = end_idx - norm_content.rfind("\n", 0, end_idx) - 1
            all_ranges.append((f"{line_start}.{col_start}", f"{line_end}.{col_end}"))
            start_offset = end_idx
            while True:
                idx2 = norm_content.find(norm_selected, start_offset)
                if idx2 < 0:
                    break
                ls = norm_content.count("\n", 0, idx2) + 1
                cs = idx2 - norm_content.rfind("\n", 0, idx2) - 1
                ei2 = idx2 + len(norm_selected)
                le = norm_content.count("\n", 0, ei2) + 1
                ce = ei2 - norm_content.rfind("\n", 0, ei2) - 1
                all_ranges.append((f"{ls}.{cs}", f"{le}.{ce}"))
                start_offset = ei2
                if len(all_ranges) >= 50:
                    break

        if not all_ranges:
            start = "1.0"
            while True:
                pos = txt_clip.search(selected_text, start, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(selected_text)}c"
                all_ranges.append((pos, end))
                start = end
                if len(all_ranges) >= 50:
                    break

        if all_ranges:
            for range_start, range_end in all_ranges:
                txt_clip.tag_add("match_highlight", range_start, range_end)
            txt_clip.tag_lower("match_highlight")
            txt_clip.see(all_ranges[0][0])
            logging.info(f"Arbitrary: Selección del editor encontrada en portapapeles ({len(all_ranges)} resultado(s)).")
        else:
            logging.info("Arbitrary: Selección del editor no encontrada en portapapeles.")

        return "break"

    txt_edit.bind("<Button-2>", on_edit_right_click)
    txt_edit.bind("<Button-3>", on_edit_right_click)
    txt_edit.bind("<Control-Button-1>", on_edit_right_click)

    def clear_match_highlight(event=None):
        txt_edit.tag_remove("match_highlight", "1.0", tk.END)
        txt_clip.tag_remove("match_highlight", "1.0", tk.END)

    txt_edit.bind("<Button-1>", clear_match_highlight)

    def _cancel_search_job():
        if state["search_job"]:
            try:
                popup.after_cancel(state["search_job"])
            except Exception:
                pass
            state["search_job"] = None

    def _cancel_syntax_job():
        if state["syntax_job"]:
            try:
                popup.after_cancel(state["syntax_job"])
            except Exception:
                pass
            state["syntax_job"] = None

    def _set_search_text(value):
        if search_var.get() == value:
            return
        state["search_trace_suspended"] = True
        try:
            search_var.set(value)
        finally:
            state["search_trace_suspended"] = False

    def _clear_search_tags():
        txt_edit.tag_remove("search_match", "1.0", tk.END)
        txt_edit.tag_remove("search_current", "1.0", tk.END)
        state["search_current_start"] = None
        state["search_current_end"] = None

    def _clear_syntax_error_tags():
        txt_edit.tag_remove("syntax_error_line", "1.0", tk.END)
        txt_edit.tag_remove("syntax_error_token", "1.0", tk.END)

    def _highlight_syntax_error(result):
        _clear_syntax_error_tags()

        if not result or result.get("ok") or not result.get("supported"):
            return

        line = max(int(result.get("line") or 1), 1)
        column = max(int(result.get("column") or 1), 1)
        end_line = max(int(result.get("end_line") or line), line)
        end_column = result.get("end_column")

        line_count = max(int(txt_edit.index("end-1c").split(".")[0]), 1)
        line = min(line, line_count)
        end_line = min(end_line, line_count)

        txt_edit.tag_add("syntax_error_line", f"{line}.0", f"{line}.end")

        start_col_zero = max(column - 1, 0)
        if end_line == line and end_column:
            end_col_zero = max(int(end_column) - 1, start_col_zero + 1)
        else:
            end_col_zero = start_col_zero + 1

        txt_edit.tag_add(
            "syntax_error_token",
            f"{line}.{start_col_zero}",
            f"{line}.{end_col_zero}",
        )
        txt_edit.tag_raise("syntax_error_line")
        txt_edit.tag_raise("syntax_error_token")
        txt_edit.see(f"{line}.0")

    def _apply_syntax_validation_result(result):
        if not popup.winfo_exists() or not txt_edit.winfo_exists():
            return

        state["syntax_result"] = result
        _clear_syntax_error_tags()

        if not result.get("supported"):
            syntax_status_var.set(result["message"])
            syntax_status.configure(fg="#858585")
            return

        if result.get("ok"):
            syntax_status_var.set(f"Sintaxis OK: {result['message']}")
            syntax_status.configure(fg="#6a9955")
            return

        line = result.get("line") or 1
        column = result.get("column") or 1
        syntax_status_var.set(
            f"Error de sintaxis en linea {line}, columna {column}: {result['message']}"
        )
        syntax_status.configure(fg="#f44747")
        _highlight_syntax_error(result)

    def _start_pending_syntax_validation():
        if state["syntax_destroyed"] or state["syntax_running"] or not state["syntax_pending_payload"]:
            return

        request_seq, content_snapshot = state["syntax_pending_payload"]
        state["syntax_pending_payload"] = None
        state["syntax_running"] = True

        def _worker(seq=request_seq, snapshot=content_snapshot):
            result = validate_code_syntax(snapshot, file_path)

            def _deliver():
                if state["syntax_destroyed"] or not popup.winfo_exists():
                    state["syntax_running"] = False
                    return

                state["syntax_running"] = False
                if seq >= state["syntax_applied_seq"]:
                    state["syntax_applied_seq"] = seq
                    _apply_syntax_validation_result(result)

                if state["syntax_pending_payload"]:
                    _start_pending_syntax_validation()

            try:
                popup.after(0, _deliver)
            except Exception:
                state["syntax_running"] = False

        threading.Thread(target=_worker, daemon=True).start()

    def _queue_syntax_validation():
        if state["syntax_destroyed"] or not popup.winfo_exists() or not txt_edit.winfo_exists():
            state["syntax_job"] = None
            return

        state["syntax_job"] = None
        state["syntax_request_seq"] += 1
        state["syntax_pending_payload"] = (
            state["syntax_request_seq"],
            txt_edit.get("1.0", "end-1c"),
        )
        syntax_status_var.set("Validando sintaxis...")
        syntax_status.configure(fg="#9cdcfe")
        _start_pending_syntax_validation()

    def _schedule_syntax_validation(delay_ms=500):
        _cancel_syntax_job()
        state["syntax_job"] = popup.after(delay_ms, _queue_syntax_validation)

    def _set_current_search_match(start_index, end_index):
        state["search_current_start"] = start_index
        state["search_current_end"] = end_index
        txt_edit.tag_remove("search_current", "1.0", tk.END)
        txt_edit.tag_add("search_current", start_index, end_index)
        txt_edit.tag_raise("search_current")
        txt_edit.mark_set("insert", end_index)
        txt_edit.see(start_index)

    def _collect_search_matches():
        term = search_var.get()
        _clear_search_tags()

        if not term:
            search_status_var.set("")
            return []

        if len(term) < search_live_min_chars:
            search_status_var.set(f"Enter para buscar {len(term)} carácter" if len(term) == 1 else "")
            return []

        matches = []
        start_index = "1.0"
        term_length = len(term)
        truncated = False
        while True:
            match_index = txt_edit.search(term, start_index, stopindex=tk.END, nocase=True)
            if not match_index:
                break
            end_index = f"{match_index}+{term_length}c"
            matches.append((match_index, end_index))
            txt_edit.tag_add("search_match", match_index, end_index)
            start_index = end_index
            if len(matches) >= search_highlight_limit:
                truncated = True
                break

        txt_edit.tag_raise("search_match")
        if matches:
            if truncated:
                search_status_var.set(f"{search_highlight_limit}+ coincidencias")
            else:
                search_status_var.set(f"{len(matches)} coincidencia{'s' if len(matches) != 1 else ''}")
        else:
            search_status_var.set("Sin resultados")
        return matches

    def _select_search_result(match_tuple):
        if not match_tuple:
            return
        start_index, end_index = match_tuple
        _set_current_search_match(start_index, end_index)

    def _refresh_search_matches(select_first=False):
        if not popup.winfo_exists() or not txt_edit.winfo_exists():
            state["search_job"] = None
            return []
        matches = _collect_search_matches()
        if select_first and matches:
            _select_search_result(matches[0])
        elif not matches:
            _clear_search_tags()
        state["search_job"] = None
        return matches

    def _schedule_search_refresh(select_first=False, delay_ms=None):
        _cancel_search_job()
        if not search_bar_visible["value"]:
            return
        delay = search_live_delay_ms if delay_ms is None else delay_ms
        state["search_job"] = popup.after(delay, lambda: _refresh_search_matches(select_first=select_first))

    def _find_next_match(event=None):
        term = search_var.get()
        if not term:
            return "break"

        start_index = state["search_current_end"] or txt_edit.index("insert")
        match_index = txt_edit.search(term, start_index, stopindex=tk.END, nocase=True)
        if not match_index:
            match_index = txt_edit.search(term, "1.0", stopindex=start_index, nocase=True)
        if not match_index:
            search_status_var.set("Sin resultados")
            return "break"

        end_index = f"{match_index}+{len(term)}c"
        _set_current_search_match(match_index, end_index)
        return "break"

    def _find_previous_match(event=None):
        term = search_var.get()
        if not term:
            return "break"

        start_index = state["search_current_start"] or txt_edit.index("insert")
        match_index = txt_edit.search(term, start_index, stopindex="1.0", nocase=True, backwards=True)
        if not match_index:
            match_index = txt_edit.search(term, tk.END, stopindex=start_index, nocase=True, backwards=True)
        if not match_index:
            search_status_var.set("Sin resultados")
            return "break"

        end_index = f"{match_index}+{len(term)}c"
        _set_current_search_match(match_index, end_index)
        return "break"

    def _hide_search_bar(event=None):
        _cancel_search_job()
        if search_bar_visible["value"]:
            search_frame.pack_forget()
            search_bar_visible["value"] = False
        _set_search_text("")
        search_status_var.set("")
        _clear_search_tags()
        txt_edit.focus_set()
        return "break"

    def _show_search_bar(event=None):
        if not search_bar_visible["value"]:
            search_frame.pack(side="right")
            search_bar_visible["value"] = True

        try:
            selected_text = txt_edit.get("sel.first", "sel.last").strip()
        except tk.TclError:
            selected_text = ""

        if selected_text and "\n" not in selected_text:
            _set_search_text(selected_text)

        search_entry.focus_set()
        search_entry.selection_range(0, tk.END)
        _schedule_search_refresh(select_first=bool(search_var.get()), delay_ms=0)
        return "break"

    def _on_search_text_change(*_args):
        if state["search_trace_suspended"] or not search_bar_visible["value"]:
            return
        _schedule_search_refresh(select_first=True)

    search_var.trace_add("write", _on_search_text_change)

    tk.Button(
        search_frame,
        text="↑",
        command=_find_previous_match,
        bg="#333333",
        fg="#d4d4d4",
        font=(Styles.FONT_FAMILY, 10, "bold"),
        padx=6,
        pady=1
    ).pack(side="left", padx=(0, 4), pady=6)

    tk.Button(
        search_frame,
        text="↓",
        command=_find_next_match,
        bg="#333333",
        fg="#d4d4d4",
        font=(Styles.FONT_FAMILY, 10, "bold"),
        padx=6,
        pady=1
    ).pack(side="left", padx=(0, 4), pady=6)

    tk.Button(
        search_frame,
        text="✕",
        command=_hide_search_bar,
        bg="#5a1d1d",
        fg="#ff9b9b",
        font=(Styles.FONT_FAMILY, 10, "bold"),
        padx=6,
        pady=1
    ).pack(side="left", padx=(0, 8), pady=6)

    search_entry.bind("<Return>", _find_next_match)
    search_entry.bind("<Shift-Return>", _find_previous_match)
    search_entry.bind("<Escape>", _hide_search_bar)
    def on_edit_change(event=None):
        """Re-highlighter con debounce simple"""
        if state["editor_job"]:
            popup.after_cancel(state["editor_job"])
        # Esperar 300ms de inactividad para colorear (performance)
        def _refresh_editor_visuals():
            highlight_syntax(txt_edit, file_path)
            if search_var.get():
                _schedule_search_refresh(select_first=False, delay_ms=0)

        state["editor_job"] = popup.after(300, _refresh_editor_visuals)
        _schedule_syntax_validation(delay_ms=500)

    # --- UNDO / REDO (Ctrl+Z / Ctrl+Y) ---
    def on_undo(event=None):
        try:
            txt_edit.edit_undo()
            on_edit_change()  # Re-highlight tras deshacer
        except tk.TclError:
            pass  # Pila de undo vacía
        return "break"  # Evitar comportamiento por defecto

    def on_redo(event=None):
        try:
            txt_edit.edit_redo()
            on_edit_change()  # Re-highlight tras rehacer
        except tk.TclError:
            pass  # Pila de redo vacía
        return "break"

    # --- PASTE con indentado preservado ---
    def on_paste(event=None):
        """Pega texto del portapapeles preservando indentación original."""
        try:
            # Obtener texto raw del portapapeles (preserva espacios/tabs)
            try:
                raw_text = txt_edit.clipboard_get()
            except tk.TclError:
                return "break"
            
            if not raw_text:
                return "break"
            
            # Si hay selección, eliminarla primero
            try:
                sel_start = txt_edit.index("sel.first")
                sel_end = txt_edit.index("sel.last")
                txt_edit.delete(sel_start, sel_end)
            except tk.TclError:
                pass  # No hay selección, OK
            
            # Insertar texto en posición actual del cursor
            txt_edit.insert("insert", raw_text)
            
            # Re-highlight
            on_edit_change()
            
        except Exception as e:
            logging.error(f"Error en paste personalizado: {e}")
        
        return "break"  # Evitar el paste por defecto de Tkinter

    # --- TAB / SHIFT+TAB (Indent / Dedent) ---
    def on_tab(event=None):
        """Añade 4 espacios de indentación a las líneas seleccionadas."""
        try:
            sel_start = txt_edit.index("sel.first")
            sel_end = txt_edit.index("sel.last")
        except tk.TclError:
            # Sin selección: insertar 4 espacios en cursor
            txt_edit.insert("insert", "    ")
            on_edit_change()
            return "break"

        # Obtener rango de líneas
        start_line = int(sel_start.split(".")[0])
        end_line = int(sel_end.split(".")[0])
        # Si el cursor está al inicio de la última línea, no incluirla
        if sel_end.endswith(".0") and end_line > start_line:
            end_line -= 1

        for line in range(start_line, end_line + 1):
            txt_edit.insert(f"{line}.0", "    ")

        # Restaurar selección
        txt_edit.tag_remove("sel", "1.0", tk.END)
        txt_edit.tag_add("sel", f"{start_line}.0", f"{end_line + 1}.0")
        on_edit_change()
        return "break"

    def on_shift_tab(event=None):
        """Quita hasta 4 espacios de indentación de las líneas seleccionadas."""
        try:
            sel_start = txt_edit.index("sel.first")
            sel_end = txt_edit.index("sel.last")
        except tk.TclError:
            # Sin selección: quitar espacios de la línea actual
            line_num = int(txt_edit.index("insert").split(".")[0])
            line_text = txt_edit.get(f"{line_num}.0", f"{line_num}.end")
            spaces = len(line_text) - len(line_text.lstrip(" "))
            remove = min(spaces, 4)
            if remove > 0:
                txt_edit.delete(f"{line_num}.0", f"{line_num}.{remove}")
                on_edit_change()
            return "break"

        start_line = int(sel_start.split(".")[0])
        end_line = int(sel_end.split(".")[0])
        if sel_end.endswith(".0") and end_line > start_line:
            end_line -= 1

        for line in range(start_line, end_line + 1):
            line_text = txt_edit.get(f"{line}.0", f"{line}.end")
            spaces = len(line_text) - len(line_text.lstrip(" "))
            remove = min(spaces, 4)
            if remove > 0:
                txt_edit.delete(f"{line}.0", f"{line}.{remove}")

        # Restaurar selección
        txt_edit.tag_remove("sel", "1.0", tk.END)
        txt_edit.tag_add("sel", f"{start_line}.0", f"{end_line + 1}.0")
        on_edit_change()
        return "break"

    txt_edit.bind("<KeyRelease>", on_edit_change)
    txt_edit.bind("<Control-z>", on_undo)
    txt_edit.bind("<Control-Z>", on_undo)  # Con Shift/CapsLock
    txt_edit.bind("<Control-y>", on_redo)
    txt_edit.bind("<Control-Y>", on_redo)
    txt_edit.bind("<Control-v>", on_paste)
    txt_edit.bind("<Control-V>", on_paste)
    txt_edit.bind("<Tab>", on_tab)
    txt_edit.bind("<Shift-Tab>", on_shift_tab)
    # macOS support (Command key)
    txt_edit.bind("<Command-z>", on_undo)
    txt_edit.bind("<Command-Z>", on_undo)
    txt_edit.bind("<Command-y>", on_redo)
    txt_edit.bind("<Command-Y>", on_redo)
    txt_edit.bind("<Command-Shift-z>", on_redo)  # macOS usa Cmd+Shift+Z para redo
    txt_edit.bind("<Command-Shift-Z>", on_redo)
    txt_edit.bind("<Command-v>", on_paste)
    txt_edit.bind("<Command-V>", on_paste)
    txt_edit.bind("<Control-f>", _show_search_bar)
    txt_edit.bind("<Control-F>", _show_search_bar)
    txt_edit.bind("<Command-f>", _show_search_bar)
    txt_edit.bind("<Command-F>", _show_search_bar)

    def update_view():
        full_block, start_idx, end_idx, match_abs_start = get_match_context(file_path, match_text, line_num)
        
        if full_block is None:
            return
            
        state["start_idx"] = start_idx
        state["end_idx"] = end_idx
        
        # Update Editor
        txt_edit.delete("1.0", "end")
        txt_edit.insert("1.0", full_block)
        highlight_syntax(txt_edit, file_path)
        if search_var.get():
            _schedule_search_refresh(select_first=False, delay_ms=0)
        _schedule_syntax_validation(delay_ms=0)
        
        # Highlight matched region with subtle gray background
        txt_edit.tag_remove("match_highlight", "1.0", tk.END)
        rel_pos = match_abs_start - start_idx
        if rel_pos >= 0 and match_text:
            # Calculate start line/col from rel_pos
            text_before_match = full_block[:rel_pos]
            match_start_line = text_before_match.count('\n') + 1
            last_newline = text_before_match.rfind('\n')
            match_start_col = rel_pos - last_newline - 1 if last_newline != -1 else rel_pos
            
            # Calculate end line/col
            match_end_pos = rel_pos + len(match_text)
            text_before_end = full_block[:match_end_pos]
            match_end_line = text_before_end.count('\n') + 1
            last_newline_end = text_before_end.rfind('\n')
            match_end_col = match_end_pos - last_newline_end - 1 if last_newline_end != -1 else match_end_pos
            
            start_index = f"{match_start_line}.{match_start_col}"
            end_index = f"{match_end_line}.{match_end_col}"
            
            txt_edit.tag_configure("match_highlight", background="#fff792", foreground="#111827")
            txt_edit.tag_add("match_highlight", start_index, end_index)
            # Ensure match_highlight is below syntax tags so colors are preserved
            txt_edit.tag_lower("match_highlight")
        
        # Resetear pila de undo para que la carga inicial no sea deshacible
        txt_edit.edit_reset()
        txt_edit.edit_separator()  # Separador para que la primera edición del usuario sea un bloque limpio
        

        # --- Sincronización visual: alinear línea 1 del portapapeles con match en el editor ---
        # match_start_line = línea dentro de full_block donde empieza el match
        match_line = match_start_line if rel_pos >= 0 and match_text else 1

        def _do_sync_scroll():
            popup.update_idletasks()

            # 1. Poner el editor con match_line en la parte superior
            total_edit_lines = int(txt_edit.index("end-1c").split(".")[0])
            if total_edit_lines > 0:
                frac_edit = max(0.0, (match_line - 1) / total_edit_lines)
                txt_edit.yview_moveto(frac_edit)

            # 2. El portapapeles tiene (match_line - 1) líneas de contexto antes del match.
            #    Queremos que la línea 1 del portapapeles quede a la misma altura visual
            #    que match_line en el editor, es decir, desplazar txt_clip hacia arriba
            #    (match_line - 1) líneas respecto al inicio.
            #    Como el portapapeles empieza en línea 1, necesitamos hacer scroll negativo:
            #    scrolleamos txt_clip a la fracción equivalente a -(match_line-1) líneas.
            #    En la práctica: ponemos txt_clip al inicio (0.0) y luego hacemos scroll
            #    hacia arriba tantas unidades como líneas de contexto hay antes del match.
            txt_clip.yview_moveto(0.0)
            # Desplazar hacia abajo en el portapapeles para que la línea 1 quede
            # alineada con match_line del editor. Como el portapapeles es más corto,
            # simplemente lo dejamos al inicio (línea 1 = inicio del portapapeles).
            # El editor se desplaza para que match_line esté arriba → ambos alineados.

        popup.after(50, _do_sync_scroll)



    update_view() # Initial load

    def _close_previous_popup():
        if previous_popup is popup:
            return
        try:
            if previous_popup and previous_popup.winfo_exists():
                previous_popup.destroy()
        except Exception:
            pass

    popup.after_idle(_close_previous_popup)

    def _on_popup_destroy(event=None):
        global _ACTIVE_ARBITRARY_POPUP
        state["syntax_destroyed"] = True
        state["syntax_pending_payload"] = None
        _cancel_search_job()
        _cancel_syntax_job()
        if state["editor_job"]:
            try:
                popup.after_cancel(state["editor_job"])
            except Exception:
                pass
            state["editor_job"] = None
        state["syntax_running"] = False
        if _ACTIVE_ARBITRARY_POPUP is popup:
            _ACTIVE_ARBITRARY_POPUP = None

    popup.bind("<Destroy>", _on_popup_destroy, add="+")



def show_file_picker_dialog(file_list):
    """
    Muestra un diálogo global con un botón por cada fichero de la sección.
    Devuelve el path del fichero seleccionado o None si se cancela.
    """
    result = {"value": None}
    
    dialog = tk.Toplevel()
    dialog.title("🔍 Seleccionar Fichero")
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(True, True)
    dialog.attributes('-topmost', True)
    dialog.focus_force()
    
    # Tamaño y posición centrada
    w = 500
    h = min(60 + len(file_list) * 42, 700)  # Altura dinámica según nº ficheros
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = int((ws / 2) - (w / 2))
    y = int((hs / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    
    # Header
    tk.Label(
        dialog,
        text="No se pudo identificar el fichero con certeza.\nSelecciona el fichero donde buscar:",
        bg=THEME["bg"], fg="#569cd6",
        font=(Styles.FONT_FAMILY, 13),
        justify="left"
    ).pack(padx=15, pady=(12, 8), anchor="w")
    
    # Frame scrollable para los botones
    canvas = tk.Canvas(dialog, bg=THEME["bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    btn_frame = tk.Frame(canvas, bg=THEME["bg"])
    
    btn_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=btn_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=5)
    scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)
    
    # Crear un "botón" (Label clicable) por cada fichero
    # macOS ignora bg/fg en tk.Button, así que usamos Labels con binds
    for fpath in file_list:
        try:
            parent_dir = os.path.basename(os.path.dirname(fpath))
            filename = os.path.basename(fpath)
            display_name = f"{parent_dir}/{filename}"
        except Exception:
            display_name = fpath
        
        def make_callback(p=fpath):
            def cb(event=None):
                result["value"] = p
                dialog.destroy()
            return cb
        
        lbl = tk.Label(
            btn_frame,
            text=f"📄 {display_name}",
            bg="#333333", fg="#d4d4d4",
            font=(Styles.FONT_FAMILY, 12),
            anchor="w",
            padx=10, pady=6,
            cursor="hand2"
        )
        lbl.pack(fill="x", padx=5, pady=2)
        
        cb = make_callback(fpath)
        lbl.bind("<Button-1>", cb)
        # Hover effect
        lbl.bind("<Enter>", lambda e, l=lbl: l.configure(bg="#264f78", fg="white"))
        lbl.bind("<Leave>", lambda e, l=lbl: l.configure(bg="#333333", fg="#d4d4d4"))
    
    # Botón Cancelar al final (Label clicable)
    cancel_lbl = tk.Label(
        dialog,
        text="❌ Cancelar",
        bg="#5a1d1d", fg="#ff6b6b",
        font=(Styles.FONT_FAMILY, 11, "bold"),
        padx=15, pady=6,
        cursor="hand2"
    )
    cancel_lbl.pack(pady=(5, 12))
    cancel_lbl.bind("<Button-1>", lambda e: dialog.destroy())
    cancel_lbl.bind("<Enter>", lambda e: cancel_lbl.configure(bg="#7a2d2d"))
    cancel_lbl.bind("<Leave>", lambda e: cancel_lbl.configure(bg="#5a1d1d"))
    
    # Handle window close
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    
    # Modal
    dialog.grab_set()
    dialog.wait_window()
    
    return result["value"]


def _get_code_files_for_arbitrary_search(app_instance):
    """Obtiene los ficheros objetivo de Arbitrary Search."""
    code_files = []
    seen_paths = set()

    def _append_candidate(file_path):
        normalized_path = os.path.normpath(str(file_path or "").strip())
        if not normalized_path or normalized_path in seen_paths or not os.path.exists(normalized_path):
            return
        seen_paths.add(normalized_path)
        code_files.append(normalized_path)

    code_view = None
    if hasattr(app_instance, 'layout') and hasattr(app_instance.layout, 'code_view'):
        code_view = app_instance.layout.code_view

    # Prioridad: ficheros visibles/listados en CodeView
    if code_view:
        if hasattr(code_view, 'tree'):
            for item_id in code_view.tree.get_children():
                file_path = None
                if hasattr(code_view, "_get_tree_item_path"):
                    file_path = code_view._get_tree_item_path(item_id)
                else:
                    tags = code_view.tree.item(item_id, 'tags')
                    if tags:
                        file_path = tags[0] if isinstance(tags, (list, tuple)) else tags

                _append_candidate(file_path)

    # Fallback 1: preview actual de segmento/región/archivo en el panel derecho.
    if code_view:
        _append_candidate(getattr(code_view, "_segment_code_preview_file_hint", None))

        preview_file_map = getattr(code_view, "_segment_code_preview_file_map", None)
        if isinstance(preview_file_map, dict):
            for file_path in preview_file_map.values():
                _append_candidate(file_path)

    # Fallback 2: elementos asociados al segmento o región seleccionados.
    controller = getattr(app_instance, "controller", None)
    if code_view and controller and hasattr(code_view, "_get_selected_tree_item_info"):
        try:
            scope_kind, section_name, subsection_name, leaf_name = code_view._get_selected_tree_item_info()
        except Exception:
            scope_kind, section_name, subsection_name, leaf_name = (None, None, None, None)

        selected_entity = None
        if scope_kind == "segment" and section_name and subsection_name and leaf_name:
            try:
                selected_entity = controller.section_manager.get_segment(section_name, subsection_name, leaf_name)
            except Exception:
                selected_entity = None
        elif scope_kind == "region_segment" and leaf_name and hasattr(controller, "region_segment_manager"):
            try:
                selected_entity = controller.region_segment_manager.get_region_segment(leaf_name)
            except Exception:
                selected_entity = None

        if isinstance(selected_entity, dict):
            for item in selected_entity.get("items", []):
                if not isinstance(item, dict):
                    continue
                _append_candidate(item.get("file_path"))

    return code_files


def run_arbitrary_search_with_text(
    app_instance,
    search_text,
    prioritize_clipboard_file=False,
    display_clipboard_text=None,
):
    try:
        search_text = (search_text or "").strip()
        if not search_text:
            logging.info("Arbitrary: Texto de búsqueda vacío.")
            return

        search_text, _ = strip_modification_comments(search_text)
        search_text = search_text.strip()
        if not search_text:
            logging.info("Arbitrary: Texto de búsqueda vacío tras limpiar comentarios [MODIFICACIÓN].")
            return

        try:
            current_clipboard = pyperclip.paste()
            cleaned_clipboard, had_comments = strip_modification_comments(current_clipboard)
            cleaned_clipboard_stripped = cleaned_clipboard.strip()
            if had_comments > 0 and cleaned_clipboard_stripped:
                pyperclip.copy(cleaned_clipboard)
        except Exception:
            pass

        if display_clipboard_text is None:
            display_clipboard_text = search_text
        else:
            display_clipboard_text, _ = strip_modification_comments(display_clipboard_text)

        code_files = _get_code_files_for_arbitrary_search(app_instance)
        if not code_files:
             tk.messagebox.showwarning("Arbitrary", "No se pudieron resolver archivos objetivo para la búsqueda.")
             return

        min_search_len, max_search_len = _get_arbitrary_search_bounds(app_instance, search_text)
        forced_file = None
        if prioritize_clipboard_file:
            path_hint, cleaned_search_text = _extract_clipboard_file_hint(search_text)
            if path_hint:
                search_text = cleaned_search_text
                min_search_len, max_search_len = _get_arbitrary_search_bounds(app_instance, search_text)
                matched_files = _match_code_files_by_path_hint(path_hint, code_files)
                if len(matched_files) == 1:
                    forced_file = matched_files[0]
                    logging.info(
                        f"Arbitrary: Archivo detectado en portapapeles. "
                        f"Priorizando {os.path.basename(forced_file)}."
                    )
                elif matched_files:
                    logging.info(
                        f"Arbitrary: La pista de archivo '{path_hint}' es ambigua. "
                        "Se mantiene búsqueda global."
                    )
                else:
                    logging.info(
                        f"Arbitrary: La pista de archivo '{path_hint}' no coincide con "
                        "ningún fichero objetivo. Se mantiene búsqueda global."
                    )

        logging.info(f"Arbitrary: Buscando en {len(code_files)} ficheros objetivo.")

        app_instance.root.config(cursor="watch")
        app_instance.root.update()

        # --- PRIMERA CAPA: Busqueda por estructuras de codigo ---
        struct_match, struct_file, struct_ratio, struct_line = _find_match_by_structures(
            search_text, code_files, forced_file=forced_file
        )

        if struct_match and struct_file and struct_ratio >= _ARBITRARY_STRUCTURE_MIN_SCORE:
            app_instance.root.config(cursor="")
            logging.info(
                f"[Arbitrary] Coincidencia por estructura (score={struct_ratio:.2f}, "
                f"fichero={os.path.basename(struct_file)}, linea={struct_line})"
            )
            show_popup(
                display_clipboard_text,
                struct_match,
                struct_file,
                struct_ratio,
                struct_line,
                app_instance=app_instance,
            )
            return

        logging.info("[Arbitrary] Busqueda por estructuras sin resultado satisfactorio, intentando busqueda por substring...")

        # --- SEGUNDA CAPA: Busqueda por substring (algoritmo original) ---
        match, file_path, ratio, line_num = find_similar_region(
            code_files,
            search_text,
            forced_file=forced_file,
            min_search_len=min_search_len,
            max_search_len=max_search_len,
        )

        app_instance.root.config(cursor="")

        if match and file_path:
            show_popup(
                display_clipboard_text,
                match,
                file_path,
                ratio,
                line_num,
                app_instance=app_instance,
            )
        else:
            logging.info("Arbitrary: Sin coincidencias suficientes para abrir popup.")

    except Exception as e:
        app_instance.root.config(cursor="")
        logging.error(f"Error: {e}")
        tk.messagebox.showerror("Error", str(e))


def run_arbitrary_search(app_instance, prioritize_clipboard_file=False):
    clipboard_text = pyperclip.paste().strip()
    if not clipboard_text:
        logging.info("Arbitrary: Portapapeles vacío.")
        return

    clipboard_text, _ = strip_modification_comments(clipboard_text)
    clipboard_text = clipboard_text.strip()
    if not clipboard_text:
        logging.info("Arbitrary: Portapapeles vacío tras limpiar comentarios [MODIFICACIÓN].")
        return

    if clipboard_text != pyperclip.paste().strip():
        pyperclip.copy(clipboard_text)

    run_arbitrary_search_with_text(
        app_instance,
        clipboard_text,
        prioritize_clipboard_file=prioritize_clipboard_file,
    )

def process_smart_paste(app_instance):
    """
    Maneja la lógica de pegado inteligente lanzada por Shift+Click.
    La sustitución automática por regiones está desactivada temporalmente.
    Shift+Click solo debe abrir la sustitución manual (Arbitrary Search)
    cuando no haya sido resuelta antes por sustitución de estructuras.
    """
    try:
        def _log_smart_paste_skip(reason):
            message = f"Smart Paste: Arbitrary_sus no se disparó porque {reason}."
            logging.info(message)
            print(message)

        content = pyperclip.paste()
        if not content:
            _log_smart_paste_skip("el portapapeles está vacío")
            return False

        content, _ = strip_modification_comments(content)
        content = content.strip()
        if not content:
            _log_smart_paste_skip("el portapapeles está vacío tras limpiar comentarios [MODIFICACIÓN]")
            return False

        original_clipboard = pyperclip.paste()
        if content != original_clipboard.strip():
            pyperclip.copy(content)

        # 0. Chequeo de Comando de Consola
        if is_console_command(content):
            # Preguntar al usuario con ventana topmost
            if show_global_confirmation_dialog("Ejecutar Comando", f"¿Quieres ejecutar este comando en la raíz del proyecto?\n\n{content}"):
                _log_smart_paste_skip("el contenido del portapapeles se confirmó como comando de consola")
                execute_clipboard_command(app_instance, content)
                return True

        target_files = _get_code_files_for_arbitrary_search(app_instance)
        if target_files:
            logging.info(
                f"Smart Paste: Se conocen {len(target_files)} fichero(s) objetivo. "
                "Buscando directamente en ellos sin depender de la lista visible."
            )
            run_arbitrary_search_with_text(
                app_instance,
                content,
                prioritize_clipboard_file=_should_prioritize_clipboard_file_hint(app_instance),
            )
            return True

        logging.info("Smart Paste: No hay ficheros objetivo resueltos. Lanzando búsqueda arbitraria.")
        run_arbitrary_search(
            app_instance,
            prioritize_clipboard_file=_should_prioritize_clipboard_file_hint(app_instance),
        )
        return True

    except Exception as e:
        logging.error(f"Error en Smart Paste: {e}")
        tk.messagebox.showerror("Error", f"Error procesando portapapeles: {e}")
        return False

def is_console_command(text):
    """
    Determina si el texto en el portapapeles es probablemente un comando de consola.
    """
    text = text.strip()
    if not text:
        return False
        
    # No considerar si tiene múltiples líneas (salvo que sean comandos encadenados con && o similar, 
    # pero por seguridad mejor limitarlo a una línea o pocas muy claras)
    if len(text.split('\n')) > 3: 
        return False

    # Lista de comandos comunes iniciales
    COMMON_COMMANDS = {
        "git", "npm", "pip", "pip3", "python", "python3", "node", "docker", 
        "cd", "ls", "mkdir", "rm", "mv", "cp", "touch", "echo", "cat", 
        "npx", "yarn", "bun", "uv", "virtualenv", "source", "./"
    }
    
    first_word = text.split(' ')[0]
    
    # Check 1: Empieza por comando común
    if first_word in COMMON_COMMANDS:
        return True
        
    # Check 2: Empieza por ./ (script local)
    if text.startswith("./"):
        return True
        
    return False

def show_global_confirmation_dialog(title, message):
    """
    Shows a custom Toplevel dialog that is topmost and forces focus.
    Returns True if user clicked Yes, False otherwise.
    """
    result = {"value": False}
    
    dialog = tk.Toplevel()
    dialog.title(title)
    
    # Configure window
    dialog.configure(bg=THEME["bg"])
    dialog.resizable(False, False)
    
    # Make it topmost and grab focus
    dialog.attributes('-topmost', True)
    dialog.focus_force()
    
    # Center on screen
    w = 600
    h = 250
    ws = dialog.winfo_screenwidth()
    hs = dialog.winfo_screenheight()
    x = (ws/2) - (w/2)
    y = (hs/2) - (h/2)
    dialog.geometry('%dx%d+%d+%d' % (w, h, x, y))
    
    # UI Elements
    frame = tk.Frame(dialog, bg=THEME["bg"], padx=20, pady=20)
    frame.pack(fill="both", expand=True)
    
    lbl_msg = tk.Label(
        frame, 
        text=message, 
        bg=THEME["bg"], 
        fg=THEME["fg"],
        font=(Styles.FONT_FAMILY, 12),
        wraplength=550,
        justify="left"
    )
    lbl_msg.pack(pady=(0, 20), anchor="w")
    
    btn_frame = tk.Frame(frame, bg=THEME["bg"])
    btn_frame.pack(side="bottom", fill="x")
    
    def on_yes():
        result["value"] = True
        dialog.destroy()
        
    def on_no():
        result["value"] = False
        dialog.destroy()
        
    btn_yes = tk.Button(
        btn_frame, 
        text="Sí, Ejecutar", 
        command=on_yes,
        bg="#6a9955", 
        fg="black", 
        font=(Styles.FONT_FAMILY, 11, "bold"),
        padx=15, pady=5,
        relief="raised",
        cursor="hand2"
    )
    btn_yes.pack(side="right", padx=10)
    
    btn_no = tk.Button(
        btn_frame, 
        text="Cancelar", 
        command=on_no,
        bg="#f44336", 
        fg="black", 
        font=(Styles.FONT_FAMILY, 11),
        padx=15, pady=5,
        relief="raised",
        cursor="hand2"
    )
    btn_no.pack(side="right")
    
    # Handle window close button (X)
    dialog.protocol("WM_DELETE_WINDOW", on_no)
    
    # Modal wait
    dialog.grab_set()
    dialog.wait_window()
    
    return result["value"]

def execute_clipboard_command(app_instance, command):
    """
    Ejecuta el comando en un hilo separado para no congelar la UI.
    """
    def _run():
        try:
            # Obtener raíz del proyecto
            cwd = None
            if hasattr(app_instance, 'controller') and hasattr(app_instance.controller, 'project_manager'):
                cwd = app_instance.controller.project_manager.current_project_path
            
            if not cwd:
                cwd = os.getcwd()

            logging.info(f"Ejecutando comando en {cwd}: {command}")
            
            # Ejecutar
            # Usamos shell=True para permitir pipes y &&, aunque sea menos seguro, 
            # el usuario ya confirmó la ejecución.
            result = subprocess.run(
                command, 
                shell=True, 
                cwd=cwd, 
                capture_output=True, 
                text=True
            )
            
            output = result.stdout
            error = result.stderr
            
            msg = f"Resultado del comando:\n\n{output}"
            if error:
                msg += f"\n\nErrores/Warnings:\n{error}"
                
            logging.info(f"Comando terminado. Return code: {result.returncode}")
            
            # Mostrar resultado en UI (thread-safe ish con tkinter message box, 
            # a veces da problemas desde threads, pero messagebox suele bloquear 
            # o requerir after. Probemos invocando via after)
            
            def show_result():
                if result.returncode == 0:
                    tk.messagebox.showinfo("Comando Ejecutado", msg)
                else:
                    tk.messagebox.showerror("Error en Comando", msg)
            
            app_instance.root.after(0, show_result)
            
        except Exception as e:
            logging.error(f"Error ejecutando comando: {e}")
            app_instance.root.after(0, lambda: tk.messagebox.showerror("Error", f"Error ejecutando comando: {e}"))

    threading.Thread(target=_run, daemon=True).start()
