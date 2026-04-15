import tkinter as tk
from tkinter import ttk, messagebox
import os
import pyperclip
import logging
import difflib
import re
import subprocess
import shlex
import threading

# --- PYGMENTS (Syntax Highlighting profesional) ---
from pygments import lex
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.token import Token

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

FONT_CODE = ("Consolas", 14) 
FONT_UI = ("Segoe UI", 14) # Aumentado tamano base a 14

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


def find_unique_substring(search_text, loaded_files, min_len=20, max_len=None, step=10):
    """
    Algoritmo de búsqueda por coincidencia exacta única.

    Estrategia:
    - Toma substrings de tamaño creciente del texto del portapapeles.
    - Para cada tamaño, prueba múltiples posiciones de inicio (inicio, centro, fin).
    - Busca ese substring exacto en todos los ficheros cargados.
    - Cuando exactamente 1 fichero contiene el substring → coincidencia única encontrada.
    - Devuelve (match_text, file_path, line_num) o (None, None, -1) si no se encuentra.

    Parámetros:
    - min_len: longitud mínima del substring a probar.
    - max_len: longitud máxima (por defecto, longitud total del texto).
    - step: incremento de tamaño entre iteraciones.
    """
    text_len = len(search_text)
    if max_len is None:
        max_len = text_len

    # Aseguramos que min_len no supere el texto
    min_len = min(min_len, text_len)
    max_len = min(max_len, text_len)

    logging.info(f"🔎 [Arbitrary] Buscando substring único. Texto: {text_len} chars, "
                 f"rango [{min_len}..{max_len}], step={step}")

    best_result = None  # (substring, file_path, line_num)
    best_len = 0

    for substr_len in range(min_len, max_len + 1, step):
        # Posiciones de inicio a probar: inicio, 1/4, centro, 3/4, fin
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

            # Ignorar substrings que sean solo espacios/saltos de línea
            if not substring.strip():
                continue

            # Buscar en todos los ficheros
            matching_files = []
            for file_path, content in loaded_files:
                if substring in content:
                    matching_files.append(file_path)

            if len(matching_files) == 1:
                # ¡Coincidencia única encontrada!
                file_path = matching_files[0]
                content = next(c for fp, c in loaded_files if fp == file_path)

                # Calcular número de línea
                idx = content.find(substring)
                line_num = content[:idx].count('\n') + 1

                logging.info(
                    f"✅ [Arbitrary] Substring único encontrado! "
                    f"Len={substr_len}, pos={start}, fichero={os.path.basename(file_path)}, "
                    f"línea={line_num}"
                )
                # Guardamos el mejor resultado (mayor substring único)
                if substr_len > best_len:
                    best_len = substr_len
                    best_result = (substring, file_path, line_num)

    if best_result:
        return best_result

    logging.info("⚠️ [Arbitrary] No se encontró substring único. Sin coincidencias.")
    return None, None, -1


def find_similar_region(file_list, search_text, step=None, forced_file=None):
    """
    Busca la región de código usando el algoritmo de substring único.

    1. Carga todos los ficheros en memoria.
    2. Si forced_file, filtra solo ese fichero.
    3. Llama a find_unique_substring para encontrar la coincidencia exacta única.
    4. Devuelve (match_text, file_path, ratio, line_num).

    El 'ratio' devuelto es 1.0 si se encontró coincidencia exacta, 0 si no.
    """
    if not file_list:
        return None, None, 0, -1

    # Cargar contenidos
    loaded_files = _load_file_contents(file_list)

    if not loaded_files:
        return None, None, 0, -1

    if forced_file:
        # Filtrar solo el fichero forzado
        loaded_files = [(fp, c) for fp, c in loaded_files if fp == forced_file]
        logging.info(f"🎯 [Arbitrary] Fichero forzado: {os.path.basename(forced_file)}")

    text_len = len(search_text)

    # Parámetros adaptativos según tamaño del texto
    if text_len < 50:
        min_len = max(10, text_len // 2)
        substr_step = 5
    elif text_len < 200:
        min_len = 20
        substr_step = 10
    elif text_len < 1000:
        min_len = 30
        substr_step = 15
    else:
        min_len = 40
        substr_step = 20

    substring, file_path, line_num = find_unique_substring(
        search_text, loaded_files,
        min_len=min_len,
        max_len=text_len,
        step=substr_step
    )

    if substring and file_path:
        return substring, file_path, 1.0, line_num

    return None, None, 0, -1


def identify_best_file(file_list, search_text):
    """
    Identifica el archivo candidato usando el algoritmo de substring único.
    Devuelve (file_path, score) donde score=1.0 si hay coincidencia única, 0 si no.
    Mantenida por compatibilidad con el flujo existente.
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
        logging.info(f"👉 [Arbitrary] Fichero identificado: {os.path.basename(file_path)} (Score: 1.0)")
        return file_path, 1.0

    logging.info("👉 [Arbitrary] No se pudo identificar fichero único.")
    return None, 0

def get_match_context(file_path, match_text, approximate_line_num, margin=150):
    """(Sin cambios funcionales - extracción de contexto)"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        content_norm = content.replace("\r\n", "\n")
        match_norm = match_text.replace("\r\n", "\n")
        
        pattern = re.escape(match_norm)
        matches = list(re.finditer(pattern, content_norm))
        
        if not matches:
             return None, 0, 0

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
            return None, 0, 0
            
        start_idx = selected_match.start()
        end_idx = selected_match.end()
        
        context_start = max(0, start_idx - margin)
        context_end = min(len(content_norm), end_idx + margin)
        
        full_block = content_norm[context_start:context_end]
        
        return full_block, context_start, context_end, start_idx

    except Exception as e:
        logging.error(f"❌ Error obteniendo contexto: {e}")
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
            
        logging.info(f"✅ Archivo modificado: {file_path}")
        return True
    except Exception as e:
        logging.error(f"❌ Error escribiendo archivo: {e}")
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

def configure_tags(text_widget):
    """
    Configura los tags de colores estilo VS Code en el widget de texto.
    Crea un tag Tkinter para cada tipo de token definido en VSCODE_TOKEN_COLORS.
    """
    for token_type, style_dict in VSCODE_TOKEN_COLORS.items():
        tag_name = _get_token_tag_name(token_type)
        config = {}
        if "fg" in style_dict:
            config["foreground"] = style_dict["fg"]
        if style_dict.get("bold"):
            # Crear font con bold
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
    
    # Obtener lexer adecuado
    lexer = _get_lexer_for_file(file_path)
    
    # Tokenizar y aplicar tags
    # Rastreamos posición como (línea, columna) para eficiencia con Tkinter indices
    line = 1
    col = 0
    
    for token_type, token_value in lex(content, lexer):
        if not token_value:
            continue
        
        # Calcular posición inicio
        start_index = f"{line}.{col}"
        
        # Calcular posición final contando newlines dentro del token
        lines_in_token = token_value.split('\n')
        if len(lines_in_token) > 1:
            # Token multi-línea (ej: comentario de bloque, string multilínea)
            end_line = line + len(lines_in_token) - 1
            end_col = len(lines_in_token[-1])
        else:
            end_line = line
            end_col = col + len(token_value)
        
        end_index = f"{end_line}.{end_col}"
        
        # Solo aplicar tag si no es texto plano (Token.Text)
        if token_type != Token.Text and token_type != Token.Text.Whitespace:
            # Resolver estilo (subiendo jerarquía si es necesario)
            style = _resolve_token_style(token_type)
            if style.get("fg") and style["fg"] != "#d4d4d4":
                tag_name = _get_token_tag_name(token_type)
                # Asegurar que el tag existe
                if tag_name not in text_widget.tag_names():
                    config = {}
                    if "fg" in style:
                        config["foreground"] = style["fg"]
                    if style.get("bold"):
                        config["font"] = (FONT_CODE[0], FONT_CODE[1], "bold")
                    if style.get("italic"):
                        config["font"] = (FONT_CODE[0], FONT_CODE[1], "italic")
                    text_widget.tag_configure(tag_name, **config)
                text_widget.tag_add(tag_name, start_index, end_index)
        
        # Actualizar posición
        if len(lines_in_token) > 1:
            line = end_line
            col = end_col
        else:
            col = end_col


def create_styled_text_widget(parent, editable=True):
    """Crea un widget de texto preconfigurado con estilo VS Code"""
    txt = tk.Text(
        parent, 
        font=FONT_CODE, 
        bg=THEME["bg"], 
        fg=THEME["fg"], 
        relief="flat", 
        wrap="none",
        insertbackground=THEME["cursor"], # Color del cursor
        selectbackground=THEME["select_bg"],
        undo=True,              # Habilitar pila de undo/redo
        maxundo=-1,             # Historial ilimitado
        autoseparators=True     # Separadores automáticos entre acciones
    )
    # Configurar tags inicialmente
    configure_tags(txt)
    return txt

def show_popup(clipboard_text, match_text, file_path, ratio, line_num, app_instance=None):
    """
    Muestra popup de 3 paneles con estilo VS Code Highlighting.
    """
    if not match_text:
        return

    # Estado mutable
    state = {
        "start_idx": 0,
        "end_idx": 0,
        "editor_job": None # Para debounce
    }

    # Popup
    popup = tk.Toplevel()
    popup.title(f"✨ Comparación y Edición - {os.path.basename(file_path)}")
    
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
        font=("Segoe UI", 16, "bold"), fg="#569cd6", bg=THEME["bg"]
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
        font=("Segoe UI", 16), fg="#ce9178", bg=THEME["bg"]
    )
    lbl_path.pack(side="left", padx=5)

    # Label: Line
    tk.Label(
        info_frame, text="| 🔢 Línea aprox:", 
        font=("Segoe UI", 16, "bold"), fg="#569cd6", bg=THEME["bg"]
    ).pack(side="left", padx=(15, 0))
    
    tk.Label(
        info_frame, text=str(line_num), 
        font=("Segoe UI", 16), fg="#b5cea8", bg=THEME["bg"]
    ).pack(side="left", padx=5)

    # Header Controls
    control_frame = tk.Frame(popup, bg=THEME["bg"])
    control_frame.pack(fill="x", padx=10, pady=5)
    
    lbl_scale = tk.Label(control_frame, text="Margen de Contexto:", bg=THEME["bg"], fg="#569cd6", font=FONT_UI)
    lbl_scale.pack(side="left", padx=(0, 10))
    
    margin_var = tk.IntVar(value=5000)
    scale_margin = tk.Scale(
        control_frame, from_=0, to=5000, orient="horizontal", variable=margin_var,
        bg=THEME["bg"], fg=THEME["fg"], highlightthickness=0, length=400,
        sliderrelief="flat", activebackground="#569cd6", troughcolor="#333333"
    )
    scale_margin.pack(side="left")

    # --- BUTTONS (Header Right) ---
    def on_accept():
        # txt_edit se define más abajo, pero estará disponible cuando se pulse el botón
        new_content = txt_edit.get("1.0", "end-1c") 
        # Confirmación automática
        success = apply_replacement(file_path, state["start_idx"], state["end_idx"], new_content)
        if success:
            # messagebox.showinfo("Éxito", "Actualizado.") # Removed popup
            popup.destroy()

    # Cancel button (Rightmost)
    tk.Button(
        control_frame, text="❌ Cancelar", command=popup.destroy, 
        bg="#f44336", fg="black", font=FONT_UI, padx=10, pady=2
    ).pack(side="right", padx=5)

    # Accept button (Left of Cancel)
    tk.Button(
        control_frame, text="✅ Aceptar y Sustituir", command=on_accept, 
        bg="#6a9955", fg="black", font=FONT_UI, padx=10, pady=2
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
        popup.after_idle(lambda: run_arbitrary_search_with_text(app_instance, selected_text))
        return "break"

    txt_clip.bind("<Button-2>", on_clip_right_click)
    txt_clip.bind("<Button-3>", on_clip_right_click)
    txt_clip.bind("<Control-Button-1>", on_clip_right_click)
    txt_clip.config(state="disabled")
    txt_clip.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    lbl_edit = tk.Label(content_frame, text="✏️ Editor (VS Code Style)", bg=THEME["bg"], fg="#dcdcaa", font=FONT_UI)
    lbl_edit.grid(row=0, column=1, sticky="w", padx=5, pady=(5,0))
    
    txt_edit = create_styled_text_widget(content_frame, editable=True)
    # Borde para distinguir editor
    txt_edit.config(bd=1, relief="solid") 
    txt_edit.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

    content_frame.columnconfigure(2, weight=0)  # columna para scrollbar compartida

    # Scrollbar independiente para cada panel (no sincronizamos por fracción,
    # sino por unidades absolutas en el mousewheel para mantener la alineación)
    scroll_clip = ttk.Scrollbar(content_frame, orient="vertical", command=txt_clip.yview)
    scroll_clip.grid(row=1, column=0, sticky="nse", pady=5)
    txt_clip.config(yscrollcommand=scroll_clip.set)

    scroll_edit = ttk.Scrollbar(content_frame, orient="vertical", command=txt_edit.yview)
    scroll_edit.grid(row=1, column=1, sticky="nse", pady=5)
    txt_edit.config(yscrollcommand=scroll_edit.set)




    
    def on_edit_change(event=None):
        """Re-highlighter con debounce simple"""
        if state["editor_job"]:
            popup.after_cancel(state["editor_job"])
        # Esperar 300ms de inactividad para colorear (performance)
        state["editor_job"] = popup.after(300, lambda: highlight_syntax(txt_edit, file_path))

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

    def update_view(val=None):
        margin = margin_var.get()
        full_block, start_idx, end_idx, match_abs_start = get_match_context(file_path, match_text, line_num, margin=margin)
        
        if full_block is None:
            return
            
        state["start_idx"] = start_idx
        state["end_idx"] = end_idx
        
        # Update Editor
        txt_edit.delete("1.0", "end")
        txt_edit.insert("1.0", full_block)
        highlight_syntax(txt_edit, file_path)
        
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
            
            txt_edit.tag_configure("match_highlight", background="#2d2d2d")
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



    scale_margin.config(command=update_view)
    update_view() # Initial load



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
        font=("Segoe UI", 13),
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
            font=("Segoe UI", 12),
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
        font=("Segoe UI", 11, "bold"),
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

    # Prioridad: ficheros visibles/listados en CodeView
    if hasattr(app_instance, 'layout') and hasattr(app_instance.layout, 'code_view'):
        code_view = app_instance.layout.code_view
        if hasattr(code_view, 'tree'):
            for item_id in code_view.tree.get_children():
                tags = code_view.tree.item(item_id, 'tags')
                if tags:
                    file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                    if file_path and os.path.exists(file_path):
                        code_files.append(file_path)

    # Fallback: todos los ficheros procesados del proyecto
    if not code_files:
        if hasattr(app_instance, 'controller') and hasattr(app_instance.controller, 'project_manager'):
            files_data = app_instance.controller.project_manager.get_files()
            code_files = [f['path'] for f in files_data]
            logging.info("Arbitrary: Usando todos los ficheros del proyecto (fallback).")

    return code_files


def run_arbitrary_search_with_text(app_instance, search_text):
    try:
        search_text = (search_text or "").strip()
        if not search_text:
            logging.info("Arbitrary: Texto de búsqueda vacío.")
            return

        code_files = _get_code_files_for_arbitrary_search(app_instance)
        if not code_files:
             tk.messagebox.showwarning("Arbitrary", "No hay archivos de código procesados.")
             return

        logging.info(f"Arbitrary: Buscando en {len(code_files)} ficheros listados.")

        app_instance.root.config(cursor="watch")
        app_instance.root.update()

        # El nuevo algoritmo de substring único determina el fichero automáticamente
        match, file_path, ratio, line_num = find_similar_region(
            code_files, search_text
        )

        app_instance.root.config(cursor="")

        if match and file_path:
            show_popup(search_text, match, file_path, ratio, line_num, app_instance=app_instance)
        else:
            logging.info("Arbitrary: Sin coincidencias exactas únicas.")

    except Exception as e:
        app_instance.root.config(cursor="")
        logging.error(f"Error: {e}")
        tk.messagebox.showerror("Error", str(e))


def run_arbitrary_search(app_instance):
    clipboard_text = pyperclip.paste().strip()
    if not clipboard_text:
        logging.info("Arbitrary: Portapapeles vacío.")
        return

    run_arbitrary_search_with_text(app_instance, clipboard_text)

def process_smart_paste(app_instance):
    """
    Maneja la lógica de pegado inteligente lanzada por Shift+Click.
    1. Si es una región (#region "name") -> Reemplazo automático.
    2. Si NO es región -> Abre ventana de sustitución manual (Arbitrary Search).
    
    Supports multiple comment styles:
    - // #region "name" (JS/TS/C++/Java)
    - # #region "name" (Python/Shell)
    - -- #region "name" (SQL/Lua)
    - /* #region "name" */ (CSS/C)
    - <!-- #region "name" --> (HTML/XML)
    """
    try:
        content = pyperclip.paste()
        if not content:
            logging.info("Smart Paste: Portapapeles vacío.")
            return

        # 0. Chequeo de Comando de Consola
        if is_console_command(content):
            # Preguntar al usuario con ventana topmost
            if show_global_confirmation_dialog("Ejecutar Comando", f"¿Quieres ejecutar este comando en la raíz del proyecto?\n\n{content}"):
                execute_clipboard_command(app_instance, content)
                return

        # 1. Chequeo de Región
        # Regex para detectar región con múltiples estilos de comentarios
        # Captura el nombre de la región independientemente del estilo de comentario
        region_patterns = [
            # Line comment styles: //, #, --
            r'(?://|#|--)[ \t]*#?region[ \t]+["\']?([^"\'\n\r]+?)["\']?[ \t]*(?:\r?\n|$)',
            # Block comment style: /* */
            r'/\*[ \t]*#?region[ \t]+["\']?([^"\'\n\r]+?)["\']?[ \t]*\*/',
            # HTML comment style: <!-- -->
            r'<!--[ \t]*#?region[ \t]+["\']?([^"\'\n\r]+?)["\']?[ \t]*-->',
        ]
        
        region_name = None
        for pattern in region_patterns:
            match = re.search(pattern, content)
            if match:
                region_name = match.group(1).strip()
                break
        
        if region_name:
             logging.info(f"📋 Smart Paste: Detectada región '{region_name}' en portapapeles.")
             
             if hasattr(app_instance, 'controller'):
                 success = app_instance.controller.replace_region_from_clipboard(region_name, content)
                 if success:
                     logging.info(f"Smart Paste: Región '{region_name}' actualizada correctamente.")
                 else:
                     tk.messagebox.showwarning("Smart Paste", f"⚠️ No se encontró la región '{region_name}' en el proyecto.")
             return

        # 2. Fallback: Sustitución Manual
        logging.info("📋 Smart Paste: No es región, lanzando búsqueda arbitraria.")
        run_arbitrary_search(app_instance)

    except Exception as e:
        logging.error(f"❌ Error en Smart Paste: {e}")
        tk.messagebox.showerror("Error", f"Error procesando portapapeles: {e}")

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
        font=("Segoe UI", 12),
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
        font=("Segoe UI", 11, "bold"),
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
        font=("Segoe UI", 11),
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

            logging.info(f"🚀 Ejecutando comando en {cwd}: {command}")
            
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
                
            logging.info(f"✅ Comando terminado. Return code: {result.returncode}")
            
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
