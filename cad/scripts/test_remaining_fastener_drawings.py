"""Offline contracts for the six remaining PR 358 fastener sheets.

These sheets follow cad/docs/drawing-simplicity-policy.md after the
2026-09-02 blind machinist review: no datums or frames on any screw, one
GROUND roughness symbol on the cone pivot screw's running shoulder, every
head and shank size on a view as a native marked dimension, the thread
designation leadered to the shank (never a note line, never the modeled
thread-minor cylinder dimensioned), the (REF) overall stacked outside the
chained lengths, and notes of at most four short lines that carry only what
the views cannot say.
"""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


@dataclass(frozen=True)
class Case:
    part_name: str
    module_name: str
    spec_name: str
    build_name: str
    shank_dim: str
    dimension_callouts: dict[str, str]


CASES = (
    Case(
        "cone-pivot-screw",
        "draw_cone_pivot_screw",
        "cone_pivot_screw_spec",
        "build_cone_pivot_screw",
        "ThreadSolidDiaDim",
        {},
    ),
    Case(
        "cone-tip-pinch-screw",
        "draw_cone_tip_pinch_screw",
        "cone_tip_pinch_screw_spec",
        "build_cone_tip_pinch_screw",
        "ShankDiaDim",
        {},
    ),
    Case(
        "hanger-screw",
        "draw_hanger_screw",
        "hanger_screw_spec",
        "build_hanger_screw",
        "ShankDia",
        {},
    ),
    Case(
        "pen-set-screw",
        "draw_pen_set_screw",
        "pen_set_screw_spec",
        "build_pen_set_screw",
        "ShankDia",
        {"KnobDia": "BEFORE REEDING"},
    ),
    Case(
        "swing-stop-screw",
        "draw_swing_stop_screw",
        "swing_stop_screw_spec",
        "build_swing_stop_screw",
        "ShankDiaDim",
        {},
    ),
    Case(
        "thumb-screw",
        "draw_thumb_screw",
        "thumb_screw_spec",
        "build_thumb_screw",
        "ShankDia",
        {"HeadDia": "BEFORE REEDING"},
    ),
)
CASES_BY_NAME = {case.part_name: case for case in CASES}

# The five formerly note-only sheets: each side view carries the head
# height/length and the under-head length as the extrude-depth model dims
# (feature -> dim name); the shank diameter is never dimensioned.
SIDE_LENGTH_MARKS = {
    "cone_tip_pinch_screw_spec": {"Head": "HeadHt", "Shank": "ShankLg"},
    "hanger_screw_spec": {"HexHead": "HeadHt", "Shank": "ShankLg"},
    "pen_set_screw_spec": {"Knob": "KnobLg", "Shank": "ShankLg"},
    "swing_stop_screw_spec": {"Head": "HeadHt", "Shank": "ShankLg"},
    "thumb_screw_spec": {"Head": "HeadLg", "Shank": "ShankLg"},
}

# The sheet's top frame rule (memory/drawing-sheet-zone-border.md).
TOP_RULE_Y = 0.2665

THREAD_LINE = "THREADED TO THE {head}; LAST 2 PITCHES MAY BE INCOMPLETE."
SLOT_LINE = "SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD."


def _all_kept(drawing) -> set[str]:
    return (
        set(drawing.END_KEEP)
        | set(getattr(drawing, "SIDE_KEEP", {}))
        | set(getattr(drawing, "SLOT_KEEP", {}))
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
    assert _all_kept(drawing) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert drawing.RECIPE.end_keep is drawing.END_KEEP
    assert drawing.RECIPE.side_keep is drawing.SIDE_KEEP
    assert drawing.RECIPE.scale == drawing.SHEET_SCALE
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_face_xy == drawing.SIDE_AXIS_FACE_XY


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_catalog_thread_rides_the_view_as_a_leader(case: Case) -> None:
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    part = importlib.import_module(case.build_name)
    catalog = fastener(case.part_name)
    source = Path(drawing.__file__).read_text(encoding="utf-8")

    assert spec.THREAD == catalog.thread
    # The class is the title block's (blind review over-specification).
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    # The designation is a leader to the shank silhouette through the
    # recipe's decorate hook, sourced from the spec -- never a literal in the
    # drawing, never a note line, never the modeled thread-minor cylinder
    # dimensioned as if it were a turned size.
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert "silhouette_xy=THREAD_LEADER_XY" in source
    assert f'"{catalog.thread}' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert case.shank_dim not in _all_kept(drawing)
    assert drawing.DIMENSION_CALLOUTS == case.dimension_callouts
    assert "THREAD NOT MODELED" not in spec.DRAWING_NOTES
    assert "REFERENCE ONLY" not in spec.DRAWING_NOTES
    assert "PERPENDICULAR" not in spec.DRAWING_NOTES
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
    head = "KNOB" if case.part_name == "pen-set-screw" else "HEAD"
    assert spec.DRAWING_NOTES.split("\n")[0] == THREAD_LINE.format(head=head)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_title_block_properties_are_complete(case: Case) -> None:
    config = _config.parts(case.part_name)
    assert config["number"].startswith("MHA-")
    assert config["material"] == config["material_specification"]
    assert config["finish"].strip()
    assert int(config["quantity"]) >= 1


def test_assembly_fastener_quantities_are_pinned() -> None:
    assert int(_config.parts("foot-screw")["quantity"]) == 3
    # 22 on the paper-drive platen (4 clip + 10 guide + 8 lock) + 4 holding the
    # maker's nameplate to the base (build_frame_assembly).
    assert int(_config.parts("fillister-screw")["quantity"]) == 26


@pytest.mark.parametrize(
    "spec_name",
    (
        "bracket_screw_spec",
        "clamp_screw_spec",
        "cone_tip_pinch_screw_spec",
        "fillister_screw_spec",
        "foot_screw_spec",
        "hanger_screw_spec",
        "lag_screw_spec",
        "pen_set_screw_spec",
        "slotted_screw_spec",
        "swing_stop_screw_spec",
        "thumb_screw_spec",
    ),
)
def test_dimensioned_sheets_do_not_duplicate_underhead_length_note(
    spec_name: str,
) -> None:
    # The under-head length is a marked model dimension on every sheet, so
    # the thread line says only how far the thread runs -- no size, no
    # designation (that is the leader's), and runout is permitted rather
    # than an impossible full form against the shoulder.
    spec = importlib.import_module(spec_name)
    head = "KNOB" if spec_name == "pen_set_screw_spec" else "HEAD"
    assert "ShankLg" in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert "UNDER HEAD" not in spec.DRAWING_NOTES
    assert "UNDER KNOB" not in spec.DRAWING_NOTES
    assert f"{spec.SHANK_LEN:.2f}" not in spec.DRAWING_NOTES
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert spec.DRAWING_NOTES.split("\n")[0] == THREAD_LINE.format(head=head)


@pytest.mark.parametrize("spec_name", sorted(SIDE_LENGTH_MARKS))
def test_side_views_carry_head_and_shank_lengths_as_marked_depths(
    spec_name: str,
) -> None:
    # Policy rule 6 / blind machinist review: the head height and under-head
    # length are extrude DEPTH dims the build names and marks (the vertical
    # profiles cannot point-select the edge-on shoulder/tip), the spec is the
    # single source of the marked set, and the drawing keeps them in its side
    # view.  The build script's marks come straight from DRAWING_DIMENSIONS.
    spec = importlib.import_module(spec_name)
    stem = spec_name.removesuffix("_spec")
    build = importlib.import_module(f"build_{stem}")
    drawing = importlib.import_module(f"draw_{stem}")
    build_source = Path(build.__file__).read_text(encoding="utf-8")
    for feature, dim in SIDE_LENGTH_MARKS[spec_name].items():
        assert spec.DRAWING_DIMENSIONS[feature] == {dim}, (feature, dim)
        assert f'name_dimensions(adapter, "{feature}", ["{dim}"])' in build_source
        assert dim in drawing.SIDE_KEEP, dim
    assert build.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert "mark_dimensions_for_drawing(adapter, feature_name, dimension_names)" in (
        build_source
    )
    # No size survives in the notes once it is on a view.
    for value in (spec.SHANK_LEN, spec.SHANK_DIA):
        assert f"{value:.2f}" not in spec.DRAWING_NOTES, value
    for banned in (" DIA X ", " HIGH.", " LONG,", "ACROSS FLATS", "UNDER "):
        assert banned not in spec.DRAWING_NOTES, banned


@pytest.mark.parametrize(
    ("spec_name", "build_name"),
    (
        ("cone_pivot_screw_spec", "build_cone_pivot_screw"),
        ("cone_tip_pinch_screw_spec", "build_cone_tip_pinch_screw"),
        ("swing_stop_screw_spec", "build_swing_stop_screw"),
    ),
)
def test_slotted_screw_slot_is_dimensioned_on_the_slot_profile_view(
    spec_name: str, build_name: str
) -> None:
    # Blind review blocker on every slotted head: the slot had a size in a
    # note and no location.  Now the slot width (sketch dim) and depth (cut
    # depth) are marked model dims on a slot-profile (*Right) view where the
    # notch is visible, and the note carries only the centring fact.
    spec = importlib.import_module(spec_name)
    stem = spec_name.removesuffix("_spec")
    drawing = importlib.import_module(f"draw_{stem}")
    build_source = Path(importlib.import_module(build_name).__file__).read_text(
        encoding="utf-8"
    )
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert spec.SLOT_W > 0
    assert spec.SLOT_D > 0
    assert spec.DRAWING_DIMENSIONS["SlotProfile"] == {"SlotWDim"}
    assert spec.DRAWING_DIMENSIONS["DriverSlot"] == {"SlotDepth"}
    assert set(drawing.SLOT_KEEP) == {"SlotWDim", "SlotDepth"}
    assert f"{spec.SLOT_W:.2f}" not in spec.DRAWING_NOTES
    assert f"{spec.SLOT_D:.2f}" not in spec.DRAWING_NOTES
    assert "SLOT CENTERED ON THE HEAD AXIS" in spec.DRAWING_NOTES
    assert "SLOT_W," in build_source
    assert "SLOT_D," in build_source
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in build_source
    assert 'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER' in drawing_source
    assert 'keep=SLOT_KEEP, view_label="slot profile"' in drawing_source
    assert "set_hidden_lines_visible(adapter, right)" in drawing_source
    assert "face_xy=SLOT_AXIS_FACE_XY" in drawing_source


@pytest.mark.parametrize(
    "module_name",
    ("draw_cone_tip_pinch_screw", "draw_swing_stop_screw", "draw_hanger_screw",
     "draw_pen_set_screw", "draw_thumb_screw"),
)
def test_end_view_leaders_end_at_the_rim(module_name: str) -> None:
    # Blind review clarity finding on every round head: the diameter line
    # crossed both slot edges.  Round heads end the leader at the rim and get
    # a center mark; the hex head has no rim to mark.
    drawing = importlib.import_module(module_name)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    if module_name == "draw_hanger_screw":
        assert drawing.END_KEEP == {}
        assert "end_diameter_leaders_at_rim(" not in source
        return
    assert "end_diameter_leaders_at_rim(" in source
    assert set(drawing.END_DIAMETERS) == set(drawing.END_KEEP)
    if module_name in ("draw_cone_tip_pinch_screw", "draw_swing_stop_screw"):
        assert "add_circle_center_mark(" in source
        assert drawing.RECIPE.end_center_mark == "not_applicable"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_overall_is_a_conspicuous_reference_outside_the_chain(case: Case) -> None:
    # Blind review on every one of these sheets: "no conspicuous overall".
    # The overall is a drawing-native dimension between the two end faces
    # (model points projected into the view), parenthesised as ASME
    # reference, pinned to the axis direction and stacked outside the
    # chained lengths.
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_overall_reference(" in source
    assert "end_points_mm=OVERALL_END_POINTS_MM" in source
    assert "text_xy=OVERALL_TEXT_XY" in source
    ends = drawing.OVERALL_END_POINTS_MM
    axis = {"hanger-screw": 2, "pen-set-screw": 0, "thumb-screw": 0}.get(case.part_name, 1)
    span = abs(ends[0][axis] - ends[1][axis])
    if case.part_name == "cone-pivot-screw":
        assert span == pytest.approx(spec.HEAD_T + spec.UNDERHEAD_LEN)
        assert 'orientation="vertical"' in source
        # Left of the profile (the right side holds the lengths and the
        # fillet callout), text clear of the thread-end view.
        assert drawing.OVERALL_DIM_X < drawing.SIDE_CENTER[0] - 0.060
        assert drawing.OVERALL_TEXT_XY[0] - 0.010 > drawing.END_CENTER[0] + spec.HEAD_DIA / 2.0 * drawing._S
        return
    head_len_attr = {
        "pen-set-screw": "KNOB_LENGTH",
        "thumb-screw": "HEAD_LENGTH",
        "hanger-screw": "HEAD_H",
        "cone-tip-pinch-screw": "HEAD_T",
        "swing-stop-screw": "HEAD_T",
    }[case.part_name]
    assert span == pytest.approx(getattr(spec, head_len_attr) + spec.SHANK_LEN)
    if axis == 1:
        # Vertical profiles: the lengths chain in an inner column, the
        # overall in the outer one, both clear of the slot-profile view.
        assert 'orientation="vertical"' in source
        assert {xy[0] for xy in drawing.SIDE_KEEP.values()} == {drawing.SIDE_DIM_X}
        assert drawing.OVERALL_DIM_X - drawing.SIDE_DIM_X >= 0.018
        head_dia = spec.HEAD_DIA
        assert drawing.OVERALL_TEXT_XY[0] + 0.010 < drawing.RIGHT_CENTER[0] - head_dia / 2.0 * drawing._S
        return
    # Horizontal profiles: the overall stacks above the length row, under
    # the sheet's top rule.
    assert 'orientation="horizontal"' in source
    assert drawing.OVERALL_TEXT_XY[1] >= drawing._ROW_ABOVE_Y + 0.014
    assert drawing.OVERALL_TEXT_XY[1] + 0.004 < TOP_RULE_Y
    if case.part_name == "hanger-screw":
        assert 'entity_types=("VERTEX", "EDGE")' in source
        assert ends[0] == (spec.HEAD_AF / (2.0 * 3.0**0.5), spec.HEAD_AF / 2.0, spec.HEAD_H)
    else:
        assert 'entity_types=("EDGE", "EDGE")' in source


def test_swing_stop_overall_uses_the_true_model_extents() -> None:
    # The swing stop is authored with its origin at the base top, so the
    # overall's model picks come from the spec's proud/embedded split, not
    # the drawing's bbox-relative sheet math.
    spec = importlib.import_module("swing_stop_screw_spec")
    drawing = importlib.import_module("draw_swing_stop_screw")
    build_source = Path(
        importlib.import_module("build_swing_stop_screw").__file__
    ).read_text(encoding="utf-8")
    assert spec.EMBED_LEN + spec.PROUD_LEN == spec.SHANK_LEN
    assert "EMBED_LEN = " not in build_source
    assert "PROUD_LEN = " not in build_source
    assert drawing.OVERALL_END_POINTS_MM[0][1] == spec.PROUD_LEN + spec.HEAD_T
    assert drawing.OVERALL_END_POINTS_MM[1][1] == -spec.EMBED_LEN


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
    # The full-form margin stays a spec-level sanity check, not a note.
    assert (
        spec.THREAD_TAIL_LEN
        - spec.THREAD_LENGTH_TOL
        - spec.THREAD_RUNOUT_PITCHES * spec.THREAD_PITCH
        - spec.DISTAL_CHAMFER
        >= spec.MIN_FULL_FORM
    )
    # The shoulder length sets the plate's running clearance: a practical
    # +-0.10 band (blind review: the +0.05/0 was unusually tight for an
    # unground axial length).
    assert spec.SHOULDER_LENGTH_TOL == 0.10
    assert (
        'set_dimension_symmetric_tolerance(\n        adapter, "Shoulder", "ShoulderLg", SHOULDER_LENGTH_TOL\n    )'
        in build_source
    )
    assert build_source.count("set_dimension_symmetric_tolerance(") == 1
    assert build_source.count("set_dimension_bilateral_tolerance(") == 1
    # No cosmetic thread: it drew a dashed cone at the shoulder/tail junction
    # (blind review blocker) and no thread lines.
    assert "InsertCosmeticThread3(" not in build_source
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert lines == [
        "SHOULDER GROUND TO SIZE; PIVOT RUNNING SURFACE.",
        "SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD; FLAT FLOOR.",
    ]
    # The thread-start chamfer and the under-head fillet are leadered
    # callouts on the side view, never note lines.
    assert spec.THREAD_CHAMFER_CALLOUT == f"C{spec.DISTAL_CHAMFER:.2f} THREAD START"
    assert spec.UNDERHEAD_FILLET_CALLOUT == f"R{spec.UNDERHEAD_FILLET_MAX:.2f} MAX FILLET"
    # policy rules 1, 3 and 6: no title-block override, no datum lore, no
    # acceptance limits that belong on a dimension, no thread/chamfer/fillet
    # prose the view now carries.
    for banned in (
        "DATUM",
        "TITLE-BLOCK",
        "MIN FULL-FORM",
        "RUNOUT",
        "FLOOR CORNERS",
        "MANDATORY",
        "DO NOT RELEASE",
        "THREAD LENGTH",
        "ON THE TAIL ONLY",
        "CHAMFER",
        "FILLET",
        spec.THREAD_DESIGNATION,
    ):
        assert banned not in notes, banned


def test_cone_pivot_tail_view_exposes_the_ground_shoulder() -> None:
    drawing = importlib.import_module("draw_cone_pivot_screw")
    spec = importlib.import_module("cone_pivot_screw_spec")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    build_source = Path(
        importlib.import_module("build_cone_pivot_screw").__file__
    ).read_text(encoding="utf-8")
    assert drawing.RECIPE.end_view == "*Bottom"
    assert drawing.RECIPE.side_center == (0.190, 0.170)
    # The end view carries nothing but the ground shoulder's roughness
    # symbol; the explanatory circle prose is gone (blind review).
    assert spec.END_VIEW_NOTE == "THREAD-END VIEW"
    assert drawing.END_KEEP == {}
    # Both turned diameters and every length on the longitudinal view.
    assert set(drawing.SIDE_KEEP) == {
        "HeadDiaDim",
        "HeadHt",
        "ShoulderLg",
        "ShoulderDiaDim",
        "ThreadLg",
    }
    assert set(drawing.SLOT_KEEP) == {"SlotWDim", "SlotDepth"}
    assert drawing.SIDE_DIMENSION_CALLOUTS == {}
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_face_xy == drawing.SIDE_AXIS_FACE_XY
    # Leadered callouts: the thread designation and chamfer at the tail, the
    # fillet under the head.
    assert 'label="tail thread designation"' in drawing_source
    assert "text=THREAD_CHAMFER_CALLOUT" in drawing_source
    assert "text=UNDERHEAD_FILLET_CALLOUT" in drawing_source
    assert drawing_source.count("add_attached_note(") == 2
    # The chamfer leader lands on the tail's end-face edge right of the
    # axis, clear of the overall's witness line running left from it.
    assert drawing.CHAMFER_LEADER_XY[0] > drawing.SIDE_CENTER[0]
    assert drawing.CHAMFER_LEADER_XY[1] == drawing._TIP_Y
    # policy rules 3-5: no datum, no frames; the ONE roughness symbol marks
    # the ground shoulder, the pivot's running surface.
    assert drawing_source.count("add_datum_feature(") == 0
    assert drawing_source.count("add_feature_control_frame(") == 0
    assert drawing_source.count("set_basic_dimension(") == 0
    assert drawing_source.count("add_surface_finish(") == 1
    assert 'label="ground shoulder finish"' in drawing_source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert len(spec.SURFACE_FINISHES) == 1
    assert "import_cosmetic_threads(" not in drawing_source
    assert 'place_view(adapter, str(SOURCE), "*Right"' in drawing_source
    # Hidden lines ON in the slot-profile view (policy rule 7).
    assert "set_hidden_lines_visible(adapter, right)" in drawing_source
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


def test_cone_tip_pinch_sheet_dimensions_the_head_once_and_keeps_a_flat_end() -> None:
    drawing = importlib.import_module("draw_cone_tip_pinch_screw")
    spec = importlib.import_module("cone_tip_pinch_screw_spec")
    # The head diameter lives on the driver-face view ONLY; the side view
    # carries the lengths, the slot-profile view the slot, so no size is
    # printed twice and none rides a note.
    assert set(drawing.END_KEEP) == {"HeadDiaDim"}
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg"}
    assert set(drawing.SLOT_KEEP) == {"SlotWDim", "SlotDepth"}
    assert spec.DRAWING_DIMENSIONS == {
        "HeadProfile": {"HeadDiaDim"},
        "Head": {"HeadHt"},
        "Shank": {"ShankLg"},
        "SlotProfile": {"SlotWDim"},
        "DriverSlot": {"SlotDepth"},
    }
    assert drawing.RECIPE.side_center == (0.190, 0.190)
    assert drawing.RIGHT_CENTER == (0.285, 0.190)
    # The flat end is the title's job ("Flat-End Pinch Screw"), not a note's.
    notes = spec.DRAWING_NOTES
    assert notes.split("\n") == [THREAD_LINE.format(head="HEAD"), SLOT_LINE]
    assert f"{spec.HEAD_DIA:.2f}" not in notes
    assert f"{spec.HEAD_T:.2f}" not in notes
    assert "CONICAL" not in notes
    assert "MIDPLANE" not in notes
    assert spec.END_VIEW_NOTE == "DRIVER-FACE VIEW"


@pytest.mark.parametrize("spec_name", tuple(case.spec_name for case in CASES))
def test_notes_are_short_lines_with_no_cad_commentary(spec_name: str) -> None:
    spec = importlib.import_module(spec_name)
    lines = spec.DRAWING_NOTES.split("\n")
    assert 1 <= len(lines) <= 4
    assert max(map(len, lines)) < 80
    assert "THREAD NOT MODELED" not in spec.DRAWING_NOTES
    assert "REFERENCE ONLY" not in spec.DRAWING_NOTES


def test_hanger_hex_across_flats_is_a_native_end_view_dimension() -> None:
    # The hex head is a polygon with no marked diameter, so its across-flats
    # is a drawing-native vertical between the two flats on the hex-head view
    # (the hexagon sits flats top and bottom in *Front); its height is the
    # marked extrude depth.  "HEX HEAD, WRENCH DRIVEN" restated the drawn
    # head (blind review), so the note keeps only the thread extent.
    drawing = importlib.import_module("draw_hanger_screw")
    spec = importlib.import_module("hanger_screw_spec")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    half = spec.HEAD_AF / 2.0 * drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.END_FLAT_PICKS == (
        (drawing.END_CENTER[0], drawing.END_CENTER[1] + half),
        (drawing.END_CENTER[0], drawing.END_CENTER[1] - half),
    )
    assert drawing.END_FLATS_TEXT_XY[0] < drawing.END_CENTER[0] - half
    assert 'label="hex across-flats"' in source
    assert 'orientation="vertical"' in source
    assert source.count("add_edge_dimension(") == 1
    assert drawing.END_KEEP == {}
    assert spec.DRAWING_NOTES == THREAD_LINE.format(head="HEAD")
    assert spec.END_VIEW_NOTE == "HEX-HEAD VIEW"
    assert "WRENCH DRIVEN" not in spec.DRAWING_NOTES
    assert "ACROSS FLATS" not in spec.DRAWING_NOTES
    assert "WITHIN" not in spec.DRAWING_NOTES
    assert "PERPENDICULAR" not in spec.DRAWING_NOTES


@pytest.mark.parametrize(
    "module_name", ("draw_hanger_screw", "draw_pen_set_screw", "draw_thumb_screw")
)
def test_horizontal_axis_sheets_leave_room_for_the_thread_text(module_name: str) -> None:
    # The thread designation is leadered to the shank's lower outline with
    # its text below the profile; the isometric sits far enough right that
    # neither the text nor the (REF) overall's witness line at the tip runs
    # into it.
    drawing = importlib.import_module(module_name)
    assert drawing.ISO_CENTER[0] >= 0.325
    assert drawing.RECIPE.iso_center == drawing.ISO_CENTER
    assert drawing.THREAD_LEADER_XY[1] < drawing.SIDE_CENTER[1]
    assert drawing.THREAD_NOTE_XY[1] < drawing.THREAD_LEADER_XY[1]
    assert drawing.THREAD_NOTE_XY[0] < drawing.ISO_CENTER[0] - 0.060
    # The lengths ride one row above the profile, both off the shoulder.
    assert len({xy[1] for xy in drawing.SIDE_KEEP.values()}) == 1
    assert drawing._ROW_ABOVE_Y > drawing.SIDE_CENTER[1]


def test_thumb_note_uses_short_lines_in_a_raised_lane() -> None:
    drawing = importlib.import_module("draw_thumb_screw")
    spec = importlib.import_module("thumb_screw_spec")
    assert drawing.RECIPE.note_xy == (0.020, 0.110)
    assert max(map(len, spec.DRAWING_NOTES.splitlines())) < 80


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
    length = spec.KNOB_LENGTH if head_name == "KNOB" else spec.HEAD_LENGTH
    dia = spec.KNOB_DIA if head_name == "KNOB" else spec.HEAD_DIA
    # The head length and diameter are marked dims (the diameter reads
    # "BEFORE REEDING"), so the reeding lines carry the groove form and the
    # fact that a grip is not gauged -- the blind review's blocker was the
    # title-block .XX band putting a negative lower limit on a 0.50 groove.
    lines = spec.DRAWING_NOTES.split("\n")
    assert lines == [
        THREAD_LINE.format(head=head_name),
        f"{head_name} REEDED: {spec.GROOVE_COUNT}X EQUALLY SPACED AXIAL GROOVES, "
        "R0.50 BALL NOSE 0.50 DEEP.",
        "GROOVES ARE A GRIP; RADIUS AND DEPTH NOT GAUGED.",
    ]
    assert spec.GROOVE_DIA == 1.0
    assert f"{length:.2f} LONG" not in spec.DRAWING_NOTES
    assert f"{dia:.2f}" not in spec.DRAWING_NOTES
    assert "RUNOUT" not in spec.DRAWING_NOTES
    # The end view looks from the shank tip toward the head, and says so.
    assert spec.END_VIEW_NOTE == "VIEW FROM SHANK END"
    # The shank is an offset-start extrude off the head's outer face, so its
    # depth dim IS the under-head length rather than head + shank.
    assert "extrude_at_offset(adapter, SHANK_LEN, " in source
    assert "ShankExtent" not in source
