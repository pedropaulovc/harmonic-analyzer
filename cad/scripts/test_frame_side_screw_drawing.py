"""Offline contracts for the frame-side-screw drawing.

A #10-24 cheese-head screw on the shared fastener recipe after the
2026-09-02 blind machinist review: no datums, frames, roughness symbols or
basic dimensions (cad/docs/drawing-simplicity-policy.md rules 3-5); the
thread designation is a leader on the shank (class left to the title
block), the head diameter leader ends at the rim, the slot is dimensioned
on a slot-profile view and both profiles carry the axis centerline
(rule 7); two lines of note (rule 6).
"""

from __future__ import annotations

from pathlib import Path

import build_frame_side_screw as part
import draw_frame_side_screw as drawing
import frame_side_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener

BANNED_NOTE_PHRASES = (
    "UOS",
    "DIMENSIONS IN",
    "+/-",
    "DATUM",
    "PERPENDICULAR",
    "RUNOUT",
    "ASME",
    "B18",
    "DEBURR",
    "BREAK SHARP",
    "TITLE BLOCK",
    "COMMERCIAL",
    "THREAD NOT MODELED",
    "REFERENCE ONLY",
    "WIDE X",
    "UNDER HEAD",
    "-2A",
)


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/frame-side-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/frame-side-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/frame-side-screw_drawing.png")
    assert DRAWINGS_BY_NAME["frame_side_screw"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.SLOT_KEEP) == set().union(*spec.SLOT_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) | set(drawing.SLOT_KEEP) == marked
    assert (
        spec.END_VIEW_DIMENSIONS.keys()
        | spec.SIDE_VIEW_DIMENSIONS.keys()
        | spec.SLOT_VIEW_DIMENSIONS.keys()
    ) == spec.DRAWING_DIMENSIONS.keys()
    assert drawing.RECIPE.end_keep is drawing.END_KEEP
    assert drawing.RECIPE.side_keep is drawing.SIDE_KEEP


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("frame-side-screw")
    assert spec.THREAD == catalog.thread == "#10-24"
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    # Blind review: "#10-24 UNC" -- the 2A class is the title block's.
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"#10-24' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert "ShankDia" not in drawing.SIDE_KEEP
    assert drawing.DIMENSION_CALLOUTS == {}


def test_contract_geometry_matches_the_top_frame_rederive() -> None:
    # Top-frame contract: #10-24 x 12.7 under-head, cheese head O7 x 3.
    assert spec.SHANK_LEN == 12.7
    assert spec.HEAD_DIA == 7.0
    assert spec.HEAD_H == 3.0


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    assert "side_keep=SIDE_KEEP" in _source()


def test_slot_is_dimensioned_where_the_notch_is_visible() -> None:
    # Blind review: the 1.40 width and 1.20 depth were note lines; they are
    # now the slot sketch dim and the cut depth on a slot-profile (*Right)
    # view the decorate hook adds to the recipe's three views.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in part_source
    assert "width_mm=SLOT_W" in part_source
    assert "depth_mm=SLOT_D" in part_source
    assert spec.SLOT_VIEW_DIMENSIONS == {
        "DriverSlotProfile": {"SlotWidth"},
        "DriverSlot": {"SlotDepth"},
    }
    source = _source()
    assert 'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER' in source
    assert 'keep=SLOT_KEEP, view_label="slot profile"' in source
    assert "set_hidden_lines_visible(adapter, right)" in source
    assert drawing.RIGHT_CENTER == (0.285, 0.190)


def test_view_annotations_follow_the_machinist() -> None:
    source = _source()
    assert drawing.RECIPE.decorate is drawing._decorate
    assert "end_diameter_leaders_at_rim(" in source
    assert drawing.END_DIAMETERS == ("HeadDia",)
    # The rim center mark is explicit (the recipe's auto marks only find
    # holes); the recipe's side centerline plus the slot-profile's.
    assert drawing.RECIPE.end_center_mark == "not_applicable"
    assert "add_circle_center_mark(" in source
    assert drawing.RECIPE.side_centerline_face_xy == drawing.SIDE_AXIS_FACE_XY
    assert "face_xy=SLOT_AXIS_FACE_XY" in source
    assert drawing.THREAD_NOTE_XY[0] < drawing.SIDE_CENTER[0]
    assert all(xy[0] > drawing.SIDE_CENTER[0] for xy in drawing.SIDE_KEEP.values())


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 2
    assert max(map(len, lines)) < 80
    assert lines[0] == "THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    assert lines[1] == "SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD."
    for value in (spec.HEAD_DIA, spec.HEAD_H, spec.SHANK_LEN, spec.SLOT_W, spec.SLOT_D):
        assert f"{value:.2f}" not in notes, value
    for banned in BANNED_NOTE_PHRASES:
        assert banned not in notes, banned
    assert spec.END_VIEW_NOTE == "DRIVER-FACE VIEW"


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "SURFACE_FINISHES")
    # The view display (HLR on the tiny end view, kept deliberately; hidden
    # lines on in the profile) is the shared recipe's.
    assert "build_fastener_sheet(" in source
    assert drawing.RECIPE.scale == drawing.SHEET_SCALE == (6.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("frame-side-screw")
    assert config["number"] == "MHA-117"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    # 4 in frame.SLDASM (corner bosses) + 2 in channel.SLDASM (the fulcrum
    # keepers' foot screws into the rail top face, 2026-08-02 remount).
    assert int(config["quantity"]) == 6
