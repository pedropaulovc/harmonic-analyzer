"""Offline contracts for the fillister-screw drawing.

A brass #4-40 machine screw after the 2026-09-02 blind machinist review: no
datums, frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md rules 3-5); the thread designation is
a leader on the shank, the head diameter leader ends at the rim, the slot is
dimensioned on the profile and the screw axis carries a centerline (rule 7);
two lines of note that say only where the thread runs and that the slot is
centred (rule 6); hidden lines on in the profile.
"""

from __future__ import annotations

from pathlib import Path

import build_fillister_screw as part
import draw_fillister_screw as drawing
import fillister_screw_spec as spec
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
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fillister-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fillister-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fillister-screw_drawing.png")
    assert DRAWINGS_BY_NAME["fillister_screw"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    # The head diameter is the ONLY end-view dimension; every length and the
    # slot ride the profile.
    assert set(drawing.END_KEEP) == {"HeadDia"}
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg", "SlotWidth", "SlotDepth"}


def test_catalog_is_the_single_source_of_the_thread() -> None:
    """The drawing must never invent a thread the part does not build."""
    catalog = fastener("fillister-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    # The designation rides the view as a leader to the shank silhouette,
    # sourced from the spec -- never a literal in the drawing, never repeated
    # in the notes, and the modeled thread-minor shank is never dimensioned.
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"#4-40' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert "ShankDia" not in drawing.SIDE_KEEP
    assert drawing.DIMENSION_CALLOUTS == {}


def test_lengths_and_slot_are_marked_model_dimensions() -> None:
    # The two lengths are the head/shank extrude-DEPTH model dims; the slot
    # width is the slot sketch dim and its depth the cut depth, all named by
    # the build and inserted on the profile, where the notch is visible.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in part_source
    assert "width_mm=SLOT_W" in part_source
    assert spec.DRAWING_DIMENSIONS["DriverSlotProfile"] == {"SlotWidth"}
    assert spec.DRAWING_DIMENSIONS["DriverSlot"] == {"SlotDepth"}
    # No explicit bands: the block's decimal places govern a plain screw.
    assert "set_dimension_symmetric_tolerance(" not in part_source
    assert "set_dimension_bilateral_tolerance(" not in part_source


def test_view_annotations_follow_the_machinist() -> None:
    source = _source()
    # Head diameter leader ends at the rim, never across the slot; the rim
    # gets a center mark and the profile its axis centerline.
    assert "end_diameter_leaders_at_rim(" in source
    assert drawing.END_DIAMETERS == ("HeadDia",)
    assert "add_circle_center_mark(" in source
    assert 'add_view_centerline(\n        adapter, side, face_xy=SIDE_AXIS_FACE_XY' in source
    # The thread leader lands on the shank silhouette, text clear of the head
    # dimension above the profile.
    assert drawing.THREAD_LEADER_XY[1] > drawing.SIDE_CENTER[1]
    assert drawing.THREAD_NOTE_XY[0] < drawing.SIDE_CENTER[0]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 2
    assert max(map(len, lines)) < 80
    assert lines[0] == "THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    assert lines[1] == "SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD."
    # Every size is a dimension, so the note never repeats one.
    for value in (spec.HEAD_DIA, spec.HEAD_H, spec.SHANK_LEN, spec.SLOT_W, spec.SLOT_D):
        assert f"{value:.2f}" not in notes, value
    for banned in BANNED_NOTE_PHRASES:
        assert banned not in notes, banned
    assert spec.END_VIEW_NOTE == "DRIVER-FACE VIEW"


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # policy rules 3-5: a machine screw is off the GD&T allowlist and nothing
    # runs on it.
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
    # The tiny head-end view keeps HLR on purpose: the shank-behind-head
    # circle would read as a hole.
    assert "set_hidden_lines_removed(adapter, end)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert drawing.SHEET_SCALE == (8.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("fillister-screw")
    assert config["number"] == "MHA-030"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 27
