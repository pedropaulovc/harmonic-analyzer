"""Offline contracts for the six remaining PR 358 fastener sheets.

These sheets follow cad/docs/drawing-simplicity-policy.md: no datums or
frames on any screw, one GROUND roughness symbol on the cone pivot screw's
running shoulder, every head and shank size on a view as a native marked
dimension (rule 6: a note is never a dimension), and notes of at most four
short lines.
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
        thread_on_dimension=True,
    ),
    Case(
        "hanger-screw",
        "draw_hanger_screw",
        "hanger_screw_spec",
        "build_hanger_screw",
        "ShankDia",
        thread_on_dimension=True,
    ),
    Case(
        "pen-set-screw",
        "draw_pen_set_screw",
        "pen_set_screw_spec",
        "build_pen_set_screw",
        "ShankDia",
        thread_on_dimension=True,
    ),
    Case(
        "swing-stop-screw",
        "draw_swing_stop_screw",
        "swing_stop_screw_spec",
        "build_swing_stop_screw",
        "ShankDiaDim",
        thread_on_dimension=True,
    ),
    Case(
        "thumb-screw",
        "draw_thumb_screw",
        "thumb_screw_spec",
        "build_thumb_screw",
        "ShankDia",
        thread_on_dimension=True,
    ),
)

# The five formerly note-only sheets: each side view now carries the head
# height/length and the under-head length as the extrude-depth model dims
# (feature -> dim name), plus the shank diameter relabelled with the thread.
SIDE_LENGTH_MARKS = {
    "cone_tip_pinch_screw_spec": {"Head": "HeadHt", "Shank": "ShankLg"},
    "hanger_screw_spec": {"HexHead": "HeadHt", "Shank": "ShankLg"},
    "pen_set_screw_spec": {"Knob": "KnobLg", "Shank": "ShankLg"},
    "swing_stop_screw_spec": {"Head": "HeadHt", "Shank": "ShankLg"},
    "thumb_screw_spec": {"Head": "HeadLg", "Shank": "ShankLg"},
}


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
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    if case.thread_on_dimension:
        # The marked shank Ø is the modeled thread MINOR, so the side view
        # relabels it with the catalog designation (the fillister pattern)
        # through the recipe's decorate hook, never a bare diameter.
        assert case.shank_dim in drawing.SIDE_KEEP
        assert drawing.SIDE_DIMENSION_TEXT == {case.shank_dim: spec.THREAD_DESIGNATION}
        assert drawing.RECIPE.decorate is drawing._decorate
        assert drawing.RECIPE.side_keep is drawing.SIDE_KEEP
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        assert "label_shank_thread(" in source
        assert "dimensions=SIDE_DIMENSION_TEXT" in source
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
    assert "THREADED TO THE" in spec.DRAWING_NOTES
    assert "PERPENDICULAR" not in spec.DRAWING_NOTES


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
    spec = importlib.import_module(spec_name)
    head = "KNOB" if spec_name == "pen_set_screw_spec" else "HEAD"
    assert "ShankLg" in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert "UNDER HEAD" not in spec.DRAWING_NOTES
    assert "UNDER KNOB" not in spec.DRAWING_NOTES
    assert f"{spec.SHANK_LEN:.2f}" not in spec.DRAWING_NOTES
    assert f"{spec.THREAD_DESIGNATION} THREADED TO THE {head}; LAST 2 PITCHES MAY BE INCOMPLETE." in spec.DRAWING_NOTES


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
        # The slot is dimensioned (bands on the model dims), so the note
        # never repeats its size.
        assert spec.DRAWING_DIMENSIONS["SlotProfile"] == {"SlotWDim"}
        assert spec.DRAWING_DIMENSIONS["DriverSlot"] == {"SlotDepth"}
        assert f"{spec.SLOT_W:.2f}" not in spec.DRAWING_NOTES
    else:
        assert f"SLOT {spec.SLOT_W:.2f} WIDE X {spec.SLOT_D:.2f} DEEP" in (
            spec.DRAWING_NOTES
        )
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
    # The full-form margin stays a spec-level sanity check, not a note.
    assert (
        spec.THREAD_TAIL_LEN
        - spec.THREAD_LENGTH_TOL
        - spec.THREAD_RUNOUT_PITCHES * spec.THREAD_PITCH
        - spec.DISTAL_CHAMFER
        >= spec.MIN_FULL_FORM
    )
    notes = spec.DRAWING_NOTES
    assert notes.split("\n")[0] == f"{spec.THREAD_DESIGNATION} ON THE TAIL ONLY; SHOULDER PLAIN."
    assert "SHOULDER GROUND TO SIZE" in notes
    assert "SLOT FULL WIDTH OF HEAD" in notes
    assert f"THREAD START CHAMFER C{spec.DISTAL_CHAMFER:.2f}" in notes
    assert "UNDERHEAD FILLET R0.25 MAX" in notes
    # policy rules 1, 3 and 6: no title-block override, no datum lore, no
    # acceptance limits that belong on a dimension.
    for banned in (
        "DATUM",
        "TITLE-BLOCK",
        "MIN FULL-FORM",
        "RUNOUT",
        "FLOOR CORNERS",
        "MANDATORY",
        "DO NOT RELEASE",
        "THREAD LENGTH 8.00",
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
    assert f"INNER CIRCLE = {spec.THREAD} EXTERNAL THREAD" in spec.END_VIEW_NOTE
    assert "MIDDLE CIRCLE = GROUND SHOULDER OD" in spec.END_VIEW_NOTE
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShoulderLg", "ThreadLg"}
    assert set(drawing.SLOT_KEEP) == {"SlotWDim", "SlotDepth"}
    assert drawing.SIDE_DIMENSION_CALLOUTS["ThreadLg"] == spec.THREAD_DESIGNATION
    assert '"1/4-20' not in drawing_source
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_face_xy == (0.190, 0.145)
    # policy rules 3-5: no datum, no frames; the ONE roughness symbol marks
    # the ground shoulder, the pivot's running surface.
    assert drawing_source.count("add_datum_feature(") == 0
    assert drawing_source.count("add_feature_control_frame(") == 0
    assert drawing_source.count("set_basic_dimension(") == 0
    assert drawing_source.count("add_surface_finish(") == 1
    assert 'label="ground shoulder finish"' in drawing_source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert "import_cosmetic_threads(adapter, side)" in drawing_source
    assert 'place_view(adapter, str(SOURCE), "*Right"' in drawing_source
    # Hidden lines ON in the slot-profile view (policy rule 7).
    assert "set_hidden_lines_visible(adapter, right)" in drawing_source
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


def test_cone_tip_pinch_sheet_dimensions_the_head_once_and_keeps_a_flat_end() -> None:
    drawing = importlib.import_module("draw_cone_tip_pinch_screw")
    spec = importlib.import_module("cone_tip_pinch_screw_spec")
    # The head diameter lives on the driver-face view ONLY; the side view
    # carries the lengths and the thread, so no size is printed twice.
    assert set(drawing.END_KEEP) == {"HeadDiaDim"}
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg", "ShankDiaDim"}
    assert spec.DRAWING_DIMENSIONS == {
        "HeadProfile": {"HeadDiaDim"},
        "Head": {"HeadHt"},
        "ShankProfile": {"ShankDiaDim"},
        "Shank": {"ShankLg"},
    }
    assert drawing.RECIPE.side_center == (0.190, 0.190)
    assert drawing.RECIPE.end_center_mark == "required"
    # The head sizes are dimensions now; only the slot rides the note.  The
    # flat end is the title's job ("Flat-End Pinch Screw"), not a note's.
    notes = spec.DRAWING_NOTES
    assert f"SLOTTED HEAD; SLOT {spec.SLOT_W:.2f} WIDE X {spec.SLOT_D:.2f} DEEP" in notes
    assert f"{spec.HEAD_DIA:.2f}" not in notes
    assert f"{spec.HEAD_T:.2f}" not in notes
    assert "CONICAL" not in notes
    assert "MIDPLANE" not in notes


@pytest.mark.parametrize("spec_name", ("hanger_screw_spec", "thumb_screw_spec"))
def test_long_reference_note_is_split_for_readable_rendering(spec_name: str) -> None:
    spec = importlib.import_module(spec_name)
    assert "THREAD NOT MODELED; SHANK OUTLINE REFERENCE ONLY." in spec.DRAWING_NOTES


def test_hanger_hex_across_flats_is_a_native_end_view_dimension() -> None:
    # The hex head is a polygon with no marked diameter, so its across-flats
    # is a drawing-native vertical between the two flats on the hex-head view
    # (the hexagon sits flats top and bottom in *Front); its height is the
    # marked extrude depth.  The note keeps only the drive style.
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
    assert spec.DRAWING_NOTES.split("\n")[-1] == "HEX HEAD, WRENCH DRIVEN."
    assert "ACROSS FLATS" not in spec.DRAWING_NOTES
    assert "WITHIN" not in spec.DRAWING_NOTES
    assert "PERPENDICULAR" not in spec.DRAWING_NOTES


@pytest.mark.parametrize(
    "module_name", ("draw_hanger_screw", "draw_pen_set_screw", "draw_thumb_screw")
)
def test_horizontal_axis_sheets_leave_room_for_the_thread_text(module_name: str) -> None:
    # The thread designation hangs off the shank tip as a vertical linear Ø;
    # the recipe's usual iso centre (0.310) put the isometric's leftmost point
    # ~17 mm from the tip, less than the text is wide, so these sheets carry
    # the isometric further right.
    drawing = importlib.import_module(module_name)
    assert drawing.ISO_CENTER[0] >= 0.325
    assert drawing.RECIPE.iso_center == drawing.ISO_CENTER
    shank_dim = next(name for name in drawing.SIDE_KEEP if name.startswith("ShankDia"))
    assert drawing.SIDE_KEEP[shank_dim][0] > drawing.SIDE_CENTER[0]


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
    # The head length is the marked extrude depth now, so the reeding line
    # carries only the groove form.
    assert (
        f"{head_name} REEDED: {spec.GROOVE_COUNT}X R0.50 GROOVES 0.50 DEEP, "
        "EQUALLY SPACED." in spec.DRAWING_NOTES
    )
    assert f"{length:.2f} LONG" not in spec.DRAWING_NOTES
    assert f" THREADED TO THE {head_name}; LAST 2 PITCHES MAY BE INCOMPLETE." in spec.DRAWING_NOTES
    assert "RUNOUT" not in spec.DRAWING_NOTES
    # The shank is an offset-start extrude off the head's outer face, so its
    # depth dim IS the under-head length rather than head + shank.
    assert "extrude_at_offset(adapter, SHANK_LEN, " in source
    assert "ShankExtent" not in source
