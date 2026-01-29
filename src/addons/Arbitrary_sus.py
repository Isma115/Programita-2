import tkinter as tk
from tkinter import ttk, messagebox
import os
import pyperclip
import logging
import difflib
import re

# --- CONFIGURACIÓN DE ESTILOS VS CODE ---
THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "cursor": "#aeafad",
    "select_bg": "#264f78",
    "line_num_fg": "#858585",
    "sidebar_bg": "#252526",
    
    # Sintaxis
    "keyword": "#569cd6",      # blue
    "control": "#c586c0",      # purple
    "string": "#ce9178",       # orange
    "comment": "#6a9955",      # green
    "number": "#b5cea8",       # light green
    "function": "#dcdcaa",     # yellow
    "class": "#4ec9b0",        # teal
    "operator": "#d4d4d4",     # white/grey
    "bracket": "#ffd700",      # gold (custom visibility)
}

FONT_CODE = ("Consolas", 14) 
FONT_UI = ("Segoe UI", 14) # Aumentado tamano base a 14

def identify_best_file(file_list, search_text):
    """
    Identifica el archivo más probable comparando coincidencia de tokens únicos.
    Retorna la ruta del archivo ganador.
    """
    # Tokenizar search_text (palabras de 3+ chars)
    search_tokens = set(re.findall(r'\b\w{3,}\b', search_text.lower()))
    if not search_tokens:
        return None
        
    best_score = 0
    best_file = None
    
    logging.info(f"🔎 [Arbitrary] Identificando fichero candidato entre {len(file_list)} archivos...")
    
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
            matches = sum(1 for token in search_tokens if token in content)
            
            # Score simple: porcentaje de tokens encontrados
            score = matches / len(search_tokens)
            
            if score > best_score:
                best_score = score
                best_file = file_path
                
            # Si encontramos todos los tokens, es un match perfecto para candidato
            if best_score >= 1.0:
                break
                
        except Exception:
            pass
            
    logging.info(f"👉 [Arbitrary] Fichero ganador: {os.path.basename(best_file) if best_file else 'Ninguno'} (Score: {best_score:.2f})")
    
    # Si el score es muy bajo, quizás no merece la pena, pero probaremos el mejor que haya
    if best_score < 0.1:
        logging.warning("⚠️ Score de coincidencia de fichero muy bajo, la búsqueda puede fallar.")
        
    return best_file

def find_similar_region(file_list, search_text, step=None):
    """
    Busca la región de código más similar.
    OPTIMIZACIÓN: Primero identifica el fichero candidato y luego busca ventana solo en ese.
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
        
    # Reducimos la lista a solo el candidato
    target_files = [candidate_file]

    search_lines_count = search_text.count('\n') + 1
    window_size = search_lines_count
    
    logging.info(f"🔍 [Arbitrary] Iniciando escaneo detallado en: {candidate_file}. Step: {step}")

    for file_path in target_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if len(lines) < 1:
                continue
            
            # Si es muy pequeño, quizás ajustar
            if len(lines) < window_size * 0.5:
                # Permitir búsqueda aunque sea pequeño si es el candidato
                pass 

            if step is not None and step > 0:
                current_step = step
            else:
                current_step = 1 if len(lines) < 1000 else 2 
            
            for i in range(0, max(1, len(lines) - window_size + 1), current_step):
                window_lines = lines[i : i + window_size]
                window_text = "".join(window_lines)
                
                # Validación pre-difflib
                if abs(len(window_text) - len(search_text)) > len(search_text) * 0.5:
                   ratio = 0
                else:
                    ratio = difflib.SequenceMatcher(None, search_text, window_text).ratio()
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = window_text
                    best_file = file_path
                    best_line_num = i + 1
                    
                    if ratio >= 0.98:
                        return best_match, best_file, best_ratio, best_line_num
                                
        except Exception:
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

# === HIGHILIGHTING LOGIC ===
def configure_tags(text_widget):
    """Configura los tags de colores estilo VS Code en el widget de texto"""
    text_widget.tag_configure("TOKEN_KEYWORD", foreground=THEME["keyword"])
    text_widget.tag_configure("TOKEN_CONTROL", foreground=THEME["control"])
    text_widget.tag_configure("TOKEN_STRING", foreground=THEME["string"])
    text_widget.tag_configure("TOKEN_COMMENT", foreground=THEME["comment"])
    text_widget.tag_configure("TOKEN_NUMBER", foreground=THEME["number"])
    text_widget.tag_configure("TOKEN_FUNCTION", foreground=THEME["function"])
    text_widget.tag_configure("TOKEN_CLASS", foreground=THEME["class"])
    text_widget.tag_configure("TOKEN_OPERATOR", foreground=THEME["operator"])

def highlight_syntax(text_widget):
    """Aplica resaltado de sintaxis usando regex simple"""
    content = text_widget.get("1.0", tk.END)
    
    # Limpiar tags previos
    for tag in text_widget.tag_names():
        if tag.startswith("TOKEN_"):
            text_widget.tag_remove(tag, "1.0", tk.END)
            
    # PATRONES REGEX
    
    # 1. Comentarios (Alta prioridad)
    # Soporte para # (python), // (js/cpp), /*...*/ (c-style), <!-- (html)
    patterns_comments = [
        r'(#.*)', 
        r'(//.*)',
        r'(/\*[\s\S]*?\*/)',
        r'(<!--[\s\S]*?-->)'
    ]
    for pat in patterns_comments:
        for match in re.finditer(pat, content):
            text_widget.tag_add("TOKEN_COMMENT", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
            
    # 2. Strings
    patterns_strings = [
        r'(".*?")',
        r"('.*?')",
        r'("""[\s\S]*?""")',
        r"('''[\s\S]*?''')"
    ]
    for pat in patterns_strings:
        for match in re.finditer(pat, content):
             # Evitar sobrescribir comentarios si ya se marcaron
             # (Este método es simple, lo ideal es un lexer real)
             # Chequeo simple: si el inicio no tiene ya tag de comment
             is_comment = False
             tags = text_widget.tag_names(f"1.0+{match.start()}c")
             if "TOKEN_COMMENT" in tags:
                 continue
                 
             text_widget.tag_add("TOKEN_STRING", f"1.0+{match.start()}c", f"1.0+{match.end()}c")

    # 3. Keywords & Control
    # Lista combinada multi-lenguaje
    keywords = r'\b(def|class|import|from|return|pass|lambda|with|as|global|nonlocal|assert|del|yield|raise|try|except|finally|if|elif|else|for|while|break|continue|in|is|not|and|or|True|False|None|self|var|let|const|function|async|await|new|this|extends|super|interface|implements|public|private|protected|static|void|int|float|string|bool)\b'
    
    for match in re.finditer(keywords, content):
        # Chequear conflictos
        start_idx = f"1.0+{match.start()}c"
        tags = text_widget.tag_names(start_idx)
        if "TOKEN_COMMENT" in tags or "TOKEN_STRING" in tags:
            continue
            
        word = match.group(0)
        # Separar control flow de keywords normales (visual)
        if word in ["if", "else", "elif", "for", "while", "break", "continue", "try", "except", "return"]:
            text_widget.tag_add("TOKEN_CONTROL", start_idx, f"1.0+{match.end()}c")
        else:
            text_widget.tag_add("TOKEN_KEYWORD", start_idx, f"1.0+{match.end()}c")

    # 4. Funciones (palabra seguida de paren abierto)
    # Exluimos keywords
    func_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    for match in re.finditer(func_pattern, content):
        start_pos = match.start(1)
        end_pos = match.end(1)
        
        start_idx = f"1.0+{start_pos}c"
        tags = text_widget.tag_names(start_idx)
        if "TOKEN_COMMENT" in tags or "TOKEN_STRING" in tags or "TOKEN_KEYWORD" in tags or "TOKEN_CONTROL" in tags:
            continue
            
        text_widget.tag_add("TOKEN_FUNCTION", start_idx, f"1.0+{end_pos}c")

    # 5. Números
    num_pattern = r'\b\d+\b'
    for match in re.finditer(num_pattern, content):
        start_idx = f"1.0+{match.start()}c"
        tags = text_widget.tag_names(start_idx)
        if "TOKEN_COMMENT" in tags or "TOKEN_STRING" in tags:
            continue
        text_widget.tag_add("TOKEN_NUMBER", start_idx, f"1.0+{match.end()}c")


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
        selectbackground=THEME["select_bg"]
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
    w, h = 1200, 800
    ws = popup.winfo_screenwidth()
    hs = popup.winfo_screenheight()
    x = (ws - w) // 2
    y = (hs - h) // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")
    
    popup.configure(bg=THEME["bg"])

    # Info Header (File Path & Line)
    info_frame = tk.Frame(popup, bg=THEME["bg"])
    info_frame.pack(fill="x", padx=10, pady=(10, 0))
    
    # Label: Archivo
    tk.Label(
        info_frame, text="📂 Archivo:", 
        font=("Segoe UI", 16, "bold"), fg=THEME["keyword"], bg=THEME["bg"]
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
        font=("Segoe UI", 16), fg=THEME["string"], bg=THEME["bg"]
    )
    lbl_path.pack(side="left", padx=5)

    # Label: Line
    tk.Label(
        info_frame, text="| 🔢 Línea aprox:", 
        font=("Segoe UI", 16, "bold"), fg=THEME["keyword"], bg=THEME["bg"]
    ).pack(side="left", padx=(15, 0))
    
    tk.Label(
        info_frame, text=str(line_num), 
        font=("Segoe UI", 16), fg=THEME["number"], bg=THEME["bg"]
    ).pack(side="left", padx=5)

    # Header Controls
    control_frame = tk.Frame(popup, bg=THEME["bg"])
    control_frame.pack(fill="x", padx=10, pady=5)
    
    lbl_scale = tk.Label(control_frame, text="Margen de Contexto:", bg=THEME["bg"], fg=THEME["keyword"], font=FONT_UI)
    lbl_scale.pack(side="left", padx=(0, 10))
    
    margin_var = tk.IntVar(value=500)
    scale_margin = tk.Scale(
        control_frame, from_=0, to=5000, orient="horizontal", variable=margin_var,
        bg=THEME["bg"], fg=THEME["fg"], highlightthickness=0, length=400,
        sliderrelief="flat", activebackground=THEME["keyword"], troughcolor="#333333"
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
        bg=THEME["comment"], fg="black", font=FONT_UI, padx=10, pady=2
    ).pack(side="right", padx=5)

    # Content Grid
    content_frame = tk.Frame(popup, bg=THEME["bg"])
    content_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    content_frame.columnconfigure(0, weight=1)
    content_frame.columnconfigure(1, weight=1)
    content_frame.rowconfigure(1, weight=1)
    content_frame.rowconfigure(3, weight=1)
    
    # --- PANELES ---
    
    # 1. Clipboard
    lbl_clip = tk.Label(content_frame, text="📋 Portapapeles", bg=THEME["bg"], fg=THEME["string"], font=FONT_UI)
    lbl_clip.grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
    
    txt_clip = create_styled_text_widget(content_frame, editable=False)
    txt_clip.insert("1.0", clipboard_text)
    highlight_syntax(txt_clip) # Highlight once
    txt_clip.config(state="disabled")
    txt_clip.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    # 2. Editor
    lbl_edit = tk.Label(content_frame, text="✏️ Editor (VS Code Style)", bg=THEME["bg"], fg=THEME["function"], font=FONT_UI)
    lbl_edit.grid(row=0, column=1, sticky="w", padx=5, pady=(5,0))
    
    txt_edit = create_styled_text_widget(content_frame, editable=True)
    # Borde para distinguir editor
    txt_edit.config(bd=1, relief="solid") 
    txt_edit.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
    
    # 3. Original
    lbl_orig = tk.Label(content_frame, text="🔒 Original", bg=THEME["bg"], fg=THEME["comment"], font=FONT_UI)
    lbl_orig.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=(10,0))
    
    txt_orig = create_styled_text_widget(content_frame, editable=False)
    txt_orig.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

    # --- UPDATES & EVENTS ---
    
    def on_edit_change(event=None):
        """Re-highlighter con debounce simple"""
        if state["editor_job"]:
            popup.after_cancel(state["editor_job"])
        # Esperar 300ms de inactividad para colorear (performance)
        state["editor_job"] = popup.after(300, lambda: highlight_syntax(txt_edit))

    txt_edit.bind("<KeyRelease>", on_edit_change)

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
        highlight_syntax(txt_edit)
        
        # Update Original
        txt_orig.config(state="normal")
        txt_orig.delete("1.0", "end")
        txt_orig.insert("1.0", full_block)
        highlight_syntax(txt_orig)
        txt_orig.config(state="disabled")

        # Scroll to match logic
        # Calculate line offset
        rel_pos = match_abs_start - start_idx
        # Text before match in the block
        text_before = full_block[:rel_pos]
        # Number of newlines + 1 = line number (1-based)
        match_line = text_before.count('\n') + 1
        
        # Center the view on this line
        # see() makes it visible, usually at bottom or top if scrolling needed.
        # To center, we can try to see a few lines below it too if possible
        # Simple approach: see the line.
        txt_edit.see(f"{match_line}.0")
        txt_orig.see(f"{match_line}.0")
        
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
             txt_orig.see(f"{match_line}.0")
             
             # Attempt to center: scroll so match_line is middle
             # Get total lines visible (height)
             visible_lines = 20 # assumption or txt_edit.cget('height')
             target_top = max(1, match_line - 10)
             txt_edit.yview(target_top)
             txt_orig.yview(target_top)
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
        if hasattr(app_instance, 'controller') and hasattr(app_instance.controller, 'project_manager'):
            files_data = app_instance.controller.project_manager.get_files()
            # Convert to list of paths or keep as dict depending on what find_similar_region expects
            # identify_best_file handles dicts if they have 'full_path', ProjectManager uses 'path'
            # Let's map them to have 'full_path' or just pass 'path' if we adjust identify_best_file
            # Actually, ProjectManager dicts have 'path' (absolute path).
            # identify_best_file checks for 'full_path' in dict (line 50).
            # Let's clean this up by creating a list of paths directly, which identify_best_file also accepts.
            code_files = [f['path'] for f in files_data]
        
        if not code_files:
             tk.messagebox.showwarning("Arbitrary", "No hay archivos de código procesados.")
             return

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
    """
    try:
        content = pyperclip.paste()
        if not content:
            logging.info("Smart Paste: Portapapeles vacío.")
            return

        # 1. Chequeo de Región
        # Regex simple para detectar #region "nombre" o #region nombre
        match = re.search(r'#region\s+["\']?([^"\']+)["\']?', content)
        if match:
             region_name = match.group(1)
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

