"""Offline contracts for the cone-tip-bushing drawing.

The print follows cad/docs/drawing-simplicity-policy.md: no datums, frames,
bands or roughness symbols on an axial spacer in an adjuster-screw take-up
stack; the drilled bore says DRILL on the callout and the title block's
DRILLED HOLES row governs it; OD, bore and length all read on SECTION A-A
(rule 7), the end view carries only the cutting line.
"""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_bushing as part
import cone_tip_bushing_spec
import draw_cone_tip_bushing as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-bushing_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_bushing"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SECTION_KEEP_OFFSETS)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.OUTER_DIA, drawing.BORE_DIA, drawing.LENGTH) == (
        cone_tip_bushing_spec.OUTER_DIA,
        cone_tip_bushing_spec.BORE_DIA,
        cone_tip_bushing_spec.LENGTH,
    )


def test_every_dimension_reads_on_the_axial_section() -> None:
    # Machinist review 2026-09-02: the OD was dimensioned across the end view,
    # crowding the tiny bore's leaders. The side view is now SECTION A-A
    # through the axis (axis horizontal), carrying OD, bore and length; the
    # end view keeps nothing and is never curated (SolidWorks inserts each
    # marked dimension into one view only).
    assert drawing.END_KEEP == {}
    assert set(drawing.SECTION_KEEP_OFFSETS) == {"ODDim", "BoreDiaDim", "Depth"}
    assert drawing.SECTION_KEEP_OFFSETS["ODDim"][0] > 0.0
    assert drawing.SECTION_KEEP_OFFSETS["BoreDiaDim"][0] < 0.0
    assert drawing.SECTION_KEEP_OFFSETS["Depth"][1] > drawing.END_RADIUS
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1 == drawing.END_CENTER[0]
    assert y0 > drawing.END_CENTER[1] + drawing.END_RADIUS
    assert y1 < drawing.END_CENTER[1] - drawing.END_RADIUS
    source = _source()
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    # The sleeve runs y 0..LENGTH, so the layout origin is the projected
    # mid-length axis point, not the model origin.
    assert "(0.0, LENGTH / 2000.0, 0.0)" in source
    assert "curate_view_dimensions(\n        adapter, end" not in source
    assert 'place_view(adapter, str(SOURCE), "*Front"' not in source
    assert "add_view_centerline(" not in source


def test_bore_is_a_plain_drill_at_the_block_tolerance() -> None:
    # Harvey #13: the callout says DRILL and the fraction. The title block's
    # DRILLED HOLES row governs the size and its .XX row the length: an axial
    # spacer the adjuster screw loads against carries no band of its own and
    # prints no three-decimal "hold it" (review 2026-09-02).
    assert drawing.DIMENSION_CALLOUTS == {"BoreDiaDim": "DRILL THRU (1/32 IN)"}
    assert cone_tip_bushing_spec.BORE_DIA == 0.03125 * 25.4
    assert not hasattr(cone_tip_bushing_spec, "BORE_DIA_BAND")
    assert not hasattr(cone_tip_bushing_spec, "LENGTH_TOLERANCE_MM")
    assert not hasattr(drawing, "DIMENSION_PRECISION")
    assert "set_dimension_precision(" not in _source()
    assert model_toleranced_dimensions(part) == {}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_tip_bushing_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The one note says what the bore rides (a MATES WITH line); chucking is
    # the shop's call (review 2026-09-02).
    assert notes.startswith("MATES WITH MHA-014")
    assert "ONE SETTING" not in notes
    # The drill size rides the bore callout, not the notes.
    for banned in ("1/32", "0.794", "WITHIN", "+/-", "UOS", "DATUM", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    """An axial spacer: no datums, no frames, no Ra (policy rules 3, 5). The
    tip stub is located by the tip block, and a drilled 0.79 hole is not held
    to Ra 1.6 without reaming (review 2026-09-02)."""
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_tip_bushing_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(cone_tip_bushing_spec, "GEOMETRIC_CONTROLS")
    assert cone_tip_bushing_spec.SURFACE_FINISHES == ()
    assert "roughness_ra=" not in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (end, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    assert _source().count("scale=(8, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-bushing")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
