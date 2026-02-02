import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import logging
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

        try:
            self.controller = parent.master.controller
        except:
            try:
                self.controller = parent.winfo_toplevel().controller
            except:
                pass

        self._create_layout()

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
        self.actions_row = ttk.Frame(self.header_frame, style="Main.TFrame")
        self.actions_row.pack(side="top", fill="x")

        ttk.Button(self.actions_row, text="📂 Cargar Carpeta", style="Action.TButton", command=self._on_load_docs).pack(side="left", padx=(0, 10))
        ttk.Button(self.actions_row, text="➕ Nuevo Doc", style="Action.TButton", command=self._on_new_doc).pack(side="left", padx=5)
        ttk.Button(self.actions_row, text="💾 Guardar", style="Action.TButton", command=self._on_save_doc).pack(side="left", padx=5)
        ttk.Button(self.actions_row, text="🗑️ Borrar", style="Secondary.TButton", command=self._on_delete_doc).pack(side="left", padx=5)

        # File Selector for Multiple Matches
        self.selector_row = ttk.Frame(self.header_frame, style="Main.TFrame")
        self.selector_row.pack(side="top", fill="x", pady=(10, 0))

        self.lbl_file_count = ttk.Label(self.selector_row, text="Documentos:", style="TLabel")
        self.lbl_file_count.pack(side="left", padx=(0, 10))

        self.cmb_files = ttk.Combobox(self.selector_row, state="readonly", width=40)
        self.cmb_files.pack(side="left", fill="x", expand=True)
        self.cmb_files.bind("<<ComboboxSelected>>", self._on_file_selected_via_combo)

        # Title Label
        self.lbl_title = ttk.Label(self.header_frame, text="Contenido de Documentación", style="Header.TLabel")
        self.lbl_title.pack(side="top", anchor="w", pady=(10, 0))

        # Scrollable Text Widget for Content (Editable)
        self.txt_content = tk.Text(
            self.left_frame,
            font=("Segoe UI", 13),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground="white",
            relief="flat",
            padx=20, pady=20,
            wrap="word",
            state="disabled",
            undo=True # Enable undo/redo
        )
        self.txt_content.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
        
        ttk.Button(btn_frame, text="Nueva Sección", style="Nav.TButton", command=self._on_add_section).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Editar Sección", style="Nav.TButton", command=self._on_edit_section).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Borrar Sección", style="Nav.TButton", command=self._on_delete_section).pack(fill="x", pady=2)

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
            self._display_message("Selecciona una sección.")
            self.cmb_files.config(values=[])
            self.cmb_files.set("")
            return
            
        section_name = self.section_list.get(selected_indices[0])
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
            self.lbl_title.config(text=f"� Editando: {os.path.basename(file_path)}")
            self.txt_content.config(state="normal")
            self.txt_content.delete("1.0", tk.END)
            # Use empty content if file is empty to ensure editable state
            self.txt_content.insert("1.0", content)
            self.txt_content.edit_reset() # Clear undo stack
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
        self.lbl_title.config(text="Información")
        self.txt_content.config(state="normal")
        self.txt_content.delete("1.0", tk.END)
        self.txt_content.insert("1.0", message)
        self.txt_content.config(state="disabled")

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

    def _on_add_section(self):
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller)
            self.wait_window(popup)
            self._refresh_sections()
        except: pass

    def _on_edit_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        section_name = self.section_list.get(selected_indices[0])
        files = self.controller.section_manager.get_files_in_section(section_name)
        from src.ui.popups.section_creation_popup import SectionCreationPopup
        try:
            popup = SectionCreationPopup(self, self.controller, section_name=section_name, initial_files=files)
            self.wait_window(popup)
            self._refresh_sections()
        except: pass

    def _on_delete_section(self):
        selected_indices = self.section_list.curselection()
        if not selected_indices: return
        name = self.section_list.get(selected_indices[0])
        self.controller.section_manager.delete_section(name)
        self._refresh_sections()

    def _refresh_sections(self):
        self.section_list.delete(0, tk.END)
        if self.controller and hasattr(self.controller, 'section_manager'):
            for s in self.controller.section_manager.get_sections():
                self.section_list.insert(tk.END, s)
