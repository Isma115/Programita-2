import os
import tempfile
import unittest
from types import SimpleNamespace

from src.addons import Arbitrary_sus


def _build_app(project_root, project_files=None):
    project_manager = SimpleNamespace(
        current_project_path=project_root,
        get_files=lambda: project_files or [],
    )
    controller = SimpleNamespace(project_manager=project_manager)
    return SimpleNamespace(controller=controller)


class ArbitraryExplicitFileHintTests(unittest.TestCase):
    def test_extracts_file_marker_from_code_comment(self):
        path_hint, cleaned = Arbitrary_sus._extract_clipboard_file_hint(
            "# Archivo: src/example.py\n"
            "def main():\n"
            "    return 1\n"
        )

        self.assertEqual(path_hint, "src/example.py")
        self.assertEqual(cleaned, "def main():\n    return 1")

    def test_resolves_relative_project_file_not_in_code_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "src", "hidden.py")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")

            app = _build_app(tmpdir)

            resolved = Arbitrary_sus._resolve_project_file_hint(
                app,
                "src/hidden.py",
                code_files=[],
            )

            self.assertEqual(resolved, os.path.normpath(file_path))

    def test_resolves_project_manager_file_not_in_visible_code_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "pkg", "target.py")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")

            app = _build_app(
                tmpdir,
                project_files=[{"path": file_path, "rel_path": "pkg/target.py"}],
            )

            resolved = Arbitrary_sus._resolve_project_file_hint(
                app,
                "pkg/target.py",
                code_files=[],
            )

            self.assertEqual(resolved, os.path.normpath(file_path))


class ArbitraryFuzzyMatchTests(unittest.TestCase):
    def test_fuzzy_rejects_single_common_line_as_match(self):
        search_text = (
            "function buildInvoiceView() {\n"
            "  const rows = getInvoiceRows(invoice);\n"
            "  renderInvoiceTable(rows);\n"
            "  return rows.length;\n"
            "}\n"
        )
        loaded_files = [(
            "/tmp/unrelated.js",
            "function buildInvoiceView() {\n"
            "  const user = getCurrentUser();\n"
            "  renderProfile(user);\n"
            "  return user.name;\n"
            "}\n",
        )]

        match, file_path, ratio, line_num = Arbitrary_sus._fuzzy_match_region(search_text, loaded_files)

        self.assertIsNone(match)
        self.assertIsNone(file_path)
        self.assertEqual(ratio, 0.0)
        self.assertEqual(line_num, -1)

    def test_fuzzy_returns_substantial_matching_span(self):
        search_text = (
            "function buildInvoiceView() {\n"
            "  const rows = getInvoiceRows(invoice);\n"
            "  const total = calculateInvoiceTotal(rows);\n"
            "  renderInvoiceTable(rows, total);\n"
            "  return rows.length;\n"
            "}\n"
        )
        project_text = (
            "const unrelated = true;\n"
            "\n"
            "function buildInvoiceView() {\n"
            "  const rows = getInvoiceRows(invoice);\n"
            "  const total = calculateInvoiceSubtotal(rows);\n"
            "  renderInvoiceTable(rows, total);\n"
            "  return rows.length;\n"
            "}\n"
            "\n"
            "export default buildInvoiceView;\n"
        )
        loaded_files = [("/tmp/invoice.js", project_text)]

        match, file_path, ratio, line_num = Arbitrary_sus._fuzzy_match_region(search_text, loaded_files)

        self.assertEqual(file_path, "/tmp/invoice.js")
        self.assertEqual(line_num, 3)
        self.assertLessEqual(ratio, 1.0)
        self.assertGreaterEqual(ratio, 0.68)
        self.assertIn("function buildInvoiceView()", match)
        self.assertIn("calculateInvoiceSubtotal", match)

    def test_find_similar_region_does_not_return_whole_file_for_low_similarity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "target.js")
            file_content = (
                "export function profileCard(user) {\n"
                "  return `<section>${user.name}</section>`;\n"
                "}\n"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)

            match, matched_file, ratio, line_num = Arbitrary_sus.find_similar_region(
                [file_path],
                "def calculate_irrigation_plan(zone):\n"
                "    return zone.moisture * 3\n",
            )

            self.assertIsNone(match)
            self.assertIsNone(matched_file)
            self.assertEqual(ratio, 0)
            self.assertEqual(line_num, -1)


if __name__ == "__main__":
    unittest.main()
