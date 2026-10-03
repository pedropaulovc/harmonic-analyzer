"""Offline tests for requirement-feature face naming and STEP read-back.

Every SolidWorks object here is a synthetic double: these tests prove the
selection, naming, parsing and export-ordering rules, NOT that a seat's STEP
writer carries face names (that needs the farm proof described in issue #1204).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import export_models
from _export_feature_faces import (
    FeatureFaceError,
    assign_feature_patches,
    face_name,
    name_feature_faces,
    step_face_sets,
)
from _gtol_spec import CylinderFace, PlanarFace
from _part_pmi import _FaceGeometry

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


def _geometries() -> list[_FaceGeometry]:
    return [
        _FaceGeometry("upper", _CYLINDER, _cylinder_params(6.5), None, _UPPER_HALF),
        _FaceGeometry("boss", _CYLINDER, _cylinder_params(10.0), None, _BOSS_BOX),
        _FaceGeometry("lower", _CYLINDER, _cylinder_params(6.5), None, _LOWER_HALF),
        _FaceGeometry(
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


_BORE_1 = face_name("pivot_bore", 1)
_BORE_2 = face_name("pivot_bore", 2)
_TOP_1 = face_name("hub_top", 1)


# --- STEP read-back ----------------------------------------------------------


def test_step_face_sets_groups_labelled_faces_and_ignores_unnamed_ones() -> None:
    text = _step("NONE", _BORE_2, "it's unnamed", _TOP_1, _BORE_1)

    assert step_face_sets(text, ["pivot_bore", "hub_top"]) == {
        "pivot_bore": [
            "#14/ADVANCED_FACE[5]/HAF_PIVOT_BORE__P01",
            "#11/ADVANCED_FACE[2]/HAF_PIVOT_BORE__P02",
        ],
        "hub_top": ["#13/ADVANCED_FACE[4]/HAF_HUB_TOP__P01"],
    }


def test_one_native_bore_split_into_two_step_faces_keeps_both() -> None:
    # Split periodic exports the one native Ø6.5 bore as two ADVANCED_FACE
    # halves; both are expected to carry its name.  Ordinals are illustrative.
    labels = [_BORE_1, *["NONE"] * 14, _BORE_1, _TOP_1]
    text = _step(*labels)
    bore = ["#10/ADVANCED_FACE[1]/HAF_PIVOT_BORE__P01", "#25/ADVANCED_FACE[16]/HAF_PIVOT_BORE__P01"]
    expected = {"pivot_bore": bore, "hub_top": ["#26/ADVANCED_FACE[17]/HAF_HUB_TOP__P01"]}

    assert step_face_sets(text, ["pivot_bore", "hub_top"]) == expected
    assert step_face_sets(text, {"pivot_bore": [_BORE_1], "hub_top": [_TOP_1]}) == expected


@pytest.mark.parametrize(
    ("labels", "complaint"),
    [
        ((_BORE_1,), "hub_top: no named STEP face"),
        ((_BORE_1, _TOP_1, face_name("tip_flat", 1)), "unknown feature 'tip_flat'"),
        ((_BORE_1, _TOP_1, "HAF_pivot"), "HAF_pivot: malformed"),
        ((_BORE_1, face_name("pivot_bore", 3), _TOP_1), "patch numbers [1, 3] are not 1..2"),
    ],
    ids=["missing", "unknown", "malformed", "gap"],
)
def test_step_face_sets_refuses_bad_labels(labels: tuple[str, ...], complaint: str) -> None:
    with pytest.raises(FeatureFaceError, match=re.escape(complaint)):
        step_face_sets(_step(*labels), ["pivot_bore", "hub_top"])


@pytest.mark.parametrize(
    ("labels", "assigned", "complaint"),
    [
        # P01 alone is a contiguous set: only the export-time claim sees P02 lost.
        (
            (_BORE_1, _TOP_1),
            {"pivot_bore": [_BORE_1, _BORE_2], "hub_top": [_TOP_1]},
            "pivot_bore: assigned labels ['HAF_PIVOT_BORE__P02'] label no STEP face",
        ),
        (
            (_BORE_1, _BORE_2, _TOP_1),
            {"pivot_bore": [_BORE_1], "hub_top": [_TOP_1]},
            "HAF_PIVOT_BORE__P02: labels a STEP face but was never assigned",
        ),
        (
            (_BORE_1, _TOP_1),
            {"pivot_bore": [_BORE_1], "hub_top": [_TOP_1, _BORE_1]},
            "HAF_PIVOT_BORE__P01: claimed by features ['hub_top', 'pivot_bore']",
        ),
    ],
    ids=["dropped-label", "unassigned-label", "two-features"],
)
def test_step_face_sets_holds_the_export_to_its_assigned_labels(
    labels: tuple[str, ...], assigned: dict[str, list[str]], complaint: str,
) -> None:
    with pytest.raises(FeatureFaceError, match=re.escape(complaint)):
        step_face_sets(_step(*labels), assigned)


def test_step_face_sets_rejects_a_duplicated_entity_id() -> None:
    text = _step(_BORE_1, _BORE_1, _TOP_1, ids=(10, 10, 11))

    with pytest.raises(FeatureFaceError, match=re.escape("#10: STEP entity id defined 2 times")):
        step_face_sets(text, ["pivot_bore", "hub_top"])


def test_step_face_sets_rejects_a_step_with_no_faces() -> None:
    with pytest.raises(FeatureFaceError, match="no ADVANCED_FACE"):
        step_face_sets(_step(), ["pivot_bore"])


@pytest.mark.parametrize("feature", ["PivotBore", "pivot__bore", "pivot-bore", "_bore"])
def test_feature_keys_must_round_trip_through_upper_case_names(feature: str) -> None:
    with pytest.raises(FeatureFaceError, match="feature key"):
        face_name(feature, 1)


# --- native selection ---------------------------------------------------------


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


# --- COM naming (synthetic doubles) -----------------------------------------


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
        halves = {_CYLINDER: 2, _PLANE: 1}
        return _step(*(
            face.name or "NONE"
            for face in self.faces
            for _half in range(halves[face.surface.Identity])
        ))


@pytest.fixture
def selectors(monkeypatch) -> dict[str, tuple]:
    calls: list[str] = []

    def feature_selectors(stem: str) -> dict[str, tuple]:
        calls.append(stem)
        return _SELECTORS

    monkeypatch.setitem(
        sys.modules, "export_features",
        SimpleNamespace(feature_selectors=feature_selectors, SUPPORTED_PARTS=("rocker_arm",)),
    )
    return {"calls": calls}


# The split-periodic export of _PartDoc once named: ADVANCED_FACE 1-2 the bore
# halves, 3-4 the unnamed boss halves, 5 the top plane.
_EXPORTED_SETS = {
    "pivot_bore": [
        "#10/ADVANCED_FACE[1]/HAF_PIVOT_BORE__P01",
        "#11/ADVANCED_FACE[2]/HAF_PIVOT_BORE__P01",
    ],
    "hub_top": ["#14/ADVANCED_FACE[5]/HAF_HUB_TOP__P01"],
}


def test_name_feature_faces_assigns_native_names_without_claiming_step_behavior(
    selectors,
) -> None:
    doc = _PartDoc()

    assert name_feature_faces(doc, "rocker_arm") == {
        "pivot_bore": [_BORE_1], "hub_top": [_TOP_1],
    }
    assert [face.name for face in doc.faces] == [_BORE_1, "", _TOP_1]


def test_name_feature_faces_refuses_to_rename_a_named_face(selectors) -> None:
    doc = _PartDoc()
    doc.faces[2].name = "Face<mate>"

    with pytest.raises(FeatureFaceError, match="already named 'Face<mate>'"):
        name_feature_faces(doc, "rocker_arm")


def test_name_feature_faces_fails_when_set_entity_name_is_refused(selectors) -> None:
    doc = _PartDoc()
    doc.SetEntityName = lambda _face, _name: False

    with pytest.raises(FeatureFaceError, match="returned False"):
        name_feature_faces(doc, "rocker_arm")


def test_name_feature_faces_fails_on_a_wrong_read_back(selectors) -> None:
    doc = _PartDoc()
    doc.misreport = "Face7"

    with pytest.raises(FeatureFaceError, match="read back 'Face7'"):
        name_feature_faces(doc, "rocker_arm")


# --- export_models integration ------------------------------------------------


class _ExportDoc(_PartDoc):
    """An opened part with independently controllable STEP naming failures.
    ``native`` emulates an export that wrongly saves the part."""

    def __init__(
        self, *, drop_names: bool = False, drop_half: bool = False,
        native: Path | None = None,
    ) -> None:
        super().__init__()
        self.drop_names = drop_names
        self.drop_half = drop_half
        self.native = native
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )

    def SaveAs3(self, path: str, _version: int, _options: int) -> int:
        out = Path(path)
        if out.suffix == ".STEP":
            text = self.step_text()
            if self.drop_half:
                text = text.replace(_BORE_1, "NONE", 1)
            out.write_bytes((text.replace("HAF_", "NONE_") if self.drop_names else text).encode("ascii"))
            if self.native is not None:
                self.native.write_bytes(b"saved by the export")
        else:
            out.write_bytes(b"mesh")
        return 1


_STEMS = ("frame_rail", "rocker_arm")
_ROCKER_BUNDLE = ("rocker-arm.STEP", "features.toml")


def _exporter(tmp_path: Path, monkeypatch, doc=lambda _native: _ExportDoc()):
    """Point export_models at isolated outputs and a synthetic seat.
    The manifest writer is a boundary double; generator tests own its schema."""
    sldprt = tmp_path / "sldprt"
    sldprt.mkdir()
    for stem in _STEMS:
        (sldprt / f"{stem.replace('_', '-')}.SLDPRT").write_bytes(b"native part")
    seen: dict = {"opened": [], "preferences": [], "drop_half": False}

    def write_manifest(stem: str, step: Path, *, revision: str) -> Path:
        path = step.with_name("features.toml")
        path.write_text(
            f'step = "{step.name}"\n'
            f'step_sha256 = "{hashlib.sha256(step.read_bytes()).hexdigest()}"\n'
            f'[drawing]\nrevision = "{revision}"\n',
            encoding="utf-8",
        )
        return path

    monkeypatch.setitem(sys.modules, "export_features", SimpleNamespace(
        SUPPORTED_PARTS=("rocker_arm",),
        feature_selectors=lambda _stem: _SELECTORS,
        write_manifest=write_manifest,
    ))

    class _Adapter:
        swApp = SimpleNamespace(CloseAllDocuments=lambda _include_unsaved: True)
        currentModel = None

        async def open_model(self, path: str):
            seen["opened"].append(Path(path).name)
            self.currentModel = doc(Path(path))
            self.currentModel.drop_half |= seen["drop_half"]
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
    monkeypatch.setattr(export_models, "release_revision", lambda: "v41")
    monkeypatch.setattr(
        export_models, "enforce_preferences",
        lambda _adapter, spec: seen["preferences"].append(spec),
    )
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    monkeypatch.setattr(export_models, "validated_outputs", lambda *_args: [])
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (asyncio.run(build(_Adapter())), 0)[1],
    )

    async def _render_png(_adapter, _stem: str) -> None:
        return None

    monkeypatch.setattr(export_models, "export_build_png", _render_png)

    def run(*argv: str) -> dict:
        monkeypatch.setattr(sys, "argv", ["export_models.py", *argv])
        seen["opened"].clear()
        seen["rc"] = export_models.main()
        return seen

    return run, seen


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def test_feature_bundle_writes_only_step_and_manifest_without_saving_native(
    tmp_path: Path, monkeypatch,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    before = _tree(tmp_path)

    run("--features", "rocker-arm")

    assert seen["rc"] == 0
    assert seen["opened"] == ["rocker-arm.SLDPRT"]
    after = _tree(tmp_path)
    # Nothing outside the bundle is written: no global STEP/STL/PNG, colours,
    # ledger or certificate, and the native keeps its bytes.
    assert {key: after[key] for key in before} == before
    assert set(after) - set(before) == {f"features/rocker_arm/{name}" for name in _ROCKER_BUNDLE}
    bundle = tmp_path / "features" / "rocker_arm"
    step = bundle / "rocker-arm.STEP"
    assert step_face_sets(step.read_text(), ["pivot_bore", "hub_top"]) == _EXPORTED_SETS
    assert (bundle / "features.toml").is_file()
    assert seen["preferences"] == [export_models.EXPORT_PREFERENCES]


def test_full_and_scoped_exports_keep_their_paths_disjoint_and_native_unsaved(
    tmp_path: Path, monkeypatch,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)

    run()

    assert seen["rc"] == 0
    assert seen["opened"] == ["frame-rail.SLDPRT", "rocker-arm.SLDPRT"]
    full = (tmp_path / "step" / "rocker-arm.STEP").read_bytes()
    assert step_face_sets(full.decode(), ["pivot_bore", "hub_top"]) == _EXPORTED_SETS
    assert "HAF_" not in (tmp_path / "step" / "frame-rail.STEP").read_text()
    assert not (tmp_path / "features").exists()  # the full export writes no bundle
    assert (tmp_path / "sldprt" / "rocker-arm.SLDPRT").read_bytes() == b"native part"

    run("--features", "rocker_arm")

    scoped = (tmp_path / "features" / "rocker_arm" / "rocker-arm.STEP").read_text()
    assert step_face_sets(scoped, ["pivot_bore", "hub_top"]) == _EXPORTED_SETS
    assert seen["preferences"] == [export_models.EXPORT_PREFERENCES] * 2


@pytest.mark.parametrize("argv", [(), ("--features", "rocker_arm")], ids=["full", "bundle"])
def test_export_fails_when_the_step_drops_the_face_names(
    tmp_path: Path, monkeypatch, argv: tuple[str, ...],
) -> None:
    run, _seen = _exporter(
        tmp_path, monkeypatch, doc=lambda _native: _ExportDoc(drop_names=True),
    )

    with pytest.raises(FeatureFaceError, match="pivot_bore: no named STEP face"):
        run(*argv)
    assert not (tmp_path / "features" / "rocker_arm" / "features.toml").exists()


@pytest.mark.parametrize("argv", [(), ("--features", "rocker_arm")], ids=["full", "bundle"])
def test_export_fails_when_the_native_part_is_saved(
    tmp_path: Path, monkeypatch, argv: tuple[str, ...],
) -> None:
    run, _seen = _exporter(tmp_path, monkeypatch, doc=lambda native: _ExportDoc(native=native))

    with pytest.raises(RuntimeError, match="rocker-arm.SLDPRT changed on disk"):
        run(*argv)
    assert not (tmp_path / "features" / "rocker_arm" / "features.toml").exists()


@pytest.mark.parametrize("argv", [(), ("--features", "rocker_arm")], ids=["full", "bundle"])
def test_export_refuses_a_periodic_bore_with_only_one_named_half(
    tmp_path: Path, monkeypatch, argv: tuple[str, ...],
) -> None:
    run, _seen = _exporter(
        tmp_path, monkeypatch, doc=lambda _native: _ExportDoc(drop_half=True),
    )

    with pytest.raises(FeatureFaceError, match="pivot_bore: expected exactly 2 STEP patches, found 1"):
        run(*argv)
    assert not (tmp_path / "features" / "rocker_arm" / "features.toml").exists()


def test_export_refuses_more_than_two_named_rocker_bore_patches(tmp_path: Path, selectors) -> None:
    doc = _ExportDoc()
    doc.step_text = lambda: _step(_BORE_1, _BORE_1, _BORE_1, "NONE", _TOP_1)

    with pytest.raises(FeatureFaceError, match="expected exactly 2 STEP patches, found 3"):
        export_models._save_feature_step(doc, "rocker_arm", tmp_path / "rocker-arm.STEP")


def test_a_failed_rerun_removes_the_previous_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    run("--features", "rocker_arm")
    seen["drop_half"] = True

    with pytest.raises(FeatureFaceError, match="expected exactly 2 STEP patches"):
        run("--features", "rocker_arm")

    assert not (tmp_path / "features" / "rocker_arm" / "features.toml").exists()


def test_feature_export_preserves_the_build_runner_exit_code(tmp_path: Path, monkeypatch) -> None:
    run, seen = _exporter(tmp_path, monkeypatch)
    monkeypatch.setattr(export_models, "run_build", lambda _build: 37)

    run("--features", "rocker_arm")

    assert seen["rc"] == 37
    assert not (tmp_path / "features").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--features", "frame_rail"],
        ["--features", "rocker_arm", "--force"],
        ["--features", "rocker_arm", "--record-digests"],
        ["--features", "rocker_arm", "--comparisons"],
    ],
    ids=["unsupported-part", "forced", "recording", "with-comparisons"],
)
def test_features_flag_rejects_invalid_selections(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setitem(
        sys.modules, "export_features", SimpleNamespace(SUPPORTED_PARTS=("rocker_arm",)),
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", *argv])

    with pytest.raises(SystemExit) as rejected:
        export_models._parse_args()
    assert rejected.value.code == 2
