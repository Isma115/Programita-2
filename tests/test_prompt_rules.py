import unittest

from src.logic.controller import Controller
from src.logic.prompt_rules import build_return_regions_instruction


class ReturnRegionsPromptRulesTests(unittest.TestCase):
    def test_return_regions_instruction_is_strict(self):
        instruction = build_return_regions_instruction()

        self.assertIn("regiones completas", instruction)
        self.assertIn("Markdown", instruction)
        self.assertIn("```", instruction)
        self.assertIn("bloque", instruction)
        self.assertIn("#region", instruction)
        self.assertIn("#endregion", instruction)
        self.assertIn("SIN CAMBIOS", instruction)
        self.assertIn("archivos completos", instruction)
        self.assertIn("[MODIFICACION]", instruction)
        self.assertLessEqual(len(instruction.splitlines()), 4)

    def test_controller_uses_strict_return_regions_instruction(self):
        instruction = Controller.get_code_output_prompt(object(), return_regions=True)

        self.assertEqual(instruction, build_return_regions_instruction())


if __name__ == "__main__":
    unittest.main()
