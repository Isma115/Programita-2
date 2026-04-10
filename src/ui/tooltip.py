import tkinter as tk

from src.ui.styles import Styles


class Tooltip:
    def __init__(self, widget, text, delay=350):
        self.widget = widget
        self.text = (text or "").strip()
        self.delay = delay
        self._job = None
        self._window = None

        if not self.text:
            return

        self.widget.bind("<Enter>", self._schedule_show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")
        self.widget.bind("<Destroy>", self._hide, add="+")

    def _schedule_show(self, event=None):
        self._cancel_job()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel_job(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        self._job = None
        if self._window is not None or not self.widget.winfo_exists():
            return

        try:
            state = str(self.widget.cget("state"))
            if state == "disabled":
                return
        except Exception:
            pass

        self._window = tk.Toplevel(self.widget)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(bg=Styles.COLOR_BG_MAIN)

        label = tk.Label(
            self._window,
            text=self.text,
            bg=Styles.COLOR_BG_MAIN,
            fg=Styles.COLOR_FG_TEXT,
            relief="solid",
            bd=1,
            padx=10,
            pady=6,
            font=("Segoe UI", 10, "bold"),
            highlightthickness=1,
            highlightbackground=Styles.COLOR_BORDER,
        )
        label.pack()

        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self._window.geometry(f"+{x}+{y}")
        self._window.deiconify()

    def _hide(self, event=None):
        self._cancel_job()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None


def attach_tooltip(widget, text, delay=350):
    tooltip = Tooltip(widget, text, delay=delay)
    setattr(widget, "_tooltip_helper", tooltip)
    return tooltip
