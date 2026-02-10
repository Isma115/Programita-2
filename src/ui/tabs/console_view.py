import tkinter as tk
from tkinter import ttk
from src.ui.styles import Styles

class ConsoleView(ttk.Frame):
    """
    The view for the 'Console' tab.
    Provides a text area for output and an entry for input.
    """
    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1) # Output area expands
        self.rowconfigure(1, weight=0) # Input area fixed
        
        # Output Area
        self.output_text = tk.Text(
            self,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            font=Styles.FONT_CODE,
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
            padx=10, pady=10
        )
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        
        # Scrollbar for Output
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.output_text.yview, style="Vertical.TScrollbar")
        self.output_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(10, 5))
        
        # Input Area Container
        input_frame = ttk.Frame(self, style="Main.TFrame")
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        
        self.lbl_prompt = ttk.Label(input_frame, text=">>>", style="TLabel", font=Styles.FONT_CODE)
        self.lbl_prompt.pack(side="left")
        
        # Command Suggestions
        self.builtin_commands = ["help", "clear", "status", "version", "exit"]
        self.commands = self.builtin_commands.copy()
        
        # Scan for addons initially
        self._scan_addons()

        self.input_entry = ttk.Combobox(
            input_frame,
            values=self.commands,
            style="TCombobox",
            font=Styles.FONT_CODE
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<KeyRelease>", self._on_key_release)
        self.input_entry.bind("<Tab>", self._on_tab)
        
        # MacOS Dark Mode Hack for Combobox
        self.input_entry['postcommand'] = self._colorize_combo_items
        
        # Send Button
        self.btn_send = ttk.Button(
            input_frame,
            text="Enviar",
            style="Action.TButton",
            command=self._on_send
        )
        self.btn_send.pack(side="right")
        
        # Initial Message
        self._log("Consola iniciada.")

    def _on_tab(self, event):
        """Autocompletes with the first suggestion."""
        values = self.input_entry['values']
        if values:
            first_match = values[0]
            # Must preserve the part of the command that might be arguments?
            # The user asked: "Al pulsar tab se tiene que autocompletar con el primer comando encontrado"
            # Usually tab completion completes the defining word.
            # Since our commands are "whole strings" (like "cambiar colores"), 
            # replacing the content with the match is likely what is expected for the command part.
            
            # Use current text to check if we are completing arguments?
            # Current implementation of 'commands' includes full command strings like "cambiar colores".
            # So simply setting the text to the match is correct.
            
            self.input_entry.set(first_match)
            self.input_entry.icursor(tk.END)
            self.input_entry.selection_clear()
            
            # Close the dropdown
            try:
                self.input_entry.tk.call('ttk::combobox::Unpost', self.input_entry)
            except:
                pass
                
        return "break"

    def _scan_addons(self):
        """Scans the addons directory for valid commands."""
        try:
            import os
            addon_dir = os.path.join("src", "addons")
            if not os.path.exists(addon_dir):
                return
                
            for f in os.listdir(addon_dir):
                if f.endswith(".py") and f != "__init__.py":
                    cmd_name = f[:-3].replace("_", " ") # cambiar_colores.py -> cambiar colores
                    if cmd_name not in self.commands:
                        self.commands.append(cmd_name)
                        # Also add the exact filename version just in case? 
                        # User wants "cambiar colores", scanning gives "cambiar_colores.py".
                        # logic in _on_send handles "cambiar colores" -> "cambiar_colores".
                        
        except Exception as e:
            print(f"Error scanning addons: {e}")

    def _on_key_release(self, event):
        """Filters suggestions based on input."""
        if event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            return
            
        text = self.input_entry.get()
        if not text:
            self.input_entry['values'] = self.commands
            return

        # Simple similarity: starts with or contains
        # Sort matches: exact start first, then contains
        matches = []
        for cmd in self.commands:
            if cmd.startswith(text):
                matches.append((0, cmd)) # Priority 0
            elif text in cmd:
                matches.append((1, cmd)) # Priority 1
        
        matches.sort()
        filtered = [m[1] for m in matches]
        
        if filtered:
            self.input_entry['values'] = filtered
            
            # Force open the dropdown if hidden
            # We use a try block because sometimes this call can be flaky depending on OS/Focus
            try:
                 # Check if already mapped (visible)
                 # 'popdown' is the internal name for the dropdown window
                 popdown = self.input_entry.tk.call('ttk::combobox::PopdownWindow', self.input_entry)
                 if not self.input_entry.tk.call('winfo', 'ismapped', popdown):
                     self.input_entry.tk.call('ttk::combobox::Post', self.input_entry)
                     self.input_entry.focus_set() # Restore focus
                     
                     # Ensure cursor is at the end or preserved
                     # self.input_entry.icursor(tk.END) # Optional, depends on behavior
                     
                 # Re-apply colors because posting might reset them on some themes
                 self._colorize_combo_items()
            except Exception:
                pass
        else:
             self.input_entry['values'] = []
             # Optional: Close if empty?
             try:
                 self.input_entry.tk.call('ttk::combobox::Unpost', self.input_entry)
             except:
                 pass

    def _colorize_combo_items(self):
        """Attempts to colorize the items in the dropdown listbox."""
        # Delay slightly to allow listbox list to populate
        self.after(100, self._apply_colors)

    def _apply_colors(self):
        try:
            # Get the popdown window
            popdown = self.input_entry.tk.call('ttk::combobox::PopdownWindow', self.input_entry)
            listbox_path = f"{popdown}.f.l"
            
            if not self.input_entry.tk.call('winfo', 'exists', listbox_path):
                return
            
            # Colors
            c_bg = getattr(Styles, 'COLOR_INPUT_BG', '#313338')
            c_fg = getattr(Styles, 'COLOR_FG_TEXT', '#f2f3f5')
            
            # Configure Listbox
            self.input_entry.tk.call(listbox_path, 'configure', '-background', c_bg)
            self.input_entry.tk.call(listbox_path, 'configure', '-foreground', c_fg)
            self.input_entry.tk.call(listbox_path, 'configure', '-selectbackground', Styles.COLOR_ACCENT)
            self.input_entry.tk.call(listbox_path, 'configure', '-selectforeground', '#ffffff')

        except Exception as e:
            print(f"Error coloring combobox: {e}")

    def _on_enter(self, event):
        self._on_send()

    def _on_send(self):
        text = self.input_entry.get().strip()
        if not text:
            return
            
        self._log(f"> {text}")
        self.input_entry.set("")
        
        # Parse command
        parts = text.split()
        if not parts: return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 1. Built-in Commands
        if cmd == "help":
            self._log("Comandos disponibles: help, clear, exit, cambiar colores [rojo|azul|verde|amarillo]")
            return
        elif cmd == "clear":
            self.output_text.config(state="normal")
            self.output_text.delete("1.0", tk.END)
            self.output_text.config(state="disabled")
            return
        elif cmd == "exit":
            self.quit()
            return

        # 2. Addons search
        try:
            import importlib
            import os
            
            # Try to find the longest matching addon command
            # e.g., "copia de codigo arg1" -> tries "copia_de_codigo", then "copia_de", then "copia"
            module_name = None
            remaining_args = []
            all_words = [cmd] + args
            
            for i in range(len(all_words), 0, -1):
                potential_name = "_".join(all_words[:i])
                addon_path = os.path.join("src", "addons", f"{potential_name}.py")
                if os.path.exists(addon_path):
                    module_name = potential_name
                    remaining_args = all_words[i:]
                    break
            
            if module_name:
                module = importlib.import_module(f"src.addons.{module_name}")
                importlib.reload(module)
                
                if hasattr(self.master.master, 'controller'):
                    app = self.master.master.controller.app
                    result = module.run(app, remaining_args)
                    if result:
                        self._log(str(result))
                else:
                    self._log("Error: No se pudo acceder a la aplicación.")
            else:
                self._log(f"Comando '{cmd}' no encontrado.")
                
        except Exception as e:
            self._log(f"Error ejecutando comando: {e}")

    def _log(self, message):
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")
