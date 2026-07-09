import os
import tempfile
import unittest

from src.addons import sus_mod


class _ProjectManager:
    def __init__(self, root, files):
        self.current_project_path = root
        self._files = files

    def get_files(self):
        return self._files


class _Controller:
    def __init__(self, root, files):
        self.project_manager = _ProjectManager(root, files)

    def refresh_cached_file_content(self, path, content=None):
        for file_info in self.project_manager.get_files():
            if file_info["path"] == path:
                file_info["content"] = content
                return True
        return False


class _App:
    def __init__(self, root, files):
        self.controller = _Controller(root, files)


class SusModTests(unittest.TestCase):
    def _build_app(self, tmpdir, rel_path, content):
        file_path = os.path.join(tmpdir, rel_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        files = [{"path": file_path, "rel_path": rel_path, "content": content}]
        return _App(tmpdir, files), file_path

    def test_applies_inline_and_block_modification_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = (
                "const mainWindow = new BrowserWindow({\n"
                "  height: 900,\n"
                "  minWidth: 800,\n"
                "  minHeight: 600,\n"
                "  title: 'GeoFlow Designer',\n"
                "  webPreferences: {\n"
                "    nodeIntegration: false,\n"
                "    contextIsolation: true,\n"
                "    preload: path.join(__dirname, 'preload.js')\n"
                "  },\n"
                "  icon: path.join(__dirname, 'app', 'icon.png')\n"
                "});\n"
                "\n"
                "mainWindow.loadFile(path.join(__dirname, 'app', 'index.html'));\n"
                "\n"
                "// Menu de la aplicación\n"
            )
            app, file_path = self._build_app(tmpdir, "src/main.js", original)
            clipboard = (
                "```javascript\n"
                "// Archivo: src/main.js\n"
                "  height: 900,\n"
                "  minWidth: 800,\n"
                "  minHeight: 600,\n"
                "  title: 'GeoFlow Designer',\n"
                "  backgroundColor: backgroundColor, // [MODIFICACIÓN] Color de fondo para evitar flash\n"
                "  webPreferences: {\n"
                "    nodeIntegration: false,\n"
                "    contextIsolation: true,\n"
                "    preload: path.join(__dirname, 'preload.js')\n"
                "  },\n"
                "  icon: path.join(__dirname, 'app', 'icon.png')\n"
                "});\n"
                "\n"
                "mainWindow.loadFile(path.join(__dirname, 'app', 'index.html'));\n"
                "\n"
                "// [MODIFICACIÓN] Enviar el tema inicial al renderer\n"
                "mainWindow.webContents.on('did-finish-load', () => {\n"
                "  const initialTheme = nativeTheme.shouldUseDarkColors ? 'dark' : 'light';\n"
                "  mainWindow.webContents.send('initial-theme', initialTheme);\n"
                "});\n"
                "\n"
                "// Menu de la aplicación\n"
                "```\n"
            )

            results = sus_mod.apply_sus_mod_substitutions(app, clipboard)

            self.assertEqual(results["failed"], 0)
            self.assertEqual(results["success"], 1)
            with open(file_path, "r", encoding="utf-8") as fh:
                updated = fh.read()
            self.assertIn("backgroundColor: backgroundColor,", updated)
            self.assertIn("mainWindow.webContents.on('did-finish-load'", updated)
            self.assertNotIn("[MODIFICACIÓN]", updated)

    def test_resolves_unique_file_without_explicit_file_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app, file_path = self._build_app(
                tmpdir,
                "app.py",
                "def build():\n    title = 'Old'\n    return title\n",
            )
            other_path = os.path.join(tmpdir, "other.py")
            with open(other_path, "w", encoding="utf-8") as fh:
                fh.write("def other():\n    return 'x'\n")
            app.controller.project_manager.get_files().append({
                "path": other_path,
                "rel_path": "other.py",
                "content": "def other():\n    return 'x'\n",
            })

            clipboard = (
                "```python\n"
                "def build():\n"
                "    title = 'New'  # [MODIFICACIÓN] Nuevo título\n"
                "    return title\n"
                "```\n"
            )

            results = sus_mod.apply_sus_mod_substitutions(app, clipboard)

            self.assertEqual(results["failed"], 0)
            with open(file_path, "r", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "def build():\n    title = 'New'\n    return title\n")


if __name__ == "__main__":
    unittest.main()
