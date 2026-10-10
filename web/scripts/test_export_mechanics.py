"""Pure mechanics export contracts across archived and split recipe layouts."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mechanics_exporter", HERE / "export-mechanics.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class TablesProjected(Exception):
    """Stop before the unrelated full-machine geometry imports."""


class MechanicsRecipeTableTests(unittest.TestCase):
    def project_tables(self, thumb_source, fillister_source, specs=None):
        specs = specs or {}
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            diagnostics = cad / "scripts/diagnostics"
            diagnostics.mkdir(parents=True)
            (diagnostics / "diag_mcmaster_thumb.py").write_text(thumb_source)
            (diagnostics / "diag_mcmaster_fillister.py").write_text(fillister_source)
            identity_map = Mock()
            identity_map.source_file.side_effect = lambda root, relative: root / relative

            def import_spec(root, name):
                self.assertEqual(root, cad)
                if name == "_config":
                    raise TablesProjected
                return specs[name]

            identity_map.import_module.side_effect = import_spec
            # The exporter owns these historical projections; isolate them and
            # its archived-source search path from every other test's imports.
            with patch.dict(sys.modules), patch.object(sys, "path", list(sys.path)):
                names = (
                    "diagnostics.diag_mcmaster_thumb",
                    "diagnostics.diag_mcmaster_fillister",
                )
                for name in names:
                    sys.modules.pop(name, None)
                with self.assertRaises(TablesProjected):
                    exporter.export_snapshot(
                        types.SimpleNamespace(), cad.parent, cad, identity_map,
                        {}, {}, "0" * 64,
                    )
                tables = tuple(sys.modules.get(name) for name in names)
            imported = [call.args[1] for call in identity_map.import_module.call_args_list]
            return tables, imported

    def test_archived_fillister_binds_original_and_ms_aliases_from_pinned_specs(self):
        frame = types.SimpleNamespace(
            SHANK_DIA=2.1844, SHANK_LEN=9.525, HEAD_H=2.1082,
            HEAD_DIA=3.556, PITCH=25.4 / 56.0,
        )
        stop = types.SimpleNamespace(
            MAJOR_DIA=2.1844, LENGTH=6.35, HEAD_H=2.1082,
            HEAD_DIA=3.556, PITCH=25.4 / 56.0,
        )
        source = (
            "from vn_frame_cross_screw_spec import SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH\n"
            "from vn_ms_stop_plate_screw_spec import (\n"
            "    MAJOR_DIA as MS_MAJOR_DIA, LENGTH as MS_LENGTH,\n"
            "    HEAD_H as MS_HEAD_H, HEAD_DIA as MS_HEAD_DIA, PITCH as MS_PITCH)\n"
            "from unused_spec import UNUSED\n"
            "import unavailable_com_recipe\n"
            "FILLISTER_SIZES = {\n"
            "    '90280A837': (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH),\n"
            "    '90114A124': (MS_MAJOR_DIA, MS_LENGTH, MS_HEAD_H, MS_HEAD_DIA, MS_PITCH),\n"
            "    '91794A077': (2.1844, 6.35, 2.1082, 3.556, 25.4 / 56.0)}\n"
            "raise AssertionError('COM recipe must not execute')\n"
        )
        (_, fillister), imported = self.project_tables("", source, {
            "vn_frame_cross_screw_spec": frame,
            "vn_ms_stop_plate_screw_spec": stop,
        })
        self.assertEqual(fillister.FILLISTER_SIZES, {
            "90280A837": (frame.SHANK_DIA, frame.SHANK_LEN, frame.HEAD_H, frame.HEAD_DIA, frame.PITCH),
            "90114A124": (stop.MAJOR_DIA, stop.LENGTH, stop.HEAD_H, stop.HEAD_DIA, stop.PITCH),
            "91794A077": (2.1844, 6.35, 2.1082, 3.556, 25.4 / 56.0),
        })
        self.assertEqual(imported, [
            "vn_frame_cross_screw_spec", "vn_ms_stop_plate_screw_spec", "_config",
        ])

    def test_split_recipes_do_not_install_obsolete_central_table_modules(self):
        tables, imported = self.project_tables(
            "import unavailable_com_recipe\n",
            "from _mcmaster_90114a124 import FILLISTER_SIZE, SKU\n",
        )
        self.assertEqual(tables, (None, None))
        self.assertEqual(imported, ["_config"])

    def test_archived_thumb_preserves_supplier_expression_without_recipe_execution(self):
        (thumb, fillister), imported = self.project_tables(
            "import unavailable_com_recipe\n"
            "THUMB_SPECS = {'91375A104': dict(pitch=25.4 / 40.0, length=9.525)}\n"
            "raise AssertionError('COM recipe must not execute')\n",
            "",
        )
        self.assertEqual(thumb.THUMB_SPECS, {
            "91375A104": {"pitch": 25.4 / 40.0, "length": 9.525},
        })
        self.assertIsNone(fillister)
        self.assertEqual(imported, ["_config"])


class MechanicsMatrixContractTests(unittest.TestCase):
    def test_current_ms_component_matrices_are_preserved_without_identity_aliases(self):
        tree = ast.parse((HERE / "export-mechanics.py").read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "export_snapshot")
        data = next(node.value for node in function.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "data"
                            for target in node.targets))
        frames = data.values[next(index for index, key in enumerate(data.keys)
                                  if isinstance(key, ast.Constant) and key.value == "renderFrames")]
        matrices = frames.values[next(index for index, key in enumerate(frames.keys)
                                      if isinstance(key, ast.Constant) and key.value == "worldMatrices")]
        prefix = "ha-harmonic-analyzer/ms-measuring-stick/"
        paths = [prefix + name for name in (
            "ms-stop-block-1", "ms-stop-plate-1", "ms-stick-1",
            "vn-thumb-screw-1", "vn-ms-stop-plate-screw-1", "vn-ms-stop-plate-screw-2",
        )]
        nodes = {path: [index + 0.125] * 16 for index, path in enumerate(paths)}
        nodes["Camera"] = [0.0] * 16
        exported = eval(compile(ast.Expression(matrices), str(HERE / "export-mechanics.py"), "eval"),
                        {"nodes": nodes})
        self.assertEqual(set(exported), set(paths))
        for path in paths:
            self.assertIs(exported[path], nodes[path])


if __name__ == "__main__":
    unittest.main()
