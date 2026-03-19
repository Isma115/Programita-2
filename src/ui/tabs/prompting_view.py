import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import re
from src.ui.styles import Styles


class PromptingView(ttk.Frame):
    """
    View for managing prompt templates with placeholders ([]),
    filling them, and copying the final prompt to the clipboard.
    """
    PROMPTS_FILENAME = "prompts.json"

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.controller = None
        try:
            self.controller = parent.winfo_toplevel().controller
        except Exception:
            pass

        self.prompts_dir = None
        self.prompts = []  # List of dicts: {"title": str, "template": str}
        self.filtered_indices = []
        self.current_index = None

        self.folder_var = tk.StringVar(value="Sin carpeta seleccionada")
        self.search_var = tk.StringVar(value="")
        self.title_var = tk.StringVar(value="")

        self.placeholder_vars = []
        self._last_placeholders = []
        self._suspend_template_events = False

        self._create_layout()
        self._load_from_config()

    def _create_layout(self):
        """Creates the main layout."""
        self.main_container = ttk.Frame(self, style="Main.TFrame")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # === Top Bar ===
        top_bar = ttk.Frame(self.main_container, style="Main.TFrame")
        top_bar.pack(fill="x")
        top_bar.columnconfigure(1, weight=1)

        self.btn_folder = ttk.Button(
            top_bar,
            text="📁 Carpeta",
            style="Action.TButton",
            command=self._on_select_folder
        )
        self.btn_folder.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.lbl_folder = ttk.Label(
            top_bar,
            textvariable=self.folder_var,
            style="TLabel",
            anchor="w"
        )
        self.lbl_folder.grid(row=0, column=1, sticky="ew")

        self.btn_new = ttk.Button(
            top_bar,
            text="➕ Nuevo",
            style="Nav.TButton",
            command=self._on_new_prompt
        )
        self.btn_new.grid(row=0, column=2, padx=(10, 0))

        self.btn_save = ttk.Button(
            top_bar,
            text="💾 Guardar",
            style="Action.TButton",
            command=self._on_save_prompt
        )
        self.btn_save.grid(row=0, column=3, padx=(10, 0))

        self.btn_delete = ttk.Button(
            top_bar,
            text="🗑️ Eliminar",
            style="Secondary.TButton",
            command=self._on_delete_prompt
        )
        self.btn_delete.grid(row=0, column=4, padx=(10, 0))

        # === Split Pane ===
        self.paned_window = tk.PanedWindow(
            self.main_container,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            bg=Styles.COLOR_BG_MAIN,
            sashrelief="flat"
        )
        self.paned_window.pack(fill="both", expand=True, pady=(15, 0))

        # --- Left Pane: Prompt List ---
        left_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(left_frame, minsize=260, stretch="never")

        search_frame = ttk.Frame(left_frame, style="Main.TFrame")
        search_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(search_frame, text="Buscar:", style="TLabel").pack(side="left", padx=(0, 6))
        self.ent_search = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=Styles.FONT_MAIN,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT
        )
        self.ent_search.pack(side="left", fill="x", expand=True)
        self.search_var.trace_add("write", self._on_search_change)

        self.prompt_list = tk.Listbox(
            left_frame,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            exportselection=0,
            font=Styles.FONT_MAIN
        )
        self.prompt_list.pack(side="left", fill="both", expand=True)
        self.prompt_list.bind("<<ListboxSelect>>", self._on_prompt_select)

        list_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.prompt_list.yview, style="Vertical.TScrollbar")
        list_scroll.pack(side="right", fill="y")
        self.prompt_list.configure(yscrollcommand=list_scroll.set)

        # --- Right Pane: Editor & Filler ---
        right_frame = ttk.Frame(self.paned_window, style="Main.TFrame")
        self.paned_window.add(right_frame, minsize=500, stretch="always")

        # Title Row
        title_row = ttk.Frame(right_frame, style="Main.TFrame")
        title_row.pack(fill="x", pady=(0, 10))
        ttk.Label(title_row, text="Título:", style="TLabel").pack(side="left", padx=(0, 6))

        self.ent_title = tk.Entry(
            title_row,
            textvariable=self.title_var,
            font=Styles.FONT_MAIN,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
            highlightcolor=Styles.COLOR_ACCENT
        )
        self.ent_title.pack(side="left", fill="x", expand=True)

        # Template Editor
        ttk.Label(right_frame, text="Plantilla (usa [] como casillas):", style="TLabel").pack(anchor="w")

        self.txt_template = tk.Text(
            right_frame,
            font=("Consolas", 14),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground="white",
            relief="flat",
            padx=10, pady=10,
            wrap="word",
            height=8
        )
        self.txt_template.pack(fill="x", pady=(5, 15))
        self.txt_template.bind("<KeyRelease>", self._on_template_change)

        # Fields (placeholders)
        ttk.Label(right_frame, text="Campos detectados:", style="TLabel").pack(anchor="w")

        fields_container = ttk.Frame(right_frame, style="Main.TFrame")
        fields_container.pack(fill="both", expand=True, pady=(5, 15))

        self.fields_canvas = tk.Canvas(
            fields_container,
            bg=Styles.COLOR_BG_MAIN,
            highlightthickness=0
        )
        fields_scroll = ttk.Scrollbar(fields_container, orient="vertical", command=self.fields_canvas.yview, style="Vertical.TScrollbar")

        self.fields_inner = ttk.Frame(self.fields_canvas, style="Main.TFrame")
        self.fields_inner.bind(
            "<Configure>",
            lambda e: self.fields_canvas.configure(scrollregion=self.fields_canvas.bbox("all"))
        )

        self._fields_window = self.fields_canvas.create_window((0, 0), window=self.fields_inner, anchor="nw")
        self.fields_canvas.configure(yscrollcommand=fields_scroll.set)

        self.fields_canvas.bind(
            "<Configure>",
            lambda e: self.fields_canvas.itemconfigure(self._fields_window, width=e.width)
        )

        self.fields_canvas.pack(side="left", fill="both", expand=True)
        fields_scroll.pack(side="right", fill="y")

        # Preview + Copy
        preview_header = ttk.Frame(right_frame, style="Main.TFrame")
        preview_header.pack(fill="x", pady=(0, 5))
        ttk.Label(preview_header, text="Prompt final:", style="TLabel").pack(side="left")

        self.btn_copy = ttk.Button(
            preview_header,
            text="📋 Copiar",
            style="Action.TButton",
            command=self._on_copy_prompt
        )
        self.btn_copy.pack(side="right")

        self.txt_preview = tk.Text(
            right_frame,
            font=("Consolas", 13),
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_FG_TEXT,
            insertbackground="white",
            relief="flat",
            padx=10, pady=10,
            wrap="word",
            height=6,
            state="disabled"
        )
        self.txt_preview.pack(fill="x", pady=(0, 5))

    def _load_from_config(self):
        """Load last prompts folder from config and auto-load prompts."""
        if self.controller and hasattr(self.controller, "config_manager"):
            path = self.controller.config_manager.get_prompting_path()
            if path and os.path.exists(path):
                self.prompts_dir = path
                self.folder_var.set(path)
                self._load_prompts_from_folder()
                return
        self.folder_var.set("Sin carpeta seleccionada")

    def _on_select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.prompts_dir = path
            self.folder_var.set(path)
            if self.controller and hasattr(self.controller, "config_manager"):
                self.controller.config_manager.set_prompting_path(path)
            self._load_prompts_from_folder()

    def _prompts_file_path(self):
        if not self.prompts_dir:
            return None
        return os.path.join(self.prompts_dir, self.PROMPTS_FILENAME)

    def _load_prompts_from_folder(self):
        """Loads prompts from prompts.json inside the selected folder."""
        self.prompts = []
        path = self._prompts_file_path()
        if not path:
            return
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            title = str(item.get("title", "")).strip()
                            template = str(item.get("template", ""))
                            if title or template:
                                self.prompts.append({
                                    "title": title or "(Sin título)",
                                    "template": template
                                })
                else:
                    messagebox.showwarning("Prompting", "Formato inválido en prompts.json")
            except Exception as e:
                messagebox.showerror("Prompting", f"No se pudo cargar prompts.json\n{e}")
        self.current_index = None
        self._refresh_prompt_list()
        self._clear_editor()

    def _save_prompts_to_file(self):
        path = self._prompts_file_path()
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Prompting", f"No se pudo guardar prompts.json\n{e}")
            return False

    def _refresh_prompt_list(self):
        """Refreshes the listbox based on the current search."""
        filter_text = self.search_var.get().strip().lower()
        keywords = [w for w in filter_text.split() if w]

        self.filtered_indices = []
        for idx, item in enumerate(self.prompts):
            haystack = f"{item.get('title', '')} {item.get('template', '')}".lower()
            if all(k in haystack for k in keywords):
                self.filtered_indices.append(idx)

        self.prompt_list.delete(0, tk.END)
        for idx in self.filtered_indices:
            title = self.prompts[idx].get("title", "(Sin título)")
            self.prompt_list.insert(tk.END, title)

        # Reselect current prompt if still visible
        if self.current_index in self.filtered_indices:
            visible_idx = self.filtered_indices.index(self.current_index)
            self.prompt_list.selection_set(visible_idx)
            self.prompt_list.see(visible_idx)

    def _on_search_change(self, *_):
        self._refresh_prompt_list()

    def _on_prompt_select(self, event=None):
        selection = self.prompt_list.curselection()
        if not selection:
            return
        visible_idx = selection[0]
        if visible_idx >= len(self.filtered_indices):
            return
        self.current_index = self.filtered_indices[visible_idx]
        prompt = self.prompts[self.current_index]
        self.title_var.set(prompt.get("title", ""))
        self._set_template_text(prompt.get("template", ""))
        self._refresh_fields_from_template()

    def _on_new_prompt(self):
        self.current_index = None
        self.title_var.set("")
        self._set_template_text("")
        self._refresh_fields_from_template()
        self.prompt_list.selection_clear(0, tk.END)

    def _on_save_prompt(self):
        if not self.prompts_dir:
            messagebox.showinfo("Prompting", "Selecciona una carpeta para guardar los prompts.")
            return
        title = self.title_var.get().strip()
        template = self._get_template_text()
        if not title:
            messagebox.showinfo("Prompting", "El título no puede estar vacío.")
            return

        if self.current_index is None:
            self.prompts.append({"title": title, "template": template})
            self.current_index = len(self.prompts) - 1
        else:
            self.prompts[self.current_index] = {"title": title, "template": template}

        if self._save_prompts_to_file():
            self._refresh_prompt_list()
            self._select_prompt_by_index(self.current_index)

    def _on_delete_prompt(self):
        if self.current_index is None:
            return
        prompt = self.prompts[self.current_index]
        confirm = messagebox.askyesno("Prompting", f"¿Eliminar '{prompt.get('title', '')}'?")
        if not confirm:
            return
        del self.prompts[self.current_index]
        self.current_index = None
        self._save_prompts_to_file()
        self._refresh_prompt_list()
        self._clear_editor()

    def _select_prompt_by_index(self, idx):
        if idx is None:
            return
        if idx not in self.filtered_indices:
            self._refresh_prompt_list()
        if idx in self.filtered_indices:
            visible_idx = self.filtered_indices.index(idx)
            self.prompt_list.selection_clear(0, tk.END)
            self.prompt_list.selection_set(visible_idx)
            self.prompt_list.see(visible_idx)

    def _clear_editor(self):
        self.title_var.set("")
        self._set_template_text("")
        self._refresh_fields_from_template()

    def _set_template_text(self, text):
        self._suspend_template_events = True
        self.txt_template.delete("1.0", tk.END)
        if text:
            self.txt_template.insert("1.0", text)
        self._suspend_template_events = False

    def _get_template_text(self):
        return self.txt_template.get("1.0", "end-1c")

    def _on_template_change(self, event=None):
        if self._suspend_template_events:
            return
        self._refresh_fields_from_template()

    def _extract_placeholders(self, template_text):
        return re.findall(r"\[(.*?)\]", template_text)

    def _refresh_fields_from_template(self):
        template = self._get_template_text()
        placeholders = self._extract_placeholders(template)

        if placeholders != self._last_placeholders:
            self._build_placeholder_fields(placeholders)
            self._last_placeholders = list(placeholders)

        self._update_preview()

    def _build_placeholder_fields(self, placeholders):
        # Preserve existing values by position
        old_values = [var.get() for var in self.placeholder_vars]
        self.placeholder_vars = []

        for widget in self.fields_inner.winfo_children():
            widget.destroy()

        if not placeholders:
            ttk.Label(self.fields_inner, text="No hay casillas [] en la plantilla.", style="TLabel").pack(anchor="w", padx=5, pady=5)
            return

        for i, label in enumerate(placeholders):
            display = label.strip() if label.strip() else f"Campo {i + 1}"
            row = ttk.Frame(self.fields_inner, style="Main.TFrame")
            row.pack(fill="x", pady=4)

            ttk.Label(row, text=display + ":", style="TLabel").pack(side="left", padx=(0, 6))
            var = tk.StringVar(value=old_values[i] if i < len(old_values) else "")
            var.trace_add("write", lambda *_: self._update_preview())
            entry = tk.Entry(
                row,
                textvariable=var,
                font=Styles.FONT_MAIN,
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_INPUT_FG,
                insertbackground="white",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=Styles.COLOR_BORDER,
                highlightcolor=Styles.COLOR_ACCENT
            )
            entry.pack(side="left", fill="x", expand=True)
            self.placeholder_vars.append(var)

    def _build_filled_prompt(self, template_text):
        values = [v.get() for v in self.placeholder_vars]
        iterator = iter(values)

        def repl(_match):
            try:
                return next(iterator)
            except StopIteration:
                return ""

        return re.sub(r"\[(.*?)\]", repl, template_text)

    def _update_preview(self):
        template = self._get_template_text()
        if template:
            final_text = self._build_filled_prompt(template)
        else:
            final_text = ""
        self.txt_preview.config(state="normal")
        self.txt_preview.delete("1.0", tk.END)
        if final_text:
            self.txt_preview.insert("1.0", final_text)
        self.txt_preview.config(state="disabled")

    def _on_copy_prompt(self):
        content = self.txt_preview.get("1.0", "end-1c")
        if not content.strip():
            return
        copied = False
        if self.controller and hasattr(self.controller, "copy_to_clipboard"):
            copied = self.controller.copy_to_clipboard(content)
        if not copied:
            try:
                self.clipboard_clear()
                self.clipboard_append(content)
                copied = True
            except Exception:
                copied = False
        if not copied:
            messagebox.showerror("Prompting", "No se pudo copiar al portapapeles.")
