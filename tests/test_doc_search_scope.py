import os
import tempfile
import unittest

from src.ui.tabs.doc_view import DocView


class _DocumentSearchScopeStub:
    def __init__(self, tree_items):
        self.tree_items = tree_items

    def _iter_section_tree_items(self):
        return iter(self.tree_items)

    @staticmethod
    def _is_descendant_path(base_path, candidate_path):
        try:
            return os.path.commonpath([
                os.path.normpath(base_path),
                os.path.normpath(candidate_path),
            ]) == os.path.normpath(base_path)
        except Exception:
            return False


class DocumentSearchScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = self.temp_dir.name
        self.section_a = os.path.join(root, "Sección A")
        self.section_b = os.path.join(root, "Sección B")
        os.makedirs(self.section_a)
        os.makedirs(self.section_b)

        self.file_a = os.path.join(self.section_a, "uno.md")
        self.file_b = os.path.join(self.section_b, "dos.md")
        with open(self.file_a, "w", encoding="utf-8") as file_handle:
            file_handle.write("contenido A")
        with open(self.file_b, "w", encoding="utf-8") as file_handle:
            file_handle.write("contenido B")

        self.view = _DocumentSearchScopeStub([
            self.section_a,
            self.file_a,
            self.section_b,
            self.file_b,
        ])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_no_selection_searches_all_markdown_files(self):
        candidates = DocView._get_document_search_candidates(self.view, ())

        self.assertEqual(candidates, [self.file_a, self.file_b])

    def test_section_selection_limits_search_to_descendants(self):
        candidates = DocView._get_document_search_candidates(
            self.view,
            (self.section_a,),
        )

        self.assertEqual(candidates, [self.file_a])

    def test_file_selection_limits_search_to_that_file(self):
        candidates = DocView._get_document_search_candidates(
            self.view,
            (self.file_b,),
        )

        self.assertEqual(candidates, [self.file_b])


if __name__ == "__main__":
    unittest.main()
