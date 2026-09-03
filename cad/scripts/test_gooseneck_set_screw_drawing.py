"""Offline contracts for the gooseneck-set-screw drawing.

A 1/4-20 square-head set screw on the shared fastener recipe after the
2026-09-02 blind machinist review: no datums, frames, roughness symbols or
basic dimensions (cad/docs/drawing-simplicity-policy.md rules 3-5); the
thread designation is a leader on the shank (class left to the title
block), the across-flats is a marked dimension on the wrench-flats view and
the profile carries the axis centerline (rule 7); two lines of note that
say only where the thread runs and the head/point form (rule 6).
"""

from __future__ import annotations

from pathlib import Path

import build_gooseneck_set_screw as part
import draw_gooseneck_set_screw as drawing
import gooseneck_set_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import DriveStyle, HeadStyle, fastener

BANNED_NOTE_PHRASES = (
    "UOS",
    "DIMENSIONS IN",
    "+/-",
    "DATUM",
    "PERPENDICULAR",
    "RUNOUT",
    "WITHIN",
    "ASME",
    "B18",
    "DEBURR",
    "BREAK SHARP",
    "TITLE BLOCK",
    "COMMERCIAL",
    "GOOSENECK POST",
    "THREAD NOT MODELED",
    "REFERENCE ONLY",
    "WRENCH DRIVEN",
    "DRIVER SLOT",
    "UNDER HEAD",
    "-2A",
)


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck-set-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck-set-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck-set-screw_drawing.png")
    assert DRAWINGS_BY_NAME["gooseneck_set_screw"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The wrench-flats end view carries the across-flats width, the side view
    # the two lengths; together they cover exactly the marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )
    assert set(drawing.END_KEEP) == {"HeadWDim"}


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("gooseneck-set-screw")
    assert spec.THREAD == catalog.thread == "1/4-20"
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    # Blind review: "1/4-20 UNC" -- the 2A class is the title block's.
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    source = _source()
    assert "add_thread_leader(" in source
    assert "designation=THREAD_DESIGNATION" in source
    assert '"1/4-20' not in source
    assert spec.THREAD_DESIGNATION not in spec.DRAWING_NOTES
    assert "ShankDia" not in drawing.SIDE_KEEP
    assert drawing.DIMENSION_CALLOUTS == {}


def test_catalog_row_is_the_period_square_head_black_screw() -> None:
    # Book p.45 spec, reused from the deleted gooseneck-clamp's screw: square
    # head, wrench-driven, black oxide.
    catalog = fastener("gooseneck-set-screw")
    assert catalog.head is HeadStyle.SQUARE
    assert catalog.drive is DriveStyle.EXTERNAL_SQUARE
    assert catalog.finish == "black"


def test_contract_geometry_matches_the_top_frame_rederive() -> None:
    # Top-frame contract: 1/4-20 x 16 under-head, square head 10 x 10 x 6.
    assert spec.SHANK_LEN == 16.0
    assert spec.HEAD_AF == 10.0
    assert spec.HEAD_H == 6.0


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    assert "side_keep=SIDE_KEEP" in _source()


def test_view_annotations_follow_the_machinist() -> None:
    # The thread designation is leadered to the shank through the recipe's
    # decorate hook; the profile carries the axis centerline.  A square head
    # has no rim to center-mark or to end a diameter leader at.
    source = _source()
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing.RECIPE.side_centerline_face_xy == drawing.SIDE_AXIS_FACE_XY
    assert "add_circle_center_mark(" not in source
    assert "end_diameter_leaders_at_rim(" not in source
    assert drawing.THREAD_NOTE_XY[0] < drawing.SIDE_CENTER[0]
    assert all(xy[0] > drawing.SIDE_CENTER[0] for xy in drawing.SIDE_KEEP.values())


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    # The across-flats and height are dimensions and "WRENCH DRIVEN" restated
    # the drawn head, so the note carries only the thread extent and the
    # head/point form.
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 2
    assert max(map(len, lines)) < 80
    assert lines[0] == "THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    assert lines[1] == "SQUARE HEAD; PLAIN FLAT POINT."
    for value in (spec.HEAD_AF, spec.HEAD_H, spec.SHANK_LEN):
        assert f"{value:.2f}" not in notes, value
    for banned in BANNED_NOTE_PHRASES:
        assert banned not in notes, banned
    assert spec.END_VIEW_NOTE == "WRENCH-FLATS VIEW"


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
    assert "build_fastener_sheet(" in source
    assert drawing.RECIPE.scale == drawing.SHEET_SCALE == (5.0, 1.0)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck-set-screw")
    assert config["number"] == "MHA-118"
    assert config["material"] == config["material_specification"]
    assert "black oxide" in config["finish"]
    assert int(config["quantity"]) == 1
