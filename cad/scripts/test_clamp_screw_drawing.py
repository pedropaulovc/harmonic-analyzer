"""Offline contracts for the clamp-screw drawing.

A #8-32 machine screw after the 2026-09-02 blind machinist review: no
datums, frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md rules 3-5); the thread designation
is a leader on the shank, the head diameter leader ends at the rim, the slot
is dimensioned on the profile, the (REF) overall is stacked below the
under-head length so the prominent 28.00 no longer reads as the overall,
and the axis carries a centerline (rule 7); two lines of note (rule 6);
hidden lines on in the profile.
"""

from __future__ import annotations

from pathlib import Path

import build_clamp_screw as part
import clamp_screw_spec as spec
import draw_clamp_screw as drawing
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
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/clamp-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/clamp-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/clamp-screw_drawing.png")
    assert DRAWINGS_BY_NAME["clamp_screw"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert set(drawing.END_KEEP) == {"HeadDia"}
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg", "SlotWidth", "SlotDepth"}


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("clamp-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"#8-32' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert "ShankDia" not in drawing.SIDE_KEEP
    assert drawing.DIMENSION_CALLOUTS == {}


def test_lengths_and_slot_are_marked_model_dimensions() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "mark_dimensions=DRAWING_DIMENSIONS" in part_source
    assert "slot_width=SLOT_W" in part_source
    assert "slot_depth=SLOT_D" in part_source
    assert spec.DRAWING_DIMENSIONS["Head"] == {"HeadHt"}
    assert spec.DRAWING_DIMENSIONS["Shank"] == {"ShankLg"}
    assert spec.DRAWING_DIMENSIONS["DriverSlotProfile"] == {"SlotWidth"}
    assert spec.DRAWING_DIMENSIONS["DriverSlot"] == {"SlotDepth"}


def test_overall_is_a_conspicuous_reference_below_the_lengths() -> None:
    # Blind review: "28.00 can be mistaken for the overall; add (30.50) REF
    # while retaining the 28.00 under-head length".
    source = _source()
    assert "add_overall_reference(" in source
    assert 'orientation="horizontal"' in source
    assert 'entity_types=("EDGE", "EDGE")' in source
    assert drawing.OVERALL_END_POINTS_MM == (
        (0.0, -0.7 * spec.HEAD_DIA / 2.0, -spec.HEAD_H),
        (0.0, -0.7 * spec.SHANK_DIA / 2.0, spec.SHANK_LEN),
    )
    assert "ShankLg" in drawing.SIDE_KEEP
    assert drawing.OVERALL_TEXT_XY[1] < drawing.SIDE_KEEP["ShankLg"][1] - 0.012
    assert drawing.OVERALL_TEXT_XY[1] > 0.115 + 0.010  # above the note block


def test_view_annotations_follow_the_machinist() -> None:
    source = _source()
    assert "end_diameter_leaders_at_rim(" in source
    assert drawing.END_DIAMETERS == ("HeadDia",)
    assert "add_circle_center_mark(" in source
    assert "face_xy=SIDE_AXIS_FACE_XY" in source
    assert drawing.THREAD_LEADER_XY[1] > drawing.SIDE_CENTER[1]
    assert drawing.THREAD_NOTE_XY[0] < drawing.SIDE_CENTER[0]
    # The isometric sits right of the slot-width text on this long profile.
    assert drawing.ISO_CENTER == (0.335, 0.180)


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


def test_hidden_lines_stay_on_in_the_profile_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, side)" in source
    assert "set_hidden_lines_removed(adapter, end)" in source  # tiny end view
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert drawing.SHEET_SCALE == (4.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "mark_dimensions=DRAWING_DIMENSIONS" in source
    assert "drawing_properties=" in source
    import _config

    config = _config.parts("clamp-screw")
    assert config["number"] == "MHA-107"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 6
