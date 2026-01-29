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
        
        self.input_entry = tk.Entry(
            input_frame,
            bg=Styles.COLOR_INPUT_BG,
            fg=Styles.COLOR_INPUT_FG,
            font=Styles.FONT_CODE,
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.input_entry.bind("<Return>", self._on_enter)
        
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

    def _on_enter(self, event):
        self._on_send()

    def _on_send(self):
        text = self.input_entry.get().strip()
        if not text:
            return
            
        self._log(f"> {text}")
        self.input_entry.delete(0, tk.END)
        # TODO: Process command here

    def _log(self, message):
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")
