"""Refusal boundaries for exact-source CAD/native identity projection."""
import copy
from pathlib import Path
import tempfile
import unittest

from native_identity_source import (
    CadIdentityMap,
    RELEASE_MODELS,
    magnifier_installation,
    validate_path_projection,
    validate_release_pair,
)


ROOT = Path(__file__).resolve().parents[2]


class NativeIdentitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity_map = CadIdentityMap(ROOT)

    def test_established_release_rejects_wrong_source_or_raw_identity(self):
        for commit, digest in RELEASE_MODELS.items():
            with self.subTest(commit=commit, boundary="raw"), self.assertRaisesRegex(ValueError, "requires the existing raw"):
                validate_release_pair(commit, "0" * 64)
            with self.subTest(commit=commit, boundary="source"), self.assertRaisesRegex(ValueError, "exact source commit"):
                validate_release_pair("0" * 40, digest)

    def test_changed_map_bytes_refuse_even_if_identity_json_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = repo / "cad/config/identity-migration-map.json"
            path.parent.mkdir(parents=True)
            path.write_bytes((ROOT / "cad/config/identity-migration-map.json").read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "differs from pinned"):
                CadIdentityMap(repo)

    def test_archive_resolution_refuses_missing_or_ambiguous_original_files(self):
        logical = "scripts/mg_lever_wire_geom.py"
        original = self.identity_map.original_paths["cad/" + logical]
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            cad.mkdir()
            with self.assertRaisesRegex(ValueError, "Missing archived CAD source"):
                self.identity_map.source_file(cad, logical)
            old = cad.parent / original
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_text("WIRE_DIA = 0.8\n")
            (cad / logical).write_text("WIRE_DIA = 9.0\n")
            with self.assertRaisesRegex(ValueError, "Ambiguous archived CAD source"):
                self.identity_map.source_file(cad, logical)

    def projection_fixture(self):
        raw = {
            "harmonic-analyzer": [1.0],
            "harmonic-analyzer/magnifier": [2.0],
            "harmonic-analyzer/magnifier/magnifying-wheel-1": [3.0],
            "Camera": [4.0],
        }
        projection = {
            "rawSha256": "a" * 64,
            "identity": {
                "mapSha256": self.identity_map.sha256,
                "canonicalSha256": "b" * 64,
                "renamedNodes": 3,
                "nodeCount": 4,
            },
            "paths": [
                {"source": "harmonic-analyzer", "canonical": "ha-harmonic-analyzer"},
                {"source": "harmonic-analyzer/magnifier", "canonical": "ha-harmonic-analyzer/mg-magnifier"},
                {"source": "harmonic-analyzer/magnifier/magnifying-wheel-1",
                 "canonical": "ha-harmonic-analyzer/mg-magnifier/mg-magnifying-wheel-1"},
            ],
        }
        return raw, projection

    def test_projection_rejects_wrong_raw_map_or_missing_canonical_digest(self):
        raw, projection = self.projection_fixture()
        for boundary in ("raw", "map", "canonical"):
            changed = copy.deepcopy(projection)
            if boundary == "raw":
                changed["rawSha256"] = "c" * 64
            elif boundary == "map":
                changed["identity"]["mapSha256"] = "c" * 64
            else:
                changed["identity"].pop("canonicalSha256")
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                validate_path_projection(raw, "a" * 64, changed, self.identity_map)

    def test_projection_rejects_unknown_missing_duplicate_or_colliding_paths(self):
        raw, projection = self.projection_fixture()
        for boundary in ("unknown", "missing", "missing-root", "source-duplicate", "canonical-collision", "outside-native"):
            changed = copy.deepcopy(projection)
            if boundary == "unknown":
                changed["paths"][-1]["source"] = "harmonic-analyzer/magnifier/unknown-1"
            elif boundary == "missing":
                changed["paths"].pop()
            elif boundary == "missing-root":
                changed["paths"].pop(0)
            elif boundary == "source-duplicate":
                changed["paths"][-1]["source"] = changed["paths"][1]["source"]
            elif boundary == "canonical-collision":
                changed["paths"][-1]["canonical"] = changed["paths"][1]["canonical"]
            else:
                changed["paths"][-1]["canonical"] = "Camera"
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                validate_path_projection(raw, "a" * 64, changed, self.identity_map)

    def test_missing_or_non_numeric_assembly_datum_has_no_layout_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build_magnifier_assembly.py"
            for source in (
                "LEVER_ROD_Y = 979.7\nLEVER_ROD_Z = -128.3\nFIXTURE_Y0 = 915.7\n",
                "LEVER_ROD_Y = 979.7\nLEVER_ROD_Z = -128.3\nVROD_TOP_Y = unsupported_geometry()\nFIXTURE_Y0 = 915.7\n",
            ):
                path.write_text(source)
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, "magnifier installation datum"):
                    magnifier_installation(path)


if __name__ == "__main__":
    unittest.main()
