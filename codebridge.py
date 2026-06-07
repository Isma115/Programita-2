import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pyperclip


class CodeBridgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CodeBridge - Puente entre IA y tu proyecto")
        self.root.geometry("1100x750")
        self.root.configure(bg="#1e1e2e")

        self.project_path = tk.StringVar()
        self.file_vars = {}
        self.file_checkbuttons = {}

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#1e1e2e")
        self.style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4",
                             font=("Segoe UI", 10))
        self.style.configure("TButton", background="#45475a", foreground="#cdd6f4",
                             font=("Segoe UI", 10, "bold"), padding=8)
        self.style.map("TButton",
                       background=[("active", "#585b70")])
        self.style.configure("Accent.TButton", background="#89b4fa",
                             foreground="#1e1e2e", font=("Segoe UI", 11, "bold"))
        self.style.map("Accent.TButton",
                       background=[("active", "#74c7ec")])
        self.style.configure("Inject.TButton", background="#a6e3a1",
                             foreground="#1e1e2e", font=("Segoe UI", 11, "bold"))
        self.style.map("Inject.TButton",
                       background=[("active", "#94e2d5")])
        self.style.configure("Treeview", background="#313244", foreground="#cdd6f4",
                             fieldbackground="#313244", rowheight=24)
        self.style.configure("Treeview.Heading", background="#45475a",
                             foreground="#cdd6f4", font=("Segoe UI", 9, "bold"))

        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(top_frame, text="Proyecto:").pack(side=tk.LEFT)
        path_entry = tk.Entry(top_frame, textvariable=self.project_path,
                              bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                              relief=tk.FLAT, font=("Consolas", 10), width=60)
        path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(top_frame, text="Examinar", command=self._load_project).pack(side=tk.LEFT)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        left_frame = ttk.Frame(main_pane, width=300)
        main_pane.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Archivos del proyecto:",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_frame, text="Todos", command=self._select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Ninguno", command=self._deselect_all).pack(side=tk.LEFT)

        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_container, selectmode="none", show="tree")
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Button-1>", self._on_tree_click)

        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Petición para la IA:",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        self.prompt_text = scrolledtext.ScrolledText(
            right_frame, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
            font=("Consolas", 11), relief=tk.FLAT, wrap=tk.WORD, height=10
        )
        self.prompt_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.status_label = ttk.Label(bottom_frame, text="Listo",
                                      font=("Segoe UI", 9), foreground="#a6adc8")
        self.status_label.pack(side=tk.LEFT)

        ttk.Button(bottom_frame, text="Copiar prompt al portapapeles",
                   style="Accent.TButton",
                   command=self._copy_prompt).pack(side=tk.LEFT, padx=5)

        ttk.Label(bottom_frame, text="Pega aquí la respuesta de la IA:",
                  foreground="#a6adc8").pack(side=tk.LEFT, padx=(20, 5))

        ttk.Button(bottom_frame, text="Inyectar cambios",
                   style="Inject.TButton",
                   command=self._inject_changes).pack(side=tk.RIGHT)

    def _load_project(self):
        path = filedialog.askdirectory(title="Seleccionar carpeta del proyecto")
        if not path:
            return
        self.project_path.set(path)
        self.file_vars.clear()
        self.file_checkbuttons.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._populate_tree(path, "")

    def _populate_tree(self, root_path, parent_iid):
        IGNORED = {
            "__pycache__", ".git", "node_modules", ".venv", "venv",
            "env", ".idea", ".vscode", "dist", "build", ".next",
            ".tox", "migrations", ".mypy_cache", ".pytest_cache"
        }
        EXTENSIONS = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
            ".h", ".hpp", ".cs", ".rb", ".go", ".rs", ".php", ".swift",
            ".kt", ".scala", ".sh", ".bash", ".zsh", ".css", ".scss",
            ".html", ".htm", ".xml", ".json", ".yaml", ".yml", ".toml",
            ".md", ".txt", ".sql", ".vue", ".svelte"
        }
        try:
            entries = sorted(os.listdir(root_path))
        except PermissionError:
            return

        for entry in entries:
            full_path = os.path.join(root_path, entry)
            rel_path = os.path.relpath(full_path, self.project_path.get())

            if os.path.isdir(full_path):
                if entry.startswith(".") or entry in IGNORED:
                    continue
                dir_iid = self.tree.insert(parent_iid, tk.END, text=f" {entry}",
                                           open=False, values=(full_path, "dir"))
                self._populate_tree(full_path, dir_iid)
            else:
                ext = os.path.splitext(entry)[1].lower()
                if ext not in EXTENSIONS:
                    continue
                self.tree.insert(parent_iid, tk.END, text=f" {entry}",
                                 values=(full_path, "file"))
                var = tk.BooleanVar(value=False)
                self.file_vars[rel_path] = var

    def _on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        if not values or values[1] != "file":
            return
        rel_path = os.path.relpath(values[0], self.project_path.get())
        if rel_path in self.file_vars:
            var = self.file_vars[rel_path]
            var.set(not var.get())
            current_text = self.tree.item(item, "text")
            if var.get():
                self.tree.item(item, text=f" [x] {current_text.lstrip()}")
            else:
                clean = current_text.lstrip()
                if clean.startswith("[x] "):
                    clean = clean[4:]
                self.tree.item(item, text=f" [ ] {clean}")

    def _select_all(self):
        for item in self.tree.get_children():
            self._toggle_recursive(item, True)

    def _deselect_all(self):
        for item in self.tree.get_children():
            self._toggle_recursive(item, False)

    def _toggle_recursive(self, item, value):
        values = self.tree.item(item, "values")
        if values and values[1] == "file":
            rel_path = os.path.relpath(values[0], self.project_path.get())
            if rel_path in self.file_vars:
                self.file_vars[rel_path].set(value)
                current_text = self.tree.item(item, "text")
                clean = current_text.lstrip()
                if clean.startswith("[x] "):
                    clean = clean[4:]
                elif clean.startswith("[ ] "):
                    clean = clean[4:]
                prefix = "[x]" if value else "[ ]"
                self.tree.item(item, text=f" {prefix} {clean}")
        for child in self.tree.get_children(item):
            self._toggle_recursive(child, value)

    def _get_selected_files(self):
        selected = []
        for rel_path, var in self.file_vars.items():
            if var.get():
                selected.append(rel_path)
        return sorted(selected)

    def _read_file(self, rel_path):
        full_path = os.path.join(self.project_path.get(), rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"[ERROR leyendo archivo: {e}]"

    def _build_prompt(self):
        user_msg = self.prompt_text.get("1.0", tk.END).strip()
        if not user_msg:
            return None, "Escribe una petición para la IA"
        selected = self._get_selected_files()
        if not selected:
            return None, "Selecciona al menos un archivo"

        prompt_parts = []
        prompt_parts.append("=" * 60)
        prompt_parts.append("CONTEXTO: PROYECTO DE CÓDIGO")
        prompt_parts.append("=" * 60)
        prompt_parts.append("")
        prompt_parts.append("A continuación se te proporciona el código fuente de varios")
        prompt_parts.append("archivos de un proyecto. Tu tarea es realizar las modificaciones")
        prompt_parts.append("solicitadas por el usuario.")
        prompt_parts.append("")
        prompt_parts.append("-" * 60)
        prompt_parts.append("FORMATO DE RESPUESTA OBLIGATORIO")
        prompt_parts.append("-" * 60)
        prompt_parts.append("")
        prompt_parts.append("Para CADA modificación que realices, debes devolverla EXACTAMENTE")
        prompt_parts.append("en el siguiente formato (respeta los marcadores al pie de la letra):")
        prompt_parts.append("")
        prompt_parts.append("```")
        prompt_parts.append("<<< ARCHIVO: ruta/del/archivo.ext >>>")
        prompt_parts.append("<<< ORIGINAL")
        prompt_parts.append("// pega aquí el código ORIGINAL exacto que vas a reemplazar")
        prompt_parts.append("ORIGINAL >>>")
        prompt_parts.append(">>> MODIFICADO")
        prompt_parts.append("// pega aquí el código NUEVO que reemplaza al original")
        prompt_parts.append("MODIFICADO <<<")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("REGLAS:")
        prompt_parts.append("1. El bloque <<< ORIGINAL debe contener código EXACTO del archivo,")
        prompt_parts.append("   carácter por carácter, para que pueda encontrarse y reemplazarse.")
        prompt_parts.append("2. Incluye suficiente contexto (2-3 líneas antes/después) para que")
        prompt_parts.append("   la búsqueda sea única y no ambigua.")
        prompt_parts.append("3. Si hay múltiples cambios en un mismo archivo, usa múltiples bloques.")
        prompt_parts.append("4. Si necesitas CREAR un archivo nuevo, usa:")
        prompt_parts.append("   <<< ARCHIVO NUEVO: ruta/nuevo/archivo.ext >>>")
        prompt_parts.append("   >>> CONTENIDO")
        prompt_parts.append("   // código completo del nuevo archivo")
        prompt_parts.append("   CONTENIDO <<<")
        prompt_parts.append("5. Si necesitas ELIMINAR código, deja el bloque MODIFICADO vacío.")
        prompt_parts.append("")
        prompt_parts.append("-" * 60)
        prompt_parts.append("PETICIÓN DEL USUARIO")
        prompt_parts.append("-" * 60)
        prompt_parts.append("")
        prompt_parts.append(user_msg)
        prompt_parts.append("")
        prompt_parts.append("=" * 60)
        prompt_parts.append("CÓDIGO FUENTE DE LOS ARCHIVOS")
        prompt_parts.append("=" * 60)

        for rel_path in selected:
            content = self._read_file(rel_path)
            prompt_parts.append("")
            prompt_parts.append(f"{'─' * 60}")
            prompt_parts.append(f"<<< ARCHIVO: {rel_path} >>>")
            prompt_parts.append(f"{'─' * 60}")
            prompt_parts.append(content)
            prompt_parts.append(f"<<< FIN ARCHIVO: {rel_path} >>>")

        prompt_parts.append("")
        prompt_parts.append("=" * 60)
        prompt_parts.append("FIN DEL CONTEXTO. Realiza las modificaciones ahora.")
        prompt_parts.append("=" * 60)

        return "\n".join(prompt_parts), None

    def _copy_prompt(self):
        prompt, error = self._build_prompt()
        if error:
            messagebox.showwarning("Aviso", error)
            return
        try:
            pyperclip.copy(prompt)
            self.status_label.configure(text=f"Prompt copiado ({len(prompt)} chars) - "
                                             f"{len(self._get_selected_files())} archivos incluidos")
        except Exception:
            self._fallback_copy(prompt)

    def _fallback_copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_label.configure(text="Prompt copiado (fallback)")

    def _inject_changes(self):
        try:
            clipboard_content = pyperclip.paste()
        except Exception:
            clipboard_content = self.root.clipboard_get()

        if not clipboard_content.strip():
            messagebox.showwarning("Aviso", "El portapapeles está vacío. "
                                   "Pega la respuesta de la IA primero.")
            return

        changes = self._parse_ai_response(clipboard_content)
        if not changes:
            messagebox.showwarning("Aviso",
                                   "No se encontraron bloques de cambios válidos en el portapapeles.\n\n"
                                   "Asegúrate de que la IA ha usado el formato:\n"
                                   "<<< ARCHIVO: ruta >>>\n"
                                   "<<< ORIGINAL ... ORIGINAL >>>\n"
                                   ">>> MODIFICADO ... MODIFICADO <<<")
            return

        project_root = self.project_path.get()
        if not project_root:
            messagebox.showwarning("Aviso", "Carga un proyecto primero")
            return

        results = {"success": 0, "failed": 0, "created": 0, "details": []}

        for change in changes:
            file_path = change["file"]
            full_path = os.path.join(project_root, file_path)

            if change["type"] == "new_file":
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(change["content"])
                    results["created"] += 1
                    results["details"].append(f"[CREADO] {file_path}")
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append(f"[ERROR] {file_path}: {e}")
                continue

            if not os.path.exists(full_path):
                results["failed"] += 1
                results["details"].append(f"[ERROR] No existe: {file_path}")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                results["failed"] += 1
                results["details"].append(f"[ERROR] Leyendo {file_path}: {e}")
                continue

            original = change["original"]
            modified = change["modified"]

            if original in content:
                content = content.replace(original, modified, 1)
                try:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    results["success"] += 1
                    results["details"].append(f"[OK] {file_path}")
                except Exception as e:
                    results["failed"] += 1
                    results["details"].append(f"[ERROR] Escribiendo {file_path}: {e}")
            else:
                normalized_content = self._normalize_whitespace(content)
                normalized_original = self._normalize_whitespace(original)
                if normalized_original in normalized_content:
                    start_idx = normalized_content.index(normalized_original)
                    original_start = self._map_normalized_to_original(
                        content, start_idx)
                    original_end = self._map_normalized_to_original(
                        content, start_idx + len(normalized_original))
                    content = (content[:original_start] + modified +
                               content[original_end:])
                    try:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        results["success"] += 1
                        results["details"].append(f"[OK~] {file_path} (match fuzzy)")
                    except Exception as e:
                        results["failed"] += 1
                        results["details"].append(f"[ERROR] {file_path}: {e}")
                else:
                    results["failed"] += 1
                    results["details"].append(
                        f"[NO MATCH] {file_path}: "
                        f"fragmento original no encontrado")

        self._show_injection_results(results)

    def _normalize_whitespace(self, text):
        return re.sub(r'[ \t]+', ' ', re.sub(r'\r\n', '\n', text))

    def _map_normalized_to_original(self, original, norm_pos):
        norm_idx = 0
        orig_idx = 0
        while norm_idx < norm_pos and orig_idx < len(original):
            if original[orig_idx] in ('\r',):
                orig_idx += 1
                continue
            if original[orig_idx] in (' ', '\t'):
                run_start = orig_idx
                while orig_idx < len(original) and original[orig_idx] in (' ', '\t'):
                    orig_idx += 1
                if norm_idx < norm_pos:
                    norm_idx += 1
            else:
                norm_idx += 1
                orig_idx += 1
        return orig_idx

    def _parse_ai_response(self, text):
        changes = []
        text = text.replace("\r\n", "\n")

        new_file_pattern = re.compile(
            r'<<<\s*ARCHIVO\s+NUEVO:\s*(.+?)\s*>>>.*?'
            r'>>>\s*CONTENIDO\s*\n(.*?)CONTENIDO\s*<<<',
            re.DOTALL
        )
        for match in new_file_pattern.finditer(text):
            changes.append({
                "type": "new_file",
                "file": match.group(1).strip(),
                "content": match.group(2).rstrip("\n")
            })

        change_pattern = re.compile(
            r'<<<\s*ARCHIVO:\s*(.+?)\s*>>>\s*\n'
            r'<<<\s*ORIGINAL\s*\n(.*?)ORIGINAL\s*>>>\s*\n'
            r'>>>\s*MODIFICADO\s*\n(.*?)MODIFICADO\s*<<<',
            re.DOTALL
        )
        for match in change_pattern.finditer(text):
            file_path = match.group(1).strip()
            original = match.group(2)
            modified = match.group(3)

            if original.endswith("\n"):
                original = original[:-1]
            if modified.endswith("\n"):
                modified = modified[:-1]

            changes.append({
                "type": "modification",
                "file": file_path,
                "original": original,
                "modified": modified
            })

        return changes

    def _show_injection_results(self, results):
        detail_text = "\n".join(results["details"])
        summary = (
            f"Inyección completada:\n\n"
            f"  Modificaciones aplicadas: {results['success']}\n"
            f"  Archivos creados: {results['created']}\n"
            f"  Fallos: {results['failed']}\n\n"
            f"Detalle:\n{detail_text}"
        )
        self.status_label.configure(
            text=f"Inyección: {results['success']} OK, "
                 f"{results['created']} creados, {results['failed']} fallos")
        messagebox.showinfo("Resultado de inyección", summary)


if __name__ == "__main__":
    root = tk.Tk()
    app = CodeBridgeApp(root)
    root.mainloop()
