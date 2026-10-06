"""Native inventory consumer and refusal boundaries; no GPU/source-pixel oracle."""
import copy
import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter = load_script("export-native-inventory.py", "native_inventory_exporter")


def write_fixture(path, document):
    text = json.dumps(document, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    vertices = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, 28 + len(text) + len(vertices))
        + struct.pack("<II", len(text), 0x4E4F534A) + text
        + struct.pack("<II", len(vertices), 0x004E4942) + vertices
    )


class NativeInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.model = Path(cls.directory.name) / "native.glb"
        cls.document = {
            "asset": {"version": "2.0"}, "scene": 0,
            "scenes": [{"nodes": [3, 0]}],
            "nodes": [
                {"name": "harmonic-analyzer", "children": [1],
                 "translation": [1, 2, 3], "rotation": [0, 0, math.sqrt(0.5), math.sqrt(0.5)]},
                {"name": "magnifier", "children": [2], "translation": [2, 0, 0]},
                {"name": "magnifying-lever-1", "mesh": 0,
                 "translation": [0, 3, 0], "scale": [2, 1, 1]},
                {"name": "current camera"},
            ],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}},
                                         {"attributes": {"POSITION": 0}}]}],
            "buffers": [{"byteLength": 36}],
            "bufferViews": [{"buffer": 0, "byteLength": 36}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
        }
        write_fixture(cls.model, cls.document)
        cls.projection = json.loads(subprocess.check_output(
            ["node", str(HERE / "native-identity-map.mjs"), "--model", str(cls.model), "--paths-only"],
            text=True,
        ))
        cls.digest = cls.projection["rawSha256"]
        cls.commit = "0" * 40
        cls.approved = {
            "source": {"sha256": cls.digest, "sourceCommit": cls.commit},
            "identity": cls.projection["identity"],
            "equivalence": {"drawableCount": 2},
        }
        cls.identity_map = exporter.CadIdentityMap(ROOT)
        _, cls.metadata, cls.raw_nodes, _ = exporter.read_native_nodes(cls.model)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def assemble(self, **overrides):
        arguments = {
            "document": self.document, "metadata": self.metadata,
            "raw_nodes": self.raw_nodes, "raw_sha256": self.digest,
            "projection": self.projection, "approved": self.approved,
            "identity_map": self.identity_map, "source_commit": self.commit,
            "expected_model_sha256": self.digest,
        }
        arguments.update(overrides)
        return exporter.assemble_inventory(**arguments)

    def test_actual_fitter_consumes_nested_native_metres_without_root_camera_or_clone_rows(self):
        fitter = load_script("fit-source.py", "native_inventory_fitter")
        inventory = self.assemble()
        part = "ha-harmonic-analyzer/mg-magnifier/mg-magnifying-lever-1"
        observations = {
            "model": {"sha256": self.digest},
            "anchors": [{"id": "local-witness", "partPath": part,
                         "partLocalMetres": [1, 2, 0],
                         "correspondenceEvidence": "Synthetic transform-order control, not a source measurement"}],
        }
        point = fitter.world_points(observations, inventory)["local-witness"]
        for actual, expected in zip(point, [-4, 6, 3]):
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertEqual({row["path"] for row in inventory["inventory"]},
                         {"ha-harmonic-analyzer/mg-magnifier", part})
        self.assertEqual(inventory["census"]["releasedDescendantRestMatrixCount"], 2)
        self.assertEqual(inventory["census"]["artifactDrawableCount"], 2)
        self.assertEqual(inventory["census"]["releasedMeshNodeCount"], 1)
        self.assertEqual(inventory["census"]["nonNativeNodeCount"], 1)
        with self.assertRaisesRegex(ValueError, "Model hash differs"):
            fitter.world_points({**observations, "model": {"sha256": "f" * 64}}, inventory)

    def test_wrong_source_raw_identity_or_canonical_epoch_cannot_produce_inventory(self):
        for boundary in ("source", "raw", "canonical", "map"):
            projection = copy.deepcopy(self.projection)
            overrides = {"projection": projection}
            if boundary == "source":
                overrides["source_commit"] = "1" * 40
            elif boundary == "raw":
                overrides["raw_sha256"] = "f" * 64
            elif boundary == "canonical":
                projection["identity"]["canonicalSha256"] = "f" * 64
            else:
                projection["identity"]["mapSha256"] = "f" * 64
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                self.assemble(**overrides)

    def test_ambiguous_native_paths_are_not_overwritten(self):
        document = copy.deepcopy(self.document)
        document["nodes"].append(copy.deepcopy(document["nodes"][2]))
        document["nodes"][1]["children"].append(4)
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "duplicate.glb"
            write_fixture(model, document)
            with self.assertRaisesRegex(ValueError, "Duplicate qualified model path"):
                exporter.read_native_nodes(model)
        projection = copy.deepcopy(self.projection)
        projection["paths"][-1]["canonical"] = projection["paths"][-2]["canonical"]
        with self.assertRaisesRegex(ValueError, "bijective"):
            self.assemble(projection=projection)

    def test_publication_preserves_raw_bytes_and_refuses_a_hard_link_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "raw.glb"
            output = Path(directory) / "inventory.json"
            alias = Path(directory) / "raw-alias.json"
            write_fixture(model, self.document)
            original = model.read_bytes()
            authority = {"projection": self.projection, "approved": self.approved}
            arguments = ["export-native-inventory.py", "--model", str(model),
                         "--source-commit", self.commit, "--expected-model-sha256", self.digest]
            with patch.object(exporter, "native_authority", return_value=authority):
                with patch("sys.argv", [*arguments, "--output", str(output)]), contextlib.redirect_stdout(io.StringIO()):
                    exporter.main()
                self.assertEqual(model.read_bytes(), original)
                fitter = load_script("fit-source.py", "native_inventory_publication_fitter")
                point = fitter.world_points({
                    "model": {"sha256": self.digest},
                    "anchors": [{"id": "published-witness",
                                 "partPath": "ha-harmonic-analyzer/mg-magnifier/mg-magnifying-lever-1",
                                 "partLocalMetres": [1, 2, 0],
                                 "correspondenceEvidence": "Independent synthetic transform-order control"}],
                }, json.loads(output.read_text()))["published-witness"]
                for actual, expected in zip(point, [-4, 6, 3]):
                    self.assertAlmostEqual(actual, expected, places=12)
                alias.hardlink_to(model)
                with patch("sys.argv", [*arguments, "--output", str(alias)]), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as refusal:
                        exporter.main()
                self.assertEqual(refusal.exception.code, 2)
            self.assertEqual(model.read_bytes(), original)
            self.assertEqual(alias.read_bytes(), original)

    def test_malformed_transforms_are_rejected_not_repaired_or_defaulted(self):
        identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        perspective = identity.copy()
        perspective[3] = 0.1
        transforms = (
            {"translation": [0, 0]}, {"translation": [True, 0, 0]},
            {"translation": [math.nan, 0, 0]}, {"rotation": [0, 0, 0, 0]},
            {"rotation": [0, 0, 0, 2]}, {"scale": [1, 0, 1]},
            {"matrix": identity[:-1]}, {"matrix": perspective},
            {"matrix": identity, "translation": [0, 0, 0]},
        )
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "malformed.glb"
            for transform in transforms:
                document = copy.deepcopy(self.document)
                document["nodes"][2] = {"name": "magnifying-lever-1", "mesh": 0, **transform}
                write_fixture(model, document)
                with self.subTest(transform=transform), self.assertRaises(ValueError):
                    exporter.read_native_nodes(model)


if __name__ == "__main__":
    unittest.main()
