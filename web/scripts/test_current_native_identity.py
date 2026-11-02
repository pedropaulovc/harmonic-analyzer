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
    project_current_native_path, require_current_native_occurrence_namespace,
)
from native_identity_source import CadIdentityMap, MAP_SHA256

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "ha-harmonic-analyzer/"

# Explicit expected behaviors remain independent of the implementation's table.
SHARED_CASES = [
    ("pd-paper-drive", "vn-chain-inner-link", "MHA-VN-002", "pd-vn-chain-inner-link", "MHA-PD-VN-50",
     "sh-vn-chain-link--InnerLink", "MHA-SH-VN-50"),
    ("pd-paper-drive", "vn-chain-outer-link", "MHA-VN-003", "pd-vn-chain-outer-link", "MHA-PD-VN-51",
     "sh-vn-chain-link--OuterLink", "MHA-SH-VN-50"),
    ("dt-drive-train", "vn-fillister-screw", "MHA-VN-006", "dt-vn-fillister-screw", "MHA-DT-VN-50",
     "sh-vn-brass-fillister-screw", "MHA-SH-VN-51"),
    ("fr-frame", "vn-fillister-screw", "MHA-VN-006", "fr-vn-fillister-screw", "MHA-FR-VN-50",
     "sh-vn-brass-fillister-screw", "MHA-SH-VN-51"),
    ("pd-paper-drive", "vn-fillister-screw", "MHA-VN-006", "pd-vn-fillister-screw", "MHA-PD-VN-52",
     "sh-vn-brass-fillister-screw", "MHA-SH-VN-51"),
    ("dt-drive-train", "vn-foot-screw", "MHA-VN-020", "dt-vn-foot-screw", "MHA-DT-VN-58",
     "sh-vn-fillister-screw-90280a108__FootScrew", "MHA-SH-VN-52"),
    ("dt-drive-train", "vn-swing-stop-screw", "MHA-VN-015", "dt-vn-swing-stop-screw", "MHA-DT-VN-53",
     "sh-vn-fillister-screw-90280a108__SwingStopScrew", "MHA-SH-VN-52"),
    ("pd-paper-drive", "vn-latch-hook-bracket-screw", "MHA-VN-043", "pd-vn-latch-hook-bracket-screw", "MHA-PD-VN-59",
     "sh-vn-fillister-screw-90280a108", "MHA-SH-VN-52"),
    ("mg-magnifier", "vn-clamp-screw", "MHA-VN-021", "mg-vn-clamp-screw", "MHA-MG-VN-51",
     "sh-vn-clamp-screw", "MHA-SH-VN-53"),
    ("pd-paper-drive", "vn-clamp-screw", "MHA-VN-021", "pd-vn-clamp-screw", "MHA-PD-VN-53",
     "sh-vn-clamp-screw", "MHA-SH-VN-53"),
    ("ch-channel", "vn-arbor-set-screw", "MHA-VN-034", "ch-vn-arbor-set-screw", "MHA-CH-VN-53",
     "sh-vn-arbor-set-screw", "MHA-SH-VN-54"),
    ("dt-drive-train", "vn-arbor-set-screw", "MHA-VN-034", "dt-vn-arbor-set-screw", "MHA-DT-VN-64",
     "sh-vn-arbor-set-screw", "MHA-SH-VN-54"),
    ("mg-magnifier", "vn-thumb-screw", "MHA-VN-011", "mg-vn-thumb-screw", "MHA-MG-VN-50",
     "sh-vn-thumb-screw", "MHA-SH-VN-55"),
    ("ms-measuring-stick", "vn-thumb-screw", "MHA-VN-011", "ms-vn-thumb-screw", "MHA-MS-VN-50",
     "sh-vn-thumb-screw", "MHA-SH-VN-55"),
    ("mg-magnifier", "mg-lever-wire", "MHA-MG-009", "mg-vn-lever-wire", "MHA-MG-VN-56",
     "sh-vn-music-wire--LeverWire", "MHA-SH-VN-56"),
    ("pn-pen", "pn-pen-wire", "MHA-PN-006", "pn-vn-pen-wire", "MHA-PN-VN-57",
     "sh-vn-music-wire--PenWire", "MHA-SH-VN-56"),
    ("ch-rocker-arm-tl-oblique-jig", "ch-rocker-arm-tl-oblique-hold-down-stud", "MHA-CH-006-TL-38",
     "ch-rocker-arm-tl-vn-oblique-hold-down-stud", "MHA-CH-06-TL-VN-58",
     "sh-vn-clamping-kit-hardware--HoldDownStud", "MHA-SH-VN-57"),
    ("ch-rocker-arm-tl-oblique-jig", "ch-rocker-arm-tl-oblique-t-nut", "MHA-CH-006-TL-39",
     "ch-rocker-arm-tl-vn-oblique-t-nut", "MHA-CH-06-TL-VN-59",
     "sh-vn-clamping-kit-hardware--TNut", "MHA-SH-VN-57"),
    ("ch-rocker-arm-tl-oblique-jig", "ch-rocker-arm-tl-oblique-flange-nut", "MHA-CH-006-TL-40",
     "ch-rocker-arm-tl-vn-oblique-flange-nut", "MHA-CH-06-TL-VN-60",
     "sh-vn-clamping-kit-hardware--FlangeNut", "MHA-SH-VN-57"),
]


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
current = "ha-harmonic-analyzer/pd-paper-drive/sh-vn-brass-fillister-screw-1"
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
            "occurrenceNamespace": "archive-role-local",
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

    def test_duplicate_same_source_context_is_refused(self):
        for source in ("vn-boss-hook", "vn-chain-inner-link"):
            mapping = json.loads(TABLE_PATH.read_text())
            row = next(row for row in mapping["machineVendors"] if row["sourceStem"] == source)
            mapping["machineVendors"].append(json.loads(json.dumps(row)))
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "Colliding|Duplicate"):
                self.load_mapping(mapping)

    def test_many_sources_share_declared_target_but_not_conflicting_number_or_configuration(self):
        mapping = json.loads(TABLE_PATH.read_text())
        row = next(row for row in mapping["machineVendors"]
                   if row["sourceStem"] == "vn-chain-inner-link")
        duplicate = json.loads(json.dumps(row))
        duplicate["sourceStem"] = "vn-test-shared-inner-link"
        duplicate["identities"][0]["priorStem"] = "pd-vn-test-shared-inner-link"
        mapping["machineVendors"].append(duplicate)
        identity = self.load_mapping(mapping)
        self.assertEqual(identity.project_path(PREFIX + "pd-paper-drive/vn-test-shared-inner-link-1"),
                         PREFIX + "pd-paper-drive/sh-vn-chain-link--InnerLink-1")
        for field, value in (("number", "MHA-SH-VN-99"), ("configuration", "UnknownMember"),
                             ("role", "OuterLink")):
            changed = json.loads(json.dumps(mapping))
            changed["machineVendors"][-1]["identities"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load_mapping(changed)

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
        aliases = identity.source_aliases({
            "cad/scripts/build_vn_test_first.py", "cad/scripts/build_vn_test_second.py"})
        self.assertEqual(set(aliases["cad/scripts/build_test_shared.py"]), {
            "cad/scripts/build_vn_test_first.py", "cad/scripts/build_vn_test_second.py"})
        self.assertIsInstance(aliases["cad/scripts/build_test_shared.py"], tuple)
        self.assertEqual(identity.source_aliases({"cad/scripts/build_vn_test_first.py",
                                                "cad/scripts/build_vn_test_second.py"},
                                               parent="dt-drive-train")["cad/scripts/build_test_shared.py"],
                         ("cad/scripts/build_vn_test_first.py",))

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
            self.assertEqual(identity.source_aliases({sealed})[logical], (sealed,))

    def test_retired_tooling_is_reserved_history_not_a_current_projection_or_registry(self):
        cad_map = json.loads((ROOT / "cad/config/current-identity-map.json").read_text(encoding="utf-8"))
        identity = CurrentNativeIdentity()
        retired = cad_map["retired_identities"]
        self.assertEqual(len(retired), 31)
        oblique_reservations = {
            "ch-rocker-arm-tl-oblique-pivot-pin": "MHA-CH-06-TL-23",
            "ch-rocker-arm-tl-oblique-hub-pin": "MHA-CH-06-TL-25",
            "ch-rocker-arm-tl-oblique-nut-bracket": "MHA-CH-06-TL-29",
            "ch-rocker-arm-tl-oblique-pivot-cap": "MHA-CH-06-TL-30",
            "ch-rocker-arm-tl-oblique-pivot-retainer": "MHA-CH-06-TL-31",
            "ch-rocker-arm-tl-vn-oblique-bearing": "MHA-CH-06-TL-VN-52",
            "ch-rocker-arm-tl-vn-oblique-block-screw": "MHA-CH-06-TL-VN-63",
            "ch-rocker-arm-tl-vn-oblique-block-washer": "MHA-CH-06-TL-VN-70",
            "ch-rocker-arm-tl-vn-oblique-pivot-cap-screw": "MHA-CH-06-TL-VN-73",
            "ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin": "MHA-CH-06-TL-VN-74",
            "ch-rocker-arm-tl-vn-oblique-pivot-cotter": "MHA-CH-06-TL-VN-75",
            "ch-rocker-arm-tl-vn-oblique-pivot-lock-wire": "MHA-CH-06-TL-VN-76",
        }
        actual_oblique = {
            target["stem"]: target["number"]
            for row in retired for target in row["new_identities"]
            if "-tl-oblique-" in target["stem"] or "-tl-vn-oblique-" in target["stem"]
        }
        self.assertEqual(actual_oblique, oblique_reservations)
        active_numbers = {target["number"] for row in cad_map["parts_and_assemblies"]
                          for target in row["new_identities"]}
        for row in retired:
            self.assertEqual(row["status"], "retired")
            self.assertNotIn(row["old_stem"], identity.sources)
            self.assertNotIn(row["old_stem"], identity.stems)
            for target in row["new_identities"]:
                stem = target["stem"]
                with self.subTest(stem=stem):
                    self.assertNotIn(stem, identity.stems)
                    self.assertNotIn(stem, {current for _, current in identity.targets})
                    self.assertNotIn(target["number"], active_numbers)
                    for reserved_stem in {row["old_stem"], stem}:
                        self.assertFalse((ROOT / "cad/config/parts" / (reserved_stem + ".yaml")).exists())
                    sealed = "cad/config/parts/" + row["old_stem"] + ".yaml"
                    self.assertNotIn("cad/config/parts/" + stem + ".yaml", identity.source_aliases({sealed}))
                    unknown = PREFIX + "ch-channel/" + stem + "-1"
                    self.assertEqual(identity.project_path(unknown), unknown)

    def test_all_shared_paths_and_numbers_are_exact_and_idempotent(self):
        identity = CurrentNativeIdentity()
        self.assertEqual(len(SHARED_CASES), 19)
        self.assertEqual(len({row[-1] for row in SHARED_CASES}), 8)
        for parent, source, source_number, prior, prior_number, occurrence, number in SHARED_CASES:
            with self.subTest(parent=parent, source=source):
                expected = PREFIX + parent + "/" + occurrence + "-1"
                for stem in (source, prior, occurrence):
                    self.assertEqual(identity.project_path(PREFIX + parent + "/" + stem + "-1"), expected)
                for value, stem in ((source_number, source), (prior_number, prior),
                                    (number, occurrence), (number, occurrence + "-1")):
                    self.assertEqual(identity.project_number(value, stem, parent), number)
        self.assertEqual(project_current_native_path(PREFIX + "mg-magnifier/mg-lever-wire--T006-1@upper"),
                         PREFIX + "mg-magnifier/sh-vn-music-wire--LeverWire--T006-1@upper")
        self.assertEqual(project_current_native_path(PREFIX + "pd-paper-drive/vn-latch-hook-rivet-1"),
                         PREFIX + "pd-paper-drive/pd-vn-latch-hook-rivet-1")

    def test_all_five_default_shared_groups_keep_native_variants_idempotently(self):
        default_numbers = {"MHA-SH-VN-51", "MHA-SH-VN-52", "MHA-SH-VN-53",
                           "MHA-SH-VN-54", "MHA-SH-VN-55"}
        defaults = [row for row in SHARED_CASES if row[-1] in default_numbers]
        self.assertEqual({row[-1] for row in defaults}, default_numbers)
        identity = CurrentNativeIdentity()
        for parent, source, _, prior, _, occurrence, _ in defaults:
            for variant in ("T006", "Installed"):
                expected = PREFIX + parent + "/" + occurrence + "--" + variant + "-7@upper"
                for stem in (source, prior):
                    with self.subTest(parent=parent, source=stem, variant=variant):
                        old = PREFIX + parent + "/" + stem + "--" + variant + "-7@upper"
                        current = identity.project_path(old)
                        self.assertEqual(current, expected)
                        self.assertEqual(identity.project_path(current), expected)
                        self.assertEqual(identity.project_path(expected), expected)

    def test_js_and_python_execute_the_same_explicit_shared_behaviors_in_subprocesses(self):
        payload = {"paths": [], "numbers": [], "failures": []}
        expected_paths, expected_numbers = [], []
        for parent, source, source_number, prior, prior_number, occurrence, number in SHARED_CASES:
            current = PREFIX + parent + "/" + occurrence + "-1"
            for stem in (source, prior, occurrence):
                payload["paths"].append(PREFIX + parent + "/" + stem + "-1")
                expected_paths.append(current)
            for value, stem in ((source_number, source), (prior_number, prior),
                                (number, occurrence), (number, occurrence + "-1")):
                payload["numbers"].append([value, stem, parent])
                expected_numbers.append(number)
        payload["paths"].append(PREFIX + "mg-magnifier/mg-lever-wire--T006-1@upper")
        expected_paths.append(PREFIX + "mg-magnifier/sh-vn-music-wire--LeverWire--T006-1@upper")
        payload["numbers"] += [
            ["MHA-DT-003-T006", "dt-cone-gear", None],
            ["MHA-VN-032", "vn-pedestal-hold-down-screw", "ch-channel"],
        ]
        expected_numbers += ["MHA-DT-03-T006", None]
        default_numbers = {"MHA-SH-VN-51", "MHA-SH-VN-52", "MHA-SH-VN-53",
                           "MHA-SH-VN-54", "MHA-SH-VN-55"}
        for parent, source, _, prior, _, occurrence, number in SHARED_CASES:
            if number not in default_numbers:
                continue
            for variant in ("T006", "Installed"):
                current = PREFIX + parent + "/" + occurrence + "--" + variant + "-7@upper"
                for stem in (source, prior, occurrence):
                    payload["paths"].append(PREFIX + parent + "/" + stem + "--" + variant + "-7@upper")
                    expected_paths.append(current)
        payload["failures"] = [
            ["path", [PREFIX + "pn-pen/vn-fillister-screw-1"]],
            ["path", [PREFIX + "pd-paper-drive/vn-unknown-1"]],
            ["path", [PREFIX + "pd-paper-drive/../vn-fillister-screw-1"]],
            ["number", ["MHA-SH-VN-99", "vn-chain-inner-link", "pd-paper-drive"]],
            ["number", ["MHA-DT-003-T06", "dt-cone-gear", None]],
            ["number", ["MHA-VN-006", "vn-fillister-screw", None]],
            ["number", ["MHA-SH-VN-52", "sh-vn-fillister-screw-90280a108", "dt-drive-train"]],
            ["number", ["MHA-SH-VN-50", "sh-vn-chain-link", "pd-paper-drive"]],
            ["number", ["MHA-SH-VN-50", "sh-vn-chain-link--UnknownMember", "pd-paper-drive"]],
            ["number", ["MHA-SH-VN-52", "sh-vn-fillister-screw-90280a108__WrongRole", "dt-drive-train"]],
            ["path", [PREFIX + "pd-paper-drive/sh-vn-chain-link--UnknownMember-1"]],
            ["path", [PREFIX + "dt-drive-train/sh-vn-fillister-screw-90280a108__WrongRole-1"]],
            ["path", [PREFIX + "pd-paper-drive/sh-vn-chain-link--innerlink-1"]],
            ["number", ["MHA-SH-VN-50", "sh-vn-chain-link--innerlink", "pd-paper-drive"]],
            ["guard", ["rebuilt-native"]],
            ["guard", [""]],
            ["guard", [None]],
            ["path", [PREFIX + "dt-drive-train/vn-foot-screw-1", "rebuilt-native"]],
            ["path", ["Camera", "rebuilt-native"]],
        ]
        python_code = """
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from current_native_identity import CurrentNativeIdentity, require_current_native_occurrence_namespace
identity = CurrentNativeIdentity()
payload = json.load(sys.stdin)
def path(value, namespace="archive-role-local"):
    return identity.project_path(value, occurrence_namespace=namespace)
def refuses(kind, args):
    try:
        {"path": path, "number": identity.project_number,
         "guard": require_current_native_occurrence_namespace}[kind](*args)
    except ValueError:
        return True
    return False
print(json.dumps({
    "paths": [path(value) for value in payload["paths"]],
    "numbers": [identity.project_number(*args) for args in payload["numbers"]],
    "failures": [refuses(kind, args) for kind, args in payload["failures"]],
}))
"""
        javascript_code = """
import { readFileSync } from 'node:fs'
const projection = await import(process.argv[1])
const payload = JSON.parse(readFileSync(0, 'utf8'))
const calls = {
  path: projection.projectCurrentNativePath,
  number: projection.projectCurrentNativeNumber,
  guard: projection.requireCurrentNativeOccurrenceNamespace,
}
const refuses = ([kind, args]) => {
  try { calls[kind](...args) } catch { return true }
  return false
}
console.log(JSON.stringify({
  paths: payload.paths.map(value => calls.path(value)),
  numbers: payload.numbers.map(args => calls.number(...args)),
  failures: payload.failures.map(refuses),
}))
"""
        scripts = Path(__file__).resolve().parent
        expected = {"paths": expected_paths, "numbers": expected_numbers,
                    "failures": [True] * len(payload["failures"])}
        observed = []
        with tempfile.TemporaryDirectory() as directory:
            for language, command in (
                ("Python", [sys.executable, "-I", "-c", python_code, str(scripts)]),
                ("JavaScript", ["node", "--input-type=module", "-e", javascript_code,
                                (ROOT / "web/current-native-identity.mjs").as_uri()]),
            ):
                with self.subTest(language=language):
                    result = subprocess.run(command, input=json.dumps(payload), cwd=directory,
                                            capture_output=True, text=True, check=False, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    actual = json.loads(result.stdout)
                    self.assertEqual(actual, expected)
                    observed.append(actual)
        self.assertEqual(observed[0], observed[1])

    def test_logical_member_selectors_reject_lowercase_physical_filename_spelling(self):
        identity = CurrentNativeIdentity()
        exact = PREFIX + "pd-paper-drive/sh-vn-chain-link--InnerLink-1"
        self.assertEqual(identity.project_path(exact), exact)
        with self.assertRaisesRegex(ValueError, "No unique immediate parent"):
            identity.project_path(PREFIX + "pd-paper-drive/sh-vn-chain-link--innerlink-1")
        with self.assertRaisesRegex(ValueError, "No unique immediate parent"):
            identity.project_number("MHA-SH-VN-50", "sh-vn-chain-link--innerlink", "pd-paper-drive")

    def test_archive_namespace_guard_and_path_helper_reject_rebuilt_native(self):
        identity = CurrentNativeIdentity()
        require_current_native_occurrence_namespace("archive-role-local")
        old = PREFIX + "dt-drive-train/vn-foot-screw-1"
        self.assertEqual(identity.project_path(old, occurrence_namespace="archive-role-local"),
                         PREFIX + "dt-drive-train/sh-vn-fillister-screw-90280a108__FootScrew-1")
        for namespace in ("rebuilt-native", "", None):
            with self.subTest(namespace=namespace):
                with self.assertRaisesRegex(ValueError, "namespace"):
                    require_current_native_occurrence_namespace(namespace)
                for path in (old, "Camera"):
                    with self.assertRaisesRegex(ValueError, "namespace"):
                        identity.project_path(path, occurrence_namespace=namespace)
                    with self.assertRaisesRegex(ValueError, "namespace"):
                        project_current_native_path(path, occurrence_namespace=namespace)
        with self.assertRaisesRegex(ValueError, "namespace"):
            current_inventory_parts({"occurrenceNamespace": "rebuilt-native", "inventory": []})

    def test_anchor_declared_rebuilt_native_namespace_refuses_without_changing_source(self):
        point = [-0.0, 0.125, 1.0]
        anchor = {
            "occurrenceNamespace": "rebuilt-native",
            "partPath": PREFIX + "dt-drive-train/vn-foot-screw-1",
            "sourcePath": "harmonic-analyzer/drive-train/foot-screw-1",
            "partLocalMetres": point,
            "sha256": "a" * 64,
        }
        before = dict(anchor)
        with self.assertRaisesRegex(ValueError, "namespace"):
            project_current_anchor(anchor)
        self.assertEqual(anchor, before)
        self.assertIs(anchor["partLocalMetres"], point)

    def test_all_457_archive_occurrences_keep_exact_measurements_and_source_metadata(self):
        inventory = json.loads((ROOT / "web/content/v39-source/native-inventory.json").read_text())
        before = json.dumps(inventory, separators=(",", ":"))
        identity = CurrentNativeIdentity()
        projected = [identity.project_path(row["path"]) for row in inventory["inventory"]]
        self.assertEqual(len(projected), 457)
        self.assertEqual(len(set(projected)), 457)
        indexed = current_inventory_parts(inventory)
        for row, current in zip(inventory["inventory"], projected):
            self.assertEqual(current.rsplit("/", 1)[0], row["path"].rsplit("/", 1)[0])
            self.assertEqual(identity.project_path(current), current)
            self.assertIs(indexed[current], row)
            self.assertIs(indexed[current]["world"], row["world"])
            self.assertEqual(indexed[current]["sourcePath"], row["sourcePath"])
        for old, current in (
            ("dt-drive-train/vn-foot-screw-1", "dt-drive-train/sh-vn-fillister-screw-90280a108__FootScrew-1"),
            ("dt-drive-train/vn-swing-stop-screw-1", "dt-drive-train/sh-vn-fillister-screw-90280a108__SwingStopScrew-1"),
            ("pd-paper-drive/vn-chain-inner-link-1", "pd-paper-drive/sh-vn-chain-link--InnerLink-1"),
            ("pd-paper-drive/vn-chain-outer-link-1", "pd-paper-drive/sh-vn-chain-link--OuterLink-1"),
        ):
            self.assertIs(indexed[PREFIX + old], indexed[PREFIX + current])
        self.assertEqual(json.dumps(inventory, separators=(",", ":")), before)

    def test_wrong_parent_unknown_vendor_and_traversal_refuse(self):
        for path in (PREFIX + "pn-pen/vn-fillister-screw-1",
                     PREFIX + "pd-paper-drive/vn-unknown-1",
                     PREFIX + "pd-paper-drive/../vn-fillister-screw-1"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                project_current_native_path(path)

    def test_inventory_index_preserves_numeric_measurements_and_hashes(self):
        old = PREFIX + "pd-paper-drive/vn-fillister-screw-1"
        current = PREFIX + "pd-paper-drive/sh-vn-brass-fillister-screw-1"
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
        current = PREFIX + "pd-paper-drive/sh-vn-brass-fillister-screw-1"
        row = {"path": old, "world": list(range(16))}
        for duplicate in (row, dict(row), {**row, "path": current}):
            with self.subTest(path=duplicate["path"]), self.assertRaisesRegex(ValueError, "Colliding"):
                current_inventory_parts({"inventory": [row, duplicate]})
        indexed = current_inventory_parts({"inventory": [row]})
        self.assertIs(indexed[old], row)
        self.assertIs(indexed[current], row)

    def test_single_source_shared_logical_names_compose_to_exact_archive_bytes(self):
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
                        "sh_vn_brass_fillister_screw" if template.endswith(".py") else "sh-vn-brass-fillister-screw"))
                archived = cad.parent / original
                archived.parent.mkdir(parents=True, exist_ok=True)
                raw = b"# exact archived source\r\nvalue = 1.250\r\n"
                archived.write_bytes(raw)
                digest = hashlib.sha256(raw).hexdigest()
                logical = template.format("sh_vn_brass_fillister_screw" if template.endswith(".py") else "sh-vn-brass-fillister-screw")
                for parent in (None, "dt-drive-train", "fr-frame", "pd-paper-drive"):
                    selected = identity.source_file(cad, logical, parent=parent)
                    self.assertEqual(selected, archived)
                    self.assertEqual(hashlib.sha256(selected.read_bytes()).hexdigest(), digest)
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
