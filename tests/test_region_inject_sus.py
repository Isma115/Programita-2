import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.addons import region_inject_sus


class _ProjectManager:
    def __init__(self, root, files):
        self.current_project_path = root
        self._files = files

    def get_files(self):
        return self._files


class _Controller:
    def __init__(self, root, files):
        self.project_manager = _ProjectManager(root, files)
        self.refreshed = {}

    def refresh_cached_file_content(self, path, content=None):
        self.refreshed[path] = content
        return True


def _build_app(root, files):
    return SimpleNamespace(controller=_Controller(root, files))


class _Root:
    def __init__(self, clipboard_text):
        self._clipboard_text = clipboard_text

    def clipboard_get(self):
        return self._clipboard_text


class _CodeView:
    def __init__(self):
        self.refreshed = False

    def refresh_file_list(self):
        self.refreshed = True


class RegionInjectSusTests(unittest.TestCase):
    def test_parse_clipboard_regions_with_file_marker(self):
        regions = region_inject_sus.parse_clipboard_regions(
            "Archivo: app/main.js\n"
            "// #region Toolbar\n"
            "const color = 'blue';\n"
            "// #endregion\n"
        )

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["file_hint"], "app/main.js")
        self.assertEqual(regions[0]["header"], "Toolbar")
        self.assertIn("const color = 'blue';", regions[0]["content"])

    def test_parse_clipboard_regions_from_markdown_code_block(self):
        regions = region_inject_sus.parse_clipboard_regions(
            "```js\n"
            "// Archivo: app/main.js\n"
            "// #region Toolbar\n"
            "const color = 'blue';\n"
            "// #endregion\n"
            "```\n"
        )

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["file_hint"], "app/main.js")
        self.assertEqual(regions[0]["header"], "Toolbar")
        self.assertIn("const color = 'blue';", regions[0]["content"])

    def test_apply_region_injection_replaces_matching_region(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "app", "main.js")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            original = (
                "before();\n"
                "// #region Toolbar\n"
                "const color = 'red';\n"
                "// #endregion\n"
                "after();\n"
            )
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(original)

            files = [{
                "path": file_path,
                "rel_path": "app/main.js",
                "content": original,
            }]
            app = _build_app(tmpdir, files)
            clipboard = (
                "Archivo: app/main.js\n"
                "// #region Toolbar\n"
                "const color = 'blue';\n"
                "// #endregion\n"
            )

            results = region_inject_sus.apply_region_injections(app, clipboard)

            self.assertEqual(results["success"], 1)
            self.assertEqual(results["failed"], 0)
            with open(file_path, "r", encoding="utf-8") as fh:
                self.assertEqual(
                    fh.read(),
                    "before();\n"
                    "// #region Toolbar\n"
                    "const color = 'blue';\n"
                    "// #endregion\n"
                    "after();\n",
                )
            self.assertIn(file_path, app.controller.refreshed)

    def test_process_region_injection_is_silent_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "app", "main.js")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            original = (
                "// #region Toolbar\n"
                "const color = 'red';\n"
                "// #endregion\n"
            )
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(original)

            files = [{
                "path": file_path,
                "rel_path": "app/main.js",
                "content": original,
            }]
            clipboard = (
                "```js\n"
                "// Archivo: app/main.js\n"
                "// #region Toolbar\n"
                "const color = 'blue';\n"
                "// #endregion\n"
                "```\n"
            )
            app = _build_app(tmpdir, files)
            code_view = _CodeView()
            app.root = _Root(clipboard)
            app.layout = SimpleNamespace(code_view=code_view)

            with patch.object(region_inject_sus.messagebox, "showerror") as showerror:
                handled = region_inject_sus.process_region_injection(app)

            self.assertTrue(handled)
            showerror.assert_not_called()
            self.assertTrue(code_view.refreshed)
            with open(file_path, "r", encoding="utf-8") as fh:
                self.assertIn("const color = 'blue';", fh.read())


if __name__ == "__main__":
    unittest.main()
