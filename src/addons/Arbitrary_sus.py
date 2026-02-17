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

def identify_best_file(file_list, search_text):
    """
    Identifica el archivo más probable comparando coincidencia de tokens únicos.
    OPTIMIZACIÓN: Usa los tokens más largos y únicos para mayor discriminación y velocidad.
    """
    # Tokenizar y buscar palabras largas (más discriminatorias)
    # Palabras de 5+ caracteres
    all_tokens = re.findall(r'\b\w{5,}\b', search_text.lower())
    
    # Análisis de frecuencia simple para descartar muy comunes si fuera necesario,
    # pero por ahora simplemente cogemos las más largas.
    # Ordenar por longitud descendente
    all_tokens.sort(key=len, reverse=True)
    
    # Nos quedamos con el top 50 de tokens más largos únicos
    search_tokens = set()
    for t in all_tokens:
        if t not in search_tokens:
            search_tokens.add(t)
            if len(search_tokens) >= 50:
                break
                
    if not search_tokens:
        # Fallback a tokens más cortos si no hay largos
        search_tokens = set(re.findall(r'\b\w{3,}\b', search_text.lower())[:50])

    if not search_tokens:
        return None
        
    best_score = 0
    best_file = None
    
    logging.info(f"🔎 [Arbitrary] Identificando fichero con {len(search_tokens)} tokens clave...")
    
    for file_info in file_list:
        if isinstance(file_info, dict):
            file_path = file_info.get('full_path')
        else:
            file_path = file_info

        if not file_path or not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
            # Contar cuántos tokens de búsqueda aparecen en el archivo
            matches = 0
            for token in search_tokens:
                if token in content:
                    matches += 1
            
            # Score simple: porcentaje de tokens encontrados
            score = matches / len(search_tokens)
            
            if score > best_score:
                best_score = score
                best_file = file_path
                
            # Si encontramos casi todos, es un match muy probable
            if best_score >= 0.9:
                break
                
        except Exception:
            pass
            
    logging.info(f"👉 [Arbitrary] Fichero ganador: {os.path.basename(best_file) if best_file else 'Ninguno'} (Score: {best_score:.2f})")
    return best_file

def find_similar_region(file_list, search_text, step=None):
    """
    Busca la región de código más similar.
    OPTIMIZACIÓN:
    1. Identifica fichero candidato.
    2. Busca Líneas Ancla (Anchor Lines) exactas para posicionamiento instantáneo O(1).
    3. Fallback a ventana deslizante optimizada si falla el ancla.
    """
    best_match = None
    best_ratio = 0
    best_file = None
    best_line_num = -1

    if not file_list:
        return None, None, 0, -1

    # PASO 1: Identificar el fichero único
    candidate_file = identify_best_file(file_list, search_text)
    
    if not candidate_file:
        return None, None, 0, -1
        
    target_files = [candidate_file]
    search_lines = search_text.split('\n')
    search_lines_count = len(search_lines)
    window_size = search_lines_count
    
    logging.info(f"🔍 [Arbitrary] Escaneando: {candidate_file}")

    for file_path in target_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            lines = content.split('\n') # Mantener saltos para índices
            
            if len(lines) < 1: continue

            # --- ESTRATEGIA 1: ANCHOR LINES (O(1)) ---
            # Buscar las cadenas más largas y únicas del clipboard
            # Filtramos líneas vacías o muy cortas
            valid_lines = [l.strip() for l in search_lines if len(l.strip()) > 10]
            # Ordenamos por longitud descendente
            valid_lines.sort(key=len, reverse=True)
            
            anchor_found = False
            
            # Probamos con las 3 mejores anclas
            for anchor in valid_lines[:3]:
                # Buscar ancla en el contenido
                anchor_idx = content.find(anchor)
                if anchor_idx != -1:
                    # Ancla encontrada!
                    # Calculamos en qué línea está
                    pre_content = content[:anchor_idx]
                    anchor_line_num = pre_content.count('\n') + 1
                    
                    # Definimos ventana tentativa alrededor de esa línea
                    # El anchor en search_text está en la posición X
                    # En file está en position Y
                    # Intentamos alinear el inicio
                    
                    # Find anchor line index in search_text
                    search_anchor_idx = -1
                    for i, sl in enumerate(search_lines):
                        if anchor in sl:
                            search_anchor_idx = i
                            break
                    
                    start_line_est = max(0, anchor_line_num - search_anchor_idx - 1)
                    end_line_est = start_line_est + window_size + 2 # un margen
                    
                    window_lines = lines[start_line_est:end_line_est]
                    window_text = "\n".join(window_lines) # Reconstruir con saltos originales (aprox)
                    
                    matcher = difflib.SequenceMatcher(None, search_text, window_text)
                    ratio = matcher.quick_ratio()
                    
                    logging.info(f"⚓ [Arbitrary] Anchor Hit: '{anchor[:30]}...' en línea {anchor_line_num}. Ratio: {ratio:.2f}")
                    
                    if ratio > 0.6: # Si es decente, asumimos que es el sitio
                        return window_text, file_path, matcher.ratio(), start_line_est + 1

            # --- ESTRATEGIA 2: SLIDING WINDOW (Fallback) ---
            if step is not None and step > 0:
                current_step = step
            else:
                if len(lines) < 1000:
                    current_step = 1
                elif search_lines_count > 50:
                    current_step = 5 # Salto agresivo
                elif search_lines_count > 20:
                    current_step = 2
                else:
                    current_step = 2 
            
            # Usar índices sobre lista de líneas
            limit = max(1, len(lines) - window_size + 1)
            
            for i in range(0, limit, current_step):
                # Construcción optimizada: slice list
                window_slice = lines[i : i + window_size]
                # Join cuesta, pero es necesario para diff.
                # Optimization: check length sum first? No, too complex python side.
                window_text = "\n".join(window_slice)
                
                # Validación longitud rapida
                if abs(len(window_text) - len(search_text)) > len(search_text) * 0.5:
                   continue

                # Quick Ratio
                matcher = difflib.SequenceMatcher(None, search_text, window_text)
                if matcher.quick_ratio() < 0.5: 
                    continue
                
                ratio = matcher.ratio()
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = window_text
                    best_file = file_path
                    best_line_num = i + 1
                    
                    if ratio >= 0.95: # Early exit
                        return best_match, best_file, best_ratio, best_line_num
                                
        except Exception as e:
            logging.error(f"Error en búsqueda: {e}")
            pass

    return best_match, best_file, best_ratio, best_line_num

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

def show_popup(clipboard_text, match_text, file_path, ratio, line_num):
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
    
    margin_var = tk.IntVar(value=500)
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
    txt_clip.config(state="disabled")
    txt_clip.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    # 2. Editor
    lbl_edit = tk.Label(content_frame, text="✏️ Editor (VS Code Style)", bg=THEME["bg"], fg="#dcdcaa", font=FONT_UI)
    lbl_edit.grid(row=0, column=1, sticky="w", padx=5, pady=(5,0))
    
    txt_edit = create_styled_text_widget(content_frame, editable=True)
    # Borde para distinguir editor
    txt_edit.config(bd=1, relief="solid") 
    txt_edit.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
    


    # --- UPDATES & EVENTS ---
    
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

    txt_edit.bind("<KeyRelease>", on_edit_change)
    txt_edit.bind("<Control-z>", on_undo)
    txt_edit.bind("<Control-Z>", on_undo)  # Con Shift/CapsLock
    txt_edit.bind("<Control-y>", on_redo)
    txt_edit.bind("<Control-Y>", on_redo)
    # macOS support (Command key)
    txt_edit.bind("<Command-z>", on_undo)
    txt_edit.bind("<Command-Z>", on_undo)
    txt_edit.bind("<Command-y>", on_redo)
    txt_edit.bind("<Command-Y>", on_redo)
    txt_edit.bind("<Command-Shift-z>", on_redo)  # macOS usa Cmd+Shift+Z para redo
    txt_edit.bind("<Command-Shift-Z>", on_redo)

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
        

        # Scroll to match logic
        # match_start_line was already computed above for highlighting
        match_line = text_before_match.count('\n') + 1 if rel_pos >= 0 and match_text else 1
        
        # Center the view on this line
        # see() makes it visible, usually at bottom or top if scrolling needed.
        # To center, we can try to see a few lines below it too if possible
        # Simple approach: see the line.
        txt_edit.see(f"{match_line}.0")
        
        # Try to center visually (approximate)
        # Force update to get height
        # popup.update_idletasks() 
        # But that might be slow/flickering.
        # Just use 'see' + centered logic via yview_moveto is hard without knowing total lines accurately rendered.
        # 'see' is robust. Let's stick to 'see' but also try to see a line further down to push match up?
        # No, let's just use see(line).Ideally use `txt.yview_pickplace(line)` but it's deprecated for `see`.
        # Actually, if we want to center, we can calculate fraction.
        # total_lines = full_block.count('\n') + 1
        # fraction = (match_line - 10) / total_lines # approximate centering
        # txt_edit.yview_moveto(max(0, fraction))
        
        # Robust centering:
        try:
             # Just ensures it is visible. 
             txt_edit.see(f"{match_line}.0")
             
             # Attempt to center: scroll so match_line is middle
             # Get total lines visible (height)
             visible_lines = 20 # assumption or txt_edit.cget('height')
             target_top = max(1, match_line - 10)
             txt_edit.yview(target_top)
        except:
            pass

    scale_margin.config(command=update_view)
    update_view() # Initial load



def run_arbitrary_search(app_instance):
    try:
        clipboard_text = pyperclip.paste().strip()
        if not clipboard_text:
            logging.info("Arbitrary: Portapapeles vacío.")
            return

        code_files = []
        
        # Get files from the CodeView TreeView (only listed files, not entire project)
        if hasattr(app_instance, 'layout') and hasattr(app_instance.layout, 'code_view'):
            code_view = app_instance.layout.code_view
            if hasattr(code_view, 'tree'):
                # Get all items from the TreeView
                for item_id in code_view.tree.get_children():
                    # The full path is stored in the tags of each item
                    tags = code_view.tree.item(item_id, 'tags')
                    if tags:
                        # tags is a tuple, first element is the full path
                        file_path = tags[0] if isinstance(tags, (list, tuple)) else tags
                        if file_path and os.path.exists(file_path):
                            code_files.append(file_path)
        
        # Fallback to all project files if no files found in TreeView
        if not code_files:
            if hasattr(app_instance, 'controller') and hasattr(app_instance.controller, 'project_manager'):
                files_data = app_instance.controller.project_manager.get_files()
                code_files = [f['path'] for f in files_data]
                logging.info("Arbitrary: Usando todos los ficheros del proyecto (fallback).")
        
        if not code_files:
             tk.messagebox.showwarning("Arbitrary", "No hay archivos de código procesados.")
             return

        logging.info(f"Arbitrary: Buscando en {len(code_files)} ficheros listados.")
        arbitrary_step = getattr(app_instance, 'arbitrary_step', 1)

        app_instance.root.config(cursor="watch")
        app_instance.root.update()

        
        match, file_path, ratio, line_num = find_similar_region(code_files, clipboard_text, step=arbitrary_step)
        
        app_instance.root.config(cursor="")

        if match and ratio > 0.1:
            show_popup(clipboard_text, match, file_path, ratio, line_num)
        else:
            logging.info("Arbitrary: Sin coincidencias.")

    except Exception as e:
        app_instance.root.config(cursor="")
        logging.error(f"Error: {e}")
        tk.messagebox.showerror("Error", str(e))

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
