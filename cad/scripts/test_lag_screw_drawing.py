"""Offline contracts for the lag-screw drawing.

A 9/16-12 black-steel hold-down screw after the 2026-09-02 blind machinist
review: no datums, frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md rules 3-5); the thread designation
is a leader on the shank, the head diameter leader ends at the rim, the slot
is dimensioned on the slot-profile view, the (REF) overall stands outside
the chained lengths so the conspicuous 63.00 reads as the under-head
length, and both profiles carry the axis centerline (rule 7); two lines of
note (rule 6); hidden lines on in both profiles.
"""

from __future__ import annotations

from pathlib import Path

import build_lag_screw as part
import draw_lag_screw as drawing
import lag_screw_spec as spec
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
)


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lag-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lag-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lag-screw_drawing.png")
    assert DRAWINGS_BY_NAME["lag_screw"].script == Path(drawing.__file__).resolve()


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


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("lag-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"9/16-12' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert "ShankDia" not in drawing.SIDE_KEEP
    assert drawing.DIMENSION_CALLOUTS == {}


def test_head_end_cluster_is_clear_of_the_left_zone_border() -> None:
    assert drawing.END_CENTER == (0.085, 0.180)
    assert drawing.END_DIM_X == 0.043
    assert {xy[0] for xy in drawing.END_KEEP.values()} == {drawing.END_DIM_X}
    assert abs(drawing.END_CENTER[0] - drawing.END_DIM_X - 0.042) < 1e-12


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    assert 'keep=SIDE_KEEP, view_label="side"' in _source()


def test_overall_is_a_conspicuous_reference_outside_the_chain() -> None:
    # Blind review: "63.00 can read as the overall; add (69.00) REF".  The
    # two lengths chain in an inner column, the overall stands outside them
    # as a drawing-native vertical between the driver face and the tip
    # (model points on the right half of each end face), and the outer text
    # still clears the slot-profile view.
    source = _source()
    assert "add_overall_reference(" in source
    assert 'orientation="vertical"' in source
    assert 'entity_types=("EDGE", "EDGE")' in source
    assert drawing.OVERALL_END_POINTS_MM == (
        (0.7 * spec.HEAD_DIA / 2.0, -spec.HEAD_H, 0.0),
        (0.7 * spec.SHANK_DIA / 2.0, spec.SHANK_LEN, 0.0),
    )
    assert {xy[0] for xy in drawing.SIDE_KEEP.values()} == {drawing.SIDE_DIM_X}
    assert drawing.OVERALL_DIM_X - drawing.SIDE_DIM_X >= 0.018
    slot_view_left = drawing.RIGHT_CENTER[0] - spec.HEAD_DIA / 2.0 * drawing._S
    assert drawing.OVERALL_TEXT_XY[0] + 0.010 < slot_view_left


def test_slot_is_dimensioned_where_the_notch_is_visible() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in part_source
    assert "width_mm=SLOT_W" in part_source
    assert spec.SLOT_VIEW_DIMENSIONS == {
        "DriverSlotProfile": {"SlotWidth"},
        "DriverSlot": {"SlotDepth"},
    }
    source = _source()
    assert 'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER' in source
    assert 'keep=SLOT_KEEP, view_label="slot profile"' in source
    # Head DOWN: the driver face is seen from below and the slot sits under
    # the head.
    assert 'place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER' in source
    assert drawing.SLOT_KEEP["SlotWidth"][1] < drawing.SIDE_CENTER[1]


def test_view_annotations_follow_the_machinist() -> None:
    source = _source()
    assert "end_diameter_leaders_at_rim(" in source
    assert drawing.END_DIAMETERS == ("HeadDia",)
    assert "add_circle_center_mark(" in source
    assert source.count("add_view_centerline(") == 2
    assert "face_xy=SIDE_AXIS_FACE_XY" in source
    assert "face_xy=SLOT_AXIS_FACE_XY" in source
    assert drawing.THREAD_NOTE_XY[0] < drawing.SIDE_CENTER[0]


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


def test_hidden_lines_stay_on_in_the_profile_views() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, side)" in source
    assert "set_hidden_lines_visible(adapter, right)" in source
    assert "set_hidden_lines_removed(adapter, end)" in source  # tiny end view
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert drawing.SHEET_SCALE == (2.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lag-screw")
    assert config["number"] == "MHA-039"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 4
