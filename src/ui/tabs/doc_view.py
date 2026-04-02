import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import webbrowser
import logging
import re
import time
import shutil
from urllib.parse import quote, unquote
from html import escape as html_escape
from markdown_it import MarkdownIt
from tkinterweb import HtmlFrame
from PIL import Image, ImageTk
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Text
from src.ui.styles import Styles
try:
    from src.addons.Arbitrary_sus import create_styled_text_widget as arb_create_styled_text_widget
    from src.addons.Arbitrary_sus import highlight_syntax as arb_highlight_syntax
    from src.addons.Arbitrary_sus import THEME as ARB_THEME
    from src.addons.Arbitrary_sus import FONT_CODE as ARB_FONT_CODE
    ARB_STYLE_AVAILABLE = True
except Exception:
    ARB_STYLE_AVAILABLE = False
    ARB_THEME = {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "cursor": "#aeafad",
        "select_bg": "#264f78",
    }
    ARB_FONT_CODE = ("Consolas", 14)
    def arb_create_styled_text_widget(parent):
        return tk.Text(
            parent,
            font=ARB_FONT_CODE,
            bg=ARB_THEME["bg"],
            fg=ARB_THEME["fg"],
            relief="flat",
            wrap="none",
            insertbackground=ARB_THEME["cursor"],
            selectbackground=ARB_THEME["select_bg"]
        )
    def arb_highlight_syntax(text_widget, file_path=None):
        return None


class VsCodeDarkStyle(Style):
    background_color = "#1e1e1e"
    default_style = "#d4d4d4"
    styles = {
        Text: "#d4d4d4",
        Comment: "italic #6a9955",
        Keyword: "#569cd6",
        Operator: "#d4d4d4",
        Name.Builtin: "#4ec9b0",
        Name.Function: "#dcdcaa",
        Name.Class: "#4ec9b0",
        Name.Decorator: "#c586c0",
        String: "#ce9178",
        Number: "#b5cea8",
    }


class VsCodeLightStyle(Style):
    background_color = "#f5f5f5"
    default_style = "#24292f"
    styles = {
        Text: "#24292f",
        Comment: "italic #008000",
        Keyword: "#0000ff",
        Operator: "#24292f",
        Name.Builtin: "#267f99",
        Name.Function: "#795e26",
        Name.Class: "#267f99",
        Name.Decorator: "#af00db",
        String: "#a31515",
        Number: "#098658",
    }

class DocView(ttk.Frame):
    """
    The view responsible for displaying the 'Documentation' section.
    Includes a sections panel, a markdown viewer/editor with CRUD functionality,
    and a selector for multiple matching documents.
    """
    DRAG_SASH_WIDTH = 18
    DRAG_HANDLE_SIZE = 14

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        
        self.controller = None
        self.current_file_path = None
        self.available_md_files = [] # Files matching the selected section
        self.highlight_timer = None   # For debounce
        self.is_dark_mode = False     # Default to Light
        self.is_editor_mode = False   # Default to Viewer (False=Viewer, True=Editor)
        self.is_right_panel_visible = True
        self.is_code_panel_visible = False
        self.is_fullscreen_mode = False
        self._last_code_token = None
        self._sidebar_visible_before_fullscreen = True
        self._editable_blocks = {}
        self._editable_block_seq = 0
        self._pending_web_view_scroll = None
        self._pending_web_view_fragment = None

        try:
            self.controller = parent.master.controller
        except:
            try:
                self.controller = parent.winfo_toplevel().controller
            except:
                pass
        
        self._last_selected_section = None

        # Load settings if available
        if self.controller and hasattr(self.controller, 'config_manager'):
            settings = self.controller.config_manager.get_doc_view_settings()
            self.is_dark_mode = settings.get("is_dark_mode", False)
            self.is_editor_mode = settings.get("is_editor_mode", False)
            self.code_sash_ratio = settings.get("code_sash_ratio", 0.7)
            self.is_fullscreen_mode = settings.get("is_fullscreen_mode", False)
        else:
            self.code_sash_ratio = 0.7
        try:
            self.code_sash_ratio = float(self.code_sash_ratio)
        except Exception:
            self.code_sash_ratio = 0.7
        self.code_sash_ratio = max(0.2, min(0.9, self.code_sash_ratio))

        self._load_icons()
        self._create_layout()

    def _load_icons(self):
        """Loads icons from assets directory."""
        self.icons = {}
        icon_names = ["folder_open", "file_plus", "save", "delete", "edit", "view", "moon", "sun"]
        try:
            # Assuming assets is at project root
            base_path = os.path.join(os.getcwd(), "assets", "icons")
            for name in icon_names:
                path = os.path.join(base_path, f"{name}.png")
                if os.path.exists(path):
                    img = Image.open(path).resize((20, 20), Image.Resampling.LANCZOS)
                    self.icons[name] = ImageTk.PhotoImage(img)
                else:
                    self.icons[name] = None
        except Exception as e:
            logging.error(f"Error loading icons: {e}")

    def set_controller(self, controller):
        """Explicitly set controller if not available via hierarchy."""
        self.controller = controller
        self._refresh_sections()

    def _create_layout(self):
        """Creates the split-pane layout."""
        self.paned_window = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=self.DRAG_SASH_WIDTH,
            handlesize=self.DRAG_HANDLE_SIZE,
            showhandle=True,
            bg=Styles.COLOR_BG_MAIN,
            sashrelief="flat"
        )
        self.paned_window.pack(fill="both", expand=True)

        # --- Left Pane (Markdown Content) ---
        self.left_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(self.left_frame, minsize=400, stretch="always")

        # Header with actions
        self.header_frame = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.header_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        # Action Buttons Row
        # Action Buttons Row
        self.actions_row = ttk.Frame(self.header_frame, style="Main.TFrame")
        self.actions_row.pack(side="top", fill="x")

        self.btn_load = ttk.Button(self.actions_row, image=self.icons.get("folder_open"), width=3, style="Action.TButton", command=self._on_load_docs)
        self.btn_load.pack(side="left", padx=(0, 10))
        
        self.btn_new = ttk.Button(self.actions_row, image=self.icons.get("file_plus"), width=3, style="Action.TButton", command=self._on_new_doc)
        self.btn_new.pack(side="left", padx=5)
        
        self.btn_save = ttk.Button(self.actions_row, image=self.icons.get("save"), width=3, style="Action.TButton", command=self._on_save_doc)
        self.btn_save.pack(side="left", padx=5)

        self.btn_prompt_template = ttk.Button(
            self.actions_row,
            text="{}",
            width=4,
            style="Nav.TButton",
            command=self._open_prompt_builder
        )
        self.btn_prompt_template.pack(side="left", padx=5)
        
        self.btn_delete = ttk.Button(self.actions_row, image=self.icons.get("delete"), width=3, style="Secondary.TButton", command=self._on_delete_doc)
        self.btn_delete.pack(side="left", padx=5)

        # View Toggles
        mode_icon = self.icons.get("edit") if not self.is_editor_mode else self.icons.get("view")
        self.btn_mode = ttk.Button(self.actions_row, image=mode_icon, width=3, style="Nav.TButton", command=self._toggle_mode)
        self.btn_mode.pack(side="right", padx=5)

        theme_icon = self.icons.get("moon") if not self.is_dark_mode else self.icons.get("sun")
        self.btn_theme = ttk.Button(self.actions_row, image=theme_icon, width=3, style="Nav.TButton", command=self._toggle_theme)
        self.btn_theme.pack(side="right", padx=5)

        self.btn_toggle_fullscreen = ttk.Button(
            self.actions_row,
            text="Expandir",
            width=9,
            style="Nav.TButton",
            command=self._toggle_fullscreen_mode
        )
        self.btn_toggle_fullscreen.pack(side="right", padx=5)

        self.btn_toggle_sidebar = ttk.Button(self.actions_row, text=">", width=3, style="Nav.TButton", command=self._toggle_sidebar)
        self.btn_toggle_sidebar.pack(side="right", padx=5)

        # File Selector for Multiple Matches
        self.selector_row = ttk.Frame(self.header_frame, style="Main.TFrame")
        self.selector_row.pack(side="top", fill="x", pady=(10, 0))

        self.lbl_file_count = ttk.Label(self.selector_row, text="Documentos:", style="TLabel")
        self.lbl_file_count.pack(side="left", padx=(0, 10))

        self.cmb_files = ttk.Combobox(self.selector_row, state="readonly", width=40, font=("Segoe UI", 14))
        self.cmb_files.pack(side="left", fill="x", expand=True)
        self.cmb_files.bind("<<ComboboxSelected>>", self._on_file_selected_via_combo)
        
        # Increase dropdown list font size
        self.master.option_add('*TCombobox*Listbox.font', ("Segoe UI", 14))



        # Inner Content Area (Markdown + optional Code Panel)
        self.content_area = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.content_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.content_pane = tk.PanedWindow(
            self.content_area,
            orient=tk.HORIZONTAL,
            sashwidth=self.DRAG_SASH_WIDTH,
            handlesize=self.DRAG_HANDLE_SIZE,
            showhandle=True,
            bg=Styles.COLOR_BG_MAIN,
            sashrelief="flat"
        )
        self.content_pane.pack(fill="both", expand=True)
        self.content_pane.bind("<ButtonRelease-1>", self._on_content_pane_release)

        self.left_content_frame = ttk.Frame(self.content_pane, style="Main.TFrame")
        self.content_pane.add(self.left_content_frame, minsize=520, stretch="always")

        # 1. Editor (Hidden by default)
        self.editor_frame = ttk.Frame(self.left_content_frame, style="Main.TFrame")
        
        # Editor Label (Optional, maybe remove if single view is clear enough)
        # ttk.Label(self.editor_frame, text="EDITOR (Markdown)", font=("Segoe UI", 10, "bold"), foreground=Styles.COLOR_DIM).pack(anchor="w", padx=5)

        self.txt_content = tk.Text(
            self.editor_frame,
            font=("Consolas", 12),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground="white",
            relief="flat",
            padx=10, pady=10,
            wrap="word",
            state="disabled",
            undo=True 
        )
        self.txt_content.pack(fill="both", expand=True)
        self.txt_content.bind("<KeyRelease>", self._on_content_change)
        self.txt_content.bind("<Control-s>", self._on_save_doc_shortcut)
        self.txt_content.bind("<Control-z>", self._on_undo_markdown_shortcut)
        self.txt_content.bind("<Control-y>", self._on_redo_markdown_shortcut)
        self.txt_content.bind("<Command-s>", self._on_save_doc_shortcut)
        self.txt_content.bind("<Command-z>", self._on_undo_markdown_shortcut)
        self.txt_content.bind("<Command-y>", self._on_redo_markdown_shortcut)

        # 2. Previewer (Visible by default)
        self.preview_frame = ttk.Frame(self.left_content_frame, style="Main.TFrame")

        # Preview Label
        # ttk.Label(self.preview_frame, text="PREVISUALIZACIÓN (Web)", font=("Segoe UI", 10, "bold"), foreground=Styles.COLOR_DIM).pack(anchor="w", padx=5)

        # Use HtmlFrame for true web-based rendering
        self.web_view = HtmlFrame(self.preview_frame, messages_enabled=False, on_link_click=self._on_web_link_click)
        self.web_view.pack(fill="both", expand=True)
        self.web_view.bind("<Button-2>", self._on_markdown_selection_right_click)
        self.web_view.bind("<Button-3>", self._on_markdown_selection_right_click)
        self.web_view.bind("<Control-Button-1>", self._on_markdown_selection_right_click)
        self.web_view.bind("<<DoneLoading>>", self._on_web_view_done_loading)

        # 3. Code Panel (Hidden by default)
        self.code_frame = ttk.Frame(self.content_pane, style="Main.TFrame")
        self.code_header = ttk.Frame(self.code_frame, style="Main.TFrame")
        self.code_header.pack(fill="x", padx=8, pady=(8, 4))

        default_margin = 25
        if self.controller and hasattr(self.controller, "config_manager"):
            try:
                default_margin = int(self.controller.config_manager.get_arbitrary_step())
            except Exception:
                default_margin = 25
        self.code_margin_var = tk.IntVar(value=default_margin)

        self.code_controls = ttk.Frame(self.code_header, style="Main.TFrame")
        self.btn_close_code = ttk.Button(self.code_header, text="x", width=3, style="Nav.TButton", command=self._hide_code_panel)
        self.btn_close_code.pack(side="right")

        self.code_controls.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.scale_margin = ttk.Scale(
            self.code_controls,
            from_=1,
            to=120,
            orient="horizontal",
            command=self._on_margin_change
        )
        self.scale_margin.set(self.code_margin_var.get())
        self.scale_margin.pack(fill="x", expand=True)

        self.code_body = ttk.Frame(self.code_frame, style="Main.TFrame")
        self.code_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.code_text = arb_create_styled_text_widget(self.code_body)
        self.code_text.configure(padx=10, pady=10)
        self.code_text.pack(side="left", fill="both", expand=True)
        self.code_text.bind("<Button-1>", self._clear_code_match_highlight)

        self.code_scroll = ttk.Scrollbar(self.code_body, orient="vertical", command=self.code_text.yview)
        self.code_scroll.pack(side="right", fill="y")
        self.code_text.configure(yscrollcommand=self.code_scroll.set)
        self.code_text.tag_configure("match_highlight", background="#facc15", foreground="#111827")
        self.code_text.config(state="disabled")

        # Initial View State
        self._update_view_mode()
        
        # Configure tags for Editor highlighting
        self._configure_markdown_tags()

        # --- Right Pane (Sections) ---
        self.right_frame = ttk.Frame(self.paned_window, style="Sidebar.TFrame")
        self.paned_window.add(self.right_frame, minsize=250, stretch="never")

        self.right_top_frame = ttk.Frame(self.right_frame, style="Sidebar.TFrame")
        self.right_top_frame.pack(side="top", fill="both", expand=True)

        lbl_sections = ttk.Label(self.right_top_frame, text="Secciones", style="Header.TLabel")
        lbl_sections.pack(fill="x")

        self.section_list = tk.Listbox(
            self.right_top_frame, 
            bg=Styles.COLOR_INPUT_BG, 
            fg=Styles.COLOR_INPUT_FG, 
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            exportselection=0,
            font=Styles.FONT_MAIN,
            height=15
        )
        self.section_list.bind("<<ListboxSelect>>", self._on_section_select)
        self.section_list.bind("<Button-1>", self._on_section_click)
        self.section_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_frame = ttk.Frame(self.right_top_frame, style="Sidebar.TFrame")
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        
        # Nueva Sección moved to context menu
        
        # Context Menu for Sections (same as CodeView)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Nueva Sección", command=self._on_add_section)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Editar", command=self._on_edit_section)
        self.context_menu.add_command(label="Eliminar", command=self._on_delete_section)

        # Bind Right Click (Mac & Windows/Linux)
        self.section_list.bind("<Button-2>", self._show_context_menu)
        self.section_list.bind("<Button-3>", self._show_context_menu)
        self.section_list.bind("<Control-Button-1>", self._show_context_menu)

        if self.controller:
            self._refresh_sections()

        self._update_sidebar_toggle()
        self._update_fullscreen_button()

    def _on_load_docs(self):
        path = filedialog.askdirectory()
        if path:
            if self.controller and hasattr(self.controller, 'config_manager'):
                self.controller.config_manager.set_doc_path(path)
            self._refresh_sections()

    def _get_doc_root(self):
        if not self.controller or not hasattr(self.controller, "config_manager"):
            return None
        doc_dir = self.controller.config_manager.get_doc_path()
        if not doc_dir:
            return None
        doc_dir = os.path.abspath(doc_dir)
        if not os.path.isdir(doc_dir):
            return None
        return doc_dir

    def _get_section_dir(self, section_name):
        doc_dir = self._get_doc_root()
        if not doc_dir:
            return None
        return os.path.join(doc_dir, section_name)

    def _has_path_separator(self, value):
        if os.sep in value:
            return True
        if os.altsep and os.altsep in value:
            return True
        return False

    def _on_section_select(self, event=None, force_reload=False):
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            self._last_selected_section = None
            self._display_message("Selecciona una sección.")
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            return
            
        section_name = self.section_list.get(selected_indices[0])
        
        # Only reload if the selection has actually changed
        if section_name == self._last_selected_section and not force_reload:
            return
            
        self._last_selected_section = section_name
        
        # Save selection
        if self.controller and hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_last_doc_section(section_name)
            
        self._find_markdown_files(section_name)

    def _find_markdown_files(self, section_name, selected_file_path=None):
        """Loads .md files from the selected section folder."""
        section_dir = self._get_section_dir(section_name)
        if not section_dir:
            self._display_message("⚠️ Carga una carpeta de documentación.")
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            self.current_file_path = None
            self.available_md_files = []
            return
        if not os.path.isdir(section_dir):
            self._display_message(f"⚠️ No existe la carpeta de sección '{section_name}'.")
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            self.current_file_path = None
            self.available_md_files = []
            return

        self.available_md_files = []
        try:
            for root, _, files in os.walk(section_dir):
                for file in files:
                    if file.lower().endswith('.md'):
                        self.available_md_files.append(os.path.join(root, file))
        except Exception as e:
            logging.error(f"Search error: {e}")

        self.available_md_files.sort(
            key=lambda path: os.path.relpath(path, section_dir).lower()
        )

        # Update Combo
        basenames = [os.path.relpath(f, section_dir) for f in self.available_md_files]
        self.cmb_files.config(values=basenames)
        
        if self.available_md_files:
            selected_index = 0
            if selected_file_path:
                normalized_target = os.path.normpath(selected_file_path)
                for idx, path in enumerate(self.available_md_files):
                    if os.path.normpath(path) == normalized_target:
                        selected_index = idx
                        break
            self.cmb_files.current(selected_index)
            self._display_file_content(self.available_md_files[selected_index])
        else:
            self.cmb_files.set("")
            self._display_message(f"Sin documentos para '{section_name}'.")
            self.current_file_path = None

    def _on_file_selected_via_combo(self, event=None):
        idx = self.cmb_files.current()
        if idx >= 0:
            self._display_file_content(self.available_md_files[idx])

    def _display_file_content(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.current_file_path = file_path
            self.txt_content.config(state="normal")
            self.txt_content.delete("1.0", tk.END)
            # Use empty content if file is empty to ensure editable state
            self.txt_content.insert("1.0", content)
            self.txt_content.edit_reset() # Clear undo stack
            
            # Apply highlighting
            self._apply_markdown_rendering()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer: {e}")

    def _on_save_doc(self):
        if not self.current_file_path:
            messagebox.showwarning("Aviso", "No hay ningún documento abierto para guardar.")
            return

        try:
            content = self.txt_content.get("1.0", "end-1c")
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"DocView: Guardado {self.current_file_path}")
            # Optional: visual feedback
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {e}")

    def _on_save_doc_shortcut(self, event=None):
        self._on_save_doc()
        return "break"

    def _on_undo_markdown_shortcut(self, event=None):
        if str(self.txt_content.cget("state")) != "normal":
            return "break"
        try:
            self.txt_content.edit_undo()
        except tk.TclError:
            return "break"
        self._on_content_change()
        return "break"

    def _on_redo_markdown_shortcut(self, event=None):
        if str(self.txt_content.cget("state")) != "normal":
            return "break"
        try:
            self.txt_content.edit_redo()
        except tk.TclError:
            return "break"
        self._on_content_change()
        return "break"

    def _on_new_doc(self):
        doc_dir = self._get_doc_root()
        if not doc_dir:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        # Get current section name as suggestion
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Aviso", "Selecciona una sección para crear el documento.")
            return
        section_name = self.section_list.get(selected_indices[0])
        suggestion = "documentacion.md"

        # Ask for filename
        filename = simpledialog.askstring("Nuevo Documento", "Nombre del archivo (.md):", initialvalue=suggestion)
        if not filename: return
        filename = filename.strip()
        if not filename:
            messagebox.showwarning("Aviso", "El nombre del documento no puede estar vacío.")
            return
        if self._has_path_separator(filename):
            messagebox.showwarning("Aviso", "El nombre del documento no puede contener separadores de ruta.")
            return
        if not filename.endswith(".md"): filename += ".md"

        section_dir = os.path.join(doc_dir, section_name)
        os.makedirs(section_dir, exist_ok=True)
        file_path = os.path.join(section_dir, filename)
        if os.path.exists(file_path):
            if not messagebox.askyesno("Confirmar", "El archivo ya existe. ¿Sobrescribir?"):
                return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {filename[:-3]}\n\n")
            
            # Refresh current section view to find the new file
            self._last_selected_section = section_name
            self._find_markdown_files(section_name, selected_file_path=file_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear: {e}")

    def _on_delete_doc(self):
        if not self.current_file_path: return
        
        fname = os.path.basename(self.current_file_path)
        if messagebox.askyesno("Confirmar Borrado", f"¿Estás seguro de que quieres borrar '{fname}'?"):
            try:
                os.remove(self.current_file_path)
                logging.info(f"DocView: Borrado {self.current_file_path}")
                self._on_section_select(force_reload=True) # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo borrar: {e}")

    def _build_documentation_prompt(self, functionality_name):
        functionality_name = (functionality_name or "").strip()

        return (
            f"Genera un documento markdown para conocer de forma simple y directa el flujo de la funcionalidad del software "
            f"\"{functionality_name}\".\n\n"
            "Junto con referencias al código y funciones, variables o elementos importantes relacionados con el flujo. "
            "Incluye una pequeña descripción de lo que hace cada paso y documenta cada funcionalidad implicada. "
            "Agrega trozos de código en cada apartado para saber qué código se está ejecutando en cada paso.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Primero escribe el flujo en lenguaje no técnico, simple y directo.\n"
            "2. Después añade el apartado equivalente en lenguaje técnico.\n"
            "3. Divide el documento por pasos claros del flujo.\n"
            "4. En cada paso, indica referencias al código relacionado.\n"
            "5. Señala funciones, variables, componentes, endpoints, consultas o tablas importantes si aplica.\n"
            "6. Añade fragmentos de código útiles y concretos en cada apartado.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Explicación clara y directa.\n"
            "- Primero visión funcional y después visión técnica.\n"
            "- Código de apoyo en cada sección relevante.\n\n"
            "Guarda el documento en docs."
        )

    def _build_optimization_prompt(self, target_name):
        target_name = (target_name or "").strip()

        return (
            f"Genera un documento markdown con un plan claro para optimizar la parte del código "
            f"\"{target_name}\".\n\n"
            "El objetivo es hacer esa zona más legible, mantenible y eficiente sin romper el comportamiento actual. "
            "Analiza nombres, responsabilidades, complejidad, duplicidad, estructura, posibles mejoras de rendimiento "
            "y riesgos del refactor.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Resume qué hace actualmente esa parte del código en lenguaje simple.\n"
            "2. Describe los problemas detectados de legibilidad, diseño, mantenimiento y rendimiento.\n"
            "3. Propón una secuencia de pasos concreta para optimizarla.\n"
            "4. En cada paso, indica archivos, funciones, clases, variables o componentes implicados.\n"
            "5. Explica el beneficio esperado de cada cambio.\n"
            "6. Añade fragmentos de código o pseudocódigo cuando ayuden a entender el cambio.\n"
            "7. Cierra con una checklist de validación para confirmar que el refactor no rompe nada.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Pasos ordenados y accionables.\n"
            "- Explicación directa, sin relleno.\n"
            "- Con referencias concretas al código.\n\n"
            "Guarda el documento en docs."
        )

    def _build_test_prompt(self, feature_name):
        feature_name = (feature_name or "").strip()

        return (
            f"Propón una prueba manual para validar la característica del software "
            f"\"{feature_name}\".\n\n"
            "El objetivo es definir una comprobación simple, clara y fácil de seguir para verificar manualmente que "
            "esa característica funciona correctamente.\n\n"
            "Estructura obligatoria del documento:\n"
            "1. Resume qué se quiere comprobar y cuál es el comportamiento esperado de la característica.\n"
            "2. Indica el contexto previo necesario para hacer la prueba manual.\n"
            "3. Describe los pasos exactos que debe seguir una persona dentro de la app/web/software.\n"
            "4. Explica qué debe comprobar manualmente en cada paso.\n"
            "5. Indica el resultado esperado final para dar la prueba por válida.\n"
            "6. Añade una breve lista de señales claras de que la prueba ha fallado.\n\n"
            "Formato esperado:\n"
            "- Documento en Markdown.\n"
            "- Explicación directa y accionable.\n"
            "- Pasos numerados y fáciles de seguir.\n"
            "- Solo prueba manual, sin tests automáticos.\n\n"
            "Guarda el documento en docs."
        )

    def _open_prompt_builder(self):
        dialog = tk.Toplevel(self)
        dialog.title("Construir Prompt")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("980x700")
        dialog.minsize(760, 520)
        dialog.configure(bg=Styles.COLOR_BG_MAIN)

        wrapper = ttk.Frame(dialog, style="Main.TFrame")
        wrapper.pack(fill="both", expand=True, padx=12, pady=12)

        prompt_configs = [
            {
                "name": "Documentación",
                "input_label": "Funcionalidad",
                "placeholder": "[FUNCIONALIDAD]",
                "builder": self._build_documentation_prompt,
            },
            {
                "name": "Optimización",
                "input_label": "Parte del código",
                "placeholder": "[PARTE_CODIGO]",
                "builder": self._build_optimization_prompt,
            },
            {
                "name": "Test",
                "input_label": "Característica a probar",
                "placeholder": "[CARACTERISTICA]",
                "builder": self._build_test_prompt,
            },
        ]
        prompt_index = {"value": 0}
        prompt_title_var = tk.StringVar()
        input_label_var = tk.StringVar()

        selector_row = ttk.Frame(wrapper, style="Main.TFrame")
        selector_row.pack(fill="x", pady=(0, 12))

        ttk.Button(
            selector_row,
            text="←",
            width=3,
            style="Nav.TButton",
            command=lambda: switch_prompt(-1)
        ).pack(side="left")

        ttk.Label(
            selector_row,
            textvariable=prompt_title_var,
            style="Header.TLabel"
        ).pack(side="left", padx=10)

        ttk.Button(
            selector_row,
            text="→",
            width=3,
            style="Nav.TButton",
            command=lambda: switch_prompt(1)
        ).pack(side="left")

        ttk.Label(
            selector_row,
            text="Ctrl/Cmd + ← o → para cambiar",
            style="TLabel"
        ).pack(side="right")

        ttk.Label(wrapper, textvariable=input_label_var, style="Header.TLabel").pack(fill="x")

        functionality_var = tk.StringVar()

        entry = tk.Entry(
            wrapper,
            textvariable=functionality_var,
            font=("Segoe UI", 16),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground=Styles.COLOR_FG_TEXT,
            relief="flat"
        )
        entry.pack(fill="x", pady=(10, 12), ipady=10)

        ttk.Label(wrapper, text="Plantilla del prompt", style="TLabel").pack(anchor="w")

        prompt_text = tk.Text(
            wrapper,
            font=("Consolas", 12),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground=Styles.COLOR_FG_TEXT,
            relief="flat",
            wrap="word",
            padx=12,
            pady=12
        )
        prompt_text.pack(fill="both", expand=True, pady=(8, 12))

        prompt_scroll = ttk.Scrollbar(wrapper, orient="vertical", command=prompt_text.yview)
        prompt_scroll.place(relx=1.0, rely=0.23, relheight=0.66, anchor="ne")
        prompt_text.configure(yscrollcommand=prompt_scroll.set)

        def refresh_prompt(event=None):
            config = prompt_configs[prompt_index["value"]]
            functionality_name = functionality_var.get().strip() or config["placeholder"]
            prompt = config["builder"](functionality_name)
            prompt_text.delete("1.0", tk.END)
            prompt_text.insert("1.0", prompt)

        def sync_prompt_selector():
            config = prompt_configs[prompt_index["value"]]
            prompt_title_var.set(f"Prompt: {config['name']}")
            input_label_var.set(config["input_label"])

        def switch_prompt(delta):
            prompt_index["value"] = (prompt_index["value"] + delta) % len(prompt_configs)
            sync_prompt_selector()
            refresh_prompt()

        def on_prev_prompt(event=None):
            switch_prompt(-1)
            return "break"

        def on_next_prompt(event=None):
            switch_prompt(1)
            return "break"

        def copy_prompt():
            content = prompt_text.get("1.0", "end-1c").strip()
            if not content:
                return
            try:
                if self.controller and hasattr(self.controller, "copy_to_clipboard"):
                    copied = self.controller.copy_to_clipboard(content)
                    if copied:
                        messagebox.showinfo("Prompt", "Prompt copiado al portapapeles.")
                        return
                self.clipboard_clear()
                self.clipboard_append(content)
                messagebox.showinfo("Prompt", "Prompt copiado al portapapeles.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo copiar el prompt: {e}")

        button_row = ttk.Frame(wrapper, style="Main.TFrame")
        button_row.pack(fill="x")

        ttk.Button(button_row, text="Copiar prompt", style="Action.TButton", command=copy_prompt).pack(side="right", padx=(8, 0))
        ttk.Button(button_row, text="Cerrar", style="Secondary.TButton", command=dialog.destroy).pack(side="right")

        functionality_var.trace_add("write", lambda *_: refresh_prompt())
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.bind("<Control-Left>", on_prev_prompt)
        dialog.bind("<Control-Right>", on_next_prompt)
        dialog.bind("<Command-Left>", on_prev_prompt)
        dialog.bind("<Command-Right>", on_next_prompt)
        entry.focus_set()
        sync_prompt_selector()
        refresh_prompt()

    def _display_message(self, message):

        self.txt_content.config(state="normal")
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", message)
        self.txt_content.config(state="disabled")

        # Determine Colors based on mode (or default to light for message)
        # We can respect the current mode
        if self.is_dark_mode:
            bg_color = "#0d1117"
            text_color = "#c9d1d9"
        else:
            bg_color = "#ffffff"
            text_color = "#24292f"

        # Load simple message into web view
        html = f"<html><body style='background-color:{bg_color}; color:{text_color}; font-family:sans-serif; padding:20px; font-size:15px;'>{message}</body></html>"
        self.web_view.load_html(html)

    def _capture_web_view_scroll(self):
        """Returns the current vertical scroll fraction of the markdown preview."""
        try:
            yview = self.web_view.yview()
            if isinstance(yview, tuple) and yview:
                return float(yview[0])
        except Exception:
            pass
        return 0.0

    def _restore_web_view_scroll(self, position):
        """Restores the vertical scroll position of the markdown preview."""
        try:
            self.web_view.yview_moveto(position)
        except Exception:
            pass

    def _on_web_view_done_loading(self, event=None):
        """Restores scroll once tkinterweb finishes loading the rendered markdown."""
        if self._pending_web_view_fragment is not None:
            self._pending_web_view_fragment = None
            self._pending_web_view_scroll = None
            return
        if self._pending_web_view_scroll is None:
            return
        position = self._pending_web_view_scroll
        self._pending_web_view_scroll = None
        self.after_idle(lambda pos=position: self._restore_web_view_scroll(pos))
        self.after(50, lambda pos=position: self._restore_web_view_scroll(pos))

    def _on_web_link_click(self, url):
        """Handles clicks inside the markdown viewer."""
        if url.startswith("edit://"):
            block_id = unquote(url.replace("edit://", "", 1)).strip()
            if block_id:
                self._open_markdown_block_editor(block_id)
            return

        if url.startswith("code://"):
            token = unquote(url.replace("code://", "", 1)).strip()
            if token:
                self._open_code_snippet(token)
            return

        try:
            webbrowser.open(url)
        except Exception:
            try:
                self.web_view.load_url(url)
            except Exception:
                pass

    def _on_markdown_selection_right_click(self, event=None):
        """Searches the currently selected Markdown text in the project code."""
        try:
            selected_text = self._get_markdown_search_selection()
        except Exception:
            selected_text = ""

        if not selected_text:
            return

        self._open_code_snippet(selected_text)
        return "break"

    def _get_markdown_search_selection(self):
        """Normalizes the HtmlFrame selection used for code search."""
        selected_text = ""

        try:
            selection_info = self.web_view.get_selection_position(return_elements=False)
        except Exception:
            selection_info = None

        if selection_info:
            try:
                page_text, start_idx, end_idx = selection_info
                selected_text = page_text[start_idx:end_idx]
            except Exception:
                selected_text = ""

        if not selected_text:
            selected_text = self.web_view.get_selection() or ""

        selected_text = selected_text.replace("\u00a0", " ").replace("\u200b", "").replace("\r", "")
        return selected_text.strip("\n")

    def _next_editable_block_id(self):
        self._editable_block_seq += 1
        return f"mdblock-{self._editable_block_seq}"

    def _anchor_id_for_line(self, start_line):
        return f"mdblock-line-{int(start_line)}"

    def _register_editable_block(self, token, block_kind, content):
        """Stores the line range for a rendered Markdown block."""
        if not getattr(token, "map", None):
            return None

        start_line, end_line = token.map
        if start_line is None or end_line is None:
            return None

        lines = content.splitlines(keepends=True)
        block_text = "".join(lines[start_line:end_line])
        block_id = self._next_editable_block_id()
        self._editable_blocks[block_id] = {
            "start_line": int(start_line),
            "end_line": int(end_line),
            "kind": block_kind,
            "text": block_text,
            "anchor_id": self._anchor_id_for_line(start_line),
        }
        return block_id

    def _build_edit_button_html(self, block_id):
        if not block_id:
            return ""
        return (
            f'<a class="edit-handle" href="edit://{quote(block_id, safe="")}" '
            f'title="Editar bloque">&#9998;</a>'
        )

    def _replace_markdown_block(self, block_id, replacement_text):
        block_info = self._editable_blocks.get(block_id)
        if not block_info:
            messagebox.showwarning("Aviso", "No se pudo localizar el bloque para editar.")
            return

        content = self.txt_content.get("1.0", "end-1c")
        lines = content.splitlines(keepends=True)
        start_line = block_info["start_line"]
        end_line = block_info["end_line"]
        original_text = "".join(lines[start_line:end_line])

        replacement = replacement_text
        if original_text.endswith(("\n", "\r")) and replacement and not replacement.endswith(("\n", "\r")):
            replacement += "\n"

        updated_content = "".join(lines[:start_line]) + replacement + "".join(lines[end_line:])
        self._pending_web_view_fragment = self._anchor_id_for_line(start_line)

        self.txt_content.config(state="normal")
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", updated_content)
        if self.current_file_path:
            try:
                with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}")
                return
        self._apply_markdown_rendering()

    def _open_markdown_block_editor(self, block_id):
        block_info = self._editable_blocks.get(block_id)
        if not block_info:
            messagebox.showwarning("Aviso", "No se pudo localizar el bloque para editar.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Editar bloque Markdown")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("900x520")
        dialog.minsize(640, 360)
        dialog.configure(bg=Styles.COLOR_BG_MAIN)

        header = ttk.Frame(dialog, style="Main.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 0))
        ttk.Label(
            header,
            text=f"Editar {block_info['kind']}",
            style="Header.TLabel"
        ).pack(fill="x")

        editor_frame = ttk.Frame(dialog, style="Main.TFrame")
        editor_frame.pack(fill="both", expand=True, padx=12, pady=12)

        editor = tk.Text(
            editor_frame,
            font=("Consolas", 12),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground=Styles.COLOR_FG_TEXT,
            relief="flat",
            wrap="word",
            padx=10,
            pady=10,
            undo=True
        )
        editor.pack(side="left", fill="both", expand=True)
        editor.insert("1.0", block_info.get("text", ""))

        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=editor.yview)
        scrollbar.pack(side="right", fill="y")
        editor.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(dialog, style="Main.TFrame")
        buttons.pack(fill="x", padx=12, pady=(0, 12))

        def save_changes(event=None):
            self._replace_markdown_block(block_id, editor.get("1.0", "end-1c"))
            dialog.destroy()
            return "break"

        ttk.Button(buttons, text="Guardar cambios", style="Action.TButton", command=save_changes).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Cancelar", style="Secondary.TButton", command=dialog.destroy).pack(side="right")

        dialog.bind("<Escape>", lambda event: dialog.destroy())
        dialog.bind("<Control-Return>", save_changes)
        dialog.bind("<Command-Return>", save_changes)
        editor.focus_set()

    def _ensure_code_panel_visible(self):
        if not self.is_code_panel_visible:
            try:
                self.content_pane.add(self.code_frame, minsize=260, stretch="never")
            except Exception:
                pass
            self.is_code_panel_visible = True
            self._set_code_sash()

    def _hide_code_panel(self):
        if self.is_code_panel_visible:
            try:
                self.content_pane.forget(self.code_frame)
            except Exception:
                pass
            self.is_code_panel_visible = False

    def _set_code_sash(self):
        try:
            self.update_idletasks()
            total = self.content_pane.winfo_width()
            if total > 0 and self.is_code_panel_visible:
                left = int(total * self.code_sash_ratio)
                self.content_pane.sash_place(0, left, 0)
        except Exception:
            pass

    def _on_margin_change(self, value=None):
        try:
            margin = int(float(value)) if value is not None else int(self.scale_margin.get())
        except Exception:
            margin = int(self.code_margin_var.get())
        margin = max(1, min(margin, 200))
        self.code_margin_var.set(margin)
        if self.controller and hasattr(self.controller, "config_manager"):
            self.controller.config_manager.set_arbitrary_step(margin)
        if self._last_code_token:
            self._open_code_snippet(self._last_code_token)

    def _on_content_pane_release(self, event=None):
        if not self.is_code_panel_visible:
            return
        try:
            total = self.content_pane.winfo_width()
            if total <= 0:
                return
            x, _ = self.content_pane.sash_coord(0)
            ratio = x / total if total else self.code_sash_ratio
            ratio = max(0.2, min(0.9, ratio))
            if abs(ratio - self.code_sash_ratio) > 0.005:
                self.code_sash_ratio = ratio
                self._save_settings()
        except Exception:
            pass

    def _show_code_panel_message(self, message):
        self._ensure_code_panel_visible()
        self.code_text.config(state="normal")
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", message)
        self.code_text.config(state="disabled")

    def _clear_code_match_highlight(self, event=None):
        """Removes the temporary yellow highlight when the user interacts with the code panel."""
        try:
            self.code_text.tag_remove("match_highlight", "1.0", tk.END)
        except Exception:
            pass

    def _center_code_match(self, match_index):
        """Scrolls the code viewer so the selected match sits near the vertical center."""
        try:
            self.code_text.update_idletasks()

            line_no = int(str(match_index).split(".", 1)[0])
            total_lines = max(int(self.code_text.index("end-1c").split(".", 1)[0]), 1)

            line_info = self.code_text.dlineinfo(match_index)
            if line_info:
                line_height = max(int(line_info[3]), 1)
            else:
                line_height = 20

            widget_height = max(self.code_text.winfo_height(), line_height)
            visible_lines = max(widget_height // line_height, 1)
            top_line = max(1, line_no - (visible_lines // 2))

            if total_lines <= visible_lines:
                self.code_text.yview_moveto(0.0)
                return

            max_top_line = max(1, total_lines - visible_lines + 1)
            top_line = min(top_line, max_top_line)
            self.code_text.yview_moveto((top_line - 1) / max(total_lines - 1, 1))
        except Exception:
            try:
                self.code_text.see(match_index)
            except Exception:
                pass

    def _open_code_snippet(self, token):
        self._last_code_token = token
        result = self._find_code_match(token)
        if not result:
            self._show_code_panel_message(f"No se encontró \"{token}\" en el proyecto.")
            return

        file_path, line_no, start_line, end_line, snippet_text, nocase, match_start, match_end = result
        self._ensure_code_panel_visible()
        base_root = os.getcwd()
        if self.controller and hasattr(self.controller, "project_manager"):
            base_root = self.controller.project_manager.current_project_path or base_root

        self.code_text.config(state="normal")
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", snippet_text)
        arb_highlight_syntax(self.code_text, file_path)

        self.code_text.tag_remove("match_highlight", "1.0", tk.END)
        first_match_idx = None
        try:
            start_idx = self._idx_to_tk(match_start, self.code_text)
            end_idx = self._idx_to_tk(match_end, self.code_text)
            self.code_text.tag_add("match_highlight", start_idx, end_idx)
            first_match_idx = start_idx
        except Exception:
            first_match_idx = None
        self.code_text.tag_lower("match_highlight")

        self.code_text.config(state="disabled")
        if first_match_idx:
            self.after_idle(lambda match_idx=first_match_idx: self._center_code_match(match_idx))

    def _find_code_match(self, token):
        token = (token or "").replace("\r", "").strip("\n")
        if not token:
            return None
        deadline = time.monotonic() + 7.0

        margin = 6
        if self.controller and hasattr(self.controller, "config_manager"):
            try:
                margin = int(self.controller.config_manager.get_arbitrary_step())
            except Exception:
                margin = 6
        margin = max(1, min(margin, 200))

        def build_result(path, content, idx, end_idx, nocase):
            line_no = content.count("\n", 0, idx) + 1
            lines = content.splitlines()
            lines_with_endings = content.splitlines(keepends=True)
            start_line = max(1, line_no - margin)
            end_line = min(len(lines), line_no + margin)
            snippet_abs_start = sum(len(line) for line in lines_with_endings[:start_line - 1])
            snippet_text = "".join(lines_with_endings[start_line - 1:end_line])
            match_start = max(0, idx - snippet_abs_start)
            match_end = max(match_start, min(len(snippet_text), end_idx - snippet_abs_start))
            return path, line_no, start_line, end_line, snippet_text, nocase, match_start, match_end

        def find_in_content(path, content):
            if time.monotonic() > deadline:
                return None
            idx = content.find(token)
            if idx != -1:
                return build_result(path, content, idx, idx + len(token), False)
            return None

        # Prefer ProjectManager cache (correct root even if cwd changes)
        if self.controller and hasattr(self.controller, "project_manager"):
            files = self.controller.project_manager.get_files()
            for f in files:
                if time.monotonic() > deadline:
                    return None
                content = f.get("content") or ""
                try:
                    with open(f["path"], "r", encoding="utf-8", errors="ignore") as file_obj:
                        content = file_obj.read()
                except Exception:
                    pass
                result = find_in_content(f["path"], content)
                if result:
                    return result

        # Fallback: scan filesystem from current project or cwd
        root = os.path.abspath(os.getcwd())
        include_exts = {
            ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
            ".cs", ".vb", ".fs", ".fsx",
            ".go", ".rs", ".zig",
            ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
            ".swift", ".m", ".mm",
            ".py", ".pyw", ".rb", ".php", ".phtml",
            ".pl", ".pm", ".lua", ".r", ".jl", ".dart",
            ".ex", ".exs", ".erl", ".hrl",
            ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
            ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
            ".vue", ".svelte", ".astro",
            ".ejs", ".hbs", ".handlebars", ".mustache", ".njk", ".twig", ".jinja", ".jinja2", ".tpl",
            ".sql", ".graphql", ".gql", ".proto",
            ".json", ".jsonc", ".xml", ".xsd", ".xsl", ".wsdl",
            ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".properties",
            ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1", ".psm1", ".psd1",
            ".dockerignore", ".editorconfig"
        }
        include_filenames = {
            "Dockerfile", "Containerfile", "Makefile", "CMakeLists.txt",
            "Jenkinsfile", "Procfile", "Rakefile", "Gemfile", "Podfile",
            "Brewfile", "Vagrantfile"
        }
        if self.controller and hasattr(self.controller, "project_manager"):
            pm = self.controller.project_manager
            if getattr(pm, "current_project_path", None):
                root = pm.current_project_path
            if getattr(pm, "CODE_EXTENSIONS", None):
                include_exts = set(pm.CODE_EXTENSIONS)
            if getattr(pm, "CODE_FILENAMES", None):
                include_filenames = set(pm.CODE_FILENAMES)

        skip_dirs = {
            ".git", "__pycache__", ".venv", "venv", "node_modules", "dist",
            "build", ".idea", ".vscode"
        }

        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() > deadline:
                return None
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if time.monotonic() > deadline:
                    return None
                if os.path.splitext(fname)[1].lower() not in include_exts and fname not in include_filenames:
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                result = find_in_content(path, content)
                if result:
                    return result

        return None

    def _on_section_click(self, event):
        index = self.section_list.nearest(event.y)
        if index < 0: return
        bbox = self.section_list.bbox(index)
        if not bbox: return
        y, height = bbox[1], bbox[3]
        if event.y > y + height:
            self.section_list.selection_clear(0, tk.END)
            self._on_section_select()
            return "break"

    def _show_context_menu(self, event):
        """Shows the context menu on right click."""
        try:
            # Get index at click position
            index = self.section_list.nearest(event.y)
            
            # If clicked on empty space, show menu without selection (for adding new)
            if index < 0:
                self.section_list.selection_clear(0, tk.END)
                try:
                    self.context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    self.context_menu.grab_release()
                return

            # Check if the click is actually inside the bounding box of the item
            bbox = self.section_list.bbox(index)
            
            # If clicked below items (bbox is None or y > item_end)
            if not bbox or event.y > bbox[1] + bbox[3]:
                 self.section_list.selection_clear(0, tk.END)
                 try:
                    self.context_menu.tk_popup(event.x_root, event.y_root)
                 finally:
                    self.context_menu.grab_release()
                 return
            
            # Select the item
            self.section_list.selection_clear(0, tk.END)
            self.section_list.selection_set(index)
            self.section_list.activate(index)
            self._on_section_select() # Update filter

            # Show menu
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                # Make sure to release the grab
                self.context_menu.grab_release()
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def _on_add_section(self):
        doc_dir = self._get_doc_root()
        if not doc_dir:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        section_name = simpledialog.askstring("Nueva Sección", "Nombre de la nueva sección:")
        if not section_name:
            return
        section_name = section_name.strip()
        if not section_name:
            messagebox.showwarning("Aviso", "El nombre de la sección no puede estar vacío.")
            return
        if self._has_path_separator(section_name):
            messagebox.showwarning("Aviso", "El nombre de la sección no puede contener separadores de ruta.")
            return

        section_dir = os.path.join(doc_dir, section_name)
        if os.path.exists(section_dir):
            messagebox.showwarning("Aviso", "Esa sección ya existe.")
            return

        try:
            os.makedirs(section_dir, exist_ok=False)
            self._refresh_sections()
            sections = list(self.section_list.get(0, tk.END))
            if section_name in sections:
                idx = sections.index(section_name)
                self.section_list.selection_clear(0, tk.END)
                self.section_list.selection_set(idx)
                self.section_list.activate(idx)
                self._on_section_select(force_reload=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear la sección: {e}")

    def _on_edit_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Aviso", "Selecciona una sección para editar.")
            return

        doc_dir = self._get_doc_root()
        if not doc_dir:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        old_name = self.section_list.get(selected_indices[0])
        new_name = simpledialog.askstring("Renombrar Sección", "Nuevo nombre:", initialvalue=old_name)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Aviso", "El nombre de la sección no puede estar vacío.")
            return
        if self._has_path_separator(new_name):
            messagebox.showwarning("Aviso", "El nombre de la sección no puede contener separadores de ruta.")
            return
        if new_name == old_name:
            return

        old_path = os.path.join(doc_dir, old_name)
        new_path = os.path.join(doc_dir, new_name)
        if os.path.exists(new_path):
            messagebox.showwarning("Aviso", "Ya existe otra sección con ese nombre.")
            return

        try:
            os.rename(old_path, new_path)
            self._refresh_sections()
            sections = list(self.section_list.get(0, tk.END))
            if new_name in sections:
                idx = sections.index(new_name)
                self.section_list.selection_clear(0, tk.END)
                self.section_list.selection_set(idx)
                self.section_list.activate(idx)
                self._on_section_select(force_reload=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar la sección: {e}")

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            return

        doc_dir = self._get_doc_root()
        if not doc_dir:
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        name = self.section_list.get(selected_indices[0])
        section_dir = os.path.join(doc_dir, name)
        if not os.path.isdir(section_dir):
            self._refresh_sections()
            return

        confirm = messagebox.askyesno(
            "Eliminar sección",
            f"¿Eliminar la sección '{name}' y todos sus documentos?"
        )
        if not confirm:
            return

        try:
            shutil.rmtree(section_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar la sección: {e}")
            return

        if self._last_selected_section == name:
            self._last_selected_section = None
            if self.controller and hasattr(self.controller, "config_manager"):
                self.controller.config_manager.set_last_doc_section("")
            self.current_file_path = None
            self.available_md_files = []
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            self._display_message("Selecciona una sección.")

        self._refresh_sections()

    def _refresh_sections(self):
        self.section_list.delete(0, tk.END)
        doc_dir = self._get_doc_root()
        if not doc_dir:
            self._last_selected_section = None
            self.available_md_files = []
            self.current_file_path = None
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            self._display_message("⚠️ Carga una carpeta de documentación.")
            return

        sections = []
        try:
            for name in os.listdir(doc_dir):
                full_path = os.path.join(doc_dir, name)
                if os.path.isdir(full_path):
                    sections.append(name)
        except Exception as e:
            logging.error(f"Error loading section folders: {e}")
            self._display_message("⚠️ No se pudieron cargar las secciones.")
            return

        sections.sort(key=str.lower)
        for section_name in sections:
            self.section_list.insert(tk.END, section_name)

        if not sections:
            self._last_selected_section = None
            self.available_md_files = []
            self.current_file_path = None
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            self._display_message("No hay secciones en la carpeta de documentación.")
            return

        # Restore last selection, fallback to first section
        last_section = None
        if self.controller and hasattr(self.controller, "config_manager"):
            last_section = self.controller.config_manager.get_last_doc_section()

        if last_section in sections:
            target_section = last_section
        else:
            target_section = sections[0]

        idx = sections.index(target_section)
        self.section_list.selection_set(idx)
        self.section_list.activate(idx)
        self._on_section_select(force_reload=True)

    def _toggle_mode(self):
        """Toggles between Editor and Viewer modes."""
        self.is_editor_mode = not self.is_editor_mode
        self._save_settings()
        self._update_view_mode()

    def _update_view_mode(self):
        """Updates the visible frame based on mode."""
        if self.is_editor_mode:
            # Show Editor
            self.preview_frame.pack_forget()
            self.editor_frame.pack(fill="both", expand=True)
            self.btn_mode.config(image=self.icons.get("view"))
            # If switching to editor, we might want to ensure content is fresh? 
            # Usually txt_content is the source of truth, so it's fine.
        else:
            # Show Viewer
            self.editor_frame.pack_forget()
            self.preview_frame.pack(fill="both", expand=True)
            self.btn_mode.config(image=self.icons.get("edit"))
            # Refresh render when entering view mode
            self._apply_markdown_rendering()

    def _toggle_theme(self):
        """Toggles between Dark and Light theme for the Viewer."""
        self.is_dark_mode = not self.is_dark_mode
        self._save_settings()
        self.btn_theme.config(image=self.icons.get("sun") if self.is_dark_mode else self.icons.get("moon"))
        self._apply_markdown_rendering()

    def _toggle_sidebar(self):
        """Shows or hides the right-side sections panel."""
        if self.is_fullscreen_mode:
            return

        if self.is_right_panel_visible:
            try:
                self.paned_window.forget(self.right_frame)
            except Exception:
                pass
            self.is_right_panel_visible = False
        else:
            try:
                self.paned_window.add(self.right_frame, minsize=250, stretch="never")
            except Exception:
                pass
            self.is_right_panel_visible = True

        self._update_sidebar_toggle()

    def _update_sidebar_toggle(self):
        if self.is_fullscreen_mode:
            self.btn_toggle_sidebar.state(["disabled"])
        else:
            self.btn_toggle_sidebar.state(["!disabled"])

        if self.is_right_panel_visible:
            self.btn_toggle_sidebar.config(text=">")
        else:
            self.btn_toggle_sidebar.config(text="<")

    def _update_fullscreen_button(self):
        self.btn_toggle_fullscreen.config(
            text="Normal" if self.is_fullscreen_mode else "Expandir"
        )

    def _toggle_fullscreen_mode(self):
        self.is_fullscreen_mode = not self.is_fullscreen_mode
        self._apply_fullscreen_mode()
        self._save_settings()

    def _apply_fullscreen_mode(self):
        main_layout = self._get_main_layout()

        if self.is_fullscreen_mode:
            self._sidebar_visible_before_fullscreen = self.is_right_panel_visible
            if self.is_right_panel_visible:
                try:
                    self.paned_window.forget(self.right_frame)
                except Exception:
                    pass
                self.is_right_panel_visible = False
            if main_layout and self.winfo_manager():
                main_layout.set_navbar_visible(False)
        else:
            if self._sidebar_visible_before_fullscreen and not self.is_right_panel_visible:
                try:
                    self.paned_window.add(self.right_frame, minsize=250, stretch="never")
                except Exception:
                    pass
                self.is_right_panel_visible = True
            elif not self._sidebar_visible_before_fullscreen and self.is_right_panel_visible:
                try:
                    self.paned_window.forget(self.right_frame)
                except Exception:
                    pass
                self.is_right_panel_visible = False

            if main_layout:
                main_layout.set_navbar_visible(True)

        self._update_sidebar_toggle()
        self._update_fullscreen_button()
        self.after_idle(self._set_code_sash)

    def _get_main_layout(self):
        parent = self.master
        while parent is not None:
            if hasattr(parent, "set_navbar_visible"):
                return parent
            parent = getattr(parent, "master", None)
        return None

    def on_tab_shown(self):
        """Reapplies the correct layout state when the tab becomes visible."""
        self._apply_fullscreen_mode()

    def on_tab_hidden(self):
        """Restores shared UI when leaving the documentation tab."""
        main_layout = self._get_main_layout()
        if main_layout:
            main_layout.set_navbar_visible(True)

    def _save_settings(self):
        """Saves current view settings."""
        if self.controller and hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_doc_view_settings(
                self.is_dark_mode,
                self.is_editor_mode,
                self.code_sash_ratio,
                self.is_fullscreen_mode
            )

    # --- Markdown Highlighting & Rendering Logic ---

    def _configure_markdown_tags(self):
        """Configures Tkinter tags for Markdown syntax highlighting in the EDITOR."""
        w = self.txt_content
        # Headers
        w.tag_configure("MD_H1", foreground="#569cd6", font=("Segoe UI", 16, "bold"))
        w.tag_configure("MD_H2", foreground="#569cd6", font=("Segoe UI", 14, "bold"))
        w.tag_configure("MD_H3", foreground="#569cd6", font=("Segoe UI", 13, "bold"))
        
        # Formatting
        w.tag_configure("MD_BOLD", font=("Segoe UI", 12, "bold"), foreground="#ce9178")
        w.tag_configure("MD_ITALIC", font=("Segoe UI", 12, "italic"))
        
        # Structure
        w.tag_configure("MD_CODE", font=("Consolas", 11), foreground="#dcdcaa", background="#2d2d2d")
        w.tag_configure("MD_SYMBOL", foreground="#606060")

    def _on_content_change(self, event=None):
        """Handles text change with debounce."""
        if self.highlight_timer:
            self.after_cancel(self.highlight_timer)
        self.highlight_timer = self.after(300, self._apply_markdown_rendering)

    def _render_markdown_code_block(self, code_text, language_hint, is_dark_mode):
        """Renders fenced Markdown code blocks with VS Code-like syntax colors."""
        formatter = HtmlFormatter(
            nowrap=True,
            noclasses=True,
            style=VsCodeDarkStyle if is_dark_mode else VsCodeLightStyle
        )

        lexer = None
        language_hint = (language_hint or "").strip()
        if language_hint:
            try:
                lexer = get_lexer_by_name(language_hint, stripall=False)
            except Exception:
                lexer = None

        if lexer is None and code_text.strip():
            try:
                lexer = guess_lexer(code_text)
            except Exception:
                lexer = None

        if lexer is None:
            lexer = TextLexer(stripall=False)

        try:
            highlighted = pygments_highlight(code_text, lexer, formatter)
        except Exception:
            highlighted = html_escape(code_text)

        return highlighted

    def _apply_markdown_rendering(self):
        """Highlights Editor and renders Markdown to HTML for the Web View."""
        content = self.txt_content.get("1.0", "end-1c")
        previous_scroll = self._capture_web_view_scroll()
        self._pending_web_view_scroll = previous_scroll
        
        # 1. Highlight Editor (Source view)
        self._highlight_editor(content)
        
        # 2. Render to Web View
        if self.is_dark_mode:
            bg_color = "#0d1117"
            text_color = "#c9d1d9"
            link_color = "#6ab0ff" 
            border_color = "#30363d"
            code_bg = "#161b22"
            header_border = "#30363d"
            quote_color = "#8b949e"
            table_bg = "#0d1117"
            th_bg = "#161b22"
            code_link_color = "#f59e0b"
            code_link_bg = "#2b1f10"
        else:
            bg_color = "#ffffff"
            text_color = "#24292f"
            link_color = "#0969da"
            border_color = "#d0d7de"
            code_bg = "#f6f8fa"
            header_border = "#d0d7de"
            quote_color = "#57606a"
            table_bg = "#ffffff"
            th_bg = "#f6f8fa"
            code_link_color = "#d97706"
            code_link_bg = "#fff7ed"

        try:
            # Handle empty content
            if not content.strip():
                empty_html = f"<html><body style='background-color:{bg_color}; color:{text_color}; font-family:sans-serif; padding:20px; font-size:15px;'><i>Documento vacío</i></body></html>"
                self.web_view.load_html(empty_html)
                return

            # IMPORTANT: Avoid "gfm-like" as it requires linkify-it-py
            # We use a completely manual setup to ensure it works without extra dependencies
            md = MarkdownIt()
            md.options.update({"linkify": False, "typographer": False})
            md.enable("table")
            md.enable("strikethrough")
            self._editable_blocks = {}
            self._editable_block_seq = 0

            def render_code_inline(tokens, idx, options, env):
                code_text = tokens[idx].content
                escaped = html_escape(code_text)
                href = "code://" + quote(code_text, safe="")
                return f'<a class="code-link" href="{href}"><span class="code-inline">{escaped}</span></a>'

            def render_wrapped_open(block_kind, wrapper_class, render_tag_first=False):
                def renderer(tokens, idx, options, env):
                    token = tokens[idx]
                    stack = env.setdefault("editable_wrapper_stack", [])
                    is_nested = len(stack) > 0
                    
                    block_id = self._register_editable_block(token, block_kind, content)
                    
                    # Only show edit button for the outermost block to avoid duplicate pencils
                    button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                    anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                    
                    stack.append(wrapper_class)
                    
                    open_html = md.renderer.renderToken(tokens, idx, options, env)
                    if render_tag_first:
                        return open_html + f'<div id="{anchor_id}" class="editable-block {wrapper_class}">{button_html}'
                    return f'<div id="{anchor_id}" class="editable-block {wrapper_class}">{button_html}' + open_html
                return renderer

            def render_wrapped_close(render_tag_last=False):
                def renderer(tokens, idx, options, env):
                    wrapper_class = ""
                    if env.get("editable_wrapper_stack"):
                        wrapper_class = env["editable_wrapper_stack"].pop()
                    close_html = md.renderer.renderToken(tokens, idx, options, env)
                    if render_tag_last and wrapper_class:
                        return "</div>" + close_html
                    if wrapper_class:
                        return close_html + "</div>"
                    return close_html
                return renderer

            def render_fence(tokens, idx, options, env):
                token = tokens[idx]
                language_hint = ""
                if token.info:
                    language_hint = token.info.strip().split()[0]
                
                stack = env.setdefault("editable_wrapper_stack", [])
                is_nested = len(stack) > 0
                
                block_id = self._register_editable_block(token, "bloque de código", content)
                button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                highlighted = self._render_markdown_code_block(token.content, language_hint, self.is_dark_mode)
                return f'<div id="{anchor_id}" class="editable-block editable-code">{button_html}<pre class="code-block"><code>{highlighted}</code></pre></div>'

            def render_code_block(tokens, idx, options, env):
                token = tokens[idx]
                stack = env.setdefault("editable_wrapper_stack", [])
                is_nested = len(stack) > 0
                
                block_id = self._register_editable_block(token, "bloque de código", content)
                button_html = self._build_edit_button_html(block_id) if not is_nested else ""
                anchor_id = self._editable_blocks.get(block_id, {}).get("anchor_id", "")
                highlighted = self._render_markdown_code_block(token.content, "", self.is_dark_mode)
                return f'<div id="{anchor_id}" class="editable-block editable-code">{button_html}<pre class="code-block"><code>{highlighted}</code></pre></div>'

            md.renderer.rules["code_inline"] = render_code_inline
            md.renderer.rules["fence"] = render_fence
            md.renderer.rules["code_block"] = render_code_block
            md.renderer.rules["paragraph_open"] = render_wrapped_open("párrafo", "editable-paragraph")
            md.renderer.rules["paragraph_close"] = render_wrapped_close()
            md.renderer.rules["heading_open"] = render_wrapped_open("título", "editable-heading")
            md.renderer.rules["heading_close"] = render_wrapped_close()
            md.renderer.rules["blockquote_open"] = render_wrapped_open("bloque de cita", "editable-quote")
            md.renderer.rules["blockquote_close"] = render_wrapped_close()
            md.renderer.rules["table_open"] = render_wrapped_open("tabla", "editable-table")
            md.renderer.rules["table_close"] = render_wrapped_close()
            md.renderer.rules["list_item_open"] = render_wrapped_open("elemento de lista", "editable-list-item", render_tag_first=True)
            md.renderer.rules["list_item_close"] = render_wrapped_close(render_tag_last=True)
            
            html_content = md.render(content)
            
            # Simplified CSS for tkhtml (tkinterweb) compatibility
            # tkhtml is primitive: avoid nth-child, display:block on tables, and complex flex/grid
            css = f"""
            <style>
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    color: {text_color};
                    background-color: {bg_color};
                    padding: 20px;
                }}
                h1, h2, h3 {{ color: {link_color}; border-bottom: 1px solid {header_border}; padding-bottom: 5px; margin-top: 24px; margin-bottom: 16px; }}
                h1 {{ font-size: 24px; font-weight: 600; }}
                h2 {{ font-size: 20px; font-weight: 600; }}
                h3 {{ font-size: 18px; font-weight: 600; }}
                a {{ color: {link_color}; text-decoration: underline; }}
                p {{ margin-bottom: 16px; }}
                code {{ font-family: Consolas, 'Courier New', monospace; background-color: {code_bg}; padding: 2px 4px; border-radius: 3px; font-size: 14px; color: {text_color}; }}
                a.code-link {{ text-decoration: none; }}
                a.code-link .code-inline {{ font-family: Consolas, 'Courier New', monospace; background-color: {code_link_bg}; padding: 2px 4px; border-radius: 3px; font-size: 14px; color: {code_link_color}; border: 1px solid {border_color}; }}
                pre {{ background-color: {code_bg}; padding: 16px; border-radius: 6px; overflow: auto; margin-bottom: 16px; border: 1px solid {border_color}; }}
                pre code {{ background-color: transparent; padding: 0; color: {text_color}; }}
                pre.code-block {{
                    background-color: {VsCodeDarkStyle.background_color if self.is_dark_mode else VsCodeLightStyle.background_color};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 18px;
                }}
                pre.code-block code {{
                    display: block;
                    font-family: Consolas, 'Courier New', monospace;
                    font-size: 14px;
                    line-height: 1.6;
                    white-space: pre;
                }}
                .editable-block {{
                    position: relative;
                    margin-bottom: 10px;
                    padding-left: 36px;
                }}
                .editable-list-item {{
                    padding-left: 30px;
                }}
                .editable-code {{
                    padding-left: 0;
                }}
                .editable-code .edit-handle {{
                    left: 8px;
                    top: 8px;
                }}
                .edit-handle {{
                    position: absolute;
                    left: 4px;
                    top: 6px;
                    width: 24px;
                    height: 24px;
                    line-height: 24px;
                    text-align: center;
                    text-decoration: none;
                    border-radius: 6px;
                    border: 1px solid {border_color};
                    background-color: {code_link_bg};
                    color: {code_link_color};
                    font-size: 14px;
                    font-weight: bold;
                    visibility: hidden;
                }}
                .editable-block:hover .edit-handle {{ visibility: visible; }}
                blockquote {{ border-left: 4px solid {border_color}; padding-left: 16px; color: {quote_color}; margin-left: 0; margin-bottom: 16px; }}
                
                /* Table styling optimized for tkhtml */
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; border: 1px solid {border_color}; }}
                th, td {{ border: 1px solid {border_color}; padding: 10px; text-align: left; }}
                th {{ background-color: {th_bg}; color: {text_color}; font-weight: bold; }}
                tr {{ background-color: {table_bg}; }}
            </style>
            """
            
            full_html = f"<html><head>{css}</head><body>{html_content}</body></html>"
            self.web_view.load_html(full_html, fragment=self._pending_web_view_fragment)
            
        except Exception as e:
            logging.error(f"Web Render error: {e}")

    def _highlight_editor(self, content):
        """Applies basic color highlights to the source editor."""
        for t in ["MD_H1", "MD_H2", "MD_H3", "MD_BOLD", "MD_ITALIC", "MD_CODE", "MD_SYMBOL"]:
            self.txt_content.tag_remove(t, "1.0", tk.END)

        # Headers
        for m in re.finditer(r"^(#+)(.*)$", content, re.MULTILINE):
            s, e = m.span()
            symbols_end = m.start(2)
            self.txt_content.tag_add("MD_SYMBOL", self._idx_to_tk(s, self.txt_content), self._idx_to_tk(symbols_end, self.txt_content))
            level = len(m.group(1))
            tag = f"MD_H{level}" if level <= 3 else "MD_H3"
            self.txt_content.tag_add(tag, self._idx_to_tk(symbols_end, self.txt_content), self._idx_to_tk(e, self.txt_content))

        # Inline formatting (Regex-based for Editor)
        self._apply_regex_tags(content, r"\*\*(.*?)\*\*", "MD_BOLD", self.txt_content)
        self._apply_regex_tags(content, r"\*(.*?)\*", "MD_ITALIC", self.txt_content)
        self._apply_regex_tags(content, r"`(.*?)`", "MD_CODE", self.txt_content)

    def _apply_regex_tags(self, content, pattern, tag, widget):
        for m in re.finditer(pattern, content):
            s, e = m.span()
            widget.tag_add(tag, self._idx_to_tk(s, widget), self._idx_to_tk(e, widget))

    def _idx_to_tk(self, index, widget):
        """Converts character index to Tkinter line.col index."""
        content_up_to = widget.get("1.0", f"1.0 + {index} chars")
        lines = content_up_to.split('\n')
        line = len(lines)
        col = len(lines[-1])
        return f"{line}.{col}"
