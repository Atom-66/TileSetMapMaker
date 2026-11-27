import os
import unittest

from tileset_map_maker.core.localization_audit import run_localization_audit


class TestLocalizationCompletenessAudit(unittest.TestCase):
    def test_dictionaries_and_ui_have_zero_localization_errors(self):
        pkg_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "tileset_map_maker")
        )
        report = run_localization_audit(pkg_root)

        self.assertEqual(report.duplicate_en_keys, {}, f"Duplicate EN keys: {report.duplicate_en_keys}")
        self.assertEqual(report.duplicate_pl_keys, {}, f"Duplicate PL keys: {report.duplicate_pl_keys}")
        self.assertEqual(report.missing_in_en, [], f"Keys missing in EN: {report.missing_in_en}")
        self.assertEqual(report.missing_in_pl, [], f"Keys missing in PL: {report.missing_in_pl}")
        self.assertEqual(report.empty_en_keys, [], f"Empty EN keys: {report.empty_en_keys}")
        self.assertEqual(report.empty_pl_keys, [], f"Empty PL keys: {report.empty_pl_keys}")
        self.assertEqual(report.param_mismatches, [], f"Param mismatches: {report.param_mismatches}")
        self.assertEqual(report.missing_code_keys, [], f"Missing code keys: {report.missing_code_keys}")
        self.assertEqual(
            report.hardcoded_ui_strings,
            [],
            f"Hardcoded UI strings found: {report.hardcoded_ui_strings}",
        )

    def test_polish_and_english_plural_categories(self):
        # Pure Python check of CLDR plural rules without requiring Qt
        import ast

        loc_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "tileset_map_maker",
                "core",
                "localization.py",
            )
        )
        with open(loc_path, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        fn_node = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plural_category"
        )
        from typing import Optional
        ns = {"Optional": Optional}
        exec(compile(ast.Module(body=[fn_node], type_ignores=[]), loc_path, "exec"), ns)
        plural_category = ns["plural_category"]

        self.assertEqual(plural_category(1, "pl"), "one")
        self.assertEqual(plural_category(2, "pl"), "few")
        self.assertEqual(plural_category(3, "pl"), "few")
        self.assertEqual(plural_category(4, "pl"), "few")
        self.assertEqual(plural_category(5, "pl"), "many")
        self.assertEqual(plural_category(12, "pl"), "many")
        self.assertEqual(plural_category(14, "pl"), "many")
        self.assertEqual(plural_category(22, "pl"), "few")
        self.assertEqual(plural_category(0, "pl"), "many")
        self.assertEqual(plural_category(1, "en"), "one")
        self.assertEqual(plural_category(2, "en"), "many")
        self.assertEqual(plural_category(0, "en"), "many")


if __name__ == "__main__":
    unittest.main()
