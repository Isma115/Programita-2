import os
import tempfile
import unittest

from src.addons import bridge_sus


class BridgeSusPatchTests(unittest.TestCase):
    def test_parse_incremental_patch_response(self):
        response = """[[[ ARCHIVO: src/example.py ]]]
[[[ PATCH
@@ INSERT_AFTER
FIND:
def main():
CONTENT:
    setup()

@@ REPLACE
FIND:
return old_value
WITH:
return new_value
PATCH ]]]"""

        changes = bridge_sus.parse_ai_response(response)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "patch")
        self.assertEqual(changes[0]["file"], "src/example.py")
        self.assertEqual(
            changes[0]["operations"],
            [
                {"op": "insert_after", "find": "def main():", "content": "    setup()"},
                {"op": "replace", "find": "return old_value", "with": "return new_value"},
            ],
        )

    def test_apply_incremental_patch_without_repeating_original_block(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "example.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("def main():\n    return old_value\n")

            changes = [{
                "type": "patch",
                "file": "example.py",
                "operations": [
                    {"op": "insert_after", "find": "def main():", "content": "    setup()"},
                    {"op": "replace", "find": "return old_value", "with": "return new_value"},
                ],
            }]

            results = bridge_sus._apply_changes(tmpdir, changes)

            self.assertEqual(results["success"], 2)
            self.assertEqual(results["failed"], 0)
            with open(file_path, "r", encoding="utf-8") as f:
                self.assertEqual(
                    f.read(),
                    "def main():\n    setup()\n    return new_value\n",
                )

    def test_apply_patch_uses_line_fallback_when_find_anchor_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "toolbar.css")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(".toolbar {\n    color: red;\n}\n")

            changes = [{
                "type": "patch",
                "file": "toolbar.css",
                "operations": [{
                    "op": "replace",
                    "line": "2",
                    "find": "color: blue;",
                    "with": "    color: green;",
                }],
            }]

            results = bridge_sus._apply_changes(tmpdir, changes)

            self.assertEqual(results["success"], 1)
            self.assertEqual(results["failed"], 0)
            self.assertIn("fallback LINE", results["details"][0])
            with open(file_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), ".toolbar {\n    color: green;\n}\n")

    def test_parse_patch_operation_line_section(self):
        response = """[[[ ARCHIVO: app/css/toolbar.css ]]]
[[[ PATCH
@@ INSERT_AFTER
LINE:
12
FIND:
.toolbar {
CONTENT:
    gap: 8px;
PATCH ]]]"""

        changes = bridge_sus.parse_ai_response(response)

        self.assertEqual(
            changes[0]["operations"][0],
            {
                "op": "insert_after",
                "line": "12",
                "find": ".toolbar {",
                "content": "    gap: 8px;",
            },
        )

    def test_legacy_original_modified_format_still_applies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "legacy.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("value = 1\n")

            changes = bridge_sus.parse_ai_response('''[[[ ARCHIVO: legacy.py ]]]
[[[ ORIGINAL
value = 1
ORIGINAL ]]]
]]] MODIFICADO
value = 2
MODIFICADO [[[''')

            results = bridge_sus._apply_changes(tmpdir, changes)

            self.assertEqual(results["success"], 1)
            self.assertEqual(results["failed"], 0)
            with open(file_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "value = 2\n")


if __name__ == "__main__":
    unittest.main()
