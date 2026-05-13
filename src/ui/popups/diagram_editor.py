import atexit
import os
import subprocess
import sys
from pathlib import Path


class DiagramEditorWindow:
    def __init__(self, parent, on_close=None):
        self.parent = parent
        self._on_close = on_close
        self._process = None
        self._poll_job = None
        self._launch()
        atexit.register(self.close)

    def _launch(self):
        script_path = Path(__file__).with_name("diagram_webview_app.py")
        project_root = script_path.parents[3]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--diagram-webview"]
        else:
            cmd = [sys.executable, str(script_path)]

        self._process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            env=env,
        )
        self._schedule_poll()

    def _schedule_poll(self):
        if self.parent is None:
            return
        if self._poll_job is not None:
            try:
                self.parent.after_cancel(self._poll_job)
            except Exception:
                pass
        self._poll_job = self.parent.after(1200, self._poll_process)

    def _poll_process(self):
        self._poll_job = None
        if self.winfo_exists():
            self._schedule_poll()
            return
        self._notify_closed()

    def _notify_closed(self):
        if callable(self._on_close):
            try:
                self._on_close()
            except Exception:
                pass

    def winfo_exists(self):
        return self._process is not None and self._process.poll() is None

    def deiconify(self):
        return None

    def lift(self):
        return None

    def focus_force(self):
        return None

    def close(self):
        if self._poll_job is not None and self.parent is not None:
            try:
                self.parent.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

        if self._process is not None and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass
        self._process = None
