import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import webbrowser
import logging
import re
from markdown_it import MarkdownIt
from tkinterweb import HtmlFrame
from PIL import Image, ImageTk
from src.ui.styles import Styles

class DocView(ttk.Frame):
    """
    The view responsible for displaying the 'Documentation' section.
    Includes a sections panel, a markdown viewer/editor with CRUD functionality,
    and a selector for multiple matching documents.
    """
    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        
        self.controller = None
        self.current_file_path = None
        self.available_md_files = [] # Files matching the selected section
        self.highlight_timer = None   # For debounce
        self.is_dark_mode = False     # Default to Light
        self.is_editor_mode = False   # Default to Viewer (False=Viewer, True=Editor)

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
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, bg=Styles.COLOR_BG_MAIN, sashrelief="flat")
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
        
        self.btn_delete = ttk.Button(self.actions_row, image=self.icons.get("delete"), width=3, style="Secondary.TButton", command=self._on_delete_doc)
        self.btn_delete.pack(side="left", padx=5)

        # View Toggles
        mode_icon = self.icons.get("edit") if not self.is_editor_mode else self.icons.get("view")
        self.btn_mode = ttk.Button(self.actions_row, image=mode_icon, width=3, style="Nav.TButton", command=self._toggle_mode)
        self.btn_mode.pack(side="right", padx=5)

        theme_icon = self.icons.get("moon") if not self.is_dark_mode else self.icons.get("sun")
        self.btn_theme = ttk.Button(self.actions_row, image=theme_icon, width=3, style="Nav.TButton", command=self._toggle_theme)
        self.btn_theme.pack(side="right", padx=5)

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



        # Inner Content Area (Single Pane)
        self.content_area = ttk.Frame(self.left_frame, style="Main.TFrame")
        self.content_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 1. Editor (Hidden by default)
        self.editor_frame = ttk.Frame(self.content_area, style="Main.TFrame")
        
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

        # 2. Previewer (Visible by default)
        self.preview_frame = ttk.Frame(self.content_area, style="Main.TFrame")

        # Preview Label
        # ttk.Label(self.preview_frame, text="PREVISUALIZACIÓN (Web)", font=("Segoe UI", 10, "bold"), foreground=Styles.COLOR_DIM).pack(anchor="w", padx=5)

        # Use HtmlFrame for true web-based rendering
        self.web_view = HtmlFrame(self.preview_frame, messages_enabled=False)
        self.web_view.pack(fill="both", expand=True)

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

    def _on_load_docs(self):
        path = filedialog.askdirectory()
        if path:
            if self.controller and hasattr(self.controller, 'config_manager'):
                self.controller.config_manager.set_doc_path(path)
                self._on_section_select()

    def _on_section_select(self, event=None):
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            self._last_selected_section = None
            self._display_message("Selecciona una sección.")
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            return
            
        section_name = self.section_list.get(selected_indices[0])
        
        # Only reload if the selection has actually changed
        if section_name == self._last_selected_section:
            return
            
        self._last_selected_section = section_name
        
        # Save selection
        if self.controller and hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_last_doc_section(section_name)
            
        self._find_markdown_files(section_name)

    def _find_markdown_files(self, section_name):
        """Searches for .md files matching the section name."""
        if not self.controller: return
        doc_dir = self.controller.config_manager.get_doc_path()
        if not doc_dir or not os.path.exists(doc_dir):
            self._display_message("⚠️ Carga una carpeta de documentación.")
            return

        self.available_md_files = []
        try:
            for root, dirs, files in os.walk(doc_dir):
                for file in files:
                    if file.lower().endswith('.md'):
                        if section_name.lower() in file.lower():
                            self.available_md_files.append(os.path.join(root, file))
        except Exception as e:
            logging.error(f"Search error: {e}")

        # Update Combo
        basenames = [os.path.basename(f) for f in self.available_md_files]
        self.cmb_files.config(values=basenames)
        
        if self.available_md_files:
            self.cmb_files.current(0)
            self._display_file_content(self.available_md_files[0])
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

    def _on_new_doc(self):
        if not self.controller: return
        doc_dir = self.controller.config_manager.get_doc_path()
        if not doc_dir or not os.path.exists(doc_dir):
            messagebox.showwarning("Aviso", "Primero carga una carpeta de documentación.")
            return

        # Get current section name as suggestion
        selected_indices = self.section_list.curselection()
        suggestion = ""
        if selected_indices:
            suggestion = self.section_list.get(selected_indices[0]) + ".md"

        # Ask for filename
        from tkinter import simpledialog
        filename = simpledialog.askstring("Nuevo Documento", "Nombre del archivo (.md):", initialvalue=suggestion)
        if not filename: return
        if not filename.endswith(".md"): filename += ".md"

        file_path = os.path.join(doc_dir, filename)
        if os.path.exists(file_path):
            if not messagebox.askyesno("Confirmar", "El archivo ya existe. ¿Sobrescribir?"):
                return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {filename[:-3]}\n\n")
            
            # Refresh current section view to find the new file
            if selected_indices:
                self._on_section_select()
            else:
                # If no section selected, just open it
                self._display_file_content(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear: {e}")

    def _on_delete_doc(self):
        if not self.current_file_path: return
        
        fname = os.path.basename(self.current_file_path)
        if messagebox.askyesno("Confirmar Borrado", f"¿Estás seguro de que quieres borrar '{fname}'?"):
            try:
                os.remove(self.current_file_path)
                logging.info(f"DocView: Borrado {self.current_file_path}")
                self._on_section_select() # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo borrar: {e}")

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
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening popup: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_edit_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Aviso", "Selecciona una sección para editar.")
            return
            
        section_name = self.section_list.get(selected_indices[0])
        files = self.controller.section_manager.get_files_in_section(section_name)
        tables = self.controller.section_manager.get_tables_in_section(section_name)
        
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller, section_name=section_name, initial_files=files, initial_tables=tables)
            self.wait_window(popup)
            self._refresh_sections()
        except Exception as e:
            print(f"Error opening popup for edit: {e}")
            messagebox.showerror("Error", f"Error abriendo popup: {e}")

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        name = self.section_list.get(selected_indices[0])
        self.controller.section_manager.delete_section(name)
        self._refresh_sections()

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        name = self.section_list.get(selected_indices[0])
        self.controller.section_manager.delete_section(name)
        self._refresh_sections()

    def _refresh_sections(self):
        self.section_list.delete(0, tk.END)
        if self.controller and hasattr(self.controller, 'section_manager'):
            sections = self.controller.section_manager.get_sections()
            for s in sections:
                self.section_list.insert(tk.END, s)
                
            # Restore last selection
            if hasattr(self.controller, 'config_manager'):
                last_section = self.controller.config_manager.get_last_doc_section()
                if last_section:
                    try:
                        idx = sections.index(last_section)
                        self.section_list.selection_set(idx)
                        self.section_list.activate(idx)
                        # We don't auto-load files to avoid heavy startup, 
                        # or we can if desired. Let's auto-load for better UX.
                        self._on_section_select() 
                    except ValueError:
                        pass

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

    def _save_settings(self):
        """Saves current view settings."""
        if self.controller and hasattr(self.controller, 'config_manager'):
            self.controller.config_manager.set_doc_view_settings(self.is_dark_mode, self.is_editor_mode)

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

    def _apply_markdown_rendering(self):
        """Highlights Editor and renders Markdown to HTML for the Web View."""
        content = self.txt_content.get("1.0", "end-1c")
        
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
                code {{ font-family: monospace; background-color: {code_bg}; padding: 2px 4px; border-radius: 3px; font-size: 14px; color: {text_color}; }}
                pre {{ background-color: {code_bg}; padding: 16px; border-radius: 6px; overflow: auto; margin-bottom: 16px; border: 1px solid {border_color}; }}
                pre code {{ background-color: transparent; padding: 0; color: {text_color}; }}
                blockquote {{ border-left: 4px solid {border_color}; padding-left: 16px; color: {quote_color}; margin-left: 0; margin-bottom: 16px; }}
                
                /* Table styling optimized for tkhtml */
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; border: 1px solid {border_color}; }}
                th, td {{ border: 1px solid {border_color}; padding: 10px; text-align: left; }}
                th {{ background-color: {th_bg}; color: {text_color}; font-weight: bold; }}
                tr {{ background-color: {table_bg}; }}
            </style>
            """
            
            full_html = f"<html><head>{css}</head><body>{html_content}</body></html>"
            self.web_view.load_html(full_html)
            
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
