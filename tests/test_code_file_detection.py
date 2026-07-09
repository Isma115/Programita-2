import unittest

from src.addons import copia_de_codigo
from src.logic.project_manager import ProjectManager


class CodeFileDetectionTests(unittest.TestCase):
    def test_project_manager_detects_broad_code_extensions(self):
        filenames = [
            "schema.prisma",
            "main.tf",
            "flake.nix",
            "build.bzl",
            "component.astro",
            "notebook.ipynb",
            "query.graphql",
            "model.proto",
            "script.bats",
            "module.pyx",
            "types.pyi",
            "kernel.cu",
            "template.pug",
        ]

        for filename in filenames:
            with self.subTest(filename=filename):
                self.assertTrue(ProjectManager.is_code_file(filename))

    def test_project_manager_detects_code_filenames(self):
        filenames = [
            "Dockerfile",
            "Dockerfile.prod",
            "Makefile",
            "Makefile.am",
            "Justfile",
            "BUILD",
            "WORKSPACE.bazel",
            "meson.build",
        ]

        for filename in filenames:
            with self.subTest(filename=filename):
                self.assertTrue(ProjectManager.is_code_file(filename))

    def test_copia_de_codigo_uses_project_manager_detection(self):
        self.assertTrue(copia_de_codigo._is_code_file("Dockerfile.prod"))
        self.assertTrue(copia_de_codigo._is_code_file("schema.prisma"))
        self.assertTrue(copia_de_codigo._is_code_file("README.md"))
        self.assertFalse(copia_de_codigo._is_code_file("image.png"))


if __name__ == "__main__":
    unittest.main()
