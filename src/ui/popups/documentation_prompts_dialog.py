import re
import tkinter as tk
from tkinter import messagebox, ttk

from src.ui.styles import Styles


class DocumentationPromptsDialog(tk.Toplevel):
    """Modal editor for the prompt templates used by Documentation."""

    def __init__(self, parent, config_manager, on_change=None):
        super().__init__(parent)
        self.withdraw()
        self.title("Prompts")
        self.parent_window = parent.winfo_toplevel()
        self.transient(self.parent_window)
        self.configure(bg=Styles.COLOR_BG_MAIN)
        self.minsize(780, 500)
        self.geometry("980x650")

        self.config_manager = config_manager
        self.on_change = on_change
        self.prompts = self.config_manager.get_documentation_prompts()
        self.current_index = None

        self.title_var = tk.StringVar()
        self.input_label_var = tk.StringVar()
        self.include_file_path_var = tk.BooleanVar(value=True)

        self._create_layout()
        self._refresh_prompt_list()
        if self.prompts:
            self._select_prompt(0)
        else:
            self._on_new_prompt()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after_idle(self._show_centered)

    def _create_layout(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=Styles.COLOR_BG_MAIN)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.columnconfigure(1, weight=1)
        tk.Label(
            header,
            text="Prompts de Documentación",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.ui_font(16, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Se guardan en config.json y aparecen en el botón Prompt de Documentación.",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_DIM,
            font=Styles.ui_font(10),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(16, 0))

        body = tk.Frame(self, bg=Styles.COLOR_BG_MAIN)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        list_card = tk.Frame(body, bg=Styles.COLOR_SIDEBAR_CARD_BG)
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_card.rowconfigure(1, weight=1)
        tk.Label(
            list_card,
            text="Prompts",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.ui_font(12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))

        self.prompt_list = tk.Listbox(
            list_card,
            exportselection=False,
            font=Styles.ui_font(11),
            yscrollcommand=lambda *args: self.prompt_scrollbar.set(*args),
        )
        Styles.style_sidebar_listbox(self.prompt_list)
        self.prompt_list.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))
        self.prompt_scrollbar = ttk.Scrollbar(
            list_card,
            orient="vertical",
            command=self.prompt_list.yview,
            style="Vertical.TScrollbar",
        )
        self.prompt_scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=(0, 10))
        self.prompt_list.bind("<<ListboxSelect>>", self._on_prompt_select)

        editor = tk.Frame(body, bg=Styles.COLOR_BG_MAIN)
        editor.grid(row=0, column=1, sticky="nsew")
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(3, weight=1)

        self._add_labeled_entry(editor, 0, "Nombre", self.title_var)
        self._add_labeled_entry(editor, 1, "Texto de ayuda", self.input_label_var)

        options = tk.Frame(editor, bg=Styles.COLOR_BG_MAIN)
        options.grid(row=2, column=0, sticky="ew", pady=(10, 8))
        ttk.Checkbutton(
            options,
            text="Añadir la instrucción del comentario de ruta de archivo",
            variable=self.include_file_path_var,
        ).pack(side="left")

        template_card = tk.Frame(editor, bg=Styles.COLOR_SIDEBAR_CARD_BG)
        template_card.grid(row=3, column=0, sticky="nsew")
        template_card.columnconfigure(0, weight=1)
        template_card.rowconfigure(2, weight=1)
        tk.Label(
            template_card,
            text="Plantilla del prompt",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.ui_font(12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        tk.Label(
            template_card,
            text="Usa marcadores entre corchetes, por ejemplo [FUNCIONALIDAD], para pedir datos al usar el prompt.",
            bg=Styles.COLOR_SIDEBAR_CARD_BG,
            fg=Styles.COLOR_DIM,
            font=Styles.ui_font(10),
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.template_text = tk.Text(
            template_card,
            # Proportional font reads better for natural-language prompts.
            # Keep monospace only for code fragments shown elsewhere.
            font=Styles.scale_font((Styles.FONT_FAMILY, 14)),
            bg=Styles.COLOR_INPUT_BG,
            fg="#f5f7fa",
            insertbackground="#ffffff",
            selectbackground=Styles.COLOR_ACCENT,
            selectforeground="#ffffff",
            wrap="word",
            undo=True,
            padx=14,
            pady=12,
            spacing1=2,
            spacing2=4,
            spacing3=8,
        )
        self.template_text.tag_configure(
            "prompt_marker",
            foreground=Styles.COLOR_CODE_VIEW,
            font=Styles.scale_font((Styles.FONT_FAMILY, 14, "bold")),
        )
        self.template_text.grid(row=2, column=0, sticky="nsew", padx=10, pady=(10, 10))
        Styles.soften_classic_widget(self.template_text)
        self.template_text.bind("<KeyRelease>", self._on_template_key_release)

        actions = tk.Frame(self, bg=Styles.COLOR_BG_MAIN)
        actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        ttk.Button(actions, text="Nuevo", style="Nav.TButton", command=self._on_new_prompt).pack(side="left")
        ttk.Button(actions, text="Eliminar", style="Secondary.TButton", command=self._on_delete_prompt).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Guardar", style="Action.TButton", command=self._on_save_prompt).pack(
            side="right"
        )
        ttk.Button(actions, text="Cerrar", style="Secondary.TButton", command=self.destroy).pack(
            side="right", padx=(0, 8)
        )

    def _add_labeled_entry(self, parent, row, label_text, variable):
        card = tk.Frame(parent, bg=Styles.COLOR_BG_MAIN)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.columnconfigure(1, weight=1)
        tk.Label(
            card,
            text=f"{label_text}:",
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_FG_TEXT,
            font=Styles.ui_font(11, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        entry = tk.Entry(card, textvariable=variable, font=Styles.ui_font(11))
        Styles.style_sidebar_entry(entry)
        entry.grid(row=0, column=1, sticky="ew", ipady=5)

    def _refresh_prompt_list(self):
        self.prompt_list.delete(0, tk.END)
        for prompt in self.prompts:
            self.prompt_list.insert(tk.END, prompt.get("title", "(Sin título)"))

        if self.current_index is not None and 0 <= self.current_index < len(self.prompts):
            self.prompt_list.selection_set(self.current_index)
            self.prompt_list.see(self.current_index)

    def _on_prompt_select(self, _event=None):
        selection = self.prompt_list.curselection()
        if not selection:
            return
        self._select_prompt(selection[0])

    def _select_prompt(self, index):
        if not 0 <= index < len(self.prompts):
            return
        self.current_index = index
        prompt = self.prompts[index]
        self.title_var.set(prompt.get("title", ""))
        self.input_label_var.set(prompt.get("input_label", ""))
        self.include_file_path_var.set(bool(prompt.get("include_file_path_instruction", True)))
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", prompt.get("template", ""))
        self._highlight_template_markers()
        self._refresh_prompt_list()

    def _on_new_prompt(self):
        self.current_index = None
        self.prompt_list.selection_clear(0, tk.END)
        self.title_var.set("")
        self.input_label_var.set("Describe el dato que debe completar el usuario")
        self.include_file_path_var.set(True)
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", "Escribe aquí el prompt usando [DATO].")
        self._highlight_template_markers()
        self.title_var_entry_focus()

    def _on_template_key_release(self, _event=None):
        """Keeps prompt placeholders visually distinct while editing."""
        self._highlight_template_markers()

    def _highlight_template_markers(self):
        self.template_text.tag_remove("prompt_marker", "1.0", tk.END)
        content = self.template_text.get("1.0", "end-1c")
        for match in re.finditer(r"\[[^\]\n]+\]", content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.template_text.tag_add("prompt_marker", start, end)

    def title_var_entry_focus(self):
        """Focuses the first editor entry when a new prompt is created."""
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _on_save_prompt(self):
        title = self.title_var.get().strip()
        template = self.template_text.get("1.0", "end-1c")
        if not title:
            messagebox.showwarning("Prompts", "El nombre no puede estar vacío.", parent=self)
            return
        if not template.strip():
            messagebox.showwarning("Prompts", "La plantilla no puede estar vacía.", parent=self)
            return

        prompt = {
            "title": title,
            "input_label": self.input_label_var.get().strip(),
            "template": template,
            "include_file_path_instruction": bool(self.include_file_path_var.get()),
        }
        if self.current_index is None:
            self.prompts.append(prompt)
            self.current_index = len(self.prompts) - 1
        else:
            self.prompts[self.current_index] = prompt

        self.config_manager.set_documentation_prompts(self.prompts)
        self.prompts = self.config_manager.get_documentation_prompts()
        self._refresh_prompt_list()
        self._select_prompt(self.current_index)
        if self.on_change:
            self.on_change()

    def _on_delete_prompt(self):
        if self.current_index is None or not self.prompts:
            return
        prompt = self.prompts[self.current_index]
        if not messagebox.askyesno(
            "Prompts",
            f"¿Eliminar el prompt '{prompt.get('title', '')}'?",
            parent=self,
        ):
            return

        del self.prompts[self.current_index]
        self.config_manager.set_documentation_prompts(self.prompts)
        self.prompts = self.config_manager.get_documentation_prompts()
        if self.prompts:
            self.current_index = min(self.current_index, len(self.prompts) - 1)
            self._refresh_prompt_list()
            self._select_prompt(self.current_index)
        else:
            self._on_new_prompt()
        if self.on_change:
            self.on_change()

    def _show_centered(self):
        self.update_idletasks()
        parent = self.parent_window
        parent.update_idletasks()
        width = max(self.winfo_reqwidth(), 780)
        height = max(self.winfo_reqheight(), 500)
        x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.grab_set()
