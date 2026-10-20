"""Refusal boundaries for exact-source CAD/native identity projection."""
import copy
import sys
import types
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from current_native_identity import CurrentNativeIdentity

from native_identity_source import (
    CadIdentityMap,
    RELEASE_MODELS,
    magnifier_installation,
    validate_path_projection,
    validate_release_pair,
    wheel_wire_pitch_radii,
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

    def test_shared_source_aliases_are_candidate_tuples_not_a_global_ambiguity_error(self):
        projection = CurrentNativeIdentity()
        sealed = set(self.identity_map.original_paths)
        aliases = projection.source_aliases(sealed)
        logical = "cad/scripts/sh_vn_music_wire_geom.py"
        self.assertEqual(aliases[logical], (
            "cad/scripts/mg_lever_wire_geom.py", "cad/scripts/pn_pen_wire_geom.py"))
        self.assertEqual(aliases["cad/scripts/build_sh_vn_music_wire.py"], (
            "cad/scripts/build_mg_lever_wire.py", "cad/scripts/build_pn_pen_wire.py"))
        self.assertEqual(aliases["cad/config/parts/sh-vn-music-wire.yaml"], (
            "cad/config/parts/mg-lever-wire.yaml", "cad/config/parts/pn-pen-wire.yaml"))
        self.assertEqual(projection.source_aliases(sealed, parent="mg-magnifier")[logical],
                         ("cad/scripts/mg_lever_wire_geom.py",))
        self.assertEqual(projection.source_aliases(
            sealed, configuration="PenWire", role="PenWire")[logical],
            ("cad/scripts/pn_pen_wire_geom.py",))
        self.assertEqual(projection.source_aliases(
            sealed, configuration="LeverWire", role="PenWire")[logical], ())
        self.assertEqual(projection.source_aliases(
            sealed, parent="mg-magnifier", configuration="PenWire", role="PenWire")[logical], ())

    def test_shared_wire_selectors_resolve_exact_original_bytes_without_using_file_presence_as_identity(self):
        logical = "scripts/sh_vn_music_wire_geom.py"
        sources = {
            "cad/scripts/mg_lever_wire_geom.py": b'MARKER = "lever"\r\nVALUE = 1.250\r\n',
            "cad/scripts/pn_pen_wire_geom.py": b'MARKER = "pen"\r\nVALUE = 2.500\r\n',
        }
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            originals = {}
            for sealed, raw in sources.items():
                original = cad.parent / self.identity_map.original_paths[sealed]
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(raw)
                originals[sealed] = original
            for sealed, selectors in (
                ("cad/scripts/mg_lever_wire_geom.py", {"parent": "mg-magnifier"}),
                ("cad/scripts/mg_lever_wire_geom.py", {"role": "LeverWire"}),
                ("cad/scripts/mg_lever_wire_geom.py", {"configuration": "LeverWire", "role": "LeverWire"}),
                ("cad/scripts/pn_pen_wire_geom.py", {"parent": "pn-pen", "configuration": "PenWire", "role": "PenWire"}),
            ):
                with self.subTest(selectors=selectors):
                    selected = self.identity_map.source_file(cad, logical, **selectors)
                    self.assertEqual(selected, originals[sealed])
                    self.assertEqual(selected.read_bytes(), sources[sealed])
            # An unrelated exact source remains usable although the shared lookup is ambiguous.
            unrelated = self.identity_map.source_file(cad, "scripts/mg_lever_wire_geom.py")
            self.assertEqual(unrelated.read_bytes(), sources["cad/scripts/mg_lever_wire_geom.py"])
            with self.assertRaisesRegex(ValueError, "Ambiguous archived CAD source identity"):
                self.identity_map.source_file(cad, logical)
            originals["cad/scripts/pn_pen_wire_geom.py"].unlink()
            with self.assertRaisesRegex(ValueError, "Ambiguous archived CAD source identity"):
                self.identity_map.source_file(cad, logical)
            self.assertEqual(self.identity_map.source_file(cad, logical, parent="mg-magnifier").read_bytes(),
                             sources["cad/scripts/mg_lever_wire_geom.py"])
            with self.assertRaisesRegex(ValueError, "Missing archived CAD source"):
                self.identity_map.source_file(cad, logical, parent="pn-pen")
            (cad / logical).write_bytes(b'WRONG = "canonical fallback must never select a member"\r\n')
            for selectors in (
                {"configuration": "LeverWire", "role": "PenWire"},
                {"parent": "mg-magnifier", "configuration": "PenWire", "role": "PenWire"},
            ):
                with self.subTest(selectors=selectors), self.assertRaisesRegex(
                        ValueError, "Missing archived CAD source identity"):
                    self.identity_map.source_file(cad, logical, **selectors)

    def test_shared_import_and_registry_selectors_keep_the_exact_archived_member(self):
        members = (
            ("mg-magnifier", "LeverWire", "mg_lever_wire_geom", "mg-lever-wire", "lever"),
            ("pn-pen", "PenWire", "pn_pen_wire_geom", "pn-pen-wire", "pen"),
        )
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            originals = {}
            for parent, configuration, module, registry, marker in members:
                for sealed, raw in (
                    (f"cad/scripts/{module}.py", f'MARKER = "{marker}"\r\n'.encode()),
                    (f"cad/config/parts/{registry}.yaml", f"member: {marker}\r\n".encode()),
                ):
                    original = cad.parent / self.identity_map.original_paths[sealed]
                    original.parent.mkdir(parents=True, exist_ok=True)
                    original.write_bytes(raw)
                    originals[sealed] = (original, raw)
            with patch.object(sys, "path", [str(cad / "scripts"), *sys.path]), patch.dict(sys.modules):
                for parent, configuration, module, registry, marker in members:
                    original, raw = originals[f"cad/scripts/{module}.py"]
                    sys.modules.pop(original.stem, None)
                    selectors = {"parent": parent, "configuration": configuration, "role": configuration}
                    imported = self.identity_map.import_module(cad, "sh_vn_music_wire_geom", **selectors)
                    self.assertEqual(imported.MARKER, marker)
                    self.assertEqual(Path(imported.__file__).resolve(), original.resolve())
                    self.assertEqual(original.read_bytes(), raw)
                    original_registry, registry_raw = originals[f"cad/config/parts/{registry}.yaml"]
                    self.assertEqual(self.identity_map.registry_name(cad, "sh-vn-music-wire", **selectors),
                                     original_registry.stem)
                    self.assertEqual(original_registry.read_bytes(), registry_raw)
                for operation, name in ((self.identity_map.import_module, "sh_vn_music_wire_geom"),
                                        (self.identity_map.registry_name, "sh-vn-music-wire")):
                    with self.assertRaisesRegex(ValueError, "Ambiguous archived CAD source identity"):
                        operation(cad, name)
                    with self.assertRaisesRegex(ValueError, "Missing archived CAD source identity"):
                        operation(cad, name, configuration="LeverWire", role="PenWire")

    def test_explicit_shared_pure_member_sources_preserve_historic_names_and_bytes(self):
        members = (
            ("sh_vn_music_wire_lever_geom", "mg_lever_wire_geom", "LeverWire", "mg-magnifier"),
            ("sh_vn_music_wire_lever_spec", "mg_lever_wire_spec", "LeverWire", "mg-magnifier"),
            ("sh_vn_music_wire_pen_geom", "pn_pen_wire_geom", "PenWire", "pn-pen"),
            ("sh_vn_music_wire_pen_spec", "pn_pen_wire_spec", "PenWire", "pn-pen"),
            ("sh_vn_clamping_kit_hold_down_stud_spec", "ch_rocker_arm_tl_oblique_hold_down_stud_spec",
             "HoldDownStud", "ch-rocker-arm-tl-oblique-jig"),
            ("sh_vn_clamping_kit_t_nut_spec", "ch_rocker_arm_tl_oblique_t_nut_spec",
             "TNut", "ch-rocker-arm-tl-oblique-jig"),
            ("sh_vn_clamping_kit_flange_nut_spec", "ch_rocker_arm_tl_oblique_flange_nut_spec",
             "FlangeNut", "ch-rocker-arm-tl-oblique-jig"),
        )
        projection = CurrentNativeIdentity()
        sealed_paths = set(self.identity_map.original_paths)
        aliases = projection.source_aliases(sealed_paths)
        with tempfile.TemporaryDirectory() as directory:
            cad = Path(directory) / "cad"
            for logical, source, configuration, parent in members:
                sealed = f"cad/scripts/{source}.py"
                with self.subTest(member=logical):
                    self.assertEqual(aliases[f"cad/scripts/{logical}.py"], (sealed,))
                    original = cad.parent / self.identity_map.original_paths.get(sealed, sealed)
                    original.parent.mkdir(parents=True, exist_ok=True)
                    raw = f'# exact historic member {source}\r\nVALUE = 1.250\r\n'.encode()
                    original.write_bytes(raw)
                    selectors = {"parent": parent, "configuration": configuration, "role": configuration}
                    selected = self.identity_map.source_file(cad, f"scripts/{logical}.py", **selectors)
                    self.assertEqual(selected, original)
                    self.assertEqual(selected.read_bytes(), raw)
                    self.assertEqual(self.identity_map.source_file(cad, f"scripts/{logical}.py"), original)
                    self.assertEqual(projection.source_aliases(sealed_paths, **selectors)[
                        f"cad/scripts/{logical}.py"], (sealed,))
                    wrong = {**selectors, "role": "WrongMember"}
                    self.assertEqual(projection.source_aliases(sealed_paths, **wrong)[
                        f"cad/scripts/{logical}.py"], ())
                    with self.assertRaisesRegex(ValueError, "Missing archived CAD source identity"):
                        self.identity_map.source_file(cad, f"scripts/{logical}.py", **wrong)
                    wrong_parent = {**selectors, "parent": "fr-frame"}
                    self.assertEqual(projection.source_aliases(sealed_paths, **wrong_parent)[
                        f"cad/scripts/{logical}.py"], ())
                    with self.assertRaisesRegex(ValueError, "Missing archived CAD source identity"):
                        self.identity_map.source_file(cad, f"scripts/{logical}.py", **wrong_parent)

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


class MagnifierInstallationTests(unittest.TestCase):
    # Released assembly datums, including its dependency-derived installed top.
    SOURCE = (
        "LEVER_ROD_Y = 979.7\n"
        "LEVER_ROD_Z = -128.3\n"
        "VROD_TOP_Y = LEVER_ROD_Y + 5.0\n"
        "FIXTURE_Y0 = 915.7\n"
    )
    EXPECTED = {
        "LEVER_ROD_Y": 979.7,
        "LEVER_ROD_Z": -128.3,
        "VROD_TOP_Y": 984.7,
        "FIXTURE_Y0": 915.7,
    }

    def parse_source(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build_magnifier_assembly.py"
            path.write_text(source)
            return magnifier_installation(path)

    def test_released_literal_and_dependency_datums_are_exact(self):
        self.assertEqual(self.parse_source(self.SOURCE), self.EXPECTED)

    def test_new_fixture_contract_is_refused_by_missing_datum_name(self):
        source = self.SOURCE.replace(
            "FIXTURE_Y0 = 915.7\n",
            "from mg_output_fixture_geom import FIXTURE_AXIS_Y\n",
        )
        with self.assertRaisesRegex(ValueError, "datum 'FIXTURE_Y0'"):
            self.parse_source(source)

    def test_module_rebinding_cannot_return_stale_installed_points(self):
        for rebinding in (
            "VROD_TOP_Y += 10.0\n",
            "VROD_TOP_Y, spare = (994.7, 0)\n",
            "VROD_TOP_Y: float = 994.7\n",
            "VROD_TOP_Y = 994.7\n",
            "if True:\n    VROD_TOP_Y = 994.7\n",
            "del VROD_TOP_Y\n",
            "for VROD_TOP_Y in (994.7,):\n    pass\n",
            "def install():\n    global VROD_TOP_Y\n    VROD_TOP_Y += 10.0\n",
            "class Installation:\n    global VROD_TOP_Y\n    VROD_TOP_Y += 10.0\n",
        ):
            with self.subTest(rebinding=rebinding):
                with self.assertRaisesRegex(ValueError, "magnifier installation datum"):
                    self.parse_source(self.SOURCE + rebinding)

    def test_rebound_dependency_cannot_return_stale_installed_top(self):
        source = self.SOURCE.replace(
            "VROD_TOP_Y = LEVER_ROD_Y + 5.0",
            "OFFSET = 5.0\nVROD_TOP_Y = LEVER_ROD_Y + OFFSET",
        )
        for rebinding in (
            "OFFSET += 10.0\n",
            "OFFSET, spare = (15.0, 0)\n",
            "OFFSET: float = 15.0\n",
            "OFFSET = 15.0\n",
        ):
            with self.subTest(rebinding=rebinding):
                with self.assertRaisesRegex(ValueError, "magnifier installation datum"):
                    self.parse_source(source + rebinding)

    def test_unrelated_and_local_bindings_do_not_rebind_module_datums(self):
        source = self.SOURCE + (
            "unused = 1\nunused += 2\n"
            "def local():\n"
            "    VROD_TOP_Y = 0\n"
            "    VROD_TOP_Y += 1\n"
            "    LEVER_ROD_Y, spare = (0, 1)\n"
            "    FIXTURE_Y0: float = 0\n"
            "samples = [VROD_TOP_Y for VROD_TOP_Y in (0, 1)]\n"
        )
        self.assertEqual(self.parse_source(source), self.EXPECTED)

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


class WheelWirePitchRadiiTests(unittest.TestCase):
    @staticmethod
    def module(**values):
        module = types.ModuleType("pen_wire_fixture")
        module.__dict__.update(values)
        return module

    def test_plain_rim_and_grooved_rim_releases(self):
        lever = types.SimpleNamespace(YOKE_PITCH_R=10.4)
        self.assertEqual(
            wheel_wire_pitch_radii(lever, self.module(RIM_DIA=100.0, WIRE_DIA=0.8)), (10.4, 50.4)
        )
        lever = types.SimpleNamespace(YOKE_PITCH_R=9.85)
        self.assertEqual(
            wheel_wire_pitch_radii(lever, self.module(RIM_WIRE_R=49.2, WIRE_DIA=0.4)), (9.85, 49.2)
        )

    def test_ambiguous_or_missing_rim_schema_is_refused(self):
        lever = types.SimpleNamespace(YOKE_PITCH_R=9.85)
        for pen in (
            self.module(WIRE_DIA=0.4),
            self.module(RIM_WIRE_R=49.2, RIM_DIA=100.0, WIRE_DIA=0.4),
        ):
            with self.subTest(pen=sorted(vars(pen))), self.assertRaisesRegex(ValueError, "exactly one"):
                wheel_wire_pitch_radii(lever, pen)


if __name__ == "__main__":
    unittest.main()
