"""Offline contracts for the six remaining PR 358 fastener sheets."""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_common
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


class _FakeCylinderSurface:
    def __init__(self, radius_mm: float, *, cylindrical: bool = True) -> None:
        self.CylinderParams = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, radius_mm / 1000.0)
        self._cylindrical = cylindrical

    def IsCylinder(self) -> bool:
        return self._cylindrical


class _FakeFace:
    def __init__(self, radius_mm: float, area: float, *, cylindrical: bool = True) -> None:
        self._surface = _FakeCylinderSurface(radius_mm, cylindrical=cylindrical)
        self._area = area

    def GetSurface(self) -> _FakeCylinderSurface:
        return self._surface

    def GetArea(self) -> float:
        return self._area


class _FakeAttemptAdapter:
    @staticmethod
    def _attempt(call, *, default=None):
        try:
            return call()
        except Exception:
            return default


def test_visible_cylindrical_face_uses_exact_radius_and_largest_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = _FakeFace(4.0, 100.0)
    small = _FakeFace(3.175, 1.0)
    large = _FakeFace(3.175, 2.0)
    planar = _FakeFace(3.175, 1000.0, cylindrical=False)
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, *_args: value)
    monkeypatch.setattr(
        _drawing_common,
        "visible_view_entities",
        lambda *_args, **_kwargs: [wrong, small, large, planar],
    )

    selected = _drawing_common.visible_cylindrical_face(
        _FakeAttemptAdapter(), object(), 6.35, label="shoulder"
    )

    assert selected is large


def test_visible_cylindrical_face_reports_candidate_radii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, *_args: value)
    monkeypatch.setattr(
        _drawing_common,
        "visible_view_entities",
        lambda *_args, **_kwargs: [_FakeFace(4.0, 1.0)],
    )

    with pytest.raises(RuntimeError, match=r"radius 3\.1750 mm; candidates=4\.0000"):
        _drawing_common.visible_cylindrical_face(
            _FakeAttemptAdapter(), object(), 6.35, label="shoulder"
        )


@dataclass(frozen=True)
class Case:
    part_name: str
    module_name: str
    spec_name: str
    build_name: str
    shank_dim: str
    thread_on_dimension: bool = False


CASES = (
    Case(
        "cone-pivot-screw",
        "draw_cone_pivot_screw",
        "cone_pivot_screw_spec",
        "build_cone_pivot_screw",
        "ShoulderDiaDim",
    ),
    Case(
        "cone-tip-pinch-screw",
        "draw_cone_tip_pinch_screw",
        "cone_tip_pinch_screw_spec",
        "build_cone_tip_pinch_screw",
        "ShankDiaDim",
    ),
    Case(
        "hanger-screw",
        "draw_hanger_screw",
        "hanger_screw_spec",
        "build_hanger_screw",
        "ShankDia",
    ),
    Case(
        "pen-set-screw",
        "draw_pen_set_screw",
        "pen_set_screw_spec",
        "build_pen_set_screw",
        "ShankDia",
    ),
    Case(
        "swing-stop-screw",
        "draw_swing_stop_screw",
        "swing_stop_screw_spec",
        "build_swing_stop_screw",
        "ShankDiaDim",
    ),
    Case(
        "thumb-screw",
        "draw_thumb_screw",
        "thumb_screw_spec",
        "build_thumb_screw",
        "ShankDia",
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_registry_paths_and_marked_dimensions(case: Case) -> None:
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    part = importlib.import_module(case.build_name)
    key = case.part_name.replace("-", "_")
    registered = DRAWINGS_BY_NAME[key]

    assert registered.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith(f"/slddrw/{case.part_name}.SLDDRW")
    assert drawing.PDF.as_posix().endswith(f"/pdf/{case.part_name}.pdf")
    assert drawing.PNG.as_posix().endswith(f"/png/{case.part_name}_drawing.png")
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    kept = (
        set(drawing.END_KEEP)
        | set(getattr(drawing, "SIDE_KEEP", {}))
        | set(getattr(drawing, "SLOT_KEEP", {}))
    )
    assert kept == set().union(*spec.DRAWING_DIMENSIONS.values())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_catalog_thread_and_dimension_callout_are_not_invented(case: Case) -> None:
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    part = importlib.import_module(case.build_name)
    catalog = fastener(case.part_name)

    assert spec.THREAD == catalog.thread
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    if case.part_name == "cone-pivot-screw":
        assert spec.SHOULDER_DIA == catalog.model_diameter_mm
        assert spec.UNDERHEAD_LEN == catalog.length_mm
        assert part.SHOULDER_DIA == spec.SHOULDER_DIA
        assert part.SHOULDER_LEN == spec.SHOULDER_LEN
        assert part.THREAD_TAIL_LEN == spec.THREAD_TAIL_LEN
        assert "GROUND" in spec.DRAWING_NOTES
        return
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert part.SHANK_DIA == spec.SHANK_DIA
    assert part.SHANK_LEN == spec.SHANK_LEN
    assert "REFERENCE ONLY" in spec.DRAWING_NOTES
    assert "FULL THREAD" in spec.DRAWING_NOTES
    assert (
        "DISTAL END FACE PERPENDICULAR 0.05 TO THREAD PITCH-DIAMETER AXIS"
        in spec.DRAWING_NOTES
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_title_block_properties_are_complete(case: Case) -> None:
    config = _config.parts(case.part_name)
    assert config["number"].startswith("MHA-")
    assert config["material"] == config["material_specification"]
    assert config["finish"].strip()
    assert int(config["quantity"]) >= 1


def test_assembly_fastener_quantities_are_pinned() -> None:
    assert int(_config.parts("foot-screw")["quantity"]) == 3
    assert int(_config.parts("fillister-screw")["quantity"]) == 22


@pytest.mark.parametrize(
    "spec_name",
    (
        "cone_tip_pinch_screw_spec",
        "hanger_screw_spec",
        "pen_set_screw_spec",
        "swing_stop_screw_spec",
        "thumb_screw_spec",
    ),
)
def test_sheets_without_length_dimensions_state_catalog_underhead_length(
    spec_name: str,
) -> None:
    spec = importlib.import_module(spec_name)
    assert spec.DRAWING_DIMENSIONS.get("Shank", set()).isdisjoint(
        {"ShankLg", "ThreadLg"}
    )
    assert f"UNDERHEAD LENGTH {spec.SHANK_LEN:.2f}." in spec.DRAWING_NOTES


@pytest.mark.parametrize(
    "spec_name",
    (
        "bracket_screw_spec",
        "clamp_screw_spec",
        "fillister_screw_spec",
        "foot_screw_spec",
        "lag_screw_spec",
        "slotted_screw_spec",
    ),
)
def test_dimensioned_sheets_do_not_duplicate_underhead_length_note(
    spec_name: str,
) -> None:
    spec = importlib.import_module(spec_name)
    assert "ShankLg" in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert "UNDERHEAD LENGTH" not in spec.DRAWING_NOTES


@pytest.mark.parametrize(
    ("spec_name", "build_name"),
    (
        ("cone_pivot_screw_spec", "build_cone_pivot_screw"),
        ("cone_tip_pinch_screw_spec", "build_cone_tip_pinch_screw"),
        ("swing_stop_screw_spec", "build_swing_stop_screw"),
    ),
)
def test_slotted_screw_slot_dimensions_live_in_the_pure_contract(
    spec_name: str, build_name: str
) -> None:
    spec = importlib.import_module(spec_name)
    build_source = Path(importlib.import_module(build_name).__file__).read_text(
        encoding="utf-8"
    )
    assert spec.SLOT_W > 0
    assert spec.SLOT_D > 0
    if spec_name == "cone_pivot_screw_spec":
        assert spec.DRAWING_DIMENSIONS["SlotProfile"] == {"SlotWDim"}
        assert spec.DRAWING_DIMENSIONS["DriverSlot"] == {"SlotDepth"}
    else:
        assert f"{spec.SLOT_W:.2f} +/-0.10 WIDE" in spec.DRAWING_NOTES
        assert f"{spec.SLOT_D:.2f} +/-0.10 DEEP" in spec.DRAWING_NOTES
    assert "SLOT_W," in build_source
    assert "SLOT_D," in build_source


def test_cone_pivot_defines_shoulder_clearance_and_thread_engagement() -> None:
    spec = importlib.import_module("cone_pivot_screw_spec")
    build_source = Path(
        importlib.import_module("build_cone_pivot_screw").__file__
    ).read_text(encoding="utf-8")
    base = importlib.import_module("build_harmonic_base")
    drive = importlib.import_module("build_drive_train_assembly")
    platform = importlib.import_module("build_cone_swing_platform")

    assert spec.SHOULDER_LEN == spec.PLATFORM_THICKNESS + spec.AXIAL_CLEARANCE
    assert spec.SHOULDER_DIA == pytest.approx(6.35)
    assert spec.THREAD == "#10-24"
    assert spec.THREAD_MAJOR_DIA == pytest.approx(4.826)
    assert spec.THREAD_SOLID_DIA == pytest.approx(3.797)
    assert spec.THREAD_PITCH == pytest.approx(25.4 / 24.0)
    assert (spec.SHOULDER_DIA - spec.THREAD_MAJOR_DIA) / 2.0 >= 0.75
    assert spec.PLATFORM_THICKNESS == platform.PLATE_T
    assert platform.PIVOT_HOLE_DIA > spec.SHOULDER_DIA
    assert spec.THREAD_TAIL_LEN >= spec.THREAD_MAJOR_DIA
    assert base.PIVOT_SEAT_SPEC.kind == "tapped"
    assert base.PIVOT_SEAT_SPEC.size == spec.THREAD
    assert base.PIVOT_SEAT_SPEC.thread_class == "2B"
    assert drive.PSCREW_THREAD == spec.THREAD
    assert drive.PSCREW_THREAD_SOLID_DIA == spec.THREAD_SOLID_DIA
    assert drive.PSCREW_THREAD_TAP_DRILL_DIA == spec.THREAD_TAP_DRILL_DIA
    assert spec.THREAD_TAP_DRILL_DIA == pytest.approx(3.797)
    assert spec.THREAD_SOLID_DIA == spec.THREAD_TAP_DRILL_DIA
    assert spec.THREAD_SOLID_DIA == base.PIVOT_SCREW_HOLE_DIA
    assert "THREAD_SOLID_DIA / 2.0" in build_source
    assert "THREAD_MAJOR_DIA / 2.0" not in build_source
    assert base.PIVOT_HOLE_DEPTH - spec.THREAD_TAIL_LEN >= 1.5
    assert "DO NOT RELEASE" not in spec.DRAWING_NOTES
    assert "THREAD LENGTH 8.00" not in spec.DRAWING_NOTES
    assert f"{spec.MIN_FULL_FORM:.2f} MIN FULL-FORM THREAD" in spec.DRAWING_NOTES
    assert "INCOMPLETE THREAD/RUNOUT AT SHOULDER 1P MAX" in spec.DRAWING_NOTES
    assert (
        spec.THREAD_TAIL_LEN
        - spec.THREAD_LENGTH_TOL
        - spec.THREAD_RUNOUT_PITCHES * spec.THREAD_PITCH
        - spec.DISTAL_CHAMFER
        >= spec.MIN_FULL_FORM
    )
    assert "SLOT CENTERPLANE OFFSET" not in spec.DRAWING_NOTES
    assert "SLOT FLOOR CORNERS R0.05-0.15" in spec.DRAWING_NOTES
    assert "TITLE-BLOCK EDGE OVERRIDE" in spec.DRAWING_NOTES
    assert "MANDATORY UNDERHEAD FILLET R0.10-0.25" in spec.DRAWING_NOTES
    assert "MANDATORY DISTAL START CHAMFER 0.25-0.50 X 45°" in spec.DRAWING_NOTES


def test_cone_pivot_tail_view_exposes_the_ground_shoulder() -> None:
    drawing = importlib.import_module("draw_cone_pivot_screw")
    spec = importlib.import_module("cone_pivot_screw_spec")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    build_source = Path(
        importlib.import_module("build_cone_pivot_screw").__file__
    ).read_text(encoding="utf-8")
    assert drawing.RECIPE.end_view == "*Bottom"
    assert drawing.RECIPE.side_center == (0.190, 0.170)
    assert f"INNER CIRCLE = {spec.THREAD} EXTERNAL THREAD" in spec.END_VIEW_NOTE
    assert "MIDDLE CIRCLE = GROUND SHOULDER OD" in spec.END_VIEW_NOTE
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShoulderLg", "ThreadLg"}
    assert set(drawing.SLOT_KEEP) == {"SlotWDim", "SlotDepth"}
    assert drawing.SIDE_DIMENSION_CALLOUTS["ThreadLg"] == spec.THREAD_DESIGNATION
    assert '"1/4-20' not in drawing_source
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_diameter_mm == spec.SHOULDER_DIA
    assert drawing_source.count("add_datum_feature(") == 1
    assert drawing_source.count("add_feature_control_frame(") == 4
    assert drawing_source.count("add_surface_finish(") == 1
    assert "edge_entity=head_bearing_edge" in drawing_source
    assert "import_cosmetic_threads(adapter, side)" in drawing_source
    assert 'place_view(adapter, str(SOURCE), "*Right"' in drawing_source
    assert 'quantity="SLOT MEDIAN PLANE"' in drawing_source
    assert build_source.count("set_dimension_symmetric_tolerance(") == 5
    assert build_source.count("set_dimension_bilateral_tolerance(") == 2
    assert "InsertCosmeticThread3(" in build_source
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in build_source
    assert '_blank_ref_geometry(adapter, "HeadTop", "PLANE")' in build_source
    assert '_blank_ref_geometry(adapter, pivot_axis, "AXIS")' in build_source
    assert "artefacts = await save_part_and_images" in build_source
    assert 'await _assert_saved_drawing_properties(adapter, artefacts["part"])' in (
        build_source
    )


class _SavedPropertyModel:
    def __init__(self, properties: dict[str, str]) -> None:
        self.properties = properties

    def GetCustomInfoValue(self, _configuration: str, name: str) -> str:
        return self.properties.get(name, "")


class _SavedPropertyAdapter:
    def __init__(self, properties: dict[str, str]) -> None:
        self.properties = properties
        self.currentModel = object()
        self.closed: list[bool] = []
        self.opened: list[str] = []
        self.swApp = SimpleNamespace(CloseAllDocuments=self._close_all)

    def _close_all(self, include_unsaved: bool) -> bool:
        self.closed.append(include_unsaved)
        return True

    def _attempt(self, operation, default=None):
        try:
            return operation()
        except Exception:  # pragma: no cover - mirrors the adapter boundary
            return default

    async def open_model(self, path: str):
        self.opened.append(path)
        self.currentModel = _SavedPropertyModel(self.properties)
        return SimpleNamespace(is_success=True, error=None, data=None)


def test_cone_pivot_producer_reopens_saved_part_and_requires_drawing_properties() -> None:
    build = importlib.import_module("build_cone_pivot_screw")
    properties = {
        name: f"persisted {name}" for name in build._DRAWING_REQUIRED_PROPERTIES
    }
    adapter = _SavedPropertyAdapter(properties)

    asyncio.run(build._assert_saved_drawing_properties(adapter, "exact.SLDPRT"))

    assert adapter.closed == [True]
    assert adapter.opened == ["exact.SLDPRT"]


def test_cone_pivot_producer_rejects_missing_persisted_drawing_property() -> None:
    build = importlib.import_module("build_cone_pivot_screw")
    properties = {
        name: f"persisted {name}" for name in build._DRAWING_REQUIRED_PROPERTIES
    }
    properties.pop("Manufacturing Notes")
    adapter = _SavedPropertyAdapter(properties)

    with pytest.raises(RuntimeError, match="Manufacturing Notes"):
        asyncio.run(build._assert_saved_drawing_properties(adapter, "exact.SLDPRT"))


def test_cone_tip_pinch_sheet_defines_a_flat_end_without_duplicate_head_diameter() -> None:
    drawing = importlib.import_module("draw_cone_tip_pinch_screw")
    spec = importlib.import_module("cone_tip_pinch_screw_spec")
    assert drawing.END_KEEP == {}
    assert drawing.RECIPE.side_center == (0.190, 0.190)
    assert spec.DRAWING_DIMENSIONS == {}
    assert "FLAT-END PINCH SCREW; NO CONICAL POINT" in spec.DRAWING_NOTES
    assert "DISTAL START CHAMFER" in spec.DRAWING_NOTES
    assert "MIDPLANE OFFSET FROM HEAD OD AXIS 0.00 +/-0.05" in spec.DRAWING_NOTES
    assert "HEAD OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )


@pytest.mark.parametrize("spec_name", ("hanger_screw_spec", "thumb_screw_spec"))
def test_long_reference_note_is_split_for_readable_rendering(spec_name: str) -> None:
    spec = importlib.import_module(spec_name)
    assert "THREAD GEOMETRY OMITTED IN VIEWS; SHANK OUTLINE REFERENCE ONLY." in (
        spec.DRAWING_NOTES
    )


def test_hanger_hex_head_is_controlled_to_thread_axis() -> None:
    spec = importlib.import_module("hanger_screw_spec")
    assert "HEX CENTER WITHIN DIA 0.10 OF THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )


def test_thumb_note_uses_short_lines_in_a_raised_lane() -> None:
    drawing = importlib.import_module("draw_thumb_screw")
    spec = importlib.import_module("thumb_screw_spec")
    assert drawing.RECIPE.note_xy == (0.020, 0.110)
    assert max(map(len, spec.DRAWING_NOTES.splitlines())) < 80


@pytest.mark.parametrize(
    "module_name",
    (
        "draw_bracket_screw",
        "draw_clamp_screw",
        "draw_fillister_screw",
        "draw_foot_screw",
        "draw_lag_screw",
        "draw_slotted_screw",
    ),
)
def test_custom_head_end_view_does_not_show_hidden_shank_circle(
    module_name: str,
) -> None:
    source = Path(importlib.import_module(module_name).__file__).read_text(
        encoding="utf-8"
    )
    assert "set_hidden_lines_removed(adapter, end)" in source
    assert "set_hidden_lines_visible(adapter, end)" not in source


@pytest.mark.parametrize(
    ("build_name", "spec_name"),
    (
        ("build_pen_set_screw", "pen_set_screw_spec"),
        ("build_thumb_screw", "thumb_screw_spec"),
    ),
)
def test_reeded_builder_uses_spec_groove_count(
    build_name: str, spec_name: str
) -> None:
    build = importlib.import_module(build_name)
    spec = importlib.import_module(spec_name)
    source = Path(build.__file__).read_text(encoding="utf-8")
    assert build.GROOVE_COUNT == spec.GROOVE_COUNT
    assert "groove_count=GROOVE_COUNT" in source
    head_name = "KNOB" if spec_name == "pen_set_screw_spec" else "HEAD"
    assert (
        f"{head_name} OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS"
        in spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
