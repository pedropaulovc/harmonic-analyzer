"""Offline tests for face labelling, face inventories and offline feature binding.

Every SolidWorks object here is a synthetic double: these tests prove the
selection, labelling, inventory, binding and export-isolation rules, NOT that a
seat's STEP writer carries face names (that needs the farm proof described in
issue #1204).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

import export_features
import export_models
import features_bound
from _export_feature_faces import (
    FeatureFaceError,
    assign_feature_patches,
    bind_features,
    face_label,
    face_record,
    inventory_path,
    label_all_faces,
    step_feature_refs_valid,
    step_label_refs,
    write_inventory,
)
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _gtol_face import FaceGeometry

_CYLINDER = 4002  # swSurfaceTypes_e.CYLINDER_TYPE
_PLANE = 4001  # swSurfaceTypes_e.PLANE_TYPE
_MM = 0.001

# Synthetic part: a Ø6.5 bore on Z split into two half patches, its 3.5 mm top
# plane, and an unrelated Ø10 boss.  The upper half is walked first so the
# patch numbering must come from geometry, not traversal order.
_BORE = CylinderFace(diameter_mm=6.5, contains_z_mm=0.0)
_TOP = PlanarFace(normal=(0.0, 0.0, 1.0), offset_mm=3.5)
_SELECTORS = {"pivot_bore": (_BORE,), "hub_top": (_TOP,)}


def _cylinder_params(diameter_mm: float) -> tuple[float, ...]:
    return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter_mm / 2 * _MM)


def _box(*mm: float) -> tuple[float, ...]:
    return tuple(value * _MM for value in mm)


_UPPER_HALF = _box(-3.25, 0.0, -3.5, 3.25, 3.25, 3.5)
_LOWER_HALF = _box(-3.25, -3.25, -3.5, 3.25, 0.0, 3.5)
_BORE_BOX = _box(-3.25, -3.25, -3.5, 3.25, 3.25, 3.5)
_TOP_BOX = _box(-8.0, -8.0, 3.5, 8.0, 8.0, 3.5)
_BOSS_BOX = _box(-5.0, -5.0, -3.5, 5.0, 5.0, 3.5)


def _geometries() -> list[FaceGeometry]:
    return [
        FaceGeometry("upper", _CYLINDER, _cylinder_params(6.5), None, _UPPER_HALF),
        FaceGeometry("boss", _CYLINDER, _cylinder_params(10.0), None, _BOSS_BOX),
        FaceGeometry("lower", _CYLINDER, _cylinder_params(6.5), None, _LOWER_HALF),
        FaceGeometry(
            "top", _PLANE, (0.0, 0.0, 1.0, 0.0, 0.0, 3.5 * _MM), (0.0, 0.0, 1.0),
            _TOP_BOX,
        ),
    ]


def _step(*labels: str, ids: tuple[int, ...] | None = None) -> str:
    """A minimal ISO 10303-21 body whose ADVANCED_FACEs carry ``labels``
    (entity ids 10, 11, ... unless ``ids`` gives them)."""
    rows = ["ISO-10303-21;", "HEADER;", "FILE_NAME ( 'part.STEP' );", "ENDSEC;", "DATA;"]
    for number, label in zip(ids or range(10, 10 + len(labels)), labels):
        quoted = label.replace("'", "''")
        # Wrap one entity across lines, as long STEP records are.
        rows.append(f"#{number} = ADVANCED_FACE ( '{quoted}',\n  ( #1 ), #2, .T. ) ;")
    rows += ["ENDSEC;", "END-ISO-10303-21;"]
    return "\n".join(rows)


_F1, _F2, _F3, _F4 = (face_label(number) for number in range(1, 5))


# --- STEP read-back ----------------------------------------------------------


def test_step_label_refs_maps_every_label_to_its_step_faces_in_file_order() -> None:
    text = _step(_F2, "it's named", _F1, _F2)

    assert step_label_refs(text, [_F1, _F2, "it's named"]) == {
        _F1: ["#12/ADVANCED_FACE[3]/HAF_F0001"],
        _F2: ["#10/ADVANCED_FACE[1]/HAF_F0002", "#13/ADVANCED_FACE[4]/HAF_F0002"],
        "it's named": ["#11/ADVANCED_FACE[2]/it's named"],
    }


@pytest.mark.parametrize(
    ("labels", "inventory", "complaint"),
    [
        ((_F1, "NONE"), [_F1], "1 STEP face(s) labelled 'NONE', not an inventory label"),
        ((_F1,), [_F1, _F2], "inventory labels ['HAF_F0002'] label no STEP face"),
        ((_F1, _F2), [_F1, _F2, _F1], "inventory labels repeat: ['HAF_F0001']"),
    ],
    ids=["unlabelled-face", "dropped-label", "repeated-label"],
)
def test_step_label_refs_refuses_a_step_its_inventory_does_not_describe(
    labels: tuple[str, ...], inventory: list[str], complaint: str,
) -> None:
    with pytest.raises(FeatureFaceError, match=re.escape(complaint)):
        step_label_refs(_step(*labels), inventory)


def test_step_label_refs_rejects_a_duplicated_entity_id() -> None:
    text = _step(_F1, _F1, _F2, ids=(10, 10, 11))

    with pytest.raises(FeatureFaceError, match=re.escape("#10: STEP entity id defined 2 times")):
        step_label_refs(text, [_F1, _F2])


def test_step_label_refs_rejects_a_step_with_no_faces() -> None:
    with pytest.raises(FeatureFaceError, match="no ADVANCED_FACE"):
        step_label_refs(_step(), [])


@pytest.mark.parametrize("number", [0, -1, True, "1"])
def test_face_label_numbers_start_at_one(number) -> None:
    with pytest.raises(FeatureFaceError, match="must be >= 1"):
        face_label(number)


def test_recorded_face_sets_must_name_whole_labels_of_one_feature() -> None:
    text = _step(_F1, _F1, _F2)
    halves = ["#10/ADVANCED_FACE[1]/HAF_F0001", "#11/ADVANCED_FACE[2]/HAF_F0001"]
    top = ["#12/ADVANCED_FACE[3]/HAF_F0002"]

    assert step_feature_refs_valid(text, {"pivot_bore": halves, "hub_top": top}) == []
    assert step_feature_refs_valid(text, {"pivot_bore": halves[:1]}) == [
        "pivot_bore faces omit STEP faces labelled 'HAF_F0001': ['#11/ADVANCED_FACE[2]/HAF_F0001']",
    ]
    assert step_feature_refs_valid(text, {"pivot_bore": halves, "hub_top": halves})[0].startswith(
        "HAF_F0001: claimed by features ['hub_top', 'pivot_bore']"
    )
    assert "name no or repeated STEP faces ['#12/ADVANCED_FACE[3]/HAF_F0001']" in step_feature_refs_valid(
        text, {"hub_top": ["#12/ADVANCED_FACE[3]/HAF_F0001"]}
    )[0]


# --- selection ------------------------------------------------------------------


@pytest.mark.parametrize("feature", ["PivotBore", "pivot__bore", "pivot-bore", "_bore"])
def test_feature_keys_must_be_lower_case_words(feature: str) -> None:
    with pytest.raises(FeatureFaceError, match="feature key"):
        assign_feature_patches(_geometries(), {feature: (_BORE,)})


def test_split_bore_claims_every_patch_in_geometric_order() -> None:
    assigned = assign_feature_patches(_geometries(), _SELECTORS)

    # Index 2 (lower half) precedes index 0 (upper half): sorted by box, not walk.
    assert assigned == {"pivot_bore": [2, 0], "hub_top": [3]}


def test_selectors_of_one_feature_share_faces_without_double_counting() -> None:
    selectors = {
        "pivot_bore": (_BORE, CylinderFace(diameter_mm=6.5, contains_x_mm=0.0)),
        "hub_top": (_TOP,),
    }

    assert assign_feature_patches(_geometries(), selectors)["pivot_bore"] == [2, 0]


def test_selector_matching_no_face_fails() -> None:
    selectors = {**_SELECTORS, "tip_flat": (PlanarFace(normal=(1.0, 0.0, 0.0), offset_mm=40.0),)}

    with pytest.raises(FeatureFaceError, match="tip_flat: selector .* matched no face"):
        assign_feature_patches(_geometries(), selectors)


def test_face_claimed_by_two_features_fails() -> None:
    selectors = {**_SELECTORS, "bore_upper": (CylinderFace(diameter_mm=6.5, contains_y_mm=2.0),)}

    with pytest.raises(FeatureFaceError, match=r"face #0 is claimed by \['bore_upper', 'pivot_bore'\]"):
        assign_feature_patches(_geometries(), selectors)


# --- offline binding over a face inventory ------------------------------------


def _inventory_step(tmp_path: Path, labels: tuple[str, ...]) -> Path:
    """A STEP whose faces carry ``labels`` and the inventory of _geometries()
    labelled F0001..F0004 in walk order."""
    step = tmp_path / "part.STEP"
    step.write_text(_step(*labels), encoding="ascii")
    write_inventory(step, [face_record(face_label(n), g) for n, g in enumerate(_geometries(), start=1)])
    return step


def test_bind_features_maps_declared_selectors_through_the_inventory(tmp_path: Path) -> None:
    # Upper half F0001, boss F0002, lower half F0003, top F0004.
    step = _inventory_step(tmp_path, (_F4, _F1, _F2, _F3))

    assert bind_features(step, _SELECTORS) == {
        "pivot_bore": ["#13/ADVANCED_FACE[4]/HAF_F0003", "#11/ADVANCED_FACE[2]/HAF_F0001"],
        "hub_top": ["#10/ADVANCED_FACE[1]/HAF_F0004"],
    }
    assert bind_features(step, {}) == {}


def test_bind_features_refuses_an_inventory_of_other_step_bytes(tmp_path: Path) -> None:
    step = _inventory_step(tmp_path, (_F4, _F1, _F2, _F3))
    step.write_bytes(step.read_bytes() + b"\n")

    with pytest.raises(FeatureFaceError, match="its STEP is"):
        bind_features(step, _SELECTORS)


def test_write_inventory_refuses_a_step_without_its_labels(tmp_path: Path) -> None:
    step = tmp_path / "part.STEP"
    step.write_text(_step(_F1, "NONE"), encoding="ascii")

    with pytest.raises(FeatureFaceError, match="not an inventory label"):
        write_inventory(step, [face_record(_F1, _geometries()[0])])
    assert not inventory_path(step).exists()


# --- COM labelling (synthetic doubles) ---------------------------------------


class _Face:
    def __init__(self, surface: SimpleNamespace, box: tuple[float, ...]) -> None:
        self.surface = surface
        self.box = box
        self.next: _Face | None = None
        self.name = ""

    def GetSurface(self) -> SimpleNamespace:
        return self.surface

    def FaceInSurfaceSense(self) -> bool:
        return False

    def GetBox(self) -> tuple[float, ...]:
        return self.box

    def GetNextFace(self) -> _Face | None:
        return self.next


class _PartDoc:
    """IPartDoc entity-name semantics: SetEntityName refuses a named face or a
    name already used in the part, and GetEntityName reads the name back.
    Its STEP fixture is synthetic input, not proof of SolidWorks' writer."""

    def __init__(self) -> None:
        faces = [
            _Face(SimpleNamespace(Identity=_CYLINDER, CylinderParams=_cylinder_params(6.5)),
                  _BORE_BOX),
            _Face(SimpleNamespace(Identity=_CYLINDER, CylinderParams=_cylinder_params(10.0)),
                  _BOSS_BOX),
            _Face(SimpleNamespace(Identity=_PLANE, PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0035)),
                  _TOP_BOX),
        ]
        for face, following in zip(faces, faces[1:]):
            face.next = following
        self.faces = faces
        self.body = SimpleNamespace(GetFirstFace=lambda: faces[0])
        self.misreport: str | None = None
        self.halves = {_CYLINDER: 2, _PLANE: 1}

    def GetBodies2(self, body_type: int, visible_only: bool) -> tuple[SimpleNamespace, ...]:
        assert (body_type, visible_only) == (0, False)  # swSolidBody, all bodies
        return (self.body,)

    def GetEntityName(self, face: _Face) -> str:
        return self.misreport if self.misreport is not None and face.name else face.name

    def SetEntityName(self, face: _Face, name: str) -> bool:
        if face.name or any(other.name == name for other in self.faces):
            return False
        face.name = name
        return True

    def step_text(self) -> str:
        return _step(*(
            face.name or "NONE"
            for face in self.faces
            for _half in range(self.halves[face.surface.Identity])
        ))


def test_label_all_faces_labels_every_face_in_box_order() -> None:
    doc = _PartDoc()

    records = label_all_faces(doc, "ch_rocker_arm")

    # Top (box from -8 mm) < boss (-5 mm) < bore (-3.25 mm), not walk order.
    assert [face.name for face in doc.faces] == [_F3, _F2, _F1]
    assert [row["label"] for row in records] == [_F1, _F2, _F3]
    assert records[0]["identity"] == _PLANE and records[0]["outward_normal"] == [0.0, 0.0, 1.0]
    assert records[2]["parameters"] == list(_cylinder_params(6.5))


def test_label_all_faces_keeps_an_existing_name_as_the_label() -> None:
    doc = _PartDoc()
    doc.faces[2].name = "Face<mate>"

    records = label_all_faces(doc, "ch_rocker_arm")

    assert [face.name for face in doc.faces] == [_F2, _F1, "Face<mate>"]
    assert [row["label"] for row in records] == ["Face<mate>", _F1, _F2]


def test_label_all_faces_skips_a_number_an_existing_name_already_uses() -> None:
    doc = _PartDoc()
    doc.faces[0].name = _F1

    label_all_faces(doc, "ch_rocker_arm")

    assert [face.name for face in doc.faces] == [_F1, _F3, _F2]


def test_label_all_faces_never_reuses_a_label_an_earlier_configuration_gave() -> None:
    used: set[str] = set()
    label_all_faces(_PartDoc(), "ch_rocker_arm", used)
    assert used == {_F1, _F2, _F3}
    # Another configuration of the same open part suppresses the face named
    # _F2 and shows a new, unnamed face where it was.
    other = _PartDoc()
    other.faces[0].name, other.faces[2].name = _F3, _F1

    label_all_faces(other, "ch_rocker_arm", used)

    assert [face.name for face in other.faces] == [_F3, _F4, _F1]
    assert used == {_F1, _F2, _F3, _F4}


def test_label_all_faces_fails_when_set_entity_name_is_refused() -> None:
    doc = _PartDoc()
    doc.SetEntityName = lambda _face, _name: False

    with pytest.raises(FeatureFaceError, match="returned False"):
        label_all_faces(doc, "ch_rocker_arm")


def test_label_all_faces_fails_on_a_wrong_read_back() -> None:
    doc = _PartDoc()
    doc.misreport = "Face7"

    with pytest.raises(FeatureFaceError, match="read back 'Face7'"):
        label_all_faces(doc, "ch_rocker_arm")


# --- export_models integration ------------------------------------------------


class _ExportDoc(_PartDoc):
    """An opened part with independently controllable STEP labelling failures.
    ``native`` emulates an export that wrongly saves the part."""

    def __init__(
        self, *, drop_names: bool = False, split: bool = True,
        native: Path | None = None,
    ) -> None:
        super().__init__()
        self.drop_names = drop_names
        self.native = native
        self.saved_paths: list[Path] = []
        if not split:
            self.halves = {_CYLINDER: 1, _PLANE: 1}
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )

    def SaveAs3(self, path: str, _version: int, _options: int) -> int:
        out = Path(path)
        self.saved_paths.append(out)
        if out.suffix == ".STEP":
            text = self.step_text()
            out.write_bytes((text.replace("HAF_", "NONE_") if self.drop_names else text).encode("ascii"))
            if self.native is not None:
                self.native.write_bytes(b"saved by the export")
        else:
            out.write_bytes(b"mesh")
        return 1


_STEMS = ("fr_frame_rail", "ch_rocker_arm")
_ROCKER_STEP = ("ch-rocker-arm.STEP", "ch-rocker-arm.faces.json")
# The split-periodic export of _PartDoc once labelled: ADVANCED_FACE 1-2 the
# bore halves (F0003), 3-4 the boss halves (F0002), 5 the top plane (F0001).
_BOUND = {
    "pivot_bore": ["#10/ADVANCED_FACE[1]/HAF_F0003", "#11/ADVANCED_FACE[2]/HAF_F0003"],
    "hub_top": ["#14/ADVANCED_FACE[5]/HAF_F0001"],
}


def _exporter(tmp_path: Path, monkeypatch, doc=lambda _native: _ExportDoc()):
    """Point export_models at isolated outputs and a synthetic seat.
    Only requirement declarations and COM are doubles: the inventory and
    manifest writers, schema validation and consumer read-back are real."""
    sldprt = tmp_path / "sldprt"
    sldprt.mkdir()
    for stem in _STEMS:
        (sldprt / f"{stem.replace('_', '-')}.SLDPRT").write_bytes(b"native part")
    seen: dict = {"opened": [], "documents": [], "preferences": []}

    def requirement_manifest(stem: str) -> dict:
        # These are the two synthetic face domains above, not the real rocker's
        # drawing requirements. Keep the real writer/schema/binding gate intact.
        return {
            "part": stem.replace("_", "-"),
            "units": "mm",
            "cite": {},
            "drawing": {"revision": "unknown"},
            "frames": {
                "model": {
                    "origin": [0.0, 0.0, 0.0],
                    "x": [1.0, 0.0, 0.0],
                    "y": [0.0, 1.0, 0.0],
                    "z": [0.0, 0.0, 1.0],
                },
            },
            "features": {
                "pivot_bore": {
                    "kind": "hole", "frame": "model", "requirements": [],
                    "nominal_dia": 6.5, "faces": "unknown", "cite": {},
                },
                "hub_top": {
                    "kind": "plane", "frame": "model", "requirements": [],
                    "plane": {"frame": "model", "axis": "z", "value": 3.5},
                    "faces": "unknown", "cite": {},
                },
            },
        }

    # Patch the shared module, not sys.modules: features_bound must see exactly
    # the inventory the producer supplies, rather than the complete recipe.
    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", ("ch_rocker_arm",))
    monkeypatch.setattr(export_features, "DECLARED_PARTS", ("ch_rocker_arm",))
    monkeypatch.setattr(export_features, "feature_selectors", lambda _stem, _configuration=None: _SELECTORS)
    monkeypatch.setattr(export_features, "requirement_manifest", requirement_manifest)

    class _Adapter:
        swApp = SimpleNamespace(CloseAllDocuments=lambda _include_unsaved: True)
        currentModel = None

        def open_model(self, path: str):
            seen["opened"].append(Path(path).name)
            self.currentModel = doc(Path(path))
            seen["documents"].append(self.currentModel)
            return SimpleNamespace(is_success=True, data=None)

        def _attempt(self, call, default=None):
            try:
                return call()
            except Exception:
                return default

    for name, path in {
        "OUT_SLDPRT": sldprt, "OUT_SLDASM": tmp_path / "sldasm",
        "OUT_STL": tmp_path / "stl", "OUT_GLTF": tmp_path / "gltf",
        "OUT_STEP": tmp_path / "step", "OUT_BOXES": tmp_path / "boxes",
        "OUT_PNG": tmp_path / "png", "COLORS": tmp_path / "stl" / "colors.json",
        "SRC_DIGESTS": tmp_path / "stl" / "export-src.json",
        "NEUTRAL_MANIFEST": tmp_path / "reports" / "release-neutral.json",
        "OUT_FEATURES": tmp_path / "features", "REPO": tmp_path,
    }.items():
        monkeypatch.setattr(export_models, name, path)
    monkeypatch.setattr(export_models, "part_stems", lambda: list(_STEMS))
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ())
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _asms: {})
    monkeypatch.setattr(export_models, "_exporter_digest", lambda: "exporter-v1")
    monkeypatch.setattr(
        export_models, "enforce_preferences",
        lambda _adapter, spec: seen["preferences"].append(spec),
    )
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    monkeypatch.setattr(export_models, "validated_outputs", lambda *_args: [])
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (build(_Adapter()), 0)[1],
    )

    def _render_png(_adapter, _stem: str) -> None:
        return None

    monkeypatch.setattr(export_models, "export_build_png", _render_png)

    def run(*argv: str) -> dict:
        monkeypatch.setattr(sys, "argv", ["export_models.py", *argv])
        seen["opened"].clear()
        seen["documents"].clear()
        seen["rc"] = export_models.main()
        return seen

    return run, seen


def _manifest(stem: str, tmp_path: Path) -> dict:
    _path, step = export_features.bundle_paths(stem, tmp_path)
    path = export_features.write_manifest(stem, step, revision="v41")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def _refuse_feature_production(monkeypatch) -> None:
    def refuse(*_args, **_kwargs):
        pytest.fail("full exports must consume existing feature STEPs, not regenerate them")

    for name in ("feature_selectors", "requirement_manifest", "write_manifest"):
        monkeypatch.setattr(export_features, name, refuse)
    monkeypatch.setattr(export_models, "_save_feature_step", refuse)
    monkeypatch.setattr(export_models, "label_all_faces", refuse)


def test_feature_leaf_writes_only_the_labelled_step_and_inventory_without_saving_native(
    tmp_path: Path, monkeypatch,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    before = _tree(tmp_path)

    run("--features", "ch-rocker-arm")

    assert seen["rc"] == 0
    assert seen["opened"] == ["ch-rocker-arm.SLDPRT"]
    after = _tree(tmp_path)
    # Nothing outside the bundle is written: no global STEP/STL/PNG, colours,
    # ledger or certificate, no manifest, and the native keeps its bytes.
    assert {key: after[key] for key in before} == before
    assert set(after) - set(before) == {f"features/ch_rocker_arm/{name}" for name in _ROCKER_STEP}
    assert seen["preferences"] == [export_models.EXPORT_PREFERENCES]
    inventory = json.loads(after["features/ch_rocker_arm/ch-rocker-arm.faces.json"])
    assert inventory["step_sha256"] == hashlib.sha256(after["features/ch_rocker_arm/ch-rocker-arm.STEP"]).hexdigest()
    assert [row["label"] for row in inventory["faces"]] == [_F1, _F2, _F3]


def test_the_manifest_binds_declarations_without_a_seat(tmp_path: Path, monkeypatch) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    run("--features", "ch_rocker_arm")
    monkeypatch.setattr(export_models, "run_build", lambda _build: pytest.fail("binding must not open a seat"))

    manifest = _manifest("ch_rocker_arm", tmp_path)

    assert {name: feature["faces"] for name, feature in manifest["features"].items()} == _BOUND
    step = export_features.bundle_paths("ch_rocker_arm", tmp_path)[1]
    assert manifest["step_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest()
    assert manifest["drawing"]["revision"] == "v41"
    assert features_bound.validate_bundle("ch_rocker_arm", tmp_path)


def test_an_undeclared_part_binds_an_empty_feature_table(tmp_path: Path, monkeypatch) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch)
    declared_manifest = export_features.requirement_manifest
    monkeypatch.setattr(export_features, "DECLARED_PARTS", ())
    # Undeclared, the rocker counts no pivot-bore patches either.
    monkeypatch.setattr(export_features, "STEP_FACE_COUNTS", {})
    monkeypatch.setattr(export_features, "feature_selectors", lambda _stem, _configuration=None: {})
    monkeypatch.setattr(
        export_features, "requirement_manifest",
        lambda stem: {**declared_manifest(stem), "features": {}},
    )
    run("--features", "ch_rocker_arm")

    assert _manifest("ch_rocker_arm", tmp_path)["features"] == {}
    assert features_bound.validate_bundle("ch_rocker_arm", tmp_path)


@pytest.mark.parametrize("argv", [(), ("--force",)], ids=["full", "forced-full"])
def test_full_and_scoped_exports_keep_their_paths_disjoint_and_native_unsaved(
    tmp_path: Path, monkeypatch, argv: tuple[str, ...],
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    native_before = _tree(tmp_path / "sldprt")

    # Full export is a consumer: its authoritative STEP must already exist.
    run("--features", "ch_rocker_arm")
    assert seen["rc"] == 0
    scoped_step = tmp_path / "features" / "ch_rocker_arm" / "ch-rocker-arm.STEP"
    records = json.loads(inventory_path(scoped_step).read_text(encoding="utf-8"))["faces"]
    # ANSI metadata and CRLFs make this an exact raw-byte copy proof, not just
    # equivalent face labels from an independent SaveAs.
    content = scoped_step.read_bytes().replace(
        b"HEADER;\n", b"HEADER;\nFILE_DESCRIPTION(('M\xe9tal \x80 metadata'),'2;1');\n",
    ).replace(b"\n", b"\r\n")
    scoped_step.write_bytes(content)
    write_inventory(scoped_step, records)
    bundle_before = _tree(tmp_path / "features")

    with monkeypatch.context() as consumer:
        _refuse_feature_production(consumer)
        run(*argv)

    assert seen["rc"] == 0
    assert set(seen["opened"]) == {"fr-frame-rail.SLDPRT", "ch-rocker-arm.SLDPRT"}
    full = tmp_path / "step" / "ch-rocker-arm.STEP"
    assert full.read_bytes() == content
    assert {path.name for path in (tmp_path / "step").iterdir()} == {
        "fr-frame-rail.STEP", "ch-rocker-arm.STEP",
    }
    assert "HAF_" not in (tmp_path / "step" / "fr-frame-rail.STEP").read_text()
    assert _tree(tmp_path / "features") == bundle_before
    assert _tree(tmp_path / "sldprt") == native_before
    assert {
        path.relative_to(tmp_path).as_posix()
        for doc in seen["documents"] for path in doc.saved_paths
    } == {"stl/fr-frame-rail.STL", "step/fr-frame-rail.STEP", "stl/ch-rocker-arm.STL"}
    assert all(not face.name for doc in seen["documents"] for face in doc.faces)
    full_outputs = {
        name: raw for name, raw in _tree(tmp_path).items()
        if not name.startswith("features/")
    }

    run("--features", "ch_rocker_arm")

    assert seen["rc"] == 0
    assert seen["opened"] == ["ch-rocker-arm.SLDPRT"]
    assert _tree(tmp_path / "features").keys() == bundle_before.keys()
    assert {
        name: raw for name, raw in _tree(tmp_path).items()
        if not name.startswith("features/")
    } == full_outputs
    assert _tree(tmp_path / "sldprt") == native_before


def test_export_fails_when_the_step_drops_the_face_names(
    tmp_path: Path, monkeypatch,
) -> None:
    run, _seen = _exporter(
        tmp_path, monkeypatch, doc=lambda _native: _ExportDoc(drop_names=True),
    )

    with pytest.raises(FeatureFaceError, match="not an inventory label"):
        run("--features", "ch_rocker_arm")
    assert not inventory_path(tmp_path / "features" / "ch_rocker_arm" / "ch-rocker-arm.STEP").exists()


def test_export_fails_when_the_native_part_is_saved(
    tmp_path: Path, monkeypatch,
) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch, doc=lambda native: _ExportDoc(native=native))

    with pytest.raises(RuntimeError, match="rocker-arm.SLDPRT changed on disk"):
        run("--features", "ch_rocker_arm")


def test_the_manifest_refuses_an_unsplit_rocker_bore(tmp_path: Path, monkeypatch) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch, doc=lambda _native: _ExportDoc(split=False))
    run("--features", "ch_rocker_arm")

    with pytest.raises(FeatureFaceError, match="pivot_bore: expected exactly 2 STEP patches, found 1"):
        _manifest("ch_rocker_arm", tmp_path)
    assert not (tmp_path / "features" / "ch_rocker_arm" / "features.toml").exists()


def test_the_manifest_refuses_more_than_two_rocker_bore_patches(tmp_path: Path, monkeypatch) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch)
    run("--features", "ch_rocker_arm")
    step = export_features.bundle_paths("ch_rocker_arm", tmp_path)[1]
    records = json.loads(inventory_path(step).read_text(encoding="utf-8"))["faces"]
    step.write_text(_step(_F3, _F3, _F3, _F2, _F1), encoding="ascii")
    write_inventory(step, records)

    with pytest.raises(FeatureFaceError, match="expected exactly 2 STEP patches, found 3"):
        _manifest("ch_rocker_arm", tmp_path)


def test_a_feature_rerun_removes_the_previous_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch)
    run("--features", "ch_rocker_arm")
    _manifest("ch_rocker_arm", tmp_path)

    run("--features", "ch_rocker_arm")

    assert not (tmp_path / "features" / "ch_rocker_arm" / "features.toml").exists()


@pytest.mark.parametrize("member", ["inventory", "step"])
def test_full_export_rejects_a_missing_feature_step_before_any_native_or_neutral_write(
    tmp_path: Path, monkeypatch, member: str,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    # A valid earlier bundle must not leak into staging when the last is missing.
    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", _STEMS)
    run("--features", *_STEMS)
    assert seen["rc"] == 0
    step = export_features.bundle_paths("ch_rocker_arm", tmp_path)[1]
    missing = inventory_path(step) if member == "inventory" else step
    missing.unlink()
    before = _tree(tmp_path)
    _refuse_feature_production(monkeypatch)
    monkeypatch.setattr(
        export_models, "run_build",
        lambda _build: pytest.fail("invalid feature inventory must fail before the native seat opens"),
    )

    with pytest.raises(features_bound.FeaturesBoundError, match=re.escape(str(missing))):
        run()

    assert seen["opened"] == []
    assert not (tmp_path / "step").exists()
    assert _tree(tmp_path) == before


@pytest.mark.parametrize(("defect", "diagnostic"), [
    ("dropped-names", "not an inventory label"),
    ("step-drift", "its STEP is"),
    ("invalid-inventory", "unreadable face inventory"),
])
def test_full_export_rejects_malformed_steps_without_regeneration_or_partial_staging(
    tmp_path: Path, monkeypatch, defect: str, diagnostic: str,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", _STEMS)
    run("--features", *_STEMS)
    assert seen["rc"] == 0
    step = export_features.bundle_paths("ch_rocker_arm", tmp_path)[1]
    if defect == "dropped-names":
        records = json.loads(inventory_path(step).read_text(encoding="utf-8"))["faces"]
        step.write_bytes(step.read_bytes().replace(b"HAF_", b"NONE_"))
        document = json.loads(inventory_path(step).read_text(encoding="utf-8"))
        document.update(step_sha256=hashlib.sha256(step.read_bytes()).hexdigest(), faces=records)
        inventory_path(step).write_text(json.dumps(document), encoding="utf-8")
    elif defect == "step-drift":
        step.write_bytes(step.read_bytes() + b"\r\n/* raw header drift */\r\n")
    else:
        inventory_path(step).write_text("{", encoding="utf-8")
    # A prior full output is neither replaced by the valid first bundle nor
    # supplemented with a partial last bundle on a failed preflight.
    previous = tmp_path / "step" / "fr-frame-rail.STEP"
    previous.parent.mkdir()
    previous.write_bytes(b"previous full export")
    before = _tree(tmp_path)
    _refuse_feature_production(monkeypatch)
    monkeypatch.setattr(
        export_models, "run_build",
        lambda _build: pytest.fail("malformed feature STEPs must fail before the native seat opens"),
    )

    with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic):
        run("--force")

    assert seen["opened"] == []
    assert _tree(tmp_path) == before


@pytest.mark.parametrize(("defect", "diagnostic"), [
    ("no-features", "feature manifest has no features"),
    ("scalar-feature", "every feature must be a table"),
    ("invalid-toml", "invalid TOML"),
    ("unbound-digest", "does not bind the adjacent STEP"),
    ("half-a-label", "omit STEP faces labelled"),
    ("foreign-face", "name no or repeated STEP faces"),
    ("face-count", "pivot_bore must be exactly 1 STEP faces, found 2"),
])
def test_the_release_gate_rejects_malformed_manifests(
    tmp_path: Path, monkeypatch, defect: str, diagnostic: str,
) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch)
    run("--features", "ch_rocker_arm")
    manifest = _manifest("ch_rocker_arm", tmp_path)
    manifest_path = export_features.bundle_paths("ch_rocker_arm", tmp_path)[0]
    bore = manifest["features"]["pivot_bore"]
    if defect == "no-features":
        manifest["features"] = {}
    elif defect == "scalar-feature":
        manifest["features"]["pivot_bore"] = "not a table"
    elif defect == "unbound-digest":
        manifest["step_sha256"] = "0" * 64
    elif defect == "half-a-label":
        bore["faces"] = bore["faces"][:1]
    elif defect == "foreign-face":
        bore["faces"] = [bore["faces"][0].replace("HAF_F0003", "HAF_F0001"), bore["faces"][1]]
    elif defect == "face-count":
        monkeypatch.setitem(export_features.STEP_FACE_COUNTS, "ch_rocker_arm", {"pivot_bore": 1})
    if defect == "invalid-toml":
        manifest_path.write_text("[features", encoding="utf-8")
    else:
        manifest_path.write_text(export_features._toml(manifest), encoding="utf-8")

    with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic):
        features_bound.validate_bundle("ch_rocker_arm", tmp_path)


def test_feature_export_preserves_the_build_runner_exit_code(tmp_path: Path, monkeypatch) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    monkeypatch.setattr(export_models, "run_build", lambda _build: 37)

    run("--features", "ch_rocker_arm")

    assert seen["rc"] == 37
    assert not (tmp_path / "features").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--features", "frame_rail"],
        ["--features", "ch_rocker_arm", "--force"],
        ["--features", "ch_rocker_arm", "--record-digests"],
        ["--features", "ch_rocker_arm", "--comparisons"],
    ],
    ids=["unsupported-part", "forced", "recording", "with-comparisons"],
)
def test_features_flag_rejects_invalid_selections(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setitem(
        sys.modules, "export_features", SimpleNamespace(SUPPORTED_PARTS=("ch_rocker_arm",)),
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", *argv])

    with pytest.raises(SystemExit) as rejected:
        export_models._parse_args()
    assert rejected.value.code == 2
