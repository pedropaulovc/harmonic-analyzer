"""Current naming boundaries; archived fixtures and source bytes stay unchanged."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from current_native_identity import (
    CURRENT_NATIVE_IDENTITY_MAP_SHA256, SOURCE_MAP_SHA256, TABLE_PATH,
    CurrentNativeIdentity, current_inventory_parts, project_current_anchor,
    project_current_native_path,
)
from native_identity_source import CadIdentityMap, MAP_SHA256

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "ha-harmonic-analyzer/"


class CurrentNativeIdentityTests(unittest.TestCase):
    def test_path_loaded_consumers_resolve_sibling_adapter_without_scripts_on_sys_path(self):
        code = """
import importlib.util
from pathlib import Path
import sys
assert str(Path(sys.argv[1]).parent) not in sys.path
modules = {}
for index, filename in enumerate(sys.argv[1:-1]):
    spec = importlib.util.spec_from_file_location(f"isolated_consumer_{index}", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    modules[Path(filename).name] = module
old = "ha-harmonic-analyzer/pd-paper-drive/vn-fillister-screw-1"
current = "ha-harmonic-analyzer/pd-paper-drive/pd-vn-fillister-screw-1"
assert modules["compact-source-common.py"].project_current_native_path(old) == current
assert modules["fit-source.py"].project_current_native_path(old) == current
root = Path(sys.argv[-1])
identity = modules["native_identity_source.py"].CadIdentityMap(root)
assert identity.source_file(root / "cad", "config/identity-migration-map.json").is_file()
"""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", code,
                 *(str(scripts / filename) for filename in
                   ("compact-source-common.py", "fit-source.py", "native_identity_source.py")),
                 str(ROOT)],
                cwd=directory, capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_projection_provenance_is_separate_from_sealed_map(self):
        projection = CurrentNativeIdentity()
        self.assertEqual(MAP_SHA256, SOURCE_MAP_SHA256)
        self.assertNotEqual(MAP_SHA256, projection.map_sha256)
        self.assertEqual(projection.provenance, {
            "kind": "current-native-identity-projection",
            "mapSha256": CURRENT_NATIVE_IDENTITY_MAP_SHA256,
            "sourceMapSha256": MAP_SHA256,
        })
        with self.assertRaises(TypeError):
            projection.provenance["mapSha256"] = "0" * 64

    def test_archive_only_parent_does_not_replace_active_parent_identity(self):
        for parent, prefix in (("ch-channel", "ch"), ("dt-drive-train", "dt")):
            path = PREFIX + parent + "/vn-pedestal-hold-down-screw-1"
            self.assertEqual(project_current_native_path(path),
                             PREFIX + parent + "/" + prefix + "-vn-pedestal-hold-down-screw-1")

    def test_current_spring_stock_helper_resolves_exact_sealed_source(self):
        identity = CadIdentityMap(ROOT)
        sealed = "cad/scripts/vn_channel_spring_stock_geom.py"
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            original = cad.parent / identity.original_paths[sealed]
            original.parent.mkdir(parents=True)
            raw = b"# archived spring stock datums\r\nWIRE_DIA = 0.8\r\n"
            original.write_bytes(raw)
            selected = identity.source_file(cad, "scripts/ch_vn_channel_spring_stock_geom.py")
            self.assertEqual(selected, original)
            self.assertEqual(selected.read_bytes(), raw)
            (cad / "scripts/ch_vn_channel_spring_stock_geom.py").write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                identity.source_file(cad, "scripts/ch_vn_channel_spring_stock_geom.py")

    def test_current_counter_stock_helper_resolves_exact_sealed_source(self):
        identity = CadIdentityMap(ROOT)
        sealed = "cad/scripts/vn_counter_spring_stock_geom.py"
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            original = cad.parent / identity.original_paths[sealed]
            original.parent.mkdir(parents=True)
            raw = b"# archived counter stock datums\r\nWIRE_DIA = 0.7\r\n"
            original.write_bytes(raw)
            selected = identity.source_file(cad, "scripts/sm_vn_counter_spring_stock_geom.py")
            self.assertEqual(selected, original)
            self.assertEqual(selected.read_bytes(), raw)
            (cad / "scripts/sm_vn_counter_spring_stock_geom.py").write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                identity.source_file(cad, "scripts/sm_vn_counter_spring_stock_geom.py")

    def test_wrong_current_map_content_is_refused(self):
        mapping = json.loads(TABLE_PATH.read_text())
        mapping["machineVendors"][0]["identities"][0]["stem"] += "-changed"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "SHA256"):
                CurrentNativeIdentity(path)

    def load_mapping(self, mapping):
        raw = json.dumps(mapping, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(raw, encoding="utf-8")
            with patch("current_native_identity.CURRENT_NATIVE_IDENTITY_MAP_SHA256", digest):
                return CurrentNativeIdentity(path)

    def test_duplicate_mapping_target_is_refused_even_for_same_source(self):
        for same_source in (True, False):
            mapping = json.loads(TABLE_PATH.read_text())
            row = mapping["machineVendors"][0]
            duplicate = json.loads(json.dumps(row))
            if not same_source:
                duplicate["sourceStem"] += "-other"
            mapping["machineVendors"].append(duplicate)
            with self.subTest(same_source=same_source), self.assertRaisesRegex(ValueError, "Colliding"):
                self.load_mapping(mapping)

    def test_conflicting_source_number_is_refused(self):
        mapping = json.loads(TABLE_PATH.read_text())
        duplicate = json.loads(json.dumps(mapping["machineVendors"][0]))
        duplicate["sourceNumber"] += "-other"
        mapping["machineVendors"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Conflicting historical number"):
            self.load_mapping(mapping)

    def test_source_rows_merge_only_with_matching_historical_number(self):
        mapping = json.loads(TABLE_PATH.read_text())
        row = mapping["machineVendors"][0]
        duplicate = json.loads(json.dumps(row))
        duplicate["identities"][0]["parent"] = "pd-paper-drive"
        duplicate["identities"][0]["stem"] = "pd-test-boss-hook"
        mapping["machineVendors"].append(duplicate)
        identity = self.load_mapping(mapping)
        for target in (row["identities"][0], duplicate["identities"][0]):
            path = PREFIX + target["parent"] + "/" + row["sourceStem"] + "-1"
            self.assertEqual(identity.project_path(path),
                             PREFIX + target["parent"] + "/" + target["stem"] + "-1")

    def test_target_stem_uniqueness_is_parent_scoped(self):
        mapping = json.loads(TABLE_PATH.read_text())
        mapping["machineVendors"] += [
            {"sourceStem": "vn-test-first", "sourceNumber": "TEST-01", "identities": [
                {"parent": "dt-drive-train", "stem": "test-shared"}]},
            {"sourceStem": "vn-test-second", "sourceNumber": "TEST-02", "identities": [
                {"parent": "pd-paper-drive", "stem": "test-shared"}]},
        ]
        identity = self.load_mapping(mapping)
        for parent, source in (("dt-drive-train", "vn-test-first"),
                               ("pd-paper-drive", "vn-test-second")):
            expected = PREFIX + parent + "/test-shared-1"
            self.assertEqual(identity.project_path(PREFIX + parent + "/" + source + "-1"), expected)
            self.assertEqual(identity.project_path(expected), expected)
        with self.assertRaisesRegex(ValueError, "Ambiguous composed"):
            identity.source_aliases(set())

    def test_multiple_targets_for_one_source_parent_are_ambiguous(self):
        mapping = json.loads(TABLE_PATH.read_text())
        row = mapping["machineVendors"][0]
        duplicate = json.loads(json.dumps(row["identities"][0]))
        duplicate["stem"] += "-other"
        row["identities"].append(duplicate)
        identity = self.load_mapping(mapping)
        path = PREFIX + duplicate["parent"] + "/" + row["sourceStem"] + "-1"
        with self.assertRaisesRegex(ValueError, "No unique immediate parent"):
            identity.project_path(path)

    def test_archive_only_identities_have_no_live_cad_metadata(self):
        mapping = json.loads(TABLE_PATH.read_text())
        self.assertEqual(len(mapping["archiveOnlyVendors"]), 3)
        identity = CurrentNativeIdentity()
        for row in mapping["archiveOnlyVendors"]:
            self.assertEqual(row["status"], "archive-only")
            for field in ("number", "registry", "builder"):
                self.assertIsNone(row[field])
            sealed = "cad/config/parts/" + row["sourceStem"] + ".yaml"
            logical = "cad/config/parts/" + row["stem"] + ".yaml"
            self.assertEqual(identity.source_aliases({sealed})[logical], sealed)

    def test_parent_scoped_paths_are_idempotent_and_keep_configuration(self):
        for parent in ("dt-drive-train", "fr-frame", "pd-paper-drive"):
            path = PREFIX + parent + "/vn-fillister-screw--T006-7"
            expected = PREFIX + parent + "/" + parent[:2] + "-vn-fillister-screw--T006-7"
            self.assertEqual(project_current_native_path(path), expected)
            self.assertEqual(project_current_native_path(expected), expected)
        self.assertEqual(project_current_native_path(PREFIX + "mg-magnifier/mg-lever-wire-1"),
                         PREFIX + "mg-magnifier/mg-vn-lever-wire-1")
        self.assertEqual(project_current_native_path(PREFIX + "pd-paper-drive/vn-latch-hook-rivet-1"),
                         PREFIX + "pd-paper-drive/pd-vn-latch-hook-rivet-1")

    def test_wrong_parent_unknown_vendor_and_traversal_refuse(self):
        for path in (PREFIX + "pn-pen/vn-fillister-screw-1",
                     PREFIX + "pd-paper-drive/vn-unknown-1",
                     PREFIX + "pd-paper-drive/../vn-fillister-screw-1"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                project_current_native_path(path)

    def test_inventory_index_preserves_numeric_measurements_and_hashes(self):
        old = PREFIX + "pd-paper-drive/vn-fillister-screw-1"
        current = PREFIX + "pd-paper-drive/pd-vn-fillister-screw-1"
        matrix = [float(value) for value in range(16)]
        row = {"path": old, "world": matrix}
        inventory = {"sha256": "a" * 64, "inventory": [row]}
        indexed = current_inventory_parts(inventory)
        self.assertIs(indexed[current], row)
        self.assertIs(indexed[current]["world"], matrix)
        self.assertEqual(row["path"], old)
        anchor = {"partPath": old, "sourcePath": old, "sha256": "a" * 64,
                  "partLocalMetres": [0.001, 0.002, 0.003]}
        projected = project_current_anchor(anchor)
        self.assertEqual(projected["partPath"], current)
        self.assertEqual(projected["sourcePath"], old)
        self.assertIs(projected["partLocalMetres"], anchor["partLocalMetres"])
        self.assertEqual(anchor["partPath"], old)
        with self.assertRaisesRegex(ValueError, "Colliding"):
            current_inventory_parts({"inventory": [row, {"path": current, "world": matrix}]})

    def test_duplicate_inventory_entries_are_refused_even_when_equal(self):
        old = PREFIX + "pd-paper-drive/vn-fillister-screw-1"
        current = PREFIX + "pd-paper-drive/pd-vn-fillister-screw-1"
        row = {"path": old, "world": list(range(16))}
        for duplicate in (row, dict(row), {**row, "path": current}):
            with self.subTest(path=duplicate["path"]), self.assertRaisesRegex(ValueError, "Colliding"):
                current_inventory_parts({"inventory": [row, duplicate]})
        indexed = current_inventory_parts({"inventory": [row]})
        self.assertIs(indexed[old], row)
        self.assertIs(indexed[current], row)

    def test_current_logical_sources_compose_to_one_exact_archive_file(self):
        identity = CadIdentityMap(ROOT)
        for template in ("scripts/build_{}.py", "config/parts/{}.yaml"):
            sealed_stem = "vn_fillister_screw" if template.endswith(".py") else "vn-fillister-screw"
            sealed = "cad/" + template.format(sealed_stem)
            original = identity.original_paths[sealed]
            with tempfile.TemporaryDirectory() as directory:
                cad = Path(directory) / "cad"
                cad.mkdir()
                with self.assertRaisesRegex(ValueError, "Missing archived CAD source"):
                    identity.source_file(cad, template.format(
                        "pd_vn_fillister_screw" if template.endswith(".py") else "pd-vn-fillister-screw"))
                archived = cad.parent / original
                archived.parent.mkdir(parents=True, exist_ok=True)
                raw = b"# exact archived source\r\nvalue = 1.250\r\n"
                archived.write_bytes(raw)
                digest = hashlib.sha256(raw).hexdigest()
                for parent in ("dt", "fr", "pd"):
                    stem = parent + ("_vn_fillister_screw" if template.endswith(".py") else "-vn-fillister-screw")
                    selected = identity.source_file(cad, template.format(stem))
                    self.assertEqual(selected, archived)
                    self.assertEqual(hashlib.sha256(selected.read_bytes()).hexdigest(), digest)
                logical = template.format("pd_vn_fillister_screw" if template.endswith(".py") else "pd-vn-fillister-screw")
                duplicate = cad / logical
                duplicate.parent.mkdir(parents=True, exist_ok=True)
                duplicate.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "Ambiguous"):
                    identity.source_file(cad, logical)

    def test_source_traversal_is_refused(self):
        identity = CadIdentityMap(ROOT)
        for logical in ("../escape.py", "scripts/../../escape.py", "C:/escape.py",
                        "scripts\\escape.py", "/escape.py", ""):
            with self.subTest(logical=logical), self.assertRaisesRegex(ValueError, "Unsafe"):
                identity.source_file(ROOT / "web/content/v39-source/cad", logical)

    def test_source_fit_accepts_mixed_current_archive_names_without_refitting(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fit_source_current_identity_test", Path(__file__).with_name("fit-source.py"))
        fit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fit)
        old = PREFIX + "pd-paper-drive/vn-fillister-screw-1"
        current = project_current_native_path(old)
        matrix = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 2., 3., 4., 1.]
        for anchor_path, inventory_path in ((old, current), (current, old)):
            observations = {"model": {"sha256": "a" * 64}, "anchors": [{
                "id": "screw", "partPath": anchor_path,
                "correspondenceEvidence": {"kind": "fixture"},
                "partLocalMetres": [0.1, 0.2, 0.3],
            }]}
            inventory = {"sha256": "a" * 64, "inventory": [{"path": inventory_path, "world": matrix}]}
            point = fit.world_points(observations, inventory)["screw"]
            self.assertEqual(point.tolist(), [2.1, 3.2, 4.3])
            self.assertEqual(observations["anchors"][0]["partPath"], anchor_path)
            self.assertEqual(inventory["inventory"][0]["path"], inventory_path)
            inventory["sha256"] = "b" * 64
            with self.assertRaisesRegex(ValueError, "Model hash differs"):
                fit.world_points(observations, inventory)


if __name__ == "__main__":
    unittest.main()
